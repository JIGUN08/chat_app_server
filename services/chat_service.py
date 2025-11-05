#chat_service.py
import json
import os
import base64
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI, APIError, AsyncOpenAI
from django.core.files.uploadedfile import UploadedFile

from api.models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from .context_service import get_activity_recommendation, search_activities_for_context
from .memory_service import extract_and_save_user_context_data
from .image_captioning_service import ImageCaptioningService
from . import vector_service, location_service, schedule_service, emotion_service, prompt_service, emoticon_service
from datetime import date # date 추가


def process_chat_interaction(request, user_message_text: str, latitude: Optional[float] = None, longitude: Optional[float] = None, image_file: Optional[UploadedFile] = None):
    """사용자 메시지를 처리하고 AI 응답을 생성하는 전체 프로세스를 조율합니다."""
    user = request.user
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None
    user_message_obj = None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        client = OpenAI()

        # 0단계: 이모티콘 파싱
        user_message_for_llm = emoticon_service.parse_emoticon(user_message_text)

        # 1단계: 이미지 분석 (이미지가 있는 경우)
        image_analysis_context = None
        image_b64_data = None
        if image_file:
            print("--- [디버그] 이미지 파일 감지됨. 1차 분석 시작 ---")
            
            # 추가된 디버깅 로그
            print(f"--- [디버그] 파일명: {image_file.name}, Content-Type: {image_file.content_type} ---")

            # ImageCaptioningService가 Base64를 사용하므로, 파일 내용을 인코딩하여 전달
            image_b64_data = base64.b64encode(image_file.read()).decode('utf-8')
            image_file.seek(0) # 파일을 다시 읽을 수 있도록 포인터를 처음으로 되돌림

            analyzer = ImageCaptioningService()
            # 업로드된 파일의 content_type을 함께 전달
            analysis_result = analyzer.analyze_image(image_b64_data, user_message_text, image_file.content_type)
            if analysis_result:
                image_analysis_context = analysis_result
                print("--- [디버그] 1차 분석 완료 --- ")
            else:
                print("--- [경고] 1차 분석 실패 --- ")

        # 2단계: 컨텍스트 생성
        history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        time_contexts = _get_time_contexts(history)
        # 벡터 검색은 이미지가 없을 때만 수행하여 효율성 증대
        assembled_contexts = _assemble_context_data(user, user_message_for_llm, latitude, longitude, bool(image_file))
        
        # 3단계: 최종 프롬프트 생성 (이미지 분석 결과 포함)
        final_system_prompt = prompt_service.build_final_system_prompt(user, time_contexts, assembled_contexts, image_analysis_context)
        messages = _prepare_llm_messages(final_system_prompt, history, user_message_for_llm)
        

        # 4단계: 최종 LLM 호출 (파인튜닝된 모델)
        model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
        response_json = _call_openai_api(client, model_to_use, messages)
        
        # 5단계: 응답 처리 및 저장
        bot_message_text, explanation, bot_message_obj, user_message_obj = _finalize_chat_interaction(
            request, user_message_text, response_json, history, api_key, image_file
        )

    except APIError as e:
        print(f"OpenAI API 요청 실패: {e}")
        bot_message_text = f"API 요청 중 오류가 발생했습니다: {e}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API 응답 형식 오류: {e}")
        bot_message_text = "API 응답 형식이 예상과 다릅니다."
    except Exception as e:
        import traceback
        print(f"예상치 못한 오류: {e}")
        traceback.print_exc()
        bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"

    # user_message_obj를 반환하도록 수정
    return bot_message_text, explanation, bot_message_obj, user_message_obj

