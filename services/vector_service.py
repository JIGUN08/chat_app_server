# services/vector_service_pg.py

# ==========================================================
# 🚨 긴급 복구 모드: Status 132 오류 해결을 위해 기능 우회 🚨
# ==========================================================
from typing import List, Dict, Any, Optional
import os

# 임시로 OpenAI 임베딩 생성 기능도 비활성화
def get_openai_embedding(text: str) -> Optional[List[float]]:
    """더미 함수: 임베딩 생성 건너뛰기"""
    return None

def setup_vector_table(table_name="chat_vectors", embedding_dim=1536):
    """더미 함수: 테이블 생성 건너뛰기"""
    print(f"--- [DEBUG] Vector Service Disabled: Table setup skipped. ---")
    pass

def connect_db():
    """더미 함수: DB 연결 건너뛰기"""
    return None

def get_or_create_collection(collection_name: str) -> None:
    """더미 함수: 컬렉션 생성 호출 처리"""
    print(f"--- [DEBUG] Vector Service Disabled: Collection '{collection_name}' creation skipped. ---")
    pass

def upsert_message(table_name: str, chat_message: Any):
    """더미 함수: 메시지 저장 건너뛰기"""
    print(f"--- [DEBUG] Vector Service Disabled: Upsert skipped for message ID {getattr(chat_message, 'id', 'N/A')}. ---")
    return

def add_documents_to_collection(collection_name: str, chat_message: Any) -> None:
    """더미 함수: 외부 인터페이스 처리"""
    upsert_message(table_name=collection_name, chat_message=chat_message)

def query_similar_messages(table_name: str, query_text: str, user_id: int, n_results: int = 3, distance_threshold: float = 0.8) -> Dict[str, Any]:
    """더미 함수: 검색 결과 없음 반환"""
    print(f"--- [DEBUG] Vector Service Disabled: Query skipped. ---")
    return {
        'ids': [], 'documents': [], 'metadatas': [], 'distances': []
    }
