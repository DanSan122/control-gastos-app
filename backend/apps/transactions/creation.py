from types import SimpleNamespace
from django.db import connection
from apps.audit.context import current_actor
from .serializers import TransactionSerializer
from apps.core.scope import scope_values


def create_movement(
    user, payload, *, request=None, idempotency_key=None, request_hash=""
):
    actor = current_actor.get()
    if not connection.in_atomic_block or not actor or actor[0].pk != user.pk:
        raise RuntimeError("create_movement requires owner_lock")
    serializer = TransactionSerializer(
        data=payload,
        context={"request": request or SimpleNamespace(user=user)},
    )
    serializer.is_valid(raise_exception=True)
    return serializer.save(
        **scope_values(user), idempotency_key=idempotency_key, request_hash=request_hash
    )
