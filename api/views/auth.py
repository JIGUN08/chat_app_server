# api/views/auth.py

from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
# api 앱의 상위 폴더(api)에 있는 serializers.py에서 임포트해야 합니다.
from ..serializers import RegisterSerializer 

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    """회원가입 API"""
    queryset = User.objects.all()
    # 인증이 필요 없습니다 (새 계정을 만들기 때문)
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer



from rest_framework_simplejwt.views import TokenObtainPairView
from ..serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
