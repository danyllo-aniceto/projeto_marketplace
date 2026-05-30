from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils import timezone

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
    # If there is no proposal yet, the counterparty should act first (can accept/reject)
    if latest_proposal is None:
        return trade_request.counterparty
    return trade_request.counterparty if latest_proposal.proposer_id == trade_request.requester_id else trade_request.requester


def _get_trade_proposal_state(request, trade_request, proposals):
    latest_proposal = proposals.first()
    is_active_negotiation = trade_request.status in [TradeRequest.PENDING, TradeRequest.NEGOTIATING]
    next_actor = None if _is_trade_final(trade_request) or not is_active_negotiation else _get_trade_next_actor(trade_request, latest_proposal)
    is_user_turn = bool(next_actor and request.user.id == next_actor.id)
    return {
        'latest_proposal': latest_proposal,
        'next_actor': next_actor,
        'can_create_proposal': is_user_turn and is_active_negotiation,
        'can_reject_trade': is_user_turn and is_active_negotiation,
        'can_cancel_trade': request.user.id == trade_request.requester_id and is_active_negotiation,
        'proposal_prompt': (
            'Envie sua proposta inicial para iniciar a negociação.'
            if latest_proposal is None and request.user.id == trade_request.requester_id
            else 'Aguardando a proposta inicial do solicitante.'
            if latest_proposal is None
            else 'Envie um produto, um valor em dinheiro ou ambos para responder à proposta.'
        ),
        'proposal_button_label': (
            'Enviar proposta inicial'
            if latest_proposal is None
            else 'Enviar contraproposta'
        ),
        'turn_message': (
            'Sua vez de responder.'
            if is_user_turn
            else 'A troca já foi aprovada. Agora siga para o checkout.'
            if trade_request.status == TradeRequest.APPROVED
            else 'Aguardando resposta do outro participante.'
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
    fulfillment_form = TradeFulfillmentForm(
        initial={
            'payment_method': Order.PIX,
            'delivery_method': Order.TO_AGREE,
        }
    )
    user_delivery = None
    other_delivery = None
    try:
        user_delivery = TradeDelivery.objects.get(trade_request=trade_request, user=request.user)
    except TradeDelivery.DoesNotExist:
        user_delivery = None
    other_user = trade_request.requester if request.user != trade_request.requester else trade_request.counterparty
    try:
        other_delivery = TradeDelivery.objects.get(trade_request=trade_request, user=other_user)
    except TradeDelivery.DoesNotExist:
        other_delivery = None
    user_delivery_form = TradeDeliveryForm(instance=user_delivery)
    other_delivery_form = TradeDeliveryForm(instance=other_delivery)
    timeline_items = []

    for proposal in proposals:
        timeline_items.append({
            'kind': 'proposal',
            'created_at': proposal.created_at,
            'actor': proposal.proposer.username,
            'title': 'Proposta enviada' if proposal.proposer_id == trade_request.requester_id else 'Contraproposta recebida',
            'description': proposal.item_description or 'Sem produto descrito.',
            'cash_amount': proposal.cash_amount,
            'note': proposal.note,
        })

    for trade_message in trade_messages:
        timeline_items.append({
            'kind': 'message',
            'created_at': trade_message.created_at,
            'actor': trade_message.sender.username,
            'title': 'Mensagem na negociação',
            'description': trade_message.content,
            'cash_amount': None,
            'note': '',
        })

    if hasattr(trade_request, 'fulfillment'):
        fulfillment = trade_request.fulfillment
        timeline_items.append({
            'kind': 'fulfillment',
            'created_at': fulfillment.created_at,
            'actor': trade_request.counterparty.username,
            'title': 'Acordo pronto para checkout',
            'description': 'A negociação foi aceita e está pronta para a etapa de entrega.',
            'cash_amount': fulfillment.payment_amount,
            'note': fulfillment.agreed_proposal.item_description if fulfillment.agreed_proposal else '',
        })

    timeline_items.sort(key=lambda item: item['created_at'], reverse=True)

    return render(request, 'marketplace_app/trade_request_detail.html', {
        'trade_request': trade_request,
        'proposals': proposals,
        'trade_messages': trade_messages,
        'message_form': message_form,
        'proposal_form': proposal_form,
        'fulfillment_form': fulfillment_form,
        'latest_proposal': proposal_state['latest_proposal'],
        'next_actor': proposal_state['next_actor'],
        'can_create_proposal': proposal_state['can_create_proposal'],
        'can_reject_trade': proposal_state['can_reject_trade'],
        'can_cancel_trade': proposal_state['can_cancel_trade'],
        'proposal_prompt': proposal_state['proposal_prompt'],
        'proposal_button_label': proposal_state['proposal_button_label'],
        'turn_message': proposal_state['turn_message'],
        'trade_is_final': _is_trade_final(trade_request),
        'fulfillment': getattr(trade_request, 'fulfillment', None),
        'timeline_items': timeline_items,
        'user_delivery_form': user_delivery_form,
        'other_delivery': other_delivery,
        'other_delivery_form': other_delivery_form,
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
            proposal.save()
            images = form.cleaned_data.get('images') or []
            for img in images:
                TradeProposalImage.objects.create(proposal=proposal, image=img)
            if trade_request.status == TradeRequest.PENDING:
                trade_request.status = TradeRequest.NEGOTIATING
                trade_request.save(update_fields=['status'])
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

    listing_owner = trade_request.listing.seller if hasattr(trade_request, 'listing') else None
    if listing_owner and request.user.id != listing_owner.id:
        messages.error(request, 'Apenas o criador do anúncio pode aceitar a proposta.')
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
        messages.success(request, 'Negociação cancelada com sucesso.')

    return redirect('trade_requests')


@login_required
def trade_checkout(request, pk):
    trade_request = get_object_or_404(
        TradeRequest.objects.select_related('listing', 'requester', 'counterparty'),
        pk=pk,
    )

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if _is_trade_final(trade_request):
        messages.error(request, 'Esta negociação já foi encerrada.')
        return redirect('trade_request_detail', pk=pk)

    fulfillment = getattr(trade_request, 'fulfillment', None)
    if fulfillment is None:
        messages.error(request, 'Esta troca ainda não foi aceita.')
        return redirect('trade_request_detail', pk=pk)

    deliveries = _get_trade_deliveries(trade_request)
    user_delivery = deliveries.get(request.user.id)
    other_user = trade_request.requester if request.user != trade_request.requester else trade_request.counterparty
    other_delivery = deliveries.get(other_user.id)

    trade_checkout_data = _get_trade_checkout(request)

    payer = fulfillment.agreed_proposal.proposer if fulfillment.agreed_proposal else None

    if request.method == 'POST':
        form = TradeFulfillmentForm(request.POST, instance=fulfillment)
        if form.is_valid():
            fulfillment = form.save(commit=False)
            if fulfillment.payment_amount == 0 and fulfillment.trade_request_id:
                fulfillment.payment_status = TradeFulfillment.DRAFT
            fulfillment.save()
            _store_trade_checkout(request, trade_request, fulfillment, form)

            if request.POST.get('confirm_trade') == '1':
                if user_delivery is None:
                    messages.error(request, 'Preencha seus dados de envio antes de confirmar a troca.')
                    return redirect('trade_request_detail', pk=pk)

                with transaction.atomic():
                    fulfillment = TradeFulfillment.objects.select_for_update().get(pk=fulfillment.pk)
                    user_delivery = TradeDelivery.objects.select_for_update().get(trade_request=trade_request, user=request.user)
                    user_delivery.status = TradeDelivery.DELIVERED
                    user_delivery.save(update_fields=['status', 'updated_at'])

                    if fulfillment.payment_amount > 0 and request.user == payer:
                        fulfillment.payment_status = TradeFulfillment.COMPLETED
                        fulfillment.payment_confirmed_at = timezone.now()

                    deliveries = _get_trade_deliveries(trade_request)
                    if _can_complete_trade(fulfillment, deliveries):
                        fulfillment.confirmed_at = timezone.now()
                        fulfillment.save(update_fields=['payment_status', 'payment_confirmed_at', 'confirmed_at', 'updated_at'])

                        trade_request.status = TradeRequest.COMPLETED
                        trade_request.save(update_fields=['status'])

                        trade_request.listing.status = Listing.SOLD
                        trade_request.listing.save(update_fields=['status'])

                        _clear_trade_checkout(request)
                        messages.success(request, 'Troca confirmada com sucesso. O histórico foi atualizado.')
                        return redirect('trade_request_detail', pk=pk)

                    update_fields = ['updated_at']
                    if fulfillment.payment_amount > 0 and request.user == payer:
                        update_fields.extend(['payment_status', 'payment_confirmed_at'])
                    fulfillment.save(update_fields=update_fields)

                messages.success(request, 'Sua confirmação foi registrada. Agora falta a confirmação do outro participante.')
                return redirect('trade_checkout', pk=pk)

            return render(request, 'marketplace_app/trade_checkout.html', {
                'trade_request': trade_request,
                'fulfillment': fulfillment,
                'form': form,
                'show_qr_simulation': fulfillment.payment_amount > 0,
                'ready_to_confirm': fulfillment.payment_amount == 0,
                'qr_pattern': SIMULATED_QR_PATTERN if fulfillment.payment_amount > 0 else [],
                'qr_token': request.session[TRADE_CHECKOUT_SESSION_KEY]['token'],
                'user_delivery': user_delivery,
                'other_delivery': other_delivery,
            })
            messages.error(request, 'Não foi possível salvar os dados da troca.')
    else:
        form = TradeFulfillmentForm(instance=fulfillment, initial={'payment_method': Order.PIX, 'delivery_method': Order.TO_AGREE})

    if trade_checkout_data:
        form = TradeFulfillmentForm(instance=fulfillment, initial=trade_checkout_data.get('form_data', {}))
        show_qr_simulation = fulfillment.payment_amount > 0
        ready_to_confirm = fulfillment.payment_amount == 0
    else:
        show_qr_simulation = False
        ready_to_confirm = False

    return render(request, 'marketplace_app/trade_checkout.html', {
        'trade_request': trade_request,
        'fulfillment': fulfillment,
        'form': form,
        'show_qr_simulation': show_qr_simulation,
        'ready_to_confirm': ready_to_confirm,
        'qr_pattern': SIMULATED_QR_PATTERN if show_qr_simulation else [],
        'qr_token': trade_checkout_data['token'] if trade_checkout_data else '',
        'user_delivery': user_delivery,
        'other_delivery': other_delivery,
        'user_delivery_confirmed': bool(user_delivery and user_delivery.status == TradeDelivery.DELIVERED),
        'other_delivery_confirmed': bool(other_delivery and other_delivery.status == TradeDelivery.DELIVERED),
        'can_finalize_trade': _can_complete_trade(fulfillment, deliveries),
        'payer': payer,
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
            messages.success(request, 'Mensagem enviada.')
        else:
            messages.error(request, 'Não foi possível enviar a mensagem.')

    return redirect('trade_request_detail', pk=pk)
