"""
LOCALYN Multi-Agency Fusion Module

Implements cross-source event fusion between BBMP municipal grievance records
and Bengaluru Traffic Police (BTP) incident telemetry:
- Crosswalk taxonomy mapping
- Gated candidate generation
- Spatial point-in-polygon containment
- Multi-feature candidate scoring
- Entity resolution and canonical event clustering
- Full CHEF confidence with source diversity
"""

from backend.app.fusion.crosswalk import (
    CrosswalkRegistry,
    CrosswalkEntry,
    get_crosswalk,
    EVENT_FAMILIES,
    STRENGTH_WEIGHTS
)

from backend.app.fusion.matcher import (
    CandidatePair,
    CandidateGenerator,
    compute_text_similarity,
    score_temporal_compatibility,
    calculate_temporal_distance_hours,
    DEFAULT_WEIGHTS,
    DEFAULT_MATCH_THRESHOLD
)

from backend.app.fusion.cluster import (
    CanonicalEvent,
    cluster_matched_pairs
)

from backend.app.fusion.gold_set import (
    GOLD_SET_PAIRS,
    get_gold_set
)

__all__ = [
    "CrosswalkRegistry",
    "CrosswalkEntry",
    "get_crosswalk",
    "EVENT_FAMILIES",
    "STRENGTH_WEIGHTS",
    "CandidatePair",
    "CandidateGenerator",
    "compute_text_similarity",
    "score_temporal_compatibility",
    "calculate_temporal_distance_hours",
    "DEFAULT_WEIGHTS",
    "DEFAULT_MATCH_THRESHOLD",
    "CanonicalEvent",
    "cluster_matched_pairs",
    "GOLD_SET_PAIRS",
    "get_gold_set"
]
