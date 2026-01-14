from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('The Phone Number must be set')
        
        # Normalize email if provided
        if extra_fields.get('email'):
            extra_fields['email'] = self.normalize_email(extra_fields['email'])

        user = self.model(phone=phone, **extra_fields)
        
        # We set an unusable password for regular users because they login via OTP
        # But if a password is provided (e.g. for admins), we set it.
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.save()
        return user

    def create_superuser(self, phone, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)