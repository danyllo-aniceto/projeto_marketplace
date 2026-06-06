from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from .moderation import validate_clean_text, validate_image_upload
from .models import Listing, Comment, CommonProfile, StoreProfile, CartItem, Order, TradeMessage, TradeRequest, TradeProposal, TradeFulfillment, TradeDelivery, Delivery, PaymentTransaction, Address

User = get_user_model()


def _only_digits(value):
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _is_valid_cpf(value):
    digits = _only_digits(value)

    if len(digits) != 11:
        return False

    if digits == digits[0] * 11:
        return False

    def calc_digit(base, weights):
        total = sum(int(number) * weight for number, weight in zip(base, weights))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first_digit = calc_digit(digits[:9], range(10, 1, -1))
    second_digit = calc_digit(digits[:10], range(11, 1, -1))
    return digits[-2:] == f'{first_digit}{second_digit}'


def _is_valid_phone(value):
    digits = _only_digits(value)
    return len(digits) in (10, 11)


def _format_cpf(value):
    digits = _only_digits(value)[:11]
    if len(digits) != 11:
        return value
    return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'


def _format_phone(value):
    digits = _only_digits(value)[:11]
    if len(digits) < 10:
        return value
    if len(digits) == 10:
        return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'


def _format_cep(value):
    digits = _only_digits(value)[:8]
    if len(digits) == 8:
        return f'{digits[:5]}-{digits[5:]}'
    return value


def _format_currency(value):
    if value in (None, ''):
        return ''

    try:
        numeric_value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    formatted_value = f'{numeric_value:,.2f}'
    return f'R$ {formatted_value}'.replace(',', 'X').replace('.', ',').replace('X', '.')


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if data in self.empty_values:
            if self.required:
                raise ValidationError(self.error_messages['required'], code='required')
            return []

        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned_files = []
        for file in data:
            cleaned_files.append(super().clean(file, initial))

        return cleaned_files


