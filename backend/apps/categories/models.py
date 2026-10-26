import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Classification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    seed_code = models.CharField(max_length=60, null=True, blank=True, editable=False)

    class Meta:
        abstract = True


class Area(Classification):
    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", condition=models.Q(family__isnull=True), name="area_owner_name_unique"),
            models.UniqueConstraint(Lower("name"), "family", condition=models.Q(family__isnull=False), name="fam_area_owner_name_unique"),
            models.UniqueConstraint(fields=["owner", "seed_code"], condition=models.Q(family__isnull=True), name="area_seed_unique"),
            models.UniqueConstraint(fields=["family", "seed_code"], condition=models.Q(family__isnull=False), name="fam_area_seed_unique"),
        ]


class Category(Classification):
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="categories")
    kind = models.CharField(max_length=7, choices=[("INCOME", "Ingreso"), ("EXPENSE", "Gasto")])

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", "area", "kind", condition=models.Q(family__isnull=True), name="category_owner_name_unique"),
            models.UniqueConstraint(Lower("name"), "family", "area", "kind", condition=models.Q(family__isnull=False), name="fam_category_owner_name_unique"),
            models.UniqueConstraint(fields=["owner", "seed_code"], condition=models.Q(family__isnull=True), name="category_seed_unique"),
            models.UniqueConstraint(fields=["family", "seed_code"], condition=models.Q(family__isnull=False), name="fam_category_seed_unique"),
        ]


class Subcategory(Classification):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategories")

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", "category", condition=models.Q(family__isnull=True), name="subcategory_owner_name_unique"),
            models.UniqueConstraint(Lower("name"), "family", "category", condition=models.Q(family__isnull=False), name="fam_subcategory_owner_name_unique"),
            models.UniqueConstraint(fields=["owner", "seed_code"], condition=models.Q(family__isnull=True), name="subcategory_seed_unique"),
            models.UniqueConstraint(fields=["family", "seed_code"], condition=models.Q(family__isnull=False), name="fam_subcategory_seed_unique"),
        ]
