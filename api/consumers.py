# app_server/api/consumers.py

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from asgiref.sync import async_to_sync
from openai import OpenAI, APIError
from django.conf import settings 
from django.contrib.auth import get_user_model

# 🚨 주의: 아래 service 함수들은 동기(Sync) 함수이므로, 
# 반드시 @database_sync_to_async로 감싸서 호출해야 합니다.
from services.chat_service import (
    _assemble_context_data, 
    _get_time_contexts, 
    _prepare_llm_messages, 
    _call_openai_api,
    extract_and_save_user_context_data,
    async_stream_openai_api
)
from .models import ChatMessage

from services import prompt_service 
from services import emotion_service
from services import emoticon_service
from services import proactive_service
from services import location_service


User = get_user_model()

# ----------------------------------------------------
# 헬퍼 함수: 동기 \ 비동기로 실행
# ----------------------------------------------------
@database_sync_to_async
def get_inactivity_message_sync(user):
    """proactive_service의 동기 함수를 비동기로 호출하여 메시지/감정을 가져옵니다."""
    # 🚨 새로 추가된 proactive_service 함수 호출
    return proactive_service.get_proactive_message_for_timer(user)

@database_sync_to_async
def get_user_chat_history(user, limit=10):
    """DB에서 동기적으로 채팅 기록을 가져옵니다."""
    # return list(ChatMessage.objects.filter(user=user).order_by('-timestamp')[:limit])
    return ChatMessage.objects.filter(user=user).order_by('-timestamp')[:limit]

@database_sync_to_async
def assemble_context_data_sync(user, user_message_for_llm, latitude, longitude):
    """동기 Service 함수 호출: 모든 컨텍스트 데이터를 모읍니다."""
    # chat_service.py의 함수 시그니처가 request 대신 user를 받도록 수정했다고 가정합니다.
    # _assemble_context_data는 request 객체를 필요로 하지 않으므로 user를 직접 전달합니다.
    return _assemble_context_data(user, user_message_for_llm, latitude, longitude, has_image=False)

@database_sync_to_async
def finalize_and_save_messages_sync(user, user_message_text, bot_message_text, history):
    """최종 메시지를 DB에 저장하고 메모리 추출 로직을 실행합니다."""
    
    # 1. 사용자 메시지 저장
    user_message_obj = ChatMessage.objects.create(
        user=user, message=user_message_text, is_user=True
    )
    
    # 2. 봇 메시지 저장
    bot_message_obj = ChatMessage.objects.create(
        user=user, message=bot_message_text, is_user=False
    )
    
    # 3. 메모리 추출 및 저장 (API 키 필요)
    api_key = settings.OPENAI_API_KEY # settings에서 직접 키를 사용합니다.
    recent_history_for_extraction = history[:10]
    extract_and_save_user_context_data(
        user, user_message_text, bot_message_text, recent_history_for_extraction, api_key
    )
    
    return user_message_obj, bot_message_obj

@database_sync_to_async
def get_location_recommendation_sync(user, message, latitude, longitude):
    """location_service의 동기 함수를 비동기로 호출합니다."""
    # 🚨 location_service.py에 정의된 동기 함수 호출
    return location_service.get_location_based_recommendation(user, message, latitude, longitude)



# ----------------------------------------------------
# 메인 Consumer
# ----------------------------------------------------

class ChatConsumer(AsyncWebsocketConsumer):


    INACTIVITY_TIMEOUT = 30 
    inactivity_task = None


    async def start_inactivity_timer(self):
        """지정된 시간 후 AI가 말을 걸도록 타이머를 시작합니다."""
        # 기존 타이머가 있다면 확실히 취소
        await self.cancel_inactivity_timer() 
        print(f"--- [DEBUG] 비활성 타이머 시작 ({self.INACTIVITY_TIMEOUT}초 후 능동형 메시지) ---")
        self.inactivity_task = asyncio.create_task(
            self._inactivity_countdown()
        )

    async def cancel_inactivity_timer(self):
        """현재 실행 중인 타이머를 취소합니다."""
        if self.inactivity_task:
            self.inactivity_task.cancel()
            try:
                # 취소 작업 완료를 기다림
                await self.inactivity_task
            except asyncio.CancelledError:
                pass
            self.inactivity_task = None
            print("--- [DEBUG] 비활성 타이머 취소됨 ---")

