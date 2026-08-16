# Driftline — Senior Full-Stack Audit Report

**Audited repo:** `C:\Users\tejas\Downloads\driftline` (git `main`, HEAD `1c84537`)
**Stack (verified):** FastAPI + SQLAlchemy 2 async/asyncpg + Alembic + PostgreSQL 16 backend; Polars/Pandas + CatBoost/LightGBM/XGBoost/sklearn ML core; APScheduler; structlog + OpenTelemetry; slowapi; argon2-cffi + PyJWT cookie auth. Next.js 14 App Router + React 18 + Tailwind v4 + framer-motion/GSAP + Plotly/Vega + SWR frontend. Vitest (frontend), pytest (backend), GitHub Actions CI, Docker Compose.
**Date of review:** 2026-08-16. All findings are **confirmed by reading source** unless explicitly marked *assumed*.

---

## 1. Full Audit Verdict

**Overall:** A genuinely well-engineered ML-demo monorepo with a strong, well-tested algorithmic core — but **not product-ready**. It is a senior-worthy portfolio piece whose *backend science* is the best part, and whose *product wiring* is the worst part.

Score by layer:

| Layer | Grade | Rationale |
|---|---|---|
| ML/anomaly/forecast core | **A–** | Ground-truth tested, leakage-guarded, idempotent upserts |
| Backend API hygiene | **B** | Layered, rate-limited, audited, async — but GETs mutate state |
| Auth & multi-tenancy | **C–** | Correct primitives; broken onboarding; one security landmine |
| Frontend engineering | **B–** | Polished, typed, mostly correct SSR — two confirmed breakers |
| Deployment/infra | **C+** | Multi-worker scheduler duplication; hardcoded SECRET_KEY |
| Docs vs. reality | **D** | README/BUILD_LOG overclaim and contradict code |
| Test coverage | **B–** | 53 backend + 6 frontend tests, but auth and wiring untested |

Two **confirmed broken user journeys** and one **confirmed security landmine** make this unfit for a public launch until the "Critical pre-release fixes" in §11 are done. None are hard; a focused 3–7 day pass fixes all of them. The algorithmic work does not need rework.

---

## 2. Implemented Properly

1. **Anomaly-detection core is mathematically sound and tested.** `decompose_timeseries` (src/anomalies/service.py:24) uses a rolling-mean trend + residual + robust-z scoring. Tests cover the core invariant (`test_decomposition_core_invariant`), ground-truth recovery, level-shift/volatility classification, MAD consistency, zero/low-variance suppression, date-gap resilience, and feedback weight decay (tests/test_anomalies.py, 18 tests). This is the strongest part of the codebase.
2. **Forecasting has a real evaluation harness, not vibes.** Walk-forward backtest (`run_walk_forward_backtest`, src/forecasting/service.py:591) uses an expanding window, asserts `max(train_dates) < pred_start_date` (leakage invariant, line 639), reuses the *exact* live pipeline with `save_to_db=False` (`test_backtest_does_not_pollute_live_forecasts_table`), derives `used_ml_model` from the fold's `low_confidence` flag, and enforces quantile non-crossing via rearrangement (`enforce_quantile_non_crossing`, line 130).
3. **Idempotent persistence everywhere.** Rollups, anomalies, forecasts, and `forecast_accuracy_log` all upsert via `on_conflict_do_update` against explicit unique constraints (`uq_anomalies_metric_date`, `uq_forecasts_metric_dim_date_horizon_backend`, `uq_forecast_accuracy_log_metric_date_horizon_backend`). `run_daily_rollup_and_decomposition` and append/confirm are repeatable.
4. **Multi-tenancy access control is enforced server-side.** `verify_metric_access` (src/ingestion/service.py:437) scopes every metric query to `current_user.workspace_id`; workspace user management is admin-gated and returns 403 (src/workspaces/router.py:37-108). `test_workspaces.py` pops the mock override and exercises the real auth path including the member-403 case — the single best integration test in the repo.
5. **Observability matches current best practice.** structlog JSON pipeline + correlation IDs (`asgi-correlation-id`) + optional OpenTelemetry setup (src/logger.py, src/telemetry.py, main.py:34,80). This is exactly the shape recommended in current FastAPI+OTel guides (RealPython 2026; SigNoz 2026).
6. **Rate limiting on all mutating and read endpoints** via slowapi (5–60/min), disabled under TESTING (src/limiter.py). Login 10/min, register 5/min.
7. **Cookie auth baseline is correct.** `driftline_token` cookie is `HttpOnly`, `SameSite=Lax`, `Secure` defaults to true in production (src/auth/security.py:16-20); argon2 (not bcrypt/PBKDF2) for new users — OWASP's recommended algorithm; JWT HS256 with `exp`. This is materially better than the common localStorage-JWT anti-pattern (LogRocket 2026; Skycloak 2026).
8. **Migrations are coherent.** Clean 9-step chain (head `2d7591fb702c`), duplicate-deletion before the unique anomaly index, `setval` for the seeded workspace sequence, JSONB/quantile columns wired through. `test_schema.py` validates all tables.
9. **Frontend engineering hygiene.** Typed API client (frontend/app/api.ts), SWR with deduping, plotly/vega loaded via `next/dynamic({ ssr:false })` everywhere *except one place* (§5), consistent design system, error/loading states, page transitions.
10. **CI does the right things.** ruff → `alembic upgrade head` → psql seed → pytest → vitest + `next build`; weekly `pip-audit` (`.github/workflows/ci.yml`, `security.yml`). Gunicorn runs 4 workers.

