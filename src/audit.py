"""
Structured audit logging for all state-mutating operations.

Emits structured JSON log entries via structlog with a dedicated 'audit' event type,
capturing who did what, to which entity, and when. These logs can be shipped to any
log aggregator (Datadog, ELK, CloudWatch Logs) for compliance, debugging, and forensics.

Usage:
    from src.audit import audit_log
    audit_log("metric.created", user_id=current_user.id, resource_id=metric.id, details={"name": metric.name})
"""
import structlog
from typing import Any, Dict, Optional

_audit_logger = structlog.get_logger("audit")


def audit_log(
    action: str,
    *,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    workspace_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit a structured audit log entry.

    Args:
        action: Dot-delimited action identifier, e.g. 'metric.created', 'user.role_changed', 'alert_rule.deleted'.
        user_id: The ID of the user performing the action.
        user_email: The email of the user performing the action.
        workspace_id: The workspace context.
        resource_type: The type of resource being acted upon (e.g. 'metric', 'user', 'alert_rule').
        resource_id: The ID of the resource being acted upon.
        details: Additional context (e.g. changed fields, old/new values).
    """
    log_data: Dict[str, Any] = {
        "audit": True,
        "action": action,
    }
    if user_id is not None:
        log_data["user_id"] = user_id
    if user_email is not None:
        log_data["user_email"] = user_email
    if workspace_id is not None:
        log_data["workspace_id"] = workspace_id
    if resource_type is not None:
        log_data["resource_type"] = resource_type
    if resource_id is not None:
        log_data["resource_id"] = resource_id
    if details:
        log_data["details"] = details

    _audit_logger.info("audit_event", **log_data)
