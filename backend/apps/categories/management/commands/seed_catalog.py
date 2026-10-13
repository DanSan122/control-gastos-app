from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from apps.categories.catalog import seed_catalog


class Command(BaseCommand):
    help = "Crea catálogo inicial por usuario de forma idempotente, sin reactivar ni renombrar datos existentes."

    def handle(self, *args, **options):
        count = 0
        for user in get_user_model().objects.all().iterator():
            seed_catalog(user)
            count += 1
        self.stdout.write(f"Catálogos comprobados: {count}")