---

## 3. Partially Implemented

1. **Auth is correct-but-incomplete.** Single 60-min JWT cookie, no refresh-token rotation and no silent renewal → users hard-logged-out every hour (src/auth/security.py:14). Modern guidance is short-lived access token + rotating refresh token in an HttpOnly/Secure/SameSite cookie (LogRocket 2026; Dev.Spot 2026; OAuth 2.0 BCP). Acceptable for a demo, wrong for a product.
2. **Role model enforced server-side, but client-controlled at the door.** `UserCreate.role` defaults to `"admin"` and is accepted verbatim from the client (src/auth/schemas.py:9; src/auth/service.py:26). The workspace admin-gating (src/workspaces/service.py) is correct; the registration API is the hole.
3. **Ingestion replace-vs-append.** Both modes exist and are tested (`test_append_vs_replace_semantics`), but the UI hardcodes `replace:false` (DataUploadModal.tsx:137), so replace is latent backend-only, and replace does not invalidate derived tables (§4, §7).
4. **Forecasting horizon semantics.** The API accepts `horizon=30`, but the backtest folds are **always 7-day windows** regardless of the requested horizon — the requested value only labels the log rows (src/forecasting/service.py:627-652). Settings asks for 30-day accuracy; the numbers it shows were produced by 7-day folds (settings/page.tsx:101).
5. **Alerts are in-app-complete, email best-effort.** Notifications UI + polling works. Email uses SMTP env defaults of `localhost:587` / `admin@driftline.io` and swallows failures to a warning (src/alerts/email.py:11-16,60-70) — fine as a guard, but there is no per-workspace recipient config, so digests/alerts go to a hardcoded default address.
6. **Driver analysis recomputes everything.** `run_daily_pipeline` iterates *every* anomaly a metric has ever produced and recomputes driver explanations for each (src/jobs/service.py:54-65) — no recency filter. Correct, but scales O(total anomalies) per day.

---

## 4. Broken / Missing

