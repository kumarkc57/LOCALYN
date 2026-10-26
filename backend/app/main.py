import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database.db import init_db
from backend.app.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("localyn")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite schema
    logger.info("Initializing LOCALYN SQLite Database...")
    init_db()
    from backend.app.database.seed_hyperlocal import seed_hyperlocal_corridors
    seed_hyperlocal_corridors()
    logger.info("Database initialized with hyperlocal benchmarks.")

    # Start automated background real-time ingestion scheduler
    from backend.app.ingestion.scheduler import scheduler
    scheduler.start()

    yield
    # Shutdown
    logger.info("LOCALYN backend shutting down...")
    await scheduler.stop()
    logger.info("LOCALYN backend shutdown complete.")

app = FastAPI(
    title="LOCALYN — Hyperlocal Urban Intelligence Platform",
    description="Multi-Agency Spatio-Temporal Entity Resolution & Civic Evidence Fusion for Bengaluru",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits Vite frontend on any local port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API endpoints
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
