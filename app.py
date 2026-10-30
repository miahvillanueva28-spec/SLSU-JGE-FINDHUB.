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
    raise RuntimeError("SECRET_KEY must be configured.")
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
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql+psycopg://"):
    database_url = database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)

if not database_url:
    if IS_VERCEL:
        raise RuntimeError("DATABASE_URL is missing.")
    database_url = f"sqlite:///{DATA_DIR / 'findhub.db'}"
    app.logger.warning("Using local SQLite for development only.")

if not database_url.startswith(("postgresql+psycopg2://", "sqlite:///")):
    raise RuntimeError("Unsupported DATABASE_URL.")

if IS_VERCEL and database_url.startswith("sqlite:///"):
    raise RuntimeError("SQLite not supported on Vercel. Use PostgreSQL.")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}
db = SQLAlchemy(app)

# ==================================================
# CLOUDINARY
# ==================================================
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()
USE_CLOUDINARY = bool(CLOUDINARY_URL)
if USE_CLOUDINARY:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)

# ==================================================
# BRANDING
# ==================================================
CAMPUS_LOGO = "https://www.slsu.edu.ph/wp-content/uploads/2023/05/Campuses/Campus-Logo/SLSU-JGE-Logo.png"
CAMPUS_PHOTO = "https://www.slsu.edu.ph/wp-content/uploads/elementor/thumbs/JGE%20bldg-q6759ky68kjrv7f9iklhioqfdjrgb6067ofnjh7qns.jpg"

