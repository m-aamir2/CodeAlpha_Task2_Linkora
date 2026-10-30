from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets
    list_display = ("username", "email", "is_staff", "created_at")

class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

admin.site.register(UserProfile)
