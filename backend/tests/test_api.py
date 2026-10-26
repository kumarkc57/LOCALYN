import unittest
from fastapi.testclient import TestClient
from backend.app.main import app

class TestLOCALYNApi(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["version"], "1.0.0")
        self.assertTrue(data["database_connected"])

    def test_reports_endpoint(self):
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_reports_404(self):
        response = self.client.get("/reports/non-existent-id")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
