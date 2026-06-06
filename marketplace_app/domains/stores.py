from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from marketplace_app.models import StoreProfile, Listing, StoreVerificationRequest, OrderItem


User = get_user_model()


@login_required
def stores_view(request):
    search = (request.GET.get('q') or '').strip()

    stores = (
        StoreProfile.objects
        .select_related('user')
        .annotate(active_listings=models.Count(
            'user__listings',
            filter=models.Q(user__listings__status=Listing.ACTIVE),
        ))
    )

    if search:
        stores = stores.filter(
            models.Q(fantasy_name__icontains=search)
            | models.Q(razao_social__icontains=search)
            | models.Q(user__username__icontains=search)
        )

    # Verificadas primeiro, depois por nome.
    stores = stores.order_by('-verified', 'fantasy_name', 'razao_social')

    page_obj = Paginator(stores, 12).get_page(request.GET.get('page', 1))

    return render(request, 'marketplace_app/stores.html', {
        'page_obj': page_obj,
        'search': search,
        'verified_count': StoreProfile.objects.filter(verified=True).count(),
        'total_count': StoreProfile.objects.count(),
    })


@login_required
def my_store(request):
    if not request.user.is_store:
        messages.error(request, 'Apenas contas de loja têm catálogo.')
        return redirect('home')

    profile, _ = StoreProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        from marketplace_app.moderation import find_prohibited, validate_image_upload
        from django.core.exceptions import ValidationError

        description = (request.POST.get('description') or '').strip()
        if find_prohibited(description):
            messages.error(request, 'A descrição contém termos não permitidos.')
            return redirect('my_store')

        banner_file = request.FILES.get('banner')
        if banner_file:
            try:
                validate_image_upload(banner_file)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
                return redirect('my_store')
            profile.banner = banner_file

        profile.description = description
        if request.POST.get('remove_banner') == '1':
            profile.banner = None
        profile.save(update_fields=['description', 'banner'])
        messages.success(request, 'Catálogo atualizado.')
        return redirect('my_store')

    listings = request.user.listings.prefetch_related('images').order_by('-created_at')
    listings_list = list(listings)

    # Insights
    total_products = len(listings_list)
    active_products = sum(1 for l in listings_list if l.is_available)
    sold_out = sum(1 for l in listings_list if l.is_sold_out)
    total_stock = sum(l.stock for l in listings_list)

    completed_items = OrderItem.objects.filter(seller=request.user, status=OrderItem.RECEIVED)
    sales_count = completed_items.count()
    revenue = sum((i.unit_price_snapshot * i.quantity for i in completed_items), 0)

    return render(request, 'marketplace_app/my_store.html', {
        'profile': profile,
        'listings': listings_list,
        'insights': {
            'total_products': total_products,
            'active_products': active_products,
            'sold_out': sold_out,
            'total_stock': total_stock,
            'sales_count': sales_count,
            'revenue': revenue,
        },
    })


@login_required
def store_verification(request):
    if not request.user.is_store:
        messages.error(request, 'Apenas contas de loja podem solicitar verificação.')
        return redirect('home')

    profile, _ = StoreProfile.objects.get_or_create(user=request.user)
    pending = StoreVerificationRequest.objects.filter(
        store=request.user, status=StoreVerificationRequest.PENDING
    ).first()

    if request.method == 'POST':
        if profile.verified:
            messages.info(request, 'Sua loja já é verificada.')
            return redirect('store_verification')
        if pending:
            messages.info(request, 'Você já tem uma solicitação em análise.')
            return redirect('store_verification')

        document = request.FILES.get('document')
        if not document:
            messages.error(request, 'Anexe um documento para solicitar a verificação.')
            return redirect('store_verification')

        StoreVerificationRequest.objects.create(
            store=request.user,
            document=document,
            message=(request.POST.get('message') or '').strip(),
        )
        messages.success(request, 'Solicitação enviada! Nossa equipe vai analisar em breve.')
        return redirect('store_verification')

    history = StoreVerificationRequest.objects.filter(store=request.user)

    return render(request, 'marketplace_app/store_verification.html', {
        'profile': profile,
        'pending': pending,
        'history': history,
    })
