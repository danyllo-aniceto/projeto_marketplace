from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db import transaction
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone

from marketplace_app.models import Notification
from marketplace_app.notifications import notify


def _trade_other_user(trade_request, user):
    return trade_request.counterparty if user.id == trade_request.requester_id else trade_request.requester


def _notify_trade(recipient, title, message, trade_request, actor, icon='handshake'):
    notify(
        recipient, title, message,
        url=reverse('trade_request_detail', args=[trade_request.pk]),
        category=Notification.TRADE, icon=icon, actor=actor,
    )

from marketplace_app.forms import (
    TradeMessageForm,
    TradeProposalForm,
    TradeFulfillmentForm,
    TradeDeliveryForm,
)
from marketplace_app.models import (
    TradeRequest,
    TradeProposal,
    TradeFulfillment,
    TradeMessage,
    TradeDelivery,
    TradeProposalImage,
    Listing,
    Order,
)
from marketplace_app.domains.checkout import SIMULATED_QR_PATTERN


TRADE_CHECKOUT_SESSION_KEY = 'trade_checkout_pending'
TRADE_FINAL_STATUSES = [TradeRequest.CANCELLED, TradeRequest.COMPLETED, TradeRequest.REJECTED]


def _clear_trade_checkout(request):
    request.session.pop(TRADE_CHECKOUT_SESSION_KEY, None)
    request.session.modified = True


def _store_trade_checkout(request, trade_request, fulfillment, form):
    request.session[TRADE_CHECKOUT_SESSION_KEY] = {
        'trade_request_id': trade_request.pk,
        'fulfillment_id': fulfillment.pk,
        'form_data': form.data.dict(),
        'token': get_random_string(12),
    }
    request.session.modified = True


def _get_trade_checkout(request):
    return request.session.get(TRADE_CHECKOUT_SESSION_KEY)


def _get_trade_deliveries(trade_request):
    return {
        delivery.user_id: delivery
        for delivery in TradeDelivery.objects.filter(trade_request=trade_request).select_related('user')
    }


def _can_complete_trade(fulfillment, deliveries):
    if len(deliveries) < 2:
        return False

    if any(delivery.status != TradeDelivery.DELIVERED for delivery in deliveries.values()):
        return False

    if fulfillment.payment_amount > 0 and fulfillment.payment_status != TradeFulfillment.COMPLETED:
        return False

    return True


def _is_trade_final(trade_request):
    return trade_request.status in TRADE_FINAL_STATUSES


def _get_trade_next_actor(trade_request, latest_proposal=None):
    # The first proposal is always sent by the requester (who wants to trade for the
    # listing). After that, the turn alternates between the two participants.
    if latest_proposal is None:
        return trade_request.requester
    return trade_request.counterparty if latest_proposal.proposer_id == trade_request.requester_id else trade_request.requester


def _get_trade_proposal_state(request, trade_request, proposals):
    latest_proposal = proposals.first()
    is_active_negotiation = trade_request.status in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]
    next_actor = None if _is_trade_final(trade_request) or not is_active_negotiation else _get_trade_next_actor(trade_request, latest_proposal)
    is_user_turn = bool(next_actor and request.user.id == next_actor.id)
    is_requester = request.user.id == trade_request.requester_id
    is_owner = request.user.id == trade_request.counterparty_id

    # Either participant can accept the latest proposal, as long as it was made by the
    # other side and the negotiation is still active.
    can_accept_proposal = (
        latest_proposal is not None
        and is_active_negotiation
        and latest_proposal.proposer_id != request.user.id
    )

    return {
        'latest_proposal': latest_proposal,
        'next_actor': next_actor,
        'can_create_proposal': is_user_turn and is_active_negotiation,
        'can_accept_proposal': can_accept_proposal,
        'can_reject_trade': is_user_turn and is_active_negotiation and latest_proposal is not None,
        'can_cancel_trade': is_requester and is_active_negotiation,
        'proposal_prompt': (
            'Descreva o que você oferece — um produto, um valor em dinheiro ou ambos — para iniciar a negociação.'
            if latest_proposal is None
            else 'Responda com uma contraproposta: ajuste o produto, o valor ou ambos.'
        ),
        'proposal_button_label': (
            'Enviar proposta'
            if latest_proposal is None
            else 'Enviar contraproposta'
        ),
        'turn_message': (
            'Sua vez de responder.'
            if is_user_turn
            else 'A troca já foi aprovada. Agora siga para o checkout.'
            if trade_request.status == TradeRequest.APPROVED
            else 'Aguardando o solicitante enviar a proposta inicial.'
            if latest_proposal is None
            else 'Aguardando a resposta do outro participante.'
        ),
    }


