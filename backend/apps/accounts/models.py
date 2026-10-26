import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Account(models.Model):
    class Kind(models.TextChoices):
        CASH = "CASH", "Efectivo"
        BANK = "BANK", "Banco"
        WALLET = "WALLET", "Billetera digital"
        CREDIT = "CREDIT", "Tarjeta de crédito"
        OTHER = "OTHER", "Otra cuenta de activos"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    institution = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3, default="PEN", choices=[("PEN", "PEN")])
    initial_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", condition=models.Q(family__isnull=True), name="account_owner_name_unique"),
            models.UniqueConstraint(Lower("name"), "family", condition=models.Q(family__isnull=False), name="fam_account_owner_name_unique"),
            models.CheckConstraint(condition=~models.Q(kind="CREDIT") | models.Q(initial_balance__lte=0), name="credit_initial_nonpositive"),
        ]
