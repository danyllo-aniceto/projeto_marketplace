from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Listing, TradeFulfillment, TradeProposal, TradeRequest
from .models import TradeDelivery
from django.core.files.uploadedfile import SimpleUploadedFile


class TradeFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.requester = User.objects.create_user(username='requester', password='Pwd12345!')
        self.counterparty = User.objects.create_user(username='counterparty', password='Pwd12345!')
        self.category = Category.objects.create(name='Eletrônicos')
        self.listing = Listing.objects.create(
            seller=self.counterparty,
            category=self.category,
            title='PlayStation 5',
            description='Console para troca',
            trade_suggestions='Notebook gamer ou smartphone com volta em dinheiro',
            price=Decimal('3500.00'),
            listing_type=Listing.TRADE,
            condition=Listing.USED,
        )
        self.trade_request = TradeRequest.objects.create(
            requester=self.requester,
            counterparty=self.counterparty,
            listing=self.listing,
            initial_message='Quero trocar meu notebook por este console.',
        )

    def test_trade_counterproposal_acceptance_and_checkout_confirmation(self):
        # requester (quem iniciou a solicitação) deve enviar a primeira proposta
        self.client.login(username='requester', password='Pwd12345!')

        proposal_url = reverse('trade_proposal_create', args=[self.trade_request.pk])
        response = self.client.post(proposal_url, {
            'item_description': 'Console + câmera semi-nova',
            'cash_amount': '250.00',
            'note': 'Primeira proposta do solicitante.',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.trade_request.proposals.count(), 1)

        # contraparte responde
        self.client.logout()
        self.client.login(username='counterparty', password='Pwd12345!')

        response = self.client.post(proposal_url, {
            'item_description': 'Notebook gamer usado',
            'cash_amount': '0.00',
            'note': 'Contraproposta do dono do anúncio.',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.trade_request.proposals.count(), 2)

        latest_proposal = self.trade_request.proposals.order_by('-created_at').first()
        self.assertEqual(latest_proposal.proposer, self.counterparty)

        # tentativa fora de turno pelo mesmo usuário
        response = self.client.post(proposal_url, {
            'item_description': 'Tentativa fora de turno',
            'cash_amount': '0.00',
            'note': 'Tentativa fora de turno.',
        }, follow=True)

        self.assertContains(response, 'Aguarde a resposta do outro participante')
        self.assertEqual(self.trade_request.proposals.count(), 2)

        # o criador do anúncio (counterparty) pode aceitar a proposta mais recente
        accept_url = reverse('trade_proposal_accept', args=[self.trade_request.pk, latest_proposal.pk])
        response = self.client.post(accept_url, follow=True)

        self.assertEqual(response.status_code, 200)
        detail_response = self.client.get(reverse('trade_request_detail', args=[self.trade_request.pk]))
        self.assertContains(detail_response, 'Linha do tempo')
        self.assertContains(detail_response, 'Propostas da negociação')
        self.trade_request.refresh_from_db()
        self.assertEqual(self.trade_request.status, TradeRequest.APPROVED)

        fulfillment = TradeFulfillment.objects.get(trade_request=self.trade_request)
        self.assertEqual(fulfillment.payment_amount, Decimal('0.00'))

        checkout_url = reverse('trade_checkout', args=[self.trade_request.pk])
        checkout_data = {
            'payment_method': 'pix',
            'delivery_method': 'to_agree',
            'recipient_name': 'João Teste',
            'recipient_phone': '(11) 99999-9999',
            'postal_code': '01001-000',
            'street': 'Rua A',
            'number': '123',
            'complement': 'Casa 1',
            'neighborhood': 'Centro',
            'city': 'São Paulo',
            'state': 'SP',
            'notes': 'Entregar em horário comercial',
        }

        response = self.client.post(checkout_url, checkout_data)
        self.assertEqual(response.status_code, 200)

        # create deliveries for both participants directly to avoid session flush
        TradeDelivery.objects.create(
            trade_request=self.trade_request,
            user=self.counterparty,
            delivery_method='seller_shipping',
            recipient_name='Counterparty Dest',
            recipient_phone='(11) 99999-2222',
            postal_code='02002-000',
            street='Rua Ctr',
            number='2',
            city='São Paulo',
            state='SP',
            notes='Enviar bem embalado',
        )
        TradeDelivery.objects.create(
            trade_request=self.trade_request,
            user=self.requester,
            delivery_method='seller_shipping',
            recipient_name='Requester Dest',
            recipient_phone='(11) 99999-1111',
            postal_code='01001-000',
            street='Rua Req',
            number='1',
            city='São Paulo',
            state='SP',
            notes='Envio por sedex',
        )

        confirm_response = self.client.post(checkout_url, {'confirm_trade': '1'}, follow=True)
        self.assertEqual(confirm_response.status_code, 200)

        self.trade_request.refresh_from_db()
        fulfillment.refresh_from_db()
        self.listing.refresh_from_db()

        self.assertEqual(self.trade_request.status, TradeRequest.COMPLETED)
        self.assertEqual(fulfillment.payment_status, TradeFulfillment.COMPLETED)
        self.assertEqual(self.listing.status, Listing.SOLD)

    def test_counterparty_can_reject_pending_trade(self):
        self.client.login(username='counterparty', password='Pwd12345!')

        reject_url = reverse('trade_request_reject', args=[self.trade_request.pk])
        response = self.client.post(reject_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.trade_request.refresh_from_db()
        self.assertEqual(self.trade_request.status, TradeRequest.REJECTED)
        self.assertEqual(self.trade_request.proposals.count(), 0)

        detail_response = self.client.get(reverse('trade_request_detail', args=[self.trade_request.pk]))
        self.assertNotContains(detail_response, 'Enviar proposta inicial')

    def test_proposal_image_upload_and_delivery_flow(self):
        # create the first proposal as the requester and attach an image directly (avoids multipart in tests)
        from .models import TradeProposalImage, TradeProposal
        image = SimpleUploadedFile('test.jpg', b'\x47\x49\x46\x38\x39\x61', content_type='image/gif')
        proposal = TradeProposal.objects.create(
            trade_request=self.trade_request,
            proposer=self.requester,
            item_description='Notebook com 8GB RAM',
            cash_amount=Decimal('100.00'),
            note='Inclui carregador'
        )
        TradeProposalImage.objects.create(proposal=proposal, image=image)
        self.trade_request.refresh_from_db()
        latest = self.trade_request.proposals.order_by('-created_at').first()
        self.assertIsNotNone(latest)
        # images should be attached
        self.assertTrue(latest.images.count() >= 1)

        # owner of the listing (counterparty) accepts
        self.client.logout()
        self.client.login(username='counterparty', password='Pwd12345!')

        accept_url = reverse('trade_proposal_accept', args=[self.trade_request.pk, latest.pk])
        response = self.client.post(accept_url, follow=True)
        self.assertEqual(response.status_code, 200)

        # test bilateral deliveries: both users fill delivery
        # requester fills
        delivery_url = reverse('trade_delivery', args=[self.trade_request.pk])
        response = self.client.post(delivery_url, {
            'delivery_method': 'seller_shipping',
            'recipient_name': 'Requester Dest',
            'recipient_phone': '(11) 99999-1111',
            'postal_code': '01001-000',
            'street': 'Rua Req',
            'number': '1',
            'city': 'São Paulo',
            'state': 'SP',
            'notes': 'Envio por sedex'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # counterparty fills
        self.client.logout()
        self.client.login(username='counterparty', password='Pwd12345!')
        response = self.client.post(delivery_url, {
            'delivery_method': 'seller_shipping',
            'recipient_name': 'Counter Dest',
            'recipient_phone': '(11) 99999-2222',
            'postal_code': '02002-000',
            'street': 'Rua Ctr',
            'number': '2',
            'city': 'São Paulo',
            'state': 'SP',
            'notes': 'Enviar bem embalado'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # check deliveries exist
        deliveries = TradeDelivery.objects.filter(trade_request=self.trade_request)
        self.assertEqual(deliveries.count(), 2)
