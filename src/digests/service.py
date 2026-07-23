import os
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import AsyncSessionLocal
from src.ingestion.models import Metric, Observation
from src.anomalies.models import DailyRollup, Anomaly
from src.anomalies.service import run_daily_rollup_and_decomposition, detect_and_persist_anomalies
from src.drivers.service import calculate_anomaly_drivers, train_and_persist_structural_importance
from src.forecasting.models import Forecast, ForecastAccuracyLog
from src.forecasting.service import generate_multi_step_forecast, run_walk_forward_backtest, get_forecast_accuracy
from src.digests.models import Digest

logger = logging.getLogger(__name__)

STORAGE_DIR = os.getenv("DIGEST_STORAGE_DIR", os.path.join(os.getcwd(), "storage", "digests"))

async def generate_weekly_digest(
    db: AsyncSession,
    workspace_id: int,
    metric_id: int
) -> Digest:
    """
    Generates a headless 1-page PDF digest for the specified metric covering the 7-day period ending on max observation date.
    Performs idempotent database upsert on (workspace_id, metric_id, period_start, period_end).
    """
    # 1. Query Metric
    m_stmt = select(Metric).where(Metric.id == metric_id)
    m_res = await db.execute(m_stmt)
    metric = m_res.scalar_one_or_none()
    if not metric:
        raise ValueError(f"Metric {metric_id} not found")

    # 2. Query total daily rollups for the metric
    rollups_stmt = select(DailyRollup).where(
        DailyRollup.metric_id == metric_id,
        DailyRollup.dimension_values == {}
    ).order_by(DailyRollup.date.asc())
    r_res = await db.execute(rollups_stmt)
    total_rollups = list(r_res.scalars().all())

    if not total_rollups:
        raise ValueError(f"Metric {metric_id} has no daily rollups available to generate a digest.")

    max_date = max(r.date for r in total_rollups)
    period_end = max_date
    period_start = max_date - timedelta(days=6)

    # 3. Period Total & Prior Period Total
    period_rollups = [r for r in total_rollups if period_start <= r.date <= period_end]
    period_total = sum(r.value_total for r in period_rollups)

    prior_period_start = period_start - timedelta(days=7)
    prior_period_end = period_start - timedelta(days=1)
    prior_rollups = [r for r in total_rollups if prior_period_start <= r.date <= prior_period_end]
    prior_period_total = sum(r.value_total for r in prior_rollups)

    # Period-over-period change calculation with zero guard
    if len(prior_rollups) > 0 and prior_period_total != 0:
        abs_change = period_total - prior_period_total
        pct_change = (abs_change / abs(prior_period_total)) * 100.0
        change_str = f"{abs_change:+.1f} ({pct_change:+.1f}%)"
    else:
        change_str = "Initial digest period (no prior baseline)"

    # 4. Anomaly / Driver Explanation Text for the period
    anom_stmt = select(Anomaly).where(
        Anomaly.metric_id == metric_id,
        Anomaly.date >= period_start - timedelta(days=7)
    ).order_by(Anomaly.severity_score.desc())
    anom_res = await db.execute(anom_stmt)
    anomalies = list(anom_res.scalars().all())

    if anomalies:
        top_anom = anomalies[0]
        explanation = top_anom.explanation_text or f"{top_anom.type.value.capitalize()} detected on {top_anom.date} with severity {top_anom.severity_score:.1f}."
        if len(anomalies) > 1:
            anomaly_summary = f"Primary Anomaly ({top_anom.type.value}, severity {top_anom.severity_score:.1f}): {explanation} ({len(anomalies) - 1} other anomalies detected this period)."
        else:
            anomaly_summary = f"Anomaly ({top_anom.type.value}, severity {top_anom.severity_score:.1f}): {explanation}"
    else:
        anomaly_summary = "No anomalies detected during this 7-day period."

    # 5. MAPE Stat from 12-week backtest accuracy logs
    accuracy_info = await get_forecast_accuracy(
        metric_id=metric_id,
        session=db,
        horizon_days=7,
        auto_run=False
    )
    mape_val = accuracy_info.get("mape")
    mape_str = f"{mape_val * 100.0:.2f}%" if mape_val is not None else "N/A"

    # 6. Fetch 30-day recent actuals and active 30-day forecast
    hist_cutoff = max_date - timedelta(days=30)
    recent_rollups = [r for r in total_rollups if r.date >= hist_cutoff]

    forecast_stmt = select(Forecast).where(
        Forecast.metric_id == metric_id,
        Forecast.dimension_values == {}
    ).order_by(Forecast.forecast_date.asc())
    f_res = await db.execute(forecast_stmt)
    forecasts = list(f_res.scalars().all())

    # 7. Render Matplotlib PDF
    os.makedirs(STORAGE_DIR, exist_ok=True)
    pdf_path = os.path.join(STORAGE_DIR, f"digest_{metric_id}_{period_start.isoformat()}_{period_end.isoformat()}.pdf")

    fig = plt.figure(figsize=(8.5, 11), dpi=150)
    fig.patch.set_facecolor('#ffffff')

    # Grid layout: Title (top), Big Numbers (middle top), Anomaly/Driver (middle), Forecast Plot (bottom)
    gs = fig.add_gridspec(4, 1, height_ratios=[1.2, 1.8, 1.8, 4.2], hspace=0.4)

    # Panel 1: Header Banner
    ax0 = fig.add_subplot(gs[0])
    ax0.axis('off')
    ax0.text(0.0, 0.75, "DRIFTLINE METRIC DIGEST", fontsize=18, fontweight='bold', color='#1e293b')
    unit_str = f" ({metric.unit})" if metric.unit else ""
    ax0.text(0.0, 0.40, f"Metric: {metric.name}{unit_str}", fontsize=14, fontweight='bold', color='#0f766e')
    ax0.text(0.0, 0.10, f"Period Covered: {period_start.isoformat()} to {period_end.isoformat()} (Workspace #{workspace_id})", fontsize=11, color='#64748b')
    ax0.axhline(0.0, color='#cbd5e1', linewidth=1.5)

    # Panel 2: Big Number Summary Card
    ax1 = fig.add_subplot(gs[1])
    ax1.axis('off')
    ax1.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax1.transAxes, facecolor='#f8fafc', edgecolor='#e2e8f0'))
    
    ax1.text(0.05, 0.70, "PERIOD TOTAL VALUE", fontsize=9, fontweight='bold', color='#64748b', transform=ax1.transAxes)
    ax1.text(0.05, 0.30, f"{period_total:,.1f}", fontsize=24, fontweight='bold', color='#0f172a', transform=ax1.transAxes)

    ax1.text(0.45, 0.70, "CHANGE VS PRIOR WEEK", fontsize=9, fontweight='bold', color='#64748b', transform=ax1.transAxes)
    change_color = '#16a34a' if '+$' in change_str or '+' in change_str else ('#dc2626' if '-' in change_str else '#0f172a')
    ax1.text(0.45, 0.30, change_str, fontsize=14, fontweight='bold', color=change_color, transform=ax1.transAxes)

    ax1.text(0.75, 0.70, "PRIOR WEEK TOTAL", fontsize=9, fontweight='bold', color='#64748b', transform=ax1.transAxes)
    ax1.text(0.75, 0.30, f"{prior_period_total:,.1f}", fontsize=14, fontweight='bold', color='#475569', transform=ax1.transAxes)

    # Panel 3: Anomaly & Driver Explanation Card
    ax2 = fig.add_subplot(gs[2])
    ax2.axis('off')
    ax2.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax2.transAxes, facecolor='#f8fafc', edgecolor='#cbd5e1'))
    
    ax2.text(0.05, 0.80, "ANOMALY & ROOT-CAUSE DRIVER SUMMARY", fontsize=10, fontweight='bold', color='#1e293b', transform=ax2.transAxes)
    
    # Wrap explanation text for clean card rendering
    words = anomaly_summary.split()
    lines = []
    curr_line = []
    for w in words:
        curr_line.append(w)
        if len(" ".join(curr_line)) > 75:
            lines.append(" ".join(curr_line[:-1]))
            curr_line = [w]
    if curr_line:
        lines.append(" ".join(curr_line))
    
    wrapped_text = "\n".join(lines[:3])
    ax2.text(0.05, 0.25, wrapped_text, fontsize=9.5, color='#334155', transform=ax2.transAxes, verticalalignment='top')

    # Panel 4: Forecast & Accuracy Chart
    ax3 = fig.add_subplot(gs[3])
    
    hist_dates = [r.date for r in recent_rollups]
    hist_vals = [r.value_total for r in recent_rollups]
    
    ax3.plot(hist_dates, hist_vals, color='#2563eb', linewidth=2, label='Actual Values')
    
    if forecasts:
        fc_dates = [f.forecast_date for f in forecasts]
        fc_p50 = [f.p50 for f in forecasts]
        fc_p10 = [f.p10 for f in forecasts]
        fc_p90 = [f.p90 for f in forecasts]
        
        # Connect last actual point to first forecast point for smooth continuity
        if hist_dates:
            conn_dates = [hist_dates[-1]] + fc_dates
            conn_p50 = [hist_vals[-1]] + fc_p50
            conn_p10 = [hist_vals[-1]] + fc_p10
            conn_p90 = [hist_vals[-1]] + fc_p90
        else:
            conn_dates, conn_p50, conn_p10, conn_p90 = fc_dates, fc_p50, fc_p10, fc_p90
            
        ax3.plot(conn_dates, conn_p50, color='#7c3aed', linestyle='--', linewidth=2, label='Forecast p50 (Median)')
        ax3.fill_between(conn_dates, conn_p10, conn_p90, color='#8b5cf6', alpha=0.2, label='p10 - p90 Prediction Band')

    ax3.set_title(f"30-Day Trend & Forecast (12-Week 7-Day MAPE: {mape_str})", fontsize=11, fontweight='bold', color='#1e293b', pad=10)
    ax3.set_ylabel("Metric Value", fontsize=9, color='#475569')
    ax3.tick_params(axis='x', rotation=30, labelsize=8)
    ax3.tick_params(axis='y', labelsize=8)
    ax3.grid(True, linestyle=':', alpha=0.6)
    ax3.legend(loc='upper left', fontsize=8, frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')

    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

    # 8. Idempotent Database Upsert
    stmt = insert(Digest).values(
        workspace_id=workspace_id,
        metric_id=metric_id,
        period_start=period_start,
        period_end=period_end,
        pdf_path=pdf_path
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_digests_workspace_metric_period",
        set_={
            "pdf_path": stmt.excluded.pdf_path,
            "generated_at": func.now()
        }
    )
    await db.execute(stmt)
    await db.commit()

    # Fetch and return inserted/updated record
    res_digest = await db.execute(
        select(Digest).where(
            Digest.workspace_id == workspace_id,
            Digest.metric_id == metric_id,
            Digest.period_start == period_start,
            Digest.period_end == period_end
        )
    )
    return res_digest.scalar_one()

async def run_daily_pipeline(
    db: Optional[AsyncSession] = None,
    metric_ids: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Daily scheduled job:
    For every metric (or filtered metric_ids): re-runs decomposition on new data, runs anomaly detection, and computes driver analysis.
    Manages self-contained AsyncSessionLocal lifecycle if db is None.
    """
    if db is None:
        async with AsyncSessionLocal() as session:
            return await run_daily_pipeline(db=session, metric_ids=metric_ids)

    stmt = select(Metric)
    if metric_ids:
        stmt = stmt.where(Metric.id.in_(metric_ids))

    res = await db.execute(stmt)
    metrics = list(res.scalars().all())
    metric_info_list = [(m.id, m.name) for m in metrics]

    results = []
    for m_id, m_name in metric_info_list:
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
                    driver_data = await calculate_anomaly_drivers(db, anomaly.id)
                    anomaly.explanation_text = driver_data["explanation_text"]
                except Exception as ex:
                    logger.warning(f"Driver analysis skipped for anomaly #{anomaly.id}: {str(ex)}")

            await db.commit()

            # 3. Evaluate anomalies against alert rules and trigger in-app notifications & immediate emails
            try:
                from src.alerts.service import evaluate_and_trigger_alerts_for_metric
                await evaluate_and_trigger_alerts_for_metric(db, m_id)
            except Exception as alert_ex:
                logger.warning(f"Alert evaluation failed for metric #{m_id}: {str(alert_ex)}")

            results.append({"metric_id": m_id, "status": "success", "anomalies_count": len(anomalies)})
        except Exception as e:
            logger.error(f"Daily pipeline failed for metric #{m_id}: {str(e)}", exc_info=True)
            await db.rollback()
            results.append({"metric_id": m_id, "status": "failed", "error": str(e)})

    return results

async def run_weekly_retrain_and_digest(
    db: Optional[AsyncSession] = None,
    metric_ids: Optional[List[int]] = None
) -> List[Digest]:
    """
    Weekly scheduled job:
    For every metric (or filtered metric_ids): retrains CatBoost structural importance, retrains forecasting models,
    runs walk-forward backtest, generates the weekly digest PDF, and dispatches weekly email.
    Manages self-contained AsyncSessionLocal lifecycle if db is None.
    """
    if db is None:
        async with AsyncSessionLocal() as session:
            return await run_weekly_retrain_and_digest(db=session, metric_ids=metric_ids)

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
                logger.warning(f"Weekly digest email dispatch failed for metric #{m_id}: {str(mail_ex)}")

        except Exception as e:
            logger.error(f"Weekly retrain & digest failed for metric #{m_id}: {str(e)}", exc_info=True)
            await db.rollback()

    return digests





async def get_digest_by_id(db: AsyncSession, digest_id: int) -> Optional[Digest]:
    """Retrieves digest by primary key ID."""
    res = await db.execute(select(Digest).where(Digest.id == digest_id))
    return res.scalar_one_or_none()

async def list_digests(
    db: AsyncSession,
    workspace_id: Optional[int] = None,
    metric_id: Optional[int] = None
) -> List[Digest]:
    """Lists digests optionally filtered by workspace_id or metric_id."""
    stmt = select(Digest).order_by(Digest.generated_at.desc())
    if workspace_id is not None:
        stmt = stmt.where(Digest.workspace_id == workspace_id)
    if metric_id is not None:
        stmt = stmt.where(Digest.metric_id == metric_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())
