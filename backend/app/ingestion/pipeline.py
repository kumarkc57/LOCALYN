import re
import logging
from typing import Dict, Any, List, Optional
from backend.app.ingestion.news import fetch_news
from backend.app.ingestion.weather import fetch_weather
from backend.app.nlp.spacy_extractor import extract_entities, BENGALURU_LOCALITIES
from backend.app.classifier.classifier import classify_text
from backend.app.chef.calculator import compute_partial_chef
from backend.app.database.db import (
    insert_report,
    count_corroborating_reports,
    is_duplicate_news
)
from backend.app.geo.wards import resolve_point_to_ward

logger = logging.getLogger("localyn.pipeline")

# Keywords that clearly indicate national/international non-Bengaluru topics
IRRELEVANT_TOPIC_EXCLUSIONS = [
    "nba", "clippers", "lakers", "49ers", "super bowl", "nfl", "mlb",
    "premier league", "la liga", "bcci meeting in mumbai", "in mumbai",
    "in delhi", "in kolkata", "in chennai", "in london", "australian open",
    "formula 1", "f1 grand prix"
]

def is_bengaluru_relevant(title: str, text: str) -> bool:
    """Accept Bengaluru civic reports, not unrelated stories that merely mention the city."""
    full_text = f"{title}\n{text}".lower()

    for excl in IRRELEVANT_TOPIC_EXCLUSIONS:
        if re.search(rf"\b{re.escape(excl)}\b", full_text):
            title_lower = title.lower()
            if not any(
                re.search(rf"\b{re.escape(loc)}\b", title_lower)
                for loc in [
                    "bengaluru", "bangalore", "silk board",
                    "outer ring road", "hebbal", "indiranagar", "whitefield"
                ]
            ):
                return False

    has_location = any(
        re.search(rf"\b{re.escape(loc.lower())}\b", full_text)
        for loc in BENGALURU_LOCALITIES
    )

    civic_keywords = [
        "traffic", "congestion", "road", "pothole", "accident",
        "rain", "flood", "flooding", "waterlogging", "weather",
        "civic", "bbmp", "municipal", "garbage", "waste",
        "drainage", "sewage", "water supply", "power outage",
        "tree fall", "infrastructure", "construction", "metro"
    ]
    has_civic_topic = any(word in full_text for word in civic_keywords)

    return has_location and has_civic_topic


def process_and_store_report(raw_report: Dict[str, Any], path: Optional[str] = None) -> Optional[str]:
    """
    Executes the full telemetry processing pipeline on a single report:
    1. Relevance check (strictly ensures only Bengaluru-specific news is accepted)
    2. NLP extraction (safe null fallback)
    3. Classification (context-aware strong/weak rules)
    4. CHEF calculation
    5. SQLite persistence.
    """
    title = raw_report.get("title", "")
    raw_text = raw_report.get("raw_text", "")
    text_content = f"{title}\n{raw_text}"
    is_news = raw_report.get("source_type") == "news"

    # Step 1: Relevance Check for News
    if is_news:
        if not is_bengaluru_relevant(title, raw_text):
            logger.info("Rejected news article '%s' - not specifically related to Bengaluru.", title)
            return None

    # Step 2: NLP Extraction (Section 7)
    extracted_loc, extracted_time = extract_entities(text_content)

    # Safe null fallback: never invent Bengaluru if no location was identified
    final_location = raw_report.get("location") or extracted_loc
    if not final_location and raw_report.get("latitude") and raw_report.get("longitude"):
        ward_res = resolve_point_to_ward(raw_report["latitude"], raw_report["longitude"])
        if ward_res:
            final_location = ward_res["ward_name"]

    # Step 3: Classification (Section 8: TRAFFIC, WEATHER, OTHER)
    if raw_report.get("source_type") == "weather_api":
        category = "WEATHER"
    else:
        category = classify_text(text_content)

    # Step 4: Corroboration lookup from SQLite
    corroboration_count = count_corroborating_reports(
        category=category,
        location=final_location,
        within_hours=24,
        path=path
    )

    # Step 5: Partial CHEF Confidence Calculation (Section 9)
    chef_result = compute_partial_chef(
        source=raw_report["source"],
        source_type=raw_report.get("source_type", "news"),
        event_time=raw_report["event_time"],
        corroborating_count=corroboration_count
    )

    # Assemble report record
    record = {
        "id": raw_report["id"],
        "source": raw_report["source"],
        "source_type": raw_report.get("source_type", "news"),
        "title": raw_report["title"],
        "raw_text": raw_report["raw_text"],
        "url": raw_report.get("url"),
        "category": category,
        "location": final_location,
        "latitude": raw_report.get("latitude"),
        "longitude": raw_report.get("longitude"),
        "event_time": raw_report["event_time"],
        "confidence": chef_result["confidence"],
        "confidence_tier": chef_result["confidence_tier"],
        "chef_factors": chef_result["chef"],
        "normalized_title": raw_report.get("normalized_title", ""),
        "ingested_at": raw_report["ingested_at"]
    }

    # Step 6: Persist in SQLite
    inserted_id = insert_report(record, path=path)
    return inserted_id

def run_ingestion_pipeline(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes an end-to-end ingestion cycle:
    1. Fetch news from NewsData.io (with 24h deduplication)
    2. Filter strictly for Bengaluru-specific relevance
    3. Fetch weather from OpenWeatherMap
    4. Run NLP, classification, CHEF scoring, and store in SQLite
    """
    all_errors: List[str] = []
    news_inserted = 0
    news_rejected = 0
    weather_inserted = 0

    # Step 1: News Ingestion
    news_items, news_skipped, news_errors = fetch_news()
    all_errors.extend(news_errors)

    for item in news_items:
        try:
            result_id = process_and_store_report(item, path=path)
            if result_id:
                news_inserted += 1
            else:
                news_rejected += 1
        except Exception as e:
            err = f"Failed processing news report '{item.get('title')}': {str(e)}"
            logger.error(err)
            all_errors.append(err)

    # Step 2: Weather Ingestion (OpenWeatherMap Bengaluru sensor)
    weather_item, weather_errors = fetch_weather()
    all_errors.extend(weather_errors)

    if weather_item:
        try:
            result_id = process_and_store_report(weather_item, path=path)
            if result_id:
                weather_inserted += 1
        except Exception as e:
            err = f"Failed processing weather report: {str(e)}"
            logger.error(err)
            all_errors.append(err)

    status = "success"
    if all_errors and (news_inserted > 0 or weather_inserted > 0):
        status = "partial"
    elif all_errors and news_inserted == 0 and weather_inserted == 0:
        status = "warning_no_data_or_keys"

    return {
        "status": status,
        "news_fetched": len(news_items),
        "news_inserted": news_inserted,
        "news_rejected_not_bengaluru": news_rejected,
        "news_skipped_duplicates": news_skipped,
        "weather_fetched": 1 if weather_item else 0,
        "weather_inserted": weather_inserted,
        "errors": all_errors
    }
