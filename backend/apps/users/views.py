from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import CSRFSafeSessionAuthentication
from .serializers import ChangePasswordSerializer, LoginSerializer, RegisterSerializer, UserSerializer
from .throttles import AuthThrottle


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("password", "current_password", "new_password"), name="dispatch")
class AuthView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]


class CSRFView(AuthView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(AuthView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    rate_action = "register"

    @sensitive_variables()
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            raise ValidationError({"email": ["Ya existe una cuenta con este correo."]})
        # Registro no abre sesión: el usuario inicia sesión explícitamente.
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(AuthView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    rate_action = "login"

    @sensitive_variables()
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise AuthenticationFailed("Correo o contraseña incorrectos.")
        login(request, user)
        return Response({"user": UserSerializer(user).data, "csrfToken": get_token(request)})


class LogoutView(AuthView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(AuthView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ProfileView(AuthView):
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(AuthView):
    throttle_classes = [AuthThrottle]
    rate_action = "password"

    @sensitive_variables()
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        # Mantiene sesión actual; invalida otras sesiones al comprobar su hash.
        update_session_auth_hash(request, request.user)
        return Response({"detail": "Contraseña actualizada.", "csrfToken": get_token(request)})
