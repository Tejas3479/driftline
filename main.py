from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.session import engine
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
    # Startup: register and start AsyncIOScheduler
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

# NOTE for Session 19: Revisit CORS origins config before production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(ingestion_router, prefix="/api/v1")

app.include_router(anomalies_router)
app.include_router(anomalies_router, prefix="/api/v1")

app.include_router(drivers_router)
app.include_router(drivers_router, prefix="/api/v1")

app.include_router(forecasting_router)
app.include_router(forecasting_router, prefix="/api/v1")

app.include_router(digests_router)
app.include_router(digests_router, prefix="/api/v1")

app.include_router(alerts_router)
app.include_router(alerts_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
