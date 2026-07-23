import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import Metric
from src.anomalies.models import Anomaly, AnomalyStatusEnum
from src.alerts.models import AlertRule, Notification, User
from src.alerts.schemas import AlertRuleCreateSchema, ChannelEnum
from src.alerts.email import send_immediate_alert_email

logger = logging.getLogger(__name__)

async def create_or_update_alert_rule(db: AsyncSession, schema: AlertRuleCreateSchema) -> AlertRule:
    """
    Creates or updates the alert rule for a metric idempotently.
    """
    channel_list = [c.value if isinstance(c, ChannelEnum) else str(c) for c in schema.channels]
    
    # Query existing rule
    res = await db.execute(select(AlertRule).where(AlertRule.metric_id == schema.metric_id))
    rule = res.scalar_one_or_none()

    if rule:
        rule.min_severity = schema.min_severity
        rule.channels = {"channels": channel_list}
    else:
        rule = AlertRule(
            metric_id=schema.metric_id,
            min_severity=schema.min_severity,
            channels={"channels": channel_list}
        )
        db.add(rule)

    await db.commit()
    await db.refresh(rule)
    return rule

async def get_alert_rules(db: AsyncSession, metric_id: Optional[int] = None) -> List[AlertRule]:
    """Retrieves alert rules, optionally filtered by metric_id."""
    stmt = select(AlertRule)
    if metric_id is not None:
        stmt = stmt.where(AlertRule.metric_id == metric_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())

async def evaluate_and_trigger_alerts_for_metric(db: AsyncSession, metric_id: int) -> List[Notification]:
    """
    Evaluates anomalies for a metric against its configured min_severity threshold using a left-anti-join:
    Queries un-notified anomalies where severity_score >= min_severity and status is not false_positive/resolved.
    Creates and commits Notification records in DB, and dispatches immediate alert emails if email channel is enabled.
    """
    # 1. Fetch metric
    m_res = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = m_res.scalar_one_or_none()
    if not metric:
        return []

    # 2. Fetch alert rule for metric
    rule_res = await db.execute(select(AlertRule).where(AlertRule.metric_id == metric_id))
    rule = rule_res.scalar_one_or_none()

    if rule:
        min_severity = float(rule.min_severity)
        channels_raw = rule.channels.get("channels", ["in_app"]) if isinstance(rule.channels, dict) else rule.channels
    else:
        # Default unconfigured metric rules
        min_severity = 80.0
        channels_raw = ["in_app"]

    enabled_channels = [str(c).lower() for c in (channels_raw if isinstance(channels_raw, list) else [])]

    # 3. Left-Anti-Join Query: Un-notified, non-dismissed anomalies breaching min_severity threshold
    stmt = select(Anomaly).where(
        Anomaly.metric_id == metric_id,
        Anomaly.severity_score >= min_severity,
        Anomaly.status.notin_([AnomalyStatusEnum.false_positive, AnomalyStatusEnum.resolved]),
        ~Anomaly.id.in_(select(Notification.anomaly_id).where(Notification.metric_id == metric_id))
    ).order_by(Anomaly.date.asc())

    anom_res = await db.execute(stmt)
    target_anomalies = list(anom_res.scalars().all())

    if not target_anomalies:
        return []

    # 4. Resolve recipient email if email channel is enabled
    recipient_email = None
    if "email" in enabled_channels:
        u_res = await db.execute(select(User.email).where(User.workspace_id == metric.workspace_id))
        recipient_email = u_res.scalars().first()

    created_notifications = []

    for anomaly in target_anomalies:
        try:
            explanation = anomaly.explanation_text or f"High severity anomaly detected on {anomaly.date} (severity {anomaly.severity_score:.1f})."
            title_str = f"High-Severity Anomaly ({anomaly.type.value.capitalize()}) on {metric.name}"

            notification = Notification(
                workspace_id=metric.workspace_id,
                metric_id=metric_id,
                anomaly_id=anomaly.id,
                title=title_str,
                message=explanation,
                severity_score=anomaly.severity_score,
                is_read=False
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            created_notifications.append(notification)

            # 5. Isolated local SMTP dispatch (failure will never rollback DB notification)
            if "email" in enabled_channels:
                try:
                    send_immediate_alert_email(
                        workspace_id=metric.workspace_id,
                        metric_name=metric.name,
                        anomaly_date=anomaly.date.isoformat(),
                        severity_score=anomaly.severity_score,
                        explanation_text=explanation,
                        recipient_email=recipient_email
                    )
                except Exception as email_err:
                    logger.warning(f"Immediate alert email dispatch failed for anomaly #{anomaly.id}: {str(email_err)}")

        except Exception as e:
            logger.error(f"Failed to process notification for anomaly #{anomaly.id}: {str(e)}", exc_info=True)
            await db.rollback()

    return created_notifications

async def list_notifications(
    db: AsyncSession,
    workspace_id: Optional[int] = None,
    limit: int = 50
) -> List[Notification]:
    """Lists in-app notifications for a workspace, ordered by created_at descending."""
    stmt = select(Notification).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    if workspace_id is not None:
        stmt = stmt.where(Notification.workspace_id == workspace_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())

async def mark_notification_read(db: AsyncSession, notification_id: int) -> Optional[Notification]:
    """Marks an in-app notification as read."""
    res = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = res.scalar_one_or_none()
    if notification:
        notification.is_read = True
        await db.commit()
        await db.refresh(notification)
    return notification
