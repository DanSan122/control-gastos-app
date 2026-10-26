from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework import serializers
from apps.users.serializers import StrictInputMixin
from .models import Family, FamilyMembership, FamilyInvitation


class FamilySerializer(StrictInputMixin, serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = [
            "id",
            "name",
            "description",
            "currency",
            "timezone",
            "status",
            "created_at",
            "updated_at",
            "role",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "role"]

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Zona IANA inválida.")
        return value

    def get_role(self, obj):
        return (
            obj.memberships.filter(user=self.context["request"].user, status="ACTIVE")
            .values_list("role", flat=True)
            .first()
        )


class MembershipSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = FamilyMembership
        fields = ["id", "user", "name", "role", "status", "joined_at", "removed_at"]

    def get_name(self, obj):
        return obj.user.get_full_name() or "Integrante"


class InvitationSerializer(serializers.ModelSerializer):
    family_name = serializers.CharField(source="family.name", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = FamilyInvitation
        fields = [
            "id",
            "family",
            "family_name",
            "invited_email",
            "status",
            "expires_at",
            "created_at",
            "responded_at",
        ]

    def get_status(self, obj):
        from django.utils import timezone

        return (
            "EXPIRED"
            if obj.status == "PENDING" and obj.expires_at <= timezone.now()
            else obj.status
        )
