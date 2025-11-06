# vector_service_pg.py (Render PostgreSQL + pgvector 용)

import psycopg2
import openai
import os
import json
from psycopg2 import sql
from typing import List, Dict, Any, Optional

# PostgreSQL 접속 정보
# Render 환경 변수에서 가져오는 것을 가정
DATABASE_URL = os.environ.get("DATABASE_URL")
# 임베딩 함수는 ChromaDB에서와 동일하게 OpenAI를 사용합니다.
OPENAI_EF_MODEL = "text-embedding-3-small"

# OpenAI 클라이언트 초기화 (임베딩 생성용)
openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_openai_embedding(text: str) -> Optional[List[float]]:
    """
    OpenAI API를 사용하여 텍스트를 벡터(임베딩)로 변환합니다.
    """
    if not text.strip():
        return None
    try:
        response = openai_client.embeddings.create(
            input=[text],
            model=OPENAI_EF_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"--- [OpenAI] Error creating embedding: {e} ---")
        return None

def connect_db():
    """DB 연결 객체를 반환"""
    return psycopg2.connect(DATABASE_URL)

def setup_vector_table(table_name="chat_vectors", embedding_dim=1536):
    """
    pgvector 확장이 활성화된 PostgreSQL에 벡터 저장용 테이블을 생성합니다.
    text-embedding-3-small의 기본 차원은 1536입니다.
    """
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                # 1. pgvector 확장 활성화 확인 (선행 작업으로 이미 되어있어야 함)
                # 2. 벡터 저장용 테이블 생성
                cur.execute(sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        id VARCHAR(255) PRIMARY KEY,
                        embedding VECTOR(%s),
                        document TEXT NOT NULL,
                        speaker VARCHAR(10) NOT NULL,
                        user_id INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE
                    );
                """).format(sql.Identifier(table_name)), [embedding_dim])
            conn.commit()
            print(f"--- [PostgreSQL] Table '{table_name}' checked/created successfully. ---")
    except Exception as e:
        print(f"--- [PostgreSQL] Error setting up table: {e} ---")

def upsert_message(table_name: str, chat_message: Any): # ChatMessage는 Django 모델 객체를 가정
    """
    ChatMessage 객체를 벡터화하여 PostgreSQL 테이블에 저장/업데이트합니다.
    """
    embedding = get_openai_embedding(chat_message.message)
    if embedding is None:
        print(f"--- [PostgreSQL] Skipping upsert for message ID {chat_message.id}: Failed to generate embedding. ---")
        return

    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                # 벡터를 문자열 형태로 변환하여 SQL에 전달 (pgvector의 기본 방식)
                vector_string = '[' + ','.join(map(str, embedding)) + ']'
                
                # ON CONFLICT (id) DO UPDATE를 사용하여 upsert 구현
                cur.execute(sql.SQL("""
                    INSERT INTO {} (id, embedding, document, speaker, user_id, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        document = EXCLUDED.document,
                        speaker = EXCLUDED.speaker,
                        user_id = EXCLUDED.user_id,
                        timestamp = EXCLUDED.timestamp;
                """).format(sql.Identifier(table_name)), (
                    str(chat_message.id),
                    vector_string, # 벡터 문자열
                    chat_message.message,
                    "user" if chat_message.is_user else "ai",
                    chat_message.user.id,
                    chat_message.timestamp
                ))
            conn.commit()
            print(f"--- [PostgreSQL] Successfully upserted message ID: {chat_message.id} ---")
    except Exception as e:
        print(f"--- [PostgreSQL] Error upserting message ID {chat_message.id}: {e} ---")

def query_similar_messages(table_name: str, query_text: str, user_id: int, n_results: int = 3, distance_threshold: float = 0.8) -> Dict[str, Any]:
    """
    주어진 텍스트와 가장 유사한 대화 내용을 pgvector를 사용하여 검색합니다.
    코사인 유사도 (Cosine Similarity)를 사용하며, <-> 연산자는 L2 거리를 계산합니다.
    코사인 거리를 사용하려면 <#> (Negative Inner Product) 또는 <=> (Cosine Distance) 연산자를 사용할 수 있습니다.
    여기서는 Render의 일반적인 사용법인 코사인 거리를 사용하겠습니다.
    """
    query_embedding = get_openai_embedding(query_text)
    
    filtered_results = {
        'ids': [], 'documents': [], 'metadatas': [], 'distances': []
    }

    if query_embedding is None:
        print("--- [PostgreSQL] Query failed: Failed to generate query embedding. ---")
        return filtered_results
    
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                # pgvector의 코사인 거리 연산자 <=> (낮을수록 유사)
                # 코사인 거리 0은 완벽히 유사, 1은 완벽히 다름
                vector_string = '[' + ','.join(map(str, query_embedding)) + ']'
                
                cur.execute(sql.SQL("""
                    SELECT 
                        id, 
                        document, 
                        speaker, 
                        user_id, 
                        timestamp, 
                        embedding <=> %s AS distance
                    FROM 
                        {}
                    WHERE 
                        user_id = %s 
                    ORDER BY 
                        distance ASC
                    LIMIT %s;
                """).format(sql.Identifier(table_name)), (vector_string, user_id, n_results))

                results = cur.fetchall()

                for result in results:
                    _id, document, speaker, _user_id, timestamp, distance = result
                    
                    # 🚨 [임계값 필터링] 거리가 임계값 이하인 경우만 포함
                    if distance <= distance_threshold:
                        filtered_results['ids'].append(_id)
                        filtered_results['documents'].append(document)
                        filtered_results['metadatas'].append({
                            "speaker": speaker,
                            "user_id": _user_id,
                            "timestamp": timestamp.isoformat()
                        })
                        filtered_results['distances'].append(distance)
                        
        print(f"--- [PostgreSQL] Query successful. Found {len(filtered_results['ids'])} results below distance threshold {distance_threshold}. ---")
        return filtered_results
    
    except Exception as e:
        print(f"--- [PostgreSQL] Error querying table: {e} ---")
        return filtered_results

def get_or_create_collection(collection_name: str) -> None:
    """
    외부 인터페이스 (예: Django Channels Consumer)에서 예상하는 함수명입니다.
    실제로는 벡터 저장용 PostgreSQL 테이블이 있는지 확인하고 생성합니다.
    """
    # 테이블 이름은 collection_name을 따르도록 설정
    setup_vector_table(table_name=collection_name)
    print(f"--- [Vector Service] Collection/Table '{collection_name}' checked/created. ---")


def add_documents_to_collection(collection_name: str, chat_message: Any) -> None:
    """
    외부 인터페이스를 위해 ChromaDB의 add와 유사하게 구현합니다.
    """
    upsert_message(table_name=collection_name, chat_message=chat_message)
