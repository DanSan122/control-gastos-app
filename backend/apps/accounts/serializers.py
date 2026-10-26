from apps.core.scope import scoped, scope_timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.core.finance import MoneyField, OwnedSerializer
from .models import Account


class AccountSerializer(OwnedSerializer):
    initial_balance = MoneyField(required=False)
    balance = serializers.SerializerMethodField()
    debt = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ["id", "name", "kind", "institution", "currency", "initial_balance", "created_at", "is_active", "balance", "debt"]
        read_only_fields = ["id", "created_at"]
        validators = []

    def validate(self, attrs):
        owner = self.context["request"].user
        name = attrs.get("name", getattr(self.instance, "name", ""))
        query = scoped(Account.objects, owner).filter(name__iexact=name)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
            if self.instance.outgoing.exists() or self.instance.incoming.exists():
                for field in ("initial_balance", "currency", "kind"):
                    if field in attrs and attrs[field] != getattr(self.instance, field):
                        raise ValidationError({field: "No se modifica después de registrar movimientos, incluso anulados."})
        if query.exists():
            raise ValidationError({"name": "Ya existe una cuenta con ese nombre."})
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        opening = attrs.get("initial_balance", getattr(self.instance, "initial_balance", 0))
        if kind == Account.Kind.CREDIT and opening > 0:
            raise ValidationError({"initial_balance": "Registra la deuda inicial con signo negativo, no el límite de crédito."})
        return attrs

    def get_balance(self, obj):
        from apps.transactions.services import account_balance
        balances = self.context.get("balances")
        value = balances[obj.id] if balances is not None else account_balance(obj)
        return format(value, ".2f")

    def get_debt(self, obj):
        from decimal import Decimal
        return format(max(Decimal("0"), -Decimal(self.get_balance(obj))) if obj.kind == "CREDIT" else Decimal("0"), ".2f")
