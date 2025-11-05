# api/urls.py
from django.urls import path, include
from .views.auth import RegisterView, CustomTokenObtainPairView
from rest_framework.routers import DefaultRouter
from .views.proactive_views import ProactiveMessageViewSet
from .views.main import LocationRecommendationView, OnboardingSetupView
from .views.schedule import ScheduleListCreateView, ScheduleRetrieveUpdateDestroyView
from .views.chat import ChatMessageListCreateView, ChatMessageRetrieveUpdateDestroyView
from .views.user import UserProfileView, UserStatusView, RelationshipListCreateView, RelationshipRetrieveUpdateDestroyView, UserAttributeListCreateView, UserAttributeRetrieveUpdateDestroyView
from .views.activity import ActivityListCreateView, ActivityRetrieveUpdateDestroyView, AnalyticsListCreateView, QuizResultListCreateView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()

router.register(r'proactive-messages', ProactiveMessageViewSet, basename='proactive-message')

urlpatterns = [
    path('', include(router.urls)),

    path("auth/register/", RegisterView.as_view(), name="user_register"),

    path("token/",  CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("user/profile/", UserProfileView.as_view(), name="user_profile"),
    path("user/status/", UserStatusView.as_view(), name="user_status"),

    path("onboarding/setup/", OnboardingSetupView.as_view(), name="onboarding_setup"),
    path("location/recommendation/", LocationRecommendationView.as_view(), name="location_recommendation"),

    path("chat/messages/", ChatMessageListCreateView.as_view(), name="chat_message_list_create"),
    path("chat/messages/<int:pk>/", ChatMessageRetrieveUpdateDestroyView.as_view(), name="chat_message_detail"),


    path("schedule/", ScheduleListCreateView.as_view(), name="schedule_list_create"),
    path("schedule/<int:pk>/", ScheduleRetrieveUpdateDestroyView.as_view(), name="schedule_detail"),

    path("analytics/", AnalyticsListCreateView.as_view(), name="analytics_list_create"),

    path("activities/", ActivityListCreateView.as_view(), name="activity_list_create"),
    path("activities/<int:pk>/", ActivityRetrieveUpdateDestroyView.as_view(), name="activity_detail"),

    path("relationships/", RelationshipListCreateView.as_view(), name="relationship_list_create"),
    path("relationships/<int:pk>/", RelationshipRetrieveUpdateDestroyView.as_view(), name="relationship_detail"),

    path("attributes/", UserAttributeListCreateView.as_view(), name="attribute_list_create"),
    path("attributes/<int:pk>/", UserAttributeRetrieveUpdateDestroyView.as_view(), name="attribute_detail"),

    path("quiz/results/", QuizResultListCreateView.as_view(), name="quiz_result_list_create"),
]


