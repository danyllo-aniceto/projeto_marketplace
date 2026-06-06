from django.contrib import admin
from django.utils import timezone
from .notifications import notify
from .models import (
	User,
	Category,
	Listing,
	ListingImage,
	StoreProfile,
	CommonProfile,
	Cart,
	CartItem,
	Order,
	OrderItem,
	PaymentTransaction,
	Delivery,
	TradeRequest,
	TradeMessage,
	Notification,
	Address,
	StoreVerificationRequest,
	ListingReport,
)

def _ban_user(user):
	"""Desativa a conta e remove os anúncios do usuário."""
	user.is_active = False
	user.save(update_fields=['is_active'])
	Listing.objects.filter(seller=user).delete()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ('username', 'email', 'is_store', 'is_active', 'strikes', 'date_joined')
	list_filter = ('is_store', 'is_active', 'is_staff')
	search_fields = ('username', 'email')
	actions = ('ban_users', 'reactivate_users', 'reset_strikes')

	@admin.action(description='Zerar advertências (strikes)')
	def reset_strikes(self, request, queryset):
		updated = queryset.update(strikes=0)
		self.message_user(request, f'{updated} conta(s) com strikes zerados.')

	@admin.action(description='Banir (desativar conta e excluir anúncios)')
	def ban_users(self, request, queryset):
		count = 0
		for user in queryset:
			if user.is_superuser:
				continue
			_ban_user(user)
			count += 1
		self.message_user(request, f'{count} usuário(s) banido(s) e seus anúncios removidos.')

	@admin.action(description='Reativar conta')
	def reactivate_users(self, request, queryset):
		updated = queryset.update(is_active=True)
		self.message_user(request, f'{updated} conta(s) reativada(s).')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug')
	search_fields = ('name', 'slug')
	ordering = ('name',)
	list_per_page = 50


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
	list_display = (
		'title', 'seller', 'category', 'listing_type',
		'condition', 'status', 'is_featured', 'is_store_featured', 'created_at',
	)
	list_display_links = ('title',)
	list_editable = ('status', 'is_featured', 'is_store_featured')
	list_filter = ('listing_type', 'condition', 'status', 'is_featured', 'is_store_featured', 'category')
	search_fields = ('title', 'description', 'seller__username', 'category__name')
	ordering = ('-created_at',)
	list_per_page = 25
	date_hierarchy = 'created_at'


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
	list_display = ('listing', 'image')


@admin.register(StoreProfile)
class StoreProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'razao_social', 'cnpj', 'verified')
	list_display_links = ('user',)
	list_editable = ('verified',)
	list_filter = ('verified',)
	search_fields = ('user__username', 'razao_social', 'cnpj')


