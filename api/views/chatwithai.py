#api/views/chatwithai.py

from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async 
import json
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    """실시간 AI 채팅 통신을 처리하는 WebSocket Consumer 뼈대"""
    
    async def connect(self):
        # 🔑 JWT 인증 검증 로직이 필요 (scope['user']에 사용자 정보가 있어야 함)
        if self.scope["user"].is_authenticated:
            self.chat_group_name = f"chat_{self.scope['user'].id}"
            await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
            await self.accept()
        else:
            await self.close() 

    async def disconnect(self, close_code):
        if self.scope["user"].is_authenticated:
            await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')
        
        # ⚠️ (여기에 비동기적으로 AI 응답을 생성하는 로직이 들어갑니다.)
        
        # 임시 응답 (실제 로직 구현 전까지)
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'sender': 'assistant',
            'message': f"AI: '{message}'에 대해 생각하고 있습니다.",
            'timestamp': str(timezone.now()) 
        }))
