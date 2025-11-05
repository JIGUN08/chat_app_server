#celery.py

import os
from celery import Celery

# Django 설정 파일을 Celery가 사용하도록 합니다.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app_server.settings')

app = Celery('app_server')

# Django 설정 파일(settings.py)에서 'CELERY_'로 시작하는 모든 설정을 가져옵니다.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 앱의 tasks.py 모듈을 자동으로 찾습니다.
app.autodiscover_tasks()
