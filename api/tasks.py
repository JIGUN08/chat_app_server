# api/tasks.py

from celery import shared_task
from django.contrib.auth import get_user_model
from services import proactive_service # proactive_service 임포트

User = get_user_model()

@shared_task(bind=True)
def check_and_send_proactive_messages(self):
    """
    모든 활성 사용자들에 대해 능동 메시지 트리거를 확인하고 생성합니다.
    """
    print("--- [Scheduler] 능동 메시지 확인 태스크 시작 ---")
    
    # 🚨 능동 메시지 생성 로직을 반복 실행
    active_users = User.objects.filter(is_active=True) # 활성 사용자 필터링
    
    for user in active_users:
        # 이미 읽지 않은 능동 메시지가 대기 중이라면 새로 생성하지 않습니다. (선택적 최적화)
        from api.models import PendingProactiveMessage
        if PendingProactiveMessage.objects.filter(user=user).exists():
            print(f"--- [Scheduler] {user.username}님에게 이미 대기 중인 메시지가 있습니다. 스킵합니다. ---")
            continue
            
        proactive_message_obj = proactive_service.generate_proactive_message(user)
        
        if proactive_message_obj:
            print(f"--- [Scheduler] {user.username}님에게 능동 메시지 '{proactive_message_obj.message[:20]}...' 생성 완료 ---")
        else:
            # 트리거 조건에 맞지 않아 메시지 생성이 안 된 경우
            print(f"--- [Scheduler] {user.username}님에게 보낼 능동 메시지 트리거에 해당하지 않아 메시지를 생성하지 않았습니다. ---")
            
    print("--- [Scheduler] 능동 메시지 확인 태스크 종료 ---")
