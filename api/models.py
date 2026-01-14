from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import CustomUserManager
from django.conf import settings

# ==========================================
# 1. CUSTOM USER MODEL
# ==========================================
# Custom User model using phone number as USERNAME_FIELD

class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Custom Fields for the User Model
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True)
    city = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    # Required Django Fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # True if they can access admin panel

    # Configuration
    USERNAME_FIELD = 'phone'
    
    # These fields are asked for when running 'python manage.py createsuperuser'
    REQUIRED_FIELDS = ['full_name'] 

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name}|{self.phone}"
    
# ==========================================
# 2. PROPERTY MODEL
# ==========================================
# Model to represent a Property listing

class Property(models.Model):
    # --- Choices ---
    PROPERTY_TYPES = [('APARTMENT', 'Apartment'), ('HOUSE', 'House'), ('COMMERCIAL', 'Commercial'),('LAND', 'Land'),('PLOT','Plot'),('PG','PG')]
    STATUS_CHOICES = [('AVAILABLE', 'Available'), ('SOLD', 'Sold'), ('RENTED', 'Rented'),('DRAFT','Draft'),('UNDER_REVIEW','Under Review')]
    
    # New: Define the purpose of the listing
    PURPOSE_CHOICES = [
        ('SALE', 'For Sale'),
        ('RENT', 'For Rent'),
    ]
    
    RENTAL_FREQUENCY_CHOICES = [
        ('MONTH', 'Per Month'),
        ('QUARTER', 'Per Quarter'),
        ('HALF_YEAR', 'Per Half Year'),
        ('YEAR', 'Per Year'),
    ]

    # --- Core Fields ---
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=255)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES) # Renamed from 'type' to avoid python keyword conflict
    location = models.CharField(max_length=255)
    colony = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    created_at = models.DateTimeField(auto_now_add=True)

    # --- The Split: Sale vs Rent ---
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES, default='SALE')
    
    # We use a single 'price' field for optimization. 
    # If Sale: This is Total Price. If Rent: This is Rent Amount.
    price = models.DecimalField(max_digits=12, decimal_places=2) 
    
    # Fields specific to Rentals (Nullable)
    rental_frequency = models.CharField(max_length=10, choices=RENTAL_FREQUENCY_CHOICES, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_purpose_display()})"


class PropertyImages(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='property_images/')
    
    def __str__(self):
        return f"Image for {self.property.title}"

# ==========================================
# 3. LEAD MODEL
# ==========================================
# Model to capture leads/inquiries for properties
class Lead(models.Model):
    property = models.ForeignKey('Property', on_delete=models.CASCADE, related_name='leads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='my_leads', blank=True, null=True)
    
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_enquiry = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Auto-fill details from owner if they are missing
        if self.user:
            if not self.name:
                self.name = getattr(self.user, 'full_name', '')
            if not self.phone:
                self.phone = getattr(self.user, 'phone', '')
            if not self.email:
                self.email = getattr(self.user, 'email', '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lead by {self.name} for {self.property.title}"