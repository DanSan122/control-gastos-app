from datetime import timedelta
from functools import wraps
import hashlib
import hmac
import math
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.audit.context import audit_scope
from apps.core.finance import FinancePagination
from apps.core.scope import current_family
from apps.reports.throttles import ReportThrottle
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import Family, FamilyMembership, FamilyInvitation
from .serializers import FamilySerializer, MembershipSerializer, InvitationSerializer
from .services import locked_family, change_member, respond, expire, event


class FamilyThrottle(ReportThrottle):
    # Reuse persistent atomic counters with a separate namespace, 30 writes/hour.
    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        from apps.users.models import AuthRateLimit
        from django.conf import settings

        key = hmac.new(
            settings.SECRET_KEY.encode(),
            f"families:{request.user.pk}".encode(),
            hashlib.sha256,
        ).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            AuthRateLimit.objects.get_or_create(
                key=key, defaults={"expires_at": now + timedelta(hours=1)}
            )
            counter = AuthRateLimit.objects.select_for_update().get(pk=key)
            if counter.expires_at <= now:
                counter.attempts, counter.expires_at = 0, now + timedelta(hours=1)
            self.retry_after = max(
                1, math.ceil((counter.expires_at - now).total_seconds())
            )
            if counter.attempts >= 30:
                return False
            counter.attempts += 1
            counter.save(update_fields=["attempts", "expires_at"])
        return True


