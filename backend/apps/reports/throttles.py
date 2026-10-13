import hashlib
import hmac
import math
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle
from apps.users.models import AuthRateLimit


class ReportThrottle(BaseThrottle):
    def allow_request(self, request, view):
        scope = "export" if getattr(view, "export_format", None) else "preview"
        limit = (
            settings.REPORT_EXPORT_LIMIT
            if scope == "export"
            else settings.REPORT_PREVIEW_LIMIT
        )
        key = hmac.new(
            settings.SECRET_KEY.encode(),
            f"reports:{scope}:{request.user.pk}".encode(),
            hashlib.sha256,
        ).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            AuthRateLimit.objects.get_or_create(
                key=key,
                defaults={
                    "expires_at": now
                    + timedelta(seconds=settings.REPORT_RATE_SECONDS)
                },
            )
            counter = AuthRateLimit.objects.select_for_update().get(pk=key)
            if counter.expires_at <= now:
                counter.attempts = 0
                counter.expires_at = now + timedelta(
                    seconds=settings.REPORT_RATE_SECONDS
                )
            self.retry_after = max(
                1, math.ceil((counter.expires_at - now).total_seconds())
            )
            if counter.attempts >= limit:
                return False
            counter.attempts += 1
            counter.save(update_fields=["attempts", "expires_at"])
        return True

    def wait(self):
        return self.retry_after
