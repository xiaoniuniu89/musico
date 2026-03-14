from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_index_endpoint_returns_bootstrap_metadata(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["app"], "musico-teach")
        self.assertEqual(payload["status"], "ok")
