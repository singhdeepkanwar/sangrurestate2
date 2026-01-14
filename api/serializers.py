from rest_framework import serializers
from .models import CustomUser, Property, PropertyImages
import re

# ==========================================
# 1. AUTHENTICATION SERIALIZERS
# ==========================================

class VerifyOTPSerializer(serializers.Serializer):
    """
    Used for the /auth/verify/ endpoint.
    """
    phone = serializers.CharField()
    otp = serializers.CharField(max_length=4, min_length=4)
    # This matches the 'purpose' logic we added to the View
    purpose = serializers.ChoiceField(choices=['LOGIN', 'SIGNUP'], default='LOGIN')

    def validate_phone(self, value):
        # Basic validation: Ensure it's 10-15 digits
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number.")
        return value


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Used to send user profile data back to the frontend.
    """
    class Meta:
        model = CustomUser
        fields = ['id', 'phone', 'full_name', 'email', 'city', 'address']


class UserSignUpSerializer(serializers.ModelSerializer):
    """
    Used for the /auth/init/ endpoint. 
    Handles both Login (Phone only) and Signup (Full details).
    """
    # We explicitly define phone to add custom validation if needed
    phone = serializers.CharField() 

    class Meta:
        model = CustomUser
        fields = ['phone', 'full_name', 'email', 'address', 'city']
        # We make fields optional so this serializer works for Login checks too
        extra_kwargs = {
            'full_name': {'required': False}, 
            'email': {'required': False},
            'address': {'required': False},
            'city': {'required': False},
        }

    def validate_phone(self, value):
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number.")
        return value

# ==========================================
# 2. PROPERTY SERIALIZERS
# ==========================================

class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImages
        fields = ['id', 'image']



class PropertySerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    leads_count = serializers.IntegerField(read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)

    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=1000000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False 
    )
    class Meta:
        model = Property
        fields = '__all__'
        read_only_fields = ['owner', 'created_at', 'status', 'leads_count']


    def validate(self, data):
        """
        Custom validation to enforce logic between Sale and Rent.
        """
        purpose = data.get('purpose')
        
        # Logic: If Renting, Frequency is required
        if purpose == 'RENT':
            if not data.get('rental_frequency'):
                raise serializers.ValidationError({"rental_frequency": "Required for rental properties."})
        
        # Logic: If Selling, Frequency should be empty
        if purpose == 'SALE':
            if data.get('rental_frequency'):
                data['rental_frequency'] = None # Auto-clean the data
            if data.get('security_deposit'):
                data['security_deposit'] = None

        return data
    
    def create(self, validated_data):
        # 1. Pop the images out because 'Property' model doesn't have an 'uploaded_images' field
        uploaded_images = validated_data.pop("uploaded_images", [])

        # 2. Create the Property first
        property_obj = Property.objects.create(**validated_data)

        # 3. Loop through images and save them linked to the property
        for image in uploaded_images:
            PropertyImages.objects.create(property=property_obj, image=image)

        return property_obj

from .models import Lead

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['id', 'property', 'name', 'phone', 'email', 'message', 'created_at']
        read_only_fields = ['created_at']

    def validate(self, data):
        # Access the user from the context
        user = self.context['request'].user

        # If user is NOT logged in, Name and Phone are mandatory manually
        if not user.is_authenticated:
            if not data.get('name'):
                raise serializers.ValidationError({"name": "Name is required for guest users."})
            if not data.get('phone'):
                raise serializers.ValidationError({"phone": "Phone is required for guest users."})
        
        return data