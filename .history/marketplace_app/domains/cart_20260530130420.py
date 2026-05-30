from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from marketplace_app.forms import CartItemActionForm
from marketplace_app.models import Cart, CartItem, Listing


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