import os
from contextlib import asynccontextmanager

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.alerts.router import router as alerts_router
from src.anomalies.router import router as anomalies_router
from src.auth.router import router as auth_router
from src.db.session import AsyncSessionLocal, engine
from src.digests.router import router as digests_router
from src.drivers.router import router as drivers_router
from src.forecasting.router import router as forecasting_router
from src.ingestion.router import router as ingestion_router
from src.ingestion.service import seed_default_workspace
from src.jobs.service import run_daily_pipeline, run_weekly_retrain_and_digest
from src.limiter import limiter
from src.logger import setup_logging
from src.telemetry import setup_telemetry
from src.workspaces.router import router as workspaces_router

setup_logging()
logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize telemetry
    setup_telemetry(app, engine)

    scheduler = AsyncIOScheduler()

    # Startup: seed default workspace (ID #1) atomically and start AsyncIOScheduler
    try:
        async with AsyncSessionLocal() as session:
            await seed_default_workspace(session)
    except Exception as e:
        logger.warning(f"Warning seeding default workspace on startup: {e}")

    scheduler.add_job(run_daily_pipeline, CronTrigger(hour=2, minute=0))
    scheduler.add_job(run_weekly_retrain_and_digest, CronTrigger(day_of_week="mon", hour=3))
    scheduler.start()
    yield
    # Shutdown: cleanly shut down scheduler and dispose database engine pool
    scheduler.shutdown(wait=False)
    await engine.dispose()

app = FastAPI(
    title="Driftline API",
    description="Anomaly detection, root-cause driver analysis, and short-horizon forecasting",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)

# Register auth router publicly
app.include_router(auth_router, prefix="/api/v1")

# Register domain routers securely
for r in [ingestion_router, anomalies_router, drivers_router, forecasting_router, digests_router, alerts_router, workspaces_router]:
    app.include_router(r, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