@admin.register(CommonProfile)
class CommonProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'cpf')
	search_fields = ('user__username', 'cpf')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
	list_display = ('user', 'created_at')
	search_fields = ('user__username',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
	list_display = ('cart', 'listing', 'desired_action', 'added_at')
	list_filter = ('desired_action',)
	search_fields = ('cart__user__username', 'listing__title')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('buyer', 'payment_method', 'delivery_method', 'status', 'total_amount', 'created_at')
	list_filter = ('payment_method', 'delivery_method', 'status')
	search_fields = ('buyer__username',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
	list_display = ('order', 'listing', 'seller', 'unit_price_snapshot', 'quantity')
	search_fields = ('order__buyer__username', 'listing__title', 'seller__username')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
	list_display = ('order', 'gateway', 'status', 'amount', 'created_at')
	list_filter = ('gateway', 'status')
	search_fields = ('order__buyer__username', 'external_reference', 'preference_id')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
	list_display = ('order', 'method', 'status', 'carrier_name', 'tracking_code', 'shipping_cost')
	list_filter = ('method', 'status')
	search_fields = ('order__buyer__username', 'recipient_name', 'tracking_code', 'carrier_name')


@admin.register(TradeRequest)
class TradeRequestAdmin(admin.ModelAdmin):
	list_display = ('listing', 'requester', 'counterparty', 'status', 'created_at')
	list_filter = ('status',)
	search_fields = ('listing__title', 'requester__username', 'counterparty__username')


@admin.register(TradeMessage)
class TradeMessageAdmin(admin.ModelAdmin):
	list_display = ('trade_request', 'sender', 'created_at')
	search_fields = ('trade_request__listing__title', 'sender__username', 'content')


@admin.register(StoreVerificationRequest)
class StoreVerificationRequestAdmin(admin.ModelAdmin):
	list_display = ('store', 'status', 'created_at', 'reviewed_at')
	list_filter = ('status',)
	search_fields = ('store__username', 'message')
	ordering = ('-created_at',)
	actions = ('approve_requests', 'reject_requests')

	@admin.action(description='Aprovar verificação selecionada')
	def approve_requests(self, request, queryset):
		for req in queryset:
			req.status = StoreVerificationRequest.APPROVED
			req.reviewed_at = timezone.now()
			req.save(update_fields=['status', 'reviewed_at'])
			profile = StoreProfile.objects.filter(user=req.store).first()
			if profile and not profile.verified:
				profile.verified = True
				profile.save(update_fields=['verified'])
			notify(
				req.store,
				'Loja verificada!',
				'Sua solicitação de verificação foi aprovada. Sua loja agora exibe o selo verificado.',
				url='/perfil/%s/' % req.store.username,
				category=Notification.SYSTEM,
				icon='verified',
			)
		self.message_user(request, f'{queryset.count()} solicitação(ões) aprovada(s).')

	@admin.action(description='Recusar verificação selecionada')
	def reject_requests(self, request, queryset):
		for req in queryset:
			req.status = StoreVerificationRequest.REJECTED
			req.reviewed_at = timezone.now()
			req.save(update_fields=['status', 'reviewed_at'])
			notify(
				req.store,
				'Verificação não aprovada',
				'Sua solicitação de verificação foi recusada. Você pode enviar uma nova solicitação com documentos válidos.',
				url='/loja/verificacao/',
				category=Notification.SYSTEM,
				icon='gpp_bad',
			)
		self.message_user(request, f'{queryset.count()} solicitação(ões) recusada(s).')


@admin.register(ListingReport)
class ListingReportAdmin(admin.ModelAdmin):
	list_display = ('listing', 'reason', 'reporter', 'status', 'created_at')
	list_filter = ('status', 'reason')
	search_fields = ('listing__title', 'reporter__username', 'detail')
	ordering = ('-created_at',)
	actions = ('delete_reported_listings', 'ban_sellers', 'mark_reviewed', 'dismiss_reports')

	@admin.action(description='Excluir anúncio denunciado')
	def delete_reported_listings(self, request, queryset):
		listings = {r.listing_id: r.listing for r in queryset}
		for listing in listings.values():
			listing.delete()
		queryset.update(status=ListingReport.REVIEWED)
		self.message_user(request, f'{len(listings)} anúncio(s) excluído(s).')

	@admin.action(description='Banir vendedor e excluir anúncios')
	def ban_sellers(self, request, queryset):
		sellers = {}
		for r in queryset.select_related('listing__seller'):
			seller = r.listing.seller
			if seller and not seller.is_superuser:
				sellers[seller.id] = seller
		for seller in sellers.values():
			_ban_user(seller)
		queryset.update(status=ListingReport.REVIEWED)
		self.message_user(request, f'{len(sellers)} vendedor(es) banido(s).')

	@admin.action(description='Marcar como resolvida')
	def mark_reviewed(self, request, queryset):
		queryset.update(status=ListingReport.REVIEWED)

	@admin.action(description='Descartar denúncia')
	def dismiss_reports(self, request, queryset):
		queryset.update(status=ListingReport.DISMISSED)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
	list_display = ('user', 'label', 'city', 'state', 'is_default')
	list_filter = ('state', 'is_default')
	search_fields = ('user__username', 'label', 'city', 'street')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('recipient', 'category', 'title', 'is_read', 'created_at')
	list_filter = ('category', 'is_read')
	search_fields = ('recipient__username', 'title', 'message')
	ordering = ('-created_at',)
	list_per_page = 30