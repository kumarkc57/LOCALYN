"""
LOCALYN Geo Module
Spatial indexing, Bengaluru 225-ward point-in-polygon containment, and ward resolution.
"""

from backend.app.geo.wards import (
    BENGALURU_WARD_BOUNDARIES,
    LEGACY_198_TO_225_MAP,
    WardBoundaryService,
    get_ward_service,
    point_in_polygon,
    resolve_point_to_ward,
    normalize_ward_name,
    calculate_ward_compatibility,
    haversine_distance_km
)

__all__ = [
    "BENGALURU_WARD_BOUNDARIES",
    "LEGACY_198_TO_225_MAP",
    "WardBoundaryService",
    "get_ward_service",
    "point_in_polygon",
    "resolve_point_to_ward",
    "normalize_ward_name",
    "calculate_ward_compatibility",
    "haversine_distance_km"
]
