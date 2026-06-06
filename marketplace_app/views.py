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
from .models import Listing, ListingImage, Category, StoreProfile, CommonProfile, Comment, Cart, CartItem, Order, OrderItem, TradeRequest, TradeProposal, TradeFulfillment, TradeMessage, PaymentTransaction, Delivery, TradeProposalImage, Notification
from .notifications import notify
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import RegisterSerializer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse, Http404
from django.utils.dateparse import parse_date

from .view_helpers import (
    process_buy_checkout,
    process_trade_only,
    mercadopago_webhook_handler,
    delivery_update_handler,
)
from .models import TradeDelivery
from .forms import TradeDeliveryForm
from .domains.auth import edit_profile, change_password, user_profile, user_login, user_logout, user_register, account_security
from .domains.listings import home, my_listings, edit_listing, listing_detail, delete_listing, criar_anuncio, report_listing
from .domains.cart import add_to_cart, remove_from_cart, cart_view, update_cart_item_action
from .domains.checkout import checkout_view
from .domains.addresses import addresses_view, address_create, address_edit, address_delete, address_set_default
from .domains.stores import stores_view, store_verification, my_store
from .domains.pages import about, contact, help_center, privacy, terms
from .domains.moderation_panel import moderation_panel, mod_verification, mod_report, mod_users, mod_user, mod_listings, mod_delete_listing


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
    # Compras ativas (do comprador): pagas e ainda não concluídas/canceladas
    purchases = (
        Order.objects
        .prefetch_related('items__listing__images', 'items__seller')
        .select_related('delivery', 'payment_transaction')
        .filter(buyer=request.user)
        .exclude(status__in=[Order.COMPLETED, Order.CANCELLED])
        .order_by('-created_at')
    )

    # Vendas ativas (do vendedor): itens ainda não recebidos, em pedidos não cancelados
    sales = (
        OrderItem.objects
        .select_related('order', 'order__buyer', 'listing')
        .prefetch_related('listing__images')
        .filter(seller=request.user)
        .exclude(status=OrderItem.RECEIVED)
        .exclude(order__status=Order.CANCELLED)
        .order_by('-order__created_at', '-id')
    )

    purchases_page = Paginator(purchases, 8).get_page(request.GET.get('purchase_page', 1))
    sales_page = Paginator(sales, 8).get_page(request.GET.get('sale_page', 1))

    return render(request, 'marketplace_app/orders.html', {
        'purchases_page': purchases_page,
        'sales_page': sales_page,
        'purchase_count': purchases.count(),
        'sale_count': sales.count(),
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
    order = get_object_or_404(
        Order.objects.prefetch_related('items__listing__images', 'items__seller').select_related('delivery', 'payment_transaction'),
        pk=pk,
    )

    items = list(order.items.all())
    is_buyer = order.buyer_id == request.user.id
    seller_item_ids = {item.id for item in items if item.seller_id == request.user.id}
    is_seller = bool(seller_item_ids)

    # Apenas o comprador, um vendedor de algum item, ou staff podem ver o pedido.
    if not (is_buyer or is_seller or request.user.is_staff):
        raise Http404('Pedido não encontrado.')

    delivery = getattr(order, 'delivery', None)
    shipping_cost = delivery.shipping_cost if delivery else 0
    items_total = sum((i.unit_price_snapshot * i.quantity for i in items), 0)

    return render(request, 'marketplace_app/order_detail.html', {
        'order': order,
        'items': items,
        'is_buyer': is_buyer,
        'is_seller': is_seller,
        'seller_item_ids': seller_item_ids,
        'items_total': items_total,
        'shipping_cost': shipping_cost,
        'payment_transaction': getattr(order, 'payment_transaction', None),
        'delivery': delivery,
    })


def _maybe_complete_order(order):
    """Conclui o pedido quando todos os itens foram recebidos."""
    items = list(order.items.all())
    if items and all(item.status == OrderItem.RECEIVED for item in items):
        if order.status != Order.COMPLETED:
            order.status = Order.COMPLETED
            order.save(update_fields=['status'])
        delivery = getattr(order, 'delivery', None)
        if delivery and delivery.status != Delivery.DELIVERED:
            delivery.status = Delivery.DELIVERED
            delivery.delivered_at = timezone.now()
            delivery.save(update_fields=['status', 'delivered_at'])
        return True
    return False


@login_required
@require_POST
def confirm_shipment(request, pk, item_pk):
    """Vendedor confirma o envio do seu item."""
    order = get_object_or_404(Order, pk=pk)
    item = get_object_or_404(OrderItem, pk=item_pk, order=order, seller=request.user)

    if order.status == Order.PAID and item.status == OrderItem.PENDING_SHIPMENT:
        item.status = OrderItem.SHIPPED
        item.shipped_at = timezone.now()
        item.save(update_fields=['status', 'shipped_at'])

        # Marca a entrega como em trânsito assim que algo é enviado.
        delivery = getattr(order, 'delivery', None)
        if delivery and delivery.status in (Delivery.PENDING, Delivery.PREPARING):
            delivery.status = Delivery.IN_TRANSIT
            delivery.save(update_fields=['status'])

        notify(
            order.buyer,
            'Item enviado',
            f'"{item.title_snapshot}" foi enviado pelo vendedor. Confirme quando receber.',
            url=reverse('order_detail', args=[order.pk]),
            category=Notification.PURCHASE,
            icon='local_shipping',
            actor=request.user,
        )

        messages.success(request, f'Envio de "{item.title_snapshot}" confirmado.')
    else:
        messages.error(request, 'Não foi possível confirmar o envio deste item.')

    return redirect('order_detail', pk=pk)


@login_required
@require_POST
def confirm_receipt(request, pk, item_pk):
    """Comprador confirma o recebimento de um item."""
    order = get_object_or_404(Order, pk=pk, buyer=request.user)
    item = get_object_or_404(OrderItem, pk=item_pk, order=order)

    if item.status == OrderItem.SHIPPED:
        item.status = OrderItem.RECEIVED
        item.received_at = timezone.now()
        item.save(update_fields=['status', 'received_at'])

        order_url = reverse('order_detail', args=[order.pk])
        notify(
            item.seller,
            'Recebimento confirmado',
            f'{order.buyer.username} confirmou o recebimento de "{item.title_snapshot}".',
            url=order_url,
            category=Notification.SALE,
            icon='check_circle',
            actor=request.user,
        )

        if _maybe_complete_order(order):
            messages.success(request, 'Recebimento confirmado. Pedido concluído!')
        else:
            messages.success(request, f'Recebimento de "{item.title_snapshot}" confirmado.')
    else:
        messages.error(request, 'Este item ainda não foi enviado.')

    return redirect('order_detail', pk=pk)


@login_required
def payments_view(request):
    user = request.user
    entries = []

    # ----- SAÍDAS: compras pagas -----
    purchases = (
        Order.objects.filter(buyer=user, status__in=[Order.PAID, Order.COMPLETED])
        .prefetch_related('items')
    )
    for o in purchases:
        titles = ', '.join(i.title_snapshot for i in o.items.all()[:3])
        entries.append({
            'date': o.created_at, 'kind': 'Compra', 'direction': 'out',
            'amount': o.total_amount, 'icon': 'shopping_bag',
            'title': f'Compra #{o.id}', 'detail': titles,
            'url': reverse('order_detail', args=[o.id]),
        })

    # ----- ENTRADAS: vendas (itens em pedidos pagos/concluídos) -----
    sales = (
        OrderItem.objects.filter(seller=user, order__status__in=[Order.PAID, Order.COMPLETED])
        .select_related('order')
    )
    for it in sales:
        entries.append({
            'date': it.order.created_at, 'kind': 'Venda', 'direction': 'in',
            'amount': it.unit_price_snapshot * it.quantity, 'icon': 'sell',
            'title': it.title_snapshot, 'detail': f'Pedido #{it.order_id}',
            'url': reverse('order_detail', args=[it.order_id]),
        })

    # ----- TROCAS com dinheiro concluídas (entrada para quem recebe, saída para quem paga) -----
    fulfillments = (
        TradeFulfillment.objects
        .filter(payment_status=TradeFulfillment.COMPLETED, payment_amount__gt=0)
        .select_related('trade_request__listing', 'trade_request__requester',
                        'trade_request__counterparty', 'agreed_proposal')
    )
    for tf in fulfillments:
        payer = tf.agreed_proposal.get_cash_payer_user() if tf.agreed_proposal else None
        if payer is None:
            continue
        tr = tf.trade_request
        receiver = tr.counterparty if payer.id == tr.requester_id else tr.requester
        when = tf.confirmed_at or tf.payment_confirmed_at or tf.created_at
        base = {
            'date': when, 'kind': 'Troca', 'amount': tf.payment_amount,
            'icon': 'swap_horiz', 'title': f'Troca: {tr.listing.title}',
            'url': reverse('trade_request_detail', args=[tr.id]),
        }
        if payer.id == user.id:
            entries.append({**base, 'direction': 'out', 'detail': f'Valor pago a {receiver.username}'})
        elif receiver.id == user.id:
            entries.append({**base, 'direction': 'in', 'detail': f'Recebido de {payer.username}'})

    entries.sort(key=lambda e: e['date'], reverse=True)

    spent = sum((e['amount'] for e in entries if e['direction'] == 'out'), 0)
    earned = sum((e['amount'] for e in entries if e['direction'] == 'in'), 0)

    tab = request.GET.get('tab', 'all')
    if tab == 'in':
        filtered = [e for e in entries if e['direction'] == 'in']
    elif tab == 'out':
        filtered = [e for e in entries if e['direction'] == 'out']
    else:
        filtered = entries

    page_obj = Paginator(filtered, 15).get_page(request.GET.get('page', 1))

    return render(request, 'marketplace_app/payments.html', {
        'page_obj': page_obj,
        'spent': spent,
        'earned': earned,
        'balance': earned - spent,
        'tab': tab,
        'in_count': sum(1 for e in entries if e['direction'] == 'in'),
        'out_count': sum(1 for e in entries if e['direction'] == 'out'),
        'total_count': len(entries),
    })


@login_required
def notifications_view(request):
    qs = Notification.objects.filter(recipient=request.user)
    tab = request.GET.get('tab', 'all')
    if tab == 'unread':
        qs = qs.filter(is_read=False)

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page', 1))
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return render(request, 'marketplace_app/notifications.html', {
        'page_obj': page_obj,
        'tab': tab,
        'unread_count': unread_count,
        'total_count': Notification.objects.filter(recipient=request.user).count(),
    })


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect(notification.url or 'notifications')


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'unread': 0})
    messages.success(request, 'Todas as notificações foram marcadas como lidas.')
    return redirect('notifications')


@login_required
@require_POST
def notification_mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'ok': True, 'unread': unread})


@login_required
def notifications_feed(request):
    from django.utils.timesince import timesince
    qs = Notification.objects.filter(recipient=request.user)
    unread = qs.filter(is_read=False).count()
    items = []
    for n in qs[:8]:
        items.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'open_url': reverse('notification_open', args=[n.id]),
            'icon': n.icon,
            'category': n.category,
            'is_read': n.is_read,
            'time_ago': timesince(n.created_at),
        })
    return JsonResponse({'unread': unread, 'items': items})


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