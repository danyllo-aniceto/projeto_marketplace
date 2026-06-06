from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from marketplace_app.models import (
    StoreProfile, StoreVerificationRequest, ListingReport, Listing, Notification,
)
from marketplace_app.notifications import notify
from marketplace_app.moderation import record_strike


User = get_user_model()


def _delete_listing_moderated(listing, reason=''):
    """Exclui um anúncio pela moderação: notifica o vendedor com o motivo e
    aplica um strike (pode levar a banimento automático na 3ª). Retorna (strikes, banido)."""
    seller = listing.seller
    title = listing.title
    listing.delete()
    if not seller:
        return (0, False)
    msg = f'Seu anúncio "{title}" foi removido pela moderação.'
    if reason:
        msg += f' Motivo: {reason}'
    notify(seller, 'Anúncio removido pela moderação', msg,
           category=Notification.SYSTEM, icon='gpp_bad')
    return record_strike(seller)


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'Área restrita à administração.')
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper


def _ban_user(user):
    user.is_active = False
    user.save(update_fields=['is_active'])
    Listing.objects.filter(seller=user).delete()


@staff_required
def moderation_panel(request):
    pending_verifications = (
        StoreVerificationRequest.objects
        .filter(status=StoreVerificationRequest.PENDING)
        .select_related('store')
        .order_by('created_at')
    )
    reports = (
        ListingReport.objects
        .select_related('listing', 'listing__seller', 'reporter')
        .order_by('status', '-created_at')  # 'open' < 'reviewed' < 'dismissed' alfabeticamente? não — usamos annotate
    )
    # Abertas primeiro
    reports = sorted(reports, key=lambda r: (r.status != ListingReport.OPEN, ))
    open_count = ListingReport.objects.filter(status=ListingReport.OPEN).count()

    return render(request, 'marketplace_app/moderation_panel.html', {
        'pending_verifications': pending_verifications,
        'reports': reports,
        'verifications_count': pending_verifications.count(),
        'reports_count': open_count,
        'users_total': User.objects.count(),
        'listings_total': Listing.objects.count(),
        'banned_total': User.objects.filter(is_active=False).count(),
    })


@staff_required
def mod_users(request):
    search = (request.GET.get('q') or '').strip()
    qs = User.objects.all().order_by('-date_joined')
    if search:
        qs = qs.filter(models.Q(username__icontains=search) | models.Q(email__icontains=search))
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page', 1))
    return render(request, 'marketplace_app/mod_users.html', {
        'page_obj': page_obj,
        'search': search,
    })


@staff_required
@require_POST
def mod_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    action = request.POST.get('action')
    if user.is_superuser:
        messages.error(request, 'Não é possível moderar um superusuário.')
        return redirect('mod_users')

    if action == 'ban':
        _ban_user(user)
        notify(user, 'Conta suspensa', 'Sua conta foi suspensa pela moderação por violar as regras da plataforma.',
               category=Notification.SYSTEM, icon='block')
        messages.success(request, f'{user.username} banido e anúncios removidos.')
    elif action == 'reactivate':
        user.is_active = True
        user.strikes = 0
        user.save(update_fields=['is_active', 'strikes'])
        messages.success(request, f'{user.username} reativado (strikes zerados).')
    elif action == 'reset_strikes':
        user.strikes = 0
        user.save(update_fields=['strikes'])
        messages.success(request, f'Strikes de {user.username} zerados.')

    return redirect(request.META.get('HTTP_REFERER') or 'mod_users')


@staff_required
def mod_listings(request):
    search = (request.GET.get('q') or '').strip()
    qs = Listing.objects.select_related('seller', 'category').order_by('-created_at')
    if search:
        qs = qs.filter(
            models.Q(title__icontains=search)
            | models.Q(seller__username__icontains=search)
            | models.Q(category__name__icontains=search)
        )
    page_obj = Paginator(qs, 15).get_page(request.GET.get('page', 1))
    return render(request, 'marketplace_app/mod_listings.html', {
        'page_obj': page_obj,
        'search': search,
    })


@staff_required
@require_POST
def mod_delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    reason = (request.POST.get('reason') or '').strip()
    title = listing.title
    strikes, banned = _delete_listing_moderated(listing, reason)
    if banned:
        messages.success(request, f'"{title}" excluído. Vendedor atingiu 3 strikes e foi banido.')
    else:
        messages.success(request, f'"{title}" excluído. Vendedor notificado (strike {strikes}/3).')
    return redirect(request.META.get('HTTP_REFERER') or 'mod_listings')


@staff_required
@require_POST
def mod_verification(request, pk):
    req = get_object_or_404(StoreVerificationRequest, pk=pk)
    action = request.POST.get('action')

    if req.status != StoreVerificationRequest.PENDING:
        messages.info(request, 'Esta solicitação já foi analisada.')
        return redirect('moderation_panel')

    req.reviewed_at = timezone.now()

    if action == 'approve':
        req.status = StoreVerificationRequest.APPROVED
        req.save(update_fields=['status', 'reviewed_at'])
        profile = StoreProfile.objects.filter(user=req.store).first()
        if profile and not profile.verified:
            profile.verified = True
            profile.save(update_fields=['verified'])
        notify(
            req.store, 'Loja verificada!',
            'Sua solicitação de verificação foi aprovada. Sua loja agora exibe o selo verificado.',
            url='/perfil/%s/' % req.store.username, category=Notification.SYSTEM, icon='verified',
        )
        messages.success(request, f'Loja {req.store.username} verificada.')
    elif action == 'reject':
        req.status = StoreVerificationRequest.REJECTED
        req.save(update_fields=['status', 'reviewed_at'])
        notify(
            req.store, 'Verificação não aprovada',
            'Sua solicitação foi recusada. Você pode reenviar com documentos válidos.',
            url='/loja/verificacao/', category=Notification.SYSTEM, icon='gpp_bad',
        )
        messages.success(request, 'Solicitação recusada.')

    return redirect('moderation_panel')


@staff_required
@require_POST
def mod_report(request, pk):
    report = get_object_or_404(ListingReport.objects.select_related('listing__seller'), pk=pk)
    action = request.POST.get('action')
    listing = report.listing
    seller = listing.seller if listing else None

    if action == 'delete_listing':
        if listing:
            reason = (request.POST.get('reason') or '').strip()
            strikes, banned = _delete_listing_moderated(listing, reason)
            ListingReport.objects.filter(pk=report.pk).update(status=ListingReport.REVIEWED)
            if banned:
                messages.success(request, 'Anúncio excluído. Vendedor atingiu 3 strikes e foi banido.')
            else:
                messages.success(request, f'Anúncio excluído. Vendedor notificado (strike {strikes}/3).')
        else:
            ListingReport.objects.filter(pk=report.pk).update(status=ListingReport.REVIEWED)
    elif action == 'ban_seller':
        if seller and not seller.is_superuser:
            _ban_user(seller)
            notify(seller, 'Conta suspensa', 'Sua conta foi suspensa pela moderação por violar as regras da plataforma.',
                   category=Notification.SYSTEM, icon='block')
            ListingReport.objects.filter(pk=report.pk).update(status=ListingReport.REVIEWED)
            messages.success(request, f'Vendedor {seller.username} banido e anúncios removidos.')
        else:
            messages.error(request, 'Não é possível banir este usuário.')
    elif action == 'dismiss':
        report.status = ListingReport.DISMISSED
        report.save(update_fields=['status'])
        messages.success(request, 'Denúncia descartada.')

    return redirect('moderation_panel')
