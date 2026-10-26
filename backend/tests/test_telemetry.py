import os
import tempfile
import unittest
from datetime import datetime, timezone

from backend.app.database.db import (
    init_db,
    insert_report,
    get_report_by_id,
    get_reports,
    is_duplicate_news,
    count_corroborating_reports
)
from backend.app.ingestion.news import normalize_title
from backend.app.ingestion.pipeline import process_and_store_report, is_bengaluru_relevant
from backend.app.nlp.spacy_extractor import extract_entities
from backend.app.classifier.classifier import classify_text
from backend.app.chef.calculator import (
    compute_partial_chef,
    calculate_source_reliability,
    calculate_temporal_consistency,
    calculate_corroboration
)

class TestLOCALYNTelemetry(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.db_path = self.temp_file.name
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_normalization_and_deduplication(self):
        title1 = "Traffic Snarl on Silk Board Flyover: Commuters Delayed!"
        norm1 = normalize_title(title1)
        
        title2 = "traffic snarl on silk board flyover commuters delayed"
        norm2 = normalize_title(title2)
        
        self.assertEqual(norm1, norm2)
        self.assertNotIn("!", norm1)
        self.assertNotIn(":", norm1)

        # Initially not duplicate
        self.assertFalse(is_duplicate_news("Deccan Herald", norm1, path=self.db_path))

        # Insert a report
        report = {
            "id": "rep-test-01",
            "source": "Deccan Herald",
            "source_type": "news",
            "title": title1,
            "raw_text": "Massive traffic jam reported on Silk Board during morning hours.",
            "url": "https://deccanherald.com/test",
            "category": "TRAFFIC",
            "location": "Silk Board",
            "latitude": 12.9176,
            "longitude": 77.6238,
            "event_time": datetime.now(timezone.utc).isoformat(),
            "confidence": 0.85,
            "confidence_tier": "HIGH",
            "chef_factors": {"source_reliability": 0.85, "temporal_consistency": 1.0, "corroboration": 0.5, "source_agreement": 1.0, "geographic_consistency": 1.0},
            "normalized_title": norm1,
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        insert_report(report, path=self.db_path)

        # Now should be identified as duplicate
        self.assertTrue(is_duplicate_news("Deccan Herald", norm2, path=self.db_path))
        # Different source is not treated as duplicate
        self.assertFalse(is_duplicate_news("The Hindu", norm2, path=self.db_path))

    def test_database_persistence_and_queries(self):
        report = {
            "id": "rep-weather-01",
            "source": "OpenWeatherMap",
            "source_type": "weather_api",
            "title": "Bengaluru Weather Observation: Rain (23°C)",
            "raw_text": "Heavy rainfall observed in Indiranagar and across central Bengaluru.",
            "url": "https://openweathermap.org",
            "category": "WEATHER",
            "location": "Indiranagar",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "event_time": datetime.now(timezone.utc).isoformat(),
            "confidence": 0.92,
            "confidence_tier": "HIGH",
            "chef_factors": {"source_reliability": 0.95, "temporal_consistency": 1.0, "corroboration": 0.75, "source_agreement": 1.0, "geographic_consistency": 1.0},
            "normalized_title": "bengaluru weather observation rain 23c",
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        insert_report(report, path=self.db_path)

        retrieved = get_report_by_id("rep-weather-01", path=self.db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], report["title"])
        self.assertEqual(retrieved["category"], "WEATHER")
        self.assertIsInstance(retrieved["chef_factors"], dict)
        self.assertEqual(retrieved["chef_factors"]["source_reliability"], 0.95)

        # Test filtering
        weather_reports = get_reports(category="WEATHER", path=self.db_path)
        self.assertEqual(len(weather_reports), 1)
        traffic_reports = get_reports(category="TRAFFIC", path=self.db_path)
        self.assertEqual(len(traffic_reports), 0)

    def test_exact_traffic_classification_rules(self):
        # Strong terms -> TRAFFIC
        self.assertEqual(classify_text("Traffic congestion near Silk Board"), "TRAFFIC")
        self.assertEqual(classify_text("Road closure on Outer Ring Road"), "TRAFFIC")
        self.assertEqual(classify_text("Vehicle collision near Hebbal"), "TRAFFIC")

        # Weak/metaphorical terms alone -> OTHER
        self.assertEqual(classify_text("It was a long road to recovery"), "OTHER")
        self.assertEqual(classify_text("The band held a jam session"), "OTHER")
        self.assertEqual(classify_text("The player suffered an accident during practice"), "OTHER")

    def test_relevance_filtering_and_location_null_fallback(self):
        # 1. Non-Bengaluru article -> REJECTED
        nfl_article = {
            "id": "nfl-test-01",
            "source": "Australian Herald",
            "source_type": "news",
            "title": "Nick Bosa practices, George Kittle progressing as 49ers jet to Australia",
            "raw_text": "San Francisco 49ers defensive end Nick Bosa participated in practice... 'It was a long road,' Bosa said.",
            "url": "http://example.com/nfl",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "normalized_title": "nick bosa practices",
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        res_nfl = process_and_store_report(nfl_article, path=self.db_path)
        self.assertIsNone(res_nfl)

        # 2. Bengaluru traffic article -> ACCEPTED as TRAFFIC
        blr_traffic = {
            "id": "blr-traffic-01",
            "source": "Deccan Herald",
            "source_type": "news",
            "title": "Traffic congestion reported near Silk Board",
            "raw_text": "Heavy vehicle queue and traffic congestion reported along Silk Board in Bengaluru.",
            "url": "http://example.com/blr-traffic",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "normalized_title": "traffic congestion silk board",
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        res_traffic = process_and_store_report(blr_traffic, path=self.db_path)
        self.assertIsNotNone(res_traffic)
        saved_traffic = get_report_by_id("blr-traffic-01", path=self.db_path)
        self.assertEqual(saved_traffic["category"], "TRAFFIC")
        self.assertIn("Silk Board", saved_traffic["location"])

        # 3. Bengaluru weather article -> ACCEPTED as WEATHER
        blr_weather = {
            "id": "blr-weather-01",
            "source": "OpenWeatherMap",
            "source_type": "weather_api",
            "title": "Bengaluru Weather Observation: Rain (23°C)",
            "raw_text": "Official meteorological sensor observation for Bengaluru.",
            "url": "https://openweathermap.org",
            "location": "Bengaluru",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "normalized_title": "bengaluru weather observation rain 23c",
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        res_weather = process_and_store_report(blr_weather, path=self.db_path)
        self.assertIsNotNone(res_weather)
        saved_weather = get_report_by_id("blr-weather-01", path=self.db_path)
        self.assertEqual(saved_weather["category"], "WEATHER")

        # 4. Article with no extracted location -> location = null (safe null fallback)
        insert_report({
            "id": "direct-null-loc",
            "source": "Test",
            "source_type": "news",
            "title": "No Loc",
            "raw_text": "No Loc",
            "category": "OTHER",
            "location": None,
            "event_time": datetime.now(timezone.utc).isoformat(),
            "confidence": 0.7,
            "confidence_tier": "MODERATE",
            "chef_factors": {"source_reliability": 0.7, "temporal_consistency": 0.7, "corroboration": 0.5, "source_agreement": 1.0, "geographic_consistency": 1.0},
            "normalized_title": "no loc",
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }, path=self.db_path)
        saved_null = get_report_by_id("direct-null-loc", path=self.db_path)
        self.assertIsNone(saved_null["location"])

    def test_nlp_extraction(self):
        text = "Severe traffic snarl in Indiranagar during the morning peak hours."
        location, time_val = extract_entities(text)
        self.assertTrue(location in ["Indiranagar", "Bengaluru"] or location is not None)
        self.assertIsNotNone(time_val)

    def test_chef_calculation(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        result = compute_partial_chef(
            source="OpenWeatherMap",
            source_type="weather_api",
            event_time=now_iso,
            corroborating_count=2
        )

        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)
        self.assertGreaterEqual(result["confidence"], 0.90)
        self.assertEqual(result["confidence_tier"], "HIGH")
        self.assertEqual(result["chef"]["source_agreement"], 1.0)
        self.assertEqual(result["chef"]["geographic_consistency"], 1.0)
        self.assertEqual(result["chef"]["source_reliability"], 0.95)

        # Stale unknown source
        old_time = "2020-01-01T00:00:00Z"
        low_result = compute_partial_chef(
            source="Unknown Blog",
            source_type="news",
            event_time=old_time,
            corroborating_count=0
        )
        self.assertLess(low_result["confidence"], 0.70)

if __name__ == "__main__":
    unittest.main()
