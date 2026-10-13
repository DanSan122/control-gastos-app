from decimal import Decimal
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Transaction


def balances_for(accounts, until=None):
    accounts = list(accounts)
    balances = {account.id: account.initial_balance for account in accounts}
    if not balances:
        return balances
    owner = accounts[0].owner_id
    rows = Transaction.objects.filter(owner_id=owner, status="POSTED")
    if until:
        rows = rows.filter(occurred_at__lt=until)
    else:
        rows = rows.filter(occurred_at__lte=timezone.now())
    rows = rows.filter(Q(account_id__in=balances) | Q(destination_account_id__in=balances))
    # Agregaciones NUMERIC en la base; una transferencia produce dos efectos de saldo.
    for row in rows.values("account_id", "kind").annotate(total=Sum("amount")):
        if row["account_id"] in balances:
            balances[row["account_id"]] += row["total"] if row["kind"] == "INCOME" else -row["total"]
    for row in rows.filter(kind="TRANSFER").values("destination_account_id").annotate(total=Sum("amount")):
        if row["destination_account_id"] in balances:
            balances[row["destination_account_id"]] += row["total"]
    return balances


def account_balance(account, until=None):
    return balances_for([account], until)[account.id]
