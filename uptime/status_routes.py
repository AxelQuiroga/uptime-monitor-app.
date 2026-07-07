"""
Public status page — read-only, no auth.
Serves:
  /            → Status overview (all targets, current state)
  /target/<id> → Per-target detail with uptime chart
"""
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, abort
from sqlalchemy import text

from .models import Target, Check, db

status_page = Blueprint("status_page", __name__)


@status_page.route("/")
def index():
    """Public status overview — all active targets with current status + uptime %."""
    targets = Target.query.filter_by(is_active=True).all()
    status_list = []
    for t in targets:
        last_check = (
            Check.query
            .filter_by(target_id=t.id)
            .order_by(Check.created_at.desc())
            .first()
        )
        is_up = last_check and last_check.is_up
        # Get uptime % from hourly_checks (30d)
        uptime_pct = _get_uptime_pct(t.id, 30)
        status_list.append({
            "id": t.id,
            "name": t.name,
            "url": t.url,
            "status": "up" if is_up else "down",
            "uptime_pct": uptime_pct,
            "last_check": last_check.to_dict() if last_check else None,
        })

    total = len(status_list)
    up_count = sum(1 for s in status_list if s["status"] == "up")

    return render_template(
        "status_public.html",
        status=status_list,
        total=total,
        up_count=up_count,
        down_count=total - up_count,
    )


@status_page.route("/target/<int:target_id>")
def detail(target_id):
    """Public target detail — latency chart, uptime stats, recent checks."""
    target = db.session.get(Target, target_id)
    if not target:
        abort(404)

    last_check = (
        Check.query
        .filter_by(target_id=target.id)
        .order_by(Check.created_at.desc())
        .first()
    )
    is_up = last_check and last_check.is_up

    return render_template(
        "status_detail.html",
        target=target,
        last_check=last_check,
        status="up" if is_up else "down",
    )


def _get_uptime_pct(target_id: int, days: int = 30) -> float:
    """Get uptime percentage for a target from hourly_checks (fallback 0)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        row = db.session.execute(
            text("""
                SELECT
                    CASE WHEN SUM(total_checks) > 0
                        THEN ROUND(SUM(up_checks)::numeric / SUM(total_checks) * 100, 2)
                        ELSE 0
                    END AS uptime_pct
                FROM hourly_checks
                WHERE target_id = :tid AND bucket >= :since
            """),
            {"tid": target_id, "since": since}
        ).fetchone()
        return float(row[0]) if row and row[0] else 0.0
    except Exception:
        # hourly_checks might not exist yet
        return 0.0
