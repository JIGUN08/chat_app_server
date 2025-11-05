# api/views/proactive_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import ProactiveMessage
from ..serializers import ProactiveMessageSerializer

class ProactiveMessageViewSet(viewsets.ReadOnlyModelViewSet):
    # 인증된 사용자만 접근 가능
    permission_classes = [IsAuthenticated]
    queryset = ProactiveMessage.objects.all()
    serializer_class = ProactiveMessageSerializer

    def get_queryset(self):
        """현재 로그인된 사용자의 메시지만 반환합니다."""
        return self.queryset.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """
        GET /api/proactive-messages/unread/
        현재 사용자의 읽지 않은 능동 메시지만 조회합니다.
        """
        unread_messages = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(unread_messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_as_read(self, request):
        """
        POST /api/proactive-messages/mark_as_read/
        읽지 않은 모든 메시지를 읽음 처리합니다.
        """
        user = request.user
        
        # 1. 읽지 않은 메시지를 모두 가져옵니다.
        unread_messages = ProactiveMessage.objects.filter(user=user, is_read=False)
        
        if not unread_messages.exists():
            return Response({"detail": "읽지 않은 메시지가 없습니다."}, status=status.HTTP_200_OK)
            
        # 2. 일괄 업데이트 (DB 효율적)
        updated_count = unread_messages.update(is_read=True)

        return Response({
            "detail": f"{updated_count}개의 능동 메시지를 읽음 처리했습니다.", 
            "updated_count": updated_count
        }, status=status.HTTP_200_OK)
