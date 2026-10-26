import unittest
import asyncio
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.ingestion.scheduler import AutoIngestionScheduler

class TestAutoIngestionScheduler(unittest.TestCase):

    def test_scheduler_initial_status(self):
        s = AutoIngestionScheduler(interval_minutes=20, enabled=True)
        status = s.get_status()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["interval_minutes"], 20)
        self.assertEqual(status["total_runs"], 0)
        self.assertFalse(status["running"])

    def test_scheduler_lifecycle(self):
        async def run_lifecycle():
            s = AutoIngestionScheduler(interval_minutes=15, enabled=True)
            s.start()
            status = s.get_status()
            self.assertTrue(status["running"])
            await s.stop()
            status_after = s.get_status()
            self.assertFalse(status_after["running"])

        asyncio.run(run_lifecycle())

    def test_health_endpoint_includes_auto_ingest(self):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("auto_ingest", data)
        self.assertIsNotNone(data["auto_ingest"])
        self.assertIn("interval_minutes", data["auto_ingest"])

if __name__ == "__main__":
    unittest.main()
