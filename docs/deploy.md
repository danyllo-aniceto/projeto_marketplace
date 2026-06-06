# Checklist de Deploy — TechHub

O `settings.py` já é **env-driven** (via `django-environ`). Em desenvolvimento tudo
funciona com os defaults; em produção, defina as variáveis abaixo num arquivo `.env`
(ou nas variáveis de ambiente do servidor).

## 1. Variáveis de ambiente (.env)

```env
DEBUG=False
SECRET_KEY=<gere-uma-chave-longa-e-aleatoria>
ALLOWED_HOSTS=seudominio.com,www.seudominio.com

# Banco (exemplo PostgreSQL) — ajuste conforme seu settings de DB
# DATABASE_URL=postgres://user:senha@host:5432/nome

# Atrás de proxy/HTTPS (Heroku, Render, Nginx):
USE_X_FORWARDED_PROTO=True

# Opcionais de segurança (já têm default seguro quando DEBUG=False):
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True
# SECURE_SSL_REDIRECT=True
# SECURE_HSTS_SECONDS=31536000
```

Gerar SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 2. Proteções já ativas quando `DEBUG=False`
Definidas em `settings.py` (seção PRODUCTION HARDENING):
- Erro se `SECRET_KEY` for a insegura padrão.
- Erro se `ALLOWED_HOSTS` estiver vazio.
- `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` → `True`.
- HSTS de 1 ano, `X_FRAME_OPTIONS=DENY`.

## 3. Passos de publicação

```bash
# 1. Dependências
pip install -r requirements.txt

# 2. Migrações
python manage.py migrate

# 3. Arquivos estáticos (STATIC_ROOT = /staticfiles)
python manage.py collectstatic --noinput

# 4. Checagem de produção (não deve listar issues críticos)
python manage.py check --deploy

# 5. Servir com WSGI (exemplo)
gunicorn marketplace.wsgi:application
```

## 4. Servir estáticos e mídia
- **Estáticos**: servir `/staticfiles` (WhiteNoise ou Nginx).
- **Mídia** (`/media`): uploads de imagens/documentos — servir via Nginx ou storage
  externo (S3). Em produção não use o servidor de desenvolvimento para mídia.

## 5. Páginas de erro
- `templates/404.html` e `templates/500.html` já existem e são usadas automaticamente
  quando `DEBUG=False`.

## 6. Lembretes
- O pagamento é **simulado** (QR fictício) — não há integração financeira real ativa.
- Revisar dados de exemplo/usuários de teste antes de publicar.
