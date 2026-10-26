from apps.core.scope import scoped, scope_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Account
from apps.accounts.serializers import AccountSerializer
from apps.core.finance import owner_lock
from apps.users.authentication import CSRFSafeSessionAuthentication
from .models import Transaction
from .periods import period_bounds
from .services import balances_for


def money(value):
    return format(value or Decimal("0"), ".2f")


class SummaryView(APIView):
    authentication_classes = [CSRFSafeSessionAuthentication]

    def get(self, request):
        start, end = period_bounds(request.query_params, request.user)
        if request.query_params.get("currency", "PEN") != "PEN":
            raise ValidationError({"currency": "Solo PEN está habilitado en esta fase."})
        # Snapshot lógico consistente: todas las escrituras financieras toman este bloqueo.
        with owner_lock(request.user):
            rows = scoped(Transaction.objects, request.user).filter(status="POSTED", currency="PEN", occurred_at__gte=start, occurred_at__lt=end)
            cashflow = rows.exclude(kind="TRANSFER")
            incomes = cashflow.filter(kind="INCOME").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            expenses = cashflow.filter(kind="EXPENSE").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            breakdown = {}
            for field in ("area", "category"):
                breakdown[f"expenses_by_{field}"] = [
                    {"id": str(item[f"{field}_id"]), "name": item[f"{field}__name"], "amount": money(item["total"])}
                    for item in cashflow.filter(kind="EXPENSE").values(f"{field}_id", f"{field}__name").annotate(total=Sum("amount")).order_by("-total")
                ]
            evolution = {}
            for name, trunc in [("daily", TruncDay), ("weekly", TruncWeek), ("monthly", TruncMonth)]:
                buckets = {}
                for item in cashflow.annotate(bucket=trunc("occurred_at", tzinfo=ZoneInfo(scope_timezone(request.user)))).values("bucket", "kind").annotate(total=Sum("amount")).order_by("bucket"):
                    bucket = item["bucket"].date().isoformat()
                    point = buckets.setdefault(bucket, {"date": bucket, "income": "0.00", "expense": "0.00"})
                    point["income" if item["kind"] == "INCOME" else "expense"] = money(item["total"])
                evolution[name] = [{**point, "net": money(Decimal(point["income"]) - Decimal(point["expense"]))} for point in buckets.values()]
            accounts = list(scoped(Account.objects, request.user).filter(currency="PEN").order_by("name", "id"))
            current = balances_for(accounts)
            at_end = balances_for(accounts, until=end)
            asset_balances = sum((current[a.id] for a in accounts if a.kind != "CREDIT"), Decimal("0"))
            debt = sum((max(Decimal("0"), -current[a.id]) for a in accounts if a.kind == "CREDIT"), Decimal("0"))
            return Response({
                "currency": "PEN", "timezone": scope_timezone(request.user), "start": start.isoformat(), "end_exclusive": end.isoformat(),
                "income": money(incomes), "expense": money(expenses), "net_flow": money(incomes - expenses),
                "asset_balances": money(asset_balances), "credit_debt": money(debt),
                "net_worth": money(sum(current.values(), Decimal("0"))),
                "net_worth_at_period_end": money(sum(at_end.values(), Decimal("0"))),
                "accounts": AccountSerializer(accounts, many=True, context={"request": request, "balances": current}).data,
                "evolution": evolution, **breakdown,
            })
