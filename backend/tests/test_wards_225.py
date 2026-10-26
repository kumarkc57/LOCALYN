"""
LOCALYN 225 Bengaluru Ward Boundaries Integration & Geographic Service Test Suite
Validates:
1. Loading all 225 wards from authoritative GeoJSON
2. Unique ward identifiers (1 to 225)
3. Valid Polygon and MultiPolygon geometries
4. Known coordinates resolving to expected wards verified against dataset
5. Coordinates outside Bengaluru returning no match
6. Invalid latitude and longitude handling
7. Points on polygon boundaries handled deterministically
8. Legacy ward-name normalization (Kannada transliterations, prefixes, numbers)
9. Ward compatibility scoring
10. Existing candidate generation and event matching with 225 wards
11. Geo API endpoints (/geo/wards, /geo/wards/{id}, /geo/wards/geojson, /geo/lookup)
"""

import unittest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon, MultiPolygon

from backend.app.main import app
from backend.app.geo.wards import (
    get_ward_service,
    resolve_point_to_ward,
    normalize_ward_name,
    calculate_ward_compatibility,
    point_in_polygon,
    haversine_distance_km,
    BENGALURU_WARD_BOUNDARIES,
    LEGACY_198_TO_225_MAP
)
from backend.app.fusion.matcher import CandidateGenerator, CandidatePair
from backend.app.fusion.gold_set import get_gold_set


