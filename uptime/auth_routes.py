"""Auth routes — single-password admin login via Flask-Login."""
import os
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from .models import AdminUser

auth = Blueprint("auth", __name__)

# Cache the admin password hash at module level (avoids re-hashing on every request)
_admin_password_hash = None


def _get_admin_hash():
    global _admin_password_hash
    if _admin_password_hash is None:
        pw = os.getenv("ADMIN_PASSWORD", "")
        if pw:
            _admin_password_hash = generate_password_hash(pw)
    return _admin_password_hash


def _is_safe_url(target):
    """Validate that a redirect target stays within the app (prevents open redirect)."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@auth.route("/login", methods=["GET"])
def login_page():
    """Render login form. Already logged in → redirect to dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    """Authenticate against ADMIN_PASSWORD env var."""
    password = request.form.get("password", "")
    admin_hash = _get_admin_hash()

    if not admin_hash:
        return render_template("login.html", error="ADMIN_PASSWORD not configured")

    if check_password_hash(admin_hash, password):
        login_user(AdminUser(), remember=False)
        session.permanent = False
        next_page = request.args.get("next")
        if next_page and not _is_safe_url(next_page):
            next_page = None
        return redirect(next_page or url_for("dashboard.index"))

    return render_template("login.html", error="Incorrect password")


@auth.route("/logout")
def logout():
    """Log out and redirect to login page."""
    logout_user()
    return redirect(url_for("auth.login_page"))


# ── API-level auth check for non-public endpoints ─────────────────────────


def api_login_required(view):
    """Decorator: requires active session, returns 401 JSON for API routes."""
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)
    return wrapped
