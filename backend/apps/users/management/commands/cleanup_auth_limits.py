from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import AuthRateLimit


class Command(BaseCommand):
    help = "Elimina exclusivamente contadores de autenticación expirados."

    def handle(self, *args, **options):
        count, _ = AuthRateLimit.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"Contadores expirados eliminados: {count}")
