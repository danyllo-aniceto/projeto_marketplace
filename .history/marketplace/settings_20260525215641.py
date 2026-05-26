from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables using django-environ
import environ

# initialize environment
env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-key')

DEBUG = env.bool('DEBUG', default=True)

# ALLOWED_HOSTS can be provided as a comma separated list in .env
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])


# =========================
# APPS
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # REMOVIDO: 'users'
    'marketplace_app',
]


# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'marketplace.urls'


# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'marketplace.wsgi.application'


# =========================
# DATABASE
# =========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='marketplace_db'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='1234'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}


# =========================
# AUTH
# =========================
AUTH_USER_MODEL = 'marketplace_app.User'


# =========================
# PASSWORD
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =========================
# INTERNATIONAL
# =========================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True
USE_TZ = True


# =========================
# STATIC / MEDIA
# =========================
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =========================
# EMAIL CONFIGURATION
# =========================
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')  # Para desenvolvimento - mostra emails no console
# SMTP example (configure .env for production)
# EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env('EMAIL_PORT', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='')

# External service tokens are configured in the PAYMENTS section below


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =========================
# PAYMENTS
# =========================
MERCADO_PAGO_ACCESS_TOKEN = env('MERCADO_PAGO_ACCESS_TOKEN', default='')
MERCADO_PAGO_PUBLIC_KEY = env('MERCADO_PAGO_PUBLIC_KEY', default='')
SITE_URL = env('SITE_URL', default='http://127.0.0.1:8000')