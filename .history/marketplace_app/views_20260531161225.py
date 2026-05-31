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
from .domains.cart import add_to_cart, remove_from_cart, cart_view, update_cart_item_action
from .domains.checkout import checkout_view


# Mercado Pago preference creation and other helpers live in view_helpers.py


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


# Mercado Pago preference creation and other helpers live in view_helpers.py

# Trade-related views/helpers were moved to marketplace_app.domains.trades
from .domains.trades import (
    trade_requests_view,
    trade_request_detail,
    trade_proposal_create,
    trade_delivery_create_or_update,
    trade_proposal_accept,
    trade_request_reject,
    trade_request_cancel,
    trade_checkout,
    trade_message_create,
)

    


@login_required
def criar_anuncio(request):
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            for image in form.cleaned_data.get('images', []):
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