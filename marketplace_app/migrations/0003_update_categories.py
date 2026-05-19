from django.db import migrations
from django.utils.text import slugify # Importante para gerar o slug

def create_categories(apps, schema_editor):
    Category = apps.get_model('marketplace_app', 'Category')
    
    # Remove Eletrônicos se existir
    Category.objects.filter(name='Eletrônicos').delete()
    
    categories = [
        'Dispositivos pessoais',
        'Informática',
        'Games',
        'TV e audio',
        'Foto e video',
        'Todos'
    ]
    
    for category_name in categories:
        # Aqui está o pulo do gato: passamos o slug no get_or_create
        Category.objects.get_or_create(
            name=category_name,
            defaults={'slug': slugify(category_name)}
        )

def reverse_categories(apps, schema_editor):
    Category = apps.get_model('marketplace_app', 'Category')
    Category.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0002_listing_is_featured_listing_is_store_featured'),
    ]

    operations = [
        migrations.RunPython(create_categories, reverse_categories),
    ]