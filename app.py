import os
import csv
import io
import hmac
import secrets
from pathlib import Path
from datetime import date, datetime, timezone
from functools import wraps

import cloudinary
import cloudinary.uploader
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
    make_response,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.utils import secure_filename

# ==================================================
# APP CONFIGURATION
# ==================================================
BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = os.environ.get("VERCEL", "").lower() == "1"
DATA_DIR = Path(
    os.environ.get(
        "DATA_DIR",
        "/tmp/findhub" if IS_VERCEL else str(BASE_DIR / "data"),
    )
).resolve()
UPLOAD_FOLDER = DATA_DIR / "uploads"
if not IS_VERCEL:
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY", "").strip()
if IS_VERCEL and not secret_key:
    raise RuntimeError(
        "SECRET_KEY must be configured in Vercel Environment Variables."
    )
app.config["SECRET_KEY"] = secret_key or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", "true").lower() == "true"
)

# ==================================================
# DATABASE CONFIGURATION
# ==================================================
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql+psycopg2://", 1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )
elif database_url.startswith("postgresql+psycopg://"):
    database_url = database_url.replace(
        "postgresql+psycopg://", "postgresql+psycopg2://", 1
    )

if not database_url:
    if IS_VERCEL:
        raise RuntimeError(
            "DATABASE_URL is missing. Configure PostgreSQL and add "
            "DATABASE_URL in Vercel Environment Variables."
        )
    database_url = f"sqlite:///{DATA_DIR / 'findhub.db'}"
    app.logger.warning(
        "DATABASE_URL is missing. Using local SQLite for development only."
    )

if not database_url.startswith(("postgresql+psycopg2://", "sqlite:///")):
    raise RuntimeError(
        "Unsupported DATABASE_URL. Use PostgreSQL or SQLite locally."
    )

