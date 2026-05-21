from django import forms
from django.contrib.auth import get_user_model
from .models import Listing, Comment, CommonProfile, StoreProfile

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
        fields = []  # Sem campos editáveis (CPF não pode ser alterado)


class StoreProfileForm(forms.ModelForm):
    class Meta:
        model = StoreProfile
        fields = ['cnpj', 'razao_social']


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
