"""Slack + email notifications."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

from ..settings import SignalSettings, get_settings


def send_slack_message(text: str, settings: SignalSettings | None = None) -> bool:
    s = settings or get_settings()
    if not s.slack_webhook_url:
        return False
    r = requests.post(
        s.slack_webhook_url,
        json={"text": text},
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    return r.status_code < 400


def send_email(
    subject: str,
    body: str,
    *,
    to: str | None = None,
    settings: SignalSettings | None = None,
) -> bool:
    s = settings or get_settings()
    dest = to or s.digest_email_to or s.alert_email_to
    if not (s.smtp_host and s.alert_email_from and dest):
        return False
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = s.alert_email_from
    msg["To"] = dest
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
            if s.smtp_user and s.smtp_password:
                server.starttls()
                server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.alert_email_from, [dest], msg.as_string())
        return True
    except Exception:
        return False
