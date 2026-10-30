from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.conf import settings

def validate_upload(file):
    if file.size > settings.MAX_UPLOAD_SIZE:
        from django.core.exceptions import ValidationError
        raise ValidationError("Images must be 8 MB or smaller.")

class User(AbstractUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            UserProfile.objects.get_or_create(user=self)

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=120, blank=True)
    bio = models.CharField(max_length=300, blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    avatar = models.ImageField(upload_to="profiles/avatars/", blank=True, null=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_upload])
    cover_image = models.ImageField(upload_to="profiles/covers/", blank=True, null=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_upload])
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Profile for {self.user.username}"
