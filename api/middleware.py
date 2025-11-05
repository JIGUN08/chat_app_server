# api/middleware.py

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

@database_sync_to_async
def get_user(scope):
    """scope에서 JWT 토큰을 파싱하여 사용자 객체를 비동기적으로 가져옵니다."""
    try:
        # 1. scope['headers']에서 'authorization' 헤더의 값을 직접 찾습니다.
        auth_header = None
        
        # Channels 헤더는 튜플 리스트 [(b'key', b'value')] 이며 키는 소문자 바이트입니다.
        for header_name, header_value in scope['headers']:
            if header_name == b'authorization': # 🚨 소문자 바이트 키 사용
                auth_header = header_value.decode()
                break

        if not auth_header:
            # 🚨 추가: 웹 환경에서는 토큰이 쿼리 파라미터로 올 수 있음
            query_string = scope.get("query_string", b"").decode()
            if "token=" in query_string:
                token_str = query_string.split("token=")[1]
                if "&" in token_str:
                    token_str = token_str.split("&")[0]
                token = AccessToken(token_str)
                user_id = token['user_id']
                return User.objects.get(id=user_id)
            return None
            
        # 2. 'Bearer ' 부분을 제거하고 토큰만 추출합니다.
        if auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1]
            
            # 3. 토큰을 검증하고 사용자 ID를 가져옵니다.
            token = AccessToken(token_str)
            user_id = token['user_id']
            
            # 4. 사용자 객체를 DB에서 가져옵니다.
            return User.objects.get(id=user_id)
            
        return None
        
    except (InvalidToken, TokenError, User.DoesNotExist, IndexError) as e:
        # 토큰이 유효하지 않거나, 사용자 없음, split 오류 등을 여기서 잡습니다.
        print(f"JWT/DB 인증 오류: {e}")
        return None
    except Exception as e:
        print(f"JWT 인증 중 일반 오류 발생: {e}")
        return None

class TokenAuthMiddleware:
    """JWT 토큰을 사용하여 scope['user']에 사용자 객체를 설정하는 미들웨어"""
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 1. 웹소켓 핸드셰이크가 완료된 후, 사용자 객체를 비동기적으로 가져옵니다.
        user = await get_user(scope)
        
        # 2. 사용자 객체를 scope에 할당합니다.
        if user is not None:
            scope['user'] = user
        
        # 3. 다음 미들웨어 또는 Consumer(ChatConsumer)로 요청을 전달합니다.
        return await self.inner(scope, receive, send)
