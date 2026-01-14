from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status,filters,viewsets,permissions
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import random

# Import your models and serializers
from .models import CustomUser
from .serializers import ( 
    VerifyOTPSerializer, 
    UserDetailSerializer, 
    UserSignUpSerializer, 
    PropertySerializer
)

from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count

# Import your models and serializers
from .models import Property
from .permissions import IsOwnerOrReadOnly

# ==========================================
# 1. SERVICE LAYER (Business Logic)
# ==========================================
class OTPService:
    """
    Handles all OTP related operations to keep Views clean.
    """
    @staticmethod
    def get_cache_key(phone, purpose):
        """Generates a unique cache key based on phone and purpose."""
        return f"otp_{purpose}_{phone}"

    @staticmethod
    def generate_and_send(phone, purpose, user_data=None):
        """
        Generates OTP, caches data, and 'sends' it.
        params:
            purpose: 'LOGIN' or 'SIGNUP'
            user_data: Dict of user info (only needed for SIGNUP)
        """
        otp = str(random.randint(1000, 9999))
        cache_key = OTPService.get_cache_key(phone, purpose)
        
        # Store OTP and any extra data (like name/address for signup)
        payload = {
            'otp': otp,
            'user_data': user_data
        }
        
        # Save to Redis/Memcached for 5 minutes (300s)
        cache.set(cache_key, payload, timeout=300)

        # Mock Sending (Replace with real SMS logic)
        print(f"\n[SMS SERVICE] sending to {phone} for {purpose}: {otp}\n")
        return otp

    @staticmethod
    def verify(phone, otp_input, purpose):
        """
        Verifies OTP and returns the cached payload if valid.
        Returns None if invalid.
        """
        cache_key = OTPService.get_cache_key(phone, purpose)
        cached_payload = cache.get(cache_key)

        if cached_payload and cached_payload['otp'] == otp_input:
            # Clear cache to prevent replay attacks
            cache.delete(cache_key)
            return cached_payload
        return None

    @staticmethod
    def get_tokens(user):
        """Generates JWT tokens for a user."""
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

# ==========================================
# 2. VIEWS
# ==========================================

