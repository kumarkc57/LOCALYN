from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from email.utils import parsedate_to_datetime

# Deterministic Single-Source Weights
WEIGHT_SOURCE_RELIABILITY = 0.30
WEIGHT_TEMPORAL_CONSISTENCY = 0.25
WEIGHT_CORROBORATION = 0.25
WEIGHT_SOURCE_AGREEMENT = 0.10
WEIGHT_GEOGRAPHIC_CONSISTENCY = 0.10

# Major known news outlets for source reliability scoring
ESTABLISHED_OUTLETS = [
    "the hindu", "deccan herald", "times of india", "indian express",
    "ndtv", "bangalore mirror", "ani", "pti", "livemint", "hindustan times"
]

def calculate_source_reliability(source: str, source_type: str = "news") -> float:
    """
    Deterministic score based on source credibility.
    - Weather API (official observation sensor): 0.95
    - Established civic / national news outlets: 0.85
    - General news / syndication: 0.70
    - Other / unknown: 0.50
    """
    if source_type == "weather_api" or "openweathermap" in source.lower():
        return 0.95

    src_lower = source.lower()
    for outlet in ESTABLISHED_OUTLETS:
        if outlet in src_lower:
            return 0.85

    if source:
        return 0.70

    return 0.50

def parse_iso_or_rfc(timestamp_str: str) -> Optional[datetime]:
    """Safely parse various datetime string formats into UTC datetime."""
    if not timestamp_str:
        return None
    try:
        # Try ISO 8601
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    try:
        # Try RFC 2822 / standard email date format
        dt = parsedate_to_datetime(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    try:
        # Common format "YYYY-MM-DD HH:MM:SS"
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def calculate_temporal_consistency(event_time_str: str) -> float:
    """
    Deterministic score reflecting report recency and freshness.
    - <= 2 hours: 1.00
    - 2 - 6 hours: 0.90
    - 6 - 12 hours: 0.80
    - 12 - 24 hours: 0.65
    - 24 - 48 hours: 0.50
    - > 48 hours: 0.30
    """
    dt = parse_iso_or_rfc(event_time_str)
    if not dt:
        return 0.60

    now_utc = datetime.now(timezone.utc)
    diff_seconds = (now_utc - dt).total_seconds()
    diff_hours = max(0.0, diff_seconds / 3600.0)

    if diff_hours <= 2:
        return 1.00
    elif diff_hours <= 6:
        return 0.90
    elif diff_hours <= 12:
        return 0.80
    elif diff_hours <= 24:
        return 0.65
    elif diff_hours <= 48:
        return 0.50
    else:
        return 0.30

def calculate_corroboration(corroborating_count: int) -> float:
    """
    Deterministic score based on co-occurring civic reports:
    - 0 other reports: 0.50 (isolated report)
    - 1 other report:  0.75 (partially corroborated)
    - 2+ other reports: 0.95 (strongly corroborated)
    """
    if corroborating_count >= 2:
        return 0.95
    elif corroborating_count == 1:
        return 0.75
    else:
        return 0.50

def get_confidence_tier(score: float) -> str:
    if score >= 0.80:
        return "HIGH"
    elif score >= 0.60:
        return "MODERATE"
    else:
        return "LOW"

def compute_partial_chef(
    source: str,
    source_type: str,
    event_time: str,
    corroborating_count: int = 0
) -> Dict[str, Any]:
    """
    Computes the partial CHEF evidence-confidence score and exposes individual factors.
    NOTE: CHEF is an evidence-confidence score, not a proof of ground-truth reality.
    """
    source_reliability = calculate_source_reliability(source, source_type)
    temporal_consistency = calculate_temporal_consistency(event_time)
    corroboration = calculate_corroboration(corroborating_count)
    
    # Baseline constants
    source_agreement = 1.0
    geographic_consistency = 1.0

    raw_score = (
        WEIGHT_SOURCE_RELIABILITY * source_reliability
        + WEIGHT_TEMPORAL_CONSISTENCY * temporal_consistency
        + WEIGHT_CORROBORATION * corroboration
        + WEIGHT_SOURCE_AGREEMENT * source_agreement
        + WEIGHT_GEOGRAPHIC_CONSISTENCY * geographic_consistency
    )

    # Clamp to [0.0, 1.0]
    confidence = max(0.0, min(1.0, round(raw_score, 2)))
    confidence_tier = get_confidence_tier(confidence)

    return {
        "confidence": confidence,
        "confidence_tier": confidence_tier,
        "chef": {
            "source_reliability": round(source_reliability, 2),
            "temporal_consistency": round(temporal_consistency, 2),
            "corroboration": round(corroboration, 2),
            "source_agreement": round(source_agreement, 2),
            "geographic_consistency": round(geographic_consistency, 2)
        }
    }


# Multi-Agency Full CHEF Weights
FULL_CHEF_WEIGHTS = {
    "source_diversity": 0.30,
    "source_reliability": 0.20,
    "source_agreement": 0.20,
    "geographic_consistency": 0.15,
    "temporal_freshness": 0.15
}

AGENCY_BASE_RELIABILITY = {
    "BTP": 0.90,       # Police incident telemetry
    "BBMP": 0.85,      # Official municipal grievance records
    "WEATHER": 0.95,   # Sensor observation
    "WEATHER_API": 0.95,
    "NEWS": 0.80,      # Press reports
    "CITIZEN": 0.65    # Unverified public report
}


def calculate_source_diversity(agencies: List[str]) -> float:
    """
    Evaluates cross-agency diversity.
    Penalizes duplicate reports from the same agency; rewards cross-agency corroboration.
    - 0 agencies: 0.30
    - 1 agency (isolated / single agency duplication): 0.50
    - 2 distinct agencies (e.g. BBMP + BTP): 0.85
    - 3+ distinct agencies (e.g. BBMP + BTP + News/Weather): 0.98
    """
    unique_agencies = set(a.upper() for a in agencies if a)
    count = len(unique_agencies)
    if count >= 3:
        return 0.98
    elif count == 2:
        return 0.85
    elif count == 1:
        return 0.50
    else:
        return 0.30


def compute_full_chef(canonical_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full CHEF confidence calculator with Source Diversity.
    Evaluates explainable evidence factors over a canonical event cluster.
    """
    agencies = canonical_event.get("participating_agencies", [])
    event_time = canonical_event.get("event_time", "")
    
    # 1. Source Diversity
    diversity_score = calculate_source_diversity(agencies)

    # 2. Source Reliability
    if agencies:
        reliabilities = [AGENCY_BASE_RELIABILITY.get(a.upper(), 0.70) for a in agencies]
        avg_reliability = sum(reliabilities) / len(reliabilities)
    else:
        avg_reliability = 0.50

    # 3. Source Agreement
    # Cross-source agreement is high when corroboration occurs across multiple agencies
    agreement_score = 0.95 if len(set(a.upper() for a in agencies)) >= 2 else 0.70

    # 4. Geographic Consistency
    # Point-in-polygon containment
    geo_score = 1.00 if canonical_event.get("ward_name") else 0.70

    # 5. Temporal Freshness
    temp_score = calculate_temporal_consistency(event_time) if event_time else 0.75

    raw_score = (
        FULL_CHEF_WEIGHTS["source_diversity"] * diversity_score
        + FULL_CHEF_WEIGHTS["source_reliability"] * avg_reliability
        + FULL_CHEF_WEIGHTS["source_agreement"] * agreement_score
        + FULL_CHEF_WEIGHTS["geographic_consistency"] * geo_score
        + FULL_CHEF_WEIGHTS["temporal_freshness"] * temp_score
    )

    confidence = max(0.0, min(1.0, round(raw_score, 2)))
    tier = get_confidence_tier(confidence)

    diversity_text = f"{len(set(agencies))} distinct agencies ({', '.join(agencies)})"
    explainability = (
        f"Confidence {confidence:.2f} ({tier}): Cross-corroborated by {diversity_text} "
        f"with {diversity_score*100:.0f}% diversity score."
    )

    return {
        "confidence": confidence,
        "confidence_tier": tier,
        "explainability_summary": explainability,
        "chef": {
            "source_diversity": round(diversity_score, 2),
            "source_reliability": round(avg_reliability, 2),
            "source_agreement": round(agreement_score, 2),
            "geographic_consistency": round(geo_score, 2),
            "temporal_consistency": round(temp_score, 2)
        }
    }

