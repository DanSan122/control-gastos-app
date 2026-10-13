from rest_framework.authentication import SessionAuthentication


class CSRFSafeSessionAuthentication(SessionAuthentication):
    """Aplica CSRF también al usuario anónimo de registro/login."""

    def authenticate(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            self.enforce_csrf(request)
        return super().authenticate(request)
