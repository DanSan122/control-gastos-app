from uuid import UUID
from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.models import Account
from apps.categories.models import Area, Category, Subcategory
from apps.analytics.services import totals, evolution, distribution
from apps.transactions.filters import filtered_transactions
from apps.transactions.periods import period_bounds
from apps.transactions.reports import money

ALLOWED_PARAMS = {
    "period",
    "start",
    "end",
    "account",
    "area",
    "category",
    "subcategory",
    "kind",
    "status",
    "payment_method",
    "granularity",
    "currency",
    "page",
    "page_size",
    "ordering",
    "format",
}


def report_query(user, params):
    if set(params) - ALLOWED_PARAMS:
        raise ValidationError("El reporte contiene filtros no admitidos.")
    if params.get("currency", "PEN") != "PEN":
        raise ValidationError({"currency": "Solo PEN está habilitado."})
    start, end = period_bounds(params, user)
    if (end.date() - start.date()).days > settings.REPORT_MAX_DAYS:
        raise ValidationError(
            {"period": f"Máximo {settings.REPORT_MAX_DAYS} días calendario."}
        )
    granularity = params.get("granularity", "daily")
    if granularity not in ("daily", "weekly", "monthly"):
        raise ValidationError({"granularity": "Usa daily, weekly o monthly."})
    for field, model in (
        ("account", Account),
        ("area", Area),
        ("category", Category),
        ("subcategory", Subcategory),
    ):
        if params.get(field):
            try:
                identifier = UUID(params[field])
            except ValueError:
                raise ValidationError({field: "UUID inválido."})
            if not model.objects.filter(owner=user, pk=identifier).exists():
                raise ValidationError(
                    {field: "El recurso no existe o no te pertenece."}
                )
    filters = dict(params.items())
    if filters.get("payment_method") == "UNSPECIFIED":
        filters.pop("payment_method")
    status = filters.get("status") or "POSTED"
    if status == "ALL":
        filters.pop("status", None)
    else:
        filters["status"] = status
    rows = filtered_transactions(user, filters, optional_period=False).filter(
        currency="PEN"
    )
    if params.get("payment_method") == "UNSPECIFIED":
        # This special filter is handled before the shared enum validation.
        rows = rows.filter(payment_method="")
    return rows, start, end, granularity


def summary(rows, start, end, granularity, user, params):
    posted = rows.filter(status="POSTED")
    values = totals(posted)
    return {
        "currency": "PEN",
        "timezone": user.timezone,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "generated_at": timezone.now().isoformat(),
        "filters": {
            key: value
            for key, value in params.items()
            if key not in ("page", "page_size", "format")
        },
        **{key: money(value) for key, value in values.items()},
        "areas": distribution(posted, "area"),
        "categories": distribution(posted, "category"),
        "evolution": evolution(
            posted, start, end, ZoneInfo(user.timezone), granularity
        ),
        "note": "Indicadores solo de movimientos vigentes. Transferencias excluidas de ingresos y gastos; anulados pueden aparecer en el detalle.",
    }
