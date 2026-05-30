from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, IntegrityError, transaction
from django.contrib import messages
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
import json
import urllib.error
import urllib.parse
import urllib.request
from .forms import (
    ListingForm,
    CommentForm,
    UserProfileForm,
    CommonProfileForm,
    StoreProfileForm,
    ChangePasswordForm,
    CartItemActionForm,
    CheckoutForm,
    DeliveryForm,
    TradeMessageForm,
    TradeStatusForm,
    TradeProposalForm,
    TradeFulfillmentForm,
)
from .forms import IndividualRegistrationForm, StoreRegistrationForm
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Listing
from .serializers import ListingSerializer
from .forms import ListingForm, CommentForm, UserProfileForm, CommonProfileForm, StoreProfileForm
from .models import Listing, ListingImage, Category, StoreProfile, CommonProfile, Comment, Cart, CartItem, Order, OrderItem, TradeRequest, TradeProposal, TradeFulfillment, TradeMessage, PaymentTransaction, Delivery, TradeProposalImage
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import RegisterSerializer
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.utils.dateparse import parse_date

from .view_helpers import (
    process_buy_checkout,
    process_trade_only,
    mercadopago_webhook_handler,
    delivery_update_handler,
)
from .models import TradeDelivery
from .forms import TradeDeliveryForm
from .domains.auth import edit_profile, change_password, user_profile, user_login, user_logout, user_register
from .domains.listings import home, my_listings, edit_listing, listing_detail, delete_listing, criar_anuncio


# Mercado Pago preference creation and other helpers live in view_helpers.py


CHECKOUT_SESSION_KEY = 'checkout_pending_purchase'
TRADE_CHECKOUT_SESSION_KEY = 'trade_checkout_pending'
TRADE_FINAL_STATUSES = [TradeRequest.CANCELLED, TradeRequest.COMPLETED, TradeRequest.REJECTED]
SIMULATED_QR_PATTERN = [
    '111111100011100111111',
    '100000100010100100001',
    '101110100111100101101',
    '101110100100100101101',
    '101110100011100101101',
    '100000100000100100001',
    '111111101010101111111',
    '000000000000000000000',
    '101011110010111010101',
    '100010001110001000101',
    '111011101000101110111',
    '100010001110001000001',
    '101011110010111010101',
    '000000000000000000000',
    '111111100011100111111',
]


def _clear_pending_checkout(request):
    request.session.pop(CHECKOUT_SESSION_KEY, None)
    request.session.modified = True


def _store_pending_checkout(request, form, buy_items, trade_items):
    request.session[CHECKOUT_SESSION_KEY] = {
        'form_data': form.data.dict(),
        'token': get_random_string(12),
        'buy_item_ids': [item.pk for item in buy_items],
        'trade_item_ids': [item.pk for item in trade_items],
    }
    request.session.modified = True


def _get_pending_checkout(request):
    return request.session.get(CHECKOUT_SESSION_KEY)


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
    # The first proposal should be created by the user who initiated the solicitation
    if latest_proposal is None:
        return trade_request.requester
    # If the latest proposer was the requester, it's the counterparty's turn, and vice-versa
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
            # If there is no proposal yet, the requester (initiator) should send the first proposal.
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
def add_to_cart(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status='active')
    requested_action = request.GET.get('action', CartItem.BUY)

    if listing.listing_type == Listing.SALE:
        requested_action = CartItem.BUY
    elif listing.listing_type == Listing.TRADE:
        requested_action = CartItem.TRADE
    elif requested_action not in [CartItem.BUY, CartItem.TRADE]:
        requested_action = CartItem.BUY

    if listing.seller.is_store and requested_action == CartItem.TRADE:
        messages.error(request, 'Lojas não aceitam troca.')
        next_url = request.GET.get('next')
        return redirect(next_url) if next_url else redirect('listing_detail', pk=pk)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        listing=listing,
        defaults={'desired_action': requested_action},
    )

    if not created and cart_item.desired_action != requested_action:
        cart_item.desired_action = requested_action
        cart_item.save()

    messages.success(request, 'Item adicionado ao carrinho.')
    next_url = request.GET.get('next')
    return redirect(next_url) if next_url else redirect('cart')


