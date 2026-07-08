from datetime import datetime, timezone, timedelta
from sqlalchemy import text, desc

from flask import Blueprint, request, jsonify
from .models import Target, Check, AlertChannel, db

api = Blueprint("api", __name__, url_prefix="/api")

@api.route("/targets", methods=["GET"])
def list_targets():
    targets = Target.query.all()
    return jsonify([t.to_dict() for t in targets])

@api.route("/targets", methods=["POST"])
def create_target():
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "url is required"}), 400
    existing = Target.query.filter_by(url=data["url"]).first()
    if existing:
        return jsonify({"error": "target already exists", "target": existing.to_dict()}), 409
    target = Target(
        name=data.get("name", data["url"]),
        url=data["url"],
        webhook_url=data.get("webhook_url"),
        interval_seconds=data.get("interval_seconds", 30),
    )
    db.session.add(target)
    db.session.commit()
    return jsonify(target.to_dict()), 201

@api.route("/targets/<int:target_id>", methods=["DELETE"])
def delete_target(target_id):
    target = Target.query.get_or_404(target_id)
    Check.query.filter_by(target_id=target.id).delete()
    db.session.delete(target)
    db.session.commit()
    return jsonify({"message": "deleted"})

# ─── AlertChannels CRUD ───────────────────────────────────────────────────


@api.route("/alert-channels", methods=["GET"])
def list_alert_channels():
    channels = AlertChannel.query.all()
    return jsonify([c.to_dict() for c in channels])


@api.route("/alert-channels", methods=["POST"])
def create_alert_channel():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    ch_type = data.get("type")
    if ch_type not in ("slack", "discord", "email"):
        return jsonify({"error": "type must be slack, discord, or email"}), 400
    if not data.get("value"):
        return jsonify({"error": "value (webhook URL or email) is required"}), 400

    # Validate target_id if provided
    target_id = data.get("target_id")
    if target_id is not None:
        target = Target.query.get(target_id)
        if not target:
            return jsonify({"error": "target not found"}), 404

    channel = AlertChannel(
        type=ch_type,
        value=data["value"],
        name=data.get("name", ""),
        target_id=target_id,
        is_active=data.get("is_active", True),
    )
    db.session.add(channel)
    db.session.commit()
    return jsonify(channel.to_dict()), 201


@api.route("/alert-channels/<int:channel_id>", methods=["PUT"])
def update_alert_channel(channel_id):
    channel = AlertChannel.query.get_or_404(channel_id)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if "type" in data:
        if data["type"] not in ("slack", "discord", "email"):
            return jsonify({"error": "type must be slack, discord, or email"}), 400
        channel.type = data["type"]
    if "value" in data:
        channel.value = data["value"]
    if "name" in data:
        channel.name = data["name"]
    if "target_id" in data:
        if data["target_id"] is not None:
            if not Target.query.get(data["target_id"]):
                return jsonify({"error": "target not found"}), 404
        channel.target_id = data["target_id"]
    if "is_active" in data:
        channel.is_active = data["is_active"]

    db.session.commit()
    return jsonify(channel.to_dict())


@api.route("/alert-channels/<int:channel_id>", methods=["DELETE"])
def delete_alert_channel(channel_id):
    channel = AlertChannel.query.get_or_404(channel_id)
    db.session.delete(channel)
    db.session.commit()
    return jsonify({"message": "deleted"})


@api.route("/alert-channels/<int:channel_id>/toggle", methods=["PATCH"])
def toggle_alert_channel(channel_id):
    channel = AlertChannel.query.get_or_404(channel_id)
    channel.is_active = not channel.is_active
    db.session.commit()
    return jsonify(channel.to_dict())


# ───────────────────────────────────────────────────────────────────────────


@api.route("/status", methods=["GET"])
def get_status():
    targets = Target.query.filter_by(is_active=True).all()
    result = []
    for t in targets:
        last_check = Check.query.filter_by(target_id=t.id).first()
        status = "up" if last_check and last_check.is_up else "down"
        result.append({"id": t.id, "name": t.name, "url": t.url, "status": status, "last_check": last_check.to_dict() if last_check else None})
    return jsonify(result)

@api.route("/history/<int:target_id>", methods=["GET"])
def get_history(target_id):
    limit = request.args.get("limit", 20, type=int)
    checks = Check.query.filter_by(target_id=target_id).limit(limit).all()
    return jsonify([c.to_dict() for c in checks])


