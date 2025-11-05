#proactive_service.py
from api.models import ChatMessage, PendingProactiveMessage
from django.utils import timezone
from datetime import timedelta, datetime, date, time
import os
import requests
import json
import re
from .chat_service import _assemble_context_data # 필요한 함수 임포트
from .prompt_service import build_persona_system_prompt, build_rag_instructions_prompt
from .emotion_service import analyze_emotion
from . import schedule_service 
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def _check_upcoming_schedule(user):
    today = date.today()
    schedules = schedule_service.get_schedules_for_day(user, today)
    now_korea = timezone.now().astimezone(timezone.get_default_timezone())

    for schedule in schedules:
        if schedule.schedule_time and schedule.content:
            # 오늘 날짜와 스케줄 시간을 결합하여 datetime 객체 생성
            schedule_datetime = datetime.combine(today, schedule.schedule_time)
            schedule_datetime = timezone.make_aware(schedule_datetime, timezone.get_default_timezone())

            time_until_schedule = schedule_datetime - now_korea

            # 스케줄이 10분 이내로 다가왔고 과거가 아닌지 확인
            if timedelta(minutes=0) < time_until_schedule <= timedelta(minutes=10):
                return schedule.content # 가장 빨리 다가오는 스케줄 내용 반환
    return None

def _call_llm_for_proactive_message(user, system_prompt):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("오류: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return None, None

    model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': f"{user.username}님에게 능동적인 대화를 시작할 메시지를 생성해줘."}
    ]

    data = {
        "model": model_to_use,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        
        content_from_llm = json.loads(response_json['choices'][0]['message']['content'])
        message_text = content_from_llm.get('answer', '').strip()
        explanation = content_from_llm.get('explanation', '설명 없음.') # Extract explanation
        emotion = analyze_emotion(message_text) # emotion_service를 사용하여 감정 분석 

        print("\n" + "-"*20 + " [Debug] Proactive Message Explanation " + "-"*20)
        print(explanation)
        print("-"*66 + "\n")

        return message_text, emotion, explanation # Return explanation
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"LLM 능동적 메시지 생성 오류: {e}")
        return None, None, None # Return None for explanation on error


def generate_proactive_message(user):
    last_chat = ChatMessage.objects.filter(user=user).order_by('-timestamp').first()
    korea_tz = timezone.get_default_timezone()
    now_korea = timezone.now().astimezone(korea_tz)
    
    trigger_type = None
    proactive_instruction_base = ""
    message_text = None
    emotion = "default"

    # 1. 비활동 기반 트리거
    if last_chat and (now_korea - last_chat.timestamp.astimezone(korea_tz)) > timedelta(hours=1):
        trigger_type = "inactivity"
        proactive_instruction_base = f"너는 {user.username}님에게 오랜만에 말을 거는 상황이야. 1시간 이상 대화가 없었으니, {user.username}님의 안부를 묻거나, "
    
    # 2. 시간대 기반 트리거
    elif not last_chat or (now_korea - last_chat.timestamp.astimezone(korea_tz)) > timedelta(minutes=30):
        current_hour = now_korea.hour
        if 6 <= current_hour < 10:
            trigger_type = "morning_greeting"
            proactive_instruction_base = f"좋은 아침이야, {user.username}! 오늘 하루를 활기차게 시작할 수 있도록 응원하는 메시지를 생성해줘. "
        elif 12 <= current_hour < 14:
            trigger_type = "lunch_time"
            proactive_instruction_base = f"{user.username}님, 점심시간이야! 맛있는 점심을 추천하거나, 점심 관련 가벼운 대화를 시작하는 메시지를 생성해줘. "
        elif 18 <= current_hour < 22:
            trigger_type = "evening_greeting"
            proactive_instruction_base = f"{user.username}님, 저녁 시간이야! 오늘 하루는 어땠는지 묻거나, 편안한 저녁을 보낼 수 있도록 격려하는 메시지를 생성해줘. "

    # 3. 일정 알림 트리거
    upcoming_schedule_content = _check_upcoming_schedule(user)
    if upcoming_schedule_content:
        trigger_type = "upcoming_schedule"
        proactive_instruction_base = f"{user.username}님, 곧 일정이 있어! '{upcoming_schedule_content}' 일정이 10분 이내로 다가왔으니, 일정을 상기시켜주거나, 준비를 돕는 메시지를 생성해줘. "

    if trigger_type:
        persona_system_prompt = build_persona_system_prompt(user)
        rag_instructions_prompt = build_rag_instructions_prompt(user)
        assembled_contexts_dict = _assemble_context_data(user, "")
        assembled_contexts_str = "\n".join([f"[{key.replace('_', ' ').capitalize()}]: {value}" for key, value in assembled_contexts_dict.items() if value])
        if assembled_contexts_str:
            assembled_contexts_str = "\n## 사용자 기억 컨텍스트 ##\n" + assembled_contexts_str
        
        proactive_instruction = f"{proactive_instruction_base}제공된 사용자 정보와 기억 컨텍스트를 적극적으로 활용하여 메시지를 생성해줘. 너의 페르소나에 맞게 재치있고 흥미롭게 말을 걸어줘. 응답은 반드시 JSON 형식으로 'answer' 키와 'explanation' 키를 포함해야 해."
        system_prompt = f"{persona_system_prompt}{rag_instructions_prompt}{assembled_contexts_str}\n\n## 능동적 대화 지시 ##\n{proactive_instruction}"
        
        message_text, emotion, explanation = _call_llm_for_proactive_message(user, system_prompt)

        # LLM 호출 실패 시 기본 메시지 설정
        if not message_text:
            emotion = "default"
            if trigger_type == "inactivity":
                message_text = "오랜만이야! 뭐 하고 지냈어?"
            elif trigger_type == "morning_greeting":
                message_text = "좋은 아침이야!"
                emotion = "happy"
            elif trigger_type == "lunch_time":
                message_text = "점심시간이야! 뭐 먹을지 고민돼?"
                emotion = "thinking"
            elif trigger_type == "evening_greeting":
                message_text = "오늘 하루도 수고했어!"
            elif trigger_type == "upcoming_schedule":
                message_text = f"곧 '{upcoming_schedule_content}' 일정이 있어! 준비는 잘 되고 있어?"

    if message_text:
        # ChatMessage 객체 생성 및 저장
        proactive_chat_message = ChatMessage.objects.create(
            user=user,
            message=message_text,
            is_user=False,
            character_emotion=emotion
        )
        
        # 벡터 DB에 저장
        try:
            from . import vector_service
            collection = vector_service.get_or_create_collection()
            vector_service.upsert_message(collection, proactive_chat_message)
            print("--- [디버그] 능동 메시지 벡터 DB 저장 완료 ---")
        except Exception as e:
            print(f"--- [오류] 능동 메시지 벡터 DB 저장 실패: {e} ---")

        # 읽지 않은 메시지로 등록
        PendingProactiveMessage.objects.update_or_create(
            user=user,
            defaults={'message': proactive_chat_message}
        )
        print(f"--- [디버그] {user.username}님에게 읽지 않은 능동 메시지 등록 완료 ---")

        _notify_user_of_proactive_message(user.id)
            
        return proactive_chat_message

    return None # 능동적인 메시지가 생성되지 않음

