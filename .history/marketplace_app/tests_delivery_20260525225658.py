from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Order, Delivery, Category, Listing


class DeliveryWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username='buyer2', password='Pwd12345!')
        self.cat = Category.objects.create(name='Books')
        self.listing = Listing.objects.create(
            seller=self.user,
            category=self.cat,
            title='Livro',
            description='Desc',
            price=20,
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )
        self.order = Order.objects.create(buyer=self.user, payment_method=Order.PIX, delivery_method=Order.PLATFORM_SHIPPING)
        self.delivery = Delivery.objects.create(order=self.order, recipient_name='Dest', recipient_phone='(11) 99999-9999', postal_code='00000-000', street='Rua', number='1', neighborhood='Bairro', city='Cidade', state='SP')

    def test_update_delivery_status_and_tracking(self):
        url = reverse('api_delivery_update', args=[self.order.pk])
        payload = {'status': Delivery.IN_TRANSIT, 'tracking_code': 'ABC123', 'carrier_name': 'CarrierX', 'estimated_delivery_date': '2026-06-01'}
        resp = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.IN_TRANSIT)
        self.assertEqual(self.delivery.tracking_code, 'ABC123')
        self.assertEqual(self.delivery.carrier_name, 'CarrierX')

    def test_invalid_status_returns_400(self):
        url = reverse('api_delivery_update', args=[self.order.pk])
        payload = {'status': 'not_a_status'}
        resp = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 400)