class ListingForm(forms.ModelForm):

    price = forms.CharField(
        required=True,
        label='Preço (R$)',
        widget=forms.TextInput(attrs={
            'class': 'form-control currency-mask',
            'placeholder': 'R$ 0,00',
            'inputmode': 'decimal',
            'autocomplete': 'off',
        }),
    )

    images = MultipleFileField(
        required=False,
        help_text='Selecione uma ou mais imagens para o anúncio.',
        label='Fotos do Produto',
        widget=MultipleFileInput(attrs={
            'class': 'file-input-input',
            'accept': 'image/*',
            'multiple': True,
        })
    )

    class Meta:
        model = Listing
        fields = [
            'title',
            'description',
            'trade_suggestions',
            'price',
            'category',
            'listing_type',
            'condition',
            'stock',
        ]
        labels = {
            'title': 'Título do Anúncio',
            'description': 'Descrição',
            'trade_suggestions': 'Sugestões para troca',
            'price': 'Preço (R$)',
            'category': 'Categoria',
            'listing_type': 'Tipo de Anúncio',
            'condition': 'Condição do Produto',
            'stock': 'Quantidade em estoque',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: iPhone 14 Pro'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Descreva detalhes do produto...'}),
            'trade_suggestions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ex: notebook gamer, smartphone semi-novo...'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'listing_type': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_create_mode = not getattr(self.instance, 'pk', None)

        if not self.is_bound and not is_create_mode:
            self.initial['price'] = _format_currency(self.instance.price)

        for field_name in ['title', 'description', 'trade_suggestions', 'price', 'category', 'listing_type', 'condition']:
            self.fields[field_name].required = True

        self.fields['stock'].required = True
        if not self.is_bound and is_create_mode and not self.initial.get('stock'):
            self.initial['stock'] = 1

        self.fields['price'].required = False
        self.fields['trade_suggestions'].required = False

        self.fields['images'].required = is_create_mode
        self.fields['trade_suggestions'].help_text = 'Informe o que você aceita na troca.'
        self.fields['listing_type'].help_text = 'Escolha entre venda ou troca.'

        # Se for loja, mantém apenas venda de produto novo.
        if self.user and self.user.is_store:
            self.fields['listing_type'].choices = [
                ('sale', 'Venda')
            ]
            self.fields['condition'].choices = [
                (Listing.NEW, 'Novo')
            ]
        else:
            self.fields['listing_type'].choices = [
                ('sale', 'Venda'),
                ('trade', 'Troca'),
                ('both', 'Venda e Troca'),
            ]

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is None or stock < 0:
            raise ValidationError('A quantidade em estoque não pode ser negativa.')
        return stock

    def clean_title(self):
        return validate_clean_text(self.cleaned_data.get('title'), 'título')

    def clean_description(self):
        return validate_clean_text(self.cleaned_data.get('description'), 'descrição')

    def clean_trade_suggestions(self):
        return validate_clean_text(self.cleaned_data.get('trade_suggestions'), 'sugestão de troca')

    def clean_images(self):
        images = self.cleaned_data.get('images') or []
        for img in images:
            validate_image_upload(img)
        return images

    def clean_price(self):
        # If the user selected 'trade', price should be ignored early
        listing_type_raw = None
        try:
            listing_type_raw = self.data.get('listing_type')
        except Exception:
            listing_type_raw = None

        if listing_type_raw == Listing.TRADE:
            return None

        value = self.cleaned_data.get('price')

        if value in self.fields['price'].empty_values:
            return None

        if isinstance(value, Decimal):
            decimal_value = value
        else:
            raw_value = str(value).strip()
            normalized_value = raw_value.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
            try:
                decimal_value = Decimal(normalized_value)
            except (InvalidOperation, ValueError):
                raise ValidationError('Informe um preço válido.')

        if decimal_value <= 0:
            raise ValidationError('O preço deve ser maior que zero.')

        return decimal_value.quantize(Decimal('0.01'))

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        price = cleaned_data.get('price')
        trade_suggestions = (cleaned_data.get('trade_suggestions') or '').strip()

        if listing_type == Listing.TRADE:
            # Troca pura: sem preço, sugestões obrigatórias
            if not trade_suggestions:
                self.add_error('trade_suggestions', 'Informe o que você aceita em troca.')
            cleaned_data['price'] = None
            cleaned_data['trade_suggestions'] = trade_suggestions

        elif listing_type == Listing.BOTH:
            # Venda e Troca: preço obrigatório E sugestões obrigatórias
            if price is None:
                self.add_error('price', 'O preço é obrigatório para anúncios de venda.')
            if not trade_suggestions:
                self.add_error('trade_suggestions', 'Informe o que você aceita em troca.')
            cleaned_data['trade_suggestions'] = trade_suggestions

        else:
            # Venda pura: preço obrigatório, sem sugestões
            if price is None:
                self.add_error('price', 'O preço é obrigatório para anúncios de venda.')
            cleaned_data['trade_suggestions'] = ''

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile_picture']
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'profile_picture': 'Foto de perfil',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu sobrenome'}),
            'profile_picture': forms.FileInput(attrs={'class': 'file-input', 'accept': 'image/*'}),
        }

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        # Valida apenas quando um novo arquivo é enviado.
        if picture and hasattr(picture, 'content_type'):
            validate_image_upload(picture)
        return picture


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label='Senha Atual',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua senha atual',
        }),
        required=True
    )
    new_password = forms.CharField(
        label='Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua nova senha',
        }),
        required=True
    )
    confirm_password = forms.CharField(
        label='Confirmação da Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme sua nova senha',
        }),
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('As novas senhas não correspondem.')
        
        return cleaned_data


class CommonProfileForm(forms.ModelForm):
    class Meta:
        model = CommonProfile
        fields = ['birth_date', 'phone', 'cep', 'address']
        labels = {
            'birth_date': 'Data de nascimento',
            'phone': 'Telefone',
            'cep': 'CEP',
            'address': 'Endereço',
        }
        widgets = {
            'birth_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, número, complemento'}),
        }

    def clean_birth_date(self):
        from datetime import date
        birth_date = self.cleaned_data.get('birth_date')
        if not birth_date:
            return birth_date
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 18:
            raise forms.ValidationError('É necessário ter pelo menos 18 anos.')
        return birth_date

    def clean_cep(self):
        cep = self.cleaned_data.get('cep', '') or ''
        digits = _only_digits(cep)
        if digits and len(digits) != 8:
            raise forms.ValidationError('CEP inválido. Informe os 8 dígitos.')
        return _format_cep(cep) if digits else ''


