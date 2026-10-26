from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections
from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import Account
from apps.categories.models import Area, Category
from apps.transactions.models import Transaction
from apps.budgets.models import Budget
from apps.audit.models import AuditEvent
from .models import Family, FamilyMembership, FamilyInvitation


class FamilyTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = [
            get_user_model().objects.create_user(
                email=f"family-{letter}@example.test",
                password="Test-only-strong-password!",
                first_name=letter.upper(),
            )
            for letter in "abc"
        ]
        self.client = APIClient()
        self.client.force_login(self.a)
        self.family = self.client.post(
            "/api/v1/families/", {"name": "Hogar QA"}, format="json"
        ).data
        self.base = f'/api/v1/families/{self.family["id"]}/'
        self.client.post(
            self.base + "invitations/", {"email": self.b.email}, format="json"
        )
        invitation = FamilyInvitation.objects.get(family_id=self.family["id"])
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/accept/",
                {},
                format="json",
            ).status_code,
            200,
        )
        self.client.force_login(self.a)
        self.account = self.post(
            "accounts/",
            {"name": "Fondo hogar", "kind": "BANK", "initial_balance": "100.00"},
        )
        self.dest = self.post(
            "accounts/",
            {"name": "Tarjeta hogar", "kind": "CREDIT", "initial_balance": "-10.00"},
        )
        self.area = self.post("areas/", {"name": "Hogar"})
        self.category = self.post(
            "categories/",
            {"name": "Servicios", "area": self.area["id"], "kind": "EXPENSE"},
        )
        self.personal = Account.objects.create(
            owner=self.a,
            name="Privado A",
            kind="BANK",
            initial_balance=Decimal("777.00"),
        )

    def post(self, path, data, code=201):
        response = self.client.post(self.base + path, data, format="json")
        self.assertEqual(
            response.status_code, code, getattr(response, "data", response.content)
        )
        return response.data if hasattr(response, "data") else response.json()

    def expense(self, **extra):
        return {
            "kind": "EXPENSE",
            "account": self.account["id"],
            "area": self.area["id"],
            "category": self.category["id"],
            "amount": "0.10",
            "occurred_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
            **extra,
        }

    def test_family_creation_and_multiple_spaces(self):
        self.assertEqual(
            FamilyMembership.objects.get(family_id=self.family["id"], user=self.a).role,
            "ADMIN",
        )
        other = self.client.post(
            "/api/v1/families/", {"name": "Otro hogar"}, format="json"
        )
        self.assertEqual(other.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/families/").data["count"], 2)
        self.assertIsNone(self.personal.family_id)

    def test_unauthenticated_and_foreign_uuid(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "accounts/").status_code, 403)
        self.client.force_login(self.c)
        for path in (
            "",
            "members/",
            "accounts/",
            "transactions/",
            "dashboard/",
            "reports/preview/",
            "audit/events/",
        ):
            self.assertEqual(self.client.get(self.base + path).status_code, 404, path)

    def test_last_admin_and_multiple_admins(self):
        admin = FamilyMembership.objects.get(family_id=self.family["id"], user=self.a)
        self.assertEqual(
            self.client.patch(
                self.base + f"members/{admin.pk}/",
                {"role": None},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(self.base + "leave/", {}, format="json").status_code, 400
        )
        self.assertEqual(
            self.client.patch(
                self.base + f"members/{admin.pk}/", {"role": "MEMBER"}, format="json"
            ).status_code,
            400,
        )
        member = FamilyMembership.objects.get(family_id=self.family["id"], user=self.b)
        self.assertEqual(
            self.client.patch(
                self.base + f"members/{member.pk}/", {"role": "ADMIN"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(self.base + "leave/", {}, format="json").status_code, 204
        )
        self.assertEqual(
            FamilyMembership.objects.filter(
                family_id=self.family["id"], role="ADMIN", status="ACTIVE"
            ).count(),
            1,
        )

    def test_invitation_privacy_duplicate_and_wrong_user(self):
        for email in (self.c.email.upper(), self.c.email, "unknown@example.test"):
            self.assertEqual(
                self.client.post(
                    self.base + "invitations/", {"email": email}, format="json"
                ).status_code,
                202,
            )
        self.assertEqual(
            FamilyInvitation.objects.filter(
                family_id=self.family["id"], status="PENDING"
            ).count(),
            1,
        )
        invitation = FamilyInvitation.objects.get(invited_user=self.c)
        sent = self.client.get(self.base + "invitations/").data["results"]
        self.assertTrue(any(row["invited_email"] == self.c.email for row in sent))
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/accept/",
                {},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(self.base + "invitations/").status_code, 403)

    def test_expired_revoked_rejected(self):
        self.post("invitations/", {"email": self.c.email}, 202)
        invitation = FamilyInvitation.objects.get(invited_user=self.c)
        invitation.expires_at = timezone.now() - timedelta(seconds=1)
        invitation.save()
        self.client.force_login(self.c)
        self.assertEqual(
            self.client.get("/api/v1/families/invitations/mine/").data["results"][0][
                "status"
            ],
            "EXPIRED",
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/accept/",
                {},
                format="json",
            ).status_code,
            409,
        )
        self.client.force_login(self.a)
        self.post("invitations/", {"email": self.c.email}, 202)
        invitation = FamilyInvitation.objects.get(invited_user=self.c, status="PENDING")
        self.post(f"invitations/{invitation.pk}/revoke/", {}, 200)
        self.client.force_login(self.c)
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/accept/",
                {},
                format="json",
            ).status_code,
            409,
        )
        self.client.force_login(self.a)
        self.post("invitations/", {"email": self.c.email}, 202)
        invitation = FamilyInvitation.objects.get(invited_user=self.c, status="PENDING")
        self.client.force_login(self.c)
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/reject/",
                {},
                format="json",
            ).data["status"],
            "REJECTED",
        )

    def test_member_cannot_manage_configuration(self):
        self.client.force_login(self.b)
        for resource, payload in [
            ("accounts/", {"name": "No", "kind": "CASH"}),
            ("areas/", {"name": "No"}),
            ("budgets/", {}),
            ("invitations/", {"email": self.c.email}),
        ]:
            self.assertEqual(
                self.client.post(
                    self.base + resource, payload, format="json"
                ).status_code,
                403,
            )
        self.assertEqual(
            self.client.patch(self.base, {"name": "No"}, format="json").status_code, 403
        )
        self.assertEqual(
            self.client.delete(
                self.base + f'accounts/{self.account["id"]}/'
            ).status_code,
            403,
        )

    def test_shared_expense_author_and_admin_edits(self):
        self.client.force_login(self.b)
        movement = self.post("transactions/", self.expense())
        self.assertEqual(movement["registered_by"], str(self.b.pk))
        self.assertEqual(
            self.client.patch(
                self.base + f'transactions/{movement["id"]}/',
                {"amount": "0.20"},
                format="json",
            ).status_code,
            200,
        )
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(self.base + "transactions/").data["count"], 1)
        self.assertEqual(
            self.client.patch(
                self.base + f'transactions/{movement["id"]}/',
                {"amount": "0.30"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                family_id=self.family["id"],
                actor=self.a,
                resource_id=movement["id"],
                operation="UPDATE",
            ).count(),
            1,
        )
        self.assertEqual(
            self.client.delete(
                self.base + f'transactions/{movement["id"]}/'
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.patch(
                self.base + f'transactions/{movement["id"]}/',
                {"amount": "0.40"},
                format="json",
            ).status_code,
            400,
        )

    def test_member_cannot_modify_others(self):
        movement = self.post("transactions/", self.expense())
        self.client.force_login(self.b)
        for method in ("patch", "delete"):
            response = getattr(self.client, method)(
                self.base + f'transactions/{movement["id"]}/',
                {"amount": "1.00"},
                format="json",
            )
            self.assertEqual(response.status_code, 403)

    def test_strict_scope_relations_and_amount(self):
        for extra in (
            {"account": str(self.personal.pk)},
            {"amount": 0.1},
            {"amount": "0.001"},
            {"owner": str(self.b.pk)},
            {"family": self.family["id"]},
        ):
            self.post("transactions/", self.expense(**extra), 400)
        personal_area = Area.objects.filter(owner=self.a, family__isnull=True).first()
        self.post("transactions/", self.expense(area=str(personal_area.pk)), 400)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_personal_endpoints_exclude_family_and_reverse(self):
        movement = self.post("transactions/", self.expense())
        for resource, identifier in [
            ("accounts", self.account["id"]),
            ("areas", self.area["id"]),
            ("transactions", movement["id"]),
        ]:
            personal = self.client.get(f"/api/v1/{resource}/").data["results"]
            self.assertNotIn(identifier, [r["id"] for r in personal])
            self.assertEqual(
                self.client.get(f"/api/v1/{resource}/{identifier}/").status_code, 404
            )
        self.assertEqual(
            self.client.get(self.base + f"accounts/{self.personal.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.base + "reports/summary/").data["expense"], "0.10"
        )
        self.assertEqual(
            self.client.get("/api/v1/reports/summary/").data["expense"], "0.00"
        )
        self.assertEqual(
            self.client.get("/api/v1/reports/summary/").data["net_worth"], "777.00"
        )

    def test_transfer_idempotence_same_scope_and_credit(self):
        payload = {
            "account": self.account["id"],
            "destination_account": self.dest["id"],
            "amount": "10.00",
            "occurred_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        }
        key = str(uuid4())
        first = self.client.post(
            self.base + "transfers/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.client.force_login(self.b)
        second = self.client.post(
            self.base + "transfers/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Transaction.objects.count(), 1)
        summary = self.client.get(self.base + "reports/summary/").data
        self.assertEqual(summary["expense"], "0.00")
        self.assertEqual(summary["net_worth"], "90.00")
        payload["destination_account"] = str(self.personal.pk)
        self.assertEqual(
            self.client.post(
                self.base + "transfers/",
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid4()),
            ).status_code,
            400,
        )

    def test_budgets_and_dashboard_exact_scope(self):
        now = timezone.now()
        budget = self.post(
            "budgets/",
            {
                "category": self.category["id"],
                "limit_amount": "0.50",
                "year": now.year,
                "month": now.month,
            },
        )
        self.client.force_login(self.b)
        self.post("transactions/", self.expense(amount="0.20"))
        self.post("transactions/", self.expense(amount="0.20"))
        self.assertEqual(
            self.client.get(self.base + f'budgets/{budget["id"]}/progress/').data[
                "alert"
            ],
            "WARNING",
        )
        self.post("transactions/", self.expense(amount="0.10"))
        dashboard = self.client.get(self.base + "dashboard/").data
        self.assertEqual(dashboard["expense"], "0.50")
        self.assertEqual(dashboard["net_worth"], "89.50")
        self.assertEqual(dashboard["budget_alerts"][0]["alert"], "EXCEEDED")

    def test_removal_revokes_all_access_and_preserves_history(self):
        self.client.force_login(self.b)
        movement = self.post("transactions/", self.expense())
        self.client.force_login(self.a)
        member = FamilyMembership.objects.get(family_id=self.family["id"], user=self.b)
        self.assertEqual(
            self.client.delete(self.base + f"members/{member.pk}/").status_code, 204
        )
        self.client.force_login(self.b)
        for path in (
            "accounts/",
            "transactions/",
            "audit/events/",
            "reports/export/csv/",
            "dashboard/",
        ):
            self.assertEqual(self.client.get(self.base + path).status_code, 404)
        self.assertTrue(Transaction.objects.filter(pk=movement["id"]).exists())
        self.assertEqual(self.client.get("/api/v1/transactions/").data["count"], 0)

    def test_exports_and_audit_never_include_personal(self):
        self.client.force_login(self.b)
        movement = self.post("transactions/", self.expense(description="Shared-marker"))
        self.client.force_login(self.a)
        for kind in ("csv", "xlsx", "pdf"):
            response = self.client.get(self.base + f"reports/export/{kind}/")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b"Privado A", response.content)
        preview = self.client.get(
            self.base + f"reports/preview/?registered_by={self.b.pk}"
        ).data
        self.assertEqual(preview["movements"]["count"], 1)
        events = self.client.get(self.base + "audit/events/").data["results"]
        self.assertTrue(
            any(
                str(e["actor"]) == str(self.b.pk)
                and str(e["resource_id"]) == str(movement["id"])
                for e in events
            )
        )
        personal = self.client.get("/api/v1/audit/events/").data["results"]
        self.assertFalse(any(e["resource_id"] == movement["id"] for e in personal))

    def test_csrf_real_for_family_and_financial_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.a)
        for url, payload in [
            ("/api/v1/families/", {"name": "No"}),
            (self.base + "transactions/", self.expense()),
            (self.base + "invitations/", {"email": self.c.email}),
        ]:
            self.assertEqual(client.post(url, payload, format="json").status_code, 403)
        token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
        self.assertEqual(
            client.post(
                self.base + "transactions/",
                self.expense(),
                format="json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            201,
        )

    def test_family_recurrences_unavailable_and_personal_refs_reject(self):
        self.assertEqual(
            self.client.get(self.base + "recurring/rules/").status_code, 404
        )
        payload = {
            "name": "Unsafe",
            "kind": "EXPENSE",
            "amount": "1.00",
            "source_account": self.account["id"],
            "area": self.area["id"],
            "category": self.category["id"],
            "frequency": "DAILY",
            "start_date": timezone.now().date().isoformat(),
            "execution_mode": "MANUAL",
        }
        self.assertEqual(
            self.client.post(
                "/api/v1/recurring/rules/", payload, format="json"
            ).status_code,
            400,
        )

    def test_financial_rollback_includes_audit(self):
        before = AuditEvent.objects.count()
        with patch(
            "apps.audit.signals.AuditEvent.objects.create",
            side_effect=RuntimeError("QA rollback"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    self.base + "transactions/", self.expense(), format="json"
                )
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_member_leave_and_archive(self):
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.post(self.base + "leave/", {}, format="json").status_code, 204
        )
        self.assertEqual(self.client.get(self.base + "accounts/").status_code, 404)
        self.client.force_login(self.a)
        self.assertEqual(
            self.client.patch(
                self.base, {"status": "ARCHIVED"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(self.base + "accounts/").status_code, 200)
        self.post("transactions/", self.expense(), 403)

    def test_uniqueness_independent_of_author(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.create(
                owner=self.b,
                family_id=self.family["id"],
                name=self.account["name"],
                kind="CASH",
            )

    def test_invitation_throttle(self):
        from apps.users.models import AuthRateLimit

        # Setup uses the same persistent family write counter.
        for _ in range(35):
            response = self.client.post(
                self.base + "invitations/",
                {"email": "unknown@example.test"},
                format="json",
            )
            if response.status_code == 429:
                break
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_same_author_different_families_never_mix(self):
        other = self.client.post(
            "/api/v1/families/", {"name": "Familia separada"}, format="json"
        ).data
        other_base = f'/api/v1/families/{other["id"]}/'
        foreign_account = self.client.post(
            other_base + "accounts/",
            {"name": "Fondo hogar", "kind": "BANK", "initial_balance": "900.00"},
            format="json",
        )
        self.assertEqual(foreign_account.status_code, 201)
        self.post(
            "transactions/", self.expense(account=foreign_account.data["id"]), 400
        )
        self.assertEqual(
            self.client.get(self.base + "reports/summary/").data["net_worth"], "90.00"
        )
        self.assertEqual(
            self.client.get(other_base + "reports/summary/").data["net_worth"], "900.00"
        )
        self.assertEqual(
            self.client.get("/api/v1/reports/summary/").data["net_worth"], "777.00"
        )

    def test_reinvitation_reactivates_membership_without_changing_author(self):
        self.client.force_login(self.b)
        movement = self.post("transactions/", self.expense())
        self.client.force_login(self.a)
        member = FamilyMembership.objects.get(family_id=self.family["id"], user=self.b)
        first_joined_at = member.joined_at
        self.assertEqual(
            self.client.delete(self.base + f"members/{member.pk}/").status_code, 204
        )
        self.post("invitations/", {"email": self.b.email}, 202)
        invitation = FamilyInvitation.objects.get(
            family_id=self.family["id"], invited_user=self.b, status="PENDING"
        )
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.post(
                f"/api/v1/families/invitations/{invitation.pk}/accept/",
                {},
                format="json",
            ).status_code,
            200,
        )
        member.refresh_from_db()
        self.assertEqual(member.joined_at, first_joined_at)
        self.assertEqual(member.status, "ACTIVE")
        self.assertEqual(member.role, "MEMBER")
        self.assertEqual(Transaction.objects.get(pk=movement["id"]).owner_id, self.b.pk)

    def test_budget_and_classification_reject_personal_relationships(self):
        personal_area = Area.objects.filter(owner=self.a, family__isnull=True).first()
        now = timezone.now()
        self.post(
            "budgets/",
            {
                "area": str(personal_area.pk),
                "limit_amount": "100.00",
                "year": now.year,
                "month": now.month,
            },
            400,
        )
        self.post(
            "categories/",
            {"area": str(personal_area.pk), "name": "Inválida", "kind": "EXPENSE"},
            400,
        )
        self.assertEqual(
            self.client.patch(
                "/api/v1/accounts/" + self.account["id"] + "/",
                {"name": "No"},
                format="json",
            ).status_code,
            404,
        )


@skipUnless(
    connection.vendor == "postgresql", "Bloqueos concurrentes requieren PostgreSQL"
)
class FamilyConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.a, self.b = [
            get_user_model().objects.create_user(
                email=f"family-race-{n}@example.test",
                password="QA-Strong-private-pass!",
            )
            for n in range(2)
        ]
        self.family = Family.objects.create(name="Carrera QA", created_by=self.a)
        self.admin = FamilyMembership.objects.create(
            family=self.family, user=self.a, role="ADMIN"
        )
        self.member = FamilyMembership.objects.create(family=self.family, user=self.b)
        self.account = Account.objects.create(
            owner=self.a, family=self.family, name="Origen", kind="BANK"
        )
        self.destination = Account.objects.create(
            owner=self.a, family=self.family, name="Destino", kind="CASH"
        )
        self.url = f"/api/v1/families/{self.family.pk}/"

    def run_as(self, user, method, path, payload=None, key=None):
        close_old_connections()
        try:
            client = APIClient()
            client.force_login(user)
            response = getattr(client, method)(
                self.url + path,
                payload or {},
                format="json",
                **({"HTTP_IDEMPOTENCY_KEY": key} if key else {}),
            )
            return response.status_code
        finally:
            close_old_connections()

    def test_concurrent_transfer_two_members_one_movement(self):
        key = str(uuid4())
        payload = {
            "account": str(self.account.pk),
            "destination_account": str(self.destination.pk),
            "amount": "0.30",
            "occurred_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda user: self.run_as(user, "post", "transfers/", payload, key),
                    [self.a, self.b],
                )
            )
        self.assertEqual(sorted(results), [200, 201])
        self.assertEqual(Transaction.objects.filter(family=self.family).count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                family=self.family, resource_type="transactions.transaction"
            ).count(),
            1,
        )

    def test_revocation_before_lock_acquisition_rejects_write(self):
        from .services import locked_family, change_member

        locked, release = Event(), Event()

        def revoke():
            close_old_connections()
            try:
                with locked_family(self.a, self.family.pk, admin=True):
                    change_member(self.a, self.family.pk, self.member.pk, remove=True)
                    locked.set()
                    if not release.wait(10):
                        raise RuntimeError("QA synchronization timeout")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            removal = pool.submit(revoke)
            self.assertTrue(locked.wait(10))
            payload = {
                "account": str(self.account.pk),
                "destination_account": str(self.destination.pk),
                "amount": "1.00",
                "occurred_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
            }
            write = pool.submit(
                self.run_as, self.b, "post", "transfers/", payload, str(uuid4())
            )
            release.set()
            removal.result(timeout=15)
            self.assertEqual(write.result(timeout=15), 404)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_concurrent_admin_demotions_leave_one_admin(self):
        self.member.role = "ADMIN"
        self.member.save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    self.run_as,
                    user,
                    "patch",
                    f"members/{member.pk}/",
                    {"role": "MEMBER"},
                )
                for user, member in [(self.a, self.admin), (self.b, self.member)]
            ]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(
            FamilyMembership.objects.filter(
                family=self.family, role="ADMIN", status="ACTIVE"
            ).count(),
            1,
        )
