import re
from decimal import Decimal
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Account
from apps.categories.models import Area, Category, Subcategory
from apps.core.finance import MoneyField, OwnedSerializer, ReferenceField
from .models import Transaction


class AwareDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else None
        except (ValueError, OverflowError):
            parsed = None
        if parsed is None or not is_aware(parsed):
            raise ValidationError("Incluye zona horaria en ISO 8601 (por ejemplo, -05:00 o Z).")
        return super().to_internal_value(value)


class TransactionSerializer(OwnedSerializer):
    amount = MoneyField(min_value=Decimal("0.01"))
    account = ReferenceField()
    destination_account = ReferenceField(required=False, allow_null=True)
    area = ReferenceField(required=False, allow_null=True)
    category = ReferenceField(required=False, allow_null=True)
    subcategory = ReferenceField(required=False, allow_null=True)
    occurred_at = AwareDateTimeField()
    account_name = serializers.CharField(source="account.name", read_only=True)
    destination_name = serializers.CharField(source="destination_account.name", read_only=True, default=None)
    area_name = serializers.CharField(source="area.name", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = ["id", "account", "account_name", "destination_account", "destination_name", "kind", "amount", "currency", "area", "area_name", "category", "category_name", "subcategory", "subcategory_name", "description", "occurred_at", "created_at", "updated_at", "payment_method", "reference", "status"]
        read_only_fields = ["id", "created_at", "updated_at", "status"]
        validators = []

    def validate_occurred_at(self, value):
        from django.utils import timezone
        if value > timezone.now():
            raise ValidationError("No se admiten movimientos futuros; no hay programación en esta fase.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.status == "VOID":
            raise ValidationError("Un movimiento anulado es inmutable.")
        kind = attrs.get("kind", getattr(instance, "kind", None))
        if instance and kind != instance.kind:
            raise ValidationError({"kind": "No se cambia el tipo; anula y registra otro movimiento."})
        for field, model in [("account", Account), ("destination_account", Account), ("area", Area), ("category", Category), ("subcategory", Subcategory)]:
            value = attrs.get(field, getattr(instance, f"{field}_id", None))
            if value is not None:
                item = self.owned_relation(model, value, field)
                # Se pueden conservar relaciones inactivas al corregir descripciones/importe,
                # pero no agregar movimientos nuevos ni cambiar hacia relaciones inactivas.
                if not item.is_active and (not instance or value != getattr(instance, f"{field}_id", None)):
                    raise ValidationError({field: "Este recurso está desactivado."})
                attrs[field] = item
            else:
                attrs[field] = None
        account = attrs["account"]
        currency = attrs.get("currency", getattr(instance, "currency", "PEN"))
        if account.currency != currency:
            raise ValidationError({"currency": "Debe coincidir con la moneda de la cuenta."})
        if kind == "TRANSFER":
            destination = attrs["destination_account"]
            if destination is None or destination.pk == account.pk:
                raise ValidationError({"destination_account": "Selecciona otra cuenta propia."})
            if destination.currency != currency:
                raise ValidationError({"currency": "No hay conversión entre monedas en esta fase."})
            if any(attrs[field] is not None for field in ("area", "category", "subcategory")):
                raise ValidationError("Una transferencia no lleva clasificaciones de ingreso/gasto.")
        else:
            area, category, subcategory = attrs["area"], attrs["category"], attrs["subcategory"]
            if not area or not category or category.area_id != area.pk or category.kind != kind:
                raise ValidationError({"category": "Selecciona una categoría del área y tipo correctos."})
            if subcategory and subcategory.category_id != category.pk:
                raise ValidationError({"subcategory": "No pertenece a la categoría."})
            if attrs["destination_account"] is not None:
                raise ValidationError({"destination_account": "Solo corresponde a transferencias."})
        return attrs
