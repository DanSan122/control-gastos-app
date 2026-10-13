from uuid import UUID
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.core.finance import OwnedViewSet, owner_lock
from .models import Budget
from .serializers import BudgetSerializer
from .services import progress_for


class BudgetViewSet(OwnedViewSet):
    queryset = Budget.objects.select_related("area", "category__area")
    serializer_class = BudgetSerializer

    def get_queryset(self):
        rows = self.queryset.filter(owner=self.request.user)
        params = self.request.query_params
        for field, minimum, maximum in (("year", 1900, 9998), ("month", 1, 12)):
            if field in params:
                try:
                    value = int(params[field])
                    if not minimum <= value <= maximum:
                        raise ValueError
                except ValueError:
                    raise ValidationError({field: "Valor fuera de rango."})
                rows = rows.filter(**{field: value})
        for field in ("area", "category"):
            if field in params:
                try:
                    UUID(params[field])
                except ValueError:
                    raise ValidationError({field: "UUID inválido."})
                rows = rows.filter(**{f"{field}_id": params[field]})
        if "active" in params:
            if params["active"] not in ("true", "false"):
                raise ValidationError({"active": "Usa true o false."})
            rows = rows.filter(is_active=params["active"] == "true")
        ordering = params.get("ordering", "-year")
        if ordering.lstrip("-") not in ("year", "month", "created_at", "limit_amount"):
            raise ValidationError({"ordering": "Ordenamiento inválido."})
        return rows.order_by(ordering, "-month", "id")

    def list(self, request, *args, **kwargs):
        with owner_lock(request.user):
            page = self.paginate_queryset(self.get_queryset())
            context = {**self.get_serializer_context(), "progress": progress_for(page, request.user)}
            return self.get_paginated_response(self.get_serializer(page, many=True, context=context).data)

    def retrieve(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        with owner_lock(request.user):
            budget = self.get_object()
            return Response(progress_for([budget], request.user)[budget.id])

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