def _notify_user_of_proactive_message(user_id):
    """
    유저에게 읽지 않은 능동 메시지가 있음을 웹소켓 채널로 알립니다.
    """
    channel_layer = get_channel_layer()
    group_name = f'chat_user_{user_id}' # 사용자별 채널 그룹 이름 (consumers.py에서 연결 가정)

    # 비동기 함수를 동기 환경에서 호출하기 위해 async_to_sync 사용
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'proactive.message.notification', # Consumer가 처리할 타입
            'message': 'new_proactive_message_available'
        }
    )
    print(f"--- [정보] User {user_id}에게 능동 메시지 알림 전송 완료 ---")



def get_proactive_message_for_timer(user):
    """
    ChatConsumer의 30초 비활동 타이머 만료 시 호출되어,
    LLM이 동적인 메시지와 감정을 생성하도록 요청합니다.
    (DB 저장, 알림 전송 로직은 제외하고 메시지와 감정만 반환)
    """
    trigger_type = "inactivity_timer"
    
    # 1. 인스트럭션 생성 (10초 비활동에 맞는 내용)
    proactive_instruction_base = f"현재 {user.username}님과 대화 연결 상태이지만 30초 이상 침묵하고 있어. 너무 무겁지 않은 가벼운 대화 주제로 말을 걸어줘. 컨텍스트를 활용해서 최근 대화와 관련 있는 내용을 물어봐도 좋아. "

    # 2. 페르소나, 컨텍스트, RAG 인스트럭션 등 최종 프롬프트 조합 (기존 로직 재활용)
    # **주의**: _assemble_context_data 함수는 proactive_service.py 상단에 임포트되어 있습니다.
    persona_system_prompt = build_persona_system_prompt(user)
    rag_instructions_prompt = build_rag_instructions_prompt(user)
    # user_message_for_llm은 빈 문자열로 전달 (사용자가 보낸 메시지가 없으므로)
    assembled_contexts_dict = _assemble_context_data(user, "") 
    assembled_contexts_str = "\n".join([f"[{key.replace('_', ' ').capitalize()}]: {value}" for key, value in assembled_contexts_dict.items() if value])
    if assembled_contexts_str:
        assembled_contexts_str = "\n## 사용자 기억 컨텍스트 ##\n" + assembled_contexts_str
        
    proactive_instruction = f"{proactive_instruction_base}제공된 사용자 정보와 기억 컨텍스트를 적극적으로 활용하여 메시지를 생성해줘. 너의 페르소나에 맞게 재치있고 흥미롭게 말을 걸어줘. 응답은 반드시 JSON 형식으로 'answer' 키와 'explanation' 키를 포함해야 해."
    system_prompt = f"{persona_system_prompt}{rag_instructions_prompt}{assembled_contexts_str}\n\n## 능동적 대화 지시 ##\n{proactive_instruction}"
    
    # 3. LLM 호출 (_call_llm_for_proactive_message 재활용)
    message_text, emotion, explanation = _call_llm_for_proactive_message(user, system_prompt)

    # 4. LLM 호출 실패 시 기본 메시지
    if not message_text:
        return "혹시 무슨 생각 하고 있었어?", "생각"

    # 5. 메시지와 감정만 반환 (DB 저장 및 알림은 ChatConsumer에서 별도로 처리)
    return message_text, emotion
