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


# Mercado Pago preference creation and other helpers live in view_helpers.py


CHECKOUT_SESSION_KEY = 'checkout_pending_purchase'
TRADE_CHECKOUT_SESSION_KEY = 'trade_checkout_pending'
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


def home(request):
    # Pegar categoria do slug se fornecida
    category_slug = request.GET.get('categoria')
    search_query = request.GET.get('q', '').strip()
    selected_category = None
    
    # Últimos produtos para o carrossel (últimos 5 criados)
    carousel_products = Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at')[:5]

    # Destaques: anúncios patrocinados ou de lojas
    featured_products = Listing.objects.prefetch_related('images').filter(
        status='active'
    ).filter(
        models.Q(is_featured=True) | models.Q(is_store_featured=True)
    ).order_by('-created_at')[:12]

    # Todos os anúncios (filtrados por categoria se fornecida)
    all_products = Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at')

    if search_query:
        all_products = all_products.filter(
            models.Q(title__icontains=search_query)
            | models.Q(description__icontains=search_query)
            | models.Q(category__name__icontains=search_query)
        )
    
    if category_slug and category_slug != 'todos':
        try:
            selected_category = Category.objects.get(slug=category_slug)
            all_products = all_products.filter(category=selected_category)
        except Category.DoesNotExist:
            pass

    # Categorias cadastradas
    categories = Category.objects.all()

    context = {
        'carousel_products': carousel_products,
        'featured_products': featured_products,
        'anuncios': all_products,
        'categories': categories,
        'selected_category': selected_category,
        'search_query': search_query,
    }

    return render(request, 'home.html', context)


@login_required
def my_listings(request):
    listings = request.user.listings.order_by('-created_at')
    return render(request, 'marketplace_app/my_listings.html', {
        'listings': listings,
    })


