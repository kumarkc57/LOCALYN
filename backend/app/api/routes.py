from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.app.database.db import (
    get_reports,
    get_report_by_id,
    count_reports,
    get_connection
)
from backend.app.database.models import (
    ReportResponse,
    HealthResponse,
    IngestionSummary
)
from backend.app.config import NEWSDATA_API_KEY, OPENWEATHER_API_KEY
from backend.app.ingestion.pipeline import run_ingestion_pipeline
from backend.app.ingestion.scheduler import scheduler

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Confirms backend is running, SQLite is reachable, and reports system stats.
    """
    db_connected = False
    report_count = 0
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_connected = True
        report_count = count_reports()
    except Exception:
        db_connected = False

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "LOCALYN Hyperlocal Intelligence Backend",
        "version": "1.0.0",
        "database_connected": db_connected,
        "total_reports": report_count,
        "has_newsdata_key": bool(NEWSDATA_API_KEY and not NEWSDATA_API_KEY.startswith("your_")),
        "has_openweather_key": bool(OPENWEATHER_API_KEY and not OPENWEATHER_API_KEY.startswith("your_")),
        "auto_ingest": scheduler.get_status()
    }

@router.get("/reports", response_model=List[ReportResponse])
def list_reports(
    category: Optional[str] = Query(None, description="Filter by category (TRAFFIC, WEATHER, OTHER, or ALL)"),
    search: Optional[str] = Query(None, description="Keyword search in title, raw_text, or location"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Retrieves persisted reports from SQLite, ordered by newest first.
    Supports category filtering and keyword searching.
    """
    reports = get_reports(category=category, search=search, limit=limit, offset=offset)
    return reports

@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_single_report(report_id: str):
    """
    Returns a single report by ID along with its full CHEF confidence breakdown factors.
    """
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report with id '{report_id}' not found.")
    return report

@router.post("/ingest", response_model=IngestionSummary)
def trigger_ingestion():
    """
    Triggers an on-demand ingestion run:
    Fetches latest real data from NewsData.io and OpenWeatherMap,
    applies spaCy extraction, deterministic classification, CHEF calculation,
    and stores new records in SQLite.
    """
    summary = run_ingestion_pipeline()
    return summary


# =====================================================================
# Multi-Agency Fusion, Crosswalk Taxonomy & Benchmark Endpoints
# =====================================================================

from backend.app.database.models import (
    CrosswalkItemResponse,
    CrosswalkSummaryResponse,
    CanonicalEventResponse,
    BenchmarkResponse
)
from backend.app.fusion.crosswalk import get_crosswalk
from backend.app.fusion.matcher import CandidateGenerator, CandidatePair
from backend.app.fusion.cluster import cluster_matched_pairs
from backend.app.fusion.gold_set import get_gold_set
from backend.app.evaluation.benchmark import run_full_benchmark, generate_benchmark_markdown_table


@router.get("/fusion/crosswalk/summary", response_model=CrosswalkSummaryResponse)
def get_crosswalk_summary():
    """
    Returns statistical summary of the BBMP (2023-2024) to BTP taxonomy crosswalk.
    """
    registry = get_crosswalk()
    return registry.get_summary()


