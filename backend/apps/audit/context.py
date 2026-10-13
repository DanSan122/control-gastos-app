from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

current_actor = ContextVar("financial_audit_actor", default=None)


@contextmanager
def audit_scope(user):
    existing = current_actor.get()
    token = current_actor.set(
        existing if existing and existing[0].pk == user.pk else (user, uuid4())
    )
    try:
        yield
    finally:
        current_actor.reset(token)