@api.route("/report/<int:target_id>")
def get_report(target_id):
    """Aggregate report from hourly_checks. Uptime = SUM(up) / SUM(total)."""
    days = min(request.args.get("days", 30, type=int), 90)
    target = Target.query.get_or_404(target_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    row = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(total_checks), 0) AS total_checks,
                COALESCE(SUM(up_checks), 0) AS up_checks,
                CASE WHEN SUM(total_checks) > 0
                    THEN ROUND(SUM(up_checks)::numeric / SUM(total_checks) * 100, 2)
                    ELSE 0
                END AS uptime_pct,
                ROUND(COALESCE(AVG(avg_latency), 0), 2) AS avg_latency,
                ROUND(COALESCE(MAX(max_latency), 0), 2) AS max_latency,
                ROUND(COALESCE(MIN(min_latency), 0), 2) AS min_latency
            FROM hourly_checks
            WHERE target_id = :tid AND bucket >= :since
        """),
        {"tid": target_id, "since": since}
    ).fetchone()

    return jsonify({
        "target_id": target_id,
        "target_name": target.name,
        "target_url": target.url,
        "days": days,
        "since": since.isoformat(),
        "total_checks": int(row[0]),
        "up_checks": int(row[1]),
        "uptime_pct": float(row[2]) if row[2] else 0,
        "avg_latency_ms": float(row[3]) if row[3] else 0,
        "max_latency_ms": float(row[4]) if row[4] else 0,
        "min_latency_ms": float(row[5]) if row[5] else 0,
    })


@api.route("/report/<int:target_id>/timeline")
def get_timeline(target_id):
    """Per-bucket timeline from hourly_checks."""
    days = min(request.args.get("days", 7, type=int), 90)
    target = Target.query.get_or_404(target_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.session.execute(
        text("""
            SELECT
                bucket,
                total_checks,
                up_checks,
                CASE WHEN total_checks > 0
                    THEN ROUND(up_checks::numeric / total_checks * 100, 2)
                    ELSE 0
                END AS uptime_pct,
                avg_latency,
                max_latency,
                min_latency
            FROM hourly_checks
            WHERE target_id = :tid AND bucket >= :since
            ORDER BY bucket ASC
        """),
        {"tid": target_id, "since": since}
    ).fetchall()

    return jsonify({
        "target_id": target_id,
        "target_name": target.name,
        "days": days,
        "timeline": [
            {
                "bucket": row[0].isoformat() if row[0] else None,
                "total_checks": int(row[1]),
                "up_checks": int(row[2]),
                "uptime_pct": float(row[3]) if row[3] else 0,
                "avg_latency_ms": float(row[4]) if row[4] else 0,
                "max_latency_ms": float(row[5]) if row[5] else 0,
                "min_latency_ms": float(row[6]) if row[6] else 0,
            }
            for row in rows
        ]
    })


# ─── Public API (read-only, no auth) ───────────────────────────────────────


@api.route("/public/status")
def public_status():
    """Public status JSON — all active targets with current state + uptime %."""
    targets = Target.query.filter_by(is_active=True).all()
    result = []
    for t in targets:
        last_check = (
            Check.query
            .filter_by(target_id=t.id)
            .order_by(Check.created_at.desc())
            .first()
        )
        is_up = last_check and last_check.is_up
        uptime_pct = _get_uptime_pct(t.id, 30)
        result.append({
            "id": t.id,
            "name": t.name,
            "url": t.url,
            "status": "up" if is_up else "down",
            "uptime_pct": uptime_pct,
            "last_check": last_check.to_dict() if last_check else None,
        })
    return jsonify(result)


@api.route("/public/report/<int:target_id>")
def public_report(target_id):
    """Public report — aggregate + timeline + recent checks, for Chart.js."""
    days = min(request.args.get("days", 30, type=int), 90)
    target = db.session.get(Target, target_id)
    if not target:
        return jsonify({"error": "target not found"}), 404

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Aggregate
    row = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(total_checks), 0) AS total_checks,
                COALESCE(SUM(up_checks), 0) AS up_checks,
                CASE WHEN SUM(total_checks) > 0
                    THEN ROUND(SUM(up_checks)::numeric / SUM(total_checks) * 100, 2)
                    ELSE 0
                END AS uptime_pct,
                ROUND(COALESCE(AVG(avg_latency), 0), 2) AS avg_latency,
                ROUND(COALESCE(MAX(max_latency), 0), 2) AS max_latency,
                ROUND(COALESCE(MIN(min_latency), 0), 2) AS min_latency
            FROM hourly_checks
            WHERE target_id = :tid AND bucket >= :since
        """),
        {"tid": target_id, "since": since}
    ).fetchone()

    return jsonify({
        "target_id": target_id,
        "target_name": target.name,
        "target_url": target.url,
        "days": days,
        "total_checks": int(row[0]),
        "up_checks": int(row[1]),
        "uptime_pct": float(row[2]) if row[2] else 0,
        "avg_latency_ms": float(row[3]) if row[3] else 0,
        "max_latency_ms": float(row[4]) if row[4] else 0,
        "min_latency_ms": float(row[5]) if row[5] else 0,
        "timeline": _get_timeline_data(target_id, since),
        "recent_checks": _get_recent_checks(target_id, 20),
    })


def _get_uptime_pct(target_id: int, days: int = 30) -> float:
    """Helper: uptime % from hourly_checks (fallback 0 on error)."""
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
        return 0.0


def _get_timeline_data(target_id: int, since: datetime) -> list:
    """Helper: per-bucket timeline for Chart.js (epoch millis for x-axis)."""
    try:
        rows = db.session.execute(
            text("""
                SELECT
                    bucket,
                    CASE WHEN total_checks > 0
                        THEN ROUND(up_checks::numeric / total_checks * 100, 2)
                        ELSE 0
                    END AS uptime_pct,
                    avg_latency,
                    max_latency
                FROM hourly_checks
                WHERE target_id = :tid AND bucket >= :since
                ORDER BY bucket ASC
            """),
            {"tid": target_id, "since": since}
        ).fetchall()
        return [
            {
                "bucket": int(row[0].timestamp() * 1000),  # epoch millis for Chart.js
                "uptime_pct": float(row[1]) if row[1] else 0,
                "avg_latency_ms": float(row[2]) if row[2] else 0,
                "max_latency_ms": float(row[3]) if row[3] else 0,
            }
            for row in rows
        ]
    except Exception:
        return []


def _get_recent_checks(target_id: int, limit: int = 20) -> list:
    """Helper: last N raw checks."""
    checks = (
        Check.query
        .filter_by(target_id=target_id)
        .order_by(Check.created_at.desc())
        .limit(limit)
        .all()
    )
    return [c.to_dict() for c in checks]
