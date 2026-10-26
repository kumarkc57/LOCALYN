"""
LOCALYN Test Suite: Multi-Agency Fusion, Crosswalk Taxonomy & Benchmark
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.fusion.crosswalk import get_crosswalk, CrosswalkRegistry
from backend.app.geo.wards import (
    point_in_polygon,
    resolve_point_to_ward,
    normalize_ward_name,
    calculate_ward_compatibility,
    BENGALURU_WARD_BOUNDARIES
)
from backend.app.fusion.matcher import (
    CandidateGenerator,
    CandidatePair,
    compute_text_similarity,
    score_temporal_compatibility
)
from backend.app.fusion.cluster import (
    CanonicalEvent,
    cluster_matched_pairs
)
from backend.app.chef.calculator import (
    compute_full_chef,
    calculate_source_diversity
)
from backend.app.fusion.gold_set import get_gold_set
from backend.app.evaluation.benchmark import (
    run_full_benchmark,
    generate_benchmark_markdown_table,
    evaluate_predictions
)


class TestLOCALYNFusion(unittest.TestCase):

    def setUp(self):
        self.crosswalk = get_crosswalk()
        self.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. Crosswalk Taxonomy Tests
    # -------------------------------------------------------------
    def test_crosswalk_loading_and_summary(self):
        summary = self.crosswalk.get_summary()
        self.assertGreater(summary["total_categories_mapped"], 150)
        self.assertGreater(summary["total_bbmp_records_covered"], 300000)
        self.assertIn("Direct", summary["counts_by_strength"])
        self.assertIn("Probable", summary["counts_by_strength"])
        self.assertIn("Do not map", summary["counts_by_strength"])

    def test_crosswalk_direct_and_probable_eligibility(self):
        # Direct: Road Maintenance -> Potholes
        pothole_entry = self.crosswalk.get_mapping("Road Maintenance(Engg)", "Potholes")
        self.assertIsNotNone(pothole_entry)
        self.assertEqual(pothole_entry.mapping_strength, "Direct")
        self.assertEqual(pothole_entry.btp_event_cause, "pot_holes")
        self.assertTrue(pothole_entry.is_eligible)
        self.assertTrue(self.crosswalk.is_family_compatible("Road Maintenance(Engg)", "Potholes", "pot_holes"))

        # Probable: Forest -> obstructions Branches / Trees.
        tree_entry = self.crosswalk.get_mapping("Forest", "obstructions Branches / Trees.")
        self.assertIsNotNone(tree_entry)
        self.assertEqual(tree_entry.mapping_strength, "Probable")
        self.assertTrue(tree_entry.is_eligible)

        # Do not map: Streetlight
        light_entry = self.crosswalk.get_mapping("Electrical", "Street Light Not Working")
        self.assertIsNotNone(light_entry)
        self.assertEqual(light_entry.mapping_strength, "Do not map")
        self.assertFalse(light_entry.is_eligible)

    # -------------------------------------------------------------
    # 2. Geo Module & Point-in-Polygon Tests
    # -------------------------------------------------------------
    def test_point_in_polygon_containment(self):
        bellandur_poly = BENGALURU_WARD_BOUNDARIES["150 - Bellandur"]["polygon"]
        # Inside Bellandur
        self.assertTrue(point_in_polygon(12.9300, 77.6800, bellandur_poly))
        # Outside Bellandur (e.g. Hebbal coordinate)
        self.assertFalse(point_in_polygon(13.0350, 77.5970, bellandur_poly))

    def test_resolve_point_to_ward(self):
        res = resolve_point_to_ward(12.9116, 77.6389)
        self.assertIsNotNone(res)
        self.assertEqual(res["ward_name"], "HSR Layout")

    def test_ward_compatibility_scoring(self):
        score, reason = calculate_ward_compatibility(
            bbmp_ward_name="150 - Bellandur",
            btp_lat=12.9280,
            btp_lon=77.6830
        )
        self.assertEqual(score, 1.0)
        self.assertIn("inside BBMP", reason)

        # Mismatched ward
        score_bad, _ = calculate_ward_compatibility(
            bbmp_ward_name="7 - Hebbal",
            btp_lat=12.9020,
            btp_lon=77.6210  # Bommanahalli
        )
        self.assertEqual(score_bad, 0.0)

    # -------------------------------------------------------------
    # 3. Candidate Generation & Feature Matcher Tests
    # -------------------------------------------------------------
    def test_candidate_gating(self):
        generator = CandidateGenerator(max_time_window_hours=48.0)

        # Valid pair: Pothole in Bellandur within 1 hour
        bbmp_good = {
            "id": "B-1",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Potholes",
            "grievance_date": "2024-06-18 10:00:00",
            "ward_name": "150 - Bellandur"
        }
        btp_good = {
            "id": "T-1",
            "cause": "pot_holes",
            "timestamp": "2024-06-18 10:30:00",
            "latitude": 12.9280,
            "longitude": 77.6830
        }
        is_cand, _ = generator.is_candidate(bbmp_good, btp_good)
        self.assertTrue(is_cand)

        # Reject temporal mismatch (>48 hours)
        btp_delayed = {**btp_good, "timestamp": "2024-06-25 10:00:00"}
        is_cand_del, reason_del = generator.is_candidate(bbmp_good, btp_delayed)
        self.assertFalse(is_cand_del)
        self.assertIn("exceeds max window", reason_del)

        # Reject excluded category (Streetlight)
        bbmp_light = {**bbmp_good, "category": "Electrical", "sub_category": "Street Light Not Working"}
        is_cand_light, reason_light = generator.is_candidate(bbmp_light, btp_good)
        self.assertFalse(is_cand_light)
        self.assertIn("excluded", reason_light)

    def test_candidate_feature_scoring(self):
        bbmp = {
            "id": "B-2",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Potholes",
            "grievance_date": "2024-06-18 10:00:00",
            "ward_name": "150 - Bellandur",
            "staff_remarks": "EcoSpace service road crater repaired"
        }
        btp = {
            "id": "T-2",
            "cause": "pot_holes",
            "timestamp": "2024-06-18 10:20:00",
            "latitude": 12.9280,
            "longitude": 77.6830,
            "title": "Pothole traffic slowdown",
            "description": "Outer Ring Road EcoSpace crater causing vehicle queue"
        }
        pair = CandidatePair(bbmp, btp)
        self.assertTrue(pair.is_match)
        self.assertGreaterEqual(pair.match_score, 0.75)
        self.assertEqual(pair.features["temporal"], 1.0)
        self.assertEqual(pair.features["spatial"], 1.0)
        self.assertEqual(pair.features["semantic"], 1.0)
        self.assertGreater(pair.features["text"], 0.1)

    # -------------------------------------------------------------
    # 4. Full CHEF with Source Diversity Tests
    # -------------------------------------------------------------
    def test_source_diversity_scoring(self):
        # 1 agency: 0.50
        self.assertEqual(calculate_source_diversity(["BBMP", "BBMP", "BBMP"]), 0.50)
        # 2 distinct agencies: 0.85
        self.assertEqual(calculate_source_diversity(["BBMP", "BTP"]), 0.85)
        # 3 distinct agencies: 0.98
        self.assertEqual(calculate_source_diversity(["BBMP", "BTP", "WEATHER"]), 0.98)

    def test_compute_full_chef(self):
        event_multi = {
            "id": "CE-TEST-01",
            "ward_name": "Bellandur",
            "participating_agencies": ["BBMP", "BTP"],
            "event_time": "2024-06-18 10:00:00"
        }
        chef_res = compute_full_chef(event_multi)
        self.assertGreaterEqual(chef_res["confidence"], 0.80)
        self.assertEqual(chef_res["confidence_tier"], "HIGH")
        self.assertEqual(chef_res["chef"]["source_diversity"], 0.85)

        # Single agency event receives lower score
        event_single = {
            "id": "CE-TEST-02",
            "ward_name": "Bellandur",
            "participating_agencies": ["BBMP"],
            "event_time": "2024-06-18 10:00:00"
        }
        chef_res_single = compute_full_chef(event_single)
        self.assertLess(chef_res_single["confidence"], chef_res["confidence"])

    # -------------------------------------------------------------
    # 5. Entity Resolution & Canonical Event Clustering Tests
    # -------------------------------------------------------------
    def test_clustering_canonical_events(self):
        gold = get_gold_set()
        bbmp_records = [g["bbmp"] for g in gold]
        btp_records = [g["btp"] for g in gold]

        gen = CandidateGenerator()
        candidates = gen.generate_candidates(bbmp_records, btp_records)
        canonical_events = cluster_matched_pairs(candidates)

        self.assertGreaterEqual(len(canonical_events), 4)
        for ev in canonical_events:
            self.assertTrue(ev.id.startswith("CE-BLR-"))
            self.assertGreaterEqual(len(ev.participating_agencies), 2)
            self.assertIn("BBMP", ev.participating_agencies)
            self.assertIn("BTP", ev.participating_agencies)

    # -------------------------------------------------------------
    # 6. Benchmark Evaluation Tests
    # -------------------------------------------------------------
    def test_benchmark_performance(self):
        bench = run_full_benchmark()
        results = bench["results"]

        b1 = results["baseline_1_date_ward"]
        b2 = results["baseline_2_date_ward_category"]
        loc = results["localyn_proposed"]

        # LOCALYN must outperform Baseline 2 in Recall and F1
        self.assertGreater(loc["f1"], b2["f1"])
        self.assertGreater(loc["recall"], b2["recall"])
        # LOCALYN must have higher Precision than Baseline 1 (no false positives from streetlights)
        self.assertGreater(loc["precision"], b1["precision"])

        md = generate_benchmark_markdown_table(bench)
        self.assertIn("LOCALYN", md)
        self.assertIn("Baseline 1", md)

    # -------------------------------------------------------------
    # 7. FastAPI Endpoint Integration Tests
    # -------------------------------------------------------------
    def test_api_fusion_endpoints(self):
        # 1. Crosswalk summary
        res_sum = self.client.get("/fusion/crosswalk/summary")
        self.assertEqual(res_sum.status_code, 200)
        self.assertGreater(res_sum.json()["total_categories_mapped"], 100)

        # 2. Crosswalk mappings filter
        res_map = self.client.get("/fusion/crosswalk/mappings?strength=Direct")
        self.assertEqual(res_map.status_code, 200)
        items = res_map.json()
        self.assertGreater(len(items), 0)
        for it in items:
            self.assertEqual(it["mapping_strength"], "Direct")

        # 3. Canonical Events
        res_ce = self.client.get("/fusion/canonical-events")
        self.assertEqual(res_ce.status_code, 200)
        events = res_ce.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)
        self.assertIn("BBMP", events[0]["participating_agencies"])

        # 4. Benchmark endpoint
        res_bench = self.client.get("/fusion/benchmark")
        self.assertEqual(res_bench.status_code, 200)
        bench_json = res_bench.json()
        self.assertIn("localyn_proposed", bench_json["results"])
        self.assertIn("markdown_table", bench_json)

        # 5. Single pair match endpoint
        gold = get_gold_set()[0]
        res_match = self.client.post("/fusion/match", json={
            "bbmp": gold["bbmp"],
            "btp": gold["btp"]
        })
        self.assertEqual(res_match.status_code, 200)
        match_json = res_match.json()
        self.assertTrue(match_json["is_candidate"])
        self.assertTrue(match_json["is_match"])


if __name__ == "__main__":
    unittest.main()