### B1 — Anomaly Log page is broken (confirmed, user-visible)
The page calls `GET /api/v1/anomalies/global` (+`?status=`), which **does not exist** (frontend/app/(dashboard)/anomalies/page.tsx:33-35). The backend route is `GET /api/v1/anomalies` (src/anomalies/router.py:24); the `/anomalies/{anomaly_id}` int route (line 95) catches `"global"` and returns **422 Unprocessable Entity**. The correct helper `fetchGlobalAnomalies` exists in api.ts:275 but is *unused* by the page. **No backend or frontend test catches this**: `anomalies_log.test.tsx` mocks `useApi`.

### B2 — New-user onboarding is a dead end (confirmed)
`register_user` creates a **brand-new workspace per user** (src/auth/service.py:17-31), and the frontend registers with `role: "member"` (register/page.tsx:33). Consequences:
- Demo/seed data lives in workspace 1; the new user's fresh workspace is empty → **empty dashboard on first login**.
- As a `member` of their own workspace they **cannot add teammates** (admin-required, 403) and cannot elevate themselves → TeamManagement UI is a dead end. `test_workspaces.py` passes only because it explicitly registers `role: "admin"` — the actual UI flow is never exercised.
- Registration self-selects a role (`"admin"` is the schema default) — a privilege-escalation anti-pattern. Server must decide the owner role.

### B3 — Auth migration backdoors a known password (confirmed, security landmine)
`alembic/versions/2d7591fb702c_add_auth.py:28` sets **every pre-existing user's hash to one hardcoded bcrypt string** — the well-known bcrypt of `"password123"`. Worse, `verify_password` (src/auth/security.py:24-28) uses argon2 and catches **only** `VerifyMismatchError`; argon2 raises `InvalidHashError` (a `ValueError` subclass) for the non-argon2 hash → **500 on every login attempt by a migrated user** (`authenticate_user` does not catch it). Any environment upgraded from the pre-auth schema has every account locked-out-with-500 *and* logged in by anyone who knows "password123". Fresh deploys are unaffected (UPDATE hits 0 rows) — which is why CI/tests never see it.

### B4 — State-mutating GETs trigger ML training on page views (confirmed)
`GET /metrics/{id}/forecast` runs the full quantile training pipeline with `save_to_db=True` (src/forecasting/router.py:18-45 → service.py:563-577). `GET /metrics/{id}/accuracy` runs the 12-week walk-forward backtest and writes `forecast_accuracy_log` when empty (`auto_run=True`, router.py:47-73 → service.py:743-751). The Settings page fires **both** on mount with horizon 30 (settings/page.tsx:101-102); the Forecast page does the same via `useApi`. Violates HTTP safety/idempotency (RFC 9110: GET must be safe; see §8) and trains GBMs on every page load — exactly the "GET with side effects" anti-pattern called out in every current REST reference.

### B5 — Scheduled jobs run N× under multi-worker gunicorn (confirmed)
`main.py:36-47` creates and starts an `AsyncIOScheduler` inside the app `lifespan`. Compose runs `gunicorn --workers 4`, so **each of the 4 worker processes runs its own scheduler** → the daily pipeline and weekly retrain/digest execute 4× (and the weekly digest email goes out 4×). No advisory lock / leader election / `--preload` guard. This is the classic single-instance assumption.

### B6 — Replace-mode leaves derived tables stale (confirmed)
`confirm_and_persist_observations` with `replace:true` deletes only `observations` and re-runs rollup+decomposition (src/ingestion/service.py:353-367,408). **Forecasts, `forecast_accuracy_log`, driver structural-importance, and resolved-anomaly state are not invalidated.** Replacing a metric's data leaves old forecasts/accuracy visible. UI never triggers replace anyway (B2-adjacent), so the bug is latent — but it will bite the moment replace ships.

### B7 — Hardcoded production secret (confirmed)
`docker-compose.yml` sets `SECRET_KEY: "change-me-in-production"`. `security.py:9-11` correctly refuses to start without it — but compose ships a known value, so a stock `docker compose up` deploys forgeable JWTs. Must come from env/secret-store, and compose should fail if absent.

