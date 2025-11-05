#settings.py
"""
Django settings for app_server project.
"""
from datetime import timedelta 
import os
from celery.schedules import crontab
from pathlib import Path
from dotenv import load_dotenv
load_dotenv() 

import dj_database_url

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0") 

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", None)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

FINETUNED_MODEL_ID = None
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-o51sdqp4+z@uj02rjcn-&8&8mguv*aah@cgu&0ep9i2-jk$j%3')
# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY 재정의하는 중복 코드를 제거합니다.

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG 모드는 환경 변수에 따라 설정됩니다. (Production 환경에서는 False)
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# ALLOWED_HOSTS는 Render 서비스 URL을 포함하도록 환경 변수를 사용하거나 와일드카드를 사용합니다.
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api.apps.ApiConfig',
    'django_celery_beat',
    'channels',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.example.com',
    'http://localhost:8000',
    'http://localhost:8000', 
    'http://127.0.0.1:8000',
    'http://127.0.0.1',
    'https://*.onrender.com'
]

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://10.0.2.2:8000", # Android 에뮬레이터 IP
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    )
}

ASGI_APPLICATION = 'app_server.asgi.application'

ROOT_URLCONF = 'app_server.urls'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)], 
        },
    },
}


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'app_server.wsgi.application'

# Database - Render PostgreSQL 또는 SQLite3 설정
# Render는 DATABASE_URL 환경 변수를 제공합니다.

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'),
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SIMPLE_JWT = {

    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1), 
   
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),

    "AUTH_HEADER_TYPES": ("Bearer",),
}

CELERY_IMPORTS = (
    'api.tasks', # 'api' 앱의 tasks.py 파일을 명시적으로 가져옵니다.
)

CELERY_TIMEZONE = 'Asia/Seoul' 
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BROKER_URL = 'redis://localhost:6379/0'  # Redis 브로커 URL
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0' # 결과 백엔드

CELERY_BEAT_SCHEDULE = {
    'proactive-message-check-every-1-minutes': {
        'task': 'api.tasks.check_and_send_proactive_messages', 
        'schedule': crontab(minute='*/1'), # 테스트를 위해 1분 설정 (배포 시 10분 권장)
        'args': (), 
    },
}

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Production 환경을 위한 WhiteNoise 설정
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 🚨 참고: User 모델을 커스터마이징 했다면 여기에 추가해야 합니다.
# AUTH_USER_MODEL = 'your_app_name.CustomUser'
