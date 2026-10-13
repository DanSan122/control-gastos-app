import uuid
from django.conf import settings
from django.db import models


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="outgoing")
    destination_account = models.ForeignKey("accounts.Account", on_delete=models.PROTECT, related_name="incoming", null=True, blank=True)
    kind = models.CharField(max_length=8, choices=[("INCOME", "Ingreso"), ("EXPENSE", "Gasto"), ("TRANSFER", "Transferencia")])
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="PEN", choices=[("PEN", "PEN")])
    area = models.ForeignKey("categories.Area", on_delete=models.PROTECT, related_name="movements", null=True, blank=True)
    category = models.ForeignKey("categories.Category", on_delete=models.PROTECT, related_name="movements", null=True, blank=True)
    subcategory = models.ForeignKey("categories.Subcategory", on_delete=models.PROTECT, related_name="movements", null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=20, blank=True, choices=[("", "Sin especificar"), ("CASH", "Efectivo"), ("CARD", "Tarjeta"), ("YAPE", "Yape"), ("PLIN", "Plin"), ("BANK", "Transferencia bancaria"), ("OTHER", "Otro")])
    reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=6, default="POSTED", choices=[("POSTED", "Vigente"), ("VOID", "Anulado")])
    idempotency_key = models.UUIDField(null=True, blank=True, editable=False)
    request_hash = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_positive"),
            models.UniqueConstraint(fields=["owner", "idempotency_key"], name="transfer_idempotency_unique"),
            models.CheckConstraint(condition=(
                models.Q(kind="TRANSFER", destination_account__isnull=False, area__isnull=True, category__isnull=True, subcategory__isnull=True)
                | models.Q(kind__in=["INCOME", "EXPENSE"], destination_account__isnull=True, area__isnull=False, category__isnull=False)
            ), name="transaction_shape_valid"),
            models.CheckConstraint(condition=~models.Q(account=models.F("destination_account")), name="transfer_accounts_different"),
        ]
        indexes = [models.Index(fields=["owner", "occurred_at"]), models.Index(fields=["owner", "account", "occurred_at"]), models.Index(fields=["owner", "category", "occurred_at"])]
