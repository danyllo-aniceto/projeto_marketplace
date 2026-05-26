from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import models, IntegrityError, transaction
from django.contrib import messages
from django.urls import reverse
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
)
from .forms import IndividualRegistrationForm, StoreRegistrationForm
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Listing
from .serializers import ListingSerializer
from .forms import ListingForm, CommentForm, UserProfileForm, CommonProfileForm, StoreProfileForm
from .models import Listing, ListingImage, Category, StoreProfile, CommonProfile, Comment, Cart, CartItem, Order, OrderItem, TradeRequest, TradeMessage, PaymentTransaction, Delivery
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import RegisterSerializer
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.utils.dateparse import parse_date

from .view_helpers import (
    create_mercado_pago_preference,
    process_buy_checkout,
    process_trade_only,
    mercadopago_webhook_handler,
    delivery_update_handler,
)


# Mercado Pago preference creation and other helpers live in view_helpers.py


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

    def _process_buy_checkout(user, buy_items, trade_items, form):
        with transaction.atomic():
            order = Order.objects.create(
                buyer=user,
                payment_method=form.cleaned_data['payment_method'],
                delivery_method=form.cleaned_data['delivery_method'],
                notes=form.cleaned_data['notes'],
                total_amount=0,
            )

            order_total = 0
            for item in buy_items:
                OrderItem.objects.create(
                    order=order,
                    listing=item.listing,
                    seller=item.listing.seller,
                    title_snapshot=item.listing.title,
                    unit_price_snapshot=item.listing.price,
                    quantity=1,
                )
                order_total += item.listing.price

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
                notes=form.cleaned_data['notes'],
            )

            payment_transaction = PaymentTransaction.objects.create(
                order=order,
                gateway=PaymentTransaction.MERCADO_PAGO,
                amount=order_total,
                external_reference=f'order-{order.pk}',
            )

            preference_response = create_mercado_pago_preference(request, order, order.items.all())
            if preference_response:
                payment_transaction.preference_id = preference_response.get('id', '')
                payment_transaction.checkout_url = preference_response.get('init_point', '')
                payment_transaction.payload = preference_response
                payment_transaction.status = PaymentTransaction.PROCESSING
                payment_transaction.save(update_fields=['preference_id', 'checkout_url', 'payload', 'status'])

            created_trade_requests = []
            for item in trade_items:
                trade_request = TradeRequest.objects.create(
                    requester=user,
                    counterparty=item.listing.seller,
                    listing=item.listing,
                    initial_message=f'Pedido iniciado pelo carrinho para {item.listing.title}.',
                )
                created_trade_requests.append(trade_request)

            if buy_items:
                CartItem.objects.filter(pk__in=[item.pk for item in buy_items]).delete()
            if trade_items:
                CartItem.objects.filter(pk__in=[item.pk for item in trade_items]).delete()

            return order, payment_transaction, created_trade_requests

    def _process_trade_only(user, trade_items):
        with transaction.atomic():
            created_trade_requests = []
            for item in trade_items:
                trade_request = TradeRequest.objects.create(
                    requester=user,
                    counterparty=item.listing.seller,
                    listing=item.listing,
                    initial_message=f'Pedido iniciado pelo carrinho para {item.listing.title}.',
                )
                created_trade_requests.append(trade_request)

            if trade_items:
                CartItem.objects.filter(pk__in=[item.pk for item in trade_items]).delete()

            return created_trade_requests

    if request.method == 'POST':
        if buy_items:
            form = CheckoutForm(request.POST)
            if form.is_valid():
                order, payment_transaction, created_trade_requests = _process_buy_checkout(request.user, buy_items, trade_items, form)

                messages.success(request, 'Checkout iniciado com sucesso.')
                if created_trade_requests:
                    messages.success(request, 'Solicitações de troca foram criadas.')
                if payment_transaction.checkout_url:
                    return redirect(payment_transaction.checkout_url)
                return redirect('order_detail', pk=order.pk)
        else:
            created_trade_requests = _process_trade_only(request.user, trade_items)
            messages.success(request, 'Solicitações de troca criadas com sucesso.')
            return redirect('trade_requests')
    else:
        form = CheckoutForm(initial={'delivery_method': Order.TO_AGREE})

    return render(request, 'marketplace_app/checkout.html', {
        'form': form,
        'buy_items': buy_items,
        'trade_items': trade_items,
        'total': sum(item.listing.price for item in buy_items),
    })


