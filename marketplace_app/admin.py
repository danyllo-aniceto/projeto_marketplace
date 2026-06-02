from django.contrib import admin
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
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ('username', 'email', 'is_store', 'is_active', 'date_joined')
	list_filter = ('is_store', 'is_active', 'is_staff')
	search_fields = ('username', 'email')


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