import hashlib
import hmac
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from .models import AuthRateLimit, User


class AuthThrottle(BaseThrottle):
    """Contadores atómicos por identidad y por IP; independientes de workers."""

    def allow_request(self, request, view):
        action = view.rate_action
        ip = request.META.get("REMOTE_ADDR", "unknown")
        if action == "login":
            data = getattr(request, "data", request.POST)
            email = data.get("email", data.get("username", "")) if isinstance(data, dict) else ""
            email = User.objects.normalize_email(email) if isinstance(email, str) else ""
            limits = [("login-ip", ip, settings.AUTH_LOGIN_IP_LIMIT),
                      ("login-email", email, settings.AUTH_LOGIN_EMAIL_LIMIT)]
        elif action == "register":
            limits = [("register-ip", ip, settings.AUTH_REGISTER_IP_LIMIT)]
        else:
            limits = [("password-user", str(request.user.pk), settings.AUTH_PASSWORD_USER_LIMIT)]
        self.retry_after = 0
        allowed = True
        now = timezone.now()
        for scope, identity, limit in limits:
            key = hmac.new(settings.SECRET_KEY.encode(), f"{scope}:{identity}".encode(), hashlib.sha256).hexdigest()
            with transaction.atomic():
                AuthRateLimit.objects.get_or_create(key=key, defaults={
                    "expires_at": now + timedelta(seconds=settings.AUTH_RATE_WINDOW_SECONDS),
                })
                counter = AuthRateLimit.objects.select_for_update().get(pk=key)
                if counter.expires_at <= now:
                    counter.attempts = 0
                    counter.expires_at = now + timedelta(seconds=settings.AUTH_RATE_WINDOW_SECONDS)
                if counter.attempts >= limit:
                    allowed = False
                    self.retry_after = max(self.retry_after, math.ceil((counter.expires_at - now).total_seconds()))
                else:
                    counter.attempts += 1
                    counter.save(update_fields=["attempts", "expires_at"])
        return allowed

    def wait(self):
        return self.retry_after