class AuthInitView(APIView):
    """
    Unified Endpoint to initialize Login OR Signup.
    Use the 'purpose' field in the serializer to switch modes.
    """
    
    # Swagger Documentation
    @swagger_auto_schema(
        operation_description="Send OTP for Login or Signup",
        request_body=UserSignUpSerializer, 
        responses={200: "OTP Sent"}
    )
    def post(self, request):
        # We use the SignUp serializer because it covers both cases 
        # (It has phone, name, etc. For login, we might just check phone)
        serializer = UserSignUpSerializer(data=request.data)
        print(serializer.is_valid())
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            # Determine if this is a Login or Signup request based on existence
            user_exists = CustomUser.objects.filter(phone=phone).exists()
     
            # --- SCENARIO A: LOGIN (User Exists) ---
            if user_exists:
                OTPService.generate_and_send(phone, purpose="LOGIN")
                return Response({
                    "message": "User exists. OTP sent for Login. <Redirect to OTP Page>",
                    "purpose": "LOGIN" 
                }, status=status.HTTP_200_OK)
            
            elif serializer.validated_data.get('full_name') != None:
                OTPService.generate_and_send(
                    phone, 
                    purpose="SIGNUP", 
                    user_data=serializer.validated_data
                )
                return Response({
                    "message": "Verify OTP to complete Signup.",
                    "phone": serializer.validated_data['phone'],
                }, status=status.HTTP_200_OK)
            # --- SCENARIO B: SIGNUP (New User) ---
            else:
                # We cache the submitted data (Name, Address) so we can save it later
                
                return Response({
                    "message": "Redirect to Signup.",
                    "purpose": "SIGNUP",
                    "phone": serializer.validated_data['phone'],
                }, status=status.HTTP_200_OK)

        else:
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuthVerifyView(APIView):
    """
    Unified Endpoint to Verify OTP and Finalize Auth.
    Handles both Login and Signup completion.
    """
    
    @swagger_auto_schema(
        operation_description="Verify OTP and return JWT Tokens",
        request_body=VerifyOTPSerializer,
        responses={200: "Success + Tokens", 400: "Invalid OTP"}
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            otp_input = serializer.validated_data['otp']
            
            # Note: You should add a 'purpose' field to your VerifySerializer 
            # so the backend knows which cache key to check.
            # For now, we try 'LOGIN' first, then 'SIGNUP' if that fails, 
            # or require it from frontend. Let's assume frontend sends it.
            purpose = request.data.get('purpose', 'LOGIN').upper() 

            # 1. Verify OTP using Service
            payload = OTPService.verify(phone, otp_input, purpose)

            if not payload:
                return Response({"error": "Invalid or Expired OTP"}, status=status.HTTP_400_BAD_REQUEST)

            user = None

            # 2. Handle Logic based on Purpose
            if purpose == 'LOGIN':
                try:
                    user = CustomUser.objects.get(phone=phone)
                except CustomUser.DoesNotExist:
                     return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            elif purpose == 'SIGNUP':
                user_data = payload.get('user_data')
                if not user_data:
                     return Response({"error": "Session error. Restart Signup."}, status=status.HTTP_400_BAD_REQUEST)
                
                # Create the user now
                user = CustomUser.objects.create_user(
                    phone=user_data['phone'],
                    full_name=user_data.get('full_name', ''),
                    email=user_data.get('email', ''),
                    # Add other fields as needed
                )

            # 3. Generate Tokens & Return
            tokens = OTPService.get_tokens(user)
            return Response({
                "message": "Authentication successful",
                "tokens": tokens,
                "user": UserDetailSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class PropertyViewSet(viewsets.ModelViewSet):
    """
    A generic ViewSet for viewing and editing properties.
    """
    serializer_class = PropertySerializer
    # Adding parsers is important if you are uploading images (multipart)
    parser_classes = [JSONParser, MultiPartParser, FormParser] 
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = [ 'location', 'status']
    ordering_fields = ['price_value', 'created_at']
    search_fields = ['title', 'colony', 'description']

    def get_queryset(self):
        """
        Optionally restricts the returned properties to a given user,
        by filtering against a `mine` query parameter in the URL.
        """
        # Start with all properties and annotate lead counts
        qs = Property.objects.all().order_by('-created_at')

        # Handle '?mine=true' filter
        if self.request.query_params.get('mine') == 'true':
            if self.request.user.is_authenticated:
                return qs.filter(owner=self.request.user)
            return qs.none() # Return empty list if not logged in

        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        # For update/partial_update/destroy, check if they own it
        return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
    
    def perform_create(self, serializer):
        """
        When a property is saved, automatically assign the current user as the owner.
        """
        serializer.save(owner=self.request.user)

    # --- SWAGGER DOCUMENTATION DECORATORS ---
    
    @swagger_auto_schema(
        operation_description="List all properties or filter by type, location, etc.",
        manual_parameters=[
            openapi.Parameter('mine', openapi.IN_QUERY, description="Filter by 'true' to see only my properties", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Post a new property (Requires Login). Owner is assigned automatically.",
        request_body=PropertySerializer,
        responses={201: PropertySerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('mine', openapi.IN_QUERY, description="Show only my properties", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('purpose', openapi.IN_QUERY, description="Filter by SALE or RENT", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

from .models import Lead
from .serializers import LeadSerializer
class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    
    def get_permissions(self):
        """
        Allow anyone to POST (create) a lead.
        Require login to GET (view) leads.
        """
        # if self.action == 'create':
        #     return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """
        Filter leads based on who is asking.
        """
        user = self.request.user
        if not user.is_authenticated:
            return None

        # 1. Show leads received on properties I own
        # 2. Show leads I sent to others
        leads_sent = Lead.objects.filter(user=user)

        # distinct() is needed because a user might have sent a lead to their own property (testing)
        return leads_sent.distinct().order_by('-created_at')

    def perform_create(self, serializer):
        # If user is logged in, save them as the 'user' of the lead
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()