class StoreProfileForm(forms.ModelForm):
    def clean_commercial_cep(self):
        cep = self.cleaned_data.get('commercial_cep', '') or ''
        digits = _only_digits(cep)
        if digits and len(digits) != 8:
            raise forms.ValidationError('CEP inválido. Informe os 8 dígitos.')
        return _format_cep(cep) if digits else ''

    class Meta:
        model = StoreProfile
        fields = [
            'cnpj', 'razao_social', 'fantasy_name', 'state_registration',
            'responsible_name', 'responsible_cpf', 'phone', 'email',
            'commercial_cep', 'commercial_address',
        ]
        labels = {
            'cnpj': 'CNPJ',
            'razao_social': 'Razão social',
            'fantasy_name': 'Nome fantasia',
            'state_registration': 'Inscrição estadual',
            'responsible_name': 'Nome do responsável',
            'responsible_cpf': 'CPF do responsável',
            'phone': 'Telefone',
            'email': 'E-mail comercial',
            'commercial_cep': 'CEP comercial',
            'commercial_address': 'Endereço comercial',
        }
        widgets = {
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'fantasy_name': forms.TextInput(attrs={'class': 'form-control'}),
            'state_registration': forms.TextInput(attrs={'class': 'form-control'}),
            'responsible_name': forms.TextInput(attrs={'class': 'form-control'}),
            'responsible_cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'commercial_cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'commercial_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, número, complemento'}),
        }


class IndividualRegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=20)
    birth_date = forms.DateField(required=True)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    cep = forms.CharField(max_length=10, required=False)
    address = forms.CharField(max_length=255, required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Nome de usuário já está em uso.')
        return username

    def clean_password(self):
        pwd = self.cleaned_data['password']
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(pwd)
        except Exception as e:
            raise forms.ValidationError(str(e))
        return pwd

    def clean_confirm_password(self):
        confirm_password = self.cleaned_data['confirm_password']
        if 'password' in self.cleaned_data and confirm_password != self.cleaned_data.get('password'):
            raise forms.ValidationError('As senhas não coincidem.')
        return confirm_password

    def clean_birth_date(self):
        from datetime import date
        birth_date = self.cleaned_data.get('birth_date')
        if not birth_date:
            raise forms.ValidationError('A data de nascimento é obrigatória.')
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 18:
            raise forms.ValidationError('É necessário ter pelo menos 18 anos para se cadastrar.')
        return birth_date

    def clean_cep(self):
        cep = self.cleaned_data.get('cep', '') or ''
        digits = _only_digits(cep)
        if digits and len(digits) != 8:
            raise forms.ValidationError('CEP inválido. Informe os 8 dígitos.')
        return _format_cep(cep) if digits else ''

    def clean_cpf(self):
        cpf = self.cleaned_data['cpf']
        if not _is_valid_cpf(cpf):
            raise forms.ValidationError('CPF inválido.')
        return _format_cpf(cpf)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone and not _is_valid_phone(phone):
            raise forms.ValidationError('Telefone inválido.')
        return _format_phone(phone) if phone else phone

    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            is_store=False,
        )

        profile = CommonProfile(
            user=user,
            cpf=self.cleaned_data.get('cpf'),
            birth_date=self.cleaned_data.get('birth_date'),
            phone=self.cleaned_data.get('phone', ''),
            cep=self.cleaned_data.get('cep', ''),
            address=self.cleaned_data.get('address', ''),
        )
        profile.full_clean()
        profile.save()
        return user


