from django.core.management.base import BaseCommand, CommandError
from apps.recurring.services import process


class Command(BaseCommand):
    help = (
        "Procesa vencimientos automáticos; nunca inserta movimientos futuros."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--per-rule", type=int, default=100)

    def handle(self, *args, **options):
        if (
            not 1 <= options["limit"] <= 1000
            or not 1 <= options["per_rule"] <= 1000
        ):
            raise CommandError("Límites entre 1 y 1000.")
        try:
            counts = process(options["limit"], options["per_rule"])
        except Exception:
            raise CommandError("PROCESS_RETRY_REQUIRED") from None
        self.stdout.write(
            f"executed={counts['executed']} failed={counts['failed']}"
        )
