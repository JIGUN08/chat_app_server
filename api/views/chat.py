from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination
from ..models import ChatMessage
from ..serializers import ChatMessageSerializer

# 커스텀 페이지네이션 설정 (예: 페이지당 50개의 메시지)
class ChatMessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class ChatMessageListCreateView(generics.ListCreateAPIView):
    """
    GET: 현재 사용자의 채팅 메시지 목록을 최신순으로 조회 (페이지네이션 적용).
    POST: 새 채팅 메시지 (사용자 또는 AI)를 생성합니다.
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ChatMessagePagination

    def get_queryset(self):
        """현재 인증된 사용자의 메시지만 반환합니다."""
        return ChatMessage.objects.filter(user=self.request.user).order_by('-timestamp')

    def perform_create(self, serializer):
        """메시지 생성 시, 사용자 필드를 현재 인증된 사용자로 자동 설정합니다."""
        # is_user 필드가 POST 데이터에 없거나 True로 설정된 경우, 기본적으로 사용자 메시지로 간주
        is_user = serializer.validated_data.get('is_user', True)
        
        # is_user가 True (사용자 메시지)이면, chatbot_name이나 emotion은 저장하지 않습니다.
        if is_user:
            serializer.validated_data['character_emotion'] = None

        serializer.save(user=self.request.user)

class ChatMessageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET, PUT/PATCH, DELETE: 특정 채팅 메시지를 조회, 수정, 삭제합니다.
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ChatMessage.objects.all()

    def get_queryset(self):
        """현재 인증된 사용자가 소유한 메시지만 조회/수정/삭제 가능하도록 필터링합니다."""
        return self.queryset.filter(user=self.request.user)