@login_required
def remove_from_cart(request, pk):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.filter(cart=cart, pk=pk).delete()
    return redirect('cart')


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('listing', 'listing__seller', 'listing__category').all().order_by('-added_at')
    buy_items = [item for item in items if item.desired_action == CartItem.BUY]
    trade_items = [item for item in items if item.desired_action == CartItem.TRADE]
    total = sum(item.listing.price for item in buy_items)

    return render(request, 'marketplace_app/cart.html', {
        'cart': cart,
        'items': items,
        'buy_items': buy_items,
        'trade_items': trade_items,
        'total': total,
    })


@login_required
def update_cart_item_action(request, pk):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item = get_object_or_404(CartItem, pk=pk, cart=cart)

    if request.method == 'POST':
        form = CartItemActionForm(request.POST, instance=cart_item)
        if form.is_valid():
            try:
                cart_item = form.save(commit=False)
                cart_item.save()
                messages.success(request, 'Tipo do item atualizado.')
            except ValidationError as error:
                messages.error(request, ' '.join(error.messages))
        else:
            messages.error(request, 'Não foi possível atualizar o item do carrinho.')

    return redirect('cart')


@login_required
def checkout_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('listing', 'listing__seller').all()
    buy_items = [item for item in items if item.desired_action == CartItem.BUY]
    trade_items = [item for item in items if item.desired_action == CartItem.TRADE]
    checkout_mode = request.GET.get('action')
    trade_checkout_mode = checkout_mode == 'trade'
    purchase_items = [] if trade_checkout_mode else buy_items
    trade_only_items = trade_items if trade_checkout_mode or not purchase_items else []
    pending_checkout = _get_pending_checkout(request)

    # Use helper functions from view_helpers for checkout and trade creation

    if request.method == 'POST' and request.POST.get('confirm_purchase') == '1':
        if not pending_checkout:
            messages.error(request, 'Não há uma compra pendente para confirmar.')
            return redirect('checkout')

        pending_buy_ids = set(pending_checkout.get('buy_item_ids', []))
        pending_trade_ids = set(pending_checkout.get('trade_item_ids', []))
        pending_items = items.filter(pk__in=pending_buy_ids | pending_trade_ids)
        buy_items = [item for item in pending_items if item.pk in pending_buy_ids and item.desired_action == CartItem.BUY]
        trade_items = [item for item in pending_items if item.pk in pending_trade_ids and item.desired_action == CartItem.TRADE]

        if not buy_items:
            _clear_pending_checkout(request)
            messages.error(request, 'Os itens da compra não estão mais disponíveis no carrinho.')
            return redirect('checkout')

        form = CheckoutForm(pending_checkout.get('form_data', {}))
        if not form.is_valid():
            _clear_pending_checkout(request)
            messages.error(request, 'Os dados do checkout expiraram. Preencha novamente.')
            return redirect('checkout')

        order, payment_transaction = process_buy_checkout(request, request.user, purchase_items, form)
        _clear_pending_checkout(request)

        messages.success(request, 'Compra confirmada com sucesso.')
        return redirect('order_detail', pk=order.pk)

    if request.method == 'POST':
        if trade_checkout_mode or not purchase_items:
            process_trade_only(request.user, trade_only_items)
            messages.success(request, 'Solicitações de troca criadas com sucesso.')
            return redirect('trade_requests')

        if purchase_items:
            form = CheckoutForm(request.POST)
            if form.is_valid():
                _store_pending_checkout(request, form, purchase_items, [])
                return render(request, 'marketplace_app/checkout.html', {
                    'form': form,
                    'buy_items': purchase_items,
                    'trade_items': trade_only_items,
                    'total': sum(item.listing.price for item in purchase_items),
                    'show_qr_simulation': True,
                    'qr_pattern': SIMULATED_QR_PATTERN,
                    'qr_token': request.session[CHECKOUT_SESSION_KEY]['token'],
                })
    else:
        form = CheckoutForm(initial={'delivery_method': Order.TO_AGREE})

    if pending_checkout and purchase_items:
        form = CheckoutForm(pending_checkout.get('form_data', {}))
        show_qr_simulation = True
    else:
        show_qr_simulation = False

    return render(request, 'marketplace_app/checkout.html', {
        'form': form,
        'buy_items': purchase_items,
        'trade_items': trade_only_items,
        'total': sum(item.listing.price for item in purchase_items),
        'show_qr_simulation': show_qr_simulation,
        'qr_pattern': SIMULATED_QR_PATTERN if show_qr_simulation else [],
        'qr_token': pending_checkout['token'] if pending_checkout else '',
    })