# ----------------------------------------------------
    async def _inactivity_countdown(self):
        """타이머가 만료되면 동적인 능동형 메시지를 생성하고 보냅니다."""
        try:
            await asyncio.sleep(self.INACTIVITY_TIMEOUT) 

            print(f"--- [DEBUG] 타이머 만료, 동적 능동형 메시지 생성 요청 ---")
            
            # 🚨 1. LLM을 호출하여 동적 메시지와 감정 획득 (get_inactivity_message_sync 사용)
            message_text, emotion_label = await get_inactivity_message_sync(self.user)
            
            if not message_text:
                message_text = "혹시 무슨 생각 하고 있었어?"
                emotion_label = "생각"
            
            print(f"--- [DEBUG] 동적 메시지 생성 완료: {message_text[:10]}... ({emotion_label}) ---")

            # 2. 감정 상태 전송 (동적 값 사용)
            await self.send(text_data=json.dumps({
                'type': 'emotion_analysis_result',
                'emotion': emotion_label, 
                'status': 'emotion_ready_passive' 
            }))

            # 3. 메시지 스트리밍 (동적 값 사용)
            await self.send(text_data=json.dumps({
                'type': 'chat_stream',
                'message_chunk': message_text, 
            }))
            
            # 4. 완료 신호 전송
            await self.send(text_data=json.dumps({
                'type': 'stream_end',
                'status': 'success_passive',
            }))
            
            # 5. DB에 메시지 저장 (ChatMessage에 기록)
            # 🚨 AI 메시지만 저장하는 별도의 헬퍼가 필요하지만, 
            # 현재 구조에서 `finalize_and_save_messages_sync`를 재활용하여 AI 메시지만 저장하도록 수정합니다.
            # user_message_text를 빈 문자열로 넘기면 (finalize... 내부에서 is_user=True로 저장되므로) 
            # 대신 ChatMessage.objects.create를 직접 호출하여 AI 메시지만 저장하도록 변경하는 것이 가장 깔끔합니다.
            await self._save_proactive_message_to_db(self.user, message_text, emotion_label)
                       
            print(f"--- [DEBUG] 능동형 메시지 전송 완료: {message_text[:10]}... ---")
            
            # 6. 타이머 재시작
            await self.start_inactivity_timer()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            # LLM 호출 실패 등의 오류 처리
            print(f"--- [오류] _inactivity_countdown 중 예외 발생: {e} ---")
            # 사용자에게 메시지는 보내지 못했지만, 타이머는 다시 시작
            await self.start_inactivity_timer()

    @database_sync_to_async
    def _save_proactive_message_to_db(self, user, message_text, emotion_label):
        """능동/환영 메시지처럼 AI 단독 메시지를 DB에 저장합니다."""
        ChatMessage.objects.create(
            user=user, 
            message=message_text, 
            is_user=False, # AI 메시지
            character_emotion=emotion_label
        )        