def _get_time_contexts(history):
    """현재 시간 및 마지막 대화와의 시간 간격에 대한 컨텍스트를 생성합니다."""
    now_utc = timezone.now()
    korea_tz = timezone.get_default_timezone()
    now_korea = now_utc.astimezone(korea_tz)
    
    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_of_week = weekdays[now_korea.weekday()]
    time_str = now_korea.strftime(f'%Y년 %m월 %d일 {day_of_week} %H시 %M분')
    current_time_context = f"[시간 정보]: 현재 대한민국 시간은 정확히 '{time_str}'이야. 시간과 관련된 모든 질문에 이 정보를 최우선으로 사용해서 답해야 해. 절대 다른 시간을 말해서는 안 돼"
    
    time_awareness_context = ""
    if history.exists():
        last_interaction = history.first()
        time_difference = now_utc - last_interaction.timestamp
        if time_difference.total_seconds() > 3600:
            hours = int(time_difference.total_seconds() // 3600)
            minutes = int((time_difference.total_seconds() % 3600) // 60)
            time_gap_str = f"{hours}시간 {minutes}분"
            last_message_text = last_interaction.message
            sender = "네가" if last_interaction.is_user else "내가"
            time_awareness_context = f"[최근 마지막 대화정보]: 마지막 대화로부터 약 {time_gap_str}이 지났어. 마지막에 {sender} 한 말은 '{last_message_text}'이었어. 이 시간의 공백을 네 캐릭터에 맞게 재치있게 언급하며 대화를 시작해줘."

    return current_time_context, time_awareness_context

def _assemble_context_data(user, user_message_text, latitude=None, longitude=None, has_image=False):
    """사용자의 기억과 관련된 모든 컨텍스트를 종합하여 반환합니다."""
    contexts = {}
    # 0. 오늘의 일정 컨텍스트
    schedule_context = ""
    try:
        today_schedules = schedule_service.get_schedules_for_day(user, date.today())
        if today_schedules:
            schedule_contents = [s.content.strip() for s in today_schedules if s.content and s.content.strip()]
            if schedule_contents:
                schedule_context = f"[사용자의 오늘 일정 (참고용)]: {', '.join(schedule_contents)}"
                contexts['schedule'] = schedule_context
    except Exception as e:
        print(f"--- Could not build schedule context due to an error: {e} ---")


    # 1. 위치 컨텍스트 및 위치 기반 추천 컨텍스트
    if latitude is not None and longitude is not None:
        location_context = location_service.get_location_context(latitude, longitude)
        if location_context:
            contexts['location'] = location_context
       
            
        location_recommendation_result = location_service.get_location_based_recommendation(user, user_message_text, latitude, longitude)
        if location_recommendation_result:
            contexts['location_recommendation'] = location_recommendation_result

    # 2. 벡터 검색 컨텍스트 (이미지가 없을 때만 수행)
    if not has_image:
        try:
            collection = vector_service.get_or_create_collection()
            similar_results = vector_service.query_similar_messages(collection, user_message_text, user.id, n_results=5)
            if similar_results and isinstance(similar_results, dict) and similar_results.get('documents'):
                past_conversations = [f"{meta.get('speaker', '알수없음')}: {doc}" for doc, meta in zip(similar_results['documents'], similar_results['metadatas'])]
                contexts['vector_search'] = "[과거 유사한 대화 내용(벡터DB)]: " + " | ".join(past_conversations)
        except Exception as e:
            print(f"--- 벡터 검색 컨텍스트 생성 오류: {e} ---")

    # 3. 사용자 속성 컨텍스트
    user_attributes = UserAttribute.objects.filter(user=user)
    if user_attributes.exists():
        attribute_strings = [f"{attr.fact_type}: {attr.content}" for attr in user_attributes]
        contexts['attributes'] = "[사용자 속성]: " + ", ".join(attribute_strings)

    # 4. 사용자 활동 컨텍스트
    activity_strings = []
    try:
        recent_activities = UserActivity.objects.filter(user=user).order_by('-activity_date', '-created_at')[:5]
        if recent_activities:
            activity_strings.extend([
                f"{act.activity_date.strftime('%Y-%m-%d') if act.activity_date else '날짜 미상'} '{act.place}' 방문" +
                (f" (동행: {act.companion})" if act.companion else "") +
                (f" (메모: {act.memo})" if act.memo else "")
                for act in recent_activities
            ])
    except Exception as e:
        print(f"--- 활동 메모리 컨텍스트 생성 오류: {e} ---")

    search_context = search_activities_for_context(user, user_message_text)
    if search_context:
        activity_strings.append(search_context)
    
    recommendation_context = get_activity_recommendation(user, user_message_text)
    if recommendation_context:
        activity_strings.append(recommendation_context)

    if activity_strings:
        contexts['activity'] = "[사용자 활동]: " + "\n".join(activity_strings)

    # 5. 활동 분석 컨텍스트
    try:
        recent_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-period_start_date')[:3]
        if recent_analytics.exists():
            analytics_strings = [
                f"'{an.period_start_date.strftime('%Y-%m-%d')}부터 {an.period_type} 동안 "
                f"장소: {an.place}, 동행: {an.companion or '없음'}, 횟수: {an.count}회'"
                for an in recent_analytics
            ]
            contexts['analytics'] = "[사용자 활동 분석]: " + "\n".join(analytics_strings)
    except Exception as e:
        print(f"--- 활동 분석 컨텍스트 생성 오류: {e} ---")

    # 6. 인간관계 컨텍스트
    try:
        user_relationships = UserRelationship.objects.filter(user=user)
        if user_relationships.exists():
            relationship_strings = []
            for rel in user_relationships:
                details = f"{rel.name} ({rel.relationship_type})"
                if rel.position:
                    details += f", 포지션: {rel.position}"
                if rel.traits:
                    details += f", 특징: {rel.traits}"
                relationship_strings.append(details)
            
            relationship_strings = [f"{rel.name} ({rel.relationship_type}, 특징: {rel.traits})" for rel in user_relationships]
            contexts['relationship'] = "[사용자의 인간관계]: " + "\n".join(relationship_strings)
    except Exception as e:
        print(f"--- 사용자 관계 컨텍스트 생성 오류: {e} ---")

    # 디버깅을 위해 모든 수집된 컨텍스트를 마지막에 한번에 출력
    for key, value in contexts.items():
        print(f"--- [디버그] {key} 컨텍스트: {value} ---")

    return contexts

def _prepare_llm_messages(final_system_prompt, history, user_message_text):
    """API 요청을 위한 메시지 리스트를 준비합니다."""
    messages = [{'role': 'system', 'content': final_system_prompt}]
    recent_history = history[:10]
    for chat in reversed(recent_history):
        role = "user" if chat.is_user else "assistant"
        messages.append({'role': role, 'content': chat.message})
    messages.append({'role': 'user', 'content': user_message_text})
    return messages

def _call_openai_api(client: OpenAI, model_to_use: str, messages: list, stream_mode: bool = False) -> Dict[str, Any]:
    """OpenAI API를 호출하고 응답 JSON을 반환합니다."""
    print(f"--- Using Model: {model_to_use}, Stream: {stream_mode} ---")

    params ={
        "model":model_to_use,
        "messages":messages,
        "temperature":0.7,
        "top_p":0.9,
        "frequency_penalty":0.2,
        "presence_penalty":0.1,
        "stream":stream_mode
    }
    
    # 스트리밍이 아닐 때만 JSON 응답 형식을 요청합니다.
    if not stream_mode:
        params["response_format"] = {"type": "json_object"}
        
    response = client.chat.completions.create(params)

    # 스트리밍 모드일 경우 response는 Generator 객체가 됩니다.
    if stream_mode:
        return response # Generator 객체 반환
    else:
        return response.model_dump() # 일반 응답은 딕셔너리로 변환하여 반환

def _finalize_chat_interaction(request, user_message_text, response_json, history, api_key, image_file: Optional[UploadedFile] = None):
    """성공적인 LLM 응답을 처리하고 관련 데이터를 RDB와 벡터 DB에 저장합니다."""
    user = request.user
    bot_message_text = "음... 생각을 정리하는 데 시간이 좀 걸리네. 다시 한번 말해줄래?"
    explanation = "AI 응답 처리 중 오류 발생."
    bot_message_obj = None
    user_message_obj = None

    try:
        if 'choices' not in response_json or not response_json['choices'] or \
           'message' not in response_json['choices'][0] or \
           'content' not in response_json['choices'][0]['message']:
            raise ValueError("OpenAI API 응답에 'content' 필드가 누락되었습니다.")

        content_from_llm_raw = response_json['choices'][0]['message']['content']

        if content_from_llm_raw is None:
            raise ValueError("OpenAI API 응답의 'content' 필드가 None입니다.")

        # --- 스마트 파싱 로직 시작 ---
        parsed_successfully = False
        try:
            # 가장 먼저, 전체가 유효한 JSON인지 시도
            content_from_llm = json.loads(content_from_llm_raw)
            if 'answer' in content_from_llm:
                bot_message_text = content_from_llm.get('answer', '').strip()
                explanation = content_from_llm.get('explanation', '설명 없음.')
                parsed_successfully = True
            else:
                 explanation = f"LLM 응답 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                 bot_message_text = "AI 응답 형식이 잘못되었습니다. (answer 키 누락)"

        except json.JSONDecodeError:
            # JSON 파싱 실패 시, 문자열 내에서 JSON을 찾아보는 로직
            try:
                start_index = content_from_llm_raw.find('{')
                end_index = content_from_llm_raw.rfind('}') + 1
                if start_index != -1 and end_index != 0:
                    json_str = content_from_llm_raw[start_index:end_index]
                    content_from_llm = json.loads(json_str)
                    if 'answer' in content_from_llm:
                        bot_message_text = content_from_llm.get('answer', '').strip()
                        explanation = content_from_llm.get('explanation', '설명 없음.')
                        parsed_successfully = True
                    else:
                        explanation = f"추출된 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                        bot_message_text = "AI 응답 형식이 잘못되었습니다. (추출된 JSON에 answer 키 누락)"

            except json.JSONDecodeError:
                 explanation = f"LLM 응답에서 JSON을 추출하여 파싱하는 데 실패했습니다."
                 bot_message_text = "AI 응답 형식이 잘못되었습니다. (JSON 파싱 실패)"
        
        # 최종적으로 파싱에 실패했다면, 원본 텍스트라도 답변으로 사용
        if not parsed_successfully and content_from_llm_raw.strip():
            bot_message_text = content_from_llm_raw.strip()
            explanation = "AI가 지정된 JSON 형식을 따르지 않았으나, 원본 응답을 그대로 반환합니다."
        elif not parsed_successfully: # 파싱에 완전히 실패했고, 원본 응답도 비어있거나 없음
            bot_message_text = f"AI 응답 파싱 실패. 원본 응답: '{content_from_llm_raw}'. 설명: {explanation}"
            explanation = "LLM 응답 파싱에 실패하여 디버그 메시지를 반환합니다."
        
        # 답변이 비어있는 경우 방지
        if not bot_message_text.strip():
            bot_message_text = "음... 뭐라 답해야 할지 잘 모르겠어. 다른 질문 해줄래?"
            explanation = "파싱 후 최종 답변이 비어있어 대체 메시지를 사용합니다."

        # --- 스마트 파싱 로직 끝 ---

    except (ValueError, KeyError, IndexError) as e:
        explanation = f"LLM 응답 구조 파싱 실패: {e}"
    except Exception as e:
        explanation = f"예상치 못한 오류 발생: {e}"

    # ChromaDB 컬렉션 가져오기
    collection = vector_service.get_or_create_collection()

    # ChatMessage 저장 시 image_file을 직접 사용
    user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, image=image_file, is_user=True)
    vector_service.upsert_message(collection, user_message_obj)

    bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
    vector_service.upsert_message(collection, bot_message_obj)
    
    recent_history_for_extraction = history[:5]
    extract_and_save_user_context_data(user, user_message_text, bot_message_text, recent_history_for_extraction, api_key)

    # 디버깅을 위해 최종 explanation 내용을 터미널에 출력
    print("\n" + "-"*20 + " [Debug] Response Explanation " + "-"*20)
    print(explanation)
    print("-"*66 + "\n")

    return bot_message_text, explanation, bot_message_obj, user_message_obj


# ----------------------------------------------------
# 비동기 GPT 스트리밍 호출 함수 (Async 버전)
# ----------------------------------------------------

async def async_stream_openai_api(model_to_use: str, messages: list):
    """
    AsyncOpenAI 클라이언트를 사용하여 GPT API를 비동기 스트리밍 방식으로 호출합니다.
    (기존 _call_openai_api와 유사하지만 async 클라이언트 사용)
    """
    # 비동기 클라이언트 초기화
    try:
        client = AsyncOpenAI() # 환경 변수에서 키 자동 로드
    except Exception as e:
        print(f"AsyncOpenAI 클라이언트 초기화 오류: {e}")
        raise APIError(f"AsyncOpenAI 클라이언트 초기화 실패: {e}")

    # 스트리밍 요청 파라미터
    params = {
        "model": model_to_use,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
        "stream": True # 👈 스트리밍 모드 강제
    }

    try:
        # 비동기 호출
        response_stream = await client.chat.completions.create(**params)
        return response_stream # AsyncGenerator 객체 반환
        
    except APIError:
        # APIError는 다시 발생시켜 consumers.py에서 처리하도록 합니다.
        raise
