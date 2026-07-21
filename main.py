from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.db.session import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    yield
    # Shutdown actions
    await engine.dispose()

app = FastAPI(
    title="Driftline API",
    description="Anomaly detection, root-cause driver analysis, and short-horizon forecasting",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
