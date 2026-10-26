import sqlite3
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from backend.app.config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    url TEXT,
    category TEXT NOT NULL,
    location TEXT,
    latitude REAL,
    longitude REAL,
    event_time TEXT NOT NULL,
    confidence REAL NOT NULL,
    confidence_tier TEXT NOT NULL,
    chef_factors TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category);
CREATE INDEX IF NOT EXISTS idx_reports_ingested_at ON reports(ingested_at);
CREATE INDEX IF NOT EXISTS idx_reports_source_norm_title ON reports(source, normalized_title);
"""

def get_connection(path: Optional[str] = None) -> sqlite3.Connection:
    target_path = path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(path: Optional[str] = None):
    conn = get_connection(path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()

# Auto-initialize database on import for convenience
init_db()

def is_duplicate_news(source: str, normalized_title: str, within_hours: int = 24, path: Optional[str] = None) -> bool:
    """
    Checks if a report with the same source and near-identical normalized title
    was already ingested within the previous `within_hours` hours.
    """
    if not normalized_title:
        return False

    cutoff = (datetime.utcnow() - timedelta(hours=within_hours)).isoformat()
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM reports
            WHERE source = ?
              AND normalized_title = ?
              AND ingested_at >= ?
            LIMIT 1
            """,
            (source, normalized_title, cutoff)
        )
        row = cursor.fetchone()
        return row is not None
    finally:
        conn.close()

def insert_report(report_data: Dict[str, Any], path: Optional[str] = None) -> str:
    """
    Inserts a processed report into SQLite.
    """
    conn = get_connection(path)
    try:
        with conn:
            chef_factors_str = (
                json.dumps(report_data["chef_factors"])
                if isinstance(report_data["chef_factors"], dict)
                else report_data["chef_factors"]
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (
                    id, source, source_type, title, raw_text, url,
                    category, location, latitude, longitude,
                    event_time, confidence, confidence_tier,
                    chef_factors, normalized_title, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_data["id"],
                    report_data["source"],
                    report_data.get("source_type", "news"),
                    report_data["title"],
                    report_data["raw_text"],
                    report_data.get("url"),
                    report_data["category"],
                    report_data.get("location"),
                    report_data.get("latitude"),
                    report_data.get("longitude"),
                    report_data["event_time"],
                    float(report_data["confidence"]),
                    report_data["confidence_tier"],
                    chef_factors_str,
                    report_data.get("normalized_title", ""),
                    report_data["ingested_at"]
                )
            )
        return report_data["id"]
    finally:
        conn.close()

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("chef_factors"), str):
        try:
            d["chef_factors"] = json.loads(d["chef_factors"])
        except Exception:
            d["chef_factors"] = {}
    return d

def get_report_by_id(report_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)
        return None
    finally:
        conn.close()

def get_reports(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    path: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM reports WHERE 1=1"
        params: List[Any] = []

        if category and category.upper() != "ALL":
            query += " AND category = ?"
            params.append(category.upper())

        if search:
            query += " AND (title LIKE ? OR raw_text LIKE ? OR location LIKE ?)"
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard])

        query += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()

def count_reports(category: Optional[str] = None, path: Optional[str] = None) -> int:
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        if category and category.upper() != "ALL":
            cursor.execute("SELECT COUNT(*) FROM reports WHERE category = ?", (category.upper(),))
        else:
            cursor.execute("SELECT COUNT(*) FROM reports")
        return cursor.fetchone()[0]
    finally:
        conn.close()

def count_corroborating_reports(
    category: str,
    location: Optional[str] = None,
    within_hours: int = 24,
    exclude_id: Optional[str] = None,
    path: Optional[str] = None
) -> int:
    """
    Counts how many other reports share the same category (or location)
    within the given timeframe to compute corroboration.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=within_hours)).isoformat()
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM reports WHERE ingested_at >= ? AND category = ?"
        params: List[Any] = [cutoff, category]

        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)

        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")

        cursor.execute(query, params)
        return cursor.fetchone()[0]
    finally:
        conn.close()
