from uuid import uuid4
from django.conf import settings
from django.db import models
from django.db.models import Q


class Family(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default="PEN", choices=[("PEN", "PEN")])
    timezone = models.CharField(max_length=64, default="America/Lima")
    status = models.CharField(
        max_length=8,
        default="ACTIVE",
        choices=[("ACTIVE", "Activa"), ("ARCHIVED", "Archivada")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(currency="PEN"), name="family_pen"),
            models.CheckConstraint(
                condition=Q(status__in=["ACTIVE", "ARCHIVED"]),
                name="family_status_valid",
            ),
        ]


class FamilyMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    family = models.ForeignKey(
        Family, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(
        max_length=6,
        default="MEMBER",
        choices=[("ADMIN", "Administrador"), ("MEMBER", "Integrante")],
    )
    status = models.CharField(
        max_length=7,
        default="ACTIVE",
        choices=[("ACTIVE", "Activo"), ("REMOVED", "Retirado")],
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "user"], name="family_member_unique"
            ),
            models.CheckConstraint(
                condition=Q(role__in=["ADMIN", "MEMBER"]), name="membership_role_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="ACTIVE", removed_at__isnull=True)
                    | Q(status="REMOVED", removed_at__isnull=False)
                ),
                name="membership_state",
            ),
        ]
        indexes = [models.Index(fields=["user", "status", "family"])]


class FamilyInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    family = models.ForeignKey(
        Family, on_delete=models.PROTECT, related_name="invitations"
    )
    invited_email = models.EmailField()
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="family_invitations",
        null=True,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_family_invitations",
    )
    status = models.CharField(
        max_length=8,
        default="PENDING",
        choices=[
            (s, s) for s in ("PENDING", "ACCEPTED", "REJECTED", "EXPIRED", "REVOKED")
        ],
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "invited_email"],
                condition=Q(status="PENDING"),
                name="family_pending_invite_unique",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["PENDING", "ACCEPTED", "REJECTED", "EXPIRED", "REVOKED"]
                ),
                name="invitation_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["invited_user", "status"])]
