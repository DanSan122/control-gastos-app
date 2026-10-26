"""Explicit request scope, entered only by authenticated family URL wrappers."""

from contextvars import ContextVar

current_family = ContextVar("financial_family", default=None)


def scope_filter(user):
    family = current_family.get()
    return {"family": family} if family else {"family__isnull": True, "owner": user}


def scoped(queryset, user):
    return queryset.filter(**scope_filter(user))


def scope_timezone(user):
    family = current_family.get()
    return family.timezone if family else user.timezone


def scope_values(user):
    return {"owner": user, "family": current_family.get()}
