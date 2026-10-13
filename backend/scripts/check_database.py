"""Consulta real y de solo lectura, utilizable antes de la primera migración."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT 1, current_setting('TimeZone')")
    result = cursor.fetchone()
    print(f"Django–PostgreSQL: SELECT 1 = {result[0]}; timezone = {result[1]}")
    tables = connection.introspection.table_names(cursor)
    print(f"Tablas existentes: {len(tables)}")
    if "django_migrations" in tables:
        cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, name")
        print("Migraciones aplicadas:", cursor.fetchall())
    else:
        print("Sin tabla django_migrations; no se aplicaron migraciones.")

if "users_user" in tables:
    from django.contrib.auth import get_user_model

    print(f"Usuarios consultables desde ORM: {get_user_model().objects.count()}")
