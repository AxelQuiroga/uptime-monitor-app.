from datetime import datetime, timezone
from .database import db

class Target(db.Model):
    __tablename__ = "targets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    webhook_url = db.Column(db.String(500), nullable=True)
    interval_seconds = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    checks = db.relationship("Check", backref="target", lazy="dynamic",
                            order_by="Check.created_at.desc()")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "webhook_url": self.webhook_url,
            "interval_seconds": self.interval_seconds,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class AlertChannel(db.Model):
    """Notification channel — slack, discord, or email.

    - target_id=NULL  → global channel (receives ALL alerts)
    - target_id=<id>  → per-target channel
    """
    __tablename__ = "alert_channels"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)        # slack | discord | email
    value = db.Column(db.String(500), nullable=False)       # webhook URL or email addr
    name = db.Column(db.String(100), nullable=True)         # friendly label
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    target = db.relationship("Target", backref=db.backref("alert_channels", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "value": self.value,
            "name": self.name,
            "target_id": self.target_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Check(db.Model):
    __tablename__ = "checks"

    id = db.Column(db.Integer, primary_key=True)
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"), nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    latency_ms = db.Column(db.Float, nullable=True)
    is_up = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms, 2) if self.latency_ms else None,
            "is_up": self.is_up,
            "error": self.error_message,
            "checked_at": self.created_at.isoformat() if self.created_at else None,
        }
