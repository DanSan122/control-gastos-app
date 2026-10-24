from datetime import timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
from django.db.models import Exists, OuterRef, Sum, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.finance import FinancePagination, owner_lock
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import RecurringRule, RecurringExecution
from .serializers import RuleSerializer, ExecutionSerializer
from .services import prepare_next, execute


def filter_choice(query, params, field, model):
    if params.get(field):
        if params[field] not in dict(model._meta.get_field(field).choices):
            raise ValidationError({field: "Valor inválido."})
        query = query.filter(**{field: params[field]})
    return query


class RuleViewSet(viewsets.ModelViewSet):
    serializer_class = RuleSerializer
    authentication_classes = [CSRFSafeSessionAuthentication]
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    def get_queryset(self):
        rows = (
            RecurringRule.objects.filter(owner=self.request.user)
            .select_related("source_account", "destination_account", "area", "category", "subcategory")
            .annotate(
                history_started=Exists(
                    RecurringExecution.objects.filter(
                        rule_id=OuterRef("pk")
                    ).exclude(status="PENDING")
                )
            )
        )
        if self.action == "list":
            for field in ("status", "kind", "frequency", "execution_mode"):
                rows = filter_choice(
                    rows, self.request.query_params, field, RecurringRule
                )
        return rows.order_by("next_due_date", "id")

    def create(self, request, *args, **kwargs):
        with owner_lock(request.user):
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            rule = serializer.save(
                owner=request.user,
                timezone=request.user.timezone,
                next_due_date=serializer.validated_data["start_date"],
            )
            prepare_next(rule)
            return Response(serializer.data, status=201)

    def partial_update(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        with owner_lock(request.user):
            rule = self.get_object()
            if rule.status != "CANCELLED":
                rule.status, rule.next_due_date = "CANCELLED", None
                rule.save(
                    update_fields=["status", "next_due_date", "updated_at"]
                )
            return Response(status=204)

    def transition(self, request, target):
        if not isinstance(request.data, dict) or request.data:
            raise ValidationError("Esta acción no admite campos adicionales.")
        with owner_lock(request.user):
            rule = self.get_object()
            if rule.status in ("CANCELLED", "COMPLETED"):
                raise ValidationError("Una regla terminal no se reactiva.")
            if target == "ACTIVE":
                validation = RuleSerializer(
                    rule, data={}, partial=True, context={"request": request}
                )
                validation.is_valid(raise_exception=True)
            rule.status = target
            rule.save(update_fields=["status", "updated_at"])
            return Response(self.get_serializer(rule).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self.transition(request, "PAUSED")

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self.transition(request, "ACTIVE")


class ExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExecutionSerializer
    authentication_classes = [CSRFSafeSessionAuthentication]
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "head", "options"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    def get_queryset(self):
        rows = RecurringExecution.objects.filter(
            rule__owner=self.request.user
        ).select_related("rule", "transaction")
        if self.action == "list":
            rows = filter_choice(
                rows, self.request.query_params, "status", RecurringExecution
            )
            if self.request.query_params.get("rule"):
                try:
                    identifier = UUID(self.request.query_params["rule"])
                except ValueError:
                    raise ValidationError({"rule": "UUID inválido."})
                rows = rows.filter(rule_id=identifier)
        return rows.order_by("-scheduled_date", "-id")

    def act(self, request, skip=False):
        if not isinstance(request.data, dict) or request.data:
            raise ValidationError("Esta acción no admite campos adicionales.")
        execution = self.get_object()
        result = execute(request.user, execution.pk, skip=skip)
        data = self.get_serializer(result).data
        if result.status == "FAILED":
            return Response(
                {
                    **data,
                    "detail": f"No se registró el movimiento: {result.error_code}. Puedes corregir la regla y reintentar.",
                },
                status=422,
            )
        return Response(data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self.act(request)

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        return self.act(request, skip=True)


class UpcomingView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", "30"))
            if not 1 <= days <= 366:
                raise ValueError
        except ValueError:
            raise ValidationError({"days": "Usa de 1 a 366 días."})
        until = timezone.now().astimezone(
            ZoneInfo(request.user.timezone)
        ).date() + timedelta(days=days)
        with owner_lock(request.user):
            rows = (
                RecurringExecution.objects.filter(
                    rule__owner=request.user,
                    rule__status="ACTIVE",
                    status__in=["PENDING", "FAILED"],
                    scheduled_date__lte=until,
                )
                .select_related("rule", "transaction")
                .order_by("scheduled_date", "id")
            )
            totals = rows.aggregate(
                **{
                    kind.lower(): Sum(
                        "rule__amount", filter=Q(rule__kind=kind)
                    )
                    for kind in ("INCOME", "EXPENSE", "TRANSFER")
                }
            )
            pagination = FinancePagination()
            page = pagination.paginate_queryset(rows, request, view=self)
            response = pagination.get_paginated_response(
                ExecutionSerializer(page, many=True).data
            )
            response.data["scheduled_totals"] = {
                key: format(value or Decimal("0"), ".2f")
                for key, value in totals.items()
            }
            return response
