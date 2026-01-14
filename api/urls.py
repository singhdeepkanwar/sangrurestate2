# api/urls.py
from django.urls import path,include
from .views import AuthInitView, AuthVerifyView, PropertyViewSet
from rest_framework.routers import DefaultRouter
from .views import LeadViewSet

router = DefaultRouter()
router.register(r'properties', PropertyViewSet, basename='properties')
router.register(r'leads', LeadViewSet, basename='lead')

urlpatterns = [
    # 1. Unified Entry Point (Handles both Login & Signup requests)
    # Payload: { "phone": "...", "full_name": "..." }
    path('auth/init/', AuthInitView.as_view(), name='auth-init'),

    # 2. Unified Verification (Verifies OTP & returns Tokens)
    # Payload: { "phone": "...", "otp": "...", "purpose": "LOGIN" or "SIGNUP" }
    path('auth/verify/', AuthVerifyView.as_view(), name='auth-verify'),

    path('', include(router.urls)),  # Property endpoints

]