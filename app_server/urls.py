# backend/app_server/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # api 앱의 모든 URL을 'api/' 경로 아래에 포함
    path('api/', include('api.urls')), 
]
