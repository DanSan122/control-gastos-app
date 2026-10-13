from uuid import UUID
from datetime import timezone
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from apps.core.finance import FinancePagination
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import AuditEvent
from .signals import FIELDS


class AuditSerializer(serializers.ModelSerializer):
    occurred_at = serializers.DateTimeField(
        default_timezone=timezone.utc, read_only=True
    )

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "actor",
            "operation",
            "resource_type",
            "resource_id",
            "occurred_at",
            "before",
            "after",
            "changed_fields",
            "correlation_id",
        ]
        read_only_fields = fields


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditSerializer
    pagination_class = FinancePagination
    authentication_classes = [CSRFSafeSessionAuthentication]
    http_method_names = ["get", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )
        response["Cache-Control"] = "private, no-store"
        return response

    def get_queryset(self):
        rows = AuditEvent.objects.filter(actor=self.request.user)
        params = self.request.query_params
        if params.get("resource_type"):
            if params["resource_type"] not in FIELDS:
                raise ValidationError({"resource_type": "Recurso inválido."})
            rows = rows.filter(resource_type=params["resource_type"])
        if params.get("resource_id"):
            try:
                identifier = UUID(params["resource_id"])
            except ValueError:
                raise ValidationError({"resource_id": "UUID inválido."})
            rows = rows.filter(resource_id=identifier)
        if params.get("operation"):
            if params["operation"] not in dict(
                AuditEvent._meta.get_field("operation").choices
            ):
                raise ValidationError({"operation": "Operación inválida."})
            rows = rows.filter(operation=params["operation"])
        return rows
