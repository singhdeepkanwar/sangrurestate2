from django.contrib import admin
from .models import CustomUser, Property, PropertyImages, Lead
# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Property)
admin.site.register(PropertyImages)
admin.site.register(Lead)