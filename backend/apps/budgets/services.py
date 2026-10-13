from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from django.db.models import Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from apps.transactions.models import Transaction
from apps.transactions.reports import money


def month_bounds(year, month, zone):
    start = datetime(year, month, 1, tzinfo=zone)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=zone)
    return start, end


def progress_for(budgets, user):
    """Two grouped ledger queries for any number of budgets, never one per row."""
    budgets = list(budgets)
    if not budgets:
        return {}
    zone = ZoneInfo(user.timezone)
    bounds = [month_bounds(b.year, b.month, zone) for b in budgets]
    rows = Transaction.objects.filter(owner=user, currency="PEN", status="POSTED", kind="EXPENSE", occurred_at__gte=min(x[0] for x in bounds), occurred_at__lt=max(x[1] for x in bounds))
    totals = {}
    for scope in ("area", "category"):
        ids = {getattr(b, f"{scope}_id") for b in budgets} - {None}
        if ids:
            grouped = rows.filter(**{f"{scope}_id__in": ids}).annotate(y=ExtractYear("occurred_at", tzinfo=zone), m=ExtractMonth("occurred_at", tzinfo=zone)).values(f"{scope}_id", "y", "m").annotate(total=Sum("amount"))
            totals[scope] = {(r[f"{scope}_id"], r["y"], r["m"]): r["total"] for r in grouped}
    result = {}
    for budget in budgets:
        scope = "area" if budget.area_id else "category"
        used = totals.get(scope, {}).get((getattr(budget, f"{scope}_id"), budget.year, budget.month), Decimal("0"))
        percentage = used * 100 / budget.limit_amount
        alert = "EXCEEDED" if percentage >= 100 else "WARNING" if percentage >= 80 else "NORMAL"
        result[budget.id] = {"consumed": money(used), "available": money(budget.limit_amount - used), "used_percent": str(percentage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), "bar_percent": min(100, int(percentage)), "alert": alert if budget.is_active else "INACTIVE", "scope_name": getattr(budget, scope).name}
    return result
