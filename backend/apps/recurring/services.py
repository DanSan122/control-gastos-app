import hashlib
import json
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.db import transaction, DatabaseError
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.core.finance import owner_lock
from apps.transactions.creation import create_movement
from .calendar import next_date, effective_at
from .models import RecurringRule, RecurringExecution
from .serializers import movement_payload


def prepare_next(rule):
    if rule.next_due_date:
        return RecurringExecution.objects.get_or_create(
            rule=rule, scheduled_date=rule.next_due_date
        )[0]


def advance(rule, scheduled_date):
    following = next_date(rule, scheduled_date)
    if following is None or (rule.end_date and following > rule.end_date):
        rule.next_due_date, rule.status = None, "COMPLETED"
    else:
        rule.next_due_date = following
    rule.save(update_fields=["next_due_date", "status", "updated_at"])
    prepare_next(rule)


def execute(user, execution_id, *, automatic=False, skip=False):
    with owner_lock(user):
        execution = RecurringExecution.objects.select_related("rule").get(
            pk=execution_id, rule__owner=user
        )
        rule = execution.rule
        if execution.status == "EXECUTED":
            if skip:
                raise ValidationError("Una ejecución realizada no se omite.")
            return execution
        if execution.status == "SKIPPED":
            if skip:
                return execution
            raise ValidationError("La ocurrencia omitida es inmutable.")
        if (
            rule.status != "ACTIVE"
            or execution.scheduled_date != rule.next_due_date
        ):
            raise ValidationError(
                "La regla no está activa o esta no es su próxima ocurrencia."
            )
        if (rule.execution_mode == "AUTOMATIC") != automatic:
            raise ValidationError("Utiliza el modo de ejecución de la regla.")
        if (
            execution.scheduled_date
            > timezone.now().astimezone(ZoneInfo(rule.timezone)).date()
        ):
            raise ValidationError("La ocurrencia todavía no ha vencido.")
        if skip:
            execution.status, execution.attempted_at = (
                "SKIPPED",
                timezone.now(),
            )
            execution.error_code = ""
            execution.save()
            advance(rule, execution.scheduled_date)
            return execution
        try:
            with transaction.atomic():
                payload = movement_payload(
                    rule, effective_at(execution.scheduled_date, rule.timezone)
                )
                fingerprint = hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()
                movement = create_movement(
                    user,
                    payload,
                    idempotency_key=execution.idempotency_key,
                    request_hash=fingerprint,
                )
                execution.transaction = movement
                execution.status = "EXECUTED"
                execution.attempted_at = execution.executed_at = timezone.now()
                execution.error_code = ""
                execution.save()
                advance(rule, execution.scheduled_date)
        except (ValidationError, ValueError, DatabaseError) as error:
            # Creation, financial audit, execution and cursor all rolled back together.
            execution.refresh_from_db()
            execution.status = "FAILED"
            execution.attempted_at = timezone.now()
            execution.error_code = (
                "INVALID_RELATIONS"
                if isinstance(error, ValidationError)
                else (
                    "CALENDAR_DATE_UNAVAILABLE"
                    if isinstance(error, ValueError)
                    else "TEMPORARY_FAILURE"
                )
            )
            execution.save()
        return execution


def process(limit=100, per_rule=100):
    from django.contrib.auth import get_user_model

    recent_failure = RecurringExecution.objects.filter(
        rule_id=OuterRef("pk"),
        status="FAILED",
        attempted_at__gt=timezone.now() - timedelta(seconds=60),
    )
    rules = list(
        RecurringRule.objects.filter(
            status="ACTIVE",
            execution_mode="AUTOMATIC",
            owner__is_active=True,
            next_due_date__lte=timezone.now().date() + timedelta(days=1),
        )
        .annotate(recent_failure=Exists(recent_failure))
        .filter(recent_failure=False)
        .order_by("next_due_date", "id")
        .values_list("id", "owner_id")[:limit]
    )
    counts = {"executed": 0, "failed": 0}
    for rule_id, owner_id in rules:
        user = get_user_model().objects.get(pk=owner_id)
        if not user.is_active:
            continue
        for _ in range(per_rule):
            with owner_lock(user):
                rule = RecurringRule.objects.get(pk=rule_id, owner=user)
                if (
                    rule.status != "ACTIVE"
                    or rule.execution_mode != "AUTOMATIC"
                    or rule.next_due_date
                    > timezone.now().astimezone(ZoneInfo(rule.timezone)).date()
                ):
                    break
                execution = prepare_next(rule)
                result = execute(user, execution.pk, automatic=True)
            if result.status == "FAILED":
                counts["failed"] += 1
                break
            counts["executed"] += 1
    return counts
