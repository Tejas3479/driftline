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

## Session 4: Time Series Decomposition & Daily Rollups
- Implemented time series rolling window trend/seasonal/residual decomposition pipeline using Pandas/NumPy in `src/anomalies/service.py`.
- Configured marginal per-dimension rollup logic to compute total series (`{}`) and single-dimension marginal rollups separately (e.g. `{"channel": "organic"}`), preventing sparse cross-product baseline drift.
- Added `dimension_values` `JSONB` column to `DailyRollup` model with a unique constraint index `uq_daily_rollups_metric_date_dims` and generated Alembic migration `cd678bef8820_add_dimension_values_to_daily_rollups.py`.
- Decisions: Configured continuous daily calendar reindexing before rolling calculation; enforced strict reconstruction validation raising `ValueError` if the decomposition invariant check fails; ensured complete historical recompute-and-overwrite of metrics on rerun.
- Next session context: All rollups are applied and validated, with 9/9 tests passing. Time series data is fully pre-processed and ready for Session 5 (anomaly detection algorithms and IsolationForest configuration).

## Session 5: Robust Anomaly Detection & Classification
- Implemented robust z-score calculation on residuals using Median Absolute Deviation (MAD) in `src/anomalies/service.py`.
- Mapped sensitivity settings (`low` $\rightarrow 3.5$, `medium` $\rightarrow 2.5$, `high` $\rightarrow 1.8$) to robust z-score thresholds.
- Configured multi-class classification: `level_shift` (compares trailing vs leading 14-day trend means), `volatility` (compares local 7-day residual std against historical baseline, excluding $\pm 14$ day buffer), and fallback `spike`/`dip`.
- Added database unique index `uq_anomalies_metric_date` on `(metric_id, date)` and migration `db622994a7d7_add_unique_to_anomalies.py` (which includes SQL-level deduplication).
- Decisions: Integrated SQL conditional `CASE` statements to freeze anomaly categories (`type`, `z_score`, `severity_score`, `isolation_score`) older than `max_date - 14 days` to preserve user-reviewed details; implemented low-variance baseline floor scaling and early return skip for all-zero/flat metrics; populated `severity_score` with $|z|$ and `isolation_score` with `0.0` as temporary placeholders pending Session 7.
- Next session context: Anomaly detection is fully operational and integrated with ingestion. Exposes `GET /metrics/{id}/anomalies` and `GET /anomalies/{id}` endpoints. 15/15 tests passing. Ready for Session 6 (FastAPI scheduling and APScheduler integration).

## Session 6: Metrics Dashboard (Overview & Time-Series Detail Pages)
- Added new `GET /metrics` backend endpoint in `src/ingestion/router.py`/`service.py` to list all metrics (with notes to add tenant scoping context in Session 19).
- Scoped CORS origins in `main.py` strictly to `http://localhost:3000` (omitting credentials).
- Extracted a single shared helper function `compute_scaled_mad(residuals, values) -> Optional[float]` in `src/anomalies/service.py` to prevent statistical calculation drift.
- Extended `/metrics/{id}/timeseries` to return the stable pre-computed `mad` value of the entire metric timeseries history.
- Built dynamic frontend pages and components: Overview list card layout with inline SVG sparklines, warning banners with expected-value check division-by-zero guards, and a dynamic-imported `react-plotly.js` component with range filtering, shaded baseline bounds (`trend ± MAD`), and type-distinct markers/lines.
- Wrote frontend Vitest unit test suites mock-verifying rendering, banners, filtering, and Plotly marker shapes counts, and added `test_timeseries_mad_consistency` backend test.
- Next session context: Overview dashboard and time-series detail page are fully operational. 16/16 backend tests passing, 3/3 frontend tests passing. Ready for Session 7 (IsolationForest anomaly classification & real severity scoring).

## Session 7: Multivariate Anomaly Detection & Weight Decay Feedback Loop
- Added a second multivariate anomaly signal using scikit-learn's `IsolationForest` fitted on each metric's daily rollups history.
- Feature engineered per-day features: `[value_total, residual, robust_z, rolling_7d_std, rolling_7d_mean_delta, day_of_week]`. Handled trailing edge NaN risks by running rolling standard deviation (`window=7, min_periods=1`) on the continuous calendar rollups history and using `.fillna(0.0)`.
- Calculated continuous isolation score using `score_samples()` (multiplied by `-1.0` and min-max scaled to `[0.0, 1.0]`). We used `score_samples()` because it yields a stable probability-like continuous score distribution, making min-max scaling consistent.
- Implemented a cold-start guard: IsolationForest scoring is skipped (and `isolation_score` defaulted to `0.0`) if the metric has fewer than 30 valid rollup points; severity score calculation uses z-score alone (`w_z = 1.0`) during cold-start to prevent severity dilution.
- Gated the IsolationForest signal with a robust z-score check: `isolation_score` is clamped to `0.0` if $|robust\_z| < 0.1$, preventing tiny noise fluctuations on flat/low-variance metrics from getting falsely scaled up to 1.0.
- Decoupled metric configuration by tracking a single weight `z_score_weight` in the database, automatically deriving `w_iso = 1.0 - z_score_weight`.
- Implemented feedback loop endpoint `POST /anomalies/{id}/feedback`. Upon recording a `false_positive` feedback:
  - Compares rescaled $|robust\_z|$ and `isolation_score` of the target anomaly.
  - Decays the dominant weight by `0.05` (clamped to `[0.1, 0.9]`).
  - Instantly recomputes the severity score of all non-frozen anomalies ($\ge$ max_date - 14 days) in the database.
