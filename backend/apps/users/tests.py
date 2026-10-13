import uuid
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .admin import CustomUserCreationForm
from .models import AuthRateLimit

User = get_user_model()
PASSWORD = "Mariposa!Nube-2026"
NEW_PASSWORD = "Ventana!Bosque-2027"
ORIGIN = "http://localhost:5173"


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user("ana@example.com", PASSWORD, first_name="Ana", last_name="Torres")

    def token(self, client=None):
        return (client or self.client).get("/api/v1/auth/csrf/").json()["csrfToken"]

    def send(self, path, data=None, method="post", client=None, **extra):
        client = client or self.client
        return getattr(client, method)(path, data or {}, format="json",
            HTTP_X_CSRFTOKEN=self.token(client), HTTP_ORIGIN=ORIGIN, **extra)

    def login(self, client=None):
        return self.send("/api/v1/auth/login/", {"email": self.user.email, "password": PASSWORD}, client=client)

    def registration(self, **overrides):
        return {"email": "nuevo@example.com", "password": PASSWORD,
                "first_name": "Luis", "last_name": "Ramos", **overrides}

    def test_registration_normalizes_email_and_hashes_password(self):
        response = self.send("/api/v1/auth/register/", self.registration(email=" Nuevo@EXAMPLE.com "))
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="nuevo@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(response.json()["id"], str(user.id))
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertEqual((user.timezone, user.currency), ("America/Lima", "PEN"))
        self.assertNotIn("password", response.json())
        self.assertNotIn("is_staff", response.json())
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)

    def test_duplicate_email_case_insensitive(self):
        response = self.send("/api/v1/auth/register/", self.registration(email="ANA@EXAMPLE.COM"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_database_rejects_case_insensitive_duplicates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="ANA@EXAMPLE.COM")])

    def test_invalid_password(self):
        response = self.send("/api/v1/auth/register/", self.registration(password="123"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_similar_password_rejected(self):
        response = self.send("/api/v1/auth/register/", self.registration(password="nuevo@example.com"))
        self.assertEqual(response.status_code, 400)

    def test_registration_rejects_privilege_fields(self):
        response = self.send("/api/v1/auth/register/", self.registration(is_staff=True, is_superuser=True))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="nuevo@example.com").exists())

    def test_correct_login_and_secure_cookie_flags(self):
        response = self.send("/api/v1/auth/login/", {"email": "ANA@EXAMPLE.COM", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], self.user.email)
        self.assertNotIn("password", response.json()["user"])
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.assertEqual(response.cookies["sessionid"]["samesite"], "Lax")
        self.assertGreater(int(response.cookies["sessionid"]["max-age"]), 0)

    def test_wrong_and_unknown_login_have_same_error(self):
        responses = [self.send("/api/v1/auth/login/", {"email": email, "password": "Wrong!12345"})
                     for email in (self.user.email, "unknown@example.com")]
        self.assertEqual(responses[0].status_code, 403)
        self.assertEqual(responses[0].json(), responses[1].json())

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.login().status_code, 403)

    def test_logout_invalidates_session(self):
        self.login()
        old_cookie = self.client.cookies["sessionid"].value
        self.assertEqual(self.send("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)
        other = APIClient()
        other.cookies["sessionid"] = old_cookie
        self.assertEqual(other.get("/api/v1/auth/me/").status_code, 403)

    def test_anonymous_login_and_registration_require_csrf(self):
        for path, data in [("/api/v1/auth/login/", {"email": self.user.email, "password": PASSWORD}),
                           ("/api/v1/auth/register/", self.registration())]:
            with self.subTest(path=path):
                response = self.client.post(path, data, format="json", HTTP_ORIGIN=ORIGIN)
                self.assertEqual(response.status_code, 403)
                self.assertIn("CSRF", response.json()["detail"])

    def test_csrf_rejects_untrusted_origin(self):
        response = self.client.post("/api/v1/auth/login/", {"email": self.user.email, "password": PASSWORD},
            format="json", HTTP_X_CSRFTOKEN=self.token(), HTTP_ORIGIN="https://evil.example")
        self.assertEqual(response.status_code, 403)

    def test_csrf_rejects_invalid_token(self):
        self.token()
        response = self.client.post("/api/v1/auth/login/", {}, format="json",
            HTTP_X_CSRFTOKEN="a" * 64, HTTP_ORIGIN=ORIGIN)
        self.assertEqual(response.status_code, 403)

    def test_csrf_rotation_after_login(self):
        previous = self.token()
        response = self.login()
        self.assertNotEqual(previous, response.json()["csrfToken"])
        rejected = self.client.post("/api/v1/auth/logout/", {}, format="json",
            HTTP_X_CSRFTOKEN=previous, HTTP_ORIGIN=ORIGIN)
        self.assertEqual(rejected.status_code, 403)

    def test_csrf_endpoint_cookie_and_no_cache(self):
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["csrftoken"]["httponly"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_unauthenticated_private_endpoints(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)
        for path, method in [("/api/v1/users/me/", "patch"),
                             ("/api/v1/auth/logout/", "post"),
                             ("/api/v1/auth/change-password/", "post")]:
            self.assertEqual(self.send(path, method=method).status_code, 403)

    def test_authenticated_mutations_require_csrf(self):
        self.login()
        for path, method in [("/api/v1/users/me/", "patch"),
                             ("/api/v1/auth/logout/", "post"),
                             ("/api/v1/auth/change-password/", "post")]:
            self.assertEqual(getattr(self.client, method)(path, {}, format="json").status_code, 403)

    def test_profile_query(self):
        self.login()
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.user.pk))
        self.assertIn("date_joined", response.json())
        self.assertIn("no-store", response["Cache-Control"])

    def test_update_profile(self):
        self.login()
        response = self.send("/api/v1/users/me/", {"first_name": "Andrea", "timezone": "UTC", "currency": "USD"}, "patch")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.timezone, self.user.currency), ("Andrea", "UTC", "USD"))

    def test_invalid_profile_values(self):
        self.login()
        for data in ({"timezone": "Fake/Zone"}, {"currency": "XYZ"}, {"first_name": ""}):
            self.assertEqual(self.send("/api/v1/users/me/", data, "patch").status_code, 400)

    def test_user_isolation_and_readonly_fields(self):
        other = User.objects.create_user("other@example.com", PASSWORD, first_name="Otra")
        self.login()
        for field, value in {"id": str(other.id), "user_id": str(other.id), "email": other.email,
                             "is_staff": True, "is_active": False, "password": NEW_PASSWORD}.items():
            self.assertEqual(self.send("/api/v1/users/me/", {field: value}, "patch").status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/users/{other.id}/").status_code, 404)
        self.send("/api/v1/users/me/", {"first_name": "Cambiada"}, "patch")
        other.refresh_from_db()
        self.assertEqual(other.first_name, "Otra")
        other_client = APIClient(enforce_csrf_checks=True)
        self.send("/api/v1/auth/login/", {"email": other.email, "password": PASSWORD}, client=other_client)
        self.assertEqual(other_client.get("/api/v1/auth/me/").json()["id"], str(other.id))

    def test_change_password_preserves_current_and_invalidates_other_session(self):
        other_session = APIClient(enforce_csrf_checks=True)
        self.login(other_session)
        self.login()
        old_key = self.client.cookies["sessionid"].value
        response = self.send("/api/v1/auth/change-password/", {
            "current_password": PASSWORD, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertNotEqual(old_key, self.client.cookies["sessionid"].value)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(other_session.get("/api/v1/auth/me/").status_code, 403)
        self.send("/api/v1/auth/logout/")
        self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.send("/api/v1/auth/login/", {"email": self.user.email, "password": NEW_PASSWORD}).status_code, 200)

    def test_password_change_rejects_wrong_weak_and_same_password(self):
        self.login()
        for current, new in [("Wrong!9999", NEW_PASSWORD), (PASSWORD, "123"), (PASSWORD, PASSWORD)]:
            response = self.send("/api/v1/auth/change-password/", {"current_password": current, "new_password": new})
            self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_persistence_with_new_client(self):
        self.login()
        reloaded = APIClient(enforce_csrf_checks=True)
        reloaded.cookies = self.client.cookies.copy()
        self.assertEqual(reloaded.get("/api/v1/auth/me/").json()["id"], str(self.user.id))

    def test_login_rotates_anonymous_session_key(self):
        session = self.client.session
        session["pre_login"] = True
        session.save()
        previous = self.client.cookies["sessionid"].value
        self.assertEqual(self.login().status_code, 200)
        self.assertNotEqual(previous, self.client.cookies["sessionid"].value)

    def test_createsuperuser_command(self):
        with patch.dict("os.environ", {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
            call_command("createsuperuser", email="cli@example.com", first_name="Admin",
                         last_name="CLI", interactive=False, stdout=StringIO())
        user = User.objects.get(email="cli@example.com")
        self.assertTrue(user.is_staff and user.is_superuser and user.check_password(PASSWORD))

    @override_settings(AUTH_LOGIN_EMAIL_LIMIT=2, AUTH_LOGIN_IP_LIMIT=20)
    def test_login_throttle_normalized_email_across_ips(self):
        for ip in ("10.0.0.1", "10.0.0.2"):
            response = self.send("/api/v1/auth/login/", {"email": "ANA@EXAMPLE.COM", "password": "wrong"}, REMOTE_ADDR=ip)
            self.assertEqual(response.status_code, 403)
        response = self.send("/api/v1/auth/login/", {"email": self.user.email, "password": PASSWORD}, REMOTE_ADDR="10.0.0.3")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertNotIn(self.user.email, str(list(AuthRateLimit.objects.values_list("key", flat=True))))

    @override_settings(AUTH_LOGIN_IP_LIMIT=1)
    def test_login_ip_throttle_and_expiry(self):
        self.send("/api/v1/auth/login/", {"email": "unknown@example.com", "password": "wrong"})
        self.assertEqual(self.login().status_code, 429)
        AuthRateLimit.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.login().status_code, 200)

    @override_settings(AUTH_REGISTER_IP_LIMIT=1)
    def test_registration_throttle(self):
        self.send("/api/v1/auth/register/", self.registration(password="123"))
        self.assertEqual(self.send("/api/v1/auth/register/", self.registration()).status_code, 429)

    @override_settings(AUTH_PASSWORD_USER_LIMIT=1)
    def test_password_change_throttle(self):
        self.login()
        data = {"current_password": "wrong", "new_password": NEW_PASSWORD}
        self.assertEqual(self.send("/api/v1/auth/change-password/", data).status_code, 400)
        self.assertEqual(self.send("/api/v1/auth/change-password/", data).status_code, 429)

    def test_manager_superuser_and_admin_form(self):
        admin = User.objects.create_superuser("ADMIN@EXAMPLE.COM", PASSWORD, first_name="Admin", last_name="Local")
        self.assertEqual(admin.email, "admin@example.com")
        self.assertTrue(admin.is_staff and admin.is_superuser)
        form = CustomUserCreationForm(data={"email": "staff@example.com", "first_name": "Staff", "last_name": "Local",
            "password1": PASSWORD, "password2": PASSWORD})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().check_password(PASSWORD))
        with self.assertRaises(ValueError):
            User.objects.create_superuser("bad@example.com", PASSWORD, is_staff=False)

    @override_settings(AUTH_LOGIN_EMAIL_LIMIT=1)
    def test_admin_login_shares_throttle_and_requires_csrf(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
        data = {"username": self.user.email, "password": "wrong"}
        self.assertEqual(self.client.post("/admin/login/", data).status_code, 403)
        self.send("/api/v1/auth/login/", {"email": self.user.email, "password": "wrong"})
        response = self.client.post("/admin/login/", data, HTTP_X_CSRFTOKEN=self.token(), HTTP_ORIGIN=ORIGIN)
        self.assertEqual(response.status_code, 429)


@skipUnless(connection.vendor == "postgresql", "Concurrencia requiere PostgreSQL")
class ThrottleConcurrencyTests(TransactionTestCase):
    @override_settings(AUTH_LOGIN_IP_LIMIT=100, AUTH_LOGIN_EMAIL_LIMIT=2)
    def test_concurrent_requests_respect_email_limit(self):
        def attempt(index):
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
                return client.post("/api/v1/auth/login/", {"email": "missing@example.com", "password": "wrong"},
                    format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN=ORIGIN,
                    REMOTE_ADDR=f"10.0.0.{index}").status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(attempt, range(1, 7)))
        self.assertEqual(statuses.count(403), 2)
        self.assertEqual(statuses.count(429), 4)
