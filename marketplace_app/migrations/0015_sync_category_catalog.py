from django.db import migrations
from django.utils.text import slugify


LEGACY_CATEGORY_RENAMES = {
    'Eletrônicos': 'Componentes eletrônicos',
    'Dispositivos pessoais': 'Smartphones e tablets',
    'Informática': 'Computadores e notebooks',
    'Games': 'Games e consoles',
    'TV e audio': 'TV e áudio',
    'Foto e video': 'Foto e vídeo',
}


CANONICAL_CATEGORY_NAMES = [
    'Componentes eletrônicos',
    'Computadores e notebooks',
    'Smartphones e tablets',
    'Games e consoles',
    'Periféricos',
    'TV e áudio',
    'Foto e vídeo',
    'Acessórios e carregadores',
    'Rede e conectividade',
]


def forward(apps, schema_editor):
    Category = apps.get_model('marketplace_app', 'Category')

    for old_name, new_name in LEGACY_CATEGORY_RENAMES.items():
        legacy_category = Category.objects.filter(name=old_name).first()
        if legacy_category is None:
            continue

        if Category.objects.filter(name=new_name).exclude(pk=legacy_category.pk).exists():
            continue

        legacy_category.name = new_name
        legacy_category.slug = slugify(new_name)
        legacy_category.save(update_fields=['name', 'slug'])

    for category_name in CANONICAL_CATEGORY_NAMES:
        Category.objects.get_or_create(
            name=category_name,
            defaults={'slug': slugify(category_name)},
        )


def backward(apps, schema_editor):
    Category = apps.get_model('marketplace_app', 'Category')

    for category_name in CANONICAL_CATEGORY_NAMES:
        Category.objects.filter(name=category_name).delete()

    for old_name, new_name in LEGACY_CATEGORY_RENAMES.items():
        restored_category = Category.objects.filter(name=new_name).first()
        if restored_category is None:
            continue

        if Category.objects.filter(name=old_name).exclude(pk=restored_category.pk).exists():
            continue

        restored_category.name = old_name
        restored_category.slug = slugify(old_name)
        restored_category.save(update_fields=['name', 'slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0014_alter_commonprofile_cpf_alter_storeprofile_cnpj_and_more'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]