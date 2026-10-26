from contextlib import contextmanager
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.audit.context import audit_scope
from apps.audit.models import AuditEvent
from .models import Family, FamilyMembership, FamilyInvitation


@contextmanager
def locked_family(user, family_id, admin=False, write=False):
    """One lock order for membership changes and every family financial request."""
    with transaction.atomic(), audit_scope(user):
        try:
            family = Family.objects.select_for_update().get(pk=family_id)
            membership = FamilyMembership.objects.get(
                family=family, user=user, status="ACTIVE"
            )
        except (Family.DoesNotExist, FamilyMembership.DoesNotExist):
            raise NotFound()
        if admin and membership.role != "ADMIN":
            raise PermissionDenied("Esta operación requiere un administrador familiar.")
        if write and family.status != "ACTIVE":
            raise PermissionDenied("La familia está archivada; solo admite consultas.")
        yield family, membership


def event(user, family, instance, before=None):
    from apps.audit.context import current_actor
    from apps.audit.signals import normalized

    label = instance._meta.label_lower
    fields = {
        "families.family": ("name", "currency", "timezone", "status"),
        "families.familymembership": ("user_id", "role", "status"),
        # Email deliberately excluded from shared audit.
        "families.familyinvitation": ("status", "invited_user_id", "expires_at"),
    }[label]
    after = {field: normalized(getattr(instance, field)) for field in fields}
    before = before or {}
    AuditEvent.objects.create(
        family=family,
        actor=user,
        operation="UPDATE" if before else "CREATE",
        resource_type=label,
        resource_id=instance.pk,
        before=before,
        after=after,
        changed_fields=[k for k in after if before.get(k) != after[k]],
        correlation_id=current_actor.get()[1],
    )


def change_member(user, family_id, member_id, role=None, remove=False):
    with locked_family(user, family_id, write=True) as (family, actor):
        try:
            member = FamilyMembership.objects.get(
                pk=member_id, family=family, status="ACTIVE"
            )
        except FamilyMembership.DoesNotExist:
            raise NotFound()
        if actor.role != "ADMIN" and (not remove or member.user_id != user.pk):
            raise PermissionDenied()
        if not remove and role not in ("ADMIN", "MEMBER"):
            raise ValidationError({"role": "Rol inválido."})
        if (
            member.role == "ADMIN"
            and (remove or role == "MEMBER")
            and FamilyMembership.objects.filter(
                family=family, status="ACTIVE", role="ADMIN"
            ).count()
            == 1
        ):
            raise ValidationError("Debe permanecer al menos un administrador activo.")
        before = {
            "user_id": str(member.user_id),
            "role": member.role,
            "status": member.status,
        }
        if remove:
            member.status, member.removed_at = "REMOVED", timezone.now()
        else:
            member.role = role
        member.save()
        event(user, family, member, before)
        return member


def expire(invitation, user):
    if invitation.status == "PENDING" and invitation.expires_at <= timezone.now():
        invitation.status, invitation.responded_at = "EXPIRED", timezone.now()
        invitation.save()
        event(user, invitation.family, invitation, {"status": "PENDING"})


def respond(user, invitation_id, action):
    # Do not reveal an invitation to anyone other than its intended recipient.
    try:
        family_id = FamilyInvitation.objects.values_list("family_id", flat=True).get(
            pk=invitation_id, invited_user=user
        )
    except FamilyInvitation.DoesNotExist:
        raise NotFound()
    with transaction.atomic(), audit_scope(user):
        family = Family.objects.select_for_update().get(pk=family_id)
        invitation = FamilyInvitation.objects.get(pk=invitation_id, invited_user=user)
        expire(invitation, user)
        if invitation.status != "PENDING" or family.status != "ACTIVE":
            return invitation, False
        if action == "accept":
            member, created = FamilyMembership.objects.get_or_create(
                family=family, user=user, defaults={"role": "MEMBER"}
            )
            if not created and member.status == "REMOVED":
                before = {
                    "user_id": str(user.pk),
                    "role": member.role,
                    "status": member.status,
                }
                member.role, member.status, member.removed_at = "MEMBER", "ACTIVE", None
                member.save()
                event(user, family, member, before)
            elif created:
                event(user, family, member)
        invitation.status = "ACCEPTED" if action == "accept" else "REJECTED"
        invitation.responded_at = timezone.now()
        invitation.save()
        event(user, family, invitation, {"status": "PENDING"})
        return invitation, True
