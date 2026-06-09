"""
Data migration que popula o banco com dados de demonstração.

Le o arquivo seed_render.sql (na raiz do projeto) e executa seu conteudo.
Roda automaticamente no deploy da Render (build.sh -> manage.py migrate),
de dentro da rede da Render, sem depender de conexao externa nem de Shell.

E idempotente: se o usuario sentinela (id=1000) ja existe, nao faz nada.
"""
import os
import re

from django.conf import settings
from django.db import migrations


# Usuario sentinela do seed (primeiro PF). Se ja existir, assume que o seed
# ja rodou e nao faz nada. Nao usamos o 'admin' aqui porque ele e criado
# separadamente pelo comando createadmin.
SENTINEL_USER_ID = 1001


def _load_seed_sql():
    """Localiza e le o seed_render.sql, removendo o BEGIN/COMMIT externo
    (a migration ja roda dentro de uma transacao)."""
    candidates = [
        os.path.join(settings.BASE_DIR, "seed_render.sql"),
        os.path.join(os.path.dirname(__file__), "..", "..", "seed_render.sql"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            # Remove os comandos de transacao do proprio arquivo
            sql = re.sub(r"(?im)^\s*(BEGIN|COMMIT)\s*;\s*$", "", sql)
            return sql
    raise FileNotFoundError(
        "seed_render.sql nao encontrado. Confirme que o arquivo esta versionado na raiz do projeto."
    )


def apply_seed(apps, schema_editor):
    User = apps.get_model("marketplace_app", "User")
    if User.objects.filter(id=SENTINEL_USER_ID).exists():
        # Ja foi populado anteriormente; nada a fazer.
        return

    sql = _load_seed_sql()
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def reverse_seed(apps, schema_editor):
    """Remove os dados de demonstracao (apaga usuarios do seed; o CASCADE
    cuida de anuncios, pedidos, etc.)."""
    User = apps.get_model("marketplace_app", "User")
    User.objects.filter(id__gte=1000).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace_app", "0025_user_strikes"),
    ]

    operations = [
        migrations.RunPython(apply_seed, reverse_seed),
    ]