class TestBengaluruWards225(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = get_ward_service()
        cls.client = TestClient(app)

    # 1. Loading all 225 wards
    def test_load_all_225_wards(self):
        all_wards = self.service.get_all_wards()
        self.assertEqual(len(all_wards), 225, "Expected exactly 225 features in authoritative dataset")
        self.assertEqual(len(self.service.features), 225)
        self.assertEqual(len(self.service.geometries), 225)

    # 2. Unique ward identifiers
    def test_unique_ward_identifiers(self):
        all_wards = self.service.get_all_wards()
        ids = [w["ward_id"] for w in all_wards]
        self.assertEqual(len(ids), len(set(ids)), "Ward IDs must be strictly unique")
        self.assertEqual(min(ids), 1)
        self.assertEqual(max(ids), 225)

    # 3. Valid Polygon and MultiPolygon geometries
    def test_valid_geometries(self):
        for idx, geom in enumerate(self.service.geometries):
            self.assertTrue(
                isinstance(geom, (Polygon, MultiPolygon)),
                f"Feature {idx} geometry must be Polygon or MultiPolygon"
            )
            self.assertTrue(geom.is_valid, f"Feature {idx} geometry must be topologically valid")
            self.assertFalse(geom.is_empty, f"Feature {idx} geometry must not be empty")

    # 4. Known coordinates resolving to expected wards verified against dataset
    def test_known_coordinates_resolution(self):
        test_cases = [
            # (lat, lon, expected_name, expected_id)
            (12.9116, 77.6389, "HSR Layout", 221),
            (12.9280, 77.6830, "Bellanduru", 107),
            (12.9340, 77.6250, "Koramangala", 174),
            (13.0358, 77.5970, "Hebbala", 63),
            (12.9698, 77.7500, "White Field", 103),
            (12.9020, 77.6210, "Bommanahalli", 218),
        ]
        for lat, lon, exp_name, exp_id in test_cases:
            res = resolve_point_to_ward(lat, lon)
            self.assertIsNotNone(res, f"Failed to resolve coordinates ({lat}, {lon})")
            self.assertEqual(res["ward_id"], exp_id, f"Expected ward ID {exp_id} for ({lat}, {lon})")
            self.assertEqual(res["ward_name"], exp_name, f"Expected {exp_name} for ({lat}, {lon})")
            self.assertEqual(res["method"], "point_in_polygon")
            self.assertEqual(res["confidence"], 1.0)
            self.assertEqual(res["resolution_status"], "exact")

    # 5. Coordinates outside Bengaluru returning no match
    def test_coordinates_outside_bengaluru(self):
        outside_points = [
            (18.9220, 72.8347),  # Mumbai
            (28.6139, 77.2090),  # New Delhi
            (13.0827, 80.2707),  # Chennai
            (51.5074, -0.1278),  # London
            (0.0, 0.0),          # Null Island
            (12.0, 77.5),        # South of Bengaluru rural
            (14.5, 77.5)         # North of Bengaluru rural
        ]
        for lat, lon in outside_points:
            res = resolve_point_to_ward(lat, lon)
            self.assertIsNone(res, f"Coordinates ({lat}, {lon}) outside Bengaluru must return None")

    # 6. Invalid latitude and longitude
    def test_invalid_coordinates(self):
        invalid_cases = [
            (None, 77.6),
            (12.9, None),
            (None, None),
            ("invalid", 77.6),
            (12.9, "bad_coord"),
            (999.0, 77.6),    # Out of latitude range
            (-120.0, 77.6),   # Out of latitude range
            (12.9, 250.0),    # Out of longitude range
        ]
        for lat, lon in invalid_cases:
            res = resolve_point_to_ward(lat, lon)
            self.assertIsNone(res, f"Invalid coords ({lat}, {lon}) must return None")

    # 7. Points on polygon boundaries handled deterministically
    def test_points_on_boundaries(self):
        # Obtain boundary vertex from a known ward
        geom_hsr = self.service.wards_by_id[221]["geometry"]
        exterior_coords = list(geom_hsr.exterior.coords)
        boundary_pt = exterior_coords[0]  # (lon, lat)

        res = resolve_point_to_ward(boundary_pt[1], boundary_pt[0])
        self.assertIsNotNone(res)
        self.assertIn(res["method"], ["point_in_polygon", "boundary_match"])
        self.assertGreaterEqual(res["confidence"], 0.85)

    # 8. Legacy ward-name normalization
    def test_ward_name_normalization(self):
        self.assertEqual(normalize_ward_name("Ward 174 - HSR Layout"), "hsr layout")
        self.assertEqual(normalize_ward_name("150 - Bellandur"), "bellandur")
        self.assertEqual(normalize_ward_name("Bellanduru"), "bellandur")
        self.assertEqual(normalize_ward_name("Hebbala"), "hebbal")
        self.assertEqual(normalize_ward_name("White Field"), "whitefield")
        self.assertEqual(normalize_ward_name("Varthuru"), "varthur")
        self.assertEqual(normalize_ward_name("w-151 koramangala:"), "koramangala")
        self.assertEqual(normalize_ward_name(""), "")
        self.assertEqual(normalize_ward_name(None), "")

    # 9. Ward compatibility scoring
    def test_ward_compatibility_scoring(self):
        # Strict inside Bellandur
        score, reason = calculate_ward_compatibility("150 - Bellandur", btp_lat=12.9280, btp_lon=77.6830)
        self.assertEqual(score, 1.0)
        self.assertIn("inside BBMP", reason)

        # Legacy Indiranagar cluster match
        score_indira, reason_indira = calculate_ward_compatibility("89 - Indiranagar", btp_lat=12.9710, btp_lon=77.6410)
        self.assertGreaterEqual(score_indira, 0.90)

        # Disjoint mismatch (Hebbal vs Bommanahalli)
        score_bad, _ = calculate_ward_compatibility("7 - Hebbal", btp_lat=12.9020, btp_lon=77.6210)
        self.assertEqual(score_bad, 0.0)

    # 10. Existing candidate generation and event matching
    def test_candidate_generation_with_225_wards(self):
        gold = get_gold_set()
        gen = CandidateGenerator()
        candidates = gen.generate_candidates([g["bbmp"] for g in gold], [g["btp"] for g in gold])
        self.assertGreater(len(candidates), 0)

        # Verify Gold-001 matches
        pair_001 = CandidatePair(gold[0]["bbmp"], gold[0]["btp"])
        self.assertTrue(pair_001.is_match)
        self.assertGreaterEqual(pair_001.match_score, 0.75)

    # 11. Geo API endpoints
    def test_geo_api_endpoints(self):
        # GET /geo/wards
        res_list = self.client.get("/geo/wards")
        self.assertEqual(res_list.status_code, 200)
        wards = res_list.json()
        self.assertEqual(len(wards), 225)
        self.assertEqual(wards[0]["ward_id"], 1)

        # GET /geo/wards/{ward_id}
        res_single = self.client.get("/geo/wards/221")
        self.assertEqual(res_single.status_code, 200)
        ward_221 = res_single.json()
        self.assertEqual(ward_221["ward_name"], "HSR Layout")
        self.assertEqual(ward_221["assembly_constituency"], "175-BOMMANAHALLI")

        # GET /geo/wards/{ward_id} 404
        res_404 = self.client.get("/geo/wards/999")
        self.assertEqual(res_404.status_code, 404)

        # GET /geo/wards/geojson
        res_geojson = self.client.get("/geo/wards/geojson")
        self.assertEqual(res_geojson.status_code, 200)
        gj = res_geojson.json()
        self.assertEqual(gj["type"], "FeatureCollection")
        self.assertEqual(len(gj["features"]), 225)

        # POST /geo/lookup
        res_lookup = self.client.post("/geo/lookup", json={"latitude": 12.9116, "longitude": 77.6389})
        self.assertEqual(res_lookup.status_code, 200)
        lookup_data = res_lookup.json()
        self.assertEqual(lookup_data["ward_id"], 221)
        self.assertEqual(lookup_data["ward_name"], "HSR Layout")

        # POST /geo/lookup outside
        res_lookup_out = self.client.post("/geo/lookup", json={"latitude": 18.9220, "longitude": 72.8347})
        self.assertEqual(res_lookup_out.status_code, 404)


if __name__ == "__main__":
    unittest.main()
