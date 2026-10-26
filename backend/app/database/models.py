from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class CHEFFactors(BaseModel):
    source_reliability: float = Field(..., ge=0.0, le=1.0, description="Source reliability score (0.0 to 1.0)")
    temporal_consistency: float = Field(..., ge=0.0, le=1.0, description="Temporal consistency/recency score (0.0 to 1.0)")
    corroboration: float = Field(..., ge=0.0, le=1.0, description="Corroboration score based on co-occurring reports (0.0 to 1.0)")
    source_agreement: float = Field(default=1.0, ge=0.0, le=1.0, description="Cross-source agreement (baseline constant: 1.0)")
    geographic_consistency: float = Field(default=1.0, ge=0.0, le=1.0, description="Geographic consistency (baseline constant: 1.0)")

class ReportBase(BaseModel):
    source: str
    source_type: str = "news"  # 'news' | 'weather_api' | 'other'
    title: str
    raw_text: str
    url: Optional[str] = None
    category: str  # 'TRAFFIC' | 'WEATHER' | 'OTHER'
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_time: str
    confidence: float
    confidence_tier: str  # 'HIGH' | 'MODERATE' | 'LOW'
    chef_factors: CHEFFactors

class ReportCreate(ReportBase):
    pass

class ReportResponse(ReportBase):
    id: str
    ingested_at: str

class IngestionSummary(BaseModel):
    status: str
    news_fetched: int
    news_inserted: int
    news_skipped_duplicates: int
    weather_fetched: int
    weather_inserted: int
    errors: list[str] = []

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database_connected: bool
    total_reports: int
    has_newsdata_key: bool
    has_openweather_key: bool
    auto_ingest: Optional[Dict[str, Any]] = None


# --- Multi-Agency Fusion Schemas ---

class CrosswalkItemResponse(BaseModel):
    category: str
    sub_category: str
    count_2023: int
    count_2024: int
    total_count: int
    localyn_category: str
    btp_event_cause: str
    mapping_strength: str
    matching_use: str

class CrosswalkSummaryResponse(BaseModel):
    total_categories_mapped: int
    total_bbmp_records_covered: int
    eligible_bbmp_records: int
    eligibility_rate_pct: float
    counts_by_strength: Dict[str, int]
    volume_by_strength: Dict[str, int]
    active_event_families: List[str]

class FullCHEFFactors(BaseModel):
    source_diversity: float
    source_reliability: float
    source_agreement: float
    geographic_consistency: float
    temporal_consistency: float

class CanonicalEventResponse(BaseModel):
    id: str
    title: str
    category: str
    ward_name: str
    ward_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    earliest_time: Optional[str] = None
    latest_time: Optional[str] = None
    participating_agencies: List[str]
    source_diversity_count: int
    observations_count: int
    confidence: float
    confidence_tier: str
    chef_factors: FullCHEFFactors
    explainability_summary: str
    observations: List[Dict[str, Any]]

class BaselineMetric(BaseModel):
    name: str
    description: str
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1: float

class BenchmarkResponse(BaseModel):
    gold_set_size: int
    evaluated_pairs: int
    results: Dict[str, BaselineMetric]
    markdown_table: str


class WardItemResponse(BaseModel):
    ward_id: int
    ward_no: int
    ward_name: str
    ward_name_ka: Optional[str] = ""
    proposed_ward_name_en: Optional[str] = ""
    assembly_constituency: Optional[str] = ""
    assembly_constituency_id: Optional[int] = None
    parliamentary_constituency: Optional[str] = ""
    population: Optional[int] = 0
    ward_area: Optional[float] = 0.0
    centroid: Optional[List[float]] = None


class WardLookupRequest(BaseModel):
    latitude: float
    longitude: float


class WardLookupResponse(BaseModel):
    ward_key: str
    ward_no: int
    ward_id: int
    ward_name: str
    ward_name_ka: Optional[str] = ""
    zone: Optional[str] = ""
    assembly_constituency: Optional[str] = ""
    assembly_constituency_id: Optional[int] = None
    parliamentary_constituency: Optional[str] = ""
    population: Optional[int] = 0
    ward_area: Optional[float] = 0.0
    centroid: Optional[List[float]] = None
    method: str
    confidence: float
    resolution_status: str
    distance_km: Optional[float] = None
    boundary_wards: Optional[List[str]] = None


# --- Live Weather Intelligence Models ---

class WeatherAlert(BaseModel):
    level: str  # 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED'
    severity: str  # 'NORMAL' | 'ADVISORY' | 'WARNING' | 'SEVERE'
    title: str
    message: str
    rainfall_rate_mm: float
    precipitation_probability: Optional[int] = None
    risk_disclaimer: str
    issued_at: str


class WeatherCurrent(BaseModel):
    temperature: float
    feels_like: float
    humidity: int
    precipitation: float
    rain: float
    precipitation_probability: Optional[int] = None
    weather_code: int
    condition: str
    wind_speed: float
    time: str


class WeatherHourlyItem(BaseModel):
    time: str
    temperature: float
    precipitation: float
    precipitation_probability: Optional[int] = None
    weather_code: int
    condition: str


class WeatherDailyItem(BaseModel):
    date: str
    weather_code: int
    condition: str
    temp_max: float
    temp_min: float
    precipitation_sum: float
    precipitation_probability_max: Optional[int] = None


class LiveWeatherResponse(BaseModel):
    status: str  # 'live' | 'degraded' | 'error'
    is_live: bool
    source: str
    source_url: str
    city: str
    latitude: float
    longitude: float
    current: Optional[WeatherCurrent] = None
    hourly_forecast: List[WeatherHourlyItem] = []
    daily_forecast: List[WeatherDailyItem] = []
    alerts: List[WeatherAlert] = []
    error: Optional[str] = None
    fetched_at: str
