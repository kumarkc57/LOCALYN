import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in current working dir, project root, and backend dir
root_dir = Path(__file__).resolve().parent.parent.parent
backend_dir = Path(__file__).resolve().parent.parent

for env_path in [root_dir / ".env", backend_dir / ".env", Path(".env")]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()

# Configuration Settings
NEWSDATA_API_KEY: str = os.getenv("NEWSDATA_API_KEY", "").strip()
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "").strip()

# Database Path
DB_PATH: str = os.getenv("DB_PATH", str(backend_dir / "localyn.db"))

# Bengaluru Hyperlocal Coordinates & Defaults
BENGALURU_LAT: float = 12.9716
BENGALURU_LON: float = 77.5946
BENGALURU_CITY_NAME: str = "Bengaluru"

# Ingestion settings
NEWSDATA_BASE_URL: str = os.getenv("NEWSDATA_BASE_URL", "https://newsdata.io/api/1/latest")
OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5/weather"

# Automated Real-time Background Ingestion Settings
AUTO_INGEST_ENABLED: bool = os.getenv("AUTO_INGEST_ENABLED", "true").lower() in ("true", "1", "yes")
AUTO_INGEST_INTERVAL_MINUTES: int = int(os.getenv("AUTO_INGEST_INTERVAL_MINUTES", "15"))
