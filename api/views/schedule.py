# api/views/schedule.py

from rest_framework import generics, permissions
from ..models import UserSchedule # Schedule 모델이 있다고 가정
from ..serializers import ScheduleSerializer

class ScheduleListCreateView(generics.ListCreateAPIView):
    """GET: 일정 목록 조회, POST: 새 일정 생성 (인증 필요)"""
    # 🔑 JWT 인증 필요
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        # 현재 로그인된 사용자의 일정만 반환
        return UserSchedule.objects.filter(user=self.request.user).order_by('date','schedule_time')

    def perform_create(self, serializer):
        # 일정 생성 시 현재 사용자를 자동으로 연결
        serializer.save(user=self.request.user)


class ScheduleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """GET: 상세 조회, PUT/PATCH: 수정, DELETE: 삭제 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ScheduleSerializer
    lookup_field = 'pk' # /schedule/1/ 에서 1에 해당하는 ID를 찾습니다.

    def get_queryset(self):
        # 현재 로그인된 사용자의 일정만 조회/수정/삭제 가능하도록 제한
        return UserSchedule.objects.filter(user=self.request.user)
