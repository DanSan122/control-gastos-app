from apps.core.scope import scoped, scope_timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.core.finance import OwnedSerializer, ReferenceField
from .models import Area, Category, Subcategory


class ClassificationSerializer(OwnedSerializer):
    def validate(self, attrs):
        model = self.Meta.model
        owner = self.context["request"].user
        query = scoped(model.objects, owner).filter(name__iexact=attrs.get("name", getattr(self.instance, "name", "")))
        relation = "area" if model == Category else "category" if model == Subcategory else None
        if relation:
            parent_id = attrs.get(relation, getattr(self.instance, f"{relation}_id", None))
            parent = self.owned_relation(Area if relation == "area" else Category, parent_id, relation)
            if not parent.is_active and (not self.instance or parent.pk != getattr(self.instance, f"{relation}_id")):
                raise ValidationError({relation: "El padre está desactivado."})
            query = query.filter(**{relation: parent})
            attrs[relation] = parent
            if self.instance and self.instance.movements.exists():
                if parent.pk != getattr(self.instance, f"{relation}_id"):
                    raise ValidationError({relation: "No se cambia la jerarquía de una clasificación con historial."})
                if model == Category and attrs.get("kind", self.instance.kind) != self.instance.kind:
                    raise ValidationError({"kind": "No se cambia el tipo de una categoría con historial."})
        if model == Category:
            query = query.filter(kind=attrs.get("kind", getattr(self.instance, "kind", None)))
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError({"name": "Ya existe una clasificación con ese nombre en este ámbito."})
        return attrs


class AreaSerializer(ClassificationSerializer):
    class Meta:
        model = Area
        fields = ["id", "name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        validators = []


class CategorySerializer(ClassificationSerializer):
    area = ReferenceField()

    class Meta:
        model = Category
        fields = ["id", "name", "area", "kind", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        validators = []


class SubcategorySerializer(ClassificationSerializer):
    category = ReferenceField()

    class Meta:
        model = Subcategory
        fields = ["id", "name", "category", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        validators = []
