
"""
LOCALYN BBMP <-> BTP Candidate Generation & Feature Matching Engine

Implements:
1. Candidate generation constraints (temporal window, crosswalk eligibility,
   ward point-in-polygon)
2. Feature scoring: temporal, spatial, category strength, text similarity
3. Explainable composite matching scores
4. SBERT semantic similarity with Jaccard fallback
"""

from typing import Optional, Dict, Any, List, Tuple
import re

from backend.app.fusion.crosswalk import get_crosswalk, CrosswalkRegistry
from backend.app.geo.wards import calculate_ward_compatibility
from backend.app.chef.calculator import parse_iso_or_rfc


# ---------------------------------------------------------------------
# Optional SBERT initialization
# ---------------------------------------------------------------------

try:
    from sentence_transformers import SentenceTransformer, util

    _sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    _sbert_model = None
    util = None


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "temporal": 0.25,
    "spatial": 0.35,
    "semantic": 0.25,
    "text": 0.15,
}

DEFAULT_MATCH_THRESHOLD = 0.65


# ---------------------------------------------------------------------
# Text similarity
# ---------------------------------------------------------------------

def compute_text_similarity(
    text1: Optional[str],
    text2: Optional[str],
) -> float:
    """Calculate token-based Jaccard similarity as a fallback."""

    if not text1 or not text2:
        return 0.0

    stop_words = {
        "the", "a", "an", "is", "in", "at", "of", "on",
        "and", "or", "to", "for", "with", "by", "near", "road",
    }

    def tokenize(text: str) -> set:
        clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
        return {
            token
            for token in clean.split()
            if len(token) > 2 and token not in stop_words
        }

    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    union = tokens1 | tokens2
    intersection = tokens1 & tokens2

    return round(len(intersection) / len(union), 3)




def compute_sbert_similarity(text1, text2):
    """Use SBERT cosine similarity, with Jaccard fallback."""
    if not text1 or not text2:
        return 0.0

    if _sbert_model is None:
        return compute_text_similarity(text1, text2)

    try:
        embeddings = _sbert_model.encode(
            [text1, text2],
            convert_to_tensor=True,
        )

        # Support both real SBERT output and test doubles.
        if hasattr(util, "pytorch_cos_sim"):
            score = util.pytorch_cos_sim(
                embeddings[0], embeddings[1]
            ).item()
        else:
            score = util.cos_sim(
                embeddings[0], embeddings[1]
            ).item()

        return round(
            max(0.0, min(1.0, (float(score) + 1.0) / 2.0)),
            3,
        )

    except Exception:
        return compute_text_similarity(text1, text2)


# ---------------------------------------------------------------------
# Temporal compatibility
# ---------------------------------------------------------------------

def calculate_temporal_distance_hours(
    time_str1: str,
    time_str2: str,
) -> Optional[float]:
    """Calculate the absolute time difference between two timestamps."""

    if not time_str1 or not time_str2:
        return None

    dt1 = parse_iso_or_rfc(time_str1)
    dt2 = parse_iso_or_rfc(time_str2)

    if not dt1 or not dt2:
        # Fallback for date-only strings.
        date1 = str(time_str1)[:10]
        date2 = str(time_str2)[:10]

        if date1 and date1 == date2:
            return 0.0

        return None

    # Handle timestamps where one is timezone-aware and the other is naive.
    if dt1.tzinfo is None and dt2.tzinfo is not None:
        dt1 = dt1.replace(tzinfo=dt2.tzinfo)
    elif dt2.tzinfo is None and dt1.tzinfo is not None:
        dt2 = dt2.replace(tzinfo=dt1.tzinfo)

    difference_seconds = abs((dt1 - dt2).total_seconds())
    return difference_seconds / 3600.0


def score_temporal_compatibility(
    diff_hours: Optional[float],
) -> float:
    """Convert temporal distance into a compatibility score."""

    if diff_hours is None:
        return 0.40

    if diff_hours <= 2:
        return 1.00
    elif diff_hours <= 6:
        return 0.95
    elif diff_hours <= 12:
        return 0.90
    elif diff_hours <= 24:
        return 0.80
    elif diff_hours <= 48:
        return 0.50
    elif diff_hours <= 72:
        return 0.30

    return 0.00


