"""
LOCALYN Entity Resolution & Canonical Event Clustering

Groups matched multi-agency candidate pairs into consolidated Canonical Events,
synthesizes centroid geometries and temporal bounds, and calculates Full CHEF confidence.
"""

from typing import List, Dict, Any, Set, Optional
from datetime import datetime
import uuid

from backend.app.fusion.matcher import CandidatePair
from backend.app.chef.calculator import compute_full_chef
from backend.app.geo.wards import resolve_point_to_ward


class CanonicalEvent:
    def __init__(
        self,
        event_id: str,
        category: str,
        ward_name: str,
        title: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        earliest_time: Optional[str] = None,
        latest_time: Optional[str] = None
    ):
        self.id = event_id
        self.category = category
        self.ward_name = ward_name
        self.title = title
        self.latitude = latitude
        self.longitude = longitude
        self.earliest_time = earliest_time
        self.latest_time = latest_time
        self.observations: List[Dict[str, Any]] = []
        self.participating_agencies: Set[str] = set()
        self.chef_data: Dict[str, Any] = {}

    def add_observation(self, obs: Dict[str, Any], agency: str):
        self.observations.append({**obs, "agency": agency})
        self.participating_agencies.add(agency.upper())

    def finalize(self):
        """Computes coordinates centroid, temporal extent, and Full CHEF score."""
        # Calculate coordinate centroids if observations have points
        lats = [o.get("latitude") for o in self.observations if o.get("latitude") is not None]
        lons = [o.get("longitude") for o in self.observations if o.get("longitude") is not None]
        self.ward_id = None
        if lats and lons:
            self.latitude = round(sum(lats) / len(lats), 5)
            self.longitude = round(sum(lons) / len(lons), 5)
            resolved = resolve_point_to_ward(self.latitude, self.longitude)
            if resolved:
                self.ward_id = resolved.get("ward_id")
                if not self.ward_name or self.ward_name.lower() in ["bengaluru", "bangalore"]:
                    self.ward_name = resolved.get("ward_name", self.ward_name)

        # Compute Full CHEF
        chef_input = {
            "id": self.id,
            "category": self.category,
            "ward_name": self.ward_name,
            "participating_agencies": list(self.participating_agencies),
            "observations_count": len(self.observations),
            "event_time": self.latest_time or self.earliest_time or datetime.utcnow().isoformat()
        }
        self.chef_data = compute_full_chef(chef_input)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "ward_name": self.ward_name,
            "ward_id": getattr(self, "ward_id", None),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "earliest_time": self.earliest_time,
            "latest_time": self.latest_time,
            "participating_agencies": sorted(list(self.participating_agencies)),
            "source_diversity_count": len(self.participating_agencies),
            "source_diversity_agencies": sorted(list(self.participating_agencies)),

            "observations_count": len(self.observations),
            "confidence": self.chef_data.get("confidence", 0.5),
            "confidence_tier": self.chef_data.get("confidence_tier", "LOW"),
            "chef_factors": self.chef_data.get("chef", {}),
            "explainability_summary": self.chef_data.get("explainability_summary", ""),
            "observations": self.observations
        }


def cluster_matched_pairs(
    matched_pairs: List[CandidatePair],
    all_bbmp: Optional[List[Dict[str, Any]]] = None,
    all_btp: Optional[List[Dict[str, Any]]] = None
) -> List[CanonicalEvent]:
    """
    Groups matched pairs into connected components, generating canonical events.
    """
    # 1. Build adjacency graph of record IDs
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    records_by_id: Dict[str, Tuple[Dict[str, Any], str]] = {}

    for pair in matched_pairs:
        if not pair.is_match:
            continue
        bbmp_id = str(pair.bbmp.get("id") or pair.bbmp.get("complaint_id"))
        btp_id = str(pair.btp.get("id") or pair.btp.get("event_id"))

        records_by_id[bbmp_id] = (pair.bbmp, "BBMP")
        records_by_id[btp_id] = (pair.btp, "BTP")

        union(bbmp_id, btp_id)

    # 2. Group records by cluster root
    clusters: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
    for rec_id, (rec_data, agency) in records_by_id.items():
        root = find(rec_id)
        clusters.setdefault(root, []).append((rec_data, agency))

    # 3. Build CanonicalEvent for each cluster
    canonical_events = []
    idx = 1

    for root, cluster_records in clusters.items():
        # Derive representative category, ward, title
        categories = [
            r.get("LOCALYN_Category") or r.get("category") or r.get("cause")
            for r, _ in cluster_records if r.get("category") or r.get("cause")
        ]
        wards = [
            r.get("ward_name") or r.get("location")
            for r, _ in cluster_records if r.get("ward_name") or r.get("location")
        ]
        times = [
            r.get("grievance_date") or r.get("timestamp") or r.get("event_time")
            for r, _ in cluster_records if r.get("grievance_date") or r.get("timestamp") or r.get("event_time")
        ]

        rep_cat = categories[0] if categories else "CIVIC_INCIDENT"
        rep_ward = wards[0] if wards else "Bengaluru"
        sorted_times = sorted([t for t in times if t])

        title = f"{rep_cat.replace('_', ' ').title()} at {rep_ward}"

        event = CanonicalEvent(
            event_id=f"CE-BLR-{idx:03d}",
            category=rep_cat,
            ward_name=rep_ward,
            title=title,
            earliest_time=sorted_times[0] if sorted_times else None,
            latest_time=sorted_times[-1] if sorted_times else None
        )

        for rec_data, agency in cluster_records:
            event.add_observation(rec_data, agency)

        event.finalize()
        canonical_events.append(event)
        idx += 1

    return canonical_events
