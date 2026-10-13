from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import Account
from apps.categories.models import Category
from apps.core.finance import owner_lock
from apps.transactions.models import Transaction
from .models import AuditEvent


class AuditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "audit@example.test", "Bosque!Prueba2026"
        )
        self.other = get_user_model().objects.create_user(
            "audit-other@example.test", "Bosque!Prueba2026"
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.account = Account.objects.create(owner=self.user, name="Banco")
        self.category = Category.objects.filter(
            owner=self.user, kind="EXPENSE"
        ).first()
        self.payload = {
            "account": str(self.account.pk),
            "kind": "EXPENSE",
            "amount": "10.00",
            "category": str(self.category.pk),
            "area": str(self.category.area_id),
            "occurred_at": "2026-01-10T12:00:00-05:00",
        }

    def send(self, path, data=None, method="post", **headers):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        return getattr(self.client, method)(
            f"/api/v1/{path}",
            data or {},
            format="json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="http://localhost:5173",
            **headers,
        )

    def test_creation_edit_void_and_noop(self):
        identifier = self.send("transactions/", self.payload).json()["id"]
        self.send(f"transactions/{identifier}/", {"amount": "12.00"}, "patch")
        self.send(f"transactions/{identifier}/", {}, "delete")
        self.send(f"transactions/{identifier}/", {}, "delete")
        events = list(
            AuditEvent.objects.filter(resource_id=identifier).order_by(
                "occurred_at"
            )
        )
        self.assertEqual(
            [event.operation for event in events], ["CREATE", "UPDATE", "VOID"]
        )
        self.assertEqual(events[1].before["amount"], "10.00")
        self.assertEqual(events[1].after["amount"], "12.00")
        self.assertEqual(events[0].before, {})
        self.assertTrue(
            all(event.actor_id == self.user.pk for event in events)
        )

    def test_redacted_changes_are_recorded_without_content(self):
        identifier = self.send("transactions/", self.payload).json()["id"]
        self.send(
            f"transactions/{identifier}/",
            {"description": "dato privado", "reference": "referencia privada"},
            "patch",
        )
        event = AuditEvent.objects.filter(resource_id=identifier).first()
        self.assertEqual(event.operation, "UPDATE")
        self.assertIn("description", event.changed_fields)
        self.assertNotIn("description", event.before)
        self.assertNotIn("reference", event.after)
        self.assertNotIn("dato privado", str(event.after))

    def test_accounts_classifications_and_budgets(self):
        account = self.send(
            "accounts/",
            {"name": "Nueva", "kind": "BANK", "initial_balance": "5.00"},
        ).json()
        self.send(f"accounts/{account['id']}/", {"name": "Editada"}, "patch")
        self.send(f"accounts/{account['id']}/", method="delete")
        self.assertEqual(
            AuditEvent.objects.filter(resource_id=account["id"]).count(), 3
        )
        self.send(f"categories/{self.category.pk}/", {"name": "Otra"}, "patch")
        self.assertTrue(
            AuditEvent.objects.filter(
                resource_type="categories.category", operation="UPDATE"
            ).exists()
        )
        budget = self.send(
            "budgets/",
            {
                "area": str(self.category.area_id),
                "limit_amount": "100",
                "year": 2026,
                "month": 1,
            },
        ).json()
        self.send(f"budgets/{budget['id']}/", {"limit_amount": "80"}, "patch")
        self.send(f"budgets/{budget['id']}/", method="delete")
        self.assertEqual(
            AuditEvent.objects.filter(resource_id=budget["id"]).count(), 3
        )

    def test_transfer_retry_only_one_event(self):
        destination = Account.objects.create(owner=self.user, name="Destino")
        key = str(uuid4())
        data = {
            "account": str(self.account.pk),
            "destination_account": str(destination.pk),
            "amount": "20.00",
            "occurred_at": self.payload["occurred_at"],
        }
        first = self.send("transfers/", data, HTTP_IDEMPOTENCY_KEY=key)
        second = self.send("transfers/", data, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        event = AuditEvent.objects.get(resource_id=first.json()["id"])
        self.assertEqual(str(event.correlation_id), key)

    def test_audit_failure_rolls_back_financial_operation(self):
        with patch(
            "apps.audit.signals.AuditEvent.objects.create",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.send("transactions/", self.payload)
        self.assertEqual(
            Transaction.objects.filter(owner=self.user).count(), 0
        )
        self.assertEqual(AuditEvent.objects.filter(actor=self.user).count(), 0)

    def test_domain_rollback_and_append_only_models(self):
        with self.assertRaises(RuntimeError):
            with owner_lock(self.user):
                Account.objects.create(owner=self.user, name="Revertida")
                raise RuntimeError("rollback")
        self.assertFalse(Account.objects.filter(name="Revertida").exists())
        self.assertEqual(AuditEvent.objects.count(), 0)
        with owner_lock(self.user):
            account = Account.objects.create(owner=self.user, name="Auditable")
        event = AuditEvent.objects.get(resource_id=account.pk)
        for operation in (
            lambda: event.save(),
            lambda: event.delete(),
            lambda: AuditEvent.objects.filter(pk=event.pk).update(
                operation="UPDATE"
            ),
            lambda: AuditEvent.objects.filter(pk=event.pk).delete(),
            lambda: AuditEvent(
                id=event.pk, actor=self.user, resource_id=account.pk
            ).save(),
        ):
            with self.assertRaises(ValidationError):
                operation()

    @skipUnless(
        connection.vendor == "postgresql", "Trigger requiere PostgreSQL"
    )
    def test_database_trigger(self):
        with owner_lock(self.user):
            Account.objects.create(owner=self.user, name="Protegida")
        event = AuditEvent.objects.first()
        for sql in (
            "UPDATE audit_auditevent SET operation='UPDATE' WHERE id=%s",
            "DELETE FROM audit_auditevent WHERE id=%s",
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, [event.pk])
        self.assertTrue(AuditEvent.objects.filter(pk=event.pk).exists())

    def test_private_api_isolation_filters_and_no_write(self):
        with owner_lock(self.other):
            account = Account.objects.create(owner=self.other, name="Ajena")
        foreign = AuditEvent.objects.get(resource_id=account.pk)
        self.assertEqual(
            self.client.get("/api/v1/audit/events/").json()["count"], 0
        )
        self.assertEqual(
            self.client.get(f"/api/v1/audit/events/{foreign.pk}/").status_code,
            404,
        )
        identifier = self.send("transactions/", self.payload).json()["id"]
        response = self.client.get(
            f"/api/v1/audit/events/?resource_id={identifier}&resource_type=transactions.transaction"
        )
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(
            response.json()["results"][0]["occurred_at"].endswith("Z")
        )
        self.assertEqual(self.send("audit/events/", {}).status_code, 405)
        for query in ("resource_id=bad", "operation=bad", "resource_type=bad"):
            self.assertEqual(
                self.client.get(f"/api/v1/audit/events/?{query}").status_code,
                400,
            )
        self.client.logout()
        self.assertEqual(
            self.client.get("/api/v1/audit/events/").status_code, 403
        )
