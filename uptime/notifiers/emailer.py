"""
Email notifier — sends alerts via SMTP.
Requires env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
Uses Python's stdlib smtplib — zero additional dependencies.
"""
import os
import smtplib
from email.message import EmailMessage
from ..models import Target, Check


def send_email(to_addr: str, target: Target, check: Check, previous_up: bool | None) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        return  # SMTP not configured, skip silently

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user)

    status, _, title, _ = _build_meta(target, check, previous_up)

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = title

    body = (
        f"Target: {target.name}\n"
        f"URL: {target.url}\n"
        f"Status: {status}\n"
        f"Status Code: {check.status_code or 'N/A'}\n"
        f"Latency: {f'{check.latency_ms:.0f}ms' if check.latency_ms else 'N/A'}\n"
        f"Error: {check.error_message or 'None'}\n"
        f"Time: {check.created_at.isoformat() if check.created_at else 'N/A'}\n"
    )
    msg.set_content(body)

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)


def _build_meta(target, check, previous_up):
    if previous_up is None:
        return "DOWN", "red", f"[DOWN] {target.name} (nuevo target)", "FIRST_CHECK_DOWN"
    if previous_up and not check.is_up:
        return "DOWN", "red", f"[DOWN] {target.name}", "DOWN"
    if not previous_up and check.is_up:
        return "UP", "green", f"[UP] {target.name} — recovered", "UP"
    return "UP", "green", f"[UP] {target.name}", "UP"
