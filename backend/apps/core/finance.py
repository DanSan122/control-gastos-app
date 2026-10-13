from contextlib import contextmanager
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.users.authentication import CSRFSafeSessionAuthentication
from apps.users.serializers import StrictInputMixin


class MoneyField(serializers.DecimalField):
    def __init__(self, **kwargs):
        super().__init__(max_digits=18, decimal_places=2, **kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, (str, Decimal)):
            raise ValidationError("Envía el importe como cadena decimal, nunca como número JSON.")
        return super().to_internal_value(data)


class ReferenceField(serializers.UUIDField):
    def to_representation(self, value):
        return str(getattr(value, "pk", value))


class FinancePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


@contextmanager
def owner_lock(user):
    # Todas las escrituras financieras de un propietario usan el mismo orden de bloqueo.
    from apps.audit.context import audit_scope
    with transaction.atomic(), audit_scope(user):
        get_user_model().objects.select_for_update().get(pk=user.pk)
        yield


class OwnedSerializer(StrictInputMixin, serializers.ModelSerializer):
    def owned_relation(self, model, value, field):
        try:
            item = model.objects.get(pk=value, owner=self.context["request"].user)
        except model.DoesNotExist:
            raise ValidationError({field: "El recurso no existe o no te pertenece."})
        return item


class OwnedViewSet(viewsets.ModelViewSet):
    authentication_classes = [CSRFSafeSessionAuthentication]
    pagination_class = FinancePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        query = self.queryset.filter(owner=self.request.user)
        active = self.request.query_params.get("active")
        if active is not None:
            if active not in ("true", "false"):
                raise ValidationError({"active": "Usa true o false."})
            query = query.filter(is_active=active == "true")
        for field in getattr(self, "relation_filters", []):
            value = self.request.query_params.get(field)
            if value:
                try:
                    from uuid import UUID
                    UUID(value)
                except ValueError:
                    raise ValidationError({field: "UUID inválido."})
                query = query.filter(**{f"{field}_id": value})
        kind = self.request.query_params.get("kind")
        if kind:
            if "kind" not in {field.name for field in self.queryset.model._meta.fields}:
                raise ValidationError({"kind": "Este recurso no tiene filtro de tipo."})
            if kind not in dict(self.queryset.model._meta.get_field("kind").choices):
                raise ValidationError({"kind": "Tipo inválido."})
            query = query.filter(kind=kind)
        search = self.request.query_params.get("search")
        if search:
            query = query.filter(name__icontains=search)
        ordering = self.request.query_params.get("ordering", "name")
        if ordering.lstrip("-") not in ("name", "created_at"):
            raise ValidationError({"ordering": "Usa name o created_at, con - para descendente."})
        return query.order_by(ordering, "id")

    def create(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        with owner_lock(request.user):
            return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
