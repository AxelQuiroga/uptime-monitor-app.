"""
Alert dispatcher — routes alerts to all active channels.
Called by uptime.notifier.send_alert().
"""
import logging

from ..models import AlertChannel, Target, Check

log = logging.getLogger("notifier")


def dispatch(target: Target, check: Check, previous_up: bool | None) -> None:
    """Send alert to ALL active channels for this target + global channels."""
    from .slack import send_slack
    from .discord import send_discord
    from .emailer import send_email

    channels = (
        AlertChannel.query
        .filter(
            (AlertChannel.target_id == target.id) | (AlertChannel.target_id.is_(None)),
            AlertChannel.is_active.is_(True),
        )
        .all()
    )

    if not channels:
        return

    for ch in channels:
        try:
            if ch.type == "slack":
                send_slack(ch.value, target, check, previous_up)
            elif ch.type == "discord":
                send_discord(ch.value, target, check, previous_up)
            elif ch.type == "email":
                send_email(ch.value, target, check, previous_up)
            log.info("Alert sent via %s → %s", ch.type, ch.value[:40])
        except Exception as e:
            log.error("Alert FAILED via %s: %s", ch.type, e)