# ==================================================
# MODELS
# ==================================================
def utcnow():
    return datetime.now(timezone.utc)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(20), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    incident_date = db.Column(db.Date, nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    contact_public = db.Column(db.Boolean, default=False, nullable=False)
    photo = db.Column(db.String(1000), nullable=True)
    status = db.Column(db.String(30), default="Open", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    claims = db.relationship("Claim", backref="report", cascade="all, delete-orphan", lazy=True)

class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"), nullable=False)
    claimant_name = db.Column(db.String(120), nullable=False)
    claimant_contact = db.Column(db.String(150), nullable=False)
    proof = db.Column(db.Text, nullable=False)
    proof_file = db.Column(db.String(1000), nullable=True)
    status = db.Column(db.String(30), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30), nullable=False, default="info")
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
# CONTEXT PROCESSORS
# ==================================================
@app.context_processor
def inject_global():
    return {
        "today": date.today(),
        "campus_logo": CAMPUS_LOGO,
        "campus_photo": CAMPUS_PHOTO,
        "admin_logged_in": bool(session.get("admin_logged_in")),
    }

@app.context_processor
def inject_notif_count():
    count = Notification.query.filter_by(is_read=False).count() if session.get("admin_logged_in") else 0
    return {"unread_notification_count": count}

# ==================================================
# HELPERS
# ==================================================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
REPORT_STATUSES = {"Open", "Pending Claim", "Returned", "Archived"}
CLAIM_STATUSES = {"Pending", "Approved", "Rejected"}

def create_notification(title, message, notification_type="info", report_id=None):
    notif = Notification(title=title, message=message, notification_type=notification_type,
                         report_id=report_id, is_read=False)
    db.session.add(notif)
    return notif

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as administrator first.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrap

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
    if not allowed_file(file_storage.filename):
        raise ValueError("Use PNG, JPG, JPEG, GIF, or WEBP.")
    if USE_CLOUDINARY:
        result = cloudinary.uploader.upload(file_storage, folder="slsu-jge-findhub", resource_type="image")
        url = result.get("secure_url")
        if not url:
            raise RuntimeError("Cloudinary upload failed.")
        return url
    if IS_VERCEL:
        raise RuntimeError("CLOUDINARY_URL not configured.")
    fn = f"{secrets.token_hex(12)}_{secure_filename(file_storage.filename)}"
    file_storage.save(UPLOAD_FOLDER / fn)
    return fn

def delete_photo(photo):
    if not photo or photo.startswith(("https://", "http://")) or IS_VERCEL:
        return
    path = UPLOAD_FOLDER / Path(photo).name
    if path.is_file():
        path.unlink()

def parse_date(val):
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

def form_val(name, default=""):
    return (request.form.get(name, default) or "").strip()

# ==================================================
# HOME
# ==================================================
@app.route("/")
def home():
    q = request.args.get("q", "").strip()[:100]
    t = request.args.get("type", "").strip()
    s = request.args.get("status", "").strip()
    sort = request.args.get("sort", "newest").strip()
    query = Report.query
    if t in {"Lost", "Found"}:
        query = query.filter(Report.report_type == t)
    if s in REPORT_STATUSES:
        query = query.filter(Report.status == s)
    if q:
        qs = f"%{q}%"
        query = query.filter(or_(Report.item_name.ilike(qs), Report.description.ilike(qs), Report.location.ilike(qs)))
    if sort == "oldest":
        query = query.order_by(Report.created_at.asc(), Report.id.asc())
    elif sort == "name":
        query = query.order_by(Report.item_name.asc(), Report.id.asc())
    else:
        query = query.order_by(Report.created_at.desc(), Report.id.desc())
    reports = query.all()
    stats = {
        "total": Report.query.count(),
        "lost": Report.query.filter_by(report_type="Lost").count(),
        "found": Report.query.filter_by(report_type="Found").count(),
        "open": Report.query.filter_by(status="Open").count(),
    }
    return render_template("home.html", reports=reports, stats=stats,
                           search_performed=bool(q or t or s), query=q,
                           selected_type=t, selected_status=s, selected_sort=sort)

# ==================================================
# NEW REPORT
# ==================================================
@app.route("/report/new", methods=["GET", "POST"])
def new_report():
    if request.method != "POST":
        return render_template("report_form.html")
    rt = form_val("report_type")
    name = form_val("item_name")
    cat = form_val("category")
    desc = form_val("description")
    loc = form_val("location")
    dt = parse_date(form_val("incident_date"))
    cname = form_val("contact_name")
    contact = form_val("contact")
    pub = request.form.get("contact_public") in {"1", "true", "on", "yes"}
    if rt not in {"Lost", "Found"}:
        flash("Select Lost or Found.", "danger")
        return redirect(url_for("new_report"))
    if not all([name, desc, loc, dt, contact]):
        flash("Complete all required fields.", "danger")
        return redirect(url_for("new_report"))
    if dt > date.today():
        flash("Date cannot be in the future.", "danger")
        return redirect(url_for("new_report"))
    photo = None
    try:
        photo = save_photo(request.files.get("photo"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("new_report"))
    rep = Report(
        report_type=rt, item_name=name, category=cat or "General",
        description=desc, location=loc, incident_date=dt,
        contact_name=cname or "Not provided", contact=contact,
        contact_public=pub, photo=photo, status="Open"
    )
    try:
        db.session.add(rep)
        db.session.flush()
        create_notification(f"New {rt} Report", f"{name} was submitted.", "info", rep.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_photo(photo)
        flash("Failed to save report.", "danger")
        return redirect(url_for("new_report"))
    flash("Report submitted successfully!", "success")
    return redirect(url_for("report_detail", report_id=rep.id))

# ==================================================
# REPORT DETAIL
# ==================================================
@app.route("/report/<int:report_id>")
def report_detail(report_id):
    report = db.get_or_404(Report, report_id)
    nid = request.args.get("notification_id", type=int)
    if nid and session.get("admin_logged_in"):
        notif = Notification.query.get(nid)
        if notif and not notif.is_read:
            try:
                notif.is_read = True
                db.session.commit()
            except Exception:
                db.session.rollback()
    return render_template("report_detail.html", report=report)

# ==================================================
# SUBMIT CLAIM — WITH PROOF PHOTO
# ==================================================
@app.route("/report/<int:report_id>/claim", methods=["POST"])
def submit_claim(report_id):
    report = db.get_or_404(Report, report_id)
    if report.status in {"Returned", "Archived"}:
        flash("No longer accepting claims.", "warning")
        return redirect(url_for("report_detail", report_id=report.id))
    cname = form_val("claimant_name")
    ccontact = form_val("claimant_contact")
    proof = form_val("proof")
    if not all([cname, ccontact, proof]):
        flash("Complete all required fields.", "danger")
        return redirect(url_for("report_detail", report_id=report.id))
    saved_proof = None
    try:
        saved_proof = save_photo(request.files.get("proof_photo"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("report_detail", report_id=report.id))
    except Exception:
        app.logger.exception("Proof photo upload failed")
        flash("Photo upload failed, but claim was submitted.", "warning")
    claim = Claim(
        report_id=report.id,
        claimant_name=cname,
        claimant_contact=ccontact,
        proof=proof,
        proof_file=saved_proof,
        status="Pending"
    )
    try:
        db.session.add(claim)
        report.status = "Pending Claim"
        db.session.flush()
        create_notification(
            "
