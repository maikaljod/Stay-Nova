"""Minimal outgoing-email helper (no external mail-service dependency).

In production, set MAIL_SERVER/MAIL_PORT/MAIL_USERNAME/MAIL_PASSWORD in the
environment and real emails are sent over SMTP (with STARTTLS by default).

In development (MAIL_SERVER unset, the default), emails are instead written
to instance/outbox/ as plain-text files and logged, so the verification /
password-reset flows work out of the box without a real mail server.
"""
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from flask import current_app


def send_email(to_address, subject, body):
    """Send a plain-text email, falling back to a dev outbox on failure."""
    cfg = current_app.config
    mail_server = cfg.get("MAIL_SERVER")

    if not mail_server:
        _write_dev_outbox(to_address, subject, body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg.get("MAIL_DEFAULT_SENDER", "no-reply@staynova.com")
    msg["To"] = to_address

    try:
        with smtplib.SMTP(mail_server, cfg.get("MAIL_PORT", 587), timeout=10) as smtp:
            if cfg.get("MAIL_USE_TLS", True):
                smtp.starttls()
            username = cfg.get("MAIL_USERNAME")
            password = cfg.get("MAIL_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(msg["From"], [to_address], msg.as_string())
    except Exception as exc:  # pragma: no cover - depends on external SMTP
        current_app.logger.error("Failed to send email to %s: %s", to_address, exc)
        _write_dev_outbox(to_address, subject, body)


def _write_dev_outbox(to_address, subject, body):
    outbox_dir = os.path.join(current_app.instance_path, "outbox")
    os.makedirs(outbox_dir, exist_ok=True)
    safe_addr = to_address.replace("@", "_at_").replace("/", "_")
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_addr}.txt"
    path = os.path.join(outbox_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"To: {to_address}\nSubject: {subject}\n\n{body}\n")
    current_app.logger.info("Dev-mode email written to %s (no MAIL_SERVER configured)", path)
