from flask import Blueprint, render_template
from .models import Target, Check

dashboard = Blueprint("dashboard", __name__)

@dashboard.route("/")
def index():
    targets = Target.query.filter_by(is_active=True).all()
    status_list = []
    for t in targets:
        last_check = Check.query.filter_by(target_id=t.id).first()
        is_up = last_check and last_check.is_up
        status_list.append({
            "id": t.id,
            "name": t.name,
            "url": t.url,
            "status": "up" if is_up else "down",
            "last_check": last_check.to_dict() if last_check else None,
        })
    return render_template("dashboard.html", status=status_list)
