from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Order, PaymentTransaction, Category, Listing


class WebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='buyer', password='Pwd12345!')
        self.cat = Category.objects.create(name='Misc')
        self.listing = Listing.objects.create(
            seller=self.user,
            category=self.cat,
            title='Item',
            description='Desc',
            price=10,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )
        self.order = Order.objects.create(buyer=self.user, payment_method=Order.PIX, delivery_method=Order.TO_AGREE)
        self.tx = PaymentTransaction.objects.create(order=self.order, gateway=PaymentTransaction.MERCADO_PAGO, amount=10, external_reference=f'order-{self.order.pk}', preference_id='pref_123')

    def test_webhook_updates_by_preference_id(self):
        url = reverse('mp_webhook')
        payload = {'type': 'payment', 'data': {'id': '1', 'status': 'approved', 'preference_id': 'pref_123'}}
        resp = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.APPROVED)

    def test_webhook_updates_by_external_reference(self):
        url = reverse('mp_webhook')
        payload = {'type': 'payment', 'data': {'id': '2', 'status': 'pending', 'external_reference': f'order-{self.order.pk}'}}
        resp = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.PENDING)
