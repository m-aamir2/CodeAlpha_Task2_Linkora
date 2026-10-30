from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from config.blob_urls import is_user_blob_url
from .models import User, UserProfile

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", required=False, allow_blank=True)
    bio = serializers.CharField(source="profile.bio", required=False, allow_blank=True)
    location = serializers.CharField(source="profile.location", required=False, allow_blank=True)
    website = serializers.URLField(source="profile.website", required=False, allow_blank=True)
    avatar = serializers.ImageField(source="profile.avatar", required=False, allow_null=True, write_only=True)
    cover_image = serializers.ImageField(source="profile.cover_image", required=False, allow_null=True, write_only=True)
    avatar_blob_url = serializers.URLField(write_only=True, required=False, max_length=500)
    cover_blob_url = serializers.URLField(write_only=True, required=False, max_length=500)
    avatar_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    posts_count = serializers.IntegerField(read_only=True, default=0)
    followers_count = serializers.IntegerField(read_only=True, default=0)
    following_count = serializers.IntegerField(read_only=True, default=0)
    is_following = serializers.BooleanField(read_only=True, default=False)
    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "bio", "location", "website", "avatar", "cover_image", "avatar_blob_url", "cover_blob_url", "avatar_url", "cover_url", "created_at", "posts_count", "followers_count", "following_count", "is_following", "is_staff", "is_active"]
        read_only_fields = ["id", "username", "email", "created_at", "is_staff", "is_active"]
        extra_kwargs = {"avatar": {"write_only": True}, "cover_image": {"write_only": True}}
    def get_avatar_url(self, obj):
        request = self.context.get("request")
        avatar = getattr(getattr(obj, "profile", None), "avatar", None)
        return request.build_absolute_uri(avatar.url) if request and avatar else (avatar.url if avatar else None)
    def get_cover_url(self, obj):
        request = self.context.get("request")
        cover = getattr(getattr(obj, "profile", None), "cover_image", None)
        return request.build_absolute_uri(cover.url) if request and cover else (cover.url if cover else None)
    def validate_avatar_blob_url(self, value):
        request = self.context.get("request")
        if not request or not is_user_blob_url(value, request.user.pk):
            raise serializers.ValidationError("Choose a profile image uploaded to your Linkora storage.")
        return value
    def validate_cover_blob_url(self, value):
        request = self.context.get("request")
        if not request or not is_user_blob_url(value, request.user.pk):
            raise serializers.ValidationError("Choose a cover image uploaded to your Linkora storage.")
        return value
    def to_representation(self, instance):
        result = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if not viewer or not viewer.is_authenticated or (viewer.pk != instance.pk and not viewer.is_staff):
            result.pop("email", None)
            result.pop("is_active", None)
        return result
    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        avatar_blob_url = validated_data.pop("avatar_blob_url", None)
        cover_blob_url = validated_data.pop("cover_blob_url", None)
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        for field, value in profile_data.items():
            setattr(profile, field, value)
        if avatar_blob_url:
            profile.avatar = avatar_blob_url
        if cover_blob_url:
            profile.cover_image = cover_blob_url
        if profile_data or avatar_blob_url or cover_blob_url:
            profile.save()
        return instance

class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=120)
    password = serializers.CharField(write_only=True, validators=[password_validation.validate_password])
    password_confirm = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ["username", "full_name", "email", "password", "password_confirm"]
    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs
    def create(self, validated_data):
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name", "")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.profile.full_name = full_name
        user.profile.save(update_fields=["full_name", "updated_at"])
        return user

class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        return token
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data
