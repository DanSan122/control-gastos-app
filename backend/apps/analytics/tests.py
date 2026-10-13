from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from unittest import skipUnless
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from apps.accounts.models import Account
from apps.categories.models import Category
from apps.transactions.models import Transaction
from apps.transactions.periods import period_bounds
from .services import change


class AnalyticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analytics@example.test", "Bosque!Prueba2026")
        self.other = get_user_model().objects.create_user("analytics-other@example.test", "Bosque!Prueba2026")
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.account = Account.objects.create(owner=self.user, name="Banco", kind="BANK", initial_balance=Decimal("100"))
        self.card = Account.objects.create(owner=self.user, name="Tarjeta", kind="CREDIT", initial_balance=Decimal("-20"))
        self.category = Category.objects.filter(owner=self.user, kind="EXPENSE").first()
        self.now = datetime(2026, 3, 15, 12, tzinfo=ZoneInfo("America/Lima"))
        self.clock = patch("django.utils.timezone.now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def movement(self, amount="10.00", occurred="2026-03-10T12:00:00-05:00", **kwargs):
        values = dict(owner=self.user, account=self.account, kind="EXPENSE", amount=Decimal(amount), currency="PEN", category=self.category, area=self.category.area, occurred_at=datetime.fromisoformat(occurred))
        values.update(kwargs)
        return Transaction.objects.create(**values)

    def fetch(self, section="dashboard", query="period=month"):
        response = self.client.get(f"/api/v1/analytics/{section}/?{query}")
        self.assertEqual(response.status_code, 200, response.data)
        return response.json()

    def test_totals_transfer_void_credit_and_owner(self):
        self.movement("30", account=self.card)
        income = Category.objects.filter(owner=self.user, kind="INCOME").first()
        self.movement("200", kind="INCOME", category=income, area=income.area)
        self.movement("40", kind="TRANSFER", destination_account=self.card, category=None, area=None)
        self.movement("999", status="VOID")
        foreign = Account.objects.create(owner=self.other, name="Otra")
        self.movement("1000", owner=self.other, account=foreign)
        data = self.fetch()
        self.assertEqual((data["income"], data["expense"], data["net_flow"]), ("200.00", "30.00", "170.00"))
        self.assertEqual((data["asset_balances"], data["credit_debt"], data["net_worth"]), ("260.00", "10.00", "250.00"))
        self.assertEqual(data["average_daily_expense"], "2.00")
        self.assertEqual(data["top_category"]["amount"], "30.00")
        self.assertEqual(len(data["accounts"]), 2)

    def test_timezone_half_open_bounds_and_zero_buckets(self):
        self.movement("1", "2026-03-01T04:59:59+00:00")
        self.movement("2", "2026-03-01T05:00:00+00:00")
        self.movement("4", "2026-03-02T05:00:00+00:00")
        data = self.fetch("evolution", "period=custom&start=2026-03-01&end=2026-03-01")
        self.assertEqual(data["expense"], "2.00")
        self.assertEqual(len(data["evolution"]["points"]), 1)
        data = self.fetch("evolution", "period=custom&start=2026-03-01&end=2026-03-03")
        self.assertEqual(len(data["evolution"]["points"]), 3)
        self.assertEqual(data["evolution"]["points"][-1]["accumulated"], "6.00")
        self.assertEqual(data["evolution"]["points"][-1]["expense"], "0.00")
        for point in data["evolution"]["points"]:
            self.assertIsInstance(point["expense_plot"], int)

    def test_equivalent_previous_period_partial_day(self):
        self.movement("8", "2026-03-14T13:00:00-05:00")
        self.movement("4", "2026-03-15T09:00:00-05:00")
        data = self.fetch("comparison", "period=day")
        self.assertEqual(data["comparison"]["start"], "2026-03-14T12:00:00-05:00")
        self.assertEqual(data["comparison"]["end_exclusive"], "2026-03-15T00:00:00-05:00")
        expense = data["comparison"]["points"][1]
        self.assertEqual(expense["change"]["percent"], "-50.00")

    def test_empty_and_zero_comparison(self):
        data = self.fetch()
        self.assertEqual(data["expense"], "0.00")
        self.assertIsNone(data["top_category"])
        self.assertEqual(data["areas"], [])
        self.assertEqual(data["comparison"]["points"][0]["change"], {"percent": "0.00", "status": "both_zero"})
        self.assertEqual(change(Decimal("10"), Decimal("0")), {"percent": None, "status": "no_base"})
        self.assertEqual(change(Decimal("-5"), Decimal("-10"))["percent"], "50.00")

    def test_periods_and_grouping(self):
        expected = {"day": "2026-03-15", "yesterday": "2026-03-14", "week": "2026-03-09", "previous_week": "2026-03-02", "month": "2026-03-01", "previous_month": "2026-02-01", "year": "2026-01-01"}
        for period, start in expected.items():
            self.assertEqual(period_bounds({"period": period}, self.user)[0].date().isoformat(), start)
        self.movement("12")
        for granularity in ("weekly", "monthly"):
            data = self.fetch("evolution", f"period=month&granularity={granularity}")
            self.assertEqual(data["evolution"]["points"][-1]["accumulated"], "12.00")

    def test_validation_private_and_read_only(self):
        for query in ("currency=USD", "granularity=invalid", "period=decade", "period=custom&start=2027-01-01&end=2027-01-02", "period=custom&start=bad&end=bad", "period=custom&start=0001-01-01&end=0001-01-01"):
            self.assertEqual(self.client.get(f"/api/v1/analytics/dashboard/?{query}").status_code, 400)
        token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        self.assertEqual(self.client.post("/api/v1/analytics/dashboard/", {}, format="json", HTTP_X_CSRFTOKEN=token).status_code, 405)
        self.client.logout()
        for section in ("dashboard", "evolution", "distribution", "comparison"):
            self.assertEqual(self.client.get(f"/api/v1/analytics/{section}/").status_code, 403)

    @skipUnless(connection.vendor == "postgresql", "NUMERIC extremo requiere PostgreSQL; SQLite redondea este valor.")
    def test_decimal_extreme_precision(self):
        self.movement("9999999999999999.99")
        data = self.fetch("distribution")
        self.assertEqual(data["categories"][0]["amount"], "9999999999999999.99")
        self.assertEqual(data["categories"][0]["weight"], 1000000)

    def test_daylight_saving_uses_local_calendar_boundaries(self):
        self.user.timezone = "America/New_York"
        self.user.save(update_fields=["timezone"])
        data = self.fetch("comparison", "period=custom&start=2026-03-08&end=2026-03-08")
        self.assertEqual(data["start"], "2026-03-08T00:00:00-05:00")
        self.assertEqual(data["end_exclusive"], "2026-03-09T00:00:00-04:00")
        self.assertEqual(data["comparison"]["start"], "2026-03-07T00:00:00-05:00")

    def test_dashboard_accounts_do_not_add_queries_or_mutate_ledger(self):
        self.movement("12")
        original = list(Transaction.objects.values("id", "amount", "status", "updated_at"))
        with CaptureQueriesContext(connection) as before:
            self.fetch()
        for index in range(15):
            Account.objects.create(owner=self.user, name=f"Cuenta {index}")
        with CaptureQueriesContext(connection) as after:
            self.fetch()
        self.assertEqual(len(before), len(after))
        self.assertEqual(original, list(Transaction.objects.values("id", "amount", "status", "updated_at")))
