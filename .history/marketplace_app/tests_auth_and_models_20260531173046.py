from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .category_catalog import CANONICAL_CATEGORY_NAMES
from .models import Category, Listing, Cart, CartItem, Order, OrderItem


class AuthAndModelTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='u1', email='u1@example.com', password='Pwd12345!')
        # create category
        self.category = Category.objects.create(name='Eletrônicos')

    def test_login_view_authenticates_user(self):
        url = reverse('login')
        response = self.client.post(url, {'username': 'u1', 'password': 'Pwd12345!'})
        self.assertEqual(response.status_code, 302)
        # session should have auth id
        session = self.client.session
        self.assertIn('_auth_user_id', session)

    def test_category_catalog_has_canonical_entries(self):
        category_names = set(Category.objects.values_list('name', flat=True))

        for category_name in CANONICAL_CATEGORY_NAMES:
            self.assertIn(category_name, category_names)

    def test_change_password_view_changes_password(self):
        # login first
        self.client.login(username='u1', password='Pwd12345!')
        url = reverse('change_password')
        response = self.client.post(url, {'old_password': 'Pwd12345!', 'new_password': 'NewPwd123!', 'confirm_password': 'NewPwd123!'})
        self.assertEqual(response.status_code, 302)
        # ensure user can login with new password
        self.client.logout()
        login_ok = self.client.login(username='u1', password='NewPwd123!')
        self.assertTrue(login_ok)

    def test_listing_price_validation(self):
        # price <= 0 should raise ValidationError
        listing = Listing(
            seller=self.user,
            category=self.category,
            title='Produto',
            description='Desc',
            price=0,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )
        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_store_cannot_set_used_or_trade(self):
        User = get_user_model()
        store_user = User.objects.create_user(username='store1', password='Pwd12345!', is_store=True)
        # used condition should raise
        listing = Listing(
            seller=store_user,
            category=self.category,
            title='Loja Produto',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.USED,
        )
        with self.assertRaises(ValidationError):
            listing.full_clean()

        # trade listing should raise
        listing2 = Listing(
            seller=store_user,
            category=self.category,
            title='Loja Produto 2',
            description='Desc',
            price=10,
            listing_type=Listing.TRADE,
            condition=Listing.NEW,
        )
        with self.assertRaises(ValidationError):
            listing2.full_clean()

    def test_cartitem_trade_buy_validation(self):
        # create a listing that is trade-only
        trade_listing = Listing.objects.create(
            seller=self.user,
            category=self.category,
            title='Troca Apenas',
            description='Desc',
            price=None,
            listing_type=Listing.TRADE,
            trade_suggestions='Notebook ou smartphone',
            condition=Listing.USED,
        )

        cart = Cart.objects.create(user=self.user)

        # trying to add as BUY should raise
        cart_item = CartItem(cart=cart, listing=trade_listing, desired_action=CartItem.BUY)
        with self.assertRaises(ValidationError):
            cart_item.full_clean()

    def test_edit_listing_is_blocked_when_order_is_processing(self):
        buyer = get_user_model().objects.create_user(username='buyer1', password='Pwd12345!')
        listing = Listing.objects.create(
            seller=self.user,
            category=self.category,
            title='Produto à venda',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )
        order = Order.objects.create(
            buyer=buyer,
            payment_method=Order.PIX,
            delivery_method=Order.TO_AGREE,
            status=Order.PENDING_PAYMENT,
            total_amount=10,
        )
        OrderItem.objects.create(
            order=order,
            listing=listing,
            seller=self.user,
            title_snapshot=listing.title,
            unit_price_snapshot=listing.price,
            quantity=1,
        )

        self.client.login(username='u1', password='Pwd12345!')
        response = self.client.get(reverse('edit_listing', args=[listing.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este anúncio já está vinculado a uma compra ou troca em andamento e não pode ser editado.')

    def test_edit_listing_page_uses_custom_controls(self):
        listing = Listing.objects.create(
            seller=self.user,
            category=self.category,
            title='Produto editável',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )

        self.client.login(username='u1', password='Pwd12345!')
        response = self.client.get(reverse('edit_listing', args=[listing.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'listing-page-header')
        self.assertContains(response, 'Selecionar Imagens')
        self.assertContains(response, 'id_listing_type')
        self.assertContains(response, 'id_trade_suggestions')

    def test_cannot_add_own_listing_to_cart(self):
        listing = Listing.objects.create(
            seller=self.user,
            category=self.category,
            title='Produto próprio',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )

        self.client.login(username='u1', password='Pwd12345!')
        response = self.client.get(reverse('add_to_cart', args=[listing.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Você não pode adicionar ao carrinho um anúncio criado por você.')
        self.assertEqual(CartItem.objects.filter(cart__user=self.user, listing=listing).count(), 0)

    def test_detail_page_hides_cart_action_for_own_listing(self):
        listing = Listing.objects.create(
            seller=self.user,
            category=self.category,
            title='Produto próprio detalhe',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )

        self.client.login(username='u1', password='Pwd12345!')
        response = self.client.get(reverse('listing_detail', args=[listing.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Seu anúncio')
        self.assertNotContains(response, 'Adicionar ao Carrinho')
