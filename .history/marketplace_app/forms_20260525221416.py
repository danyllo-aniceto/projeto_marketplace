from django import forms
from django.contrib.auth import get_user_model
from .models import Listing, Comment, CommonProfile, StoreProfile, CartItem, Order, TradeMessage, TradeRequest, Delivery, PaymentTransaction

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ListingForm(forms.ModelForm):

    image = forms.ImageField(
        required=False,
        help_text='Selecione uma imagem para o anúncio.',
        label='Foto do Produto'
    )

    class Meta:
        model = Listing
        fields = [
            'title',
            'description',
            'price',
            'category',
            'listing_type',
            'condition',
        ]
        labels = {
            'title': 'Título do Anúncio',
            'description': 'Descrição',
            'price': 'Preço (R$)',
            'category': 'Categoria',
            'listing_type': 'Tipo de Anúncio',
            'condition': 'Condição do Produto',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: iPhone 14 Pro'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Descreva detalhes do produto...'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'listing_type': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Se for loja, remove opção "Troca" e "Venda e Troca"
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


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'profile_picture']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].widget.attrs.update({
            'class': 'file-input',
            'accept': 'image/*'
        })


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
        widgets = {
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, número, complemento'}),
        }


class StoreProfileForm(forms.ModelForm):
    class Meta:
        model = StoreProfile
        fields = [
            'cnpj', 'razao_social', 'fantasy_name', 'state_registration',
            'responsible_name', 'responsible_cpf', 'phone', 'email',
            'commercial_cep', 'commercial_address',
        ]
        widgets = {
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'fantasy_name': forms.TextInput(attrs={'class': 'form-control'}),
            'state_registration': forms.TextInput(attrs={'class': 'form-control'}),
            'responsible_name': forms.TextInput(attrs={'class': 'form-control'}),
            'responsible_cpf': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'commercial_cep': forms.TextInput(attrs={'class': 'form-control'}),
            'commercial_address': forms.TextInput(attrs={'class': 'form-control'}),
        }


class IndividualRegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=20)
    birth_date = forms.DateField(required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    cep = forms.CharField(max_length=20, required=False)
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
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'comment-input',
                'placeholder': 'Escreva seu comentário...',
                'rows': 4,
            }),
        }


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


class TradeStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=TradeRequest.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status da negociação',
    )


class PaymentTransactionForm(forms.ModelForm):
    class Meta:
        model = PaymentTransaction
        fields = ['gateway']
        widgets = {
            'gateway': forms.Select(attrs={'class': 'form-control'}),
        }
