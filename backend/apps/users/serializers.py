from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class StrictInputMixin:
    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            allowed = {name for name, field in self.fields.items() if not field.read_only}
            unexpected = set(data.keys()) - allowed
            if unexpected:
                raise serializers.ValidationError({key: ["Campo no permitido."] for key in unexpected})
        return super().to_internal_value(data)


def validate_user_password(password, user):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": exc.messages})


class UserSerializer(StrictInputMixin, serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined", "is_active", "timezone", "currency"]
        read_only_fields = ["id", "email", "date_joined", "is_active"]


class RegisterSerializer(StrictInputMixin, serializers.ModelSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return email

    def validate(self, attrs):
        user = User(email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"])
        validate_user_password(attrs["password"], user)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(StrictInputMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class ChangePasswordSerializer(StrictInputMixin, serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": ["La contraseña actual no es correcta."]})
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": ["La nueva contraseña debe ser diferente."]})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages})
        return attrs
