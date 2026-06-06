from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from marketplace_app.forms import (
    ChangePasswordForm,
    CommonProfileForm,
    IndividualRegistrationForm,
    StoreProfileForm,
    StoreRegistrationForm,
    UserProfileForm,
)
from marketplace_app.models import CommonProfile, StoreProfile


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

    profile = None
    if profile_user.is_store:
        profile, _ = StoreProfile.objects.get_or_create(user=profile_user)
        # Vitrine/catálogo da loja: mostra também itens esgotados (status sold),
        # ocultando apenas os pausados. Assim a loja não recria anúncios — repõe estoque.
        listings = (
            profile_user.listings
            .exclude(status='paused')
            .prefetch_related('images')
            .order_by('-created_at')
        )
    else:
        profile, _ = CommonProfile.objects.get_or_create(user=profile_user)
        listings = (
            profile_user.listings
            .filter(status='active')
            .prefetch_related('images')
            .order_by('-created_at')
        )

    return render(request, 'users/user_profile.html', {
        'profile_user': profile_user,
        'profile': profile,
        'listings': listings,
        'is_store_view': profile_user.is_store,
    })


LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 5 * 60  # 5 minutos


def _login_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def user_login(request):
    from django.core.cache import cache

    cache_key = f'login_attempts:{_login_ip(request)}'
    attempts = cache.get(cache_key, 0)
    locked = attempts >= LOGIN_MAX_ATTEMPTS

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and locked:
        messages.error(request, 'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.')
        return render(request, 'users/login.html', {'form': form, 'locked': True})

    if request.method == 'POST' and form.is_valid():
        cache.delete(cache_key)  # sucesso zera o contador
        remember = request.POST.get('remember')
        user = form.get_user()
        login(request, user)

        if remember:
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)

        return redirect('home')

    if request.method == 'POST' and not form.is_valid():
        # incrementa e (re)define a expiração da janela de bloqueio
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, LOGIN_LOCKOUT_SECONDS)
        restantes = max(0, LOGIN_MAX_ATTEMPTS - attempts)
        if restantes:
            messages.error(request, f'Usuário ou senha inválidos. Tentativas restantes: {restantes}.')
        else:
            messages.error(request, 'Muitas tentativas. Login bloqueado por alguns minutos.')

    return render(request, 'users/login.html', {
        'form': form,
        'locked': locked,
    })


def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
def account_security(request):
    from marketplace_app.models import Listing, ListingReport
    from marketplace_app.moderation import MAX_STRIKES

    user = request.user
    listings_count = Listing.objects.filter(seller=user).count()
    reports_received = ListingReport.objects.filter(listing__seller=user).count()

    return render(request, 'users/account_security.html', {
        'strikes': user.strikes,
        'max_strikes': MAX_STRIKES,
        'listings_count': listings_count,
        'reports_received': reports_received,
    })


def user_register(request):
    form = None
    form_values = {}
    form_errors = {}
    active_step = 1
    selected_account_type = ''

    if request.method == 'POST':
        account_type = request.POST.get('account_type')
        selected_account_type = account_type or ''

        if account_type not in ['individual', 'store']:
            messages.error(request, 'Selecione o tipo de conta antes de continuar.')
            return render(request, 'users/register.html', {
                'form_values': form_values,
                'form_errors': form_errors,
                'active_step': active_step,
                'selected_account_type': selected_account_type,
            })

        # Make a mutable copy so we can synthesize missing confirmation fields
        post_data = request.POST.copy()
        if account_type == 'individual':
            if 'confirm_password' not in post_data:
                post_data['confirm_password'] = post_data.get('password', '')
            form = IndividualRegistrationForm(post_data)
        else:
            if 'confirm_store_password' not in post_data:
                post_data['confirm_store_password'] = post_data.get('store_password', '')
            form = StoreRegistrationForm(post_data)

        active_step = 2

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
        'active_step': active_step,
        'selected_account_type': selected_account_type,
    })