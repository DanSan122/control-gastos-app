from apps.core.scope import scoped, scope_timezone
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import Sum, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.models import Account
from apps.accounts.serializers import AccountSerializer
from apps.budgets.models import Budget
from apps.budgets.services import progress_for
from apps.transactions.models import Transaction
from apps.transactions.periods import period_bounds
from apps.transactions.reports import money
from apps.transactions.services import balances_for

ZERO = Decimal("0")


def totals(rows):
    values = rows.aggregate(income=Sum("amount", filter=Q(kind="INCOME")), expense=Sum("amount", filter=Q(kind="EXPENSE")))
    income, expense = values["income"] or ZERO, values["expense"] or ZERO
    return {"income": income, "expense": expense, "net_flow": income - expense}


def change(current, previous):
    if previous == 0:
        return {"percent": "0.00" if current == 0 else None, "status": "both_zero" if current == 0 else "no_base"}
    percent = (current - previous) * 100 / abs(previous)
    return {"percent": str(percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), "status": "comparable"}


def chart_scale(points, keys):
    """Integer geometry only. Exact monetary strings are never replaced by floats."""
    maximum = max((abs(Decimal(p[k])) for p in points for k in keys), default=ZERO)
    maximum = maximum or Decimal("1")
    for point in points:
        for key in keys:
            point[f"{key}_plot"] = int(Decimal(point[key]) * 1000000 / maximum)
    ticks = [{"value": i * 250000, "label": money(maximum * i / 4)} for i in range(-4 if any(Decimal(p[k]) < 0 for p in points for k in keys) else 0, 5)]
    return ticks


def ranges(params, user):
    start, calendar_end = period_bounds(params, user)
    now = timezone.now().astimezone(ZoneInfo(scope_timezone(user)))
    end = min(calendar_end, now)
    if start >= end:
        raise ValidationError({"period": "Selecciona un periodo que haya comenzado."})
    # Equal local wall-clock duration, including the same partial-day cutoff.
    duration = end - start
    try:
        previous_start, previous_end = start - duration, start
    except OverflowError:
        raise ValidationError({"period": "No existe un intervalo anterior equivalente para este rango."})
    days = (end.date() - start.date()).days + (end.timetz().replace(tzinfo=None) != time.min)
    return start, end, previous_start, previous_end, max(1, days)


def evolution(rows, start, end, zone, granularity):
    trunc = {"daily": TruncDay, "weekly": TruncWeek, "monthly": TruncMonth}[granularity]
    buckets = {}
    for item in rows.exclude(kind="TRANSFER").annotate(bucket=trunc("occurred_at", tzinfo=zone)).values("bucket", "kind").annotate(total=Sum("amount")):
        buckets.setdefault(item["bucket"].date(), {"income": ZERO, "expense": ZERO})["income" if item["kind"] == "INCOME" else "expense"] = item["total"]
    cursor = start.date()
    if granularity == "weekly":
        cursor -= timedelta(days=cursor.weekday())
    elif granularity == "monthly":
        cursor = cursor.replace(day=1)
    points, accumulated = [], ZERO
    while datetime.combine(cursor, time.min, zone) < end:
        values = buckets.get(cursor, {"income": ZERO, "expense": ZERO})
        accumulated += values["expense"]
        points.append({"date": cursor.isoformat(), **{key: money(value) for key, value in values.items()}, "net_flow": money(values["income"] - values["expense"]), "accumulated": money(accumulated)})
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) if granularity == "monthly" else cursor + timedelta(days=7 if granularity == "weekly" else 1)
    return {"points": points, "ticks": chart_scale(points, ("income", "expense", "net_flow", "accumulated"))}


def distribution(rows, scope):
    grouped = list(rows.filter(kind="EXPENSE").values(f"{scope}_id", f"{scope}__name").annotate(total=Sum("amount")).order_by("-total", f"{scope}__name", f"{scope}_id"))
    total = sum((r["total"] for r in grouped), ZERO)
    return [{"id": str(r[f"{scope}_id"]), "name": r[f"{scope}__name"], "amount": money(r["total"]), "weight": max(1, int(r["total"] * 1000000 / total))} for r in grouped]


def analytics(params, user, request, section="dashboard"):
    if params.get("currency", "PEN") != "PEN":
        raise ValidationError({"currency": "Solo PEN está habilitado."})
    granularity = params.get("granularity", "daily")
    if granularity not in ("daily", "weekly", "monthly"):
        raise ValidationError({"granularity": "Usa daily, weekly o monthly."})
    start, end, previous_start, previous_end, days = ranges(params, user)
    zone = ZoneInfo(scope_timezone(user))
    base = scoped(Transaction.objects, user).filter(status="POSTED", currency="PEN")
    rows = base.filter(occurred_at__gte=start, occurred_at__lt=end)
    result = {"currency": "PEN", "timezone": scope_timezone(user), "start": start.isoformat(), "end_exclusive": end.isoformat()}
    current = totals(rows)
    result.update({key: money(value) for key, value in current.items()})
    if section in ("dashboard", "comparison"):
        prior = totals(base.filter(occurred_at__gte=previous_start, occurred_at__lt=previous_end))
        comparison = [{"name": label, "current": money(current[key]), "previous": money(prior[key]), "change": change(current[key], prior[key])} for key, label in (("income", "Ingresos"), ("expense", "Gastos"), ("net_flow", "Flujo neto"))]
        result["comparison"] = {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat(), "criterion": "Duración equivalente en hora local inmediatamente anterior; el periodo actual se corta al momento de consulta.", "points": comparison, "ticks": chart_scale(comparison, ("current", "previous"))}
    if section in ("dashboard", "evolution"):
        result["evolution"] = evolution(rows, start, end, zone, granularity)
    if section in ("dashboard", "distribution"):
        result["areas"] = distribution(rows, "area")
        result["categories"] = distribution(rows, "category")
    if section == "dashboard":
        accounts = list(scoped(Account.objects, user).filter(currency="PEN").order_by("name", "id"))
        balances = balances_for(accounts)
        assets = sum((balances[a.pk] for a in accounts if a.kind != "CREDIT"), ZERO)
        debt = sum((max(ZERO, -balances[a.pk]) for a in accounts if a.kind == "CREDIT"), ZERO)
        result.update(asset_balances=money(assets), credit_debt=money(debt), net_worth=money(sum(balances.values(), ZERO)), average_daily_expense=money((current["expense"] / days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), days=days, top_category=result["categories"][0] if result["categories"] else None)
        result["accounts"] = AccountSerializer(accounts, many=True, context={"request": request, "balances": balances}).data
        today = timezone.now().astimezone(zone)
        budgets = list(scoped(Budget.objects, user).filter(is_active=True, year=today.year, month=today.month).select_related("area", "category__area"))
        progress = progress_for(budgets, user)
        result["budget_alerts"] = [{"id": str(b.pk), **progress[b.pk]} for b in budgets if progress[b.pk]["alert"] in ("WARNING", "EXCEEDED")]
        from apps.core.scope import current_family
        if current_family.get():
            from apps.transactions.serializers import TransactionSerializer
            result["recent_movements"] = TransactionSerializer(base.select_related("owner", "account", "destination_account", "area", "category", "subcategory").order_by("-occurred_at", "id")[:10], many=True).data
    return result
