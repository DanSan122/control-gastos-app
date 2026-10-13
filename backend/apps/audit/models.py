from uuid import uuid4
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Los eventos son inmutables.")

    def delete(self):
        raise ValidationError("Los eventos no se eliminan.")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("Los eventos son inmutables.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Usa el servicio de registro de eventos.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    operation = models.CharField(
        max_length=12,
        choices=[(s, s) for s in ("CREATE", "UPDATE", "VOID", "DEACTIVATE")],
    )
    resource_type = models.CharField(max_length=32)
    resource_id = models.UUIDField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    changed_fields = models.JSONField(default=list)
    correlation_id = models.UUIDField(default=uuid4)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["actor", "occurred_at"]),
            models.Index(fields=["actor", "resource_type", "resource_id"]),
        ]

    def save(self, *args, **kwargs):
        if (
            not self._state.adding
            or type(self).objects.filter(pk=self.pk).exists()
        ):
            raise ValidationError("Los eventos son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos no se eliminan.")