@login_required
def edit_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            image = request.FILES.get('image')
            if image:
                ListingImage.objects.create(listing=anuncio, image=image)

            return redirect('my_listings')
    else:
        form = ListingForm(instance=listing, user=request.user)

    return render(request, 'marketplace_app/edit_listing.html', {
        'form': form,
        'listing': listing,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    comment_form = CommentForm()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.listing = listing
            comment.user = request.user
            comment.save()
            return redirect('listing_detail', pk=pk)

    comments = listing.comments.select_related('user').order_by('-created_at')
    in_cart = False

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        in_cart = cart.items.filter(listing=listing).exists()

    return render(request, 'marketplace_app/listing_detail.html', {
        'listing': listing,
        'comments': comments,
        'comment_form': comment_form,
        'in_cart': in_cart,
    })


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
def delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method == 'POST':
        listing.delete()
        return redirect('my_listings')
    return redirect('edit_listing', pk=pk)


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

        order, payment_transaction, created_trade_requests = process_buy_checkout(request, request.user, buy_items, trade_items, form)
        _clear_pending_checkout(request)

        messages.success(request, 'Compra confirmada com sucesso.')
        if created_trade_requests:
            messages.success(request, 'Solicitações de troca foram criadas.')
        return redirect('order_detail', pk=order.pk)

    if request.method == 'POST':
        if buy_items:
            form = CheckoutForm(request.POST)
            if form.is_valid():
                _store_pending_checkout(request, form, buy_items, trade_items)
                return render(request, 'marketplace_app/checkout.html', {
                    'form': form,
                    'buy_items': buy_items,
                    'trade_items': trade_items,
                    'total': sum(item.listing.price for item in buy_items),
                    'show_qr_simulation': True,
                    'qr_pattern': SIMULATED_QR_PATTERN,
                    'qr_token': request.session[CHECKOUT_SESSION_KEY]['token'],
                })
        else:
            created_trade_requests = process_trade_only(request.user, trade_items)
            messages.success(request, 'Solicitações de troca criadas com sucesso.')
            return redirect('trade_requests')
    else:
        form = CheckoutForm(initial={'delivery_method': Order.TO_AGREE})

    if pending_checkout and buy_items:
        form = CheckoutForm(pending_checkout.get('form_data', {}))
        show_qr_simulation = True
    else:
        show_qr_simulation = False

    return render(request, 'marketplace_app/checkout.html', {
        'form': form,
        'buy_items': buy_items,
        'trade_items': trade_items,
        'total': sum(item.listing.price for item in buy_items),
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
            'is_finished': trade_request.status in [TradeRequest.COMPLETED, TradeRequest.CANCELLED],
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
    ).exclude(status__in=[TradeRequest.CANCELLED, TradeRequest.COMPLETED]).order_by('-created_at')

    received_query = TradeRequest.objects.select_related('listing', 'requester', 'counterparty').prefetch_related('proposals').filter(
        counterparty=request.user,
        listing__status=Listing.ACTIVE,
    ).exclude(status__in=[TradeRequest.CANCELLED, TradeRequest.COMPLETED]).order_by('-created_at')

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

    if trade_request.listing.status != Listing.ACTIVE and trade_request.status not in [TradeRequest.COMPLETED, TradeRequest.CANCELLED]:
        trade_request.status = TradeRequest.CANCELLED
        trade_request.save(update_fields=['status'])
        messages.info(request, 'Este anúncio já não está disponível. A negociação foi arquivada.')

    proposals = trade_request.proposals.select_related('proposer').order_by('-created_at')
    trade_messages = trade_request.messages.select_related('sender').order_by('created_at')
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
        'latest_proposal': proposals.first(),
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

    if trade_request.status in [TradeRequest.CANCELLED, TradeRequest.COMPLETED]:
        messages.error(request, 'Esta negociação não aceita novas propostas.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        form = TradeProposalForm(request.POST, request.FILES)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.trade_request = trade_request
            proposal.proposer = request.user
            proposal.save()
            # handle uploaded images
            images = request.FILES.getlist('images')
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

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if proposal.proposer_id == request.user.id:
        messages.error(request, 'Você não pode aceitar sua própria proposta.')
        return redirect('trade_request_detail', pk=pk)

    if trade_request.status in [TradeRequest.CANCELLED, TradeRequest.COMPLETED]:
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
def trade_request_cancel(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user != trade_request.requester:
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

    fulfillment = getattr(trade_request, 'fulfillment', None)
    if fulfillment is None:
        messages.error(request, 'Esta troca ainda não foi aceita.')
        return redirect('trade_request_detail', pk=pk)

    # deliveries for both participants
    deliveries = {d.user_id: d for d in TradeDelivery.objects.filter(trade_request=trade_request)}
    user_delivery = deliveries.get(request.user.id)
    other_user = trade_request.requester if request.user != trade_request.requester else trade_request.counterparty
    other_delivery = deliveries.get(other_user.id)

    trade_checkout_data = _get_trade_checkout(request)

    if request.method == 'POST' and request.POST.get('confirm_trade') == '1':
        if not trade_checkout_data:
            messages.error(request, 'Não há uma troca pendente para confirmar.')
            return redirect('trade_checkout', pk=pk)
        # ensure both deliveries exist before finalizing
        if not user_delivery or not other_delivery:
            messages.error(request, 'Ambas as partes precisam informar o envio antes de confirmar a troca.')
            return redirect('trade_checkout', pk=pk)

        # if payment is required, only the payer (agreed_proposal.proposer) can confirm payment
        payer = fulfillment.agreed_proposal.proposer if fulfillment.agreed_proposal else None
        if fulfillment.payment_amount > 0:
            if request.user != payer:
                messages.error(request, 'Apenas o usuário responsável pelo pagamento pode confirmá-lo.')
                return redirect('trade_checkout', pk=pk)
            fulfillment.payment_status = TradeFulfillment.COMPLETED
            fulfillment.payment_confirmed_at = timezone.now()

        fulfillment.confirmed_at = timezone.now()
        fulfillment.save(update_fields=['payment_status', 'payment_confirmed_at', 'confirmed_at', 'updated_at'])

        trade_request.status = TradeRequest.COMPLETED
        trade_request.save(update_fields=['status'])

        trade_request.listing.status = Listing.SOLD
        trade_request.listing.save(update_fields=['status'])

        _clear_trade_checkout(request)
        messages.success(request, 'Troca confirmada com sucesso.')
        return redirect('trade_request_detail', pk=pk)

    if request.method == 'POST':
        form = TradeFulfillmentForm(request.POST, instance=fulfillment)
        if form.is_valid():
            fulfillment = form.save(commit=False)
            if fulfillment.payment_amount == 0 and fulfillment.trade_request_id:
                fulfillment.payment_status = TradeFulfillment.DRAFT
            fulfillment.save()
            _store_trade_checkout(request, trade_request, fulfillment, form)
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
    })


@login_required
def trade_message_create(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

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
def edit_profile(request):
    user = request.user
    if user.is_store:
        profile, _ = StoreProfile.objects.get_or_create(user=user)
        profile_form_class = StoreProfileForm
    else:
        profile, _ = CommonProfile.objects.get_or_create(user=user)
        profile_form_class = CommonProfileForm

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        profile_form = profile_form_class(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Perfil atualizado com sucesso.')
            return redirect('edit_profile')
    else:
        user_form = UserProfileForm(instance=user)
        profile_form = profile_form_class(instance=profile)

    return render(request, 'users/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'is_store': user.is_store,
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            old_password = form.cleaned_data.get('old_password')
            new_password = form.cleaned_data.get('new_password')
            
            # Verificar se a senha antiga está correta
            if request.user.check_password(old_password):
                try:
                    validate_password(new_password, user=request.user)
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                else:
                    request.user.set_password(new_password)
                    request.user.save()
                    messages.success(request, 'Senha alterada com sucesso!')
                    return redirect('edit_profile')
            else:
                messages.error(request, 'A senha atual está incorreta.')
    else:
        form = ChangePasswordForm()

    return render(request, 'users/change_password.html', {
        'form': form,
    })


def user_profile(request, username):
    User = get_user_model()
    profile_user = get_object_or_404(User, username=username)
    listings = profile_user.listings.filter(status='active').prefetch_related('images').order_by('-created_at')

    profile = None
    if profile_user.is_store:
        profile, _ = StoreProfile.objects.get_or_create(user=profile_user)
    else:
        profile, _ = CommonProfile.objects.get_or_create(user=profile_user)

    return render(request, 'users/user_profile.html', {
        'profile_user': profile_user,
        'profile': profile,
        'listings': listings,
    })


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


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            else:
                request.session.set_expiry(0)  # Browser session
            return redirect('home')
        else:
            messages.error(request, 'Credenciais inválidas.')

    return render(request, 'users/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')


def user_register(request):
    form = None
    form_values = {}
    form_errors = {}

    if request.method == 'POST':
        account_type = request.POST.get('account_type')

        if account_type not in ['individual', 'store']:
            messages.error(request, 'Selecione o tipo de conta antes de continuar.')
            return render(request, 'users/register.html', {'form_values': form_values, 'form_errors': form_errors})

        if account_type == 'individual':
            form = IndividualRegistrationForm(request.POST)
        else:
            form = StoreRegistrationForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()

                if user.is_store:
                    messages.success(request, 'Conta de loja criada com sucesso! Aguarde verificação.')
                else:
                    messages.success(request, 'Conta criada com sucesso! Faça o login.')
                return redirect('login')
            except IntegrityError as error:
                if 'unique' in str(error).lower():
                    messages.error(request, 'Já existe um cadastro com os dados inseridos. Verifique usuário, CPF ou CNPJ.')
                else:
                    messages.error(request, f'Erro ao criar conta: {error}')
        else:
            form_values = request.POST
            form_errors = {k: [str(x) for x in v] for k, v in form.errors.items()}

    return render(request, 'users/register.html', {
        'form_values': form_values,
        'form_errors': form_errors,
    })

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