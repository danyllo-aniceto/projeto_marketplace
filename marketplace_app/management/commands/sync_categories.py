from django.core.management.base import BaseCommand

from marketplace_app.category_catalog import sync_category_catalog
from marketplace_app.models import Category


class Command(BaseCommand):
    help = 'Synchronize the category catalog with the canonical Tech Hub list.'

    def handle(self, *args, **options):
        sync_category_catalog(Category)
        self.stdout.write(self.style.SUCCESS('Category catalog synchronized successfully.'))