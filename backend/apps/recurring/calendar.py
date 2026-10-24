from calendar import monthrange
from datetime import datetime, time, timedelta, timezone as utc
from zoneinfo import ZoneInfo


def next_date(rule, current):
    try:
        if rule.frequency in ("DAILY", "WEEKLY"):
            return current + timedelta(
                days=rule.interval * (7 if rule.frequency == "WEEKLY" else 1)
            )
        if rule.frequency == "MONTHLY":
            index = current.year * 12 + current.month - 1 + rule.interval
            year, month = divmod(index, 12)
            month += 1
        else:
            year, month = current.year + rule.interval, rule.start_date.month
        return current.replace(
            year=year,
            month=month,
            day=min(rule.start_date.day, monthrange(year, month)[1]),
        )
    except (ValueError, OverflowError):
        return None


def effective_at(day, zone_name):
    zone = ZoneInfo(zone_name)
    naive = datetime.combine(day, time.min)
    # First valid local minute; a skipped entire date is not shifted silently.
    for minute in range(1440):
        candidate = naive + timedelta(minutes=minute)
        value = candidate.replace(tzinfo=zone, fold=0).astimezone(utc.utc)
        if value.astimezone(zone).replace(tzinfo=None) == candidate:
            return value
    raise ValueError("CALENDAR_DATE_UNAVAILABLE")
