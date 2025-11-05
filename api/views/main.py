# /api/views/main.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions


from ..models import UserProfile, UserAttribute
from services.location_service import get_location_based_recommendation 

PERSISTENT_ATTRIBUTES = ['성별', 'mbti', '나이']

class LocationRecommendationView(APIView):
    """GET: 위치 기반 장소 추천을 요청합니다. (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        latitude = request.query_params.get('lat')
        longitude = request.query_params.get('lon')
        user_query = request.query_params.get('query', '') 
        
        if not latitude or not longitude:
            return Response({"detail": "위도(lat)와 경도(lon)는 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            lat, lon = float(latitude), float(longitude)
        except ValueError:
            return Response({"detail": "위도와 경도는 숫자여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 🔑 location_service 호출 (가정)
        # 실제로는 여기서 로직이 서비스로 분리되어 실행됩니다.
        result_text = get_location_based_recommendation(
            request.user, user_query, lat, lon
        )
        
        return Response({'recommendation_context': result_text}, status=status.HTTP_200_OK)


class OnboardingSetupView(APIView):
    """POST: 온보딩 과정에서 사용자 정보를 저장합니다. (인증 필요)"""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        data = request.data # DRF는 request.data를 사용하여 JSON을 파싱합니다.
        fact_type = data.get('fact_type')
        content = data.get('content')
        action = data.get('action')

        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if fact_type and content:
            if fact_type == '이름':
                user.first_name = content
                user.save()
            
            elif fact_type == 'ai_name':
                profile.chatbot_name = content
                profile.save()

            elif fact_type in PERSISTENT_ATTRIBUTES:
                UserAttribute.objects.update_or_create(
                    user=user,
                    fact_type=fact_type,
                    defaults={'content': content}
                )
            return Response({'status': 'success', 'message': f'{fact_type} 저장 완료'}, status=status.HTTP_200_OK)
            
        elif action == 'complete':
            profile.is_onboarding_complete = True
            profile.save()
            return Response({'status': 'success', 'message': '온보딩 완료'}, status=status.HTTP_200_OK)

        return Response({'status': 'error', 'message': '데이터가 누락되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)