class StoreRegistrationForm(forms.Form):
    store_username = forms.CharField(max_length=150)
    store_password = forms.CharField(widget=forms.PasswordInput)
    confirm_store_password = forms.CharField(widget=forms.PasswordInput)
    store_email = forms.EmailField()
    cnpj = forms.CharField(max_length=30)
    company_name = forms.CharField(max_length=255)
    fantasy_name = forms.CharField(max_length=255, required=False)
    state_registration = forms.CharField(max_length=100, required=False)
    responsible_name = forms.CharField(max_length=150)
    responsible_cpf = forms.CharField(max_length=20)
    store_phone = forms.CharField(max_length=30, required=False)
    store_cep = forms.CharField(max_length=20, required=False)
    store_address = forms.CharField(max_length=255, required=False)

    def clean_store_username(self):
        username = self.cleaned_data['store_username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Nome de usuário já está em uso.')
        return username

    def clean_store_password(self):
        pwd = self.cleaned_data['store_password']
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(pwd)
        except Exception as e:
            raise forms.ValidationError(str(e))
        return pwd

    def clean_confirm_store_password(self):
        confirm_password = self.cleaned_data['confirm_store_password']
        if 'store_password' in self.cleaned_data and confirm_password != self.cleaned_data.get('store_password'):
            raise forms.ValidationError('As senhas não coincidem.')
        return confirm_password

    def clean_responsible_cpf(self):
        responsible_cpf = self.cleaned_data['responsible_cpf']
        if not _is_valid_cpf(responsible_cpf):
            raise forms.ValidationError('CPF inválido.')
        return _format_cpf(responsible_cpf)

    def clean_store_cep(self):
        cep = self.cleaned_data.get('store_cep', '') or ''
        digits = _only_digits(cep)
        if digits and len(digits) != 8:
            raise forms.ValidationError('CEP inválido. Informe os 8 dígitos.')
        return _format_cep(cep) if digits else ''

    def clean_store_phone(self):
        store_phone = self.cleaned_data.get('store_phone', '')
        if store_phone and not _is_valid_phone(store_phone):
            raise forms.ValidationError('Telefone inválido.')
        return _format_phone(store_phone) if store_phone else store_phone

    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data['store_username'],
            email=self.cleaned_data['store_email'],
            password=self.cleaned_data['store_password'],
            first_name=self.cleaned_data.get('responsible_name', ''),
            is_store=True,
        )

        profile = StoreProfile(
            user=user,
            cnpj=self.cleaned_data.get('cnpj'),
            razao_social=self.cleaned_data.get('company_name'),
            fantasy_name=self.cleaned_data.get('fantasy_name', ''),
            state_registration=self.cleaned_data.get('state_registration', ''),
            responsible_name=self.cleaned_data.get('responsible_name', ''),
            responsible_cpf=self.cleaned_data.get('responsible_cpf', ''),
            phone=self.cleaned_data.get('store_phone', ''),
            email=self.cleaned_data.get('store_email', ''),
            commercial_cep=self.cleaned_data.get('store_cep', ''),
            commercial_address=self.cleaned_data.get('store_address', ''),
            verified=False,
        )
        profile.full_clean()
        profile.save()
        return user


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': '',
        }
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'comment-input',
                'placeholder': 'Escreva seu comentário...',
                'rows': 5,
            }),
        }

    def clean_content(self):
        return validate_clean_text(self.cleaned_data.get('content'), 'comentário')


class CartItemActionForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ['desired_action']
        widgets = {
            'desired_action': forms.Select(attrs={'class': 'form-control'}),
        }


class CheckoutForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Forma de pagamento',
    )
    delivery_method = forms.ChoiceField(
        choices=Order.DELIVERY_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Forma de entrega',
        initial=Order.TO_AGREE,
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Observações',
    )
    recipient_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Nome do destinatário',
    )
    recipient_phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Telefone do destinatário',
    )
    postal_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='CEP',
    )
    street = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Rua',
    )
    number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Número',
    )
    complement = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Complemento',
    )
    neighborhood = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Bairro',
    )
    city = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Cidade',
    )
    state = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': 2}),
        label='Estado',
    )

    def clean(self):
        cleaned_data = super().clean()
        delivery_method = cleaned_data.get('delivery_method')

        if delivery_method == Order.PICKUP:
            return cleaned_data

        required_fields = [
            'recipient_name', 'recipient_phone', 'postal_code', 'street',
            'number', 'neighborhood', 'city', 'state',
        ]

        for field_name in required_fields:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, 'Este campo é obrigatório para entrega.')

        return cleaned_data


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            'method', 'recipient_name', 'recipient_phone', 'postal_code',
            'street', 'number', 'complement', 'neighborhood', 'city', 'state',
            'shipping_cost', 'carrier_name', 'tracking_code', 'estimated_delivery_date', 'notes',
        ]
        widgets = {
            'method': forms.Select(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'street': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'complement': forms.TextInput(attrs={'class': 'form-control'}),
            'neighborhood': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 2}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'carrier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class TradeMessageForm(forms.ModelForm):
    class Meta:
        model = TradeMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'comment-input',
                'placeholder': 'Escreva sua mensagem de negociação...',
                'rows': 4,
            }),
        }

    def clean_content(self):
        return validate_clean_text(self.cleaned_data.get('content'), 'mensagem')


class TradeStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=TradeRequest.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status da negociação',
    )


