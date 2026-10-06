import os
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.0.105']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',

    # django apps
    'accounts',
    # 'courses',
    # 'students',
    # 'enrolments',
    # 'attendance',
    # 'assignments',
    # 'assessments',
    # 'performance',
    # 'notifications',
    # 'ml_prediction',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_edu_predict.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                "django.template.context_processors.debug",
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "core.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = 'django_edu_predict.wsgi.application'

DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     os.getenv("DB_NAME"),
        "USER":     os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST":     os.getenv("DB_HOST"),
        "PORT":     os.getenv("DB_PORT"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

REDIS_URL = os.getenv("REDIS_URL")

# Redis configuration for Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


# REST FRAMEWORK for uploading images
REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Custom authentication backend
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrPhoneBackend",
]

# NOTE
# https://docs.google.com/document/d/1ZvnOAUYxl5hM5fd77eLkIgyN_uyiKcGoiz_z0LS3xfg/edit?tab=t.0


# NOTE:
# psql -U django_user -d edu_predict_db
# DROP DATABASE edu_predict_db
# CREATE DATABASE edu_predict_db OWNER django_user;

# Run this command for running on localhost in flutter app (Means: Django, listen for connections coming through any network interface on port 8000):
# python manage.py runserver 0.0.0.0:8000

# how to find my Mac's IP ?
# ipconfig getifaddr en0
# 192.168.0.105
# This change is to be made in flutter app's baseurl, django's settings.py

# redis-server
# celery -A nutrivision_food_recognition worker -l info

# source ../../learning_django/env_machine_learning/bin/activate