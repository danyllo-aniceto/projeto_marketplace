"""Cria (ou garante) um superusuario a partir de variaveis de ambiente.

Util em hosts sem shell interativo (ex.: Render Free), onde nao da para rodar
`createsuperuser`. E idempotente: se o usuario ja existe, nao faz nada.

Variaveis lidas:
  DJANGO_SUPERUSER_USERNAME  (obrigatoria)
  DJANGO_SUPERUSER_PASSWORD  (obrigatoria)
  DJANGO_SUPERUSER_EMAIL     (opcional)
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Cria um superusuario a partir das variaveis DJANGO_SUPERUSER_*'

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'createadmin: DJANGO_SUPERUSER_USERNAME/PASSWORD nao definidos; pulando.'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f'createadmin: usuario "{username}" ja existe; nada a fazer.'
            ))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            f'createadmin: superusuario "{username}" criado com sucesso.'
        ))
