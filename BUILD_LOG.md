# BUILD LOG

## Session 1: Initial Repository Scaffolding
- Built initial repository skeleton for Driftline including domain modules (`src/db`, `src/ingestion`, `src/anomalies`, `src/drivers`, `src/forecasting`, `src/digests`, `src/alerts`), `main.py` FastAPI app with `/health` endpoint, async SQLAlchemy 2.0 session handling, Next.js (App Router) + TypeScript + Tailwind frontend placeholder, and Docker Compose environment with Postgres 16.
- Decisions: Configured `postgresql+asyncpg` for database engine async sessions; pinned ML/backend dependencies in `requirements.txt`.

## Session 2: Database Models & Alembic Migration
- Created 12 core SQLAlchemy 2.0 declarative models across domain packages: `workspaces`, `users`, `metrics`, `dimension_defs`, `observations`, `daily_rollups`, `anomalies`, `anomaly_drivers`, `forecasts`, `forecast_accuracy_log`, `digests`, `alert_rules`.
- Configured async Alembic migration environment (`alembic/env.py`) and generated initial migration revision `c3cbb107211d_initial_schema.py`.
- Decisions: Configured PostgreSQL ENUM types with `create_type=False` and explicit migration `checkfirst=True` lifecycle management to ensure `alembic upgrade head` and `alembic downgrade -1` are 100% idempotent; added composite indexes `(metric_id, date)` / `(metric_id, forecast_date)` on high-frequency date-queried tables (`observations`, `daily_rollups`, `anomalies`, `forecasts`).
- Deviations: None from the schema spec. Added `pytest-asyncio` dependency to support async test execution in pytest suite.
- Next session context: All 12 tables and Alembic migrations are applied and verified (`tests/test_schema.py` passing 3/3 tests). Ready for Session 3 (data ingestion pipeline, CSV parsing, validation, and database persistence).

## Session 3: Data Ingestion Pipeline & Validation
- Built end-to-end data ingestion pipeline in `src/ingestion/`: `POST /metrics`, `POST /metrics/{id}/data`, and `POST /metrics/{id}/data/confirm`.
- Implemented bulk Polars CSV reading (`pl.read_csv`), column inference (>90% date match threshold, most populated numeric value column, candidate dimensions), validation report generation (missing/unparseable dates, duplicate date/dimension combos, non-numeric values, disallowed negative values), date gap detection, and append vs replace persistence with Polars-to-Pandas dictionary handoff at the database boundary.
- Demo Dataset: Created synthetic dataset at `demo_data/daily_revenue.csv` (60 days: 2026-01-01 to 2026-03-01, 1 dimension column `channel` with 3 values `organic`, `paid`, `referral`, totaling 180 rows).
- Decisions: Registered `python-multipart` for FastAPI file uploads; added `tests/conftest.py` with `NullPool` database dependency overrides for event-loop isolation in `pytest-asyncio`.
- Next session context: Data ingestion is fully operational and verified (6/6 tests passing). Ready for Session 4 (anomaly detection algorithm & daily rollup pipeline).
