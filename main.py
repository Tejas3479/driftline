import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.session import engine, AsyncSessionLocal
from src.ingestion.service import seed_default_workspace
from src.ingestion.router import router as ingestion_router
from src.anomalies.router import router as anomalies_router
from src.drivers.router import router as drivers_router
from src.forecasting.router import router as forecasting_router
from src.digests.router import router as digests_router
from src.alerts.router import router as alerts_router
from src.digests.service import run_daily_pipeline, run_weekly_retrain_and_digest

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed default workspace (ID #1) atomically and start AsyncIOScheduler
    try:
        async with AsyncSessionLocal() as session:
            await seed_default_workspace(session)
    except Exception as e:
        print(f"[!] Warning seeding default workspace on startup: {e}")

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

cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain routers: primary mounts exposed in OpenAPI schema, fallback mounts for /api/v1 prefix compatibility
for r in [ingestion_router, anomalies_router, drivers_router, forecasting_router, digests_router, alerts_router]:
    app.include_router(r)
    app.include_router(r, prefix="/api/v1", include_in_schema=False)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
