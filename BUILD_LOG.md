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
- Next session context: Forecasting backtesting pipeline, cold-start fallback, accuracy log, and endpoints are fully operational. Ready for Session 12 (Frontend Forecast & Accuracy Visualization components).