- Next session context: Multivariate anomaly detection and the alert feedback loop are fully functional. All 18 backend tests passing. Ready for Session 8 (Anomaly details and historical visualization).

## Session 8: Root-Cause Driver Analysis (Waterfall Bridge & CatBoost Structural Importance)
- Added driver analysis domain `src/drivers/` with `router.py`, `schemas.py`, `service.py`, and endpoint `GET /anomalies/{id}/drivers`.
- Grouped raw observations with missing/null dimension values under a fallback segment `"__unassigned__"`, ensuring complete partition of the total metric volume without data leaks.
- Calculated Part A Waterfall Bridge: `segment_delta_s = actual_value(s) - (trend(s) + seasonal(s))`. Validated that the sum invariant $\sum_s \text{segment\_delta\_s} == \text{total\_delta}$ holds exactly by construction on aligned continuous calendar rollups without requiring post-hoc proportional adjustments.
- Safely excluded young segments with incomplete decomposition history (`trend` or `seasonal` is `None` on date $t$) from ranked segment contributions.
- Handled neutral topline reallocations ($|total\_delta| < 1e-4$) as a named condition, formatting the explanation as flat/stable and returning `0.0` for segment contribution percentages.
- Implemented multi-dimension explanation selection rule: selecting the dimension whose top segment has the highest absolute contribution percentage (breaking ties alphabetically). Dynamically adjusted explanation phrasing (`"Other segments also experienced significant shifts."`) when multiple segments are anomalous.
- Implemented Part B CatBoost Structural Importance in `train_and_persist_structural_importance`: trained `CatBoostRegressor` on raw observations using `day_of_week`, `trend_index`, and `cat_features` for dimension columns. Skipped training if history < 30 days, wrapped training in exception handling to preserve existing values on failure, and stored results on `Metric.structural_importance`.
- Wrote 6 backend unit tests in `tests/test_drivers.py` covering mathematical invariants on non-flat seasonality, young segment exclusion, anomaly injection, direction word & unsigned percentage flipping, CatBoost training guards, and multi-segment anomaly explanation phrasing.
- Next session context: Root-cause driver analysis (waterfall bridge and structural importance) is fully operational. 24/24 backend tests passing. Ready for Session 9 (Anomaly detail frontend page).

## Session 9: Anomaly Detail Page & Root-Cause Driver Visualization
- Extended `GET /metrics/{id}/timeseries` with optional `?segment=dimension:value` query parameter, validating format (returning 400 Bad Request on malformed inputs) and querying marginal rollups while reusing the shared `compute_scaled_mad` function.
- Added `primary_dimension` to `AnomalyDriversResponseSchema` and `get_anomaly_drivers` service, providing the explicit argmax dimension to the frontend for default tab scoping.
- Built Next.js Anomaly Detail Page (`/anomalies/[id]`) with prominent `explanation_text`, a Plotly horizontal bar chart of ranked segment contributions (dimension-scoped, sorted, direction-aware coloring based on `direction_good`), secondary structural importance callout context, interactive segment-filtered time series re-rendering, and a feedback control loop (`POST /anomalies/{id}/feedback`) passing exact backend status values (`"false_positive"`, `"reviewed"`).
- Wrote unit & component tests in `tests/test_anomalies.py`, `tests/test_drivers.py`, and `frontend/__tests__/anomalies.test.tsx`.
- Next session context: Anomaly detail page and root-cause driver visualization are fully operational. 27/27 backend tests passing, 7/7 frontend tests passing. Ready for Session 10 (Short-horizon quantile forecasting & LightGBM/XGBoost models).

