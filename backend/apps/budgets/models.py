from uuid import uuid4
from django.conf import settings
from django.db import models
from django.db.models import Q


class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    area = models.ForeignKey("categories.Area", null=True, blank=True, on_delete=models.PROTECT)
    category = models.ForeignKey("categories.Category", null=True, blank=True, on_delete=models.PROTECT)
    limit_amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[("PEN", "PEN")], default="PEN")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(area__isnull=False, category__isnull=True) | Q(area__isnull=True, category__isnull=False)), name="budget_one_scope"),
            models.CheckConstraint(condition=Q(limit_amount__gt=0), name="budget_positive_limit"),
            models.CheckConstraint(condition=Q(month__gte=1, month__lte=12, year__gte=1900, year__lte=9998), name="budget_valid_month"),
            models.CheckConstraint(condition=Q(currency="PEN"), name="budget_pen_currency"),
            models.UniqueConstraint(fields=["owner", "area", "year", "month", "currency"], condition=Q(area__isnull=False), name="budget_unique_area"),
            models.UniqueConstraint(fields=["owner", "category", "year", "month", "currency"], condition=Q(category__isnull=False), name="budget_unique_category"),
        ]
