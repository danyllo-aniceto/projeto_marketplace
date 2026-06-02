import re

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils.text import slugify


def _only_digits(value):
    return re.sub(r'\D', '', value or '')


def validate_cpf(value):
    cpf = _only_digits(value)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError('CPF inválido.')

    digits = cpf[:9]
    first_sum = sum(int(digit) * factor for digit, factor in zip(digits, range(10, 1, -1)))
    first_digit = (first_sum * 10) % 11
    first_digit = 0 if first_digit == 10 else first_digit

    second_sum = sum(int(digit) * factor for digit, factor in zip(digits + str(first_digit), range(11, 1, -1)))
    second_digit = (second_sum * 10) % 11
    second_digit = 0 if second_digit == 10 else second_digit

    if cpf[-2:] != f'{first_digit}{second_digit}':
        raise ValidationError('CPF inválido.')


def validate_cnpj(value):
    cnpj = _only_digits(value)

    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError('CNPJ inválido.')

    def calculate_digit(base, weights):
        total = sum(int(digit) * weight for digit, weight in zip(base, weights))
        remainder = total % 11
        return '0' if remainder < 2 else str(11 - remainder)

    first_digit = calculate_digit(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second_digit = calculate_digit(cnpj[:12] + first_digit, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])

    if cnpj[-2:] != f'{first_digit}{second_digit}':
        raise ValidationError('CNPJ inválido.')


class User(AbstractUser):
    is_store = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def __str__(self):
        return self.username


class StoreProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cnpj = models.CharField(max_length=18, unique=True, validators=[validate_cnpj])
    razao_social = models.CharField(max_length=255)
    fantasy_name = models.CharField(max_length=255, blank=True)
    state_registration = models.CharField(max_length=50, blank=True)
    responsible_name = models.CharField(max_length=255, blank=True)
    responsible_cpf = models.CharField(max_length=14, blank=True, validators=[validate_cpf])
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    commercial_cep = models.CharField(max_length=9, blank=True)
    commercial_address = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        self.cnpj = _only_digits(self.cnpj)
        self.responsible_cpf = _only_digits(self.responsible_cpf)

    def __str__(self):
        return self.fantasy_name or self.razao_social


class CommonProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cpf = models.CharField(max_length=14, unique=True, validators=[validate_cpf])
    birth_date = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def clean(self):
        super().clean()
        self.cpf = _only_digits(self.cpf)

    def __str__(self):
        return self.user.username


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Listing(models.Model):
    SALE = 'sale'
    TRADE = 'trade'
    BOTH = 'both'

    LISTING_TYPE_CHOICES = [
        (SALE, 'Venda'),
        (TRADE, 'Troca'),
        (BOTH, 'Venda e Troca'),
    ]

    NEW = 'new'
    USED = 'used'

    CONDITION_CHOICES = [
        (NEW, 'Novo'),
        (USED, 'Usado'),
    ]

    ACTIVE = 'active'
    PAUSED = 'paused'
    SOLD = 'sold'

    STATUS_CHOICES = [
        (ACTIVE, 'Ativo'),
        (PAUSED, 'Pausado'),
        (SOLD, 'Vendido'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    title = models.CharField(max_length=255)
    description = models.TextField()
    trade_suggestions = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)

    is_featured = models.BooleanField(default=False, help_text="Anúncio patrocinado")
    is_store_featured = models.BooleanField(default=False, help_text="Destaque para anúncios de loja")

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if self.listing_type == self.SALE and self.price is None:
            raise ValidationError({'price': 'O preço é obrigatório para anúncios de venda.'})

        if self.listing_type == self.TRADE and self.price is not None:
            raise ValidationError({'price': 'Anúncios de troca não usam preço.'})

        if self.listing_type == self.TRADE and not (self.trade_suggestions or '').strip():
            raise ValidationError({'trade_suggestions': 'Informe as sugestões para troca.'})

        if self.price is not None and self.price <= 0:
            raise ValidationError({'price': 'O preço deve ser maior que zero.'})

        if self.seller_id and self.seller.is_store and self.condition != self.NEW:
            raise ValidationError({'condition': 'Lojas só podem anunciar produtos novos.'})

        if self.seller_id and self.seller.is_store and self.listing_type == self.TRADE:
            raise ValidationError({'listing_type': 'Lojas não podem criar anúncios de troca.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='listings/')

    def __str__(self):
        return f"Imagem de {self.listing.title}"


class Comment(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE, related_name='replies'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comentário de {self.user.username} em {self.listing.title}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carrinho de {self.user.username}"


class CartItem(models.Model):
    BUY = 'buy'
    TRADE = 'trade'

    ACTION_CHOICES = [
        (BUY, 'Compra'),
        (TRADE, 'Troca'),
    ]

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    desired_action = models.CharField(max_length=10, choices=ACTION_CHOICES, default=BUY)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'listing')

    def clean(self):
        super().clean()

        if self.listing_id and self.cart_id and self.listing.seller_id == self.cart.user_id:
            raise ValidationError({'listing': 'Você não pode adicionar ao carrinho um anúncio criado por você.'})

        if self.listing_id and self.desired_action == self.TRADE and self.listing.listing_type == Listing.SALE:
            raise ValidationError({'desired_action': 'Este anúncio não aceita troca.'})

        if self.listing_id and self.desired_action == self.BUY and self.listing.listing_type == Listing.TRADE:
            raise ValidationError({'desired_action': 'Este anúncio só aceita troca.'})

        if self.listing_id and self.listing.seller.is_store and self.desired_action == self.TRADE:
            raise ValidationError({'desired_action': 'Lojas não aceitam troca.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.listing.title} no carrinho de {self.cart.user.username}"


class Order(models.Model):
    PIX = 'pix'
    CREDIT_CARD = 'credit_card'
    DEBIT_CARD = 'debit_card'
    BANK_TRANSFER = 'bank_transfer'

    PAYMENT_METHOD_CHOICES = [
        (PIX, 'PIX'),
        (CREDIT_CARD, 'Cartão de crédito'),
        (DEBIT_CARD, 'Cartão de débito'),
        (BANK_TRANSFER, 'Transferência bancária'),
    ]

    PICKUP = 'pickup'
    SELLER_SHIPPING = 'seller_shipping'
    PLATFORM_SHIPPING = 'platform_shipping'
    TO_AGREE = 'to_agree'

    DELIVERY_METHOD_CHOICES = [
        (PICKUP, 'Retirada presencial'),
        (SELLER_SHIPPING, 'Frete do vendedor'),
        (PLATFORM_SHIPPING, 'Frete da plataforma'),
        (TO_AGREE, 'A combinar'),
    ]

    PENDING_PAYMENT = 'pending_payment'
    PAID = 'paid'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'

    STATUS_CHOICES = [
        (PENDING_PAYMENT, 'Aguardando pagamento'),
        (PAID, 'Pago'),
        (CANCELLED, 'Cancelado'),
        (COMPLETED, 'Concluído'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default=TO_AGREE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING_PAYMENT)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pedido #{self.pk} - {self.buyer.username}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sale_items')
    title_snapshot = models.CharField(max_length=255)
    unit_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.title_snapshot} em pedido #{self.order_id}'


class PaymentTransaction(models.Model):
    MERCADO_PAGO = 'mercado_pago'

    GATEWAY_CHOICES = [
        (MERCADO_PAGO, 'Mercado Pago'),
    ]

    PENDING = 'pending'
    PROCESSING = 'processing'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (PENDING, 'Pendente'),
        (PROCESSING, 'Processando'),
        (APPROVED, 'Aprovado'),
        (REJECTED, 'Recusado'),
        (CANCELLED, 'Cancelado'),
        (REFUNDED, 'Estornado'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_transaction')
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default=MERCADO_PAGO)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    external_reference = models.CharField(max_length=255, blank=True)
    preference_id = models.CharField(max_length=255, blank=True)
    checkout_url = models.URLField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pagamento #{self.order_id} - {self.get_status_display()}'


class Delivery(models.Model):
    PICKUP = 'pickup'
    SELLER_SHIPPING = 'seller_shipping'
    PLATFORM_SHIPPING = 'platform_shipping'
    TO_AGREE = 'to_agree'

    METHOD_CHOICES = [
        (PICKUP, 'Retirada presencial'),
        (SELLER_SHIPPING, 'Frete do vendedor'),
        (PLATFORM_SHIPPING, 'Frete da plataforma'),
        (TO_AGREE, 'A combinar'),
    ]

    PENDING = 'pending'
    PREPARING = 'preparing'
    IN_TRANSIT = 'in_transit'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, 'Pendente'),
        (PREPARING, 'Separando'),
        (IN_TRANSIT, 'Em trânsito'),
        (DELIVERED, 'Entregue'),
        (CANCELLED, 'Cancelada'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=TO_AGREE)
    recipient_name = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=20)
    postal_code = models.CharField(max_length=9)
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    carrier_name = models.CharField(max_length=120, blank=True)
    tracking_code = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    estimated_delivery_date = models.DateField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Entrega #{self.order_id} - {self.get_status_display()}'


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)

    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}"


class TradeRequest(models.Model):
    PENDING = 'pending'
    NEGOTIATING = 'negotiating'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, 'Aguardando'),
        (NEGOTIATING, 'Em negociação'),
        (APPROVED, 'Aprovada'),
        (REJECTED, 'Reprovada'),
        (COMPLETED, 'Concluída'),
        (CANCELLED, 'Cancelada'),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_requests_created')
    counterparty = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_requests_received')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='trade_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    initial_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if self.requester_id and self.counterparty_id and self.requester_id == self.counterparty_id:
            raise ValidationError({'counterparty': 'O remetente e o destinatário da negociação devem ser usuários diferentes.'})

        if self.listing_id:
            if self.listing.seller_id == self.requester_id:
                raise ValidationError({'requester': 'O comprador da negociação não pode ser o dono do anúncio.'})

            if self.counterparty_id and self.listing.seller_id != self.counterparty_id:
                raise ValidationError({'counterparty': 'A contraparte da negociação deve ser o vendedor do anúncio.'})

            if self.listing.status != Listing.ACTIVE and self.status not in [self.CANCELLED, self.COMPLETED]:
                raise ValidationError({'listing': 'Este anúncio não está mais disponível para troca.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Troca #{self.pk} - {self.listing.title}'


class TradeProposal(models.Model):
    trade_request = models.ForeignKey(TradeRequest, on_delete=models.CASCADE, related_name='proposals')
    proposer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_proposals_made')
    item_description = models.TextField(blank=True)
    cash_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if self.trade_request_id and self.proposer_id:
            allowed_users = {self.trade_request.requester_id, self.trade_request.counterparty_id}
            if self.proposer_id not in allowed_users:
                raise ValidationError({'proposer': 'Somente os participantes da negociação podem criar propostas.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Proposta de troca #{self.trade_request_id}'


class TradeProposalImage(models.Model):
    proposal = models.ForeignKey(TradeProposal, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='trade_proposals/')

    def __str__(self):
        return f'Imagem da proposta #{self.proposal_id}'


class TradeFulfillment(models.Model):
    DRAFT = 'draft'
    PAYMENT_PENDING = 'payment_pending'
    PAYMENT_CONFIRMED = 'payment_confirmed'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (DRAFT, 'Rascunho'),
        (PAYMENT_PENDING, 'Aguardando confirmação do pagamento'),
        (PAYMENT_CONFIRMED, 'Pagamento confirmado'),
        (COMPLETED, 'Concluída'),
        (CANCELLED, 'Cancelada'),
    ]

    trade_request = models.OneToOneField(TradeRequest, on_delete=models.CASCADE, related_name='fulfillment')
    agreed_proposal = models.ForeignKey(TradeProposal, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfillments')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=Order.PAYMENT_METHOD_CHOICES, blank=True)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    payment_checkout_token = models.CharField(max_length=255, blank=True)
    payment_payload = models.JSONField(default=dict, blank=True)
    payment_confirmed_at = models.DateTimeField(blank=True, null=True)
    delivery_method = models.CharField(max_length=20, choices=Order.DELIVERY_METHOD_CHOICES, default=Order.TO_AGREE)
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=9, blank=True)
    street = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=20, blank=True)
    complement = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    notes = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if self.trade_request_id and self.trade_request.status == TradeRequest.CANCELLED:
            raise ValidationError({'trade_request': 'Não é possível registrar execução para uma troca cancelada.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Execução da troca #{self.trade_request_id}'


class TradeMessage(models.Model):
    trade_request = models.ForeignKey(TradeRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_messages_sent')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if self.trade_request_id and self.sender_id:
            allowed_users = {self.trade_request.requester_id, self.trade_request.counterparty_id}
            if self.sender_id not in allowed_users:
                raise ValidationError({'sender': 'Somente os participantes da negociação podem enviar mensagens.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Mensagem da troca #{self.trade_request_id}'


class TradeDelivery(models.Model):
    DRAFT = 'draft'
    SENT = 'sent'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (DRAFT, 'Rascunho'),
        (SENT, 'Enviado'),
        (DELIVERED, 'Entregue'),
        (CANCELLED, 'Cancelada'),
    ]

    trade_request = models.ForeignKey(TradeRequest, on_delete=models.CASCADE, related_name='deliveries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trade_deliveries')
    delivery_method = models.CharField(max_length=20, choices=Order.DELIVERY_METHOD_CHOICES, default=Order.TO_AGREE)
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=9, blank=True)
    street = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=20, blank=True)
    complement = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.trade_request_id and self.user_id:
            allowed = {self.trade_request.requester_id, self.trade_request.counterparty_id}
            if self.user_id not in allowed:
                raise ValidationError({'user': 'Somente participantes da negociação podem registrar entregas.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Entrega de {self.user.username} para troca #{self.trade_request_id}'