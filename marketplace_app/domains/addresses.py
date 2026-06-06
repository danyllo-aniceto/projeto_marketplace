from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from marketplace_app.forms import AddressForm
from marketplace_app.models import Address


def _clear_other_defaults(user, keep_pk=None):
    qs = Address.objects.filter(user=user, is_default=True)
    if keep_pk:
        qs = qs.exclude(pk=keep_pk)
    qs.update(is_default=False)


@login_required
def addresses_view(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'users/addresses.html', {
        'addresses': addresses,
    })


@login_required
def address_create(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # Primeiro endereço vira padrão automaticamente.
            if not Address.objects.filter(user=request.user).exists():
                address.is_default = True
            address.state = (address.state or '').upper()
            address.save()
            if address.is_default:
                _clear_other_defaults(request.user, keep_pk=address.pk)
            messages.success(request, 'Endereço adicionado com sucesso.')
            return redirect('addresses')
    else:
        form = AddressForm()

    return render(request, 'users/address_form.html', {
        'form': form,
        'mode': 'create',
    })


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save(commit=False)
            address.state = (address.state or '').upper()
            address.save()
            if address.is_default:
                _clear_other_defaults(request.user, keep_pk=address.pk)
            messages.success(request, 'Endereço atualizado.')
            return redirect('addresses')
    else:
        form = AddressForm(instance=address)

    return render(request, 'users/address_form.html', {
        'form': form,
        'mode': 'edit',
        'address': address,
    })


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    was_default = address.is_default
    address.delete()
    # Se apagou o padrão, promove o mais recente a padrão.
    if was_default:
        nxt = Address.objects.filter(user=request.user).first()
        if nxt:
            nxt.is_default = True
            nxt.save(update_fields=['is_default'])
    messages.success(request, 'Endereço removido.')
    return redirect('addresses')


@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    _clear_other_defaults(request.user, keep_pk=address.pk)
    address.is_default = True
    address.save(update_fields=['is_default'])
    messages.success(request, 'Endereço padrão atualizado.')
    return redirect('addresses')