### B8 — Docs claim things the code doesn't do (confirmed)
- README/PROJECT_CONTEXT claim **STL decomposition**; code uses `rolling(28, min_periods=14).mean()` (src/anomalies/service.py:40). Not wrong — just not STL.
- BUILD_LOG Session 25 claims Bearer-header auth + frontend 401 interception; actual code uses an HttpOnly cookie with `credentials:"include"` and redirects 401→/login in `useApi`. Docs are stale; code is what ships.
- Landing page overclaims: "Upload CSV **or connect a database**" (no DB connector exists anywhere), "real-time", "Detection <1s", "4.2σ divergence". Plus a fake browser chrome bar labeled `app.driftline.io/intelligence`.
- BUILD_LOG has a duplicated "Session 14" section.

### B9 — MetricChart statically imported in one SSR page (confirmed risk)
`anomalies/[id]/page.tsx:19` does a **static import** of `MetricChart` (react-plotly.js, a window-dependent library). Every other page uses `dynamic(..., { ssr:false })`. Statically importing plotly in a page that can be server-rendered is the canonical `self is not defined` / `window is not defined` SSR crash (plotly/react-plotly.js#273; Krapton 2026). Tests mock react-plotly.js, so vitest passes regardless. Whether it crashes in production depends on the page being rendered server-side; it is a live risk, not yet observed.

---

## 5. Frontend Review

**Strengths.** Cohesive, premium design system (Tailwind v4 CSS-first `@theme` tokens in globals.css — correct v4 usage); typed `api.ts`; SWR with deduping + 401 redirect; error/loading/empty states everywhere; correct `next/dynamic({ssr:false})` for vega-embed (SegmentComparisonChart) and plotly (MetricChart) on every page *except B9*; `not-found.tsx`/error boundaries; tested components (segments, metrics, forecast, anomaly detail).

**Issues (confirmed).**
1. **B1** — `/api/v1/anomalies/global` wrong URL; `fetchGlobalAnomalies` is dead code (api.ts:275).
2. **B9** — static `MetricChart` import in `anomalies/[id]/page.tsx:19`.
3. **Google Fonts via `@import`** in globals.css:1 — render-blocking CSS fetch; best practice is `<link rel="preconnect">` + stylesheet or `next/font` to avoid the font cascade penalty.
4. **Version mismatch:** `next ^14.1.4` with `eslint-config-next ^16.3.0` (package.json:19,39) — config built for a much newer Next; `next lint` behavior drifts from actual Next 14 semantics.
5. **Anomaly log renders all rows** with no pagination/virtualization — unbounded table for long histories.
6. **`useApi` fetcher has no timeout/abort** — a hung forecast/accuracy call (GBM training on GET, B4) leaves the UI pending forever; SWR `dedupingInterval: 5000` merely throttles.
7. **Decorative layer** (CustomCursor, UISoundEngine, MeteorShower, GrainOverlay) adds motion/sound with no `prefers-reduced-motion` handling and no sound preference persistence — polish that can actively annoy in a business analytics product (*assumed*: none of these were seen gated on the media query).
8. **`role:"member"` hardcoded at registration** (register/page.tsx:33) — the root of B2.
9. **DataUploadModal:** `workspace_id:1` is sent (DataUploadModal.tsx:41; ignored by backend), `replace:false` always (line 137), and **all inspection rows are re-posted** to `/data/confirm` (line 136) — a full second copy of the dataset travels (see §7).
10. Landing page marketing claims that do not match the product (§B8).

---

## 6. Backend Review

**Strengths.** Clean routers→services layering; Pydantic schemas; async SQLAlchemy throughout; every domain router behind `Depends(get_current_user)`; workspace-scoped access on every metric route; audit logging on metric CRUD/workspace mutations/feedback; `asyncio.to_thread` used to keep heavy pandas/polars/ML off the event loop (src/forecasting/service.py:290,424,470,525; src/ingestion/service.py:348); rate limits everywhere; `seed_default_workspace` is idempotent (ingestion/service.py:60-79).

**Issues (confirmed).**
1. **B4** — GET endpoints that train + write DB.
2. **B5** — scheduler per-worker duplication (main.py:36-47).
3. **B3** — argon2 verify doesn't handle `InvalidHashError`; migration injects a known bcrypt hash.
4. **B2/B6** — client-controlled role; replace leaves derived tables stale.
5. **Append mode loads ALL existing observations into memory** to dedupe (src/ingestion/service.py:370-380) — O(n) memory per confirm; fine at demo scale, wrong at 1M rows. The `inspect_and_validate_csv` path also stringifies and returns **every row** (lines 289-291, 301-305), which combined with B-D's re-post doubles transfer (see §7).
6. **`verify_metric_access` returns 404 for foreign metrics** (ingestion/service.py:437-443) rather than 403 — lets authenticated users probe metric-id existence cross-workspace (minor enumeration concern).
7. **Date parsing is ambiguous:** `parse_date_str` tries `%m/%d/%Y` before `%d-%m-%Y` (ingestion/service.py:25-32) — a `01/02/2024`-style value's meaning depends on format order; no user-facing format selector. Minor.
8. **Audit log uses a key the response never sets:** `rows_inserted` in `metric.data_confirmed` (router.py:117) — always 0; should be `inserted_count`/`updated_count`. Cosmetic.
9. **`run_daily_pipeline` recomputes drivers for every historical anomaly** per metric per day (§3.6).
10. **Rate limiting is per-process** (slowapi in-memory) — with 4 workers the effective limit is 4×. Acceptable; note if it ever becomes a real boundary.

---

## 7. System Integration Review

1. **Contract drift is minimal but real.** The only confirmed mismatch between the two codebases is B1 (`/anomalies/global` vs `/anomalies`). Metrics, notifications, feedback, forecast, and accuracy endpoints line up. That single drift breaks a whole page, and no test on either side detects it because frontend tests mock the API and backend tests mock auth — **integration is the untested layer**.
2. **Auth across the proxy:** Next rewrites `/api/v1/*` to the backend; cookie is `SameSite=Lax` + `credentials:"include"` → same-origin path works. If deployed cross-origin (distinct `NEXT_PUBLIC_API_URL`), `CORS_ORIGINS` must include the app origin and the cookie must be `Secure` — both supported, both easy to misconfigure.
3. **B5** is the worst integration defect: compose's 4 workers × in-process scheduler ⇒ duplicate background execution + duplicate digest emails. Not visible in local dev (1 process), invisible to tests.
4. **Data path inefficiency (confirmed):** upload → backend parses & returns **all rows** → browser holds them → confirm **re-posts all rows** as JSON. A 50MB CSV becomes ~50MB+ of stringified JSON twice. Streaming/chunked server-side processing with a staged job is the current standard (Dromo 2026; ImportCSV 2026; Salesforce guidance) — see §9.
5. **CI seeds workspace 1 but no user** and frontend tests stub `useApi` → the auth/onboarding paths (B2, B3) and the anomaly-log wiring (B1) ship green.
6. **Secret handling** — compose hardcodes `SECRET_KEY` (B7) while the app correctly refuses to boot without one; a stock deploy runs with a known key.

---

## 8. Internet Best-Practice Comparison

Every comparison below is against current (2025–2026) guidance; sources are cited.

| Area | Current best practice | Driftline | Verdict |
|---|---|---|---|
| GET semantics | GET must be safe & idempotent; never mutate (RFC 9110; Postman 2025; DigitalApplied 2026) | `/forecast`, `/accuracy` train ML + write DB (B4) | **Violates** |
| Long-running/ML work | Offload >1s to queue (Celery/RQ) or background job with status polling; never block request (FastAPI docs; Johal 2025; PlainEnglish 2025) | CPU work offloaded to threads; but done synchronously inside GETs on every page view | **Partially** (thread offload good; job model missing) |
| CPU-bound in async | `asyncio.to_thread` frees the loop but GIL caps cores; process pool or worker for scale (FastAPI#8702; CodeWithKarani 2026; SO 2026) | `to_thread` used consistently; `n_jobs=1` models | **Good** |
| Plotly/Next SSR | `next/dynamic` + `ssr:false` mandatory for window-dependent libs (react-plotly.js#273; Krapton 2026; dev.to 2024) | Used everywhere except `anomalies/[id]` static import (B9) | **One violation** |
| JWT storage | HttpOnly+Secure+SameSite cookie; short access token + rotating refresh (LogRocket 2026; Skycloak 2026; Dev.Spot 2026) | Single 60-min cookie JWT, no rotation/silent renewal | **Baseline ok, incomplete** |
| Password hashing | Argon2id; migrate hashes progressively, handle foreign-hash formats (OWASP Cheat Sheet; HashCrack 2026) | Argon2 for new users; foreign bcrypt hash → unhandled `InvalidHashError` (B3) | **Violates on migration** |
| CSV ingestion | Stream server-side; batch inserts; staged job; don't echo full dataset to client (Dromo 2026; ImportCSV 2026; Speakeasy; Salesforce) | Upload streams; but returns all rows + re-post (double transfer), append loads all rows in memory | **Partial** |
| Tailwind v4 | CSS-first `@theme` config; avoid JS config (Tailwind 4.0; Combray 2025; DigitalApplied 2026) | globals.css `@theme` used correctly | **Compliant** |
| Observability | structlog JSON + trace-id injection + OTel; sample aggressively (RealPython 2026; SigNoz 2026) | Matches (correlation id + optional OTel) | **Compliant** |
| Next data fetching | Server Components by default; SWR only for live/polling data (Next docs; jsschools) | Everything client-fetched; SWR polling for notifications is legit; page loads not server-fed | **Acceptable for SPA dashboard** |
| Scheduled jobs | One scheduler with leader election / distributed lock when scaling (Celery beat, APScheduler with DB lock) | In-process AsyncIOScheduler per worker (B5) | **Violates** |

---

## 9. High-Value Improvements (impact order)

1. **Fix B1** — point the page at `/api/v1/anomalies` (or add a backend alias `/anomalies/global`). One line; unblocks a broken page. Add an API-level integration test.
2. **Fix B2** — stop trusting client roles: backend must assign the creating user an owner/admin role and join them to a workspace sensibly (either keep per-user workspace but assign `admin`, or add an invite-to-workspace flow with the default workspace seeded with demo data). Remove `role` from `UserCreate` or ignore it server-side.
3. **Fix B3** — remove the hardcoded hash from the migration (e.g. force password reset or leave null-flag for migrated users), and make `verify_password` treat `InvalidHashError` as invalid (or implement OWASP progressive rehash-on-login). Catch-all in `authenticate_user`.
4. **Fix B4** — convert forecast/accuracy generation to `POST` (or `POST` a job + `GET` status/result), debounce in the UI, cache results. Never train on a page-view GET.
5. **Fix B5** — single-worker scheduler (run gunicorn 1 worker for demo) or add an advisory DB lock (Postgres `pg_advisory_lock`) / leader election around job execution.
6. **Fix B6** — on replace, invalidate `forecasts`, `forecast_accuracy_log`, driver importance, and re-run rollups/anomalies; then expose replace in the UI with a destructive-confirm.
7. **Fix B7** — `SECRET_KEY` from environment; compose fails fast if unset; document generation (`openssl rand -hex 32`).
8. **Fix B9** — switch the static `MetricChart` import to `next/dynamic(..., { ssr:false })` like its sibling pages.
9. **Honor forecast horizon in backtests** (§3.4) or label the accuracy metric honestly (7-day).
10. **Scope driver recompute to recent anomalies** (§3.6) — e.g. only anomalies in the last N days.

## 10. Low-Priority Improvements

1. Font loading via `next/font` / preconnect link instead of CSS `@import` (globals.css:1).
2. Align `eslint-config-next` with `next ^14` (or upgrade Next).
3. Pagination/virtualization for anomaly log; cap notifications payload.
4. Timeout/abort in the `useApi` fetcher + per-request `AbortSignal` (Settings already passes a signal; useApi doesn't).
5. Fix audit log key `rows_inserted` → actual counts (router.py:117).
6. Strict date-format selection in the upload UI; drop ambiguous format guessing.
7. Landing copy de-claims (no DB connector, no real-time, no <1s); remove fake browser bar.
8. A11y: `prefers-reduced-motion` + sound-off preference for the cursor/sound/grain layer.
9. Delete dead API helpers (`fetchGlobalAnomalies`, `fetchNotifications`).
10. Append-mode dedupe via DB query (`(date, dims) NOT IN`) instead of loading all rows; or server-side staged file instead of row re-post (halves transfer).
11. Cross-workspace probe: return 403 for foreign metric IDs.
12. Per-workspace alert/digest recipient config.

## 11. Critical Pre-Release Fixes

Must fix before public/beta launch (all confirmed):
1. **B1** anomaly-log route wiring.
2. **B2** onboarding + server-side role assignment.
3. **B3** auth migration (remove known-password backdoor) + `InvalidHashError` handling.
4. **B4** GETs must not train/write (POST + job or cache).
5. **B5** scheduler duplication under multi-worker.
6. **B6** replace-mode invalidation of derived tables (before exposing replace).
7. **B7** no default `SECRET_KEY` in compose.
8. **B9** dynamic import of MetricChart in `anomalies/[id]`.

## 12. Product Readiness Verdict

**Not ready for general availability.** The analytics engine is credible and would survive scrutiny; the product shell is not. Two main pages/flows are broken (anomaly log, onboarding), one migration can lock out every existing account *and* hand them to a known password, page views retrain ML models, and background jobs run four times. As a **demo/portfolio piece it is nearly ready** — after B1 and B2 it demos well, and the test suite (53 backend tests, real ground-truth evaluation) is a genuine differentiator. With the §11 list cleared (3–7 focused days), this becomes a defensible beta.

## 13. Exact Next Step

Fix **B1** as the first code change, because it is the smallest, fully confirmed, user-visible breaker, and it exercises the frontend→backend contract:

1. `frontend/app/(dashboard)/anomalies/page.tsx:33-35` — change `"/api/v1/anomalies/global"` → `"/api/v1/anomalies"` and `` `/api/v1/anomalies/global?status=${activeTab}` `` → `` `/api/v1/anomalies?status=${activeTab}` `` (backend already supports both filters).
2. Optionally also point `fetchGlobalAnomalies` (api.ts:275) at `/api/v1/anomalies` and use it on the page so the dead helper becomes the live path.
3. Verify: backend `pytest tests/test_anomalies.py -k global` (route returns 200); frontend `npm run test` (vitest) and `npm run build` in `frontend/`. Add one API-level assertion that `GET /api/v1/anomalies?status=new` returns 200 with the filter applied, so the contract can't silently drift again.
4. Then proceed to B2 (onboarding/role) as the next critical item.

---

### Appendix — Evidence index (file:line)

- `frontend/app/(dashboard)/anomalies/page.tsx:33-35` — broken URL; `:20` imports unused `fetchGlobalAnomalies`
- `src/anomalies/router.py:24` — real `GET /anomalies`; `:95` `/anomalies/{id}` int route that 422s `"global"`
- `frontend/app/api.ts:275` — `fetchGlobalAnomalies` (dead); `:421,:430` — notification helpers (dead)
- `src/auth/service.py:17-31` — new workspace per user; `:26` client-supplied role
- `frontend/app/(auth)/register/page.tsx:33` — `role:"member"`
- `src/auth/schemas.py:9` — `role` default `"admin"` accepted from client
- `alembic/versions/2d7591fb702c_add_auth.py:28` — hardcoded bcrypt "password123"
- `src/auth/security.py:24-28` — argon2 verifies, catches only `VerifyMismatchError`; `:14` 60-min token
- `src/forecasting/router.py:18-45,47-73` — state-mutating GETs; `service.py:563-577,743-751` — writes
- `src/forecasting/service.py:627-652` — 7-day folds regardless of requested horizon
- `frontend/app/(dashboard)/settings/page.tsx:101-102` — fires accuracy+forecast GETs on load
- `main.py:36-47` — per-worker `AsyncIOScheduler`; `docker-compose.yml` — 4 gunicorn workers
- `src/jobs/service.py:54-65` — recomputes drivers for all anomalies daily
- `src/ingestion/service.py:353-367` — replace deletes only observations; `:289-305` returns all rows; `:370-380` loads all rows
- `frontend/components/DataUploadModal.tsx:41,136-137` — `workspace_id:1`, row re-post, `replace:false`
- `src/anomalies/service.py:40` — rolling-mean trend (docs claim STL)
- `frontend/app/(dashboard)/anomalies/[id]/page.tsx:19` — static `MetricChart` import
- `frontend/app/globals.css:1` — font `@import`; `:4-40` — Tailwind v4 `@theme` (compliant)
- `frontend/package.json:19,39` — Next 14 vs eslint-config-next 16
- `src/alerts/email.py:11-16,60-70` — SMTP defaults, swallow-fail
- `tests/conftest.py` — mocks `get_current_user`; `tests/test_workspaces.py` — pops override, registers `role:"admin"` explicitly
- `.github/workflows/ci.yml` — seeds workspace only, no user
- `README.md`, `BUILD_LOG.md`, `PROJECT_CONTEXT.md` — STL/Bearer/duplicate-section claims

### Appendix — Internet sources consulted (2025–2026)
- Postman, *REST API Best Practices* (2025); DigitalApplied, *REST API Design in 2026*; Pradeep Loganathan, *REST — Idempotency and Safety*
- FastAPI docs, *Background Tasks*; Johal, *FastAPI Background Tasks: Celery Integration* (2025); PlainEnglish, *Handling Background Tasks and Long-Running Jobs in FastAPI* (2025)
- fastapi/fastapi#8702; CodeWithKarani, *Why Your FastAPI async Endpoints Run in Serial* (2026); StackOverflow 79981101 (2026)
- plotly/react-plotly.js#273; Krapton, *Fix Next.js Window Undefined* (2026); dev.to, *Plotly on Next.js 14 App Router* (2024)
- LogRocket, *JWT authentication: best practices* (2026); Skycloak, *JWT Best Practices* (2026); Dev.Spot, *Refresh Token Rotation and HttpOnly Cookies* (2026); OpenReplay, *Cookies vs localStorage* (2026)
- OWASP, *Password Storage Cheat Sheet*; OnlineHashCrack, *Bcrypt vs Argon2id* (2026)
- Dromo, *Best Practices Handling Large CSV Files* (2026); ImportCSV, *Client-Side vs Server-Side CSV Parsing* (2026); Speakeasy, *File Uploads Best Practices*; Salesforce Help, streaming vs base64
- Combray, *Tailwind CSS v4 Best Practices* (2025); DigitalApplied, *Tailwind v4 Migration* (2026)
- RealPython, *OpenTelemetry With FastAPI* (2026); SigNoz, *OpenTelemetry FastAPI Guide* (2026); dev.to, *Structured Logging With Structlog* (2026)
- Next.js docs, *Client-side data fetching with SWR*; jsschools, *Client data fetching (SWR)*