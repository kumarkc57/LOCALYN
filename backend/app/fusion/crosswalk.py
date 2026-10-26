"""
LOCALYN BBMP <-> BTP Crosswalk Taxonomy Engine

Parses and queries the 161-entry crosswalk taxonomy between BBMP municipal grievances
and Bengaluru Traffic Police (BTP) incident telemetry.
"""

import os
import csv
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

DEFAULT_CROSSWALK_FILENAME = "LOCALYN_BBMP_2023_2024_BTP_Crosswalk.csv"

# Mapping strength weights
STRENGTH_WEIGHTS = {
    "Direct": 1.00,
    "Probable": 0.75,
    "Ambiguous": 0.50,
    "Do not map": 0.00
}

# Primary validated event families per LOCALYN Matching Methodology
EVENT_FAMILIES = {
    "ROAD_DAMAGE": "pot_holes",
    "WATERLOGGING": "water_logging",
    "TREE_FALL": "tree_fall",
    "TREE_OBSTRUCTION": "tree_fall",
    "CONSTRUCTION": "construction",
    "ROAD_WORK": "construction",
    "ROAD_OBSTRUCTION": "construction",
    "DRAINAGE": "water_logging",
    "WATER_RELATED": "water_logging"
}


@dataclass
class CrosswalkEntry:
    category: str
    sub_category: str
    count_2023: int
    count_2024: int
    total_count: int
    localyn_category: str
    btp_event_cause: str
    mapping_strength: str
    matching_use: str

    @property
    def is_eligible(self) -> bool:
        """Only Direct, Probable, and Ambiguous mappings are candidate-eligible."""
        return self.mapping_strength in ("Direct", "Probable", "Ambiguous")

    @property
    def strength_weight(self) -> float:
        return STRENGTH_WEIGHTS.get(self.mapping_strength, 0.0)


