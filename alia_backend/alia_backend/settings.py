import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',   # requis par les modèles
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'api',
]

# SessionMiddleware RETIRÉ — incompatible ASGI sans configuration Redis
# On stocke l'état de simulation dans alia_bridge (dict en mémoire)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'alia_backend.urls'
WSGI_APPLICATION = 'alia_backend.wsgi.application'
ASGI_APPLICATION  = 'alia_backend.asgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
}]

# ── Base de données ─────────────────────────────────────────────────────────────
# Défaut : SQLite (fichier alia_backend/db.sqlite3) — compatible Django 4.2 sans dépendre de la version MariaDB.
#
# MySQL/MariaDB UNIQUEMENT si vous définissez explicitement DB_ENGINE=mysql.
# Django 4.2 exige MariaDB >= 10.5 (XAMPP ancien = 10.4 → NotSupportedError).
# Mettre à jour MariaDB/MySQL, ou laisser SQLite pour le dev local.
_db_engine = (os.getenv('DB_ENGINE') or 'sqlite').strip().lower()

if _db_engine == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.mysql',
            'NAME':     os.getenv('DB_NAME',     'alia_db'),
            'USER':     os.getenv('DB_USER',     'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST':     os.getenv('DB_HOST',     '127.0.0.1'),
            'PORT':     os.getenv('DB_PORT',     '3306'),
            'OPTIONS':  {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME':   BASE_DIR / 'db.sqlite3',
        }
    }

# ── CORS (autorise le frontend React sur 5173) ─────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ── WebSocket (Channels) — InMemory pour dev local ────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# ── REST Framework — auth JWT custom ──────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES':     [],
}

# ── Alia core path ─────────────────────────────────────────────────────────────
ALIA_PROJECT_PATH = os.getenv('ALIA_PROJECT_PATH', r'C:\Users\eyaen\Desktop\PI')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Europe/Paris'
USE_TZ        = True
STATIC_URL    = '/static/'