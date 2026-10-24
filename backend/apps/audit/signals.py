from datetime import date, datetime, timezone as utc_timezone
from decimal import Decimal
from uuid import UUID
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .context import current_actor
from .models import AuditEvent

FIELDS = {
    "recurring.recurringrule": (
        "name",
        "kind",
        "amount",
        "currency",
        "source_account_id",
        "destination_account_id",
        "area_id",
        "category_id",
        "subcategory_id",
        "payment_method",
        "frequency",
        "interval",
        "start_date",
        "end_date",
        "next_due_date",
        "timezone",
        "execution_mode",
        "status",
    ),
    "recurring.recurringexecution": (
        "rule_id",
        "scheduled_date",
        "status",
        "transaction_id",
        "attempted_at",
        "executed_at",
        "error_code",
    ),
    "accounts.account": (
        "name",
        "kind",
        "currency",
        "initial_balance",
        "is_active",
    ),
    "categories.area": ("name", "is_active"),
    "categories.category": ("name", "area_id", "kind", "is_active"),
    "categories.subcategory": ("name", "category_id", "is_active"),
    "transactions.transaction": (
        "account_id",
        "destination_account_id",
        "kind",
        "amount",
        "currency",
        "area_id",
        "category_id",
        "subcategory_id",
        "occurred_at",
        "payment_method",
        "status",
    ),
    "budgets.budget": (
        "area_id",
        "category_id",
        "limit_amount",
        "currency",
        "year",
        "month",
        "is_active",
    ),
}
REDACTED = {
    "accounts.account": ("institution",),
    "transactions.transaction": ("description", "reference"),
}


def normalized(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(utc_timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def snapshot(instance):
    return {
        field: normalized(getattr(instance, field))
        for field in FIELDS[instance._meta.label_lower]
    }


@receiver(pre_save)
def prepare(sender, instance, raw=False, **kwargs):
    label = instance._meta.label_lower
    actor = current_actor.get()
    if (
        raw
        or label not in FIELDS
        or not actor
        or instance.owner_id != actor[0].pk
    ):
        return
    previous = (
        sender.objects.filter(pk=instance.pk).first()
        if not instance._state.adding
        else None
    )
    instance._audit_before = snapshot(previous) if previous else {}
    instance._audit_redacted = [
        f
        for f in REDACTED.get(label, ())
        if previous and getattr(previous, f) != getattr(instance, f)
    ]


@receiver(post_save)
def record(sender, instance, created, raw=False, **kwargs):
    label = instance._meta.label_lower
    actor = current_actor.get()
    if (
        raw
        or label not in FIELDS
        or not actor
        or not hasattr(instance, "_audit_before")
    ):
        return
    # Initial catalog is infrastructure, not a historical financial operation.
    if created and getattr(instance, "seed_code", None):
        return
    before, after = instance._audit_before, snapshot(instance)
    changed = [
        f for f in after if before.get(f) != after[f]
    ] + instance._audit_redacted
    if not created and not changed:
        return
    operation = (
        "CREATE"
        if created
        else (
            "VOID"
            if before.get("status") != "VOID" and after.get("status") == "VOID"
            else (
                "DEACTIVATE"
                if before.get("is_active") is True
                and after.get("is_active") is False
                else "UPDATE"
            )
        )
    )
    if (
        not created
        and label.startswith("recurring.")
        and before.get("status") != after.get("status")
    ):
        operation = {
            "PAUSED": "PAUSE",
            "CANCELLED": "CANCEL",
            "ACTIVE": "RESUME",
            "EXECUTED": "EXECUTE",
            "SKIPPED": "SKIP",
        }.get(after.get("status"), "UPDATE")
    AuditEvent.objects.create(
        actor=actor[0],
        operation=operation,
        resource_type=label,
        resource_id=instance.pk,
        before=before,
        after=after,
        changed_fields=changed,
        correlation_id=getattr(instance, "idempotency_key", None) or actor[1],
    )
    del instance._audit_before
