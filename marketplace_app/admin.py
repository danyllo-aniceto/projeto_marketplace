from django.contrib import admin
from .models import User, Category, Listing, ListingImage, StoreProfile, CommonProfile

# Registrando os modelos para aparecerem no seu print aí
admin.site.register(User)
admin.site.register(Category)
admin.site.register(Listing)
admin.site.register(ListingImage)
admin.site.register(StoreProfile)
admin.site.register(CommonProfile)