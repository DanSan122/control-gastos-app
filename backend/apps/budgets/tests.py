from datetime import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import Account
from apps.categories.models import Category
from apps.transactions.models import Transaction
from .models import Budget
from .services import progress_for


class BudgetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("budget@example.test", "Bosque!Prueba2026")
        self.other = get_user_model().objects.create_user("budget-other@example.test", "Bosque!Prueba2026")
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.category = Category.objects.filter(owner=self.user, kind="EXPENSE").first()
        self.account = Account.objects.create(owner=self.user, name="Tarjeta", kind="CREDIT")
        self.data = {"area": str(self.category.area_id), "limit_amount": "100.00", "year": 2026, "month": 1}

    def send(self, data, path="budgets/", method="post", csrf=True):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        headers = {"HTTP_X_CSRFTOKEN": token} if csrf else {}
        return getattr(self.client, method)(f"/api/v1/{path}", data, format="json", HTTP_ORIGIN="http://localhost:5173", **headers)

    def expense(self, amount, **extra):
        return Transaction.objects.create(**{**dict(owner=self.user, account=self.account, kind="EXPENSE", area=self.category.area, category=self.category, amount=Decimal(amount), occurred_at=datetime.fromisoformat("2026-01-10T10:00:00-05:00")), **extra})

    def test_crud_duplicate_reactivate_and_soft_delete(self):
        response = self.send(self.data)
        self.assertEqual(response.status_code, 201, response.data)
        identifier = response.json()["id"]
        self.assertEqual(response.json()["progress"]["alert"], "NORMAL")
        self.assertEqual(self.send(self.data).status_code, 400)
        self.assertEqual(self.send({"limit_amount": "120"}, f"budgets/{identifier}/", "patch").status_code, 200)
        self.assertEqual(self.send({}, f"budgets/{identifier}/", "delete").status_code, 204)
        self.assertTrue(Budget.objects.filter(pk=identifier, is_active=False).exists())
        self.assertEqual(self.send(self.data).status_code, 400)
        self.assertEqual(self.send({"is_active": True}, f"budgets/{identifier}/", "patch").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/budgets/?month=1&year=2026&active=true&page_size=1").json()["count"], 1)

    def test_thresholds_and_void_and_transfer(self):
        identifier = self.send(self.data).json()["id"]
        self.expense("79.99")
        path = f"/api/v1/budgets/{identifier}/progress/"
        self.assertEqual(self.client.get(path).json()["alert"], "NORMAL")
        movement = self.expense("0.01")
        self.assertEqual(self.client.get(path).json()["alert"], "WARNING")
        self.expense("20")
        self.assertEqual(self.client.get(path).json()["alert"], "EXCEEDED")
        self.expense("10")
        self.assertEqual(self.client.get(path).json()["available"], "-10.00")
        movement.status = "VOID"
        movement.save()
        self.expense("1000", status="VOID")
        destination = Account.objects.create(owner=self.user, name="Destino")
        self.expense("1000", kind="TRANSFER", area=None, category=None, destination_account=destination)
        self.assertEqual(self.client.get(path).json()["consumed"], "109.99")

    def test_calendar_boundaries_category_scope_and_inactive_history(self):
        identifier = self.send({**self.data, "area": None, "category": str(self.category.pk)}).json()["id"]
        self.expense("1", occurred_at=datetime.fromisoformat("2026-01-01T04:59:59+00:00"))
        self.expense("2", occurred_at=datetime.fromisoformat("2026-01-01T05:00:00+00:00"))
        self.expense("4", occurred_at=datetime.fromisoformat("2026-02-01T05:00:00+00:00"))
        self.category.is_active = False
        self.category.save()
        response = self.client.get(f"/api/v1/budgets/{identifier}/")
        self.assertEqual(response.json()["progress"]["consumed"], "2.00")
        self.assertEqual(self.send({"limit_amount": "200"}, f"budgets/{identifier}/", "patch").status_code, 200)

    def test_validation_and_relations(self):
        foreign = Category.objects.filter(owner=self.other, kind="EXPENSE").first()
        income = Category.objects.filter(owner=self.user, kind="INCOME").first()
        for extra in ({"limit_amount": 10}, {"limit_amount": "0"}, {"limit_amount": "1.001"}, {"year": 10000}, {"month": 13}, {"currency": "USD"}, {"area": None}, {"category": str(self.category.pk)}, {"area": None, "category": str(income.pk)}, {"area": str(foreign.area_id)}, {"owner": str(self.other.pk)}):
            self.assertEqual(self.send({**self.data, **extra}).status_code, 400, extra)

    def test_csrf_private_and_owner(self):
        self.assertEqual(self.send(self.data, csrf=False).status_code, 403)
        budget = Budget.objects.create(owner=self.other, area=Category.objects.filter(owner=self.other).first().area, limit_amount=Decimal("100"), year=2026, month=1)
        for path in (f"budgets/{budget.pk}/", f"budgets/{budget.pk}/progress/"):
            self.assertEqual(self.client.get(f"/api/v1/{path}").status_code, 404)
        self.assertEqual(self.send({"limit_amount": "1"}, f"budgets/{budget.pk}/", "patch").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/budgets/").json()["count"], 0)
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/budgets/").status_code, 403)

    def test_invalid_filters(self):
        for query in ("year=bad", "month=0", "area=bad", "active=yes", "ordering=owner"):
            self.assertEqual(self.client.get(f"/api/v1/budgets/?{query}").status_code, 400)

    def test_grouped_progress_has_no_n_plus_one(self):
        budgets = [Budget.objects.create(owner=self.user, category=c, year=2026, month=1, limit_amount=Decimal("100")) for c in Category.objects.filter(owner=self.user, kind="EXPENSE")]
        budgets = list(Budget.objects.filter(pk__in=[b.pk for b in budgets]).select_related("area", "category__area"))
        with self.assertNumQueries(1):
            values = progress_for(budgets, self.user)
        self.assertEqual(len(values), len(budgets))

    def test_database_constraints(self):
        Budget.objects.create(owner=self.user, area=self.category.area, year=2026, month=1, limit_amount=Decimal("100"))
        for extra in ({}, {"month": 0}, {"area": None}, {"limit_amount": Decimal("0")}, {"category": self.category}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Budget.objects.create(**{**dict(owner=self.user, area=self.category.area, year=2026, month=1, limit_amount=Decimal("100")), **extra})
