#emotion_service.py
import os
import json
import re
from openai import OpenAI

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class EmotionAnalyzer:
    """
    기존 구조 그대로 유지.
    GPT 모델을 내부적으로 사용해 감정 점수를 계산하는 클래스.
    """
    def __init__(self):
        self.classifier = True  # 기존 호환성 유지를 위해 더미 값 유지
        print("--- EmotionAnalyzer (GPT API version) initialized successfully. ---")

    def analyze(self, text: str):
        """
        주어진 텍스트의 감정을 분석하고, 모든 감정 레이블과 점수를 반환합니다.
        반환 형식:
        [
            {"label": "0", "score": 0.05},
            {"label": "1", "score": 0.10},
            {"label": "2", "score": 0.07},
            {"label": "3", "score": 0.15},
            {"label": "4", "score": 0.40},
            {"label": "5", "score": 0.18},
            {"label": "6", "score": 0.05}
        ]
        """
        if not self.classifier or not isinstance(text, str) or not text.strip():
            return []

        try:
            prompt = f"""
            당신은 한국어 감정 분석 전문가입니다.
            아래 문장의 감정을 각각의 점수(0~1)로 평가하세요.
            가능한 감정은 다음 7가지입니다:
            0: 공포, 1: 놀람, 2: 분노, 3: 슬픔, 4: 중립, 5: 행복, 6: 혐오

            문장: "{text}"

            각 감정에 대해 확률처럼 보이는 점수를 부여한 뒤,
            반드시 아래 JSON **객체** 형식으로 출력하세요.
            예시:
            {{"emotion_scores": [
              {{"label": "0", "score": 0.05}},
              {{"label": "1", "score": 0.12}},
              {{"label": "2", "score": 0.08}},
              {{"label": "3", "score": 0.20}},
              {{"label": "4", "score": 0.40}},
              {{"label": "5", "score": 0.10}},
              {{"label": "6", "score": 0.05}}
            ]}}
            """

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 한국어 감정 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content.strip()

            try:
                # JSON 객체 전체를 파싱
                full_result = json.loads(result_text)
                # 여기서 배열만 추출
                emotion_scores = full_result.get("emotion_scores", [])
                return emotion_scores
            except json.JSONDecodeError:
                print(f"--- Invalid GPT response format (JSON mode failed): {result_text} ---")
                return []
        except Exception as e:
            # API 호출 중 발생할 수 있는 다른 예외 처리 (예: API 키 문제, 네트워크 오류 등)
            print(f"--- [에러] API 호출 중 문제가 발생했습니다: {e} ---")
            return []

# ✅ Django 앱 로드 시 1회만 인스턴스 생성
emotion_analyzer_instance = EmotionAnalyzer()


def analyze_emotion(bot_message_text: str) -> str:
    """
    GPT가 예측한 결과 중 가장 높은 감정 ID를 변환하여 반환.
    """
    default_model_label = "중립"

    try:
        emotion_results = emotion_analyzer_instance.analyze(bot_message_text)

        if not emotion_results:
            return default_model_label

        ID_TO_LABEL_MAP = {
            0: "공포", 1: "놀람", 2: "분노", 3: "슬픔",
            4: "중립", 5: "행복", 6: "혐오"
        }

        # 🎯 수정: 배열 전체를 순회하며 최고 점수 감정을 찾습니다.
        top_score = -1.0
        top_label_int = 4 # 기본값을 중립(4)으로 설정
        
        for item in emotion_results:
            current_score = float(item.get("score", 0.0))
            current_label_int = int(item.get("label", 4))

            if current_score > top_score:
                top_score = current_score
                top_label_int = current_label_int

        final_label = ID_TO_LABEL_MAP.get(top_label_int, default_model_label)

        print(f"\n--- Emotion Analysis (GPT API, FIX Applied) ---")
        print(f"Message: {bot_message_text}")
        print(f"Top Emotion ID: {top_label_int} (Score: {top_score}) -> Final Label: {final_label}")
        print(f"---------------------------------------------")

        return final_label

    except (ValueError, TypeError, IndexError) as e:
        print(f"--- Emotion Service Error during processing: {e} ---")
        return default_model_label
