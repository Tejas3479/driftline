import uuid
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.anomalies.models import Anomaly
from src.anomalies.service import run_daily_rollup_and_decomposition
from src.db.session import AsyncSessionLocal
from src.digests.models import Digest
from src.digests.service import generate_weekly_digest
from src.drivers.service import (
    calculate_anomaly_drivers,
    train_and_persist_structural_importance,
)
from src.forecasting.service import (
    generate_multi_step_forecast,
    run_walk_forward_backtest,
)
from src.ingestion.models import Metric

logger = structlog.get_logger(__name__)

# Advisory lock keys: guarantee a single scheduler instance runs each job even
# when the app runs multiple gunicorn workers (each worker starts its own AsyncIOScheduler).
DAILY_PIPELINE_LOCK_KEY = 790_001
WEEKLY_RETRAIN_LOCK_KEY = 790_002


async def _try_acquire_job_lock(session: AsyncSession, key: int) -> bool:
    res = await session.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
    )
    return bool(res.scalar_one_or_none())


async def _release_job_lock(session: AsyncSession, key: int) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(:key)"), {"key": key}
    )


async def run_daily_pipeline(
    db: AsyncSession | None = None,
    metric_ids: list[int] | None = None
) -> list[dict[str, Any]]:
    """
    Daily scheduled job:
    For every metric (or filtered metric_ids): re-runs decomposition on new data, runs anomaly detection, and computes driver analysis.
    Manages self-contained AsyncSessionLocal lifecycle if db is None.
    """
    structlog.contextvars.bind_contextvars(request_id=f"sched-{uuid.uuid4().hex[:8]}")
    if db is None:
        async with AsyncSessionLocal() as session:
            if not await _try_acquire_job_lock(session, DAILY_PIPELINE_LOCK_KEY):
                logger.info("run_daily_pipeline skipped: advisory lock already held by another scheduler instance")
                return []
            try:
                return await run_daily_pipeline(db=session, metric_ids=metric_ids)
            finally:
                await _release_job_lock(session, DAILY_PIPELINE_LOCK_KEY)

    stmt = select(Metric)
    if metric_ids:
        stmt = stmt.where(Metric.id.in_(metric_ids))

    res = await db.execute(stmt)
    metrics = list(res.scalars().all())
    metric_info_list = [(m.id, m.name, m.workspace_id) for m in metrics]

    results = []
    for m_id, m_name, w_id in metric_info_list:
        try:
            logger.info(f"Running daily pipeline for metric #{m_id} ({m_name})...")
            # 1. Re-run daily rollups and decomposition (which triggers anomaly detection internally)
            await run_daily_rollup_and_decomposition(db, m_id)

            # 2. Query anomalies and update driver explanations for recent anomalies
            anom_res = await db.execute(
                select(Anomaly).where(Anomaly.metric_id == m_id).order_by(Anomaly.date.desc())
            )
            anomalies = list(anom_res.scalars().all())

            for anomaly in anomalies:
                try:
                    driver_data = await calculate_anomaly_drivers(db, anomaly.id, workspace_id=w_id)
                    anomaly.explanation_text = driver_data["explanation_text"]
                except Exception as ex:
                    logger.warning(f"Driver analysis skipped for anomaly #{anomaly.id}: {ex!s}")

            await db.commit()

            # 3. Evaluate anomalies against alert rules and trigger in-app notifications & immediate emails
            try:
                from src.alerts.service import evaluate_and_trigger_alerts_for_metric
                await evaluate_and_trigger_alerts_for_metric(db, m_id)
            except Exception as alert_ex:
                logger.warning(f"Alert evaluation failed for metric #{m_id}: {alert_ex!s}")

            results.append({"metric_id": m_id, "status": "success", "anomalies_count": len(anomalies)})
        except Exception as e:
            logger.error(f"Daily pipeline failed for metric #{m_id}: {e!s}", exc_info=True)
            await db.rollback()
            results.append({"metric_id": m_id, "status": "failed", "error": str(e)})

    return results

async def run_weekly_retrain_and_digest(
    db: AsyncSession | None = None,
    metric_ids: list[int] | None = None
) -> list[Digest]:
    """
    Weekly scheduled job:
    For every metric (or filtered metric_ids): retrains CatBoost structural importance, retrains forecasting models,
    runs walk-forward backtest, generates the weekly digest PDF, and dispatches weekly email.
    Manages self-contained AsyncSessionLocal lifecycle if db is None.
    """
    structlog.contextvars.bind_contextvars(request_id=f"sched-{uuid.uuid4().hex[:8]}")
    if db is None:
        async with AsyncSessionLocal() as session:
            if not await _try_acquire_job_lock(session, WEEKLY_RETRAIN_LOCK_KEY):
                logger.info("run_weekly_retrain_and_digest skipped: advisory lock already held by another scheduler instance")
                return []
            try:
                return await run_weekly_retrain_and_digest(db=session, metric_ids=metric_ids)
            finally:
                await _release_job_lock(session, WEEKLY_RETRAIN_LOCK_KEY)

    stmt = select(Metric)
    if metric_ids:
        stmt = stmt.where(Metric.id.in_(metric_ids))

    res = await db.execute(stmt)
    metrics = list(res.scalars().all())
    metric_info_list = [(m.id, m.workspace_id, m.name) for m in metrics]

    digests = []
    for m_id, w_id, m_name in metric_info_list:
        try:
            logger.info(f"Running weekly retrain & digest pipeline for metric #{m_id} ({m_name})...")
            # Sequential execution order:
            # Step 1: Retrain CatBoost structural importance
            await train_and_persist_structural_importance(db, m_id)

            # Step 2: Retrain forecasting models & generate 30-day forecast
            await generate_multi_step_forecast(metric_id=m_id, session=db, horizon_days=30, save_to_db=True)

            # Step 3: Run walk-forward backtest (7-day horizon)
            await run_walk_forward_backtest(metric_id=m_id, session=db, horizon_days=7)

            # Step 4: Generate weekly digest PDF (reads fresh accuracy log)
            digest = await generate_weekly_digest(db=db, workspace_id=w_id, metric_id=m_id)
            digests.append(digest)

            # Step 5: Dispatch weekly digest email with PDF attached
            try:
                from src.alerts.email import send_weekly_digest_email
                send_weekly_digest_email(
                    workspace_id=w_id,
                    metric_name=m_name,
                    period_str=f"{digest.period_start.isoformat()} to {digest.period_end.isoformat()}",
                    pdf_path=digest.pdf_path
                )
            except Exception as mail_ex:
                logger.warning(f"Weekly digest email dispatch failed for metric #{m_id}: {mail_ex!s}")

        except Exception as e:
            logger.error(f"Weekly retrain & digest failed for metric #{m_id}: {e!s}", exc_info=True)
            await db.rollback()

    return digests
