import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

logger = structlog.get_logger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@driftline.io")
DEFAULT_ALERT_EMAIL = os.getenv("DEFAULT_ALERT_EMAIL", "admin@driftline.io")

def send_weekly_digest_email(
    workspace_id: int,
    metric_name: str,
    period_str: str,
    pdf_path: str,
    recipient_email: str | None = None
) -> bool:
    """
    Constructs and sends an HTML email with the weekly digest PDF attached.
    Wraps SMTP dispatch in an isolated try/except block to ensure failures log a warning and return False.
    """
    to_email = recipient_email or DEFAULT_ALERT_EMAIL

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Driftline Weekly Digest: {metric_name} ({period_str})"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1e293b;">
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0;">
          <h2 style="color: #0f766e; margin-top: 0;">Driftline Weekly Digest</h2>
          <p>Here is your weekly automated metric digest for <strong>{metric_name}</strong> covering <strong>{period_str}</strong> (Workspace #{workspace_id}).</p>
          <p>Please find the complete PDF report attached to this email.</p>
          <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;">
          <p style="font-size: 12px; color: #64748b;">This email was sent automatically by Driftline Anomaly & Forecast Engine.</p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    if os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_path))
                msg.attach(attach)
        except Exception as e:
            logger.warning(f"Failed to attach PDF file '{pdf_path}' to digest email: {e!s}")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USER and SMTP_PASSWORD:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Successfully sent weekly digest email for '{metric_name}' to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"SMTP dispatch failed for weekly digest email to {to_email}: {e!s}")
        return False

def send_immediate_alert_email(
    workspace_id: int,
    metric_name: str,
    anomaly_date: str,
    severity_score: float,
    explanation_text: str,
    recipient_email: str | None = None
) -> bool:
    """
    Constructs and sends an HTML email for an immediate high-severity anomaly alert.
    Wraps SMTP dispatch in an isolated try/except block to ensure failures log a warning and return False.
    """
    to_email = recipient_email or DEFAULT_ALERT_EMAIL

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"URGENT: High-Severity Anomaly Detected on {metric_name} ({anomaly_date})"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1e293b;">
        <div style="background-color: #fff1f2; padding: 20px; border-radius: 8px; border: 1px solid #fecdd3;">
          <h2 style="color: #e11d48; margin-top: 0;">High-Severity Anomaly Alert</h2>
          <p>An anomaly breaching your metric alert threshold was detected on <strong>{metric_name}</strong> (Workspace #{workspace_id}):</p>
          <ul>
            <li><strong>Date:</strong> {anomaly_date}</li>
            <li><strong>Severity Score:</strong> <span style="color: #be123c; fontweight: bold;">{severity_score:.1f} / 100</span></li>
          </ul>
          <div style="background-color: #ffffff; padding: 12px; border-radius: 4px; border-left: 4px solid #e11d48; margin: 15px 0;">
            <p style="margin: 0; font-size: 14px; color: #334155;"><strong>Driver Explanation:</strong> {explanation_text}</p>
          </div>
          <hr style="border: 0; border-top: 1px solid #fda4af; margin: 20px 0;">
          <p style="font-size: 12px; color: #9f1239;">Log into Driftline to review root-cause waterfall driver breakdown and record feedback.</p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USER and SMTP_PASSWORD:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Successfully sent immediate anomaly alert email for '{metric_name}' to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"SMTP dispatch failed for immediate alert email to {to_email}: {e!s}")
        return False
