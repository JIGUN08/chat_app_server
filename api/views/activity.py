#activity.py
from rest_framework import generics, permissions
from ..models import UserActivity, ActivityAnalytics , QuizResult
from ..serializers import ActivitySerializer, ActivityAnalyticsSerializer, QuizResultSerializer

class ActivityListCreateView(generics.ListCreateAPIView):
    """GET: 활동 목록 조회, POST: 새 활동 기록 생성 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ActivitySerializer

    def get_queryset(self):
        # 현재 로그인된 사용자의 활동만 반환하도록 필터링
        return UserActivity.objects.filter(user=self.request.user).order_by('-activity_date', '-activity_time')

    def perform_create(self, serializer):
        # 활동 기록 생성 시 현재 사용자를 자동으로 연결
        serializer.save(user=self.request.user)

class ActivityRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """GET: 상세 조회, PUT/PATCH: 수정, DELETE: 삭제 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ActivitySerializer
    lookup_field = 'pk' 
    
    def get_queryset(self):
        # 현재 로그인된 사용자의 활동만 접근 가능하도록 제한
        return UserActivity.objects.filter(user=self.request.user)
    


class AnalyticsListCreateView(generics.ListCreateAPIView):
    """GET: 통계 목록 조회, POST: 새 통계 생성 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ActivityAnalyticsSerializer

    def get_queryset(self):
        # 현재 로그인된 사용자의 통계만 반환
        return ActivityAnalytics.objects.filter(user=self.request.user).order_by('-period_start_date')

    def perform_create(self, serializer):
        # 통계 생성 시 현재 사용자를 자동으로 연결
        # count는 read_only로 설정했으므로 여기서 count=0으로 저장할 필요는 없습니다.
        serializer.save(user=self.request.user)


class QuizResultListCreateView(generics.ListCreateAPIView):
    """GET: 퀴즈 결과 목록 조회, POST: 새 퀴즈 결과 생성 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = QuizResultSerializer

    def get_queryset(self):
        return QuizResult.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
