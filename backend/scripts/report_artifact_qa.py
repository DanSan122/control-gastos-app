"""Synthetic, database-free artifacts for manual rendering/Excel verification."""

import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from apps.reports.exporters import export_pdf, export_xlsx, export_csv

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
total = format(Decimal("1234.56") * 40, ".2f")
namespace = lambda name: SimpleNamespace(name=name)
rows = [
    SimpleNamespace(
        pk=UUID(int=index + 1),
        occurred_at=datetime(2026, 10, 10, 17, 25, tzinfo=timezone.utc),
        kind="EXPENSE",
        status="POSTED",
        account=namespace("Banco de pruebas con nombre largo"),
        destination_account=None,
        area=namespace("Alimentación"),
        category=namespace("Compras de alimentos y productos del hogar"),
        subcategory=namespace("Compra semanal"),
        amount=Decimal("1234.56"),
        currency="PEN",
        payment_method="YAPE",
        description=(
            "Descripción sintética con acentos, <etiquetas> y & signos. " * 9
        )[:500],
        reference=f"Referencia de prueba {index + 1}",
    )
    for index in range(40)
]
data = {
    "income": "0.00",
    "expense": total,
    "net_flow": "-" + total,
    "start": "2026-10-01T00:00:00-05:00",
    "end_exclusive": "2026-11-01T00:00:00-05:00",
    "generated_at": "2026-10-13T07:00:00+00:00",
    "timezone": "America/Lima",
    "filters": {"period": "month", "kind": "EXPENSE", "status": "POSTED"},
    "note": "Solo movimientos vigentes. Transferencias y pagos de deuda no son gastos adicionales.",
    "areas": [{"name": "Alimentación", "amount": total}],
    "categories": [
        {"name": "Compras de alimentos y productos del hogar", "amount": total}
    ],
    "evolution": {
        "points": [
            {
                "date": "2026-10-10",
                "income": "0.00",
                "expense": total,
                "net_flow": "-" + total,
                "accumulated": total,
            }
        ]
    },
}
for kind, exporter in (
    ("pdf", export_pdf),
    ("xlsx", export_xlsx),
    ("csv", export_csv),
):
    (destination / f"report-qa.{kind}").write_bytes(exporter(rows, data))
print(
    "QA: tres documentos sintéticos generados; no se consultó ni modificó la base."
)
