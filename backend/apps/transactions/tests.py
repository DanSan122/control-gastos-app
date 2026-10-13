from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.categories.catalog import seed_catalog
from apps.categories.models import Area, Category, Subcategory
from .models import Transaction
from .services import account_balance

User = get_user_model()


class FinanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("finance@example.test", "Prueba!Bosque2026")
        self.other = User.objects.create_user("other-finance@example.test", "Prueba!Bosque2026")
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.account = Account.objects.create(owner=self.user, name="Banco", kind="BANK", initial_balance=Decimal("100.00"))
        self.destination = Account.objects.create(owner=self.user, name="Efectivo", kind="CASH")
        self.foreign = Account.objects.create(owner=self.other, name="Ajena", kind="BANK")
        self.expense = Category.objects.filter(owner=self.user, kind="EXPENSE").first()
        self.income = Category.objects.filter(owner=self.user, kind="INCOME").first()
        self.sub = Subcategory.objects.get(category=self.expense)

    def send(self, url, data=None, method="post", csrf=True, **headers):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = token
        return getattr(self.client, method)(f"/api/v1/{url}", data or {}, format="json", HTTP_ORIGIN="http://localhost:5173", **headers)

    def payload(self, kind="EXPENSE", **extra):
        category = self.income if kind == "INCOME" else self.expense
        return {"kind": kind, "account": str(self.account.id), "amount": "10.25", "currency": "PEN",
                "area": str(category.area_id), "category": str(category.id),
                "occurred_at": "2026-01-15T12:00:00-05:00", **extra}

    def transfer(self, **extra):
        return {"account": str(self.account.id), "destination_account": str(self.destination.id),
                "amount": "20.00", "occurred_at": "2026-01-15T12:00:00-05:00", **extra}

    def test_account_crud_and_balance(self):
        response = self.send("accounts/", {"name": "Yape propio", "kind": "WALLET", "initial_balance": "25.50"})
        self.assertEqual(response.status_code, 201, response.data)
        identifier = response.json()["id"]
        self.assertEqual(response.json()["balance"], "25.50")
        self.assertEqual(self.client.get(f"/api/v1/accounts/{identifier}/").status_code, 200)
        self.assertEqual(self.send(f"accounts/{identifier}/", {"name": "Billetera"}, "patch").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/accounts/{identifier}/balance/").json()["balance"], "25.50")
        self.assertEqual(self.send(f"accounts/{identifier}/", method="delete").status_code, 204)
        self.assertFalse(Account.objects.get(pk=identifier).is_active)
        self.assertEqual(self.client.get("/api/v1/accounts/?active=true").json()["count"], 2)

    def test_account_duplicate_currency_and_credit_opening(self):
        for data in ({"name": "BANCO", "kind": "BANK"}, {"name": "USD", "kind": "BANK", "currency": "USD"},
                     {"name": "Tarjeta", "kind": "CREDIT", "initial_balance": "500.00"},
                     {"name": "Float", "kind": "BANK", "initial_balance": 0.1}):
            self.assertEqual(self.send("accounts/", data).status_code, 400)

    def test_account_financial_fields_frozen_after_history(self):
        response = self.send("transactions/", self.payload())
        self.send(f"transactions/{response.json()['id']}/", method="delete")
        for data in ({"initial_balance": "500.00"}, {"kind": "CREDIT"}):
            self.assertEqual(self.send(f"accounts/{self.account.id}/", data, "patch").status_code, 400)

    def test_catalog_idempotent_preserves_rename_and_inactive(self):
        area = Area.objects.filter(owner=self.user).first()
        area.name = "Renombrada"
        area.is_active = False
        area.save()
        for _ in range(2):
            seed_catalog(self.user)
        self.assertEqual(Area.objects.filter(owner=self.user).count(), 9)
        self.assertEqual(Category.objects.filter(owner=self.user).count(), 11)
        area.refresh_from_db()
        self.assertEqual(area.name, "Renombrada")
        self.assertFalse(area.is_active)

    def test_classification_crud(self):
        area = self.send("areas/", {"name": "Mascotas"})
        self.assertEqual(area.status_code, 201, area.data)
        aid = area.json()["id"]
        category = self.send("categories/", {"name": "Veterinaria", "area": aid, "kind": "EXPENSE"})
        self.assertEqual(category.status_code, 201, category.data)
        cid = category.json()["id"]
        self.assertEqual(category.json()["area"], aid)
        sub = self.send("subcategories/", {"name": "Consultas", "category": cid})
        self.assertEqual(sub.status_code, 201, sub.data)
        for route, identifier in [("areas", aid), ("categories", cid), ("subcategories", sub.json()["id"])]:
            self.assertEqual(self.client.get(f"/api/v1/{route}/{identifier}/").status_code, 200)
            self.assertEqual(self.send(f"{route}/{identifier}/", {"name": "Actualizada"}, "patch").status_code, 200)
            self.assertEqual(self.send(f"{route}/{identifier}/", method="delete").status_code, 204)

    def test_classification_foreign_parent_and_history(self):
        foreign_area = Area.objects.filter(owner=self.other).first()
        self.assertEqual(self.send("categories/", {"name": "Intrusión", "kind": "EXPENSE", "area": str(foreign_area.id)}).status_code, 400)
        self.send("transactions/", self.payload(subcategory=str(self.sub.id)))
        self.assertEqual(self.send(f"categories/{self.expense.id}/", {"kind": "INCOME"}, "patch").status_code, 400)
        other_area = Area.objects.filter(owner=self.user).exclude(pk=self.expense.area_id).first()
        self.assertEqual(self.send(f"categories/{self.expense.id}/", {"area": str(other_area.id)}, "patch").status_code, 400)
        self.assertEqual(self.send(f"areas/{self.expense.area_id}/", method="delete").status_code, 204)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(self.send("transactions/", self.payload()).status_code, 400)

    def test_income_expense_edit_void_and_balance(self):
        expense = self.send("transactions/", self.payload(payment_method="YAPE", reference="op-1", subcategory=str(self.sub.id)))
        self.assertEqual(expense.status_code, 201, expense.data)
        self.assertEqual(expense.json()["account"], str(self.account.id))
        income = self.send("transactions/", self.payload("INCOME", amount="50.10"))
        self.assertEqual(income.status_code, 201, income.data)
        self.assertEqual(account_balance(self.account), Decimal("139.85"))
        identifier = expense.json()["id"]
        updated = self.send(f"transactions/{identifier}/", {"amount": "20.00", "description": "Corregido"}, "patch")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(account_balance(self.account), Decimal("130.10"))
        self.assertEqual(self.send(f"transactions/{identifier}/", method="delete").status_code, 204)
        self.assertEqual(account_balance(self.account), Decimal("150.10"))
        self.assertEqual(Transaction.objects.get(pk=identifier).status, "VOID")
        self.assertEqual(self.send(f"transactions/{identifier}/", {"amount": "1.00"}, "patch").status_code, 400)

    def test_amount_validation(self):
        for value in [0.1, 10, "0.00", "-1.00", "1.001", "NaN", "Infinity", "99999999999999999.00"]:
            with self.subTest(value=value):
                self.assertEqual(self.send("transactions/", self.payload(amount=value)).status_code, 400)
        self.assertEqual(self.send("transactions/", self.payload(amount="0.01")).status_code, 201)

    def test_timezone_and_dates_validation(self):
        for value in ["2026-01-15T12:00:00", "not-a-date", "2026-02-30T12:00:00-05:00", (timezone.now() + timedelta(days=1)).isoformat()]:
            self.assertEqual(self.send("transactions/", self.payload(occurred_at=value)).status_code, 400)
        response = self.send("transactions/", self.payload(occurred_at="2026-01-15T17:00:00Z"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Transaction.objects.get(pk=response.json()["id"]).occurred_at.hour, 17)

    def test_hierarchy_type_currency_and_ownership(self):
        foreign_category = Category.objects.filter(owner=self.other, kind="EXPENSE").first()
        another_sub = Subcategory.objects.filter(owner=self.user).exclude(category=self.expense).first()
        for overrides in [{"account": str(self.foreign.id)}, {"area": str(self.income.area_id), "category": str(self.income.id)},
                          {"category": str(foreign_category.id)}, {"subcategory": str(another_sub.id)},
                          {"currency": "USD"}, {"owner": str(self.other.id)}, {"status": "VOID"}]:
            self.assertEqual(self.send("transactions/", self.payload(**overrides)).status_code, 400)

    def test_isolation_list_detail_update_delete_and_balance(self):
        own = self.send("transactions/", self.payload()).json()["id"]
        self.client.force_login(self.other)
        for route, identifier in [("accounts", self.account.id), ("areas", self.expense.area_id),
                                  ("categories", self.expense.id), ("subcategories", self.sub.id), ("transactions", own)]:
            self.assertEqual(self.client.get(f"/api/v1/{route}/{identifier}/").status_code, 404)
            self.assertEqual(self.send(f"{route}/{identifier}/", {"description": "hack"}, "patch").status_code, 404)
            self.assertEqual(self.send(f"{route}/{identifier}/", method="delete").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/transactions/").json()["count"], 0)
        self.assertEqual(self.client.get(f"/api/v1/accounts/{self.account.id}/balance/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/reports/summary/?period=custom&start=2026-01-01&end=2026-01-31").json()["expense"], "0.00")

    def test_transfer_idempotency_and_conflict(self):
        key = str(uuid4())
        payload = self.transfer()
        first = self.send("transfers/", payload, HTTP_IDEMPOTENCY_KEY=key)
        repeat = self.send("transfers/", payload, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(first.json()["id"], repeat.json()["id"])
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(account_balance(self.account), Decimal("80.00"))
        self.assertEqual(account_balance(self.destination), Decimal("20.00"))
        self.assertEqual(self.send("transfers/", self.transfer(amount="21.00"), HTTP_IDEMPOTENCY_KEY=key).status_code, 409)
        self.send(f"transactions/{first.json()['id']}/", method="delete")
        self.assertEqual(self.send("transfers/", payload, HTTP_IDEMPOTENCY_KEY=key).json()["status"], "VOID")
        self.assertEqual(account_balance(self.account), Decimal("100.00"))

    def test_invalid_transfer_atomic_no_partial_effects(self):
        for data in [self.transfer(destination_account=str(self.account.id)), self.transfer(destination_account=str(self.foreign.id)),
                     self.transfer(area=str(self.expense.area_id)), self.transfer(amount="0"), self.transfer(currency="USD")]:
            self.assertEqual(self.send("transfers/", data, HTTP_IDEMPOTENCY_KEY=str(uuid4())).status_code, 400)
        self.assertEqual(self.send("transfers/", self.transfer()).status_code, 400)
        self.assertEqual(self.send("transactions/", self.transfer(kind="TRANSFER")).status_code, 400)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(account_balance(self.account), Decimal("100.00"))

    def test_transfer_rollback_after_database_write(self):
        from unittest.mock import patch
        from rest_framework.exceptions import ValidationError
        from .serializers import TransactionSerializer
        original = TransactionSerializer.save
        def fail_after_save(serializer, **kwargs):
            original(serializer, **kwargs)
            raise ValidationError("Fallo simulado después de escribir.")
        with patch.object(TransactionSerializer, "save", fail_after_save):
            response = self.send("transfers/", self.transfer(), HTTP_IDEMPOTENCY_KEY=str(uuid4()))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(account_balance(self.account), Decimal("100.00"))
        self.assertEqual(account_balance(self.destination), Decimal("0.00"))

    def test_malformed_payloads_are_validation_errors(self):
        for path in ("transactions/", "transfers/"):
            token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
            response = self.client.post(f"/api/v1/{path}", ["invalid"], format="json", HTTP_X_CSRFTOKEN=token,
                HTTP_ORIGIN="http://localhost:5173", HTTP_IDEMPOTENCY_KEY=str(uuid4()))
            self.assertEqual(response.status_code, 400)

    def test_same_idempotency_key_is_scoped_per_user(self):
        key = str(uuid4())
        first = self.send("transfers/", self.transfer(), HTTP_IDEMPOTENCY_KEY=key)
        self.client.force_login(self.other)
        target = Account.objects.create(owner=self.other, name="Destino ajeno", kind="CASH")
        second = self.send("transfers/", self.transfer(account=str(self.foreign.pk), destination_account=str(target.pk)), HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(first.json()["id"], second.json()["id"])

    def test_transfer_edit_reverses_both_effects(self):
        response = self.send("transfers/", self.transfer(), HTTP_IDEMPOTENCY_KEY=str(uuid4()))
        updated = self.send(f"transactions/{response.json()['id']}/", {"amount": "35.50"}, "patch")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(account_balance(self.account), Decimal("64.50"))
        self.assertEqual(account_balance(self.destination), Decimal("35.50"))

    def test_credit_purchase_and_debt_payment_not_double_counted(self):
        credit = Account.objects.create(owner=self.user, name="Tarjeta", kind="CREDIT", initial_balance=Decimal("-40.00"))
        self.send("transactions/", self.payload(account=str(credit.id), amount="30.00"))
        self.send("transfers/", self.transfer(destination_account=str(credit.id), amount="50.00"), HTTP_IDEMPOTENCY_KEY=str(uuid4()))
        self.assertEqual(account_balance(credit), Decimal("-20.00"))
        summary = self.client.get("/api/v1/reports/summary/?period=custom&start=2026-01-01&end=2026-01-31").json()
        self.assertEqual((summary["income"], summary["expense"], summary["net_flow"]), ("0.00", "30.00", "-30.00"))
        self.assertEqual(summary["credit_debt"], "20.00")
        self.assertEqual(summary["net_worth"], "30.00")

    def test_reports_decimal_breakdowns_and_evolution(self):
        self.send("transactions/", self.payload(amount="0.10"))
        self.send("transactions/", self.payload(amount="0.20"))
        self.send("transactions/", self.payload("INCOME", amount="100.00"))
        self.send("transfers/", self.transfer(), HTTP_IDEMPOTENCY_KEY=str(uuid4()))
        report = self.client.get("/api/v1/reports/summary/?period=custom&start=2026-01-01&end=2026-01-31").json()
        self.assertEqual((report["expense"], report["net_flow"]), ("0.30", "99.70"))
        self.assertEqual(report["expenses_by_area"][0]["amount"], "0.30")
        for granularity in ("daily", "weekly", "monthly"):
            self.assertEqual(report["evolution"][granularity][0]["expense"], "0.30")
        self.assertEqual(report["net_worth"], "199.70")

    def test_local_period_bounds_and_account_destination_filter(self):
        self.send("transactions/", self.payload(occurred_at="2026-02-01T04:59:59Z"))
        self.send("transactions/", self.payload(occurred_at="2026-02-01T05:00:00Z"))
        response = self.client.get("/api/v1/transactions/?period=custom&start=2026-01-31&end=2026-01-31")
        self.assertEqual(response.json()["count"], 1)
        self.send("transfers/", self.transfer(), HTTP_IDEMPOTENCY_KEY=str(uuid4()))
        self.assertEqual(self.client.get(f"/api/v1/transactions/?account={self.destination.id}").json()["count"], 1)
        report = self.client.get("/api/v1/reports/summary/?period=custom&start=2026-01-31&end=2026-01-31").json()
        self.assertEqual(report["expense"], "10.25")
        self.assertEqual(report["evolution"]["daily"][0]["date"], "2026-01-31")

    def test_user_timezone_controls_filters(self):
        self.user.timezone = "Asia/Tokyo"
        self.user.save(update_fields=["timezone"])
        self.send("transactions/", self.payload(occurred_at="2026-01-15T16:00:00Z"))
        self.assertEqual(self.client.get("/api/v1/transactions/?period=custom&start=2026-01-16&end=2026-01-16").json()["count"], 1)

    def test_filters_ordering_pagination_and_invalid_queries(self):
        for amount in ("10.00", "20.00", "30.00"):
            self.send("transactions/", self.payload(amount=amount, description="Mercado"))
        response = self.client.get("/api/v1/transactions/?kind=EXPENSE&search=mercado&ordering=-amount&page_size=2")
        self.assertEqual(response.json()["count"], 3)
        self.assertEqual(response.json()["results"][0]["amount"], "30.00")
        self.assertIsNotNone(response.json()["next"])
        for query in ["period=custom&start=invalid&end=2026-01-01", "period=decade", "ordering=owner", "account=invalid", "status=wrong"]:
            self.assertEqual(self.client.get(f"/api/v1/transactions/?{query}").status_code, 400)

    def test_csrf_and_anonymous_permissions(self):
        for path, data in [("accounts/", {"name": "X", "kind": "CASH"}), ("areas/", {"name": "X"}),
                           ("categories/", {}), ("subcategories/", {}), ("transactions/", self.payload()), ("transfers/", self.transfer())]:
            self.assertEqual(self.send(path, data, csrf=False).status_code, 403)
        self.client.logout()
        for path in ("accounts/", "areas/", "categories/", "subcategories/", "transactions/", "reports/summary/"):
            self.assertEqual(self.client.get(f"/api/v1/{path}").status_code, 403)

    def test_database_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(owner=self.user, account=self.account, kind="EXPENSE", amount=Decimal("0"),
                area=self.expense.area, category=self.expense, occurred_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(owner=self.user, account=self.account, destination_account=self.account,
                kind="TRANSFER", amount=Decimal("1"), occurred_at=timezone.now())


@skipUnless(connection.vendor == "postgresql", "Bloqueos de concurrencia requieren PostgreSQL")
class TransferConcurrencyTests(TransactionTestCase):
    def test_concurrent_retries_create_one_transfer(self):
        user = User.objects.create_user("concurrency@example.test", "Prueba!Bosque2026")
        source = Account.objects.create(owner=user, name="Origen", kind="BANK", initial_balance=Decimal("100"))
        target = Account.objects.create(owner=user, name="Destino", kind="BANK")
        key = str(uuid4())
        payload = {"account": str(source.pk), "destination_account": str(target.pk), "amount": "15.25", "occurred_at": "2026-01-15T12:00:00-05:00"}
        def attempt(_):
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                client.force_login(User.objects.get(pk=user.pk))
                token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
                return client.post("/api/v1/transfers/", payload, format="json", HTTP_X_CSRFTOKEN=token,
                    HTTP_IDEMPOTENCY_KEY=key, HTTP_ORIGIN="http://localhost:5173").status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=5) as pool:
            statuses = list(pool.map(attempt, range(5)))
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(200), 4)
        self.assertEqual(Transaction.objects.filter(owner=user).count(), 1)
        self.assertEqual(account_balance(source), Decimal("84.75"))
        self.assertEqual(account_balance(target), Decimal("15.25"))
