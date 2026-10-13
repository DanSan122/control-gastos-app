from django.conf import settings
from django.test import SimpleTestCase
from rest_framework.test import APIClient


class HealthTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def test_public_health_contract(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok", "service": "controlgastos-api", "version": "v1"
        })

    def test_mutations_are_not_supported(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)("/api/v1/health/").status_code, 405)

    def test_cors_allows_only_configured_origin(self):
        allowed = self.client.get("/api/v1/health/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertEqual(allowed["Access-Control-Allow-Credentials"], "true")
        rejected = self.client.get("/api/v1/health/", HTTP_ORIGIN="https://unknown.example")
        self.assertNotIn("Access-Control-Allow-Origin", rejected)

    def test_session_and_default_api_policy(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
                         ["rest_framework.permissions.IsAuthenticated"])
