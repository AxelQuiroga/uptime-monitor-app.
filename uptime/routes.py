from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from flask import Blueprint, request, jsonify
from .models import Target, Check, db

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
    days = request.args.get("days", 30, type=int)
    target = Target.query.get_or_404(target_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    row = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(total_checks), 0) AS total_checks,
                COALESCE(SUM(up_checks), 0) AS up_checks,
                ROUND(COALESCE(AVG(uptime_pct), 0), 2) AS uptime_pct,
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
        "total_checks": row[0],
        "up_checks": row[1],
        "uptime_pct": float(row[2]) if row[2] else 0,
        "avg_latency_ms": float(row[3]) if row[3] else 0,
        "max_latency_ms": float(row[4]) if row[4] else 0,
        "min_latency_ms": float(row[5]) if row[5] else 0,
    })


@api.route("/report/<int:target_id>/timeline")
def get_timeline(target_id):
    days = request.args.get("days", 7, type=int)
    target = Target.query.get_or_404(target_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.session.execute(
        text("""
            SELECT
                bucket,
                total_checks,
                up_checks,
                uptime_pct,
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
                "total_checks": row[1],
                "up_checks": row[2],
                "uptime_pct": float(row[3]) if row[3] else 0,
                "avg_latency_ms": float(row[4]) if row[4] else 0,
                "max_latency_ms": float(row[5]) if row[5] else 0,
                "min_latency_ms": float(row[6]) if row[6] else 0,
            }
            for row in rows
        ]
    })
