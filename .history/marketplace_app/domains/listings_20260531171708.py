from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from marketplace_app.forms import CommentForm, ListingForm
from marketplace_app.models import Cart, CartItem, Category, Listing, ListingImage, Order, OrderItem, TradeRequest


PROCESSING_ORDER_STATUSES = [Order.PENDING_PAYMENT, Order.PAID]
PROCESSING_TRADE_STATUSES = [TradeRequest.PENDING, TradeRequest.NEGOTIATING, TradeRequest.APPROVED]


def _listing_is_locked(listing):
    has_active_order = OrderItem.objects.filter(
        listing=listing,
        order__status__in=PROCESSING_ORDER_STATUSES,
    ).exists()

    has_active_trade = TradeRequest.objects.filter(
        listing=listing,
        status__in=PROCESSING_TRADE_STATUSES,
    ).exists()

    return has_active_order or has_active_trade


def home(request):
    category_slug = request.GET.get('categoria')
    search_query = request.GET.get('q', '').strip()
    selected_category = None
    cart_listing_ids = set()

    def build_page_url(page_param, page_number):
        params = request.GET.copy()
        if page_number and page_number > 1:
            params[page_param] = page_number
        else:
            params.pop(page_param, None)

        query_string = params.urlencode()
        return f'?{query_string}' if query_string else request.path

    carousel_page_size = 15

    carousel_querysets = [
        {
            'key': 'latest',
            'title': 'Últimos Produtos',
            'icon': 'slideshow',
            'page_param': 'latest_page',
            'queryset': Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at'),
        },
        {
            'key': 'featured',
            'title': 'Produtos em Destaque',
            'icon': 'star',
            'page_param': 'featured_page',
            'queryset': Listing.objects.prefetch_related('images').filter(status='active').filter(
                models.Q(is_featured=True) | models.Q(is_store_featured=True)
            ).order_by('-created_at'),
        },
        {
            'key': 'sale',
            'title': 'Ofertas para Compra',
            'icon': 'shopping_cart',
            'page_param': 'sale_page',
            'queryset': Listing.objects.prefetch_related('images').filter(
                status='active',
                listing_type__in=[Listing.SALE, Listing.BOTH],
            ).order_by('-created_at'),
        },
        {
            'key': 'trade',
            'title': 'Itens para Troca',
            'icon': 'handshake',
            'page_param': 'trade_page',
            'queryset': Listing.objects.prefetch_related('images').filter(
                status='active',
                listing_type__in=[Listing.TRADE, Listing.BOTH],
            ).order_by('-created_at'),
        },
    ]

    carousel_sections = []
    for carousel in carousel_querysets:
        paginator = Paginator(carousel['queryset'], carousel_page_size)
        page_number = request.GET.get(carousel['page_param']) or 1
        page_obj = paginator.get_page(page_number)

        carousel_sections.append({
            'key': carousel['key'],
            'title': carousel['title'],
            'icon': carousel['icon'],
            'page_param': carousel['page_param'],
            'page_obj': page_obj,
            'prev_url': build_page_url(carousel['page_param'], page_obj.previous_page_number()) if page_obj.has_previous() else None,
            'next_url': build_page_url(carousel['page_param'], page_obj.next_page_number()) if page_obj.has_next() else None,
        })

    featured_products = Listing.objects.prefetch_related('images').filter(
        status='active'
    ).filter(
        models.Q(is_featured=True) | models.Q(is_store_featured=True)
    ).order_by('-created_at')[:12]

    all_products = Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at')

    if search_query:
        all_products = all_products.filter(
            models.Q(title__icontains=search_query)
            | models.Q(description__icontains=search_query)
            | models.Q(category__name__icontains=search_query)
            | models.Q(seller__username__icontains=search_query)
        )

    if category_slug and category_slug != 'todos':
        try:
            selected_category = Category.objects.get(slug=category_slug)
            all_products = all_products.filter(category=selected_category)
        except Category.DoesNotExist:
            pass

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).prefetch_related('items').first()
        if cart:
            cart_listing_ids = set(cart.items.values_list('listing_id', flat=True))

    categories = Category.objects.all()
    active_listings_count = all_products.count()
    featured_count = featured_products.count()
    categories_count = categories.count()

    return render(request, 'home.html', {
        'carousel_sections': carousel_sections,
        'featured_products': featured_products,
        'anuncios': all_products,
        'categories': categories,
        'selected_category': selected_category,
        'search_query': search_query,
        'cart_listing_ids': cart_listing_ids,
        'active_listings_count': active_listings_count,
        'featured_count': featured_count,
        'categories_count': categories_count,
    })


@login_required
def my_listings(request):
    listings = request.user.listings.order_by('-created_at')
    return render(request, 'marketplace_app/my_listings.html', {
        'listings': listings,
    })


@login_required
def edit_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if _listing_is_locked(listing):
        messages.error(request, 'Este anúncio já está vinculado a uma compra ou troca em andamento e não pode ser editado.')
        return redirect('my_listings')

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            for image in form.cleaned_data.get('images', []):
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
def delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method == 'POST':
        listing.delete()
        return redirect('my_listings')
    return redirect('edit_listing', pk=pk)


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