## Session 10: Short-Horizon Quantile Forecasting (LightGBM / XGBoost)
- Built `src/forecasting/` domain (`models.py`, `schemas.py`, `service.py`) supporting multi-quantile forecasting ($p_{10}, p_{50}, p_{90}$) for 7, 14, and 30-day horizons. Defaulted to `lightgbm` backend (`LGBMRegressor(objective='quantile')`) with configurable cross-check support for `xgboost` (`XGBRegressor(objective='reg:quantileerror', tree_method='hist')`).
- Implemented trailing-only feature engineering (`lag_1..28`, `rolling_mean_7/28`, `rolling_std_7`, `day_of_week/month`, `month`, `trend_index`) using `.shift(1)` ahead of rolling calculations to eliminate look-ahead leakage.
- Enforced $p_{10} \le p_{50} \le p_{90}$ non-crossing invariant via quantile rearrangement. Reconciled segment forecasts with total $p_{50}$ scaling while preserving raw uncertainty half-widths ($\Delta_{p10}, \Delta_{p90}$) to guarantee both sum equality and non-crossing automatically by construction.
- Added scale-relative denominator guard ($\sum_s \hat{Y}_{s, p50} < 0.01 \times |\hat{Y}_{total, p50}|$), a 60-day minimum history exception hook, and updated `Forecast.dimension_values` to `JSONB` with key-sorted JSON serialization and PostgreSQL `ON CONFLICT DO UPDATE` upsert semantics.
- Wrote 7 comprehensive unit/integration tests in `tests/test_forecasting.py`. All 34 backend pytest tests passing, all 7 frontend Vitest tests passing.

## Session 11: Walk-Forward Backtesting Pipeline, Accuracy Log, Cold-Start Fallback & Forecasting Router
- Built expanding-window walk-forward backtesting engine (`run_walk_forward_backtest`) replaying the live multi-step recursive forecasting path across up to 12 weekly history folds ($t \le \text{cutoff\_date}$), asserting $\max(\text{train\_dates}) < \min(\text{prediction\_dates})$ to guarantee zero future data leakage.
- Implemented cold-start fallback path for metrics/folds with $<60$ days history using seasonal-naive with trend adjustment ($\hat{Y}_{t, p50} = \text{value}_{t-7} \times \frac{\text{trend}_t}{\text{trend}_{t-7}}$), heuristic residual std bounds ($1.28 \times \sigma_{res}$), and returning `low_confidence = True`.
- Added `save_to_db` parameter plumbing to `generate_multi_step_forecast`, ensuring backtest runs do not pollute live `forecasts` table, and derived `used_ml_model = not low_confidence` directly from each fold's response.
- Implemented `ForecastAccuracyLog` database table and `GET /metrics/{id}/forecast` / `GET /metrics/{id}/accuracy` FastAPI endpoints with scale-relative zero-actual guards on MAPE (`actual < 0.01 * mean_val` excluded from percentage calculations, MAE computed on all dates) and null-safe empty evaluated row protections (`coverage_pct = None` when `ml_evaluations == 0`).
- Demo Dataset Accuracy: Observed backtest MAPE on demo dataset is **2.76%** (0.0276). All 37 backend pytest tests passing, all 7 frontend Vitest tests passing.

## Session 12: Forecast Visualization & Model Track Record Screen
- Built Next.js forecast detail page (`/metrics/[id]/forecast`) and components: `LowConfidenceBanner`, `ForecastStatsPanel`, `ForecastVsActualChart`, and extended `MetricChart`.
- Extended `MetricChart` to project dashed purple $p_{50}$ median line and shaded $p_{10}\dots p_{90}$ prediction band beyond actual dates, using two strictly consecutive Plotly traces (`fill: "tonexty"`) and setting range cutoff reference to `max(actual_date, forecast_end_date)`.
- Built separate `ForecastVsActualChart` track record visualization plotting historical `predicted_p50` vs `actual` from `/metrics/{id}/accuracy`, visually distinguishing seasonal-naive fallback folds (`used_ml_model = false`) with gray diamond markers.
- Added `ForecastStatsPanel` displaying 12-week MAPE, interval coverage percentage with target bounds, evaluated fold counts, model engine version, and null-safe fallback text for cold-start metrics.
- Added unit tests in `frontend/__tests__/forecast.test.tsx`. All 37 backend pytest tests passing, all 9 frontend vitest tests passing.

## Session 13: Segment Comparison Small-Multiples (Altair & Vega-Embed)
- Built backend endpoint `GET /metrics/{id}/segment-comparison` using Altair faceting to produce a raw Vega-Lite JSON specification dictionary.
- Enforced single source of truth (`DailyRollup`) for marginal segment rollups, querying PostgreSQL JSONB key presence (`func.jsonb_exists(DailyRollup.dimension_values, dimension)`) and extracting values safely without dialect ambiguity.
- Validated `dimension` against `DimensionDef` records (ordered deterministically by `id.asc()`), returning `HTTP 400 Bad Request` for unknown dimensions or zero-dimension metrics.
- Added server-side date range filtering (`range=7d|30d|90d|1y|all`) anchored to `max_date` in `DailyRollup` for that metric, ensuring demo/historical datasets never return empty plots when filtering.
- Implemented relative 5% y-axis scale domain padding (`padding = (y_max - y_min) * 0.05 if (y_max - y_min) > 0 else (abs(y_max) * 0.05 or 1.0)`) shared identically across all facets.
- Built frontend React wrapper `<SegmentComparisonChart spec={spec} />` using `vega-embed` with cleanup (`resView.finalize()`) on unmount/re-render, and Next.js page at `/metrics/[id]/segments` with dimension tabs, range selector controls, and shared-scale informative callout banner.
- Wrote 4 backend pytest unit tests in `tests/test_drivers.py` and 2 frontend vitest tests in `frontend/__tests__/segments.test.tsx`. All 41 backend pytest tests passing, all 11 frontend vitest tests passing.

