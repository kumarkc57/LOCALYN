import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
import requests

from backend.app.config import (
    OPENWEATHER_API_KEY,
    OPENWEATHER_BASE_URL,
    BENGALURU_LAT,
    BENGALURU_LON,
    BENGALURU_CITY_NAME
)
from backend.app.ingestion.news import normalize_title

logger = logging.getLogger("localyn.ingestion.weather")

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather Interpretation Codes (WW)
WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

WEATHER_RISK_DISCLAIMER = (
    "Weather forecasts and precipitation probabilities indicate atmospheric risk of heavy rainfall and potential runoff. "
    "They represent risk indicators, not confirmation of on-ground flooding or road waterlogging until corroborated by ground sensor telemetry or civic authority reports."
)

def decode_wmo_code(code: int) -> str:
    """Decodes WMO weather code to standard descriptive text."""
    return WMO_WEATHER_CODES.get(code, f"Weather condition code {code}")

def evaluate_weather_alerts(
    current_rain_mm: float,
    current_precip_prob: Optional[int] = None,
    max_forecast_rain_mm: float = 0.0,
    max_forecast_prob: Optional[int] = None,
    weather_code: int = 0
) -> List[Dict[str, Any]]:
    """
    Evaluates civic weather alerts based on documented rainfall thresholds for Bengaluru:
    - Normal / Low (Green): Rain < 2.5 mm/h
    - Advisory (Yellow): 2.5 <= Rain < 7.5 mm/h or forecast precipitation probability >= 70% with rain projected
    - Warning (Orange): 7.5 <= Rain < 15.0 mm/h or forecast rain >= 7.5 mm/h (Heavy rain / waterlogging risk)
    - Severe (Red): Rain >= 15.0 mm/h or severe thunderstorm (WMO 95, 96, 99) with active heavy rain
    """
    alerts = []
    now_iso = datetime.now(timezone.utc).isoformat()
    is_thunderstorm = weather_code in (95, 96, 99)

    if current_rain_mm >= 15.0 or (is_thunderstorm and current_rain_mm >= 7.5):
        alerts.append({
            "level": "RED",
            "severity": "SEVERE",
            "title": "Severe Rain & High Inundation Threat",
            "message": (
                f"Intense precipitation observed at {current_rain_mm:.1f} mm/h. "
                "High probability of flash waterlogging and major traffic disruption at arterial bottlenecks (e.g. Silk Board, ORR, Hebbal)."
            ),
            "rainfall_rate_mm": float(current_rain_mm),
            "precipitation_probability": current_precip_prob,
            "risk_disclaimer": WEATHER_RISK_DISCLAIMER,
            "issued_at": now_iso
        })
    elif current_rain_mm >= 7.5 or max_forecast_rain_mm >= 7.5:
        rate = current_rain_mm if current_rain_mm >= 7.5 else max_forecast_rain_mm
        prob_str = f" with {max_forecast_prob}% probability" if max_forecast_prob is not None else ""
        alerts.append({
            "level": "ORANGE",
            "severity": "WARNING",
            "title": "Heavy Rainfall Risk Advisory",
            "message": (
                f"Heavy rainfall detected or projected at {rate:.1f} mm/h{prob_str}. "
                "Substantial risk of water accumulation and traffic bottlenecks in low-lying sections and underpasses."
            ),
            "rainfall_rate_mm": float(rate),
            "precipitation_probability": max_forecast_prob if current_rain_mm < 7.5 else current_precip_prob,
            "risk_disclaimer": WEATHER_RISK_DISCLAIMER,
            "issued_at": now_iso
        })
    elif current_rain_mm >= 2.5 or (max_forecast_prob is not None and max_forecast_prob >= 70 and max_forecast_rain_mm >= 1.0):
        rate = max(current_rain_mm, max_forecast_rain_mm)
        alerts.append({
            "level": "YELLOW",
            "severity": "ADVISORY",
            "title": "Moderate Rainfall & Wet Road Advisory",
            "message": (
                f"Moderate showers observed or projected ({rate:.1f} mm/h). "
                "Road surface slickness, reduced visibility, and localized drainage slowdown expected."
            ),
            "rainfall_rate_mm": float(rate),
            "precipitation_probability": max_forecast_prob if max_forecast_prob is not None else current_precip_prob,
            "risk_disclaimer": WEATHER_RISK_DISCLAIMER,
            "issued_at": now_iso
        })
    else:
        alerts.append({
            "level": "GREEN",
            "severity": "NORMAL",
            "title": "Normal Meteorological Conditions",
            "message": (
                "Bengaluru atmospheric conditions are within normal parameters. "
                "No heavy rainfall or waterlogging risk detected."
            ),
            "rainfall_rate_mm": float(current_rain_mm),
            "precipitation_probability": current_precip_prob,
            "risk_disclaimer": WEATHER_RISK_DISCLAIMER,
            "issued_at": now_iso
        })

    return alerts

