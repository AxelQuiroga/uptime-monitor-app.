from flask import Blueprint, request, jsonify
from .models import Target, Check, db
from datetime import datetime, timezone

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