@router.get("/fusion/crosswalk/mappings", response_model=List[CrosswalkItemResponse])
def get_crosswalk_mappings(
    strength: Optional[str] = Query(None, description="Filter by Mapping_Strength: Direct, Probable, Ambiguous, Do not map, or ALL"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Returns the indexed crosswalk mappings between BBMP municipal grievance categories
    and BTP traffic incident causes.
    """
    registry = get_crosswalk()
    entries = registry.entries

    if strength and strength.upper() != "ALL":
        entries = [e for e in entries if e.mapping_strength.lower() == strength.lower()]

    paginated = entries[offset : offset + limit]
    return [
        {
            "category": e.category,
            "sub_category": e.sub_category,
            "count_2023": e.count_2023,
            "count_2024": e.count_2024,
            "total_count": e.total_count,
            "localyn_category": e.localyn_category,
            "btp_event_cause": e.btp_event_cause,
            "mapping_strength": e.mapping_strength,
            "matching_use": e.matching_use
        }
        for e in paginated
    ]


@router.get("/fusion/canonical-events", response_model=List[CanonicalEventResponse])
def get_canonical_events():
    """
    Runs multi-agency fusion over the active observation corpus (BBMP complaints,
    BTP telemetry) and returns consolidated Canonical Events with Full CHEF confidence scores.
    """
    gold = get_gold_set()
    bbmp_records = [g["bbmp"] for g in gold]
    btp_records = [g["btp"] for g in gold]

    generator = CandidateGenerator()
    candidates = generator.generate_candidates(bbmp_records, btp_records)
    canonical_events = cluster_matched_pairs(candidates)

    return [e.to_dict() for e in canonical_events]


@router.get("/fusion/benchmark", response_model=BenchmarkResponse)
def get_benchmark_results():
    """
    Executes the empirical Baseline Benchmark comparing:
    - Baseline 1: Same Date + Same Ward
    - Baseline 2: Same Date + Same Ward + Naive Category
    - LOCALYN: Crosswalk Taxonomy + Spatial PIP + Multi-Feature Scorer
    Returns Precision, Recall, F1-Scores and the formatted LaTeX/Markdown table.
    """
    bench = run_full_benchmark()
    md_table = generate_benchmark_markdown_table(bench)

    return {
        "gold_set_size": bench["gold_set_size"],
        "evaluated_pairs": bench["evaluated_pairs"],
        "results": bench["results"],
        "markdown_table": md_table
    }


@router.post("/fusion/match")
def match_single_pair(payload: Dict[str, Any]):
    """
    Evaluates candidate generation and multi-feature scoring for a single BBMP-BTP pair.
    """
    bbmp = payload.get("bbmp")
    btp = payload.get("btp")
    if not bbmp or not btp:
        raise HTTPException(status_code=400, detail="Payload must include 'bbmp' and 'btp' objects.")

    generator = CandidateGenerator()
    is_cand, gate_reason = generator.is_candidate(bbmp, btp)

    pair = CandidatePair(bbmp, btp)

    return {
        "is_candidate": is_cand,
        "gating_reason": gate_reason,
        "match_score": pair.match_score,
        "is_match": pair.is_match,
        "features": pair.features,
        "explanations": pair.explanations
    }


# =====================================================================
# Bengaluru 225-Ward Geographic Intelligence Endpoints
# =====================================================================
from backend.app.geo.wards import get_ward_service, resolve_point_to_ward
from backend.app.database.models import (
    WardItemResponse,
    WardLookupRequest,
    WardLookupResponse
)


@router.get("/geo/wards", response_model=List[WardItemResponse])
def list_bengaluru_wards():
    """
    Returns the authoritative list of all 225 Bengaluru BBMP Wards
    with verified ward IDs, names, assembly constituencies, centroids, and areas.
    """
    service = get_ward_service()
    return service.get_all_wards()


@router.get("/geo/wards/geojson")
def get_bengaluru_wards_geojson():
    """
    Serves the complete authoritative 225-ward Bengaluru GeoJSON FeatureCollection.
    """
    service = get_ward_service()
    return service.get_geojson()


@router.get("/geo/wards/{ward_id}")
def get_ward_details(ward_id: int):
    """
    Returns verified spatial and demographic details for a specific Bengaluru ward by ID (1-225).
    """
    service = get_ward_service()
    if ward_id not in service.wards_by_id:
        raise HTTPException(status_code=404, detail=f"Ward ID {ward_id} not found in the 225-ward dataset.")
    w = service.wards_by_id[ward_id]
    return {
        "ward_id": w["ward_id"],
        "ward_no": w["ward_no"],
        "ward_name": w["ward_name"],
        "ward_name_ka": w["ward_name_ka"],
        "proposed_ward_name_en": w["proposed_ward_name_en"],
        "assembly_constituency": w["assembly_constituency"],
        "assembly_constituency_id": w["assembly_constituency_id"],
        "parliamentary_constituency": w["parliamentary_constituency"],
        "population": w["population"],
        "ward_area": w["ward_area"],
        "centroid": w["centroid"]
    }


@router.post("/geo/lookup", response_model=WardLookupResponse)
def lookup_coordinates_to_ward(payload: WardLookupRequest):
    """
    Resolves GPS latitude and longitude coordinates to the containing Bengaluru BBMP ward
    using spatial point-in-polygon containment and boundary conflict handling.
    """
    res = resolve_point_to_ward(payload.latitude, payload.longitude)
    if not res:
        raise HTTPException(
            status_code=404,
            detail=f"Coordinates ({payload.latitude}, {payload.longitude}) do not resolve to any Bengaluru ward boundary."
        )
    return res


# =====================================================================
# Live Bengaluru Weather Intelligence Endpoint
# =====================================================================
from backend.app.ingestion.weather import fetch_bengaluru_weather_intelligence
from backend.app.database.models import LiveWeatherResponse


@router.get("/weather/live", response_model=LiveWeatherResponse)
def get_live_weather():
    """
    Returns real-time Bengaluru weather observation, hourly near-term forecast,
    multi-day outlook, and documented rainfall risk alerts via Open-Meteo.
    """
    return fetch_bengaluru_weather_intelligence()
