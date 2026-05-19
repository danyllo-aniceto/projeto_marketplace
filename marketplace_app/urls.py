from django.urls import path
from . import views
from .views import ListingListAPIView

urlpatterns = [
    path('', views.home, name='home'),
    path('criar-anuncio/', views.criar_anuncio, name='criar_anuncio'),
    path('meus-anuncios/', views.my_listings, name='my_listings'),
    path('editar-perfil/', views.edit_profile, name='edit_profile'),
    path('perfil/<str:username>/', views.user_profile, name='user_profile'),
    path('editar-anuncio/<int:pk>/', views.edit_listing, name='edit_listing'),
    path('excluir-anuncio/<int:pk>/', views.delete_listing, name='delete_listing'),
    path('anuncio/<int:pk>/', views.listing_detail, name='listing_detail'),
    path('carrinho/', views.cart_view, name='cart'),
    path('adicionar-carrinho/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('remover-carrinho/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    path('api/listings/', ListingListAPIView.as_view(), name='api-listings'),
    path('api/register/', views.RegisterView.as_view(), name='api_register'),
]