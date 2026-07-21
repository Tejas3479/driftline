# DRIFTLINE PROJECT CONTEXT

PROJECT: Driftline — anomaly detection, root-cause driver analysis, and
short-horizon forecasting for a single business metric (e.g. daily revenue),
with up to 3 categorical dimensions (e.g. channel, plan, region).

STACK:
- Backend: Python, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, APScheduler
- Data/ML: Polars (ingestion), Pandas + NumPy (features/stats), scikit-learn
  (IsolationForest, preprocessing), LightGBM + XGBoost (quantile forecasting),
  CatBoost (categorical driver importance)
- Viz: Plotly (main interactive chart), Altair (segment small-multiples via
  vega-embed), Matplotlib (static PDF digest)
- Frontend: Next.js (App Router), TypeScript, Tailwind
- Testing: pytest

BACKEND STRUCTURE — domain-module pattern, NOT file-type folders:
src/
  ingestion/    router.py, schemas.py, models.py, service.py
  anomalies/
  drivers/
  forecasting/
  digests/
  alerts/
  db/           engine/session setup
alembic/
tests/          mirrors src/ structure
main.py         app init, router registration, lifespan events ONLY —
                never put business logic in main.py or in router.py.
                Business logic always lives in service.py.

CONVENTIONS:
- Every pipeline stage persists its output to the DB — never leave a
  result only in memory, or a failed run becomes undiagnosable.
- Every function with a mathematical invariant must have a test asserting
  that invariant (examples: trend+seasonal+residual == actual; segment
  deltas sum to total delta; p10 <= p50 <= p90 always).
- No feature is done without the test(s) specified for its session.
- At the end of every session, append a 3-5 line entry to BUILD_LOG.md:
  what was built, what decisions were made, anything the next session
  needs to know. This is how context survives across sessions.
