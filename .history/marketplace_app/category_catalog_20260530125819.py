from django.utils.text import slugify


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

LEGACY_CATEGORY_RENAMES = {
    'Eletrônicos': 'Componentes eletrônicos',
    'Dispositivos pessoais': 'Smartphones e tablets',
    'Informática': 'Computadores e notebooks',
    'Games': 'Games e consoles',
    'TV e audio': 'TV e áudio',
    'Foto e video': 'Foto e vídeo',
}


def sync_category_catalog(category_model):
    for old_name, new_name in LEGACY_CATEGORY_RENAMES.items():
        legacy_category = category_model.objects.filter(name=old_name).first()
        if legacy_category is None:
            continue

        if category_model.objects.filter(name=new_name).exclude(pk=legacy_category.pk).exists():
            continue

        legacy_category.name = new_name
        legacy_category.slug = slugify(new_name)
        legacy_category.save(update_fields=['name', 'slug'])

    for category_name in CANONICAL_CATEGORY_NAMES:
        category_model.objects.get_or_create(
            name=category_name,
            defaults={'slug': slugify(category_name)},
        )