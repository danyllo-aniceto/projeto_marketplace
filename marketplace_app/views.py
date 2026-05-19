from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import models
from django.contrib import messages
from rest_framework import generics
from .models import Listing
from .serializers import ListingSerializer
from .forms import ListingForm, CommentForm, UserProfileForm, CommonProfileForm, StoreProfileForm
from .models import Listing, ListingImage, Category, StoreProfile, CommonProfile, Comment, Cart, CartItem
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import RegisterSerializer


def home(request):
    # Pegar categoria do slug se fornecida
    category_slug = request.GET.get('categoria')
    selected_category = None
    
    # Últimos produtos para o carrossel (últimos 5 criados)
    carousel_products = Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at')[:5]

    # Destaques: anúncios patrocinados ou de lojas
    featured_products = Listing.objects.prefetch_related('images').filter(
        status='active'
    ).filter(
        models.Q(is_featured=True) | models.Q(is_store_featured=True)
    ).order_by('-created_at')[:12]

    # Todos os anúncios (filtrados por categoria se fornecida)
    all_products = Listing.objects.prefetch_related('images').filter(status='active').order_by('-created_at')
    
    if category_slug and category_slug != 'todos':
        try:
            selected_category = Category.objects.get(slug=category_slug)
            all_products = all_products.filter(category=selected_category)
        except Category.DoesNotExist:
            pass

    # Categorias cadastradas
    categories = Category.objects.all()

    context = {
        'carousel_products': carousel_products,
        'featured_products': featured_products,
        'anuncios': all_products,
        'categories': categories,
        'selected_category': selected_category,
    }

    return render(request, 'home.html', context)


@login_required
def my_listings(request):
    listings = request.user.listings.order_by('-created_at')
    return render(request, 'marketplace_app/my_listings.html', {
        'listings': listings,
    })


@login_required
def edit_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            image = request.FILES.get('image')
            if image:
                ListingImage.objects.create(listing=anuncio, image=image)

            return redirect('my_listings')
    else:
        form = ListingForm(instance=listing, user=request.user)

    return render(request, 'marketplace_app/edit_listing.html', {
        'form': form,
        'listing': listing,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    comment_form = CommentForm()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.listing = listing
            comment.user = request.user
            comment.save()
            return redirect('listing_detail', pk=pk)

    comments = listing.comments.select_related('user').order_by('-created_at')
    in_cart = False

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        in_cart = cart.items.filter(listing=listing).exists()

    return render(request, 'marketplace_app/listing_detail.html', {
        'listing': listing,
        'comments': comments,
        'comment_form': comment_form,
        'in_cart': in_cart,
    })


@login_required
def add_to_cart(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status='active')
    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.get_or_create(cart=cart, listing=listing)
    return redirect('cart')


@login_required
def delete_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method == 'POST':
        listing.delete()
        return redirect('my_listings')
    return redirect('edit_listing', pk=pk)


@login_required
def remove_from_cart(request, pk):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.filter(cart=cart, pk=pk).delete()
    return redirect('cart')


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('listing').all()
    total = sum(item.listing.price for item in items)

    return render(request, 'marketplace_app/cart.html', {
        'cart': cart,
        'items': items,
        'total': total,
    })


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


@login_required
def criar_anuncio(request):
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            anuncio = form.save(commit=False)
            anuncio.seller = request.user
            anuncio.save()

            # Processar imagem
            image = request.FILES.get('image')
            if image:
                ListingImage.objects.create(listing=anuncio, image=image)

            return redirect('home')
    else:
        form = ListingForm(user=request.user)

    return render(request, 'marketplace_app/criar_anuncio.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            else:
                request.session.set_expiry(0)  # Browser session
            return redirect('home')
        else:
            messages.error(request, 'Credenciais inválidas.')

    return render(request, 'users/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')


def user_register(request):
    if request.method == 'POST':
        account_type = request.POST.get('account_type')

        if account_type == 'individual':
            # Criar usuário pessoa física
            User = get_user_model()
            user = User.objects.create_user(
                username=request.POST.get('username'),
                email=request.POST.get('email'),
                password=request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                is_store=False
            )

            # Criar perfil comum
            CommonProfile.objects.create(
                user=user,
                cpf=request.POST.get('cpf')
            )

            messages.success(request, 'Conta criada com sucesso! Faça o login.')
            return redirect('login')

        elif account_type == 'store':
            # Criar usuário loja
            User = get_user_model()
            user = User.objects.create_user(
                username=request.POST.get('store_username'),
                email=request.POST.get('store_email'),
                password=request.POST.get('store_password'),
                first_name=request.POST.get('responsible_name'),
                is_store=True
            )

            # Criar perfil de loja
            StoreProfile.objects.create(
                user=user,
                cnpj=request.POST.get('cnpj'),
                razao_social=request.POST.get('company_name'),
                verified=False
            )

            messages.success(request, 'Conta de loja criada com sucesso! Aguarde verificação.')
            return redirect('login')

    return render(request, 'users/register.html')


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        is_store = request.POST.get('is_store') == 'on'

        user = get_user_model().objects.create_user(
            username=username,
            password=password,
            is_store=is_store
        )

        login(request, user)
        return redirect('home')

    return render(request, 'users/register.html')

class ListingListAPIView(generics.ListAPIView):
    queryset = Listing.objects.all().order_by('-created_at')
    serializer_class = ListingSerializer

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Usuário criado com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)