# ----------------------------------------------------
    async def connect(self):
        if "user" in self.scope:
            self.user = self.scope["user"]
        else:
            # Django의 AnonymousUser 객체를 임시로 사용하거나 (권장),
            # 혹은 인증되지 않은 사용자는 바로 닫아버리는 기존 로직을 유지할 수 있습니다.
            # 여기서는 디버깅을 위해 일단 인증되지 않은 사용자를 처리합니다.
            from django.contrib.auth.models import AnonymousUser
            self.user = AnonymousUser()
        
        if self.user.is_authenticated:
            self.room_name = f"user_{self.user.id}"
            self.room_group_name = f"chat_{self.room_name}"

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

        else:
            await self.close(code=4003)


    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.cancel_inactivity_timer()

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def _run_stream_chat(self, user_message_text, latitude, longitude):
        """AI 컨텍스트 수집부터 GPT 스트리밍 및 응답 전송까지 처리합니다."""
        
        # 0. 이모티콘 파싱 및 컨텍스트/히스토리 수집
        history = await get_user_chat_history(self.user)
        
        # ✅ 0-1. 이모티콘 파싱을 동기적으로 처리
        user_message_for_llm = await database_sync_to_async(
            emoticon_service.parse_emoticon
            )(user_message_text)
        
        # 0-2. 컨텍스트 수집
        time_contexts = await database_sync_to_async(_get_time_contexts)(history)

        assembled_contexts = await assemble_context_data_sync(
          self.user, user_message_for_llm, latitude, longitude
        )

        # 🎯 1. 위치 기반 추천 정보 검색 및 클라이언트 전송
        # LLM 호출 전에 선호 장소 추천 또는 주변 장소 정보를 검색합니다.
        if latitude is not None and longitude is not None:

            # LLM에게 컨텍스트가 주어졌는지와 별개로, 클라이언트에 추천 UI를 띄워야 하므로 여기서 전송
            recommendation_message = await get_location_recommendation_sync(
                self.user, user_message_text, latitude, longitude
            )
            if recommendation_message:
                assembled_contexts['location_recommendation'] = recommendation_message
                print(f"✅ 위치 기반 추천 텍스트를 컨텍스트에 추가: {recommendation_message}")
            else:
                print(f"❌ 위치 기반 추천 검색 실패: 관련 키워드 없음 또는 검색 결과 없음")
        # ---------------------------------------------------------
        
        # 2. LLM 호출 준비 및 스트리밍
        final_system_prompt = await database_sync_to_async(
            prompt_service.build_final_system_prompt)(
            self.user, time_contexts, assembled_contexts, image_analysis_context=None
        )
        messages = await database_sync_to_async(
            _prepare_llm_messages)(final_system_prompt, history, user_message_for_llm
        )

        model_to_use = settings.FINETUNED_MODEL_ID or "gpt-4o-mini"
        print(f"--- [디버그 4.5] GPT API 호출 시작 (모델: {model_to_use}) ---")
        
        full_ai_response = ""
        
        try:
            # GPT 스트리밍 호출 (Async)
            response_stream = await async_stream_openai_api(model_to_use, messages)
            print(f"--- [디버그 5] 응답 스트림 객체 타입: {type(response_stream)} ---")

            # 비동기 Generator를 순회하며 실시간 전송
            async for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_ai_response += content
                    
                    # 개행 없이 한 줄에 이어서 디버그 출력
                    sys.stdout.write(content.strip())
                    sys.stdout.flush()

                    await self.send(text_data=json.dumps({
                        'type': 'chat_stream',
                        'message_chunk': content,
                    }))
            
            # 3. 감정 분석 및 완료 신호 전송
            emotion_label = await database_sync_to_async(emotion_service.analyze_emotion)(full_ai_response)
            print(f"--- 감정 분석 결과: {emotion_label} ---")
            
            await self.send(text_data=json.dumps({
                'type': 'stream_end',
                'status': 'success',
                'emotion': emotion_label,
            }))

        except APIError as e:
            full_ai_response = f"AI 연결 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            print(f"--- [오류] GPT API 오류: {e} ---")
            await self.send(text_data=json.dumps({"type": "error", "message": full_ai_response}))
        
        
        # 4. 메시지 저장 및 메모리 추출 (DB 접근)
        if full_ai_response and full_ai_response != "AI 연결 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.":
            await finalize_and_save_messages_sync(
                self.user, user_message_text, full_ai_response, history
            )
            print("--- [디버그] 메시지 저장 및 메모리 추출 완료 ---")        


    async def receive(self, text_data=None, bytes_data=None):
        """클라이언트로부터 메시지를 수신했을 때 호출됩니다."""
        print("--- [디버그 1] receive 함수 시작 ---") 
        try:
            await self.cancel_inactivity_timer()

            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()
            latitude = text_data_json.get('latitude')
            longitude = text_data_json.get('longitude')
            
            print(f"--- [디버그 2] 메시지 파싱 완료: {message} ---") 

            if not message:
                return
            
            await self._run_stream_chat(message, latitude, longitude)
            print("--- [디버그] _run_stream_chat 호출 완료 ---") 
            
            await self.start_inactivity_timer()

        except json.JSONDecodeError:
            print("--- [오류] 잘못된 JSON 형식 ---")
            await self.send(text_data=json.dumps({"type": "error", "message": "잘못된 JSON 형식입니다."}))
        except Exception as e:
            print(f"--- [오류] 채팅 처리 중 일반 예외 발생: {e} ---") 
            await self.send(text_data=json.dumps({"type": "error", "message": "서버 내부 오류 발생."}))
    # ----------------------------------------------------
    # 핵심 비즈니스 로직 (스트리밍 처리)
    # ----------------------------------------------------
    

    async def proactive_message_notification(self, event):
        """
        proactive_service.py에서 전송한 능동 메시지 알림을 수신하고 처리합니다.
        """
        message_type = event['message'] # 'new_proactive_message_available'
        
        # 클라이언트에게 메시지를 읽어오도록 지시하는 알림을 보냅니다.
        # 클라이언트(프론트엔드)는 이 신호를 받고 별도의 API를 호출하여 메시지를 가져가게 됩니다.
        await self.send(text_data=json.dumps({
            'type': 'proactive.message.notification',
            'status': message_type, 
            'detail': '서버에 새로운 능동 메시지가 대기 중입니다.'
        }))
        
        print(f"--- [정보] 웹소켓으로 능동 메시지 알림 전송: {message_type} ---")



