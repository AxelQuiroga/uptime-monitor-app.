"""
Dashboard — management interface. Requires direct access (no auth for now).
Serves:
  /        → Dashboard overview (manage targets + see status)
"""
from flask import Blueprint, render_template
from flask_login import login_required
from .models import Target, Check, AlertChannel

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/")
@login_required
def index():
    """Dashboard — full control panel with charts and management."""
    targets = Target.query.all()
    status_list = []
    for t in targets:
        last_check = (
            Check.query
            .filter_by(target_id=t.id)
            .order_by(Check.created_at.desc())
            .first()
        )
        is_up = last_check and last_check.is_up
        status_list.append({
            "id": t.id,
            "name": t.name,
            "url": t.url,
            "webhook_url": t.webhook_url,
            "interval_seconds": t.interval_seconds,
            "is_active": t.is_active,
            "status": "up" if is_up else "down",
            "last_check": last_check.to_dict() if last_check else None,
        })

    total = len(status_list)
    up_count = sum(1 for s in status_list if s["status"] == "up")

    # Alert channels
    channels = AlertChannel.query.all()
    targets = Target.query.all()

    return render_template(
        "dashboard.html",
        status=status_list,
        total=total,
        up_count=up_count,
        down_count=total - up_count,
        channels=[c.to_dict() for c in channels],
        targets=[t.to_dict() for t in targets],
    )
