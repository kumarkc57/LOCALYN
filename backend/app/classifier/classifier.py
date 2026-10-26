import re
from typing import List

# Strong traffic indicators that independently classify text as TRAFFIC
STRONG_TRAFFIC_TERMS = [
    "traffic jam", "traffic snarl", "road closure", "road closed",
    "road blocked", "road blockage", "vehicle collision", "vehicular collision",
    "traffic congestion", "traffic diversion", "slow-moving traffic", "traffic alert",
    "traffic", "congestion", "gridlock", "collision", "flyover", "pothole",
    "potholes", "snarl"
]

# Weak / context-dependent terms that MUST NOT independently classify text as TRAFFIC
WEAK_TRAFFIC_TERMS = [
    "road", "jam", "vehicle", "commute", "signal", "accident", "crash"
]

# Transit context keywords that give meaning to weak terms
TRANSIT_CONTEXT = [
    "car", "bus", "truck", "auto", "bike", "motorcycle", "pedestrian",
    "highway", "lane", "expressway", "commuter", "commuters", "junction",
    "flyover", "toll", "signal", "diverted", "stranded", "choked", "stalled",
    "overturned", "pileup", "outer ring road", "silk board"
]

# Weather indicators
STRONG_WEATHER_TERMS = [
    "rainfall", "thunderstorm", "monsoon", "shower", "downpour",
    "waterlogging", "waterlogged", "cyclone", "hailstorm", "flood", "flooding", "rain"
]

WEAK_WEATHER_TERMS = [
    "weather", "temperature", "wind", "humidity", "drizzle", "storm"
]

WEATHER_CONTEXT = [
    "celsius", "forecast", "met", "meteorological", "imd", "degrees",
    "heavy", "intense", "inundated", "overcast", "sensor", "observation"
]

def _matches_phrase(phrase: str, text_lower: str) -> bool:
    """Matches exact word-bounded phrase."""
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text_lower))

def classify_text(text: str) -> str:
    """
    Classifies text into strictly: TRAFFIC, WEATHER, or OTHER.
    The classification is deterministic and context-aware:
    - Strong terms independently qualify for a category.
    - Weak terms require co-occurrence with domain context.
    """
    if not text:
        return "OTHER"

    text_lower = text.lower()

    # --- 1. Evaluate Traffic Evidence ---
    has_strong_traffic = any(_matches_phrase(term, text_lower) for term in STRONG_TRAFFIC_TERMS)
    
    # Check weak traffic terms + transit context
    has_weak_traffic_with_context = False
    matching_weak_traffic = [w for w in WEAK_TRAFFIC_TERMS if _matches_phrase(w, text_lower)]
    
    if matching_weak_traffic:
        # A weak term is validated if:
        # 1. At least two distinct weak traffic terms co-occur (e.g. "vehicle" + "accident", "road" + "accident", "vehicle" + "road")
        # 2. OR a weak traffic term co-occurs with explicit transit context (e.g. "accident" + "car", "commute" + "highway")
        if len(matching_weak_traffic) >= 2:
            has_weak_traffic_with_context = True
        else:
            matching_context = [ctx for ctx in TRANSIT_CONTEXT if _matches_phrase(ctx, text_lower)]
            # Ensure the context term isn't identical to the weak term itself
            if any(ctx not in matching_weak_traffic for ctx in matching_context):
                has_weak_traffic_with_context = True

    is_traffic = has_strong_traffic or has_weak_traffic_with_context

    # --- 2. Evaluate Weather Evidence ---
    has_strong_weather = any(_matches_phrase(term, text_lower) for term in STRONG_WEATHER_TERMS)
    
    has_weak_weather_with_context = False
    matching_weak_weather = [w for w in WEAK_WEATHER_TERMS if _matches_phrase(w, text_lower)]
    if matching_weak_weather:
        if len(matching_weak_weather) >= 2:
            has_weak_weather_with_context = True
        else:
            matching_w_context = [ctx for ctx in WEATHER_CONTEXT if _matches_phrase(ctx, text_lower)]
            if any(ctx not in matching_weak_weather for ctx in matching_w_context):
                has_weak_weather_with_context = True

    is_weather = has_strong_weather or has_weak_weather_with_context

    # --- 3. Decision Resolution ---
    if is_traffic and not is_weather:
        return "TRAFFIC"
    elif is_weather and not is_traffic:
        return "WEATHER"
    elif is_traffic and is_weather:
        # Tie-breaker: prioritize whichever has more strong matches, or earlier occurrence
        strong_t_count = sum(1 for term in STRONG_TRAFFIC_TERMS if _matches_phrase(term, text_lower))
        strong_w_count = sum(1 for term in STRONG_WEATHER_TERMS if _matches_phrase(term, text_lower))
        if strong_t_count > strong_w_count:
            return "TRAFFIC"
        elif strong_w_count > strong_t_count:
            return "WEATHER"
        else:
            # Check earliest position in text
            t_pos = min((text_lower.find(t) for t in STRONG_TRAFFIC_TERMS if t in text_lower), default=999999)
            w_pos = min((text_lower.find(w) for w in STRONG_WEATHER_TERMS if w in text_lower), default=999999)
            return "TRAFFIC" if t_pos < w_pos else "WEATHER"
    else:
        return "OTHER"
