import os
from pathlib import Path
from dotenv import load_dotenv


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
    'permissions',             # Permission + RolePermission tables
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
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': { 'min_length': 6 } },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
    { 'NAME': 'core.validators.StrongPasswordValidator' },
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
SMS_COUNTRY_CODE = os.getenv("SMS_COUNTRY_CODE")

REDIS_URL = os.getenv("REDIS_URL")

# Redis configuration for Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# CORS: the browser only lets a website call this API if the website's address is listed here.
# The React admin panel runs on its own address (for example http://localhost:3000 or http://localhost:5173)
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]


# REST FRAMEWORK for uploading images
REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    # We do the login check ourselves with our own decorators (@jwt_required, @role_required, @permission_required),
    # so DRF's own session login and permission check are switched off.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# JWT (PyJWT). Access token = short life, used on every request. Refresh token = long life, used only to get a new access token.
# The two tokens are signed with two different secret keys (both are in .env).
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_REFRESH_SECRET_KEY = os.environ["JWT_REFRESH_SECRET_KEY"]
ACCESS_TOKEN_LIFETIME_MINUTES = int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", 15))
REFRESH_TOKEN_LIFETIME_DAYS = int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", 7))

# Custom authentication backend
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrPhoneBackend",
]

# LOGGING
# Instead of print(), the code writes messages like logger.warning("Failed login ...").
# "handlers" decide where a message goes: the terminal (console) and the file logs/edu_predict.log.
# The file is cut at 5 MB and only 3 old files are kept, so it can never fill the disk.
# Level INFO = show INFO, WARNING and ERROR messages (hide DEBUG).
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)        # create the logs folder, the file handler needs it

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",     # 2026-10-07 10:15:01 WARNING accounts.views Failed login ...
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": LOG_DIR / "edu_predict.log",
            "maxBytes": 5_000_000,
            "backupCount": 3,
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}





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
# python manage.py seed_permissions
# python manage.py test

# seed_permissions command loads the role matrix from the report
# running it again re-adds any default permission the Super Admin removed, so use --reset only to go back to the defaults

# source ../../learning_django/env_machine_learning/bin/activate