@login_required
def trade_requests_view(request):
    sent_query = TradeRequest.objects.select_related('listing', 'requester', 'counterparty').prefetch_related('proposals').filter(
        requester=request.user,
        listing__status=Listing.ACTIVE,
    ).exclude(status__in=TRADE_FINAL_STATUSES).order_by('-created_at')

    received_query = TradeRequest.objects.select_related('listing', 'requester', 'counterparty').prefetch_related('proposals').filter(
        counterparty=request.user,
        listing__status=Listing.ACTIVE,
    ).exclude(status__in=TRADE_FINAL_STATUSES).order_by('-created_at')

    sent_page = Paginator(sent_query, 6).get_page(request.GET.get('sent_page') or 1)
    received_page = Paginator(received_query, 6).get_page(request.GET.get('received_page') or 1)

    return render(request, 'marketplace_app/trade_requests.html', {
        'sent_page': sent_page,
        'received_page': received_page,
        'sent_count': sent_query.count(),
        'received_count': received_query.count(),
    })


@login_required
def trade_request_detail(request, pk):
    trade_request = get_object_or_404(
        TradeRequest.objects.select_related('listing', 'requester', 'counterparty', 'fulfillment').prefetch_related('proposals', 'messages__sender'),
        pk=pk,
    )

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if trade_request.listing.status != Listing.ACTIVE and trade_request.status not in TRADE_FINAL_STATUSES:
        trade_request.status = TradeRequest.CANCELLED
        trade_request.save(update_fields=['status'])
        messages.info(request, 'Este anúncio já não está disponível. A negociação foi arquivada.')

    proposals = trade_request.proposals.select_related('proposer').order_by('-created_at')
    trade_messages = trade_request.messages.select_related('sender').order_by('created_at')
    proposal_state = _get_trade_proposal_state(request, trade_request, proposals)
    message_form = TradeMessageForm()
    proposal_form = TradeProposalForm()
    timeline_items = []

    for proposal in proposals:
        cash_payer_user = proposal.get_cash_payer_user()
        timeline_items.append({
            'kind': 'proposal',
            'created_at': proposal.created_at,
            'actor': proposal.proposer.username,
            'is_mine': proposal.proposer_id == request.user.id,
            'title': 'Proposta' if proposal.proposer_id == trade_request.requester_id else 'Contraproposta',
            'description': proposal.item_description or 'Sem produto descrito.',
            'cash_amount': proposal.cash_amount,
            'cash_payer_name': cash_payer_user.username if cash_payer_user else None,
            'cash_payer_is_me': bool(cash_payer_user and cash_payer_user.id == request.user.id),
            'note': proposal.note,
            'images': list(proposal.images.all()),
        })

    for trade_message in trade_messages:
        timeline_items.append({
            'kind': 'message',
            'created_at': trade_message.created_at,
            'actor': trade_message.sender.username,
            'is_mine': trade_message.sender_id == request.user.id,
            'title': 'Mensagem',
            'description': trade_message.content,
            'cash_amount': None,
            'note': '',
            'images': [],
        })

    if hasattr(trade_request, 'fulfillment'):
        fulfillment = trade_request.fulfillment
        timeline_items.append({
            'kind': 'action',
            'created_at': fulfillment.created_at,
            'actor': trade_request.counterparty.username,
            'is_mine': False,
            'title': 'Acordo fechado',
            'description': 'A proposta foi aceita e a troca está pronta para a etapa de entrega.',
            'cash_amount': fulfillment.payment_amount,
            'note': fulfillment.agreed_proposal.item_description if fulfillment.agreed_proposal else '',
            'images': [],
        })

    timeline_items.sort(key=lambda item: item['created_at'], reverse=True)

    # Clareza de quem pagaria o valor adicional (apenas um dos dois):
    # quem propõe dinheiro é quem paga. Usamos a proposta mais recente para a prévia.
    latest_proposal = proposal_state['latest_proposal']
    fulfillment = getattr(trade_request, 'fulfillment', None)
    if fulfillment and fulfillment.agreed_proposal and fulfillment.payment_amount > 0:
        pending_payer = fulfillment.agreed_proposal.get_cash_payer_user()
        pending_cash = fulfillment.payment_amount
    elif latest_proposal and latest_proposal.cash_amount and latest_proposal.cash_amount > 0:
        pending_payer = latest_proposal.get_cash_payer_user()
        pending_cash = latest_proposal.cash_amount
    else:
        pending_payer = None
        pending_cash = 0

    return render(request, 'marketplace_app/trade_request_detail.html', {
        'trade_request': trade_request,
        'proposals': proposals,
        'trade_messages': trade_messages,
        'message_form': message_form,
        'proposal_form': proposal_form,
        'latest_proposal': latest_proposal,
        'next_actor': proposal_state['next_actor'],
        'can_create_proposal': proposal_state['can_create_proposal'],
        'can_accept_proposal': proposal_state['can_accept_proposal'],
        'can_reject_trade': proposal_state['can_reject_trade'],
        'can_cancel_trade': proposal_state['can_cancel_trade'],
        'is_owner': request.user.id == trade_request.counterparty_id,
        'is_requester': request.user.id == trade_request.requester_id,
        'proposal_prompt': proposal_state['proposal_prompt'],
        'proposal_button_label': proposal_state['proposal_button_label'],
        'turn_message': proposal_state['turn_message'],
        'trade_is_final': _is_trade_final(trade_request),
        'fulfillment': fulfillment,
        'timeline_items': timeline_items,
        'pending_payer': pending_payer,
        'pending_cash': pending_cash,
        'pending_payer_is_me': bool(pending_payer and pending_payer.id == request.user.id),
    })


