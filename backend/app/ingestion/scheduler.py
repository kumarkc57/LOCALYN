import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from backend.app.config import AUTO_INGEST_ENABLED, AUTO_INGEST_INTERVAL_MINUTES
from backend.app.ingestion.pipeline import run_ingestion_pipeline

logger = logging.getLogger("localyn.scheduler")

class AutoIngestionScheduler:
    """
    Background asynchronous periodic scheduler for LOCALYN.
    Periodically executes the live news and weather ingestion pipeline
    in a non-blocking background thread pool without stalling FastAPI request handling.
    """

    def __init__(self, interval_minutes: int = AUTO_INGEST_INTERVAL_MINUTES, enabled: bool = AUTO_INGEST_ENABLED):
        self.interval_minutes: int = max(1, interval_minutes)
        self.enabled: bool = enabled
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        
        # Telemetry & Status
        self.last_run_at: Optional[str] = None
        self.next_run_at: Optional[str] = None
        self.total_runs: int = 0
        self.last_summary: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None

    def start(self):
        """Starts the periodic background scheduler task if enabled."""
        if not self.enabled:
            logger.info("Automatic background ingestion is disabled via configuration.")
            return

        if self._task and not self._task.done():
            logger.warning("AutoIngestionScheduler is already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="localyn-auto-ingest-loop")
        logger.info(
            "AutoIngestionScheduler started (Interval: %d minutes).",
            self.interval_minutes
        )

    async def stop(self):
        """Gracefully terminates the background scheduler task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("AutoIngestionScheduler stopped.")

    async def _run_loop(self):
        """Main periodic loop."""
        # Gentle initial delay on server boot before the first auto-ingest cycle (5 seconds)
        await asyncio.sleep(5)

        while self._running:
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_error = str(e)
                logger.exception("Unexpected error in auto-ingest background loop: %s", e)

            # Calculate next run timestamp
            interval_seconds = self.interval_minutes * 60
            next_dt = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
            self.next_run_at = next_dt.isoformat()

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a single cycle in an asynchronous worker thread pool
        to prevent blocking FastAPI's event loop.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        self.last_run_at = now_str
        logger.info("[Auto-Ingest] Executing periodic real-time civic & weather ingestion cycle...")

        try:
            summary = await asyncio.to_thread(run_ingestion_pipeline)
            self.last_summary = summary
            self.total_runs += 1
            self.last_error = None

            news_inserted = summary.get("news_inserted", 0)
            weather_inserted = summary.get("weather_inserted", 0)
            skipped_dupes = summary.get("news_skipped_duplicates", 0)
            logger.info(
                "[Auto-Ingest] Cycle finished successfully! "
                "Inserted: %d news, %d weather | Skipped %d 24h duplicates | Total runs: %d",
                news_inserted,
                weather_inserted,
                skipped_dupes,
                self.total_runs
            )
            return summary
        except Exception as e:
            err = f"Pipeline execution failed: {str(e)}"
            self.last_error = err
            logger.error("[Auto-Ingest] %s", err)
            return {"status": "error", "error": err}

    def get_status(self) -> Dict[str, Any]:
        """Returns the current scheduler telemetry for the /health endpoint."""
        return {
            "enabled": self.enabled,
            "running": self._running and (self._task is not None and not self._task.done()),
            "interval_minutes": self.interval_minutes,
            "total_runs": self.total_runs,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "last_error": self.last_error,
            "last_summary": self.last_summary
        }

# Global singleton instance
scheduler = AutoIngestionScheduler()
