# api/views/user.py

from rest_framework import generics, permissions
from ..models import UserProfile, UserAttribute, UserRelationship
from ..serializers import UserStatusSerializer, UserProfileSerializer, UserRelationshipSerializer, UserAttributeSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserStatusView(generics.RetrieveAPIView):
    """GET: AI와의 호감도, 기억 등 상태 정보를 조회합니다. (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserStatusSerializer

    def get_object(self):
        # 현재 인증된 사용자 객체를 반환합니다. Serializer가 이 객체(User)를 기반으로 모든 정보를 가져옵니다.
        return self.request.user
    

class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT: 사용자 프로필(UserProfile) 정보를 조회하거나 업데이트합니다. (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    # UserProfile 모델을 다루는 Serializer 사용을 가정합니다.
    serializer_class = UserProfileSerializer 
    
    def get_object(self):
        # 현재 인증된 사용자의 UserProfile 인스턴스를 반환합니다.
        # User 모델에 'profile' related_name으로 연결되어 있습니다.
        return self.request.user.profile
    

class RelationshipListCreateView(generics.ListCreateAPIView):
    """GET: 관계 목록 조회, POST: 새 관계 정보 생성 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserRelationshipSerializer

    def get_queryset(self):
        return UserRelationship.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class RelationshipRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """GET: 상세 조회, PUT/PATCH: 수정, DELETE: 삭제 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserRelationshipSerializer
    lookup_field = 'pk'
    
    def get_queryset(self):
        return UserRelationship.objects.filter(user=self.request.user)
    

class UserAttributeListCreateView(generics.ListCreateAPIView):
    """GET: 속성 목록 조회, POST: 새 속성 생성 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserAttributeSerializer

    def get_queryset(self):
        return UserAttribute.objects.filter(user=self.request.user).order_by('fact_type')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserAttributeRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """GET: 상세 조회, PUT/PATCH: 수정, DELETE: 삭제 (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserAttributeSerializer
    lookup_field = 'pk'
    
    def get_queryset(self):
        return UserAttribute.objects.filter(user=self.request.user)