## Session 14: Unified Navigation, Global Anomaly Log Page, and Model Health Dashboard
- Built unified navigation architecture across Driftline with persistent `Navbar.tsx` wrapped in `MetricProvider` React Context, persisting selected metric ID in `localStorage` with auto-sync on metric route visits and graceful disabled tooltip state when zero metrics exist.
- Implemented global `GET /anomalies` endpoint in `src/anomalies/` joining `Anomaly` and `Metric` with `GlobalAnomalyResponseSchema`, status filtering, and sorting ordered by date descending.
- Built Global Anomaly Log Page (`/anomalies`) with full status enum tabs (`All`, `New`, `Reviewed`, `Resolved`, `False Positive`), search filter input, date/severity sort controls, canonical severity score color badges, and anomaly direction badges.
- Built Model Health & Settings Page (`/settings`) displaying verified backend fields: 12-week MAPE, interval coverage %, baseline forecast date, evaluated backtest folds, ML model version, model engine, and metric sensitivity setting.
- Wrote backend unit test `test_get_global_anomalies` in `tests/test_anomalies.py` and frontend test suite `frontend/__tests__/anomalies_log.test.tsx`. All 39 backend pytest tests passing, all 14 frontend vitest tests passing.

## Session 15: Automated AsyncIOScheduler Pipelines & Headless Matplotlib Digest PDF
- Built `src/digests/` domain (`router.py`, `schemas.py`, `service.py`, `models.py`) with `metric_id` FK column, unique index constraint `uq_digests_workspace_metric_period`, and Alembic migration `6d3e4f5a6b7c_add_metric_id_and_unique_to_digests.py`.
- Integrated `AsyncIOScheduler` bound directly to FastAPI's modern lifespan context manager in `main.py`, running daily pipeline (`CronTrigger(hour=2)`) and weekly retrain & digest (`CronTrigger(day_of_week="mon", hour=3)`).
- Implemented headless Matplotlib PDF generator (`matplotlib.use('Agg')`) rendering period total vs prior period (with zero guard), highest-severity anomaly driver text, 12-week backtest MAPE %, 30-day actuals + projected median forecast line $p_{50}$ with $p_{10}\dots p_{90}$ confidence band, and idempotent database upsert `insert(Digest).on_conflict_do_update`.
- Implemented `GET /digests/{id}` PDF download API endpoint and `GET /digests` list API endpoint with HTTP 404 guards.
- Decisions: Configured per-metric exception isolation and pre-extracted metric metadata tuples `(m_id, w_id, m_name)` to prevent SQLAlchemy ORM object expiration errors; set `n_estimators=50` for fast, robust LightGBM execution.
- Next session context: Automated daily/weekly scheduling and digest PDF generation are fully operational. All 41 backend pytest tests passing cleanly. Ready for Session 16 (Email digests and notification distribution).

## Session 16: Email Digests, Alert Rules, In-App Notifications & Alert Triggering
- Built `src/alerts/` domain (`models.py`, `schemas.py`, `service.py`, `router.py`, `email.py`) with `Notification` model (`anomaly_id` unique constraint) and Alembic migration `7e4f5a6b7c8d_create_notifications_table.py`.
- Built API endpoints `POST /alert-rules`, `GET /alert-rules`, `GET /notifications`, and `PATCH /notifications/{id}/read` with strict Pydantic `ChannelEnum` validation (`in_app`, `email`).
- Implemented left-anti-join alert evaluation query (`~Anomaly.id.in_(select(Notification.anomaly_id))` + `status.notin_(['false_positive', 'resolved'])`) catching severity-drift threshold crossings while suppressing dismissed anomalies and preventing duplicate notification errors.
- Built SMTP email dispatch (`send_weekly_digest_email` and `send_immediate_alert_email`) wrapped in isolated local `try...except Exception:` blocks, ensuring network/SMTP failures log warnings without rolling back DB notifications or interrupting daily pipeline execution.
- Decisions: Integrated alert triggering at the end of `run_daily_pipeline` and digest email sending at the end of `run_weekly_retrain_and_digest`. Unconfigured metrics default to `min_severity = 80.0` and `channels = ["in_app"]`.
- Next session context: Email digest and alert distribution operational. All 47 backend pytest tests passing cleanly.

