# api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from api.models import UserAttribute, UserRelationship, UserSchedule, UserProfile, UserActivity, ActivityAnalytics, QuizResult, ProactiveMessage, ChatMessage

########
# 인증 #
User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')
        extra_kwargs = {
            'username': {'required': True},
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


#---------------
# 위치 
#----------------
class LocationRecommendationResultSerializer(serializers.Serializer):
    recommendation_context = serializers.CharField()



#---------------
# 사용자 속성
#----------------
class UserAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAttribute
        fields = ('id', 'fact_type', 'content')
        read_only_fields = ('user', 'created_at')


#-----------------
# 일정 
#-----------------
class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSchedule 
        fields = ('id', 'date', 'schedule_time', 'content')
        read_only_fields = ('user', 'created_at', 'updated_at') # 일정은 항상 요청한 사용자와 연결됩니다.


#-----------------
#  사용자 상태 
#-----------------
class UserRelationshipSerializer(serializers.ModelSerializer):
    class Meta:
        # ⚠️ 모델 이름을 'UserRelationship'으로 가정합니다.
        model = UserRelationship 
        fields = ('id', 'name', 'relationship_type', 'position', 'traits', 'disambiguator', 'serial_code')

        read_only_fields = ('user', 'serial_code')

class UserStatusSerializer(serializers.Serializer):
    """AI 상태 페이지에 필요한 데이터를 하나로 묶어 직렬화"""
    # UserProfile 모델에서 가져올 필드
    chatbot_name = serializers.CharField(source='userprofile.chatbot_name')
    affinity_score = serializers.IntegerField(source='userprofile.affinity_score', allow_null=True)
    
    # UserAttribute 모델에서 가져올 속성
    core_facts = UserAttributeSerializer(many=True, source='attributes') 
    
    # UserRelationship 모델에서 가져올 관계 정보
    user_relationships = UserRelationshipSerializer(many=True, source='relationships')
    
    class Meta:
        fields = ('chatbot_name', 'affinity_score', 'core_facts', 'user_relationships')
        



#-----------------
#  사용자 프로필 
#-----------------
class UserProfileSerializer(serializers.ModelSerializer):
    """
    사용자 프로필 정보를 조회하고 업데이트하는 Serializer.
    (views.user.UserProfileView와 연결됨)
    """
    class Meta:
        model = UserProfile
        # 사용자가 수정할 수 있는 필드와 조회 가능한 필드 포함
        fields = (
            'is_onboarding_complete', 
            'chatbot_name', 
            'affinity_score', 
            'memory'
        )
        # 호감도와 기억은 뷰에서 로직으로만 변경되도록 읽기 전용으로 설정
        read_only_fields = ('affinity_score', 'memory') 
        # is_onboarding_complete와 chatbot_name은 수정 가능


#-----------------
#  사용자 활동
#-----------------
class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = ('id', 'activity_date', 'activity_time', 'place', 'companion', 'memo') 
        read_only_fields = ('user',)



class ActivityAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityAnalytics
        fields = (
            'id', 
            'period_type', 
            'period_start_date', 
            'place', 
            'companion', 
            'count'
        )
        read_only_fields = ('user', 'count')


#-----------------
#  퀴즈
#-----------------        

class QuizResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizResult
        fields = ('id', 'genre', 'num_questions', 'score')
        read_only_fields = ('user', 'date_completed')



#-----------------
#  능동 메세지
#-----------------    

class ProactiveMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProactiveMessage
        # Flutter 앱에 보낼 필드를 지정합니다.
        fields = ('id', 'message', 'created_at', 'emotion', 'is_read')




# -----------------
#  JWT 커스터마이징
# -----------------
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    로그인 시 반환되는 JWT에 username과 email을 포함시킵니다.
    Flutter AuthService에서 username/email을 추출할 수 있게 됩니다.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        return token
    


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    사용자의 채팅 메시지를 직렬화합니다.
    사용자 필드는 읽기 전용으로 설정하여 현재 인증된 사용자로 자동 설정되도록 합니다.
    """
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'user', 'message', 'image', 'is_user', 
            'character_emotion', 'timestamp'
        ]
        read_only_fields = ['user', 'timestamp'] # User and timestamp are set automatically    
