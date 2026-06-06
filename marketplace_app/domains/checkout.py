import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.crypto import get_random_string
from django.shortcuts import redirect, render

from marketplace_app.forms import CheckoutForm
from marketplace_app.models import Cart, CartItem, Order, Address
from marketplace_app.view_helpers import process_buy_checkout, process_trade_only
from marketplace_app.shipping import SHIPPING_INFO, calculate_shipping


def _saved_addresses_payload(user):
    """Lista de endereços salvos + JSON para preencher o formulário via JS."""
    addresses = list(Address.objects.filter(user=user))
    payload = json.dumps([
        {
            'id': a.id,
            'label': a.label or 'Endereço',
            'recipient_name': a.recipient_name,
            'recipient_phone': a.recipient_phone,
            'postal_code': a.postal_code,
            'street': a.street,
            'number': a.number,
            'complement': a.complement,
            'neighborhood': a.neighborhood,
            'city': a.city,
            'state': a.state,
            'is_default': a.is_default,
        }
        for a in addresses
    ])
    return addresses, payload


def _shipping_costs_json():
    return json.dumps({method: float(info['cost']) for method, info in SHIPPING_INFO.items()})


CHECKOUT_SESSION_KEY = 'checkout_pending_purchase'

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


@login_required
def checkout_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('listing', 'listing__seller').prefetch_related('listing__images').all()
    buy_items = [item for item in items if item.desired_action == CartItem.BUY]
    trade_items = [item for item in items if item.desired_action == CartItem.TRADE]
    checkout_mode = request.GET.get('action')
    trade_checkout_mode = checkout_mode == 'trade'
    purchase_items = [] if trade_checkout_mode else buy_items
    trade_only_items = trade_items if trade_checkout_mode or not purchase_items else []
    pending_checkout = _get_pending_checkout(request)

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
                subtotal = sum(item.listing.price for item in purchase_items)
                shipping_cost = calculate_shipping(form.cleaned_data['delivery_method'])
                saved_addresses, addresses_json = _saved_addresses_payload(request.user)
                return render(request, 'marketplace_app/checkout.html', {
                    'form': form,
                    'buy_items': purchase_items,
                    'trade_items': trade_only_items,
                    'subtotal': subtotal,
                    'shipping_cost': shipping_cost,
                    'total': subtotal + shipping_cost,
                    'show_qr_simulation': True,
                    'qr_pattern': SIMULATED_QR_PATTERN,
                    'qr_token': request.session[CHECKOUT_SESSION_KEY]['token'],
                    'saved_addresses': saved_addresses,
                    'addresses_json': addresses_json,
                    'shipping_costs_json': _shipping_costs_json(),
                })
    else:
        form = CheckoutForm(initial={'delivery_method': Order.TO_AGREE})

    subtotal = sum(item.listing.price for item in purchase_items)
    shipping_cost = 0
    if pending_checkout and purchase_items:
        form = CheckoutForm(pending_checkout.get('form_data', {}))
        show_qr_simulation = True
        if form.is_valid():
            shipping_cost = calculate_shipping(form.cleaned_data['delivery_method'])
    else:
        show_qr_simulation = False

    saved_addresses, addresses_json = _saved_addresses_payload(request.user)

    return render(request, 'marketplace_app/checkout.html', {
        'form': form,
        'buy_items': purchase_items,
        'trade_items': trade_only_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total': subtotal + shipping_cost,
        'show_qr_simulation': show_qr_simulation,
        'qr_pattern': SIMULATED_QR_PATTERN if show_qr_simulation else [],
        'qr_token': pending_checkout['token'] if pending_checkout else '',
        'saved_addresses': saved_addresses,
        'addresses_json': addresses_json,
        'shipping_costs_json': _shipping_costs_json(),
    })