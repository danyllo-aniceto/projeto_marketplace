from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Listing, Order, OrderItem, TradeProposal, TradeRequest


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

    def test_history_separates_sent_and_received_trades(self):
        sent_listing = Listing.objects.create(
            seller=self.buyer,
            category=self.category,
            title='Tablet Semi-novo',
            description='Outro anúncio para troca',
            price=Decimal('900.00'),
            listing_type=Listing.TRADE,
            condition=Listing.USED,
        )
        sent_trade = TradeRequest.objects.create(
            requester=self.seller,
            counterparty=self.buyer,
            listing=sent_listing,
            initial_message='Troca solicitada por mim.',
        )
        TradeProposal.objects.create(
            trade_request=sent_trade,
            proposer=self.seller,
            item_description='Celular usado',
            cash_amount=Decimal('120.00'),
            note='Minha proposta inicial.',
        )

        received_listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Mouse Gamer',
            description='Acessório',
            price=Decimal('150.00'),
            listing_type=Listing.TRADE,
            condition=Listing.USED,
        )
        received_trade = TradeRequest.objects.create(
            requester=self.other_buyer,
            counterparty=self.seller,
            listing=received_listing,
            initial_message='Quero trocar este item.',
        )
        TradeProposal.objects.create(
            trade_request=received_trade,
            proposer=self.other_buyer,
            item_description='Teclado mecânico',
            cash_amount=Decimal('0.00'),
            note='Sem volta em dinheiro.',
        )

        response = self.client.get(reverse('history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trocas solicitadas (1)')
        self.assertContains(response, 'Trocas recebidas (1)')
        self.assertContains(response, 'Troca solicitada por mim.')
        self.assertContains(response, 'Quero trocar este item.')
        self.assertContains(response, 'Celular usado')
        self.assertContains(response, 'Teclado mecânico')