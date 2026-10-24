from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone as utc
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import (
    connection,
    close_old_connections,
    IntegrityError,
    transaction,
)
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from apps.accounts.models import Account
from apps.audit.models import AuditEvent
from apps.budgets.models import Budget
from apps.categories.models import Category
from apps.transactions.models import Transaction
from apps.transactions.services import account_balance
from .calendar import next_date, effective_at
from .models import RecurringRule, RecurringExecution
from .services import execute, process, prepare_next


class CalendarTests(TestCase):
    def rule(self, start, frequency="MONTHLY", interval=1):
        return SimpleNamespace(
            start_date=date.fromisoformat(start),
            frequency=frequency,
            interval=interval,
        )

    def test_month_end_without_drift(self):
        for day in (29, 30, 31):
            rule = self.rule(f"2027-01-{day}")
            february = next_date(rule, rule.start_date)
            self.assertEqual(february, date(2027, 2, 28))
            self.assertEqual(next_date(rule, february), date(2027, 3, day))

    def test_monthly_leap_and_multi_interval(self):
        rule = self.rule("2024-01-31")
        self.assertEqual(next_date(rule, rule.start_date), date(2024, 2, 29))
        rule.interval = 3
        april = next_date(rule, rule.start_date)
        self.assertEqual(april, date(2024, 4, 30))
        self.assertEqual(next_date(rule, april), date(2024, 7, 31))

    def test_daily_weekly_yearly(self):
        self.assertEqual(
            next_date(self.rule("2024-02-28", "DAILY", 2), date(2024, 2, 28)),
            date(2024, 3, 1),
        )
        self.assertEqual(
            next_date(self.rule("2026-01-01", "WEEKLY", 2), date(2026, 1, 1)),
            date(2026, 1, 15),
        )
        rule = self.rule("2024-02-29", "YEARLY")
        current = rule.start_date
        for year in range(2025, 2029):
            current = next_date(rule, current)
            self.assertEqual(
                current, date(year, 2, 29 if year == 2028 else 28)
            )

    def test_timezone_and_skipped_calendar_date(self):
        self.assertEqual(
            effective_at(date(2026, 1, 31), "America/Lima"),
            datetime(2026, 1, 31, 5, tzinfo=utc.utc),
        )
        self.assertEqual(
            effective_at(date(2026, 3, 9), "America/New_York").hour, 4
        )
        with self.assertRaises(ValueError):
            effective_at(date(2011, 12, 30), "Pacific/Apia")

    def test_calendar_exhaustion(self):
        self.assertIsNone(
            next_date(
                self.rule("9998-01-01", "YEARLY", 1000), date(9998, 1, 1)
            )
        )


class RecurringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "recurring@example.test", "Bosque!Prueba2026"
        )
        self.other = get_user_model().objects.create_user(
            "recurring-other@example.test", "Bosque!Prueba2026"
        )
        self.account = Account.objects.create(
            owner=self.user,
            name="Banco",
            kind="BANK",
            initial_balance=Decimal("100"),
        )
        self.category = Category.objects.filter(
            owner=self.user, kind="EXPENSE"
        ).first()
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.now = datetime(2026, 10, 13, 15, tzinfo=ZoneInfo("America/Lima"))
        self.clock = patch("django.utils.timezone.now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.payload = {
            "name": "Gasto mensual",
            "kind": "EXPENSE",
            "amount": "10.25",
            "currency": "PEN",
            "source_account": str(self.account.pk),
            "area": str(self.category.area_id),
            "category": str(self.category.pk),
            "frequency": "MONTHLY",
            "interval": 1,
            "start_date": "2026-01-31",
            "execution_mode": "MANUAL",
        }

    def send(self, path, data=None, method="post", csrf=True):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        return getattr(self.client, method)(
            f"/api/v1/recurring/{path}",
            data or {},
            format="json",
            HTTP_ORIGIN="http://localhost:5173",
            **({"HTTP_X_CSRFTOKEN": token} if csrf else {}),
        )

    def create(self, **extra):
        response = self.send("rules/", {**self.payload, **extra})
        self.assertEqual(response.status_code, 201, response.data)
        rule = RecurringRule.objects.get(pk=response.json()["id"])
        return rule, rule.executions.get()

    def test_crud_filters_and_soft_cancel(self):
        rule, execution = self.create()
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(
            self.send(
                f"rules/{rule.pk}/",
                {"name": "Renombrada", "amount": "20.00"},
                "patch",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/recurring/rules/?kind=EXPENSE&status=ACTIVE&frequency=MONTHLY&page_size=1"
            ).json()["count"],
            1,
        )
        self.assertEqual(
            self.send(f"rules/{rule.pk}/", method="delete").status_code, 204
        )
        rule.refresh_from_db()
        self.assertEqual(rule.status, "CANCELLED")
        self.assertTrue(
            RecurringExecution.objects.filter(pk=execution.pk).exists()
        )
        self.assertEqual(
            self.send(f"executions/{execution.pk}/confirm/").status_code, 400
        )
        self.assertEqual(
            self.send(f"rules/{rule.pk}/resume/").status_code, 400
        )

    def test_manual_confirm_exact_idempotent_and_cursor(self):
        rule, occurrence = self.create()
        first = self.send(f"executions/{occurrence.pk}/confirm/")
        second = self.send(f"executions/{occurrence.pk}/confirm/")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(
            first.json()["transaction"], second.json()["transaction"]
        )
        self.assertEqual(Transaction.objects.count(), 1)
        movement = Transaction.objects.get()
        self.assertEqual(movement.amount, Decimal("10.25"))
        self.assertEqual(
            movement.occurred_at, datetime(2026, 1, 31, 5, tzinfo=utc.utc)
        )
        rule.refresh_from_db()
        self.assertEqual(rule.next_due_date, date(2026, 2, 28))
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="transactions.transaction"
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="recurring.recurringexecution",
                operation="EXECUTE",
            ).count(),
            1,
        )

    def test_skip_no_financial_effect_and_no_duplicate(self):
        rule, occurrence = self.create()
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/skip/").status_code, 200
        )
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/skip/").status_code, 200
        )
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(account_balance(self.account), Decimal("100"))
        rule.refresh_from_db()
        self.assertEqual(rule.next_due_date, date(2026, 2, 28))
        self.assertEqual(
            AuditEvent.objects.filter(operation="SKIP").count(), 1
        )
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 400
        )

    def test_pause_resume_preserves_overdue(self):
        rule, occurrence = self.create()
        self.assertEqual(self.send(f"rules/{rule.pk}/pause/").status_code, 200)
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 400
        )
        self.assertEqual(
            self.client.get("/api/v1/recurring/upcoming/").json()["count"], 0
        )
        self.assertEqual(
            self.send(f"rules/{rule.pk}/resume/").status_code, 200
        )
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 200
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                operation__in=["PAUSE", "RESUME"]
            ).count(),
            2,
        )

    def test_completion_end_date(self):
        rule, occurrence = self.create(end_date="2026-01-31")
        self.send(f"executions/{occurrence.pk}/confirm/")
        rule.refresh_from_db()
        self.assertEqual(rule.status, "COMPLETED")
        self.assertIsNone(rule.next_due_date)
        self.assertEqual(rule.executions.count(), 1)
        self.assertEqual(
            self.send(f"rules/{rule.pk}/resume/").status_code, 400
        )

    def test_validation_money_hierarchy_and_readonly(self):
        foreign = Account.objects.create(owner=self.other, name="Ajena")
        for extra in (
            {"amount": 1.2},
            {"amount": "0"},
            {"amount": "1.001"},
            {"currency": "USD"},
            {"interval": 0},
            {"interval": 1001},
            {"frequency": "wrong"},
            {"end_date": "2025-01-01"},
            {"source_account": str(foreign.pk)},
            {"status": "ACTIVE"},
            {"owner": str(self.other.pk)},
            {"next_due_date": "2026-01-31"},
            {"timezone": "UTC"},
            {"area": None},
        ):
            self.assertEqual(
                self.send("rules/", {**self.payload, **extra}).status_code,
                400,
                extra,
            )

    def test_income_and_category_kind(self):
        self.assertEqual(
            self.send(
                "rules/", {**self.payload, "kind": "INCOME"}
            ).status_code,
            400,
        )
        income = Category.objects.filter(
            owner=self.user, kind="INCOME"
        ).first()
        rule, occurrence = self.create(
            kind="INCOME", area=str(income.area_id), category=str(income.pk)
        )
        self.send(f"executions/{occurrence.pk}/confirm/")
        self.assertEqual(account_balance(self.account), Decimal("110.25"))

    def test_future_no_confirm_skip_or_automatic(self):
        rule, occurrence = self.create(start_date="2026-10-14")
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 400
        )
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/skip/").status_code, 400
        )
        automatic, _ = self.create(
            name="Futura", start_date="2026-10-14", execution_mode="AUTOMATIC"
        )
        process()
        self.assertEqual(Transaction.objects.count(), 0)

    def test_automatic_command_idempotent_and_manual_untouched(self):
        automatic, occurrence = self.create(
            execution_mode="AUTOMATIC",
            start_date="2026-10-13",
            end_date="2026-10-13",
        )
        manual, pending = self.create(name="Manual")
        output = StringIO()
        call_command("process_recurring", stdout=output)
        call_command("process_recurring", stdout=output)
        occurrence.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(occurrence.status, "EXECUTED")
        self.assertEqual(pending.status, "PENDING")
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertIn("executed=1", output.getvalue())

    def test_failed_validation_can_retry(self):
        rule, occurrence = self.create()
        self.account.is_active = False
        self.account.save()
        failure = self.send(f"executions/{occurrence.pk}/confirm/")
        self.assertEqual(failure.status_code, 422, failure.data)
        self.assertEqual(failure.json()["error_code"], "INVALID_RELATIONS")
        self.assertEqual(Transaction.objects.count(), 0)
        rule.refresh_from_db()
        self.assertEqual(rule.next_due_date, date(2026, 1, 31))
        self.account.is_active = True
        self.account.save()
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 200
        )
        self.assertEqual(Transaction.objects.count(), 1)

    def test_rollback_financial_audit_failure_keeps_pending(self):
        rule, occurrence = self.create()
        before = AuditEvent.objects.count()
        with patch(
            "apps.audit.signals.AuditEvent.objects.create",
            side_effect=RuntimeError("unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                execute(self.user, occurrence.pk)
        occurrence.refresh_from_db()
        rule.refresh_from_db()
        self.assertEqual(occurrence.status, "PENDING")
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertEqual(rule.next_due_date, date(2026, 1, 31))

    def test_database_transient_failure_retry(self):
        from django.db import OperationalError

        rule, occurrence = self.create()
        with patch(
            "apps.recurring.services.create_movement",
            side_effect=OperationalError("temporary"),
        ):
            result = execute(self.user, occurrence.pk)
        self.assertEqual(result.error_code, "TEMPORARY_FAILURE")
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(execute(self.user, occurrence.pk).status, "EXECUTED")

    def test_owner_private_csrf_filters(self):
        rule, occurrence = self.create()
        self.assertEqual(
            self.send(
                f"executions/{occurrence.pk}/confirm/", csrf=False
            ).status_code,
            403,
        )
        self.client.force_login(self.other)
        for path in (f"rules/{rule.pk}/", f"executions/{occurrence.pk}/"):
            self.assertEqual(
                self.client.get(f"/api/v1/recurring/{path}").status_code, 404
            )
        self.assertEqual(self.send(f"rules/{rule.pk}/pause/").status_code, 404)
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/v1/recurring/upcoming/").json()["count"], 0
        )
        self.client.logout()
        for path in ("rules/", "executions/", "upcoming/"):
            self.assertEqual(
                self.client.get(f"/api/v1/recurring/{path}").status_code, 403
            )

    def test_invalid_query_and_actions(self):
        rule, occurrence = self.create()
        for path in (
            "rules/?kind=bad",
            "rules/?frequency=bad",
            "executions/?status=bad",
            "executions/?rule=bad",
            "upcoming/?days=0",
            "upcoming/?days=bad",
        ):
            self.assertEqual(
                self.client.get(f"/api/v1/recurring/{path}").status_code, 400
            )
        self.assertEqual(
            self.send(f"rules/{rule.pk}/pause/", {"owner": "bad"}).status_code,
            400,
        )

    def test_calendar_edits_freeze_after_consumption(self):
        rule, occurrence = self.create()
        self.assertEqual(
            self.send(
                f"rules/{rule.pk}/", {"interval": 2}, "patch"
            ).status_code,
            200,
        )
        self.send(f"executions/{occurrence.pk}/skip/")
        self.assertEqual(
            self.send(
                f"rules/{rule.pk}/", {"interval": 3}, "patch"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.send(
                f"rules/{rule.pk}/", {"start_date": "2026-02-01"}, "patch"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/recurring/rules/{rule.pk}/").json()[
                "calendar_locked"
            ],
            True,
        )

    def test_budget_reports_exclude_pending_and_include_execution(self):
        rule, occurrence = self.create()
        budget = Budget.objects.create(
            owner=self.user,
            area=self.category.area,
            limit_amount=Decimal("100"),
            year=2026,
            month=1,
        )
        report = "/api/v1/reports/preview/?period=custom&start=2026-01-01&end=2026-01-31"
        self.assertEqual(self.client.get(report).json()["expense"], "0.00")
        self.assertEqual(
            self.client.get(f"/api/v1/budgets/{budget.pk}/progress/").json()[
                "consumed"
            ],
            "0.00",
        )
        upcoming = self.client.get("/api/v1/recurring/upcoming/").json()
        self.assertEqual(upcoming["scheduled_totals"]["expense"], "10.25")
        self.send(f"executions/{occurrence.pk}/confirm/")
        self.assertEqual(self.client.get(report).json()["expense"], "10.25")
        self.assertEqual(
            self.client.get(f"/api/v1/budgets/{budget.pk}/progress/").json()[
                "consumed"
            ],
            "10.25",
        )

    def test_transfer_no_double_accounting_and_void_retry(self):
        destination = Account.objects.create(
            owner=self.user,
            name="Tarjeta",
            kind="CREDIT",
            initial_balance=Decimal("-50"),
        )
        rule, occurrence = self.create(
            kind="TRANSFER",
            area=None,
            category=None,
            destination_account=str(destination.pk),
            amount="20.00",
        )
        response = self.send(f"executions/{occurrence.pk}/confirm/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(account_balance(self.account), Decimal("80"))
        self.assertEqual(account_balance(destination), Decimal("-30"))
        self.assertEqual(Transaction.objects.get().kind, "TRANSFER")
        self.assertEqual(
            self.client.get(
                "/api/v1/reports/preview/?period=custom&start=2026-01-01&end=2026-01-31"
            ).json()["expense"],
            "0.00",
        )
        self.send(f"executions/{occurrence.pk}/skip/")
        self.client.delete(
            f"/api/v1/transactions/{response.json()['transaction']}/",
            HTTP_X_CSRFTOKEN=self.client.get("/api/v1/auth/csrf/").json()[
                "csrfToken"
            ],
        )
        self.assertEqual(
            self.send(f"executions/{occurrence.pk}/confirm/").json()[
                "transaction"
            ],
            response.json()["transaction"],
        )
        self.assertEqual(Transaction.objects.count(), 1)

    def test_rule_timezone_is_frozen(self):
        rule, occurrence = self.create()
        self.user.timezone = "Pacific/Auckland"
        self.user.save(update_fields=["timezone"])
        execute(self.user, occurrence.pk)
        self.assertEqual(Transaction.objects.get().occurred_at.hour, 5)
        rule.refresh_from_db()
        self.assertEqual(rule.timezone, "America/Lima")

    def test_execution_history_preserves_real_amount_after_rule_edit(self):
        rule, occurrence = self.create()
        execute(self.user, occurrence.pk)
        self.send(f"rules/{rule.pk}/", {"amount": "50"}, "patch")
        self.assertEqual(
            self.client.get(
                f"/api/v1/recurring/executions/{occurrence.pk}/"
            ).json()["amount"],
            "10.25",
        )

    def test_automatic_failure_backoff_and_later_retry(self):
        rule, occurrence = self.create(
            execution_mode="AUTOMATIC",
            start_date="2026-10-13",
            end_date="2026-10-13",
        )
        self.account.is_active = False
        self.account.save()
        self.assertEqual(process()["failed"], 1)
        self.account.is_active = True
        self.account.save()
        self.assertEqual(process()["executed"], 0)
        with patch(
            "django.utils.timezone.now",
            return_value=self.now + timedelta(seconds=61),
        ):
            self.assertEqual(process()["executed"], 1)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_bounded_backlog_and_paused_cancelled_automatic(self):
        rule, occurrence = self.create(
            execution_mode="AUTOMATIC",
            frequency="DAILY",
            start_date="2026-10-10",
        )
        self.assertEqual(process(per_rule=2)["executed"], 2)
        rule.refresh_from_db()
        self.assertEqual(rule.next_due_date, date(2026, 10, 12))
        self.send(f"rules/{rule.pk}/pause/")
        self.assertEqual(process()["executed"], 0)
        self.send(f"rules/{rule.pk}/resume/")
        self.assertEqual(process(per_rule=2)["executed"], 2)
        rule.refresh_from_db()
        self.assertEqual(rule.next_due_date, date(2026, 10, 14))
        self.send(f"rules/{rule.pk}/", method="delete")
        self.assertEqual(process()["executed"], 0)
        self.assertEqual(Transaction.objects.count(), 4)

    def test_database_constraints_and_unique_occurrence(self):
        rule, occurrence = self.create()
        fields = dict(
            owner=self.user,
            name="Inválida",
            kind="EXPENSE",
            amount=Decimal("10"),
            source_account=self.account,
            area=self.category.area,
            category=self.category,
            frequency="DAILY",
            start_date=date(2026, 1, 1),
            next_due_date=date(2026, 1, 1),
        )
        for changes in (
            {"amount": Decimal("0")},
            {"interval": 0},
            {"currency": "USD"},
            {"end_date": date(2025, 12, 31)},
            {"status": "COMPLETED"},
            {"kind": "TRANSFER"},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RecurringRule.objects.create(**{**fields, **changes})
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecurringExecution.objects.create(
                rule=rule, scheduled_date=occurrence.scheduled_date
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecurringExecution.objects.create(
                rule=rule, scheduled_date=date(2026, 2, 1), status="EXECUTED"
            )

    def test_rule_list_queries_do_not_grow_per_row(self):
        rule, occurrence = self.create()
        with CaptureQueriesContext(connection) as before:
            self.client.get("/api/v1/recurring/rules/")
        for index in range(10):
            RecurringRule.objects.create(owner=self.user, name=f"Regla {index}", kind="EXPENSE", amount=Decimal("10"), source_account=self.account, area=self.category.area, category=self.category, frequency="DAILY", start_date=date(2026, 1, 1), next_due_date=date(2026, 1, 1))
        with CaptureQueriesContext(connection) as after:
            response = self.client.get("/api/v1/recurring/rules/")
        self.assertEqual(response.json()["count"], 11)
        self.assertEqual(len(before), len(after))


@skipUnless(
    connection.vendor == "postgresql", "Concurrencia real requiere PostgreSQL"
)
class RecurringConcurrencyTests(TransactionTestCase):
    def test_two_workers_same_occurrence_create_one_movement(self):
        user = get_user_model().objects.create_user(
            "recurring-race@example.test", "Bosque!Prueba2026"
        )
        account = Account.objects.create(owner=user, name="Banco")
        category = Category.objects.filter(owner=user, kind="EXPENSE").first()
        rule = RecurringRule.objects.create(
            owner=user,
            name="Concurrente",
            kind="EXPENSE",
            amount=Decimal("10"),
            source_account=account,
            area=category.area,
            category=category,
            frequency="DAILY",
            execution_mode="AUTOMATIC",
            start_date=date(2026, 1, 1),
            next_due_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
        )
        from apps.core.finance import owner_lock

        with owner_lock(user):
            occurrence = prepare_next(rule)

        def run(_):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                return execute(
                    actor, occurrence.pk, automatic=True
                ).transaction_id
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="transactions.transaction"
            ).count(),
            1,
        )