@login_required
def trade_proposal_create(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if trade_request.status not in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]:
        messages.error(request, 'Esta negociação não aceita novas propostas.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        form = TradeProposalForm(request.POST, request.FILES)
        if form.is_valid():
            if _is_trade_final(trade_request):
                messages.error(request, 'Esta negociação já foi encerrada.')
                return redirect('trade_request_detail', pk=pk)

            proposals = trade_request.proposals.select_related('proposer').order_by('-created_at')
            latest_proposal = proposals.first()
            next_actor = _get_trade_next_actor(trade_request, latest_proposal)
            if latest_proposal is None and request.user.id != trade_request.requester_id:
                messages.error(request, 'A primeira proposta deve ser enviada pelo solicitante (quem iniciou a solicitação).')
                return redirect('trade_request_detail', pk=pk)

            if latest_proposal is not None and request.user.id == latest_proposal.proposer_id:
                messages.error(request, 'Aguarde a resposta do outro participante antes de enviar outra proposta.')
                return redirect('trade_request_detail', pk=pk)

            # Only enforce turn-taking when there is a previous proposal
            if latest_proposal is not None and request.user.id != next_actor.id:
                messages.error(request, 'Você não está na vez de propor.')
                return redirect('trade_request_detail', pk=pk)

            proposal = form.save(commit=False)
            proposal.trade_request = trade_request
            proposal.proposer = request.user

            # Quem paga o valor adicional (escolhido por quem propõe).
            if proposal.cash_amount and proposal.cash_amount > 0:
                payer_side = request.POST.get('cash_payer')
                if payer_side not in (TradeProposal.PAYER_REQUESTER, TradeProposal.PAYER_OWNER):
                    # Padrão: quem propõe paga.
                    payer_side = (
                        TradeProposal.PAYER_REQUESTER
                        if request.user.id == trade_request.requester_id
                        else TradeProposal.PAYER_OWNER
                    )
                proposal.cash_payer = payer_side
            else:
                proposal.cash_payer = ''

            proposal.save()
            images = form.cleaned_data.get('images') or []
            for img in images:
                TradeProposalImage.objects.create(proposal=proposal, image=img)
            if trade_request.status == TradeRequest.PENDING:
                trade_request.status = TradeRequest.NEGOTIATING
                trade_request.save(update_fields=['status'])

            _notify_trade(
                _trade_other_user(trade_request, request.user),
                'Nova proposta de troca',
                f'{request.user.username} enviou uma proposta em "{trade_request.listing.title}".',
                trade_request, request.user, icon='swap_horiz',
            )
            messages.success(request, 'Proposta registrada. A negociação continua pendente.')
        else:
            messages.error(request, 'Não foi possível registrar a proposta.')

    return redirect('trade_request_detail', pk=pk)


@login_required
def trade_delivery_create_or_update(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    try:
        delivery = TradeDelivery.objects.get(trade_request=trade_request, user=request.user)
    except TradeDelivery.DoesNotExist:
        delivery = None

    if _is_trade_final(trade_request):
        messages.error(request, 'Esta negociação já foi encerrada.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        form = TradeDeliveryForm(request.POST, instance=delivery)
        if form.is_valid():
            d = form.save(commit=False)
            d.trade_request = trade_request
            d.user = request.user
            d.status = TradeDelivery.DRAFT
            d.save()
            messages.success(request, 'Informações de envio salvas.')
        else:
            messages.error(request, 'Não foi possível salvar as informações de envio.')

    return redirect('trade_request_detail', pk=pk)


@login_required
def trade_proposal_accept(request, pk, proposal_pk):
    trade_request = get_object_or_404(TradeRequest.objects.select_related('listing'), pk=pk)
    proposal = get_object_or_404(TradeProposal.objects.select_related('trade_request'), pk=proposal_pk, trade_request=trade_request)
    latest_proposal = trade_request.proposals.order_by('-created_at', '-id').first()

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if proposal.proposer_id == request.user.id:
        messages.error(request, 'Você não pode aceitar sua própria proposta.')
        return redirect('trade_request_detail', pk=pk)

    if latest_proposal and proposal.pk != latest_proposal.pk:
        messages.error(request, 'Só é possível aceitar a proposta mais recente.')
        return redirect('trade_request_detail', pk=pk)

    if trade_request.status not in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]:
        messages.error(request, 'Esta negociação não pode mais ser aceita.')
        return redirect('trade_request_detail', pk=pk)

    fulfillment, _ = TradeFulfillment.objects.get_or_create(
        trade_request=trade_request,
        defaults={
            'agreed_proposal': proposal,
            'payment_amount': proposal.cash_amount,
            'payment_status': TradeFulfillment.PAYMENT_PENDING if proposal.cash_amount > 0 else TradeFulfillment.DRAFT,
        },
    )
    fulfillment.agreed_proposal = proposal
    fulfillment.payment_amount = proposal.cash_amount
    fulfillment.payment_status = TradeFulfillment.PAYMENT_PENDING if proposal.cash_amount > 0 else TradeFulfillment.DRAFT
    fulfillment.save(update_fields=['agreed_proposal', 'payment_amount', 'payment_status', 'updated_at'])

    trade_request.status = TradeRequest.APPROVED
    trade_request.save(update_fields=['status'])

    _notify_trade(
        proposal.proposer,
        'Proposta aceita!',
        f'{request.user.username} aceitou sua proposta em "{trade_request.listing.title}". Finalize a troca.',
        trade_request, request.user, icon='check_circle',
    )
    messages.success(request, 'Proposta aceita. Agora preencha a entrega e confirme a troca.')
    return redirect('trade_checkout', pk=pk)


@login_required
def trade_request_reject(request, pk):
    trade_request = get_object_or_404(TradeRequest.objects.select_related('listing', 'requester', 'counterparty'), pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if request.method != 'POST':
        return redirect('trade_request_detail', pk=pk)

    if trade_request.status not in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]:
        messages.error(request, 'Esta negociação já foi encerrada.')
        return redirect('trade_request_detail', pk=pk)

    latest_proposal = trade_request.proposals.order_by('-created_at', '-id').first()

    if latest_proposal is None:
        messages.error(request, 'Ainda não há proposta para recusar. Use "Cancelar" para desistir da negociação.')
        return redirect('trade_request_detail', pk=pk)

    next_actor = _get_trade_next_actor(trade_request, latest_proposal)

    if request.user.id != next_actor.id:
        messages.error(request, 'A recusa só pode ser feita por quem está com a vez.')
        return redirect('trade_request_detail', pk=pk)

    trade_request.status = TradeRequest.REJECTED
    trade_request.save(update_fields=['status'])

    if hasattr(trade_request, 'fulfillment'):
        fulfillment = trade_request.fulfillment
        fulfillment.payment_status = TradeFulfillment.CANCELLED
        fulfillment.save(update_fields=['payment_status', 'updated_at'])

    _notify_trade(
        _trade_other_user(trade_request, request.user),
        'Troca recusada',
        f'{request.user.username} recusou a negociação de "{trade_request.listing.title}".',
        trade_request, request.user, icon='thumb_down',
    )
    messages.success(request, 'Negociação recusada com sucesso.')
    return redirect('trade_requests')


@login_required
def trade_request_cancel(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user != trade_request.requester:
        return redirect('trade_request_detail', pk=pk)

    if trade_request.status not in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]:
        messages.error(request, 'Esta negociação já avançou para a etapa de execução.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        trade_request.status = TradeRequest.CANCELLED
        trade_request.save(update_fields=['status'])
        if hasattr(trade_request, 'fulfillment'):
            fulfillment = trade_request.fulfillment
            fulfillment.payment_status = TradeFulfillment.CANCELLED
            fulfillment.save(update_fields=['payment_status', 'updated_at'])
        _notify_trade(
            trade_request.counterparty,
            'Troca cancelada',
            f'{request.user.username} cancelou a negociação de "{trade_request.listing.title}".',
            trade_request, request.user, icon='cancel',
        )
        messages.success(request, 'Negociação cancelada com sucesso.')

    return redirect('trade_requests')


def _trade_address_complete(delivery):
    return bool(delivery and delivery.street and delivery.number and delivery.city and delivery.state)


@login_required
def trade_checkout(request, pk):
    trade_request = get_object_or_404(
        TradeRequest.objects.select_related('listing', 'requester', 'counterparty'),
        pk=pk,
    )

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    fulfillment = getattr(trade_request, 'fulfillment', None)
    if fulfillment is None:
        messages.error(request, 'Esta troca ainda não foi aceita.')
        return redirect('trade_request_detail', pk=pk)

    # Permite ver o checkout quando concluída (estado final feliz); bloqueia os demais finais.
    if trade_request.status != TradeRequest.COMPLETED and _is_trade_final(trade_request):
        messages.error(request, 'Esta negociação foi encerrada.')
        return redirect('trade_request_detail', pk=pk)

    other_user = trade_request.counterparty if request.user == trade_request.requester else trade_request.requester
    deliveries = _get_trade_deliveries(trade_request)
    user_delivery = deliveries.get(request.user.id)
    other_delivery = deliveries.get(other_user.id)

    payment_needed = fulfillment.payment_amount and fulfillment.payment_amount > 0
    payer = fulfillment.agreed_proposal.get_cash_payer_user() if (fulfillment.agreed_proposal and payment_needed) else None
    is_payer = bool(payer and request.user.id == payer.id)
    payment_done = (not payment_needed) or fulfillment.payment_status == TradeFulfillment.COMPLETED

    # ---------------- AÇÕES POST ----------------
    if request.method == 'POST' and trade_request.status != TradeRequest.COMPLETED:
        action = request.POST.get('action')

        if action == 'save_address':
            form = TradeDeliveryForm(request.POST, instance=user_delivery)
            if form.is_valid():
                d = form.save(commit=False)
                d.trade_request = trade_request
                d.user = request.user
                if d.status != TradeDelivery.DELIVERED:
                    d.status = TradeDelivery.DRAFT
                d.save()
                messages.success(request, 'Endereço de entrega salvo.')
            else:
                messages.error(request, 'Verifique os campos do endereço.')
            return redirect('trade_checkout', pk=pk)

        if action == 'confirm_payment':
            both_addr = _trade_address_complete(user_delivery) and _trade_address_complete(other_delivery)
            if not is_payer:
                messages.error(request, 'Somente quem deve o valor adicional pode confirmar o pagamento.')
            elif not both_addr:
                messages.error(request, 'Aguarde os dois endereços serem cadastrados antes de pagar.')
            elif fulfillment.payment_status == TradeFulfillment.COMPLETED:
                messages.info(request, 'O pagamento já foi confirmado.')
            else:
                fulfillment.payment_method = request.POST.get('payment_method') or fulfillment.payment_method or Order.PIX
                fulfillment.payment_status = TradeFulfillment.COMPLETED
                fulfillment.payment_confirmed_at = timezone.now()
                fulfillment.save(update_fields=['payment_method', 'payment_status', 'payment_confirmed_at', 'updated_at'])
                _notify_trade(
                    other_user,
                    'Pagamento da troca confirmado',
                    f'{request.user.username} pagou R$ {fulfillment.payment_amount} na troca de "{trade_request.listing.title}".',
                    trade_request, request.user, icon='payments',
                )
                messages.success(request, 'Pagamento confirmado. Agora confirme a entrega.')
            return redirect('trade_checkout', pk=pk)

        if action == 'confirm_delivery':
            both_addr = _trade_address_complete(user_delivery) and _trade_address_complete(other_delivery)
            if not both_addr:
                messages.error(request, 'É preciso que os dois endereços estejam cadastrados.')
            elif not payment_done:
                messages.error(request, 'Aguarde a confirmação do pagamento adicional.')
            elif user_delivery is None:
                messages.error(request, 'Cadastre seu endereço primeiro.')
            else:
                with transaction.atomic():
                    ud = TradeDelivery.objects.select_for_update().get(pk=user_delivery.pk)
                    ud.status = TradeDelivery.DELIVERED
                    ud.save(update_fields=['status', 'updated_at'])

                    fresh = _get_trade_deliveries(trade_request)
                    if _can_complete_trade(fulfillment, fresh):
                        if fulfillment.payment_status != TradeFulfillment.COMPLETED:
                            fulfillment.payment_status = TradeFulfillment.COMPLETED
                        fulfillment.confirmed_at = timezone.now()
                        fulfillment.save(update_fields=['payment_status', 'confirmed_at', 'updated_at'])

                        trade_request.status = TradeRequest.COMPLETED
                        trade_request.save(update_fields=['status'])
                        # Decrementa o estoque do anúncio trocado; esgota quando chega a zero.
                        # Usa .update() para não re-disparar o full_clean do Listing.
                        listing = Listing.objects.select_for_update().get(pk=trade_request.listing_id)
                        new_stock = max(0, listing.stock - 1)
                        new_status = Listing.SOLD if new_stock == 0 else listing.status
                        Listing.objects.filter(pk=listing.pk).update(stock=new_stock, status=new_status)
                        _notify_trade(
                            other_user,
                            'Troca concluída!',
                            f'A troca de "{trade_request.listing.title}" foi finalizada pelos dois lados.',
                            trade_request, request.user, icon='verified',
                        )
                        messages.success(request, 'Troca concluída! O registro está no histórico.')
                    else:
                        _notify_trade(
                            other_user,
                            'Entrega confirmada pelo outro',
                            f'{request.user.username} confirmou a entrega em "{trade_request.listing.title}". Falta a sua confirmação.',
                            trade_request, request.user, icon='inventory',
                        )
                        messages.success(request, 'Confirmação registrada. Aguardando o outro participante.')
            return redirect('trade_checkout', pk=pk)

        return redirect('trade_checkout', pk=pk)

    # ---------------- GET: calcula a etapa ----------------
    user_has_addr = _trade_address_complete(user_delivery)
    other_has_addr = _trade_address_complete(other_delivery)
    both_addr = user_has_addr and other_has_addr
    user_confirmed = bool(user_delivery and user_delivery.status == TradeDelivery.DELIVERED)
    other_confirmed = bool(other_delivery and other_delivery.status == TradeDelivery.DELIVERED)

    if trade_request.status == TradeRequest.COMPLETED:
        phase = 'done'
    elif not both_addr:
        phase = 'address'
    elif payment_needed and not payment_done:
        phase = 'payment'
    else:
        phase = 'confirm'

    address_form = TradeDeliveryForm(instance=user_delivery)
    qr_token = 'TR-%s-%s' % (trade_request.id, get_random_string(6).upper())

    from marketplace_app.domains.checkout import _saved_addresses_payload
    saved_addresses, addresses_json = _saved_addresses_payload(request.user)

    return render(request, 'marketplace_app/trade_checkout.html', {
        'trade_request': trade_request,
        'fulfillment': fulfillment,
        'address_form': address_form,
        'phase': phase,
        'payment_needed': bool(payment_needed),
        'payment_done': payment_done,
        'payer': payer,
        'is_payer': is_payer,
        'other_user': other_user,
        'user_delivery': user_delivery,
        'other_delivery': other_delivery,
        'user_has_addr': user_has_addr,
        'other_has_addr': other_has_addr,
        'both_addr': both_addr,
        'user_confirmed': user_confirmed,
        'other_confirmed': other_confirmed,
        'qr_pattern': SIMULATED_QR_PATTERN,
        'qr_token': qr_token,
        'saved_addresses': saved_addresses,
        'addresses_json': addresses_json,
    })


@login_required
def trade_message_create(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if _is_trade_final(trade_request):
        messages.error(request, 'Esta negociação já foi encerrada.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        form = TradeMessageForm(request.POST)
        if form.is_valid():
            trade_message = form.save(commit=False)
            trade_message.trade_request = trade_request
            trade_message.sender = request.user
            trade_message.save()
            if trade_request.status == TradeRequest.PENDING:
                trade_request.status = TradeRequest.NEGOTIATING
                trade_request.save(update_fields=['status'])
            _notify_trade(
                _trade_other_user(trade_request, request.user),
                'Nova mensagem na troca',
                f'{request.user.username}: {trade_message.content[:80]}',
                trade_request, request.user, icon='chat',
            )
            messages.success(request, 'Mensagem enviada.')
        else:
            messages.error(request, 'Não foi possível enviar a mensagem.')

    return redirect('trade_request_detail', pk=pk)