@login_required
def orders_view(request):
    orders = Order.objects.prefetch_related('items__listing', 'items__seller').select_related('delivery', 'payment_transaction').filter(buyer=request.user).order_by('-created_at')
    return render(request, 'marketplace_app/orders.html', {
        'orders': orders,
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
    trade_requests = TradeRequest.objects.select_related('listing', 'requester', 'counterparty').filter(
        models.Q(requester=request.user) | models.Q(counterparty=request.user)
    ).order_by('-created_at')

    return render(request, 'marketplace_app/trade_requests.html', {
        'trade_requests': trade_requests,
    })


@login_required
def trade_request_detail(request, pk):
    trade_request = get_object_or_404(
        TradeRequest.objects.select_related('listing', 'requester', 'counterparty'),
        pk=pk,
    )

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    trade_messages = trade_request.messages.select_related('sender').order_by('created_at')
    message_form = TradeMessageForm()
    status_form = TradeStatusForm(initial={'status': trade_request.status})

    return render(request, 'marketplace_app/trade_request_detail.html', {
        'trade_request': trade_request,
        'trade_messages': trade_messages,
        'message_form': message_form,
        'status_form': status_form,
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
def trade_request_update_status(request, pk):
    trade_request = get_object_or_404(TradeRequest, pk=pk)

    if request.user not in [trade_request.requester, trade_request.counterparty]:
        return redirect('trade_requests')

    if request.method == 'POST':
        form = TradeStatusForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            allowed_statuses = {TradeRequest.NEGOTIATING}

            if request.user == trade_request.counterparty:
                allowed_statuses.update({TradeRequest.APPROVED, TradeRequest.REJECTED})

            if request.user == trade_request.requester:
                allowed_statuses.add(TradeRequest.CANCELLED)

            if new_status in allowed_statuses:
                trade_request.status = new_status
                trade_request.save(update_fields=['status'])
                messages.success(request, 'Status da negociação atualizado.')
            else:
                messages.error(request, 'Você não pode alterar a negociação para esse status.')
        else:
            messages.error(request, 'Status inválido.')

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

    # attempt to extract useful fields from known mercadopago payload shapes
    data = payload.get('data') or payload.get('resource') or payload
    status_str = None
    preference_id = None
    external_reference = None

    # common shapes: {"type":"payment","data":{"id":..., "status":"approved", "preference_id":"pref_..."}}
    if isinstance(data, dict):
        status_str = data.get('status')
        preference_id = data.get('preference_id') or data.get('id')
        external_reference = data.get('external_reference')

    # fallback: top-level
    if not preference_id:
        preference_id = payload.get('preference_id') or payload.get('id')
    if not external_reference:
        external_reference = payload.get('external_reference')

    # map incoming status to our model choices
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

    # find transaction by preference_id or external_reference
    tx = None
    if preference_id:
        tx = PaymentTransaction.objects.filter(preference_id=str(preference_id)).first()
    if not tx and external_reference:
        # external_reference may be like 'order-<pk>'
        tx = PaymentTransaction.objects.filter(external_reference=str(external_reference)).first()

    if not tx:
        # nothing to update
        return JsonResponse({'updated': False, 'reason': 'transaction_not_found'})

    if new_status:
        tx.status = new_status
        tx.payload = payload
        tx.save(update_fields=['status', 'payload', 'updated_at'])
        return JsonResponse({'updated': True, 'status': tx.status})

    # if we couldn't map a status, preserve payload
    tx.payload = payload
    tx.save(update_fields=['payload', 'updated_at'])
    return JsonResponse({'updated': True, 'status': tx.status})


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

    status_val = payload.get('status')
    tracking = payload.get('tracking_code')
    carrier = payload.get('carrier_name')
    eta = payload.get('estimated_delivery_date')

    try:
        delivery = Delivery.objects.select_related('order').get(order__pk=order_pk)
    except Delivery.DoesNotExist:
        return JsonResponse({'updated': False, 'reason': 'delivery_not_found'}, status=404)

    allowed_statuses = {s[0] for s in Delivery.STATUS_CHOICES}
    if status_val and status_val not in allowed_statuses:
        return JsonResponse({'updated': False, 'reason': 'invalid_status'}, status=400)

    if status_val:
        delivery.status = status_val
    if tracking is not None:
        delivery.tracking_code = tracking
    if carrier is not None:
        delivery.carrier_name = carrier
    if eta:
        parsed = parse_date(eta)
        if not parsed:
            return JsonResponse({'updated': False, 'reason': 'invalid_date'}, status=400)
        delivery.estimated_delivery_date = parsed

    delivery.save(update_fields=['status', 'tracking_code', 'carrier_name', 'estimated_delivery_date', 'updated_at'])
    return JsonResponse({'updated': True, 'status': delivery.status})