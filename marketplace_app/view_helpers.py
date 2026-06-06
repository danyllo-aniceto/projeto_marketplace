import json
import urllib.error
import urllib.request
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.dateparse import parse_date

from .models import Order, OrderItem, Delivery, PaymentTransaction, TradeProposal, TradeRequest, CartItem, Notification, Listing
from .notifications import notify
from .shipping import calculate_shipping


def create_mercado_pago_preference(request, order, order_items):
    access_token = getattr(settings, 'MERCADO_PAGO_ACCESS_TOKEN', '')

    if not access_token:
        return None

    items_payload = []
    for item in order_items:
        items_payload.append({
            'title': item.title_snapshot,
            'quantity': item.quantity,
            'unit_price': float(item.unit_price_snapshot),
            'currency_id': 'BRL',
        })

    payload = {
        'items': items_payload,
        'external_reference': f'order-{order.pk}',
        'back_urls': {
            'success': request.build_absolute_uri(reverse('order_detail', args=[order.pk])),
            'pending': request.build_absolute_uri(reverse('order_detail', args=[order.pk])),
            'failure': request.build_absolute_uri(reverse('order_detail', args=[order.pk])),
        },
        'auto_return': 'approved',
    }

    body = json.dumps(payload).encode('utf-8')
    api_request = urllib.request.Request(
        'https://api.mercadopago.com/checkout/preferences',
        data=body,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(api_request, timeout=15) as response:
            response_data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    return response_data


def process_buy_checkout(request, user, buy_items, form):
    with transaction.atomic():
        order = Order.objects.create(
            buyer=user,
            payment_method=form.cleaned_data['payment_method'],
            delivery_method=form.cleaned_data['delivery_method'],
            notes=form.cleaned_data['notes'],
            total_amount=0,
        )

        items_total = 0
        for item in buy_items:
            OrderItem.objects.create(
                order=order,
                listing=item.listing,
                seller=item.listing.seller,
                title_snapshot=item.listing.title,
                unit_price_snapshot=item.listing.price,
                quantity=1,
            )
            items_total += item.listing.price

            # Decrementa o estoque; esgota o anúncio quando chega a zero.
            listing = Listing.objects.select_for_update().get(pk=item.listing_id)
            listing.stock = max(0, listing.stock - 1)
            if listing.stock == 0:
                listing.status = Listing.SOLD
            Listing.objects.filter(pk=listing.pk).update(stock=listing.stock, status=listing.status)

        shipping_cost = calculate_shipping(form.cleaned_data['delivery_method'])
        order_total = items_total + shipping_cost
        order.total_amount = order_total
        order.save(update_fields=['total_amount'])

        delivery = Delivery.objects.create(
            order=order,
            method=form.cleaned_data['delivery_method'],
            recipient_name=form.cleaned_data['recipient_name'],
            recipient_phone=form.cleaned_data['recipient_phone'],
            postal_code=form.cleaned_data['postal_code'],
            street=form.cleaned_data['street'],
            number=form.cleaned_data['number'],
            complement=form.cleaned_data['complement'],
            neighborhood=form.cleaned_data['neighborhood'],
            city=form.cleaned_data['city'],
            state=form.cleaned_data['state'].upper(),
            shipping_cost=shipping_cost,
            notes=form.cleaned_data['notes'],
        )

        payment_transaction = PaymentTransaction.objects.create(
            order=order,
            gateway=PaymentTransaction.MERCADO_PAGO,
            amount=order_total,
            external_reference=f'order-{order.pk}',
            status=PaymentTransaction.APPROVED,
        )

        order.status = Order.PAID
        order.save(update_fields=['status'])

        if buy_items:
            CartItem.objects.filter(pk__in=[item.pk for item in buy_items]).delete()

        # Notifica cada vendedor sobre a nova venda.
        order_url = reverse('order_detail', args=[order.pk])
        sellers_seen = set()
        for item in order.items.all():
            if item.seller_id in sellers_seen:
                continue
            sellers_seen.add(item.seller_id)
            notify(
                item.seller,
                'Novo pedido recebido',
                f'{user.username} comprou "{item.title_snapshot}". Confirme o envio.',
                url=order_url,
                category=Notification.SALE,
                icon='sell',
                actor=user,
            )

        return order, payment_transaction


def process_trade_only(user, trade_items):
    with transaction.atomic():
        created_trade_requests = []
        for item in trade_items:
            trade_request = TradeRequest.objects.create(
                requester=user,
                counterparty=item.listing.seller,
                listing=item.listing,
                initial_message=f'Pedido iniciado pelo carrinho para {item.listing.title}.',
            )
            # Do not auto-create an initial empty proposal here. The first proposal
            # should be created explicitly by the user on the trade detail page.
            created_trade_requests.append(trade_request)

            notify(
                item.listing.seller,
                'Nova solicitação de troca',
                f'{user.username} quer trocar pelo seu anúncio "{item.listing.title}".',
                url=reverse('trade_request_detail', args=[trade_request.pk]),
                category=Notification.TRADE,
                icon='handshake',
                actor=user,
            )

        if trade_items:
            CartItem.objects.filter(pk__in=[item.pk for item in trade_items]).delete()

        return created_trade_requests


def mercadopago_webhook_handler(payload):
    # payload is a dict parsed from JSON
    data = payload.get('data') or payload.get('resource') or payload
    status_str = None
    preference_id = None
    external_reference = None

    if isinstance(data, dict):
        status_str = data.get('status')
        preference_id = data.get('preference_id') or data.get('id')
        external_reference = data.get('external_reference')

    if not preference_id:
        preference_id = payload.get('preference_id') or payload.get('id')
    if not external_reference:
        external_reference = payload.get('external_reference')

    status_map = {
        'approved': PaymentTransaction.APPROVED,
        'paid': PaymentTransaction.APPROVED,
        'authorized': PaymentTransaction.APPROVED,
        'pending': PaymentTransaction.PENDING,
        'in_process': PaymentTransaction.PROCESSING,
        'processing': PaymentTransaction.PROCESSING,
        'rejected': PaymentTransaction.REJECTED,
        'cancelled': PaymentTransaction.CANCELLED,
        'refunded': PaymentTransaction.REFUNDED,
    }

    new_status = None
    if status_str:
        new_status = status_map.get(status_str.lower())

    tx = None
    if preference_id:
        tx = PaymentTransaction.objects.filter(preference_id=str(preference_id)).first()
    if not tx and external_reference:
        tx = PaymentTransaction.objects.filter(external_reference=str(external_reference)).first()

    if not tx:
        return {'updated': False, 'reason': 'transaction_not_found'}

    if new_status:
        tx.status = new_status
        tx.payload = payload
        tx.save(update_fields=['status', 'payload', 'updated_at'])
        return {'updated': True, 'status': tx.status}

    tx.payload = payload
    tx.save(update_fields=['payload', 'updated_at'])
    return {'updated': True, 'status': tx.status}


def delivery_update_handler(order_pk, payload):
    status_val = payload.get('status')
    tracking = payload.get('tracking_code')
    carrier = payload.get('carrier_name')
    eta = payload.get('estimated_delivery_date')

    try:
        delivery = Delivery.objects.select_related('order').get(order__pk=order_pk)
    except Delivery.DoesNotExist:
        return {'updated': False, 'reason': 'delivery_not_found'}

    allowed_statuses = {s[0] for s in Delivery.STATUS_CHOICES}
    if status_val and status_val not in allowed_statuses:
        return {'updated': False, 'reason': 'invalid_status'}

    if status_val:
        delivery.status = status_val
    if tracking is not None:
        delivery.tracking_code = tracking
    if carrier is not None:
        delivery.carrier_name = carrier
    if eta:
        parsed = parse_date(eta)
        if not parsed:
            return {'updated': False, 'reason': 'invalid_date'}
        delivery.estimated_delivery_date = parsed

    delivery.save(update_fields=['status', 'tracking_code', 'carrier_name', 'estimated_delivery_date', 'updated_at'])
    return {'updated': True, 'status': delivery.status}
