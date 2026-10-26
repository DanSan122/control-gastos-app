"""Hash historical rows without printing or exporting personal/financial contents."""

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.apps import apps

labels = (
    "users.User",
    "accounts.Account",
    "categories.Area",
    "categories.Category",
    "categories.Subcategory",
    "transactions.Transaction",
    "budgets.Budget",
    "recurring.RecurringRule",
    "recurring.RecurringExecution",
    "audit.AuditEvent",
)
result = {}
for label in labels:
    model = apps.get_model(label)
    fields = [f.attname for f in model._meta.concrete_fields if f.name != "family"]
    rows = list(model.objects.order_by("pk").values_list(*fields))
    payload = json.dumps(rows, default=str, ensure_ascii=True, separators=(",", ":"))
    result[label] = {
        "count": len(rows),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }
path = Path("tmp/migration-check.json")
path.parent.mkdir(exist_ok=True)
if sys.argv[1] == "before":
    path.write_text(json.dumps(result), encoding="utf-8")
else:
    previous = json.loads(path.read_text(encoding="utf-8"))
    if result != previous:
        raise SystemExit("Historical row checksum mismatch")
    for label in labels:
        model = apps.get_model(label)
        if (
            any(f.name == "family" for f in model._meta.fields)
            and model.objects.filter(family__isnull=False).exists()
        ):
            raise SystemExit("Historical record unexpectedly assigned to family")
    print("All historical row hashes unchanged; previous rows remain PERSONAL")
print(json.dumps({label: data["count"] for label, data in result.items()}))
