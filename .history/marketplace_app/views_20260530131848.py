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