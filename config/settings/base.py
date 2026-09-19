"""
TurniQ — Base Settings (Fixed version)
No external dependencies for reading .env
"""
from pathlib import Path
from datetime import timedelta
import os, re

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env without requiring python-decouple
def _read_env():
    env_vars = {}
    for env_file in [BASE_DIR / '.env', BASE_DIR / '.env.local']:
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars

_env = _read_env()

def env_get(key, default=None, cast=None):
    val = _env.get(key, os.environ.get(key, default))
    if val is None:
        return default
    if cast is bool:
        return str(val).lower() in ('true', '1', 'yes')
    if cast is int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    if cast is list:
        return [v.strip() for v in str(val).split(',') if v.strip()]
    return val

SECRET_KEY = env_get('SECRET_KEY', 'django-insecure-turniq-dev-key-change-in-production-2025!')
DEBUG = env_get('DEBUG', True, cast=bool)
ALLOWED_HOSTS = env_get('ALLOWED_HOSTS', 'localhost,127.0.0.1', cast=list)

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',
]
LOCAL_APPS = [
    'apps.accounts',
    'apps.core',
    'apps.teams',
    'apps.tournaments',
    'apps.matches',
    'apps.notifications',
    'apps.clubs',
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.AppearanceMiddleware',
    'apps.core.middleware.ForceTeamCreationMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'apps.core.context_processors.app_settings',
                'apps.core.context_processors.active_tournament',
                'apps.core.context_processors.registration_tournament',
                'apps.core.context_processors.pending_requests',
                'apps.core.context_processors.unread_notifications',
            ],
        },
    },
]

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = []

# Database - parse URL manually, no dj-database-url needed
_db_url = env_get('DATABASE_URL', f'sqlite:///{BASE_DIR}/db.sqlite3')
if _db_url.startswith('sqlite:///'):
    _db_path = _db_url[len('sqlite:///'):]
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': _db_path}}
else:
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+):?(\d*)/(.+)', _db_url)
    if m:
        DATABASES = {'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'USER': m.group(1), 'PASSWORD': m.group(2),
            'HOST': m.group(3), 'PORT': m.group(4) or '5432', 'NAME': m.group(5),
        }}
    else:
        DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Africa/Algiers'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']
from django.utils.translation import gettext_lazy as _
LANGUAGES = [('fr', _('Français')), ('ar', _('العربية'))]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=4),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'TurniQ <noreply@turniq.dz>'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# Increase upload limits for large promo JSON data (Base64 images)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

