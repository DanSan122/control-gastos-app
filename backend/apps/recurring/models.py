from uuid import uuid4, uuid5, NAMESPACE_URL
from django.conf import settings
from django.db import models
from django.db.models import Q, F


class RecurringRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(
        max_length=8,
        choices=[(s, s) for s in ("INCOME", "EXPENSE", "TRANSFER")],
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(
        max_length=3, choices=[("PEN", "PEN")], default="PEN"
    )
    source_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="recurring_sources",
    )
    destination_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recurring_destinations",
    )
    area = models.ForeignKey(
        "categories.Area", on_delete=models.PROTECT, null=True, blank=True
    )
    category = models.ForeignKey(
        "categories.Category", on_delete=models.PROTECT, null=True, blank=True
    )
    subcategory = models.ForeignKey(
        "categories.Subcategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    payment_method = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            (s, s or "Sin especificar")
            for s in ("", "CASH", "CARD", "YAPE", "PLIN", "BANK", "OTHER")
        ],
    )
    frequency = models.CharField(
        max_length=7,
        choices=[(s, s) for s in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")],
    )
    interval = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="America/Lima")
    execution_mode = models.CharField(
        max_length=9,
        choices=[("AUTOMATIC", "Automático"), ("MANUAL", "Manual")],
        default="MANUAL",
    )
    status = models.CharField(
        max_length=9,
        choices=[
            (s, s) for s in ("ACTIVE", "PAUSED", "COMPLETED", "CANCELLED")
        ],
        default="ACTIVE",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "status", "next_due_date"]),
            models.Index(fields=["execution_mode", "status", "next_due_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    amount__gt=0,
                    interval__gte=1,
                    interval__lte=1000,
                    currency="PEN",
                ),
                name="recurring_money_interval_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True)
                | Q(end_date__gte=F("start_date")),
                name="recurring_dates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="TRANSFER",
                        destination_account__isnull=False,
                        area__isnull=True,
                        category__isnull=True,
                        subcategory__isnull=True,
                    )
                    | Q(
                        kind__in=["INCOME", "EXPENSE"],
                        destination_account__isnull=True,
                        area__isnull=False,
                        category__isnull=False,
                    )
                ),
                name="recurring_shape_valid",
            ),
            models.CheckConstraint(
                condition=~Q(source_account=F("destination_account")),
                name="recurring_accounts_distinct",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=["ACTIVE", "PAUSED"],
                        next_due_date__isnull=False,
                    )
                    | Q(
                        status__in=["COMPLETED", "CANCELLED"],
                        next_due_date__isnull=True,
                    )
                ),
                name="recurring_cursor_state_valid",
            ),
        ]


class RecurringExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    rule = models.ForeignKey(
        RecurringRule, on_delete=models.PROTECT, related_name="executions"
    )
    scheduled_date = models.DateField()
    status = models.CharField(
        max_length=8,
        choices=[(s, s) for s in ("PENDING", "EXECUTED", "FAILED", "SKIPPED")],
        default="PENDING",
    )
    transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    attempted_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def owner_id(self):
        return self.rule.owner_id

    @property
    def idempotency_key(self):
        return uuid5(
            NAMESPACE_URL,
            f"controlgastos:recurring:{self.rule_id}:{self.scheduled_date.isoformat()}",
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rule", "scheduled_date"],
                name="recurring_occurrence_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="EXECUTED",
                        transaction__isnull=False,
                        executed_at__isnull=False,
                    )
                    | Q(
                        status__in=["PENDING", "FAILED", "SKIPPED"],
                        transaction__isnull=True,
                        executed_at__isnull=True,
                    )
                ),
                name="recurring_execution_state_valid",
            ),
        ]
        indexes = [models.Index(fields=["rule", "status", "scheduled_date"])]
