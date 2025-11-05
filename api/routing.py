# api/routing.py 

from django.urls import re_path
from api.consumers import ChatConsumer # 챗봇 Consumer 임포트

# WebSocket 요청 URL 패턴 리스트
websocket_urlpatterns = [
    # 채팅 엔드포인트: ws/chat/
    # ws://YOUR_DOMAIN/ws/chat/ 경로로 접속이 들어오면 consumers.ChatConsumer가 처리하도록 연결합니다.
    re_path(r'ws/chat/$', ChatConsumer.as_asgi()), 
]
