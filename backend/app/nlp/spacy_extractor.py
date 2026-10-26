import re
from typing import Tuple, Optional
import spacy

# List of prominent Bengaluru localities and landmarks for civic intelligence
BENGALURU_LOCALITIES = [
    "Indiranagar", "Koramangala", "Whitefield", "Hebbal", "Silk Board",
    "Outer Ring Road", "ORR", "MG Road", "Brigade Road", "Electronic City",
    "Marathahalli", "Bellandur", "Jayanagar", "JP Nagar", "Malleshwaram",
    "Majestic", "Yeshwanthpur", "Yelahanka", "HSR Layout", "Banashankari",
    "BTM Layout", "Domlur", "Shivajinagar", "Rajajinagar", "Basavanagudi",
    "Kalyan Nagar", "Kammanahalli", "Sarjapur", "Bannerghatta", "Varthur",
    "Tin Factory", "K.R. Puram", "KR Puram", "Mekhri Circle", "Goraguntepalya",
    "Frazer Town", "Richmond Town", "Cunningham Road", "Kengeri", "Nagarbhavi",
    "Bengaluru", "Bangalore"
]

# Common temporal expressions
TIME_PATTERNS = [
    r"\b(?:early\s+)?morning\b",
    r"\b(?:late\s+)?afternoon\b",
    r"\b(?:rush\s+hour|peak\s+hours?)\b",
    r"\b(?:evening|tonight|night)\b",
    r"\b(?:today|yesterday|tomorrow)\b",
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)\b",
    r"\b\d{1,2}\s+(?:hours?|hrs?|mins?|minutes?)\s+ago\b"
]

_nlp = None

def get_nlp_pipeline():
    global _nlp
    if _nlp is not None:
        return _nlp

    try:
        # Attempt to load pretrained English model
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        # Fallback to blank model with custom EntityRuler
        _nlp = spacy.blank("en")
        ruler = _nlp.add_pipe("entity_ruler")
        patterns = []
        for loc in BENGALURU_LOCALITIES:
            patterns.append({"label": "GPE", "pattern": loc})
        for tp in ["morning", "afternoon", "evening", "night", "today", "yesterday", "rush hour"]:
            patterns.append({"label": "TIME", "pattern": tp})
        ruler.add_patterns(patterns)
    return _nlp

def extract_entities(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts (LOCATION, TIME) from text using spaCy with rule-based fallback.
    Returns (None, None) if not found.
    """
    if not text:
        return None, None

    nlp = get_nlp_pipeline()
    doc = nlp(text)

    location: Optional[str] = None
    time_str: Optional[str] = None

    # Step 1: Check spaCy extracted entities
    for ent in doc.ents:
        if not location and ent.label_ in ("GPE", "LOC", "FAC"):
            location = ent.text.strip()
        elif not time_str and ent.label_ in ("TIME", "DATE"):
            time_str = ent.text.strip()

    # Step 2: Fallback scan for Bengaluru localities if location is still None
    if not location:
        text_lower = text.lower()
        for loc in BENGALURU_LOCALITIES:
            # Word boundary matching
            pattern = rf"\b{re.escape(loc.lower())}\b"
            if re.search(pattern, text_lower):
                location = loc
                break

    # Step 3: Fallback scan for temporal phrases if time_str is still None
    if not time_str:
        for t_pat in TIME_PATTERNS:
            match = re.search(t_pat, text, re.IGNORECASE)
            if match:
                time_str = match.group(0).strip()
                break

    return location, time_str
