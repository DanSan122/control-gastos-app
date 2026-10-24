import signal
import threading
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from apps.recurring.services import process


class Command(BaseCommand):
    help = "Scheduler simple de desarrollo; SIGTERM finaliza sin perder ocurrencias."

    def add_arguments(self, parser):
        parser.add_argument("--seconds", type=int, default=30)

    def handle(self, *args, **options):
        seconds = options["seconds"]
        if not 5 <= seconds <= 3600:
            raise CommandError("Intervalo de 5 a 3600 segundos.")
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        signal.signal(signal.SIGINT, lambda *_: stopping.set())
        self.stdout.write("recurring scheduler started")
        while not stopping.is_set():
            close_old_connections()
            try:
                result = process()
                self.stdout.write(
                    f"executed={result['executed']} failed={result['failed']}"
                )
            except Exception:
                # Never print exception payloads, connection strings or personal data.
                self.stderr.write(
                    "recurring scheduler: PROCESS_RETRY_REQUIRED"
                )
            close_old_connections()
            stopping.wait(seconds)
