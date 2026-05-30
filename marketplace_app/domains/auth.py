from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
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


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            return redirect('home')

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