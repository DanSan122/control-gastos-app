from apps.core.scope import scoped, scope_timezone
from decimal import Decimal
from rest_framework import serializers
from apps.categories.models import Area, Category
from apps.core.finance import MoneyField, OwnedSerializer, ReferenceField
from .models import Budget
from .services import progress_for


class BudgetSerializer(OwnedSerializer):
    area = ReferenceField(required=False, allow_null=True)
    category = ReferenceField(required=False, allow_null=True)
    limit_amount = MoneyField(min_value=Decimal("0.01"))
    year = serializers.IntegerField(min_value=1900, max_value=9998)
    month = serializers.IntegerField(min_value=1, max_value=12)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = ["id", "area", "category", "limit_amount", "currency", "year", "month", "is_active", "created_at", "updated_at", "progress"]
        read_only_fields = ["id", "created_at", "updated_at", "progress"]
        validators = []

    def validate(self, attrs):
        for field, model in (("area", Area), ("category", Category)):
            if attrs.get(field) is not None:
                item = self.owned_relation(model, attrs[field], field)
                changed = not self.instance or getattr(self.instance, f"{field}_id") != item.pk
                if changed and (not item.is_active or (field == "category" and not item.area.is_active)):
                    raise serializers.ValidationError({field: "Selecciona una clasificación activa."})
                if field == "category" and item.kind != "EXPENSE":
                    raise serializers.ValidationError({field: "Solo categorías de gasto."})
                attrs[field] = item
        value = lambda key, default=None: attrs.get(key, getattr(self.instance, key, default))
        area, category = value("area"), value("category")
        if bool(area) == bool(category):
            raise serializers.ValidationError("Selecciona área o categoría, exclusivamente una.")
        duplicate = scoped(Budget.objects, self.context["request"].user).filter(area=area, category=category, year=value("year"), month=value("month"), currency=value("currency", "PEN"))
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("Ya existe ese presupuesto; edítalo o reactívalo.")
        return attrs

    def get_progress(self, obj):
        values = self.context.get("progress")
        if values is None:
            values = progress_for([obj], self.context["request"].user)
        return values[obj.id]
