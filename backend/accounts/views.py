from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"user": UserSerializer(user, context={"request": request}).data}, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

class LogoutView(APIView):
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except Exception:
            return Response({"detail": "A valid refresh token is required."}, status=400)
        return Response(status=204)

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            send_mail("Reset your Linkora password", f"Use this reset code in the app: {uid}:{token}", None, [user.email], fail_silently=True)
            if settings.DEBUG:
                return Response({"detail": "If the account exists, reset instructions were sent.", "development_token": f"{uid}:{token}"})
        return Response({"detail": "If the account exists, reset instructions were sent."})

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        try:
            uid, token = request.data.get("token", "").split(":", 1)
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except Exception:
            return Response({"detail": "Invalid or expired reset token."}, status=400)
        password = request.data.get("password", "")
        from django.contrib.auth.password_validation import validate_password
        from rest_framework.exceptions import ValidationError
        try:
            validate_password(password, user)
        except ValidationError as exc:
            return Response({"password": exc.detail}, status=400)
        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired reset token."}, status=400)
        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})

class ChangePasswordView(APIView):
    def post(self, request):
        if not request.user.check_password(request.data.get("current_password", "")):
            return Response({"current_password": ["Current password is incorrect."]}, status=400)
        password = request.data.get("new_password", "")
        from django.contrib.auth.password_validation import validate_password
        from rest_framework.exceptions import ValidationError
        try:
            validate_password(password, request.user)
        except ValidationError as exc:
            return Response({"new_password": exc.detail}, status=400)
        request.user.set_password(password)
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})