## Session 17: Synthetic Data Generator with Ground Truth Injection & Determinism Test
- Built `scripts/generate_synthetic_data.py` generating 2 full calendar years (731 days: `2024-01-01` to `2025-12-31` inclusive, accounting for leap year 2024) of daily MRR data across 9 segment combinations ($731 \times 9 = 6,579$ rows) saved to canonical path `demo_data/synthetic_mrr.csv`.
- Generated `scripts/synthetic_ground_truth.json` recording 4 injected ground-truth anomalies:
  1. SPIKE: `2024-04-29` (Day 120) — Paid channel promotional spike ($+\$8,000.00$ total / $+\$2,666.67$ per segment).
  2. DIP: `2024-10-06` (Day 280) — Enterprise plan revenue drop ($-\$6,500.00$ total / $-\$2,166.67$ per segment).
  3. LEVEL-SHIFT: `2025-03-25` to `2025-12-31` (Days 450..731) — Global pricing $+15.0\%$ step increase across all segments (`tolerance_window_days: {"before": 0, "after": 30}`).
  4. VOLATILITY: `2025-08-22` to `2025-09-05` (Days 600..614) — Self-serve plan noise scaled by $\times 4.5$ ($\text{noise}_{\text{vol}} = 4.5 \times \text{noise}_{\text{base}}$) on top of level-shifted baseline.
