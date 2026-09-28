"""
Django asosiy sozlamalari.
Bu loyihaning "boshqaruv markazi" — qaysi app'lar ishlatilishi,
qaysi bazaga ulanishi, qayerdan shablon (HTML) o'qilishi shu yerda belgilanadi.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Maxfiy kalit faqat .env dan olinadi. .env bo'lmasa (masalan toza klon) —
# vaqtinchalik tasodifiy kalit ishlatiladi. Productionда albatta .env da bo'lishi shart.
SECRET_KEY = os.getenv('SECRET_KEY') or get_random_secret_key()
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Loyiha app'lari (apps/ papkasi ichida)
    'apps.users',
    'apps.events',
    'apps.groups',
    'apps.messages_app',
    'apps.workers',
    'apps.trips',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Hamma HTML fayllar loyiha tubidagi yagona "templates/" papkasida,
        # app nomi bo'yicha kichik papkalarga bo'linadi (templates/users/, templates/events/ ...)
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'mbc_db'),
        'USER': os.getenv('DB_USER', 'mbc_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Admin sayt kirish/chiqish qaysi manzilga yo'naltirilishi
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Telegram bot tokeni (.env faylidan o'qiladi)
CLIENT_BOT_TOKEN = os.getenv('CLIENT_BOT_TOKEN', '')
PRIVATE_CHANNEL_ID = os.getenv('PRIVATE_CHANNEL_ID', '')
PRIVATE_GROUP_ID = os.getenv('PRIVATE_GROUP_ID', '')
WORKER_BOT_TOKEN = os.getenv('WORKER_BOT_TOKEN', '')
TRIPS_GROUP_ID= os.getenv('TRIPS_GROUP_ID', '')
WORK_GROUP_ID = os.getenv('WORK_GROUP_ID', '')

# Ovozli xabarni matnga aylantirish (Groq Whisper) — tekin: https://console.groq.com
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

# Guruhga begona a'zo qo'shilganda xabar oladigan adminlarning Telegram ID lari.
# .env da vergul bilan ajratib yoziladi, masalan: ADMIN_IDS=123456789,987654321
# Bu ID lar bazadagi role='admin' foydalanuvchilar bilan birga ishlatiladi.
ADMIN_IDS = [x.strip() for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