class FamilyViewSet(viewsets.ModelViewSet):
    lookup_value_regex = (
        "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )
    serializer_class = FamilySerializer
    authentication_classes = [CSRFSafeSessionAuthentication]
    throttle_classes = [FamilyThrottle]
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Family.objects.filter(
            memberships__user=self.request.user, memberships__status="ACTIVE"
        ).order_by("name", "id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("status", "ACTIVE") != "ACTIVE":
            raise ValidationError("Crea una familia activa.")
        with transaction.atomic(), audit_scope(request.user):
            family = serializer.save(created_by=request.user)
            member = FamilyMembership.objects.create(
                family=family, user=request.user, role="ADMIN"
            )
            event(request.user, family, family)
            event(request.user, family, member)
            return Response(self.get_serializer(family).data, status=201)

    def partial_update(self, request, pk=None):
        with locked_family(request.user, pk, admin=True) as (family, _):
            before = {
                "name": family.name,
                "currency": family.currency,
                "timezone": family.timezone,
                "status": family.status,
            }
            serializer = self.get_serializer(family, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            event(request.user, family, family, before)
            return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        if request.data:
            raise ValidationError("No se admiten campos adicionales.")
        with locked_family(request.user, pk) as (_, member):
            change_member(request.user, pk, member.pk, remove=True)
        return Response(status=204)


class MembersView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]
    throttle_classes = [FamilyThrottle]

    def get(self, request, family_id, membership_id=None):
        if membership_id:
            from rest_framework.exceptions import MethodNotAllowed

            raise MethodNotAllowed("GET")
        with locked_family(request.user, family_id) as (family, _):
            rows = (
                FamilyMembership.objects.filter(family=family)
                .select_related("user")
                .order_by("joined_at", "id")
            )
            pager = FinancePagination()
            return pager.get_paginated_response(
                MembershipSerializer(
                    pager.paginate_queryset(rows, request), many=True
                ).data
            )

    def patch(self, request, family_id, membership_id):
        if not isinstance(request.data, dict) or set(request.data) != {"role"}:
            raise ValidationError("Envía únicamente role.")
        return Response(
            MembershipSerializer(
                change_member(
                    request.user, family_id, membership_id, role=request.data["role"]
                )
            ).data
        )

    def delete(self, request, family_id, membership_id):
        with locked_family(request.user, family_id, admin=True, write=True):
            change_member(request.user, family_id, membership_id, remove=True)
        return Response(status=204)


class InvitationsView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]
    throttle_classes = [FamilyThrottle]

    def get(self, request, family_id=None, invitation_id=None, operation=None):
        if operation:
            from rest_framework.exceptions import MethodNotAllowed

            raise MethodNotAllowed("GET")
        if family_id:
            with locked_family(request.user, family_id, admin=True):
                return self.list_rows(
                    request, FamilyInvitation.objects.filter(family_id=family_id)
                )
        return self.list_rows(
            request, FamilyInvitation.objects.filter(invited_user=request.user)
        )

    def list_rows(self, request, rows):
        pager = FinancePagination()
        rows = rows.select_related("family").order_by("-created_at", "id")
        return pager.get_paginated_response(
            InvitationSerializer(pager.paginate_queryset(rows, request), many=True).data
        )

    def post(self, request, family_id=None, invitation_id=None, operation=None):
        if operation and operation not in ("accept", "reject", "revoke"):
            raise NotFound()
        if family_id and operation in ("accept", "reject"):
            raise NotFound()
        if operation in ("accept", "reject"):
            if request.data:
                raise ValidationError("No se admiten campos adicionales.")
            invitation, success = respond(request.user, invitation_id, operation)
            return Response(
                InvitationSerializer(invitation).data, status=200 if success else 409
            )
        with locked_family(request.user, family_id, admin=True, write=True) as (
            family,
            _,
        ):
            if operation == "revoke":
                if request.data:
                    raise ValidationError("No se admiten campos adicionales.")
                invitation = get_object_or_404(
                    FamilyInvitation, pk=invitation_id, family=family
                )
                expire(invitation, request.user)
                if invitation.status != "PENDING":
                    return Response(InvitationSerializer(invitation).data, status=409)
                invitation.status, invitation.responded_at = "REVOKED", timezone.now()
                invitation.save()
                event(request.user, family, invitation, {"status": "PENDING"})
                return Response(InvitationSerializer(invitation).data)
            from rest_framework import serializers

            class Input(serializers.Serializer):
                email = serializers.EmailField()

            if not isinstance(request.data, dict) or set(request.data) != {"email"}:
                raise ValidationError("Envía únicamente email.")
            data = Input(data=request.data)
            data.is_valid(raise_exception=True)
            email = get_user_model().objects.normalize_email(
                data.validated_data["email"]
            )
            recipient = (
                get_user_model().objects.filter(email=email, is_active=True).first()
            )
            # Same response for unknown, existing member, duplicate and successful invite.
            # Do not create invitations or expose user IDs for nonexistent accounts.
            if (
                recipient
                and not FamilyMembership.objects.filter(
                    family=family, user=recipient, status="ACTIVE"
                ).exists()
            ):
                for previous in FamilyInvitation.objects.filter(
                    family=family, invited_email=email, status="PENDING"
                ):
                    expire(previous, request.user)
                if not FamilyInvitation.objects.filter(
                    family=family, invited_email=email, status="PENDING"
                ).exists():
                    invitation = FamilyInvitation.objects.create(
                        family=family,
                        invited_user=recipient,
                        invited_email=email,
                        invited_by=request.user,
                        expires_at=timezone.now() + timedelta(days=7),
                    )
                    event(request.user, family, invitation)
            return Response(
                {
                    "detail": "Solicitud procesada. Si corresponde, el usuario recibirá la invitación dentro de la aplicación."
                },
                status=202,
            )


def family_finance_view(view, *, movements=False):
    """Explicit URL scope + authorization, held until the response is materialized."""

    @wraps(view)
    def wrapped(request, family_id, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"detail": "Autenticación requerida."}, status=403)
        try:
            write = request.method not in ("GET", "HEAD", "OPTIONS")
            with locked_family(
                request.user, family_id, admin=write and not movements, write=write
            ) as (family, member):
                token = current_family.set(family)
                try:
                    if movements and write and kwargs.get("pk"):
                        from apps.transactions.models import Transaction

                        movement = Transaction.objects.filter(
                            pk=kwargs["pk"], family=family
                        ).first()
                        if not movement:
                            raise NotFound()
                        if (
                            member.role != "ADMIN"
                            and movement.owner_id != request.user.pk
                        ):
                            raise PermissionDenied(
                                "Solo puedes gestionar movimientos registrados por ti."
                            )
                    response = view(request, **kwargs)
                    if hasattr(response, "render"):
                        response.render()
                    response["Cache-Control"] = "private, no-store"
                    return response
                finally:
                    current_family.reset(token)
        except APIException as exc:
            return JsonResponse(
                {"detail": exc.detail}, status=exc.status_code, safe=False
            )

    return wrapped
