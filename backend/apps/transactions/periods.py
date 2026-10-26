from apps.core.scope import scope_timezone
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from rest_framework.exceptions import ValidationError


def period_bounds(params, user, optional=False):
    zone = ZoneInfo(scope_timezone(user))
    today = timezone.now().astimezone(zone).date()
    period = params.get("period")
    if optional and not period and not params.get("start") and not params.get("end"):
        return None, None
    period = period or ("custom" if params.get("start") or params.get("end") else "month")
    if period == "day":
        start, end = today, today
    elif period == "yesterday":
        start = end = today - timedelta(days=1)
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
    elif period == "previous_week":
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
    elif period == "previous_month":
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "year":
        start, end = today.replace(month=1, day=1), today.replace(month=12, day=31)
    elif period == "custom":
        try:
            start, end = date.fromisoformat(params.get("start", "")), date.fromisoformat(params.get("end", ""))
        except ValueError:
            raise ValidationError({"period": "Indica start y end como YYYY-MM-DD."})
    else:
        raise ValidationError({"period": "Usa day, yesterday, week, previous_week, month, previous_month, year o custom."})
    if start > end or (end - start).days > 3660 or end == date.max:
        raise ValidationError({"period": "Rango inválido o mayor a diez años."})
    return datetime.combine(start, time.min, zone), datetime.combine(end + timedelta(days=1), time.min, zone)
