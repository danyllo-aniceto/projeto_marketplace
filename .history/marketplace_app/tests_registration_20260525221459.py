from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import CommonProfile, StoreProfile


class RegistrationIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')

    def test_individual_registration_creates_user_and_profile(self):
        data = {
            'account_type': 'individual',
            'first_name': 'Test',
            'last_name': 'User',
            'cpf': '000.000.000-00',
            'birth_date': '1990-01-01',
            'email': 'test@example.com',
            'phone': '(11) 99999-9999',
            'username': 'testuser',
            'password': 'ComplexPwd123!',
            'cep': '00000-000',
            'address': 'Rua Test, 123',
        }

        response = self.client.post(self.register_url, data)
        # should redirect to login on success
        self.assertEqual(response.status_code, 302)
        User = get_user_model()
        user = User.objects.filter(username='testuser').first()
        self.assertIsNotNone(user)
        # profile created
        profile = CommonProfile.objects.filter(user=user).first()
        self.assertIsNotNone(profile)

    def test_store_registration_creates_user_and_store_profile(self):
        data = {
            'account_type': 'store',
            'store_username': 'storeuser',
            'store_password': 'AnotherPwd123!',
            'store_email': 'store@example.com',
            'cnpj': '00.000.000/0000-00',
            'company_name': 'ACME Ltda',
            'fantasy_name': 'ACME',
            'state_registration': '12345',
            'responsible_name': 'Owner',
            'responsible_cpf': '111.111.111-11',
            'store_phone': '(11) 98888-8888',
            'store_cep': '00000-000',
            'store_address': 'Rua Loja, 10',
        }

        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 302)
        User = get_user_model()
        user = User.objects.filter(username='storeuser').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_store)
        profile = StoreProfile.objects.filter(user=user).first()
        self.assertIsNotNone(profile)