if IS_VERCEL and database_url.startswith("sqlite:///"):
    raise RuntimeError(
        "SQLite is not suitable for persistent Vercel production data. "
        "Configure PostgreSQL using DATABASE_URL."
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
db = SQLAlchemy(app)

# ==================================================
# CLOUDINARY PHOTO STORAGE
# ==================================================
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()
USE_CLOUDINARY = bool(CLOUDINARY_URL)
if USE_CLOUDINARY:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
if IS_VERCEL and not USE_CLOUDINARY:
    app.logger.warning(
        "CLOUDINARY_URL is missing. Photo uploads will not work on Vercel."
    )

# ==================================================
# WEBSITE BRANDING
# ==================================================
CAMPUS_LOGO = (
    "https://www.slsu.edu.ph/wp-content/uploads/2023/05/"
    "Campuses/Campus-Logo/SLSU-JGE-Logo.png"
)
CAMPUS_PHOTO = (
    "https://www.slsu.edu.ph/wp-content/uploads/"
    "elementor/thumbs/JGE%20bldg-q6759ky68kjrv7f9iklhioqfdjrgb6067ofnjh7qns.jpg"
)

# ==================================================
# DATABASE MODELS
# ==================================================
def utcnow():
    return datetime.now(timezone.utc)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(20), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    incident_date = db.Column(db.Date, nullable=False)
    contact_name = db.Column(db.String(120), nullable=False, default="Anonymous")
    contact = db.Column(db.String(150), nullable=False)
    contact_public = db.Column(db.Boolean, default=False, nullable=False)
    photo = db.Column(db.String(1000), nullable=True)
    status = db.Column(db.String(30), default="Open", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    claims = db.relationship(
        "Claim", backref="report", cascade="all, delete-orphan", lazy=True
    )

class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer, db.ForeignKey("report.id"), nullable=False
    )
    claimant_name = db.Column(db.String(120), nullable=False)
    claimant_contact = db.Column(db.String(150), nullable=False)
    proof = db.Column(db.Text, nullable=False)
    proof_photo = db.Column(db.String(1000), nullable=True)  # ✅ Added: proof photo
    status = db.Column(db.String(30), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.String(30), nullable=False, default="info"
    )
    report_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class DeletedReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_report_id = db.Column(db.Integer, nullable=False)
    report_type = db.Column(db.String(20), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    incident_date = db.Column(db.Date, nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    status_when_deleted = db.Column(db.String(30), nullable=False)
    photo = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    deleted_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    deleted_by = db.Column(db.String(120), nullable=True)

with app.app_context():
    db.create_all()

# ==================================================
# TEMPLATE CONTEXT
# ==================================================
@app.context_processor
def inject_global_template_values():
    return {
        "today": date.today(),
        "campus_logo": CAMPUS_LOGO,
        "campus_photo": CAMPUS_PHOTO,
        "admin_logged_in": bool(session.get("admin_logged_in")),
    }

@app.context_processor
def inject_notification_count():
    count = 0
    if session.get("admin_logged_in"):
        count = Notification.query.filter_by(is_read=False).count()
    return {"unread_notification_count": count}

# ==================================================
# CONSTANTS AND HELPERS
# ==================================================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
REPORT_STATUSES = {"Open", "Pending Claim", "Returned", "Archived"}
CLAIM_STATUSES = {"Pending", "Approved", "Rejected"}

def create_notification(title, message, notification_type="info", report_id=None):
    notification = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        report_id=report_id,
        is_read=False,
    )
    db.session.add(notification)
    return notification

def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as an administrator first.", "warning")
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)
    return wrapped_view

def allowed_file(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def photo_src(photo):
    if not photo:
        return None
    if photo.startswith(("https://", "http://")):
        return photo
    return url_for("uploaded_photo", filename=photo)

@app.context_processor
def inject_photo_helper():
    return {"photo_src": photo_src}

def save_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    original_name = secure_filename(file_storage.filename)
    if not original_name or not allowed_file(original_name):
        raise ValueError("Use a PNG, JPG, JPEG, GIF, or WEBP image.")
    if not USE_CLOUDINARY:
        if IS_VERCEL:
            raise RuntimeError(
                "Photo storage is not configured. Set CLOUDINARY_URL "
                "in Vercel Environment Variables."
            )
        filename = f"{secrets.token_hex(12)}_{original_name}"
        file_storage.save(UPLOAD_FOLDER / filename)
        return filename
    result = cloudinary.uploader.upload(
        file_storage,
        folder="slsu-jge-findhub",
        resource_type="image",
    )
    photo_url = result.get("secure_url")
    if not photo_url:
        raise RuntimeError("Cloudinary did not return a secure photo URL.")
    return photo_url

def delete_photo(photo):
    if not photo or photo.startswith(("https://", "http://")):
        return
    if IS_VERCEL:
        return
    filename = Path(photo).name
    path = UPLOAD_FOLDER / filename
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        app.logger.exception("Unable to delete local photo")

def parse_incident_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

def get_report_form_value(name, default=""):
    return (request.form.get(name, default) or "").strip()

# ==================================================
# HOME AND SEARCH
# ==================================================
@app.route("/")
def home():
    query = request.args.get("q", "").strip()[:100]
    report_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "newest").strip()

    search_performed = bool(query or report_type or status)
    reports_query = Report.query

    if report_type in {"Lost", "Found"}:
        reports_query = reports_query.filter(Report.report_type == report_type)
    if status in REPORT_STATUSES:
        reports_query = reports_query.filter(Report.status == status)
    if query:
        search_term = f"%{query}%"
        reports_query = reports_query.filter(
            or_(
                Report.item_name.ilike(search_term),
                Report.description.ilike(search_term),
                Report.location.ilike(search_term),
            )
        )

    if sort == "oldest":
        reports_query = reports_query.order_by(
            Report.created_at.asc(), Report.id.asc()
        )
    elif sort == "name":
        reports_query = reports_query.order_by(
            Report.item_name.asc(), Report.id.asc()
        )
    else:
        sort = "newest"
        reports_query = reports_query.order_by(
            Report.created_at.desc(), Report.id.desc()
        )

    reports = reports_query.all()

    total_reports = Report.query.count()
    total_lost = Report.query.filter_by(report_type="Lost").count()
    total_found = Report.query.filter_by(report_type="Found").count()
    total_open = Report.query.filter_by(status="Open").count()

    stats = {
        "total": total_reports,
        "lost": total_lost,
        "found": total_found,
        "open": total_open,
    }

    return render_template(
        "home.html",
        reports=reports,
        stats=stats,
        total_reports=total_reports,
        total_lost=total_lost,
        total_found=total_found,
        total_open=total_open,
        search_performed=search_performed,
        query=query,
        selected_type=report_type,
        selected_status=status,
        selected_sort=sort,
    )

# ==================================================
# CREATE A REPORT
# ==================================================
@app.route("/report/new", methods=["GET", "POST"])
def new_report():
    if request.method == "POST":
        report_type = get_report_form_value("report_type")
        item_name = get_report_form_value("item_name")
        category = get_report_form_value("category") or "General"
        description = get_report_form_value("description")
        location = get_report_form_value("location")
        incident_date = parse_incident_date(
            get_report_form_value("incident_date")
        )
        contact_name = get_report_form_value("contact_name")
        contact = get_report_form_value("contact")
        contact_public = request.form.get("contact_public") in {
            "1", "true", "on", "yes"
        }

        if report_type not in {"Lost", "Found"}:
            flash("Please select Lost or Found.", "danger")
            return redirect(url_for("new_report"))
        if not all([item_name, description, location, incident_date, contact]):
            flash("Please complete all required fields.", "danger")
            return redirect(url_for("new_report"))
        if incident_date > date.today():
            flash("The lost or found date cannot be in the future.", "danger")
            return redirect(url_for("new_report"))
        if len(item_name) > 150:
            flash("Item name is too long.", "danger")
            return redirect(url_for("new_report"))
        if len(location) > 200:
            flash("Location is too long.", "danger")
            return redirect(url_for("new_report"))
        if len(contact) > 150:
            flash("Contact details are too long.", "danger")
            return redirect(url_for("new_report"))
        if len(contact_name) > 120:
            flash("Your name is too long.", "danger")
            return redirect(url_for("new_report