def fetch_bengaluru_weather_intelligence() -> Dict[str, Any]:
    """
    Fetches real-time Bengaluru weather observation, hourly near-term forecast,
    and multi-day outlook from Open-Meteo without requiring an API key.
    Evaluates rainfall risk thresholds and attaches explicit non-confirmation disclaimers.
    Gracefully handles network errors, timeouts, and missing fields.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    params = {
        "latitude": BENGALURU_LAT,
        "longitude": BENGALURU_LON,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m",
        "hourly": "precipitation_probability,precipitation,rain,weather_code,temperature_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "Asia/Kolkata",
        "forecast_days": 3
    }

    try:
        response = requests.get(OPEN_METEO_BASE_URL, params=params, timeout=10)
        if response.status_code != 200:
            err_msg = f"Open-Meteo HTTP {response.status_code}: {response.text[:200]}"
            logger.error(err_msg)
            return {
                "status": "degraded",
                "is_live": False,
                "source": "Open-Meteo Weather API",
                "source_url": "https://open-meteo.com/",
                "city": BENGALURU_CITY_NAME,
                "latitude": BENGALURU_LAT,
                "longitude": BENGALURU_LON,
                "current": None,
                "hourly_forecast": [],
                "daily_forecast": [],
                "alerts": [],
                "error": err_msg,
                "fetched_at": now_iso
            }

        data = response.json()
        curr_raw = data.get("current", {})
        hourly_raw = data.get("hourly", {})
        daily_raw = data.get("daily", {})

        # Current conditions
        temp = float(curr_raw.get("temperature_2m", 0.0))
        feels_like = float(curr_raw.get("apparent_temperature", temp))
        humidity = int(curr_raw.get("relative_humidity_2m", 0))
        precip = float(curr_raw.get("precipitation", 0.0))
        rain = float(curr_raw.get("rain", 0.0))
        w_code = int(curr_raw.get("weather_code", 0))
        wind_speed = float(curr_raw.get("wind_speed_10m", 0.0))
        obs_time = curr_raw.get("time", now_iso)

        # Match current hour index in hourly arrays
        hourly_times = hourly_raw.get("time", [])
        curr_idx = 0
        if obs_time in hourly_times:
            curr_idx = hourly_times.index(obs_time)
        elif len(hourly_times) > 0:
            # find closest hour if exact match missing
            curr_idx = min(len(hourly_times) - 1, max(0, curr_idx))

        hourly_pop_list = hourly_raw.get("precipitation_probability", [])
        current_pop = None
        if curr_idx < len(hourly_pop_list) and hourly_pop_list[curr_idx] is not None:
            current_pop = int(hourly_pop_list[curr_idx])

        current_obj = {
            "temperature": temp,
            "feels_like": feels_like,
            "humidity": humidity,
            "precipitation": precip,
            "rain": rain,
            "precipitation_probability": current_pop,
            "weather_code": w_code,
            "condition": decode_wmo_code(w_code),
            "wind_speed": wind_speed,
            "time": obs_time
        }

        # Near-term hourly forecast (next 12 hours)
        hourly_forecast = []
        max_forecast_rain = 0.0
        max_forecast_pop = 0
        hourly_precip_list = hourly_raw.get("precipitation", [])
        hourly_temp_list = hourly_raw.get("temperature_2m", [])
        hourly_code_list = hourly_raw.get("weather_code", [])

        end_idx = min(curr_idx + 12, len(hourly_times))
        for i in range(curr_idx, end_idx):
            h_time = hourly_times[i]
            h_temp = float(hourly_temp_list[i]) if i < len(hourly_temp_list) and hourly_temp_list[i] is not None else temp
            h_precip = float(hourly_precip_list[i]) if i < len(hourly_precip_list) and hourly_precip_list[i] is not None else 0.0
            h_pop = int(hourly_pop_list[i]) if i < len(hourly_pop_list) and hourly_pop_list[i] is not None else None
            h_code = int(hourly_code_list[i]) if i < len(hourly_code_list) and hourly_code_list[i] is not None else 0

            if h_precip > max_forecast_rain:
                max_forecast_rain = h_precip
            if h_pop is not None and h_pop > max_forecast_pop:
                max_forecast_pop = h_pop

            hourly_forecast.append({
                "time": h_time,
                "temperature": h_temp,
                "precipitation": h_precip,
                "precipitation_probability": h_pop,
                "weather_code": h_code,
                "condition": decode_wmo_code(h_code)
            })

        # 3-day daily outlook
        daily_forecast = []
        daily_times = daily_raw.get("time", [])
        daily_codes = daily_raw.get("weather_code", [])
        daily_max_t = daily_raw.get("temperature_2m_max", [])
        daily_min_t = daily_raw.get("temperature_2m_min", [])
        daily_precip_sum = daily_raw.get("precipitation_sum", [])
        daily_pop_max = daily_raw.get("precipitation_probability_max", [])

        for i in range(len(daily_times)):
            d_date = daily_times[i]
            d_code = int(daily_codes[i]) if i < len(daily_codes) and daily_codes[i] is not None else 0
            d_max = float(daily_max_t[i]) if i < len(daily_max_t) and daily_max_t[i] is not None else 0.0
            d_min = float(daily_min_t[i]) if i < len(daily_min_t) and daily_min_t[i] is not None else 0.0
            d_sum = float(daily_precip_sum[i]) if i < len(daily_precip_sum) and daily_precip_sum[i] is not None else 0.0
            d_pop = int(daily_pop_max[i]) if i < len(daily_pop_max) and daily_pop_max[i] is not None else None

            daily_forecast.append({
                "date": d_date,
                "weather_code": d_code,
                "condition": decode_wmo_code(d_code),
                "temp_max": d_max,
                "temp_min": d_min,
                "precipitation_sum": d_sum,
                "precipitation_probability_max": d_pop
            })

        # Evaluate threshold-based alerts
        alerts = evaluate_weather_alerts(
            current_rain_mm=max(precip, rain),
            current_precip_prob=current_pop,
            max_forecast_rain_mm=max_forecast_rain,
            max_forecast_prob=max_forecast_pop if max_forecast_pop > 0 else None,
            weather_code=w_code
        )

        return {
            "status": "live",
            "is_live": True,
            "source": "Open-Meteo Weather API",
            "source_url": "https://open-meteo.com/",
            "city": BENGALURU_CITY_NAME,
            "latitude": BENGALURU_LAT,
            "longitude": BENGALURU_LON,
            "current": current_obj,
            "hourly_forecast": hourly_forecast,
            "daily_forecast": daily_forecast,
            "alerts": alerts,
            "error": None,
            "fetched_at": now_iso
        }

    except requests.exceptions.Timeout:
        err_msg = "Connection timed out contacting Open-Meteo API."
        logger.error(err_msg)
        return {
            "status": "error",
            "is_live": False,
            "source": "Open-Meteo Weather API",
            "source_url": "https://open-meteo.com/",
            "city": BENGALURU_CITY_NAME,
            "latitude": BENGALURU_LAT,
            "longitude": BENGALURU_LON,
            "current": None,
            "hourly_forecast": [],
            "daily_forecast": [],
            "alerts": [],
            "error": err_msg,
            "fetched_at": now_iso
        }
    except requests.exceptions.RequestException as e:
        err_msg = f"Network exception contacting Open-Meteo: {str(e)}"
        logger.error(err_msg)
        return {
            "status": "error",
            "is_live": False,
            "source": "Open-Meteo Weather API",
            "source_url": "https://open-meteo.com/",
            "city": BENGALURU_CITY_NAME,
            "latitude": BENGALURU_LAT,
            "longitude": BENGALURU_LON,
            "current": None,
            "hourly_forecast": [],
            "daily_forecast": [],
            "alerts": [],
            "error": err_msg,
            "fetched_at": now_iso
        }
    except Exception as e:
        err_msg = f"Unexpected error during Open-Meteo weather intelligence fetch: {str(e)}"
        logger.error(err_msg)
        return {
            "status": "error",
            "is_live": False,
            "source": "Open-Meteo Weather API",
            "source_url": "https://open-meteo.com/",
            "city": BENGALURU_CITY_NAME,
            "latitude": BENGALURU_LAT,
            "longitude": BENGALURU_LON,
            "current": None,
            "hourly_forecast": [],
            "daily_forecast": [],
            "alerts": [],
            "error": err_msg,
            "fetched_at": now_iso
        }


def fetch_weather() -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Primary weather ingestion hook for LOCALYN telemetry pipeline (pipeline.py).
    Fetches real-time Bengaluru weather observation from Open-Meteo (zero key required).
    Falls back to OpenWeatherMap if configured.
    Normalizes into the internal report format with CHEF factors.
    Returns: (report_item, errors)
    """
    errors: List[str] = []

    # Attempt 1: Open-Meteo (Primary, reliable, keyless)
    live_res = fetch_bengaluru_weather_intelligence()
    if live_res.get("is_live") and live_res.get("current"):
        c = live_res["current"]
        temp = c["temperature"]
        feels_like = c["feels_like"]
        humidity = c["humidity"]
        precip = c["precipitation"]
        pop = c.get("precipitation_probability")
        pop_str = f"{pop}%" if pop is not None else "N/A"
        condition = c["condition"]
        wind_speed = c["wind_speed"]
        alerts = live_res.get("alerts", [])
        primary_alert = alerts[0] if alerts else {}
        alert_level = primary_alert.get("level", "GREEN")
        alert_title = primary_alert.get("title", "Normal")

        title = f"Bengaluru Weather Observation: {condition} ({temp}°C)"
        raw_text = (
            f"Official Meteorological Observation for Bengaluru: {condition}.\n"
            f"Temperature: {temp}°C (Feels like {feels_like}°C)\n"
            f"Precipitation: {precip} mm (Precipitation Probability: {pop_str})\n"
            f"Relative Humidity: {humidity}%\n"
            f"Wind Speed: {wind_speed} km/h\n"
            f"Coordinates: Lat {BENGALURU_LAT}, Lon {BENGALURU_LON}\n"
            f"Risk Level: {alert_level} - {alert_title}\n"
            f"Risk Notice: {WEATHER_RISK_DISCLAIMER}"
        )

        report_item = {
            "id": str(uuid.uuid4()),
            "source": "Open-Meteo",
            "source_type": "weather_api",
            "title": title,
            "raw_text": raw_text,
            "url": "https://open-meteo.com/",
            "location": BENGALURU_CITY_NAME,
            "latitude": BENGALURU_LAT,
            "longitude": BENGALURU_LON,
            "event_time": datetime.now(timezone.utc).isoformat(),
            "normalized_title": normalize_title(title),
            "ingested_at": datetime.now(timezone.utc).isoformat()
        }
        return report_item, errors

    if live_res.get("error"):
        errors.append(f"Open-Meteo failure: {live_res['error']}")

    # Attempt 2: Fallback to OpenWeatherMap if configured
    if OPENWEATHER_API_KEY and not OPENWEATHER_API_KEY.startswith("your_"):
        try:
            params = {
                "lat": BENGALURU_LAT,
                "lon": BENGALURU_LON,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            }
            resp = requests.get(OPENWEATHER_BASE_URL, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                weather_list = data.get("weather", [])
                weather_main = weather_list[0].get("main", "Clear") if weather_list else "Clear"
                weather_desc = weather_list[0].get("description", "clear sky") if weather_list else "clear sky"
                main_data = data.get("main", {})
                temp = main_data.get("temp", "N/A")
                feels_like = main_data.get("feels_like", "N/A")
                humidity = main_data.get("humidity", "N/A")
                wind_data = data.get("wind", {})
                wind_speed = wind_data.get("speed", "N/A")

                title = f"Bengaluru Weather Observation: {weather_main} ({temp}°C)"
                raw_text = (
                    f"Official Meteorological Observation for Bengaluru: {weather_desc.capitalize()}.\n"
                    f"Temperature: {temp}°C (Feels like {feels_like}°C)\n"
                    f"Relative Humidity: {humidity}%\n"
                    f"Wind Speed: {wind_speed} m/s\n"
                    f"Coordinates: Lat {BENGALURU_LAT}, Lon {BENGALURU_LON}"
                )

                dt_epoch = data.get("dt")
                event_time = (
                    datetime.fromtimestamp(dt_epoch, tz=timezone.utc).isoformat()
                    if dt_epoch else datetime.now(timezone.utc).isoformat()
                )

                report_item = {
                    "id": str(uuid.uuid4()),
                    "source": "OpenWeatherMap",
                    "source_type": "weather_api",
                    "title": title,
                    "raw_text": raw_text,
                    "url": "https://openweathermap.org/city/1277333",
                    "location": BENGALURU_CITY_NAME,
                    "latitude": BENGALURU_LAT,
                    "longitude": BENGALURU_LON,
                    "event_time": event_time,
                    "normalized_title": normalize_title(title),
                    "ingested_at": datetime.now(timezone.utc).isoformat()
                }
                return report_item, errors
            else:
                errors.append(f"OpenWeatherMap fallback HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            errors.append(f"OpenWeatherMap fallback exception: {str(e)}")
    else:
        errors.append("OpenWeatherMap API key is not configured (OPENWEATHER_API_KEY).")

    return None, errors
