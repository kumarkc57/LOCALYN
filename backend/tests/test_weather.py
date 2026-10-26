import pytest
from unittest.mock import patch, MagicMock
import requests
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ingestion.weather import (
    decode_wmo_code,
    evaluate_weather_alerts,
    fetch_bengaluru_weather_intelligence,
    fetch_weather,
    WEATHER_RISK_DISCLAIMER,
    WMO_WEATHER_CODES
)

client = TestClient(app)


class TestWMODecoder:
    def test_known_wmo_codes(self):
        assert decode_wmo_code(0) == "Clear sky"
        assert decode_wmo_code(2) == "Partly cloudy"
        assert decode_wmo_code(61) == "Slight rain"
        assert decode_wmo_code(65) == "Heavy rain"
        assert decode_wmo_code(80) == "Slight rain showers"
        assert decode_wmo_code(95) == "Thunderstorm"

    def test_unknown_wmo_code(self):
        desc = decode_wmo_code(999)
        assert "999" in desc


class TestWeatherAlertThresholds:
    def test_normal_green_threshold(self):
        alerts = evaluate_weather_alerts(
            current_rain_mm=0.0,
            current_precip_prob=10,
            max_forecast_rain_mm=0.5,
            max_forecast_prob=20,
            weather_code=0
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "GREEN"
        assert a["severity"] == "NORMAL"
        assert "Normal Meteorological Conditions" in a["title"]
        assert WEATHER_RISK_DISCLAIMER in a["risk_disclaimer"]

    def test_advisory_yellow_threshold(self):
        # 3.5 mm/h is moderate rain (2.5 - 7.5 mm/h)
        alerts = evaluate_weather_alerts(
            current_rain_mm=3.5,
            current_precip_prob=60,
            max_forecast_rain_mm=2.0,
            max_forecast_prob=50,
            weather_code=63
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "YELLOW"
        assert a["severity"] == "ADVISORY"
        assert "Moderate Rainfall" in a["title"]
        assert WEATHER_RISK_DISCLAIMER in a["risk_disclaimer"]

    def test_advisory_yellow_forecast_probability_threshold(self):
        # High forecast probability (>= 70%) with rain
        alerts = evaluate_weather_alerts(
            current_rain_mm=0.2,
            current_precip_prob=30,
            max_forecast_rain_mm=2.5,
            max_forecast_prob=85,
            weather_code=2
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "YELLOW"
        assert a["severity"] == "ADVISORY"

    def test_warning_orange_threshold(self):
        # 9.0 mm/h is heavy rain (7.5 - 15.0 mm/h)
        alerts = evaluate_weather_alerts(
            current_rain_mm=9.0,
            current_precip_prob=90,
            max_forecast_rain_mm=10.0,
            max_forecast_prob=95,
            weather_code=65
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "ORANGE"
        assert a["severity"] == "WARNING"
        assert "Heavy Rainfall Risk Advisory" in a["title"]
        assert WEATHER_RISK_DISCLAIMER in a["risk_disclaimer"]

    def test_severe_red_threshold_by_rainfall_rate(self):
        # >= 15.0 mm/h is intense / severe
        alerts = evaluate_weather_alerts(
            current_rain_mm=18.5,
            current_precip_prob=100,
            max_forecast_rain_mm=22.0,
            max_forecast_prob=100,
            weather_code=82
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "RED"
        assert a["severity"] == "SEVERE"
        assert "Severe Rain & High Inundation Threat" in a["title"]
        assert WEATHER_RISK_DISCLAIMER in a["risk_disclaimer"]

    def test_severe_red_threshold_by_thunderstorm(self):
        # Thunderstorm (code 95) with rain >= 7.5 mm/h
        alerts = evaluate_weather_alerts(
            current_rain_mm=8.5,
            current_precip_prob=95,
            max_forecast_rain_mm=9.0,
            max_forecast_prob=95,
            weather_code=95
        )
        assert len(alerts) >= 1
        a = alerts[0]
        assert a["level"] == "RED"
        assert a["severity"] == "SEVERE"


class TestOpenMeteoParsingAndResilience:
    @patch("backend.app.ingestion.weather.requests.get")
    def test_fetch_bengaluru_weather_intelligence_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "time": "2026-10-20T16:00",
                "temperature_2m": 27.5,
                "relative_humidity_2m": 58,
                "apparent_temperature": 28.6,
                "precipitation": 1.2,
                "rain": 1.2,
                "weather_code": 61,
                "wind_speed_10m": 14.2
            },
            "hourly": {
                "time": [f"2026-10-20T{h:02d}:00" for h in range(24)],
                "precipitation_probability": [40 + h for h in range(24)],
                "precipitation": [0.5 if h % 2 == 0 else 0.0 for h in range(24)],
                "rain": [0.5 if h % 2 == 0 else 0.0 for h in range(24)],
                "weather_code": [61] * 24,
                "temperature_2m": [26.0 - (h * 0.2) for h in range(24)]
            },
            "daily": {
                "time": ["2026-10-20", "2026-10-21", "2026-10-22"],
                "weather_code": [61, 2, 0],
                "temperature_2m_max": [29.0, 30.0, 31.0],
                "temperature_2m_min": [19.0, 20.0, 19.5],
                "precipitation_sum": [4.5, 0.0, 0.0],
                "precipitation_probability_max": [65, 20, 10]
            }
        }
        mock_get.return_value = mock_resp

        res = fetch_bengaluru_weather_intelligence()
        assert res["status"] == "live"
        assert res["is_live"] is True
        assert res["city"] == "Bengaluru"
        assert res["source"] == "Open-Meteo Weather API"
        assert res["current"]["temperature"] == 27.5
        assert res["current"]["condition"] == "Slight rain"
        assert res["current"]["precipitation"] == 1.2
        assert len(res["hourly_forecast"]) > 0
        assert len(res["daily_forecast"]) == 3
        assert len(res["alerts"]) >= 1

    @patch("backend.app.ingestion.weather.requests.get")
    def test_timeout_handling(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Read timeout connecting to open-meteo")
        res = fetch_bengaluru_weather_intelligence()
        assert res["status"] == "error"
        assert res["is_live"] is False
        assert res["current"] is None
        assert "timed out" in res["error"].lower()

    @patch("backend.app.ingestion.weather.requests.get")
    def test_network_connection_error_handling(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure or no internet")
        res = fetch_bengaluru_weather_intelligence()
        assert res["status"] == "error"
        assert res["is_live"] is False
        assert res["current"] is None
        assert "network exception" in res["error"].lower()

    @patch("backend.app.ingestion.weather.requests.get")
    def test_http_error_handling(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        mock_get.return_value = mock_resp

        res = fetch_bengaluru_weather_intelligence()
        assert res["status"] == "degraded"
        assert res["is_live"] is False
        assert "503" in res["error"]

    @patch("backend.app.ingestion.weather.requests.get")
    def test_missing_values_safe_fallback(self, mock_get):
        # Empty dictionaries inside data
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {},
            "hourly": {},
            "daily": {}
        }
        mock_get.return_value = mock_resp

        res = fetch_bengaluru_weather_intelligence()
        assert res["status"] == "live"
        assert res["is_live"] is True
        assert res["current"]["temperature"] == 0.0
        assert res["current"]["humidity"] == 0
        assert res["current"]["condition"] == "Clear sky"


class TestWeatherEndpointsAndPipeline:
    def test_get_live_weather_api_endpoint(self):
        response = client.get("/weather/live")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "is_live" in data
        assert "city" in data
        assert data["city"] == "Bengaluru"
        assert "alerts" in data
        assert "hourly_forecast" in data
        assert "daily_forecast" in data

    def test_pipeline_fetch_weather_format(self):
        report, errors = fetch_weather()
        # Either live fetched or structured error (no unhandled exception)
        assert isinstance(errors, list)
        if report:
            assert report["source_type"] == "weather_api"
            assert "Bengaluru" in report["location"]
            assert report["latitude"] == 12.9716
            assert report["longitude"] == 77.5946
            assert "temperature" in report["raw_text"].lower()
            assert "risk notice" in report["raw_text"].lower()
