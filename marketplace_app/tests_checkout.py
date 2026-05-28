from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Cart, CartItem, Category, Listing, Order, PaymentTransaction


class CheckoutFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username='buyer', email='buyer@example.com', password='Pwd12345!')
        self.seller = User.objects.create_user(username='seller', email='seller@example.com', password='Pwd12345!')
        self.category = Category.objects.create(name='Eletrônicos')
        self.listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Fone Bluetooth',
            description='Descrição do produto',
            price=Decimal('199.90'),
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, listing=self.listing, desired_action=CartItem.BUY)
        self.client.login(username='buyer', password='Pwd12345!')

    def _checkout_data(self):
        return {
            'payment_method': Order.PIX,
            'delivery_method': Order.TO_AGREE,
            'notes': 'Entregar em horário comercial',
            'recipient_name': 'João Silva',
            'recipient_phone': '(11) 99999-9999',
            'postal_code': '01001-000',
            'street': 'Rua das Flores',
            'number': '123',
            'complement': 'Apto 45',
            'neighborhood': 'Centro',
            'city': 'São Paulo',
            'state': 'SP',
        }

    def test_checkout_generates_simulated_qr_before_finalizing_order(self):
        checkout_url = reverse('checkout')

        response = self.client.post(checkout_url, self._checkout_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'QR code de simulação')
        self.assertEqual(Order.objects.count(), 0)
        self.assertIn('checkout_pending_purchase', self.client.session)

        confirm_response = self.client.post(checkout_url, {'confirm_purchase': '1'}, follow=True)

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get(buyer=self.buyer)
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(order.items.count(), 1)

        payment_transaction = PaymentTransaction.objects.get(order=order)
        self.assertEqual(payment_transaction.status, PaymentTransaction.APPROVED)
        self.assertFalse(payment_transaction.checkout_url)

        self.assertNotIn('checkout_pending_purchase', self.client.session)