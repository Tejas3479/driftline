import os
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import date
from sqlalchemy import select, delete

from main import app
from src.ingestion.models import Metric, DirectionGoodEnum, SensitivityEnum, GrainEnum
from src.anomalies.models import Anomaly, AnomalyTypeEnum, AnomalyStatusEnum
from src.alerts.models import AlertRule, Notification
from src.alerts.schemas import AlertRuleCreateSchema, ChannelEnum
from src.alerts.service import (
    create_or_update_alert_rule,
    get_alert_rules,
    evaluate_and_trigger_alerts_for_metric,
    list_notifications,
    mark_notification_read,
)

@pytest.mark.asyncio
async def test_high_severity_alert_trigger_and_email_mock(override_db_dependency):
    """
    Asserts an anomaly above min_severity creates an in-app notification record and invokes SMTP email sender.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create metric via API
        m_resp = await client.post("/metrics", json={
            "workspace_id": 1,
            "name": "Revenue Metric",
            "unit": "USD",
            "direction_good": "up_is_good",
            "sensitivity": "medium",
            "grain": "daily"
        })
        assert m_resp.status_code == 201
        metric_id = m_resp.json()["id"]

        # 2. Configure alert rule with min_severity 50.0 and email channel
        rule_resp = await client.post("/alert-rules", json={
            "metric_id": metric_id,
            "min_severity": 50.0,
            "channels": ["in_app", "email"]
        })
        assert rule_resp.status_code == 201
        assert rule_resp.json()["min_severity"] == 50.0

        # 3. Inject high severity anomaly (severity 75.0 > 50.0)
        from src.db.session import get_db
        from src.auth.models import User
        async for session in app.dependency_overrides[get_db]():
            # Seed mock user so recipient_email lookup passes
            user = User(workspace_id=1, email="test@example.com", hashed_password="xyz")
            session.add(user)
            await session.commit()
            
            anomaly = Anomaly(
                metric_id=metric_id,
                date=date(2026, 3, 1),
                severity_score=75.0,
                type=AnomalyTypeEnum.spike,
                z_score=3.5,
                isolation_score=0.8,
                status=AnomalyStatusEnum.new,
                explanation_text="High severity revenue spike detected."
            )
            session.add(anomaly)
            await session.commit()
            await session.refresh(anomaly)
            anomaly_id = anomaly.id

            # 4. Mock SMTP email dispatch
            with patch("src.alerts.service.send_immediate_alert_email") as mock_send_email:
                notifications = await evaluate_and_trigger_alerts_for_metric(session, metric_id)
                
                assert len(notifications) == 1
                assert notifications[0].anomaly_id == anomaly_id
                assert notifications[0].severity_score == 75.0
                assert mock_send_email.called

            # 5. Verify GET /notifications API endpoint
            notif_resp = await client.get("/notifications?workspace_id=1")
            assert notif_resp.status_code == 200
            notifs = notif_resp.json()
            assert len(notifs) >= 1
            assert notifs[0]["anomaly_id"] == anomaly_id
            assert notifs[0]["is_read"] is False

            # 6. Mark notification as read
            notif_id = notifs[0]["id"]
            read_resp = await client.patch(f"/notifications/{notif_id}/read")
            assert read_resp.status_code == 200
            assert read_resp.json()["is_read"] is True

@pytest.mark.asyncio
async def test_low_severity_alert_suppression(override_db_dependency):
    """
    Asserts an anomaly below min_severity threshold does NOT create a notification or send email.
    """
    from src.db.session import get_db
    async for session in app.dependency_overrides[get_db]():
        # Create metric
        metric = Metric(
            workspace_id=1,
            name="Low Severity Metric",
            unit="USD",
            direction_good=DirectionGoodEnum.up_is_good,
            sensitivity=SensitivityEnum.medium,
            grain=GrainEnum.daily
        )
        session.add(metric)
        await session.commit()

        # Configure rule min_severity 80.0
        await create_or_update_alert_rule(session, AlertRuleCreateSchema(
            metric_id=metric.id,
            min_severity=80.0,
            channels=[ChannelEnum.in_app, ChannelEnum.email]
        ))

        # Inject anomaly with severity 40.0 (< 80.0)
        anomaly = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 2),
            severity_score=40.0,
            type=AnomalyTypeEnum.dip,
            z_score=-1.5,
            isolation_score=0.2,
            status=AnomalyStatusEnum.new,
            explanation_text="Minor dip below threshold."
        )
        session.add(anomaly)
        await session.commit()

        with patch("src.alerts.service.send_immediate_alert_email") as mock_send_email:
            notifications = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
            assert len(notifications) == 0
            assert not mock_send_email.called

@pytest.mark.asyncio
async def test_severity_drift_threshold_crossing(override_db_dependency):
    """
    Asserts an anomaly starting below threshold creates 0 notifications initially,
    and creates 1 notification after its severity score is recomputed above threshold.
    """
    from src.db.session import get_db
    async for session in app.dependency_overrides[get_db]():
        metric = Metric(
            workspace_id=1,
            name="Drifting Severity Metric",
            unit="USD",
            direction_good=DirectionGoodEnum.up_is_good,
            sensitivity=SensitivityEnum.medium,
            grain=GrainEnum.daily
        )
        session.add(metric)
        await session.commit()

        await create_or_update_alert_rule(session, AlertRuleCreateSchema(
            metric_id=metric.id,
            min_severity=50.0,
            channels=[ChannelEnum.in_app]
        ))

        anomaly = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 3),
            severity_score=40.0,  # Starts below threshold
            type=AnomalyTypeEnum.level_shift,
            z_score=1.8,
            isolation_score=0.4,
            status=AnomalyStatusEnum.new,
            explanation_text="Initial candidate level shift."
        )
        session.add(anomaly)
        await session.commit()

        # Call 1: Below threshold -> 0 notifications
        notifs_1 = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
        assert len(notifs_1) == 0

        # Simulate baseline drift recomputation bumping severity to 65.0
        anomaly.severity_score = 65.0
        await session.commit()

        # Call 2: Crosses threshold -> 1 notification created
        notifs_2 = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
        assert len(notifs_2) == 1
        assert notifs_2[0].anomaly_id == anomaly.id

@pytest.mark.asyncio
async def test_false_positive_and_resolved_suppression(override_db_dependency):
    """
    Asserts anomalies marked false_positive or resolved never trigger notifications even if severity > min_severity.
    """
    from src.db.session import get_db
    async for session in app.dependency_overrides[get_db]():
        metric = Metric(
            workspace_id=1,
            name="Dismissed Metric",
            unit="USD",
            direction_good=DirectionGoodEnum.up_is_good,
            sensitivity=SensitivityEnum.medium,
            grain=GrainEnum.daily
        )
        session.add(metric)
        await session.commit()

        await create_or_update_alert_rule(session, AlertRuleCreateSchema(
            metric_id=metric.id,
            min_severity=50.0,
            channels=[ChannelEnum.in_app]
        ))

        # Inject false_positive anomaly
        fp_anom = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 4),
            severity_score=85.0,
            type=AnomalyTypeEnum.spike,
            z_score=4.0,
            isolation_score=0.9,
            status=AnomalyStatusEnum.false_positive,
            explanation_text="User flagged false positive."
        )
        session.add(fp_anom)

        # Inject resolved anomaly
        res_anom = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 5),
            severity_score=90.0,
            type=AnomalyTypeEnum.volatility,
            z_score=4.5,
            isolation_score=0.95,
            status=AnomalyStatusEnum.resolved,
            explanation_text="User resolved issue."
        )
        session.add(res_anom)
        await session.commit()

        notifs = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
        assert len(notifs) == 0

@pytest.mark.asyncio
async def test_alert_evaluation_idempotency(override_db_dependency):
    """
    Asserts calling evaluate_and_trigger_alerts_for_metric twice consecutively creates exactly 1 notification
    and does not raise duplicate-key errors.
    """
    from src.db.session import get_db
    async for session in app.dependency_overrides[get_db]():
        metric = Metric(
            workspace_id=1,
            name="Idempotency Metric",
            unit="USD",
            direction_good=DirectionGoodEnum.up_is_good,
            sensitivity=SensitivityEnum.medium,
            grain=GrainEnum.daily
        )
        session.add(metric)
        await session.commit()

        await create_or_update_alert_rule(session, AlertRuleCreateSchema(
            metric_id=metric.id,
            min_severity=50.0,
            channels=[ChannelEnum.in_app]
        ))

        anomaly = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 6),
            severity_score=70.0,
            type=AnomalyTypeEnum.spike,
            z_score=3.2,
            isolation_score=0.75,
            status=AnomalyStatusEnum.new,
            explanation_text="Spike for idempotency test."
        )
        session.add(anomaly)
        await session.commit()

        # Run 1
        n1 = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
        assert len(n1) == 1

        # Run 2 (duplicate check)
        n2 = await evaluate_and_trigger_alerts_for_metric(session, metric.id)
        assert len(n2) == 0  # 0 new notifications created on second run

        # Assert DB total count remains 1
        res = await session.execute(select(Notification).where(Notification.metric_id == metric.id))
        all_notifs = list(res.scalars().all())
        assert len(all_notifs) == 1

@pytest.mark.asyncio
async def test_smtp_failure_resilience(override_db_dependency):
    """
    Asserts an SMTP network connection failure logs a warning and does NOT prevent the DB Notification record from saving.
    """
    from src.db.session import get_db
    async for session in app.dependency_overrides[get_db]():
        metric = Metric(
            workspace_id=1,
            name="SMTP Resilience Metric",
            unit="USD",
            direction_good=DirectionGoodEnum.up_is_good,
            sensitivity=SensitivityEnum.medium,
            grain=GrainEnum.daily
        )
        session.add(metric)
        await session.commit()

        await create_or_update_alert_rule(session, AlertRuleCreateSchema(
            metric_id=metric.id,
            min_severity=50.0,
            channels=[ChannelEnum.in_app, ChannelEnum.email]
        ))

        anomaly = Anomaly(
            metric_id=metric.id,
            date=date(2026, 3, 7),
            severity_score=88.0,
            type=AnomalyTypeEnum.spike,
            z_score=4.1,
            isolation_score=0.85,
            status=AnomalyStatusEnum.new,
            explanation_text="SMTP failure resilience test."
        )
        session.add(anomaly)
        await session.commit()

        # Mock smtplib.SMTP connection to raise ConnectionRefusedError
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("SMTP Connection Refused")):
            notifications = await evaluate_and_trigger_alerts_for_metric(session, metric.id)

            assert len(notifications) == 1
            assert notifications[0].anomaly_id == anomaly.id
            assert notifications[0].severity_score == 88.0
