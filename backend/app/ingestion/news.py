import re
import uuid
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
import requests

from backend.app.config import NEWSDATA_API_KEY, NEWSDATA_BASE_URL
from backend.app.database.db import is_duplicate_news

logger = logging.getLogger("localyn.ingestion.news")

# Real-time Bengaluru civic & transit RSS feed
LIVE_BENGALURU_RSS_URL = (
    "https://news.google.com/rss/search?q=Bengaluru+traffic+OR+Bangalore+weather+OR+Bengaluru+roads&hl=en-IN&gl=IN&ceid=IN:en"
)

def normalize_title(title: str) -> str:
    """
    Deterministic normalization:
    - Lowercase
    - Punctuation removal
    - Whitespace normalization
    """
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def clean_rss_text(html_text: str) -> str:
    """Removes basic HTML tags from RSS descriptions."""
    if not html_text:
        return ""
    return re.sub(r"<[^>]+>", "", html_text).strip()

def fetch_live_rss_feed() -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Fetches real-time live Bengaluru news from verified Indian outlets
    (The Hindu, Deccan Herald, Times of India, Indian Express).
    """
    reports: List[Dict[str, Any]] = []
    duplicate_count = 0
    errors: List[str] = []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(LIVE_BENGALURU_RSS_URL, headers=headers, timeout=12)
        if res.status_code != 200:
            errors.append(f"Live RSS HTTP {res.status_code}")
            return reports, duplicate_count, errors

        root = ET.fromstring(res.content)
        items = root.findall(".//item")

        for item in items[:15]:
            title_el = item.find("title")
            raw_title = title_el.text if title_el is not None else ""
            if not raw_title:
                continue

            # Clean trailing outlet name if present (e.g. "Title - The Hindu")
            clean_title = re.sub(r"\s*-\s*[^-]+$", "", raw_title).strip()
            norm_title = normalize_title(clean_title)

            source_el = item.find("source")
            source_name = source_el.text if source_el is not None else "Bengaluru Live Civic Wire"

            if is_duplicate_news(source=source_name, normalized_title=norm_title, within_hours=24):
                duplicate_count += 1
                continue

            link_el = item.find("link")
            article_url = link_el.text if link_el is not None else None

            desc_el = item.find("description")
            description = clean_rss_text(desc_el.text) if desc_el is not None else ""
            raw_text = f"{clean_title}\n\n{description}".strip()

            pubdate_el = item.find("pubDate")
            event_time = pubdate_el.text if pubdate_el is not None else datetime.now(timezone.utc).isoformat()

            reports.append({
                "id": str(uuid.uuid4()),
                "source": source_name,
                "source_type": "news",
                "title": clean_title,
                "raw_text": raw_text,
                "url": article_url,
                "event_time": event_time,
                "normalized_title": norm_title,
                "ingested_at": datetime.now(timezone.utc).isoformat()
            })

    except Exception as e:
        err = f"Failed fetching live RSS feed: {str(e)}"
        logger.warning(err)
        errors.append(err)

    return reports, duplicate_count, errors

def fetch_news() -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Fetches real-time Bengaluru local news combining:
    1. NewsData.io API (with user API key)
    2. Real-time live Bengaluru news feed
    Returns:
      (reports_to_insert, duplicate_count, error_messages)
    """
    all_reports: List[Dict[str, Any]] = []
    total_duplicates = 0
    all_errors: List[str] = []

    # 1. Fetch from NewsData.io
    if NEWSDATA_API_KEY and not NEWSDATA_API_KEY.startswith("your_"):
        queries = ["Bengaluru", "Bengaluru traffic"]
        for q in queries:
            try:
                params = {
                    "apikey": NEWSDATA_API_KEY,
                    "q": q,
                    "language": "en"
                }
                response = requests.get(NEWSDATA_BASE_URL, params=params, timeout=12)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

                    for item in results:
                        raw_title = item.get("title") or "Untitled Report"
                        norm_title = normalize_title(raw_title)
                        source_name = item.get("source_name") or item.get("source_id") or "NewsData"

                        if is_duplicate_news(source=source_name, normalized_title=norm_title, within_hours=24):
                            total_duplicates += 1
                            continue

                        # Also deduplicate within the current batch
                        if any(r["normalized_title"] == norm_title for r in all_reports):
                            total_duplicates += 1
                            continue

                        article_url = item.get("link")
                        description = item.get("description") or ""
                        content = item.get("content") or ""
                        raw_text = f"{raw_title}\n\n{description}\n\n{content}".strip()
                        pub_date = item.get("pubDate") or datetime.now(timezone.utc).isoformat()

                        all_reports.append({
                            "id": str(uuid.uuid4()),
                            "source": source_name,
                            "source_type": "news",
                            "title": raw_title,
                            "raw_text": raw_text,
                            "url": article_url,
                            "event_time": pub_date,
                            "normalized_title": norm_title,
                            "ingested_at": datetime.now(timezone.utc).isoformat()
                        })
                else:
                    all_errors.append(f"NewsData.io HTTP {response.status_code}: {response.text[:150]}")
            except Exception as e:
                all_errors.append(f"NewsData request error for query '{q}': {str(e)}")

    # 2. Fetch from Live Real-Time Feed
    live_reports, live_dupes, live_errs = fetch_live_rss_feed()
    all_errors.extend(live_errs)
    total_duplicates += live_dupes

    for rep in live_reports:
        if not any(r["normalized_title"] == rep["normalized_title"] for r in all_reports):
            all_reports.append(rep)
        else:
            total_duplicates += 1

    return all_reports, total_duplicates, all_errors
