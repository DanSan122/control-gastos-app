from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from apps.core.finance import MoneyField, OwnedSerializer, ReferenceField
from apps.transactions.serializers import TransactionSerializer
from .models import RecurringRule, RecurringExecution


def movement_payload(rule, occurred_at):
    return {
        "kind": rule.kind,
        "account": str(rule.source_account_id),
        "destination_account": (
            str(rule.destination_account_id)
            if rule.destination_account_id
            else None
        ),
        "amount": format(rule.amount, ".2f"),
        "currency": rule.currency,
        "area": str(rule.area_id) if rule.area_id else None,
        "category": str(rule.category_id) if rule.category_id else None,
        "subcategory": (
            str(rule.subcategory_id) if rule.subcategory_id else None
        ),
        "payment_method": rule.payment_method,
        "description": rule.name,
        "occurred_at": occurred_at.isoformat(),
    }


class RuleSerializer(OwnedSerializer):
    amount = MoneyField(min_value=Decimal("0.01"))
    source_account = ReferenceField()
    destination_account = ReferenceField(required=False, allow_null=True)
    area = ReferenceField(required=False, allow_null=True)
    category = ReferenceField(required=False, allow_null=True)
    subcategory = ReferenceField(required=False, allow_null=True)
    interval = serializers.IntegerField(min_value=1, max_value=1000, default=1)
    source_name = serializers.CharField(
        source="source_account.name", read_only=True
    )
    destination_name = serializers.CharField(
        source="destination_account.name", read_only=True, default=None
    )
    calendar_locked = serializers.SerializerMethodField()

    class Meta:
        model = RecurringRule
        fields = [
            "id",
            "name",
            "kind",
            "amount",
            "currency",
            "source_account",
            "destination_account",
            "area",
            "category",
            "subcategory",
            "payment_method",
            "frequency",
            "interval",
            "start_date",
            "end_date",
            "next_due_date",
            "timezone",
            "execution_mode",
            "status",
            "created_at",
            "updated_at",
            "source_name",
            "destination_name",
            "calendar_locked",
        ]
        read_only_fields = [
            "id",
            "status",
            "next_due_date",
            "timezone",
            "created_at",
            "updated_at",
            "source_name",
            "destination_name",
            "calendar_locked",
        ]
        validators = []

    def get_calendar_locked(self, obj):
        return getattr(obj, "history_started", False)

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.status in ("CANCELLED", "COMPLETED"):
            raise serializers.ValidationError(
                "Esta regla es terminal; crea una regla nueva."
            )
        value = lambda name, default=None: attrs.get(
            name, getattr(instance, name, default)
        )
        if instance:
            for field in ("kind", "start_date"):
                if field in attrs and attrs[field] != getattr(instance, field):
                    raise serializers.ValidationError(
                        {field: "No cambia tras crear la primera ocurrencia."}
                    )
            if instance.executions.exclude(status="PENDING").exists():
                for field in ("frequency", "interval"):
                    if field in attrs and attrs[field] != getattr(
                        instance, field
                    ):
                        raise serializers.ValidationError(
                            {
                                field: "El calendario tiene historial; crea otra regla."
                            }
                        )
        start, end = value("start_date"), value("end_date")
        if not 1900 <= start.year <= 9998 or (
            end and (end < start or end.year > 9998)
        ):
            raise serializers.ValidationError(
                {
                    "end_date": "Fechas entre 1900 y 9998, fin no anterior al inicio."
                }
            )
        if instance and end and end < instance.next_due_date:
            raise serializers.ValidationError(
                {
                    "end_date": "No recortes una ocurrencia pendiente; cancela la regla."
                }
            )
        payload = {
            "kind": value("kind"),
            "amount": format(value("amount"), ".2f"),
            "currency": value("currency", "PEN"),
            "occurred_at": timezone.now().isoformat(),
            "payment_method": value("payment_method", ""),
        }
        for rule_field, tx_field in (
            ("source_account", "account"),
            ("destination_account", "destination_account"),
            ("area", "area"),
            ("category", "category"),
            ("subcategory", "subcategory"),
        ):
            raw = attrs.get(
                rule_field, getattr(instance, f"{rule_field}_id", None)
            )
            payload[tx_field] = str(raw) if raw is not None else None
        financial = TransactionSerializer(data=payload, context=self.context)
        financial.is_valid(raise_exception=True)
        for rule_field, tx_field in (
            ("source_account", "account"),
            ("destination_account", "destination_account"),
            ("area", "area"),
            ("category", "category"),
            ("subcategory", "subcategory"),
        ):
            attrs[rule_field] = financial.validated_data[tx_field]
        return attrs


class ExecutionSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    kind = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    execution_mode = serializers.CharField(
        source="rule.execution_mode", read_only=True
    )
    rule_status = serializers.CharField(source="rule.status", read_only=True)
    timezone = serializers.CharField(source="rule.timezone", read_only=True)

    def get_kind(self, obj):
        return obj.transaction.kind if obj.transaction_id else obj.rule.kind

    def get_amount(self, obj):
        return format(
            obj.transaction.amount if obj.transaction_id else obj.rule.amount,
            ".2f",
        )

    class Meta:
        model = RecurringExecution
        fields = [
            "id",
            "rule",
            "rule_name",
            "scheduled_date",
            "status",
            "transaction",
            "attempted_at",
            "executed_at",
            "error_code",
            "created_at",
            "kind",
            "amount",
            "execution_mode",
            "rule_status",
            "timezone",
        ]
        read_only_fields = fields
