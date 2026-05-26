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
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Para desenvolvimento - mostra emails no console
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Para produção
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'
# DEFAULT_FROM_EMAIL = 'your-email@gmail.com'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =========================
# PAYMENTS
# =========================
MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MERCADO_PAGO_ACCESS_TOKEN', '')
MERCADO_PAGO_PUBLIC_KEY = os.getenv('MERCADO_PAGO_PUBLIC_KEY', '')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')