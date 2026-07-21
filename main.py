from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.db.session import engine
from src.ingestion.router import router as ingestion_router
from src.anomalies.router import router as anomalies_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    yield
    # Shutdown actions
    await engine.dispose()

from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
