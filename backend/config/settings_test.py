"""Tests sin PostgreSQL; no sustituye las pruebas de integración con PostgreSQL."""
import os
import secrets

os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
os.environ["DJANGO_DEBUG"] = "true"

from .settings import *  # noqa: F403,E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173"]