# ---------------------------------------------------------------------
# Candidate pair scoring
# ---------------------------------------------------------------------

class CandidatePair:
    """A candidate match between a BBMP grievance and a BTP record."""

    def __init__(
        self,
        bbmp_record: Dict[str, Any],
        btp_record: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
    ):
        self.bbmp = bbmp_record
        self.btp = btp_record
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.threshold = threshold

        self.features: Dict[str, float] = {}
        self.match_score = 0.0
        self.is_match = False
        self.explanations: List[str] = []

        self.evaluate()

    def evaluate(self) -> None:
        crosswalk = get_crosswalk()

        # 1. Temporal feature
        bbmp_date = (
            self.bbmp.get("grievance_date")
            or self.bbmp.get("event_time")
            or ""
        )

        btp_time = (
            self.btp.get("timestamp")
            or self.btp.get("event_time")
            or ""
        )

        diff_hours = calculate_temporal_distance_hours(
            bbmp_date,
            btp_time,
        )

        f_temp = score_temporal_compatibility(diff_hours)
        self.features["temporal"] = f_temp

        # 2. Spatial feature
        bbmp_ward = (
            self.bbmp.get("ward_name")
            or self.bbmp.get("location")
            or ""
        )

        btp_lat = self.btp.get("latitude")
        btp_lon = self.btp.get("longitude")

        btp_ward = (
            self.btp.get("ward_name")
            or self.btp.get("location")
            or self.btp.get("location_name")
        )

        f_spatial, spatial_reason = calculate_ward_compatibility(
            bbmp_ward_name=bbmp_ward,
            btp_lat=btp_lat,
            btp_lon=btp_lon,
            btp_ward_name=btp_ward,
        )

        self.features["spatial"] = f_spatial

        # 3. Category / semantic compatibility
        bbmp_cat = self.bbmp.get("category", "")
        bbmp_subcat = self.bbmp.get("sub_category", "")

        btp_cause = (
            self.btp.get("cause")
            or self.btp.get("event_cause")
            or self.btp.get("category", "")
        )

        entry = crosswalk.get_mapping(bbmp_cat, bbmp_subcat)

        if (
            entry
            and crosswalk.is_family_compatible(
                bbmp_cat,
                bbmp_subcat,
                btp_cause,
            )
        ):
            f_semantic = entry.strength_weight

        elif entry and entry.is_eligible:
            f_semantic = entry.strength_weight * 0.6

        else:
            f_semantic = 0.0

        self.features["semantic"] = f_semantic

        # 4. Text similarity: SBERT with Jaccard fallback
        bbmp_text = " ".join(str(self.bbmp.get(key, "") or "") for key in (
            "description", "sub_category", "staff_remarks"
        ))

        btp_text = " ".join(str(self.btp.get(key, "") or "") for key in (
            "description", "title", "location_name"
        ))

        f_text = compute_sbert_similarity(bbmp_text, btp_text)
        self.features["text"] = f_text

        # 5. Weighted composite score
        raw_score = (
            self.weights["temporal"] * f_temp
            + self.weights["spatial"] * f_spatial
            + self.weights["semantic"] * f_semantic
            + self.weights["text"] * f_text
        )

        self.match_score = round(
            max(0.0, min(1.0, raw_score)),
            3,
        )

        self.is_match = self.match_score >= self.threshold

        # 6. Explainability
        text_method = (
            "SBERT cosine similarity (rescaled)"
            if _sbert_model is not None
            else "Jaccard fallback"
        )

        self.explanations = [
            (
                f"Temporal: {f_temp:.2f} "
                f"(delta ~ "
                f"{diff_hours if diff_hours is not None else 'N/A'} hrs)"
            ),
            f"Spatial: {f_spatial:.2f} ({spatial_reason})",
            (
                f"Semantic: {f_semantic:.2f} "
                f"(Crosswalk strength: "
                f"{entry.mapping_strength if entry else 'Unmapped'})"
            ),
            f"Text Similarity: {f_text:.2f} ({text_method})",
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Return the candidate pair as a serializable dictionary."""

        return {
            "bbmp_id": (
                self.bbmp.get("id")
                or self.bbmp.get("complaint_id")
            ),
            "btp_id": (
                self.btp.get("id")
                or self.btp.get("event_id")
            ),
            "bbmp_ward": self.bbmp.get("ward_name"),
            "bbmp_category": self.bbmp.get("category"),
            "bbmp_sub_category": self.bbmp.get("sub_category"),
            "btp_cause": (
                self.btp.get("cause")
                or self.btp.get("event_cause")
            ),
            "btp_location": (
                self.btp.get("location_name")
                or self.btp.get("location")
            ),
            "match_score": self.match_score,
            "is_match": self.is_match,
            "features": self.features,
            "explanations": self.explanations,
        }


# ---------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------

class CandidateGenerator:
    """Filter incompatible records before scoring candidate pairs."""

    def __init__(
        self,
        max_time_window_hours: float = 48.0,
        crosswalk: Optional[CrosswalkRegistry] = None,
    ):
        self.max_time_window_hours = max_time_window_hours
        self.crosswalk = crosswalk or get_crosswalk()

    def is_candidate(
        self,
        bbmp: Dict[str, Any],
        btp: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Apply candidate-generation gates:
        1. Crosswalk eligibility
        2. Event-family compatibility
        3. Temporal compatibility
        4. Spatial compatibility
        """

        # 1. Crosswalk eligibility
        bbmp_cat = bbmp.get("category", "")
        bbmp_subcat = bbmp.get("sub_category", "")

        entry = self.crosswalk.get_mapping(
            bbmp_cat,
            bbmp_subcat,
        )

        if not entry:
            return False, "Category not found in crosswalk"

        if not entry.is_eligible:
            return (
                False,
                f"Category '{entry.mapping_strength}' is excluded "
                "from cross-source event fusion",
            )

        # 2. Event-family compatibility
        btp_cause = (
            btp.get("cause")
            or btp.get("event_cause")
            or btp.get("category", "")
        )

        if not self.crosswalk.is_family_compatible(
            bbmp_cat,
            bbmp_subcat,
            btp_cause,
        ):
            return (
                False,
                f"Incompatible event families: "
                f"BBMP '{entry.localyn_category}' vs BTP '{btp_cause}'",
            )

        # 3. Temporal compatibility
        bbmp_time = (
            bbmp.get("grievance_date")
            or bbmp.get("event_time")
            or ""
        )

        btp_time = (
            btp.get("timestamp")
            or btp.get("event_time")
            or ""
        )

        diff_hours = calculate_temporal_distance_hours(
            bbmp_time,
            btp_time,
        )

        if (
            diff_hours is not None
            and diff_hours > self.max_time_window_hours
        ):
            return (
                False,
                f"Temporal delta {diff_hours:.1f}h exceeds "
                f"max window {self.max_time_window_hours}h",
            )

        # 4. Spatial compatibility
        bbmp_ward = (
            bbmp.get("ward_name")
            or bbmp.get("location")
            or ""
        )

        btp_lat = btp.get("latitude")
        btp_lon = btp.get("longitude")

        btp_ward = (
            btp.get("ward_name")
            or btp.get("location")
            or btp.get("location_name")
        )

        spatial_score, reason = calculate_ward_compatibility(
            bbmp_ward_name=bbmp_ward,
            btp_lat=btp_lat,
            btp_lon=btp_lon,
            btp_ward_name=btp_ward,
        )

        if spatial_score < 0.5:
            return False, f"Spatial incompatibility: {reason}"

        return True, "Satisfies all candidate generation gates"

    def generate_candidates(
        self,
        bbmp_records: List[Dict[str, Any]],
        btp_records: List[Dict[str, Any]],
        weights: Optional[Dict[str, float]] = None,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
    ) -> List[CandidatePair]:
        """Generate and score candidate pairs that pass all gates."""

        candidates: List[CandidatePair] = []

        for bbmp in bbmp_records:
            for btp in btp_records:
                is_cand, _reason = self.is_candidate(bbmp, btp)

                if is_cand:
                    candidates.append(
                        CandidatePair(
                            bbmp,
                            btp,
                            weights=weights,
                            threshold=threshold,
                        )
                    )

        return candidates
