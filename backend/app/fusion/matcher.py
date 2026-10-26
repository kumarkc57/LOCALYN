"""
LOCALYN BBMP <-> BTP Candidate Generation & Feature Matching Engine

Implements:
1. Candidate generation constraints (temporal window, crosswalk eligibility, ward point-in-polygon)
2. Decoupled feature scoring (temporal, spatial, category strength, textual similarity)
3. Explainable composite matching scoring
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import re
import math

from backend.app.fusion.crosswalk import get_crosswalk, CrosswalkRegistry
from backend.app.geo.wards import calculate_ward_compatibility, resolve_point_to_ward
from backend.app.chef.calculator import parse_iso_or_rfc


# Standard feature weights
DEFAULT_WEIGHTS = {
    "temporal": 0.25,
    "spatial": 0.35,
    "semantic": 0.25,
    "text": 0.15
}

# Matching threshold
DEFAULT_MATCH_THRESHOLD = 0.65


def compute_text_similarity(text1: Optional[str], text2: Optional[str]) -> float:
    """
    Computes token Jaccard similarity after lowercasing, punctuation stripping,
    and civic term stopword suppression.
    """
    if not text1 or not text2:
        return 0.0

    stop_words = {"the", "a", "an", "is", "in", "at", "of", "on", "and", "or", "to", "for", "with", "by", "near", "road"}
    
    def tokenize(text: str) -> set:
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        tokens = clean.split()
        return {t for t in tokens if len(t) > 2 and t not in stop_words}

    set1 = tokenize(text1)
    set2 = tokenize(text2)

    if not set1 or not set2:
        return 0.0

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    return round(intersection / union, 3) if union > 0 else 0.0


def calculate_temporal_distance_hours(time_str1: str, time_str2: str) -> Optional[float]:
    """Computes absolute difference in hours between two timestamp strings."""
    dt1 = parse_iso_or_rfc(time_str1)
    dt2 = parse_iso_or_rfc(time_str2)

    if not dt1 or not dt2:
        # Fallback: check if dates in YYYY-MM-DD match
        d1 = str(time_str1)[:10]
        d2 = str(time_str2)[:10]
        if d1 and d2 and d1 == d2:
            return 0.0
        return None

    diff_seconds = abs((dt1 - dt2).total_seconds())
    return diff_seconds / 3600.0


def score_temporal_compatibility(diff_hours: Optional[float]) -> float:
    """
    Continuous feature score for temporal proximity:
    - 0-2 hours: 1.00
    - <= 6 hours: 0.95
    - <= 12 hours: 0.90
    - <= 24 hours (same day): 0.80
    - <= 48 hours: 0.50
    - > 48 hours: 0.20
    """
    if diff_hours is None:
        return 0.40

    if diff_hours <= 2.0:
        return 1.00
    elif diff_hours <= 6.0:
        return 0.95
    elif diff_hours <= 12.0:
        return 0.90
    elif diff_hours <= 24.0:
        return 0.80
    elif diff_hours <= 48.0:
        return 0.50
    elif diff_hours <= 72.0:
        return 0.30
    else:
        return 0.00


class CandidatePair:
    """Represents a candidate pair between a BBMP grievance and a BTP telemetry record."""

    def __init__(
        self,
        bbmp_record: Dict[str, Any],
        btp_record: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_MATCH_THRESHOLD
    ):
        self.bbmp = bbmp_record
        self.btp = btp_record
        self.weights = weights or DEFAULT_WEIGHTS
        self.threshold = threshold

        self.features: Dict[str, float] = {}
        self.match_score: float = 0.0
        self.is_match: bool = False
        self.explanations: List[str] = []

        self.evaluate()

    def evaluate(self):
        crosswalk = get_crosswalk()

        # 1. Temporal Feature
        bbmp_date = self.bbmp.get("grievance_date") or self.bbmp.get("event_time") or ""
        btp_time = self.btp.get("timestamp") or self.btp.get("event_time") or ""
        diff_hours = calculate_temporal_distance_hours(bbmp_date, btp_time)
        f_temp = score_temporal_compatibility(diff_hours)
        self.features["temporal"] = f_temp

        # 2. Spatial Feature (BBMP Ward vs BTP coordinate point-in-polygon)
        bbmp_ward = self.bbmp.get("ward_name") or self.bbmp.get("location") or ""
        btp_lat = self.btp.get("latitude")
        btp_lon = self.btp.get("longitude")
        btp_ward = self.btp.get("ward_name") or self.btp.get("location") or self.btp.get("location_name")

        f_spatial, spatial_reason = calculate_ward_compatibility(
            bbmp_ward_name=bbmp_ward,
            btp_lat=btp_lat,
            btp_lon=btp_lon,
            btp_ward_name=btp_ward
        )
        self.features["spatial"] = f_spatial

        # 3. Category / Semantic Strength Feature
        bbmp_cat = self.bbmp.get("category", "")
        bbmp_subcat = self.bbmp.get("sub_category", "")
        btp_cause = self.btp.get("cause") or self.btp.get("event_cause") or self.btp.get("category", "")

        entry = crosswalk.get_mapping(bbmp_cat, bbmp_subcat)
        if entry and crosswalk.is_family_compatible(bbmp_cat, bbmp_subcat, btp_cause):
            f_semantic = entry.strength_weight
        elif entry and entry.is_eligible:
            # Eligible category, but cause is somewhat divergent
            f_semantic = entry.strength_weight * 0.6
        else:
            f_semantic = 0.0
        self.features["semantic"] = f_semantic

        # 4. Text Similarity Feature
        # Combine Sub Category + Staff Remarks from BBMP, and Title + Description from BTP
        bbmp_text = f"{bbmp_subcat} {self.bbmp.get('staff_remarks', '')}"
        btp_text = f"{self.btp.get('title', '')} {self.btp.get('description', '')} {self.btp.get('location_name', '')}"
        f_text = compute_text_similarity(bbmp_text, btp_text)
        self.features["text"] = f_text

        # Weighted combination
        raw_score = (
            self.weights["temporal"] * f_temp
            + self.weights["spatial"] * f_spatial
            + self.weights["semantic"] * f_semantic
            + self.weights["text"] * f_text
        )
        self.match_score = round(max(0.0, min(1.0, raw_score)), 3)
        self.is_match = self.match_score >= self.threshold

        # Human explainability breakdown
        self.explanations = [
            f"Temporal: {f_temp:.2f} (delta ~ {diff_hours if diff_hours is not None else 'N/A'} hrs)",
            f"Spatial: {f_spatial:.2f} ({spatial_reason})",
            f"Semantic: {f_semantic:.2f} (Crosswalk strength: {entry.mapping_strength if entry else 'Unmapped'})",
            f"Text Similarity: {f_text:.2f} (Jaccard overlap)"
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbmp_id": self.bbmp.get("id") or self.bbmp.get("complaint_id"),
            "btp_id": self.btp.get("id") or self.btp.get("event_id"),
            "bbmp_ward": self.bbmp.get("ward_name"),
            "bbmp_category": self.bbmp.get("category"),
            "bbmp_sub_category": self.bbmp.get("sub_category"),
            "btp_cause": self.btp.get("cause") or self.btp.get("event_cause"),
            "btp_location": self.btp.get("location_name") or self.btp.get("location"),
            "match_score": self.match_score,
            "is_match": self.is_match,
            "features": self.features,
            "explanations": self.explanations
        }


class CandidateGenerator:
    """Generates candidate pairs filtering out non-compatible events before scoring."""

    def __init__(
        self,
        max_time_window_hours: float = 48.0,
        crosswalk: Optional[CrosswalkRegistry] = None
    ):
        self.max_time_window_hours = max_time_window_hours
        self.crosswalk = crosswalk or get_crosswalk()

    def is_candidate(self, bbmp: Dict[str, Any], btp: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Applies LOCALYN Methodology candidate gating rules:
        1. Date compatibility
        2. Normalized event family compatibility (via Crosswalk)
        3. Point-in-polygon ward compatibility
        4. Rejects 'Do not map' categories
        """
        # 1. Crosswalk eligibility check
        bbmp_cat = bbmp.get("category", "")
        bbmp_subcat = bbmp.get("sub_category", "")
        entry = self.crosswalk.get_mapping(bbmp_cat, bbmp_subcat)

        if not entry:
            return (False, "Category not found in crosswalk")
        if not entry.is_eligible:
            return (False, f"Category '{entry.mapping_strength}' is excluded from cross-source event fusion")

        # 2. Family compatibility check
        btp_cause = btp.get("cause") or btp.get("event_cause") or btp.get("category", "")
        if not self.crosswalk.is_family_compatible(bbmp_cat, bbmp_subcat, btp_cause):
            return (False, f"Incompatible event families: BBMP '{entry.localyn_category}' vs BTP '{btp_cause}'")

        # 3. Temporal compatibility check
        bbmp_time = bbmp.get("grievance_date") or bbmp.get("event_time") or ""
        btp_time = btp.get("timestamp") or btp.get("event_time") or ""
        diff_hours = calculate_temporal_distance_hours(bbmp_time, btp_time)

        if diff_hours is not None and diff_hours > self.max_time_window_hours:
            return (False, f"Temporal delta {diff_hours:.1f}h exceeds max window {self.max_time_window_hours}h")

        # 4. Spatial compatibility check (BBMP Ward vs BTP Coordinate)
        bbmp_ward = bbmp.get("ward_name") or bbmp.get("location") or ""
        btp_lat = btp.get("latitude")
        btp_lon = btp.get("longitude")
        btp_ward = btp.get("ward_name") or btp.get("location") or btp.get("location_name")

        spatial_score, reason = calculate_ward_compatibility(
            bbmp_ward_name=bbmp_ward,
            btp_lat=btp_lat,
            btp_lon=btp_lon,
            btp_ward_name=btp_ward
        )

        if spatial_score < 0.5:
            return (False, f"Spatial incompatibility: {reason}")

        return (True, "Satisfies all candidate generation gates")

    def generate_candidates(
        self,
        bbmp_records: List[Dict[str, Any]],
        btp_records: List[Dict[str, Any]],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_MATCH_THRESHOLD
    ) -> List[CandidatePair]:
        """Runs candidate generation and feature scoring over collections of records."""
        candidates = []
        for bbmp in bbmp_records:
            for btp in btp_records:
                is_cand, reason = self.is_candidate(bbmp, btp)
                if is_cand:
                    pair = CandidatePair(bbmp, btp, weights=weights, threshold=threshold)
                    candidates.append(pair)
        return candidates
