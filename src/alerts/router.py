from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from src.auth.dependencies import get_current_user
from src.ingestion.service import verify_metric_access
from src.auth.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from src.limiter import limiter
from src.audit import audit_log

from src.db.session import get_db
from src.alerts.schemas import (
    AlertRuleCreateSchema,
    AlertRuleResponseSchema,
    NotificationResponseSchema,
)
from src.alerts.service import (
    create_or_update_alert_rule,
    get_alert_rules,
    delete_alert_rule,
    list_notifications,
    mark_notification_read,
)

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["alerts"])

@router.post("/alert-rules", response_model=AlertRuleResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_or_update_alert_rule_endpoint(
    request: Request,
    payload: AlertRuleCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Configures or updates a metric-level min_severity threshold and notification channels idempotently.
    """
    await verify_metric_access(payload.metric_id, db, current_user.workspace_id)
    try:
        rule = await create_or_update_alert_rule(db, payload)
        audit_log("alert_rule.upserted", user_id=current_user.id, workspace_id=current_user.workspace_id,
                 resource_type="alert_rule", resource_id=rule.id,
                 details={"metric_id": payload.metric_id, "min_severity": payload.min_severity})
        channels_list = rule.channels.get("channels", []) if isinstance(rule.channels, dict) else rule.channels
        return AlertRuleResponseSchema(
            id=rule.id,
            metric_id=rule.metric_id,
            min_severity=rule.min_severity,
            channels=channels_list
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to configure alert rule: {str(e)}")

@router.delete("/metrics/{metric_id}/alert-rules", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_alert_rule_endpoint(
    request: Request,
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes an alert rule for a specific metric."""
    await verify_metric_access(metric_id, db, current_user.workspace_id)
    await delete_alert_rule(db, metric_id, current_user.workspace_id)
    audit_log("alert_rule.deleted", user_id=current_user.id, workspace_id=current_user.workspace_id,
             resource_type="alert_rule", details={"metric_id": metric_id})
    return None

@router.get("/metrics/{metric_id}/alert-rules", response_model=List[AlertRuleResponseSchema])
@limiter.limit("60/minute")
async def get_alert_rules_endpoint(
    request: Request,
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists configured alert rules."""
    await verify_metric_access(metric_id, db, current_user.workspace_id)
    rules = await get_alert_rules(db, workspace_id=current_user.workspace_id, metric_id=metric_id)
    out = []
    for r in rules:
        channels_list = r.channels.get("channels", []) if isinstance(r.channels, dict) else r.channels
        out.append(AlertRuleResponseSchema(
            id=r.id,
            metric_id=r.metric_id,
            min_severity=r.min_severity,
            channels=channels_list
        ))
    return out

@router.get("/notifications", response_model=List[NotificationResponseSchema])
@limiter.limit("60/minute")
async def get_notifications_endpoint(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Max notification count"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the in-app notification list for a workspace, ordered by created_at descending.
    """
    notifications = await list_notifications(db, workspace_id=current_user.workspace_id, limit=limit)
    return [NotificationResponseSchema.model_validate(n) for n in notifications]

@router.patch("/notifications/{id}/read", response_model=NotificationResponseSchema)
@limiter.limit("20/minute")
async def mark_notification_read_endpoint(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marks an in-app notification as read."""
    notification = await mark_notification_read(db, id, current_user.workspace_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notification #{id} not found.")
    return NotificationResponseSchema.model_validate(notification)
