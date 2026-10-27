import logging
import time
from typing import Any, Dict, List, Tuple

import requests
from dateutil import parser as date_parser

logger = logging.getLogger("localyn.bbmp")

CKAN_BASE_URL = "https://data.opencity.in/api/3/action"
DEFAULT_RESOURCE_ID = "1342a93b-9a61-4766-9c34-c8357b7926c2"
DEFAULT_BATCH_SIZE = 500


def _verify_resource(resource_id: str) -> bool:
    """Confirm that the given CKAN resource is the BBMP grievance dataset.

    Returns ``True`` if the resource name or description contains the term
    ``bbmp`` (case‑insensitive).  If the request fails (timeout, network error),
    we log a warning and **optimistically assume** the resource is correct – the
    downstream fetch will still attempt to retrieve data.
    """
    try:
        resp = requests.get(
            f"{CKAN_BASE_URL}/resource_show",
            params={"id": resource_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("result", {})
        name = data.get("name", "").lower()
        description = data.get("description", "").lower()
        if "bbmp" in name or "bbmp" in description:
            return True
        logger.warning(
            "Resource %s does not appear to be the BBMP grievance dataset (name=%s)",
            resource_id,
            name,
        )
        return False
    except Exception as e:
        logger.warning(
            "Could not verify CKAN resource %s due to %s – proceeding with fetch",
            resource_id,
            e,
        )
        return True

    """Confirm that the given CKAN resource is the BBMP grievance dataset.

    Returns ``True`` if the resource name or description contains the term
    ``bbmp`` (case‑insensitive).  Logs a warning and returns ``False`` otherwise.
    """
    try:
        resp = requests.get(
            f"{CKAN_BASE_URL}/resource_show",
            params={"id": resource_id},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("result", {})
        name = data.get("name", "").lower()
        description = data.get("description", "").lower()
        if "bbmp" in name or "bbmp" in description:
            return True
        logger.warning(
            "Resource %s does not appear to be the BBMP grievance dataset (name=%s)",
            resource_id,
            name,
        )
    except Exception as e:
        logger.error("Failed to verify CKAN resource %s: %s", resource_id, e)
    return False


def _normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a raw CKAN record into the internal ``raw_report`` format.

    The function is defensive – missing keys result in ``None`` values.  It also
    builds a minimal ``title`` from the BBMP ``category`` and ``sub_category``.
    """
    # Basic identifiers
    complaint_id = record.get("complaint_id") or record.get("id")
    if not complaint_id:
        logger.debug("Skipping record without complaint_id: %s", record)
        return {}

    category = record.get("category", "").strip()
    sub_category = record.get("sub_category", "").strip()
    title = f"{category} – {sub_category}" if category or sub_category else "BBMP Grievance"

    # Text content – combine staff remarks and any free description field
    staff_remarks = record.get("staff_remarks", "")
    description = record.get("description", "")
    raw_text = "\n".join(filter(None, [staff_remarks, description]))

    # Parse the grievance timestamp – BBMP uses ISO‑like strings
    raw_time = record.get("grievance_date") or record.get("date")
    event_time = None
    if raw_time:
        try:
            dt = date_parser.isoparse(str(raw_time))
            # Store as ISO‑8601 UTC (the dataset is already local time; we keep it as‑is)
            event_time = dt.isoformat()
        except Exception:
            logger.warning("Unable to parse grievance_date %s", raw_time)
            event_time = None

    # Geographic information
    latitude = record.get("latitude")
    longitude = record.get("longitude")
    try:
        if latitude is not None:
            latitude = float(latitude)
        if longitude is not None:
            longitude = float(longitude)
    except Exception:
        logger.warning("Invalid lat/lon in record %s", complaint_id)
        latitude = longitude = None

    # Ward name – keep as location string
    ward_name = record.get("ward_name")

    # Assemble the raw_report dict expected by the pipeline
    raw_report: Dict[str, Any] = {
        "id": str(complaint_id),
        "source": "bbmp",
        "source_type": "bbmp",
        "title": title,
        "raw_text": raw_text,
        "url": None,
        "category": "OTHER",  # will be overridden by classifier later
        "location": ward_name,
        "latitude": latitude,
        "longitude": longitude,
        "event_time": event_time or "",
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return raw_report


def fetch_bbmp(
    resource_id: str = DEFAULT_RESOURCE_ID,
    batch_size: int = DEFAULT_BATCH_SIZE,
    start: int = 0,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fetch BBMP grievance records from the CKAN datastore.

    Returns a tuple ``(reports, errors)`` where ``reports`` is a list of normalized
    ``raw_report`` dictionaries ready for ``process_and_store_report``.
    """
    if not _verify_resource(resource_id):
        return [], [f"Resource {resource_id} failed verification as BBMP dataset."]

    reports: List[Dict[str, Any]] = []
    errors: List[str] = []
    offset = start
    while True:
        try:
            resp = requests.get(
                f"{CKAN_BASE_URL}/datastore_search",
                params={
                    "resource_id": resource_id,
                    "limit": batch_size,
                    "offset": offset,
                },
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json().get("result", {})
            records = payload.get("records", [])
            if not records:
                break
            for rec in records:
                norm = _normalize_record(rec)
                if norm:
                    reports.append(norm)
            offset += batch_size
        except requests.HTTPError as http_err:
            msg = f"HTTP error while fetching BBMP data (offset {offset}): {http_err}"
            logger.error(msg)
            errors.append(msg)
            break
        except Exception as exc:
            msg = f"Unexpected error while fetching BBMP data (offset {offset}): {exc}"
            logger.error(msg)
            errors.append(msg)
            break
    return reports, errors