@login_required
def orders_view(request):
    orders = Order.objects.prefetch_related('items__listing', 'items__seller').select_related('delivery', 'payment_transaction').filter(buyer=request.user).order_by('-created_at')
    return render(request, 'marketplace_app/orders.html', {
        'orders': orders,
    })


@login_required
def history_view(request):
    purchase_page_number = request.GET.get('purchase_page') or 1
    sale_page_number = request.GET.get('sale_page') or 1
    sent_trade_page_number = request.GET.get('sent_trade_page') or 1
    received_trade_page_number = request.GET.get('received_trade_page') or 1

    purchases_queryset = Order.objects.prefetch_related(
        'items__listing',
        'items__seller',
    ).select_related(
        'delivery',
        'payment_transaction',
    ).filter(
        buyer=request.user,
    ).order_by('-created_at')

    sales_queryset = OrderItem.objects.select_related(
        'order',
        'order__buyer',
        'listing',
        'seller',
    ).filter(
        seller=request.user,
    ).order_by('-order__created_at', '-id')

    purchases_paginator = Paginator(purchases_queryset, 6)
    sales_paginator = Paginator(sales_queryset, 8)
    sent_trades_queryset = TradeRequest.objects.select_related(
        'listing',
        'requester',
        'counterparty',
    ).prefetch_related(
        models.Prefetch('proposals', queryset=TradeProposal.objects.select_related('proposer').order_by('-created_at')),
    ).filter(
        requester=request.user,
    ).order_by('-created_at')

    received_trades_queryset = TradeRequest.objects.select_related(
        'listing',
        'requester',
        'counterparty',
    ).prefetch_related(
        models.Prefetch('proposals', queryset=TradeProposal.objects.select_related('proposer').order_by('-created_at')),
    ).filter(
        counterparty=request.user,
    ).order_by('-created_at')

    def build_trade_card(trade_request, role):
        proposals = list(trade_request.proposals.all())
        latest_proposal = proposals[0] if proposals else None
        fulfillment = getattr(trade_request, 'fulfillment', None)
        cash_amount = fulfillment.payment_amount if fulfillment else (latest_proposal.cash_amount if latest_proposal else 0)
        return {
            'trade_request': trade_request,
            'role': role,
            'partner': trade_request.counterparty if role == 'requested' else trade_request.requester,
            'proposal_count': len(proposals),
            'latest_proposal': latest_proposal,
            'cash_amount': cash_amount,
            'has_cash': cash_amount > 0,
            'fulfillment': fulfillment,
            'is_finished': trade_request.status in TRADE_FINAL_STATUSES,
        }

    sent_trade_cards = [build_trade_card(trade_request, 'requested') for trade_request in sent_trades_queryset]
    received_trade_cards = [build_trade_card(trade_request, 'received') for trade_request in received_trades_queryset]

    sent_trades_paginator = Paginator(sent_trade_cards, 6)
    received_trades_paginator = Paginator(received_trade_cards, 6)

    purchases_page_obj = purchases_paginator.get_page(purchase_page_number)
    sales_page_obj = sales_paginator.get_page(sale_page_number)
    sent_trades_page_obj = sent_trades_paginator.get_page(sent_trade_page_number)
    received_trades_page_obj = received_trades_paginator.get_page(received_trade_page_number)

    return render(request, 'marketplace_app/history.html', {
        'purchases_page_obj': purchases_page_obj,
        'sales_page_obj': sales_page_obj,
        'sent_trades_page_obj': sent_trades_page_obj,
        'received_trades_page_obj': received_trades_page_obj,
        'purchase_count': purchases_queryset.count(),
        'sale_count': sales_queryset.count(),
        'sent_trade_count': sent_trades_queryset.count(),
        'received_trade_count': received_trades_queryset.count(),
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items__listing', 'items__seller').select_related('delivery', 'payment_transaction'), pk=pk, buyer=request.user)
    return render(request, 'marketplace_app/order_detail.html', {
        'order': order,
        'payment_transaction': getattr(order, 'payment_transaction', None),
        'delivery': getattr(order, 'delivery', None),
    })


@login_required
def delivery_update(request, pk):
    order = get_object_or_404(Order.objects.select_related('delivery'), pk=pk)

    if not request.user.is_staff:
        return redirect('order_detail', pk=pk)

    delivery = getattr(order, 'delivery', None)
    if delivery is None:
        messages.error(request, 'Este pedido ainda não possui entrega registrada.')
        return redirect('order_detail', pk=pk)

    if request.method == 'POST':
        form = DeliveryForm(request.POST, instance=delivery)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entrega atualizada com sucesso.')
            return redirect('order_detail', pk=pk)
    else:
        form = DeliveryForm(instance=delivery)

    return render(request, 'marketplace_app/delivery_update.html', {
        'order': order,
        'form': form,
        'delivery': delivery,
    })


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
    # delivery forms: one per user (if exists)
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
            # The first proposal must be sent by the requester (the user who initiated the solicitation)
            if latest_proposal is None and request.user.id != trade_request.requester_id:
                messages.error(request, 'A primeira proposta deve ser enviada pelo solicitante (quem iniciou a solicitação).')
                return redirect('trade_request_detail', pk=pk)

            if latest_proposal is not None and request.user.id == latest_proposal.proposer_id:
                messages.error(request, 'Aguarde a resposta do outro participante antes de enviar outra proposta.')
                return redirect('trade_request_detail', pk=pk)

            if request.user.id != next_actor.id:
                messages.error(request, 'Você não está na vez de propor.')
                return redirect('trade_request_detail', pk=pk)

            proposal = form.save(commit=False)
            proposal.trade_request = trade_request
            proposal.proposer = request.user
            proposal.save()
            # handle uploaded images
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

    # Only the owner of the listing (counterparty when a user initiated the trade) can accept/finalize a proposal
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

    # deliveries for both participants
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


@login_required
def criar_anuncio(request):
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            # Processar imagem
            image = request.FILES.get('image')
            if image:
                ListingImage.objects.create(listing=anuncio, image=image)

            return redirect('home')
    else:
        form = ListingForm(user=request.user)

    return render(request, 'marketplace_app/criar_anuncio.html', {'form': form})

class ListingListAPIView(generics.ListAPIView):
    queryset = Listing.objects.all().order_by('-created_at')
    serializer_class = ListingSerializer
    permission_classes = [AllowAny]

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Usuário criado com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def mercadopago_webhook(request):
    """Basic webhook endpoint for Mercado Pago events.

    Accepts JSON POSTs with payment info. Tries to find a PaymentTransaction by
    `preference_id` or `external_reference` (exact match) and updates its status.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    result = mercadopago_webhook_handler(payload)
    return JsonResponse(result)


@csrf_exempt
def delivery_update_api(request, order_pk):
    """API to update delivery status and optional fields.

    Expected JSON: {"status": "in_transit", "tracking_code": "XYZ", "carrier_name": "GLS", "estimated_delivery_date": "2026-05-30"}
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    result = delivery_update_handler(order_pk, payload)
    status = 200
    if not result.get('updated'):
        if result.get('reason') == 'delivery_not_found':
            status = 404
        elif result.get('reason') == 'invalid_status' or result.get('reason') == 'invalid_date':
            status = 400

    return JsonResponse(result, status=status)