class CrosswalkRegistry:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = csv_path or self._discover_csv_path()
        self.entries: List[CrosswalkEntry] = []
        # Key: (normalized_category, normalized_subcategory)
        self.lookup_table: Dict[Tuple[str, str], CrosswalkEntry] = {}
        # Key: normalized_subcategory
        self.subcat_lookup: Dict[str, CrosswalkEntry] = {}
        # Category fallback
        self.cat_lookup: Dict[str, List[CrosswalkEntry]] = {}
        self.load()

    def _discover_csv_path(self) -> str:
        """Finds crosswalk CSV across common workspace paths."""
        candidates = [
            Path(DEFAULT_CROSSWALK_FILENAME),
            Path(__file__).resolve().parents[3] / DEFAULT_CROSSWALK_FILENAME,
            Path(__file__).resolve().parents[2] / DEFAULT_CROSSWALK_FILENAME,
            Path("c:/Users/tchir/OneDrive/Desktop/major") / DEFAULT_CROSSWALK_FILENAME,
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return DEFAULT_CROSSWALK_FILENAME

    def _norm(self, s: Optional[str]) -> str:
        if not s:
            return ""
        return s.strip().lower()

    def load(self):
        """Loads and indexes all mappings from the CSV."""
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"Crosswalk CSV not found at: {self.csv_path}")

        self.entries.clear()
        self.lookup_table.clear()
        self.subcat_lookup.clear()
        self.cat_lookup.clear()

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    c23 = int(row.get("Count_2023", 0) or 0)
                except ValueError:
                    c23 = 0
                try:
                    c24 = int(row.get("Count_2024", 0) or 0)
                except ValueError:
                    c24 = 0
                try:
                    tot = int(row.get("Total_Count", 0) or (c23 + c24))
                except ValueError:
                    tot = c23 + c24

                entry = CrosswalkEntry(
                    category=row.get("Category", "").strip(),
                    sub_category=row.get("Sub Category", "").strip(),
                    count_2023=c23,
                    count_2024=c24,
                    total_count=tot,
                    localyn_category=row.get("LOCALYN_Category", "").strip(),
                    btp_event_cause=row.get("BTP_Event_Cause", "").strip(),
                    mapping_strength=row.get("Mapping_Strength", "").strip(),
                    matching_use=row.get("Matching_Use", "").strip()
                )
                self.entries.append(entry)

                k_full = (self._norm(entry.category), self._norm(entry.sub_category))
                self.lookup_table[k_full] = entry

                k_sub = self._norm(entry.sub_category)
                if k_sub not in self.subcat_lookup:
                    self.subcat_lookup[k_sub] = entry

                k_cat = self._norm(entry.category)
                if k_cat not in self.cat_lookup:
                    self.cat_lookup[k_cat] = []
                self.cat_lookup[k_cat].append(entry)

    def get_mapping(
        self,
        category: str,
        sub_category: Optional[str] = None
    ) -> Optional[CrosswalkEntry]:
        """
        Retrieves matching crosswalk entry with hierarchical fallback:
        1. Exact (category, sub_category)
        2. Exact sub_category
        3. Fuzzy sub_category substring match
        4. Category top entry
        """
        cat_norm = self._norm(category)
        sub_norm = self._norm(sub_category)

        # 1. Exact pair
        if (cat_norm, sub_norm) in self.lookup_table:
            return self.lookup_table[(cat_norm, sub_norm)]

        # 2. Exact subcategory
        if sub_norm and sub_norm in self.subcat_lookup:
            return self.subcat_lookup[sub_norm]

        # 3. Substring search in subcategory
        if sub_norm:
            for (c, s), entry in self.lookup_table.items():
                if sub_norm in s or s in sub_norm:
                    return entry

        # 4. Fallback to category list
        if cat_norm in self.cat_lookup and self.cat_lookup[cat_norm]:
            return self.cat_lookup[cat_norm][0]

        return None

    def is_fusion_eligible(
        self,
        category: str,
        sub_category: Optional[str] = None
    ) -> bool:
        """Returns True if the category mapping is Direct, Probable, or Ambiguous."""
        entry = self.get_mapping(category, sub_category)
        if not entry:
            return False
        return entry.is_eligible

    def is_family_compatible(
        self,
        bbmp_category: str,
        bbmp_sub_category: Optional[str],
        btp_cause_or_category: str
    ) -> bool:
        """
        Verifies if BBMP entry family matches BTP event cause.
        Example:
          BBMP 'Road Maintenance(Engg)' -> 'Potholes' (LOCALYN: ROAD_DAMAGE, BTP: pot_holes)
          Matches BTP cause 'pot_holes' -> True.
        """
        entry = self.get_mapping(bbmp_category, bbmp_sub_category)
        if not entry or not entry.is_eligible:
            return False

        btp_norm = self._norm(btp_cause_or_category).replace(" ", "_").replace("-", "_")
        expected_btp = self._norm(entry.btp_event_cause).replace(" ", "_").replace("-", "_")
        localyn_cat = self._norm(entry.localyn_category)

        # Direct cause match
        if btp_norm == expected_btp or btp_norm in expected_btp or expected_btp in btp_norm:
            return True

        # Family alias match
        mapped_target = EVENT_FAMILIES.get(entry.localyn_category)
        if mapped_target and (btp_norm == mapped_target or btp_norm in mapped_target or mapped_target in btp_norm):
            return True

        # Normalized category match (e.g. TRAFFIC, ROAD_DAMAGE)
        if btp_norm == localyn_cat:
            return True

        return False

    def get_summary(self) -> Dict[str, Any]:
        """Provides statistical breakdown of the 2023-2024 crosswalk dataset."""
        strength_counts: Dict[str, int] = {}
        strength_volumes: Dict[str, int] = {}
        for e in self.entries:
            strength_counts[e.mapping_strength] = strength_counts.get(e.mapping_strength, 0) + 1
            strength_volumes[e.mapping_strength] = strength_volumes.get(e.mapping_strength, 0) + e.total_count

        total_records = sum(e.total_count for e in self.entries)
        eligible_records = sum(e.total_count for e in self.entries if e.is_eligible)

        return {
            "total_categories_mapped": len(self.entries),
            "total_bbmp_records_covered": total_records,
            "eligible_bbmp_records": eligible_records,
            "eligibility_rate_pct": round((eligible_records / total_records * 100), 2) if total_records else 0.0,
            "counts_by_strength": strength_counts,
            "volume_by_strength": strength_volumes,
            "active_event_families": sorted(list(set(e.localyn_category for e in self.entries if e.is_eligible)))
        }


# Global cached singleton for application-wide fast lookup
_crosswalk_instance: Optional[CrosswalkRegistry] = None

def get_crosswalk() -> CrosswalkRegistry:
    global _crosswalk_instance
    if _crosswalk_instance is None:
        _crosswalk_instance = CrosswalkRegistry()
    return _crosswalk_instance
