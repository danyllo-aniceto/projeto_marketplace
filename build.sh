#!/usr/bin/env bash
# Script de build usado pelo Render (Build Command: ./build.sh)
# Encerra na primeira falha.
set -o errexit

pip install -r requirements.txt

# Coleta os estáticos (WhiteNoise comprime e versiona)
python manage.py collectstatic --no-input

# Aplica as migrações no banco
python manage.py migrate

# Cria o superusuário a partir das variáveis DJANGO_SUPERUSER_* (idempotente).
# Em hosts sem shell (Render Free) é assim que se cria o admin.
python manage.py createadmin
