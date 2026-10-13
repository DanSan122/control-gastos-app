from uuid import UUID
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from .models import Transaction
from .periods import period_bounds


def filtered_transactions(user, params, optional_period=True):
    query = Transaction.objects.filter(owner=user).select_related(
        "account", "destination_account", "area", "category", "subcategory"
    )
    start, end = period_bounds(params, user, optional=optional_period)
    if start:
        query = query.filter(occurred_at__gte=start, occurred_at__lt=end)
    for field in ("account", "area", "category", "subcategory"):
        if params.get(field):
            try:
                identifier = UUID(params[field])
            except ValueError:
                raise ValidationError({field: "UUID inválido."})
            query = (
                query.filter(
                    Q(account_id=identifier)
                    | Q(destination_account_id=identifier)
                )
                if field == "account"
                else query.filter(**{f"{field}_id": identifier})
            )
    for field in ("kind", "status", "payment_method"):
        if field in params and params[field] != "":
            if params[field] not in dict(
                Transaction._meta.get_field(field).choices
            ):
                raise ValidationError({field: "Valor inválido."})
            query = query.filter(**{field: params[field]})
    if params.get("search"):
        query = query.filter(
            Q(description__icontains=params["search"])
            | Q(reference__icontains=params["search"])
        )
    ordering = params.get("ordering", "-occurred_at")
    if ordering.lstrip("-") not in ("occurred_at", "created_at", "amount"):
        raise ValidationError({"ordering": "Ordenamiento no permitido."})
    return query.order_by(ordering, "id")