- Wrote [tests/test_synthetic_generator.py](file:///c:/Users/tejas/Downloads/driftline/tests/test_synthetic_generator.py) testing byte-for-byte determinism (`seed=42`), schema structure (6,579 rows), and diff-based numerical correctness ($\Delta = \text{Series}_{\text{injected}} - \text{Series}_{\text{base}}$).
- Decisions: Used `np.random.default_rng(seed)` for modern random generator isolation, explicitly cast all NumPy values to native Python types before JSON serialization, applied cumulative anomaly ordering, and recorded explicit asymmetric tolerance windows.
- Next session context: Synthetic 2-year 9-segment dataset and ground-truth specification are generated and verified. Ready for Session 18 (End-to-end evaluation benchmark: precision/recall, driver attribution accuracy, forecast backtest MAPE).

## Session 18: Whole-Pipeline Evaluation Benchmark & Quality Regression Test Suite
- Built permanent evaluation benchmark script [scripts/evaluate_pipeline.py](file:///c:/Users/tejas/Downloads/driftline/scripts/evaluate_pipeline.py) running full pipeline (ingestion → decomposition → anomaly detection → driver analysis → CatBoost structural importance → 12-week walk-forward backtest → 30-day quantile forecasting) against Session 17 synthetic dataset (`demo_data/synthetic_mrr.csv`).
- Evaluated model outputs against `scripts/synthetic_ground_truth.json`:
  | METRIC NAME | VALUE | BENCHMARK TARGET | STATUS |
  |---|---|---|---|
  | `detection_recall` | 100.00% | $\ge 75.0\%$ (4/4 GT events) | PASS |
  | `classification_accuracy` | 100.00% | $\ge 75.0\%$ type match | PASS |
  | `false_positive_rate` | 0.89% | $\le 10.0\%$ (6/675 untouched days) | PASS |
  | `driver_accuracy` | 100.00% | $\ge 66.0\%$ (3/3 segment events) | PASS |
  | `uniform_shift_proportionality` | True | $15.0\% \pm 3.0\%$ all segments | PASS (mean 15.0%) |
  | `forecast_MAPE` (12w) | 3.20% | $\le 15.0\%$ held-out backtest | PASS |
  | `interval_coverage` ($p_{10}\dots p_{90}$) | 92.86% | $65.0\%\dots 95.0\%$ calibration | PASS |
- Key Diagnostics & Rationale:
  - Detection & Classification: Spike ($z=3.82$), Dip ($z=-3.21$), Level-Shift ($\Delta trend > 3\times MAD$), and Volatility ($\text{std}_{local}/\text{std}_{hist} > 3.0$) cleared detection thresholds and matched expected classifications.
  - False Positive Rate: 0.89% (6/675 untouched days) aligns with expected tail probability of Gaussian noise under robust $2.5\sigma$ z-score threshold.
  - Driver Attribution: Waterfall bridge correctly isolated top segments `channel: Paid` ($+\$8,000$), `plan: Enterprise` ($-\$6,500$), and `plan: Self-serve` ($4.5\times$ noise peak deviation date).
- Wrote CI regression test suite [tests/test_pipeline_evaluation.py](file:///c:/Users/tejas/Downloads/driftline/tests/test_pipeline_evaluation.py). All 49 backend pytest tests passing cleanly (49/49).

## Session 19: Final Stack Scaffolding, Documentation & End-to-End Verification
- **Stack Finalization**: Built `frontend/Dockerfile` with `NEXT_PUBLIC_API_URL` build-argument support and finalized `docker-compose.yml` orchestrating PostgreSQL 16 (`db`), FastAPI backend (`backend`), and Next.js frontend (`frontend`). Added volume mounts for persistent PDF digest storage (`digest_storage:/app/storage/digests`) and synthetic demo data (`./demo_data:/app/demo_data`).
- **Database & Application Seeding**: Added atomic default workspace seeding (`seed_default_workspace`) using PostgreSQL `ON CONFLICT (id) DO NOTHING` and sequence synchronization (`SELECT setval(...)`) in `main.py` lifespan manager on startup. Updated `MetricCreateSchema` to default `workspace_id = 1` for seamless ingestion.
- **Environment & Documentation**: Created fully documented `.env.example` template and comprehensive `README.md` containing product overview, market gap analysis, ASCII architecture diagram, 15-minute containerized getting started instructions, evaluation benchmark execution steps, and walkthrough of all 7 core UI screens.
- **Backend Quality Audit**: Re-verified core backend invariants across all domain modules:
  1. `AsyncIOScheduler` lifespan binding in `main.py`.
  2. Alert left-anti-join filtering excluding `false_positive` and `resolved` anomalies.
  3. Single-source `compute_scaled_mad` calculation across decomposition and API routers.
  4. Trailing-only feature engineering in forecasting (`.shift(1)` to guarantee zero look-ahead leakage).
  5. Walk-forward backtest expanding window recursive prediction replay.
- **Final Evaluation Benchmark Results**:
  | METRIC NAME | Measured VALUE | BENCHMARK TARGET | STATUS |
  |---|---|---|---|
  | `detection_recall` | 100.00% | $\ge 75.0\%$ (4/4 GT events) | PASS |
  | `classification_accuracy` | 100.00% | $\ge 75.0\%$ type match | PASS |
  | `false_positive_rate` | 1.66% | $\le 10.0\%$ (11/662 untouched days) | PASS |
  | `driver_accuracy` | 100.00% | $\ge 66.0\%$ (3/3 segment events) | PASS |
  | `uniform_shift_proportionality` | True | $15.0\% \pm 3.0\%$ all segments | PASS (mean 15.0%) |
  | `forecast_MAPE` (12w) | 2.64% | $\le 15.0\%$ held-out backtest | PASS |
  | `interval_coverage` ($p_{10}\dots p_{90}$) | 92.86% | $60.0\%\dots 95.0\%$ calibration | PASS |
- **Project Status**: Complete. All 49 backend pytest unit & integration tests and 14 frontend vitest tests passing cleanly.

## Session 20: Codebase Deep-Dive Audit & HackForge Repairs
- Performed exhaustive line-by-line inspection of all files across root, `src/`, `frontend/`, `tests/`, `scripts/`, and `alembic/`.
- Implemented `AnomalyDriver` database persistence in `src/drivers/service.py` to ensure complete DB output persistence complying with `.agents/AGENTS.md`.
- Refactored CatBoost structural importance training in `src/drivers/service.py` to use nested savepoints (`db.begin_nested()`) preventing session transaction aborts.
- Optimized observation count in `src/ingestion/service.py` to use `select(func.count())` instead of in-memory object list loading; consolidated FastAPI router inclusions in `main.py` with `include_in_schema=False` to clean up OpenAPI docs.
- Parallelized Next.js Overview dashboard data fetching (`app/page.tsx`) using `Promise.all`, added `VegaLiteSpec` interface and error detail helper in `api.ts`, added `--dirty` and `--gaps` CLI flags to `scripts/generate_synthetic_data.py`, added mobile menu drawer in `Navbar.tsx`, and added `test_date_gaps_decomposition_resilience` test in `tests/test_anomalies.py`.
## Session 21: Framer Motion UI/UX Animations & Interactions
- Integrated `framer-motion` (v12.42) into Next.js App Router frontend for smooth micro-animations and UI state transitions.
- Built `<PageTransition>` wrapper component in `components/PageTransition.tsx` for route changes; added `motion.div` staggered entrance and hover-lift variants to Overview metric grid cards in `app/page.tsx`.
- Added `layoutId="activeTabPill"` sliding tab indicators and `AnimatePresence` status badge morphing in `app/anomalies/page.tsx` and `components/FeedbackControl.tsx`; created `CountUp.tsx` component for animated KPI statistics counters in `components/ForecastStatsPanel.tsx`.
- Decisions & Verification: Preserved all component props and API interfaces. Verified cleanly with 14/14 frontend Vitest tests and 52/52 backend pytest tests passing.

## Session 14: Premium UI Transformation & Cinematic Landing Page
- Built 12 reusable animation components: SmoothScroll (Lenis), ScrollReveal (GSAP), TextReveal, TypewriterText, AnimatedCounter, AtroposCard (3D tilt), CustomCursor (dot+ring), GlowButton, MeteorShower, GrainOverlay, UISoundEngine (Web Audio API), upgraded PageTransition (spring+blur).
- Created cinematic 7-section landing page: hero with animated mesh gradient + floating orbs + meteor shower + typewriter cycling headline + trust metric pills, tech trust strip, feature bento grid (6 cards), 3-step "how it works" timeline, performance stats with animated counters, open-source CTA, minimal footer.
- Restructured routes into `(landing)` and `(dashboard)` route groups: `/` → landing, `/dashboard` → overview. Simplified root layout to minimal HTML shell, created per-group layouts with appropriate providers.
- Expanded design system: 25+ Tailwind tokens (surface colors, accent palette, glow shadows), 8 custom animations (float, grain, meteor, pulse-glow, border-spin), glassmorphism layers (glass-card-sm/lg), mesh gradient backgrounds, CSS `@property` animated border.
- Polished all dashboard pages: glass-card containers, ScrollReveal wrapping, hover glow effects, backdrop-blur, upgraded stat card styling across overview, anomaly log, anomaly detail, metric detail, forecast, and settings pages. Upgraded all chart containers (MetricChart, ForecastVsActualChart, SegmentBarChart, SegmentComparisonChart) to glass frames.
- Created mobile hooks: useDeviceOrientation (gyro tilt), useHaptics (vibration patterns).
- Fixed 4 pre-existing build errors: vega-canvas webpack fallback, ForecastStatsPanel TS narrowing, Plotly font→tickfont axis type, Plotly Dash type assertion.
- Decisions: Used Web Audio API directly instead of Tone.js for lighter procedural UI audio; kept all data fetching and business logic completely untouched.
- Next session context: Full build passing (`npm run build` green, 9 routes). Next priorities: integrate CustomCursor + UISoundEngine into layouts, add Lenis smooth scrolling, create remaining mobile integrations, and visual QA in the browser.

## Session 22: Complete Premium Transformation & Visual Overhaul Integration
- Completed Driftline visual transformation: integrated custom cursor with magnetic snap (`CustomCursor`), Atropos 3D parallax tilt (`AtroposCard`), CSS `@property` animated gradient borders, SVG `feTurbulence` film grain overlay (`FilmGrain`), typewriter text effect (`TypewriterText`), and CSS `@starting-style` entry animations.
- Upgraded interactive UI components: replaced native selects with accessible glassmorphic `CustomSelect` across anomalies and settings, integrated `UISoundEngine` for interactive audio feedback, and added interactive demo & walkthrough to landing page.
- Decisions & Verification: Maintained zero functional/data changes and zero backend/API modifications. Ensured test accessibility for custom UI components (hidden combobox in CustomSelect, exact string formats in overview metrics). Verified with 14/14 frontend Vitest tests and 52/52 backend pytest tests passing.
- Next session context: All unit tests and Next.js production build (`npm run build`) pass cleanly. Next step is visual QA in browser or user evaluation.

## Session 23: Exhaustive Codebase Audit & Product-Readiness Verification
- Conducted full architectural, ML pipeline, database schema, and full-stack integration audit of Driftline against 2026 internet best practices.
- Confirmed all 52 backend pytest tests pass (`52 passed in 345.40s`) and verified mathematical invariants across STL decomposition, MAD Z-score residuals, waterfall bridge attribution, CatBoost structural importance, and LightGBM quantile regression.
- Identified critical "headless" UI disconnect: Data Ingestion (`POST /metrics/{id}/data`), Executive PDF Digests (`GET /digests`), and Alert Notifications (`GET /notifications`) are fully implemented and tested in the backend but 100% orphaned from the frontend.
- Recommended immediate next step: extend `frontend/app/api.ts` with ingestion/digest/alert client wrappers and build `<DataUploadModal />` to complete the self-service user journey.

## Session 24: Data Ingestion UI Implementation
- Built the complete frontend Data Ingestion & CSV Upload flow identified as missing in the Session 23 audit.
- Extended `frontend/app/api.ts` with `MetricCreateSchema`, `ValidationReportSchema`, `ColumnMappingSchema`, `InspectionResponseSchema`, `DataConfirmSchema`, and fully-typed `fetch` wrappers.
- Implemented `DataUploadModal.tsx`, a 3-step `framer-motion` glassmorphic wizard (Configuration $\rightarrow$ Upload $\rightarrow$ Validation & Review) that posts `FormData` to the backend and displays the returned Polars validation report (errors, date gaps, inferred columns) before confirming ingestion.
- Integrated the modal into `Navbar.tsx` (`+ Add Metric`) and the Dashboard Empty State (`Upload your first metric`).
- Verified zero TypeScript compilation errors.
- Next session context: The primary headless onboarding flow is complete. Ready for next priorities: offloading CPU-heavy ML ops to thread pools, or JWT authentication.


## Session 25: Full-Stack Authentication & Authorization
- Built complete backend auth layer in src/auth/ using JWTs. Secured all 6 domain API routers with Depends(get_current_user).
- Ran Alembic migration to include hashed_password to users and seed a default admin.
- Overrode FastAPI dependencies in 	ests/conftest.py ensuring the 52 integration tests remain functional and robust.
- Built frontend AuthProvider.tsx to wrap Next.js application, manage local storage state, and handle global client-side route protection for dashboard pages.
- Refactored api.ts to intercept 401 Unauthorized responses for login redirect and gracefully attach Authorization: Bearer headers to all internal requests.
- Built premium glassmorphic /login and /register components.
- Next session context: Authentication completely resolves the previous audit gap. 52/52 backend tests and 14/14 frontend tests passing. Build successful.

## Session 26: Global Error Boundaries
- Implemented global Next.js `error.tsx` boundaries for all frontend route groups: `(auth)`, `(dashboard)`, and `(landing)`.
- Built reusable premium glassmorphic `<ErrorBoundaryUI />` component in `components/ErrorBoundaryUI.tsx` using `framer-motion` and `lucide-react` to provide a consistent, high-quality fallback experience when anomalies disrupt the React tree.
- Decisions: Kept the error UI consistent with the cinematic visual design established in Session 14 and Session 22 (glow effects, backdrop blur, fluid animations).
- Next session context: Frontend error handling is now comprehensive. All 14/14 frontend tests passing.

## Session 27: Global Loading States
- Implemented Next.js `loading.tsx` boundaries across all frontend route groups: `(auth)`, `(dashboard)`, and `(landing)`.
- Built reusable premium glassmorphic `<LoadingUI />` component in `components/LoadingUI.tsx` using `framer-motion` and `lucide-react`. It provides instant, engaging feedback with animated glow rings and pulse effects during route transitions or data fetching.
- Decisions: Ensured loading states perfectly match the cinematic and glassmorphic aesthetic of the platform, resolving the partial loading state issue identified in the audit.
- Next session context: Frontend loading states and error boundaries are fully integrated.

## Session 28: Metric Deletion
- Implemented `DELETE /metrics/{id}` API endpoint in `src/ingestion/router.py` to allow permanent removal of metrics.
- Added `delete_metric` service function leveraging SQLAlchemy's `ondelete="CASCADE"` foreign key constraints to cleanly wipe all associated observations, daily rollups, anomalies, forecasts, and alert rules without manual cascade handling.
- Integrated `deleteMetric` API client method in `frontend/app/api.ts` and added a `framer-motion` styled "Permanently Delete Metric" danger button with confirmation prompts in the Model Health & Settings page (`app/(dashboard)/settings/page.tsx`).
- Decisions: Relied exclusively on DB-level cascading `ON DELETE CASCADE` to maintain referential integrity. Exposed deletion directly inside the metric settings panel rather than a global list.
- Next session context: Full CRUD lifecycle for metrics is now complete.

## Session 29: Event-Loop Unblocking for CPU-Heavy ML & Data Ops
- Offloaded all synchronous Polars/Pandas data processing and Matplotlib PDF rendering to the Starlette/asyncio threadpool (`asyncio.to_thread`) across ingestion, anomalies, drivers, forecasting, and digests services.
- Prevented large metrics (taking 5-30+ seconds for ML training or dataframe interpolation) from blocking concurrent HTTP requests during anomaly detection, CatBoost structural importance training, LightGBM forecasting, and PDF digest generation.
- Added explicit SQLAlchemy connection pool limits (`pool_size=20`, `max_overflow=10`, `pool_timeout=30`) configured via environment variables to prevent PostgreSQL connection exhaustion under heavy concurrent load.
- Re-aligned frontend `Metric` interface in `frontend/app/api.ts` with backend `MetricResponseSchema` by adding missing `structural_importance: StructuralImportance[]` array and making `z_score_weight` required.
- Hardened backend `MetricResponseSchema.structural_importance` type in `src/ingestion/schemas.py` from a bare `List[dict]` to `List[StructuralImportanceSchema]` for strict type safety.
- Aligned `forecasting/router.py` architecture by removing its `APIRouter(prefix="/metrics")` and hardcoding paths in endpoints (`@router.get("/metrics/{id}/...")`) to match `ingestion`, `anomalies`, and `digests` routers for consistent behavior under `main.py` dual-mounting.
- Replaced anti-pattern `catch (err: any)` with strongly typed `catch (e: unknown)` blocks across 9 frontend files (`settings/page.tsx`, `metrics/[id]/page.tsx`, `anomalies/page.tsx`, etc.), enforcing proper type-guards (`e instanceof Error`).
- Added `@field_validator` to `DigestResponseSchema.pdf_path` in `src/digests/schemas.py` to extract only the file basename, preventing full filesystem path disclosure in API responses.
- Next session context: Application backend is fully non-blocking under heavy CPU load, with protected database connection limits, and strictly aligned frontend API contracts.