class TradeProposalForm(forms.ModelForm):
    images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={'accept': 'image/*', 'multiple': True}),
        help_text='Adicione uma ou mais imagens da proposta (opcional).',
        label='Imagens'
    )
    cash_amount = forms.CharField(
        required=False,
        label='Valor em dinheiro (R$)',
        widget=forms.TextInput(attrs={
            'class': 'form-control js-money-brl',
            'placeholder': 'R$ 0,00',
            'autocomplete': 'off',
        }),
    )

    class Meta:
        model = TradeProposal
        fields = ['item_description', 'cash_amount', 'note']
        labels = {
            'item_description': 'Descrição do item',
            'note': 'Observação',
        }
        widgets = {
            'item_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descreva o produto que será oferecido na troca'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adicione detalhes da proposta'}),
        }

    def clean_item_description(self):
        return validate_clean_text(self.cleaned_data.get('item_description'), 'descrição')

    def clean_note(self):
        return validate_clean_text(self.cleaned_data.get('note'), 'observação')

    def clean_images(self):
        images = self.cleaned_data.get('images') or []
        for img in images:
            validate_image_upload(img)
        return images

    def clean_cash_amount(self):
        raw = self.cleaned_data.get('cash_amount', '') or ''
        raw = raw.replace('R$', '').strip()
        if not raw or raw in ('0,00', ''):
            return Decimal('0')
        # Formato BR: "1.234,56" → "1234.56"
        raw = raw.replace('.', '').replace(',', '.')
        try:
            return Decimal(raw)
        except InvalidOperation:
            raise forms.ValidationError('Informe um valor monetário válido.')

    def clean(self):
        cleaned_data = super().clean()
        item_description = cleaned_data.get('item_description', '').strip()
        cash_amount = cleaned_data.get('cash_amount') or Decimal('0')

        if not item_description and cash_amount == 0:
            raise forms.ValidationError('Informe um produto, um valor em dinheiro ou ambos.')

        return cleaned_data


class TradeFulfillmentForm(forms.ModelForm):
    class Meta:
        model = TradeFulfillment
        fields = [
            'payment_method', 'delivery_method', 'recipient_name', 'recipient_phone', 'postal_code',
            'street', 'number', 'complement', 'neighborhood', 'city', 'state', 'notes',
        ]
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'delivery_method': forms.Select(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'street': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'complement': forms.TextInput(attrs={'class': 'form-control'}),
            'neighborhood': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class TradeDeliveryForm(forms.ModelForm):
    class Meta:
        model = TradeDelivery
        fields = [
            'delivery_method', 'recipient_name', 'recipient_phone', 'postal_code',
            'street', 'number', 'complement', 'neighborhood', 'city', 'state', 'notes',
        ]
        labels = {
            'delivery_method': 'Forma de entrega',
            'recipient_name': 'Nome do destinatário',
            'recipient_phone': 'Telefone',
            'postal_code': 'CEP',
            'street': 'Rua',
            'number': 'Número',
            'complement': 'Complemento',
            'neighborhood': 'Bairro',
            'city': 'Cidade',
            'state': 'Estado (UF)',
            'notes': 'Observações',
        }
        widgets = {
            'delivery_method': forms.Select(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de quem recebe'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'street': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da rua'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº'}),
            'complement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apto, bloco (opcional)'}),
            'neighborhood': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bairro'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UF', 'maxlength': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PaymentTransactionForm(forms.ModelForm):
    class Meta:
        model = PaymentTransaction
        fields = ['gateway']
        widgets = {
            'gateway': forms.Select(attrs={'class': 'form-control'}),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'label', 'recipient_name', 'recipient_phone', 'postal_code',
            'street', 'number', 'complement', 'neighborhood', 'city', 'state', 'is_default',
        ]
        labels = {
            'label': 'Apelido do endereço',
            'recipient_name': 'Nome do destinatário',
            'recipient_phone': 'Telefone',
            'postal_code': 'CEP',
            'street': 'Rua',
            'number': 'Número',
            'complement': 'Complemento',
            'neighborhood': 'Bairro',
            'city': 'Cidade',
            'state': 'Estado (UF)',
            'is_default': 'Definir como endereço padrão',
        }
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Casa, Trabalho'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de quem recebe'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'street': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da rua'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº'}),
            'complement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apto, bloco (opcional)'}),
            'neighborhood': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bairro'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UF', 'maxlength': 2}),
            'is_default': forms.CheckboxInput(),
        }
