from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Listing, Order, OrderItem


class HistoryViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username='buyer', password='Pwd12345!')
        self.seller = User.objects.create_user(username='seller', password='Pwd12345!')
        self.other_buyer = User.objects.create_user(username='other', password='Pwd12345!')
        self.category = Category.objects.create(name='Eletrônicos')

        self.listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Notebook Gamer',
            description='Descrição',
            price=Decimal('3500.00'),
            listing_type=Listing.SALE,
            condition=Listing.NEW,
        )

        self.purchase_order = Order.objects.create(
            buyer=self.seller,
            payment_method=Order.PIX,
            delivery_method=Order.TO_AGREE,
            total_amount=Decimal('3500.00'),
        )
        OrderItem.objects.create(
            order=self.purchase_order,
            listing=self.listing,
            seller=self.seller,
            title_snapshot=self.listing.title,
            unit_price_snapshot=self.listing.price,
            quantity=1,
        )

        self.sale_order = Order.objects.create(
            buyer=self.other_buyer,
            payment_method=Order.PIX,
            delivery_method=Order.TO_AGREE,
            total_amount=Decimal('3500.00'),
        )
        self.sale_item = OrderItem.objects.create(
            order=self.sale_order,
            listing=self.listing,
            seller=self.seller,
            title_snapshot=self.listing.title,
            unit_price_snapshot=self.listing.price,
            quantity=1,
        )

        self.client.login(username='seller', password='Pwd12345!')

    def test_history_view_shows_purchases_and_sales_paginated(self):
        response = self.client.get(reverse('history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Histórico')
        self.assertContains(response, 'Compras (1)')
        self.assertContains(response, 'Vendas (2)')
        self.assertContains(response, 'seller')
        self.assertContains(response, 'Notebook Gamer')
        self.assertContains(response, 'other')

    def test_history_tab_pagination_works(self):
        for index in range(7):
            order = Order.objects.create(
                buyer=self.seller,
                payment_method=Order.PIX,
                delivery_method=Order.TO_AGREE,
                total_amount=Decimal('10.00'),
            )
            OrderItem.objects.create(
                order=order,
                listing=self.listing,
                seller=self.seller,
                title_snapshot=f'Item {index}',
                unit_price_snapshot=Decimal('10.00'),
                quantity=1,
            )

        response = self.client.get(reverse('history'), {'purchase_page': 2, 'sale_page': 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['purchases_page_obj'].number, 2)