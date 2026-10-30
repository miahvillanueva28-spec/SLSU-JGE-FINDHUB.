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

# ========== DELETED REPORTS HISTORY MODEL ==========
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
# ========================================================

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
        category = get_report_form_value("category")
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
            return redirect(url_for("new_report"))

        stored_contact_name = contact_name or "Not provided"
        saved_photo = None

        try:
            saved_photo = save_photo(request.files.get("photo"))
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("new_report"))
        except Exception:
            app.logger.exception("Photo upload failed")
            flash(
                "Photo upload failed. Check your Cloudinary configuration.",
                "danger",
            )
            return redirect(url_for("new_report"))

        report = Report(
            report_type=report_type,
            item_name=item_name,
            category=category or "General",
            description=description,
            location=location,
            incident_date=incident_date,
            contact_name=stored_contact_name,
            contact=contact,
            contact_public=contact_public,
            photo=saved_photo,
            status="Open",
        )

        try:
            db.session.add(report)
            db.session.flush()
            create_notification(
                title="New Lost and Found Report",
                message=(
                    f"A new {report.report_type.lower()} report "
                    f"was submitted: {report.item_name}."
                ),
                notification_type="report",
                report_id=report.id,
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Unable to save report")
            delete_photo(saved_photo)
            flash("Unable to save your report. Please try again.", "danger")
            return redirect(url_for("new_report"))

        flash("Your report was submitted successfully!", "success")
        return redirect(url_for("report_detail", report_id=report.id))

    return render_template("report_form.html")

# ==================================================
# REPORT DETAILS
# ==================================================
@app.route("/report/<int:report_id>")
def report_detail(report_id):
    report = db.get_or_404(Report, report_id)
    notification_id = request.args.get("notification_id", type=int)
    if notification_id and session.get("admin_logged_in"):
        notification = Notification.query.get(notification_id)
        if notification and not notification.is_read:
            try:
                notification.is_read = True
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Unable to auto-mark notification as read")
    return render_template("report_detail.html", report=report)

# ==================================================
# CLAIM SUBMISSION — UPDATED FLASH MESSAGE
# ==================================================
@app.route("/report/<int:report_id>/claim", methods=["POST"])
def submit_claim(report_id):
    report = db.get_or_404(Report, report_id)
    if report.status in {"Returned", "Archived"}:
        flash(
            "This report is no longer accepting claim requests.",
            "warning",
        )
        return redirect(url_for("report_detail", report_id=report.id))

    claimant_name = get_report_form_value("claimant_name")
    claimant_contact = get_report_form_value("claimant_contact")
    proof = get_report_form_value("proof")

    if not all([claimant_name, claimant_contact, proof]):
        # ✅ UPDATED: from "ownership proof" to "information about the item"
        flash(
            "Complete your name, contact details, and information about the item.",
            "danger",
        )
        return redirect(url_for("report_detail", report_id=report.id))
    if len(claimant_name) > 120:
        flash("Your name is too long.", "danger")
        return redirect(url_for("report_detail", report_id=report.id))
    if len(claimant_contact) > 150:
        flash("Your contact details are too long.", "danger")
        return redirect(url_for("report_detail", report_id=report.id))

    claim = Claim(
        report_id=report.id,
        claimant_name=claimant_name,
        claimant_contact=claimant_contact,
        proof=proof,
        status="Pending",
    )

    try:
        db.session.add(claim)
        report.status = "Pending Claim"
        db.session.flush()
        create_notification(
            title="New Item Claim",
            message=(
                f'{claim.claimant_name} submitted a claim for '
                f'"{report.item_name}" (report #{report.id}).'
            ),
            notification_type="claim",
            report_id=report.id,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Unable to save claim")
        flash("Unable to submit your claim. Please try again.", "danger")
        return redirect(url_for("report_detail", report_id=report.id))

    flash(
        "Your claim request was submitted successfully "
        "and is waiting for administrator review.",
        "success",
    )
    return redirect(url_for("report_detail", report_id=report.id))

# ==================================================
# LEGACY LOCAL PHOTO ROUTE
# ==================================================
@app.route("/uploads/<path:filename>")
def uploaded_photo(filename):
    if IS_VERCEL:
        return (
            "This photo uses legacy local storage. "
            "Restore it to Cloudinary and update its database URL.",
            404,
        )
    return send_from_directory(UPLOAD_FOLDER, filename)

# ==================================================
# ADMIN LOGIN
# ==================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_username = os.environ.get("ADMIN_USERNAME", "")
        expected_password = os.environ.get("ADMIN_PASSWORD", "")
        if not expected_username or not expected_password:
            flash(
                "Admin credentials are not configured on the server.",
                "danger",
            )
            return render_template("admin_login.html")
        valid_username = hmac.compare_digest(username, expected_username)
        valid_password = hmac.compare_digest(password, expected_password)
        if valid_username and valid_password:
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = expected_username
            flash("Welcome to the admin dashboard!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("admin_login.html")

# ==================================================
# ADMIN DASHBOARD
# ==================================================
@app.route("/admin")
@admin_required
def admin_dashboard():
    filter_type = request.args.get("filter", "").strip()

    reports_query = Report.query
    if filter_type in {"Lost", "Found"}:
        reports_query = reports_query.filter(Report.report_type == filter_type)

    reports = reports_query.order_by(
        Report.created_at.desc(), Report.id.desc()
    ).all()

    all_reports = Report.query.all()
    lost_reports = [r for r in all_reports if r.report_type == "Lost"]
    found_reports = [r for r in all_reports if r.report_type == "Found"]
    pending_claim_count = Claim.query.filter_by(status="Pending").count()

    stats = {
        "total": len(all_reports),
        "lost": len(lost_reports),
        "found": len(found_reports),
        "open": sum(1 for r in all_reports if r.status == "Open"),
        "pending_claims": pending_claim_count,
        "returned": sum(1 for r in all_reports if r.status == "Returned"),
        "archived": sum(1 for r in all_reports if r.status == "Archived"),
    }

    return render_template(
        "admin_dashboard.html",
        reports=reports,
        lost_reports=lost_reports,
        found_reports=found_reports,
        stats=stats,
    )

# ==================================================
# ADMIN: UPDATE REPORT STATUS
# ==================================================
@app.route("/admin/report/<int:report_id>/status", methods=["POST"])
@admin_required
def admin_update_report_status(report_id):
    report = db.get_or_404(Report, report_id)
    new_status = get_report_form_value("status")
    if new_status not in REPORT_STATUSES:
        flash("Invalid report status.", "danger")
        return redirect(url_for("admin_dashboard"))
    report.status = new_status
    try:
        db.session.commit()
        flash("Report status updated successfully.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Report status update failed")
        flash("Unable to update report status.", "danger")
    return redirect(url_for("admin_dashboard"))

# ==================================================
# ADMIN: DELETE REPORT — SAVE TO HISTORY
# ==================================================
@app.route("/admin/report/<int:report_id>/delete", methods=["POST"])
@admin_required
def admin_delete_report(report_id):
    report = db.get_or_404(Report, report_id)

    # --- Save to DELETED HISTORY before deleting ---
    deleted_record = DeletedReport(
        original_report_id=report.id,
        report_type=report.report_type,
        item_name=report.item_name,
        category=report.category,
        description=report.description,
        location=report.location,
        incident_date=report.incident_date,
        contact_name=report.contact_name,
        contact=report.contact,
        status_when_deleted=report.status,
        photo=report.photo,
        created_at=report.created_at,
        deleted_by=session.get("admin_username", "Unknown Admin"),
    )
    db.session.add(deleted_record)
    # ------------------------------------------------

    report_id_to_delete = report.id
    photo = report.photo
    try:
        db.session.delete(report)
        db.session.commit()
        delete_photo(photo)
        flash(
            f"Report #{report_id_to_delete} deleted and moved to history.",
            "success",
        )
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to delete report #%s", report_id_to_delete)
        flash("Unable to delete report. Please check the deployment logs.", "danger")
    return redirect(url_for("admin_dashboard"))

# ==================================================
# ADMIN: DELETED REPORTS HISTORY
# ==================================================
@app.route("/admin/history")
@admin_required
def admin_history():
    deleted_reports = DeletedReport.query.order_by(
        DeletedReport.deleted_at.desc()
    ).all()
    return render_template(
        "admin_history.html",
        deleted_reports=deleted_reports,
    )

@app.route("/admin/history/export.csv")
@admin_required
def export_history_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Original ID", "Type", "Item Name", "Category", "Description",
        "Location", "Incident Date", "Contact Name", "Contact",
        "Status When Deleted", "Report Created", "Deleted At", "Deleted By",
    ])
    deleted_reports = DeletedReport.query.order_by(
        DeletedReport.deleted_at.desc()
    ).all()
    for dr in deleted_reports:
        writer.writerow([
            dr.original_report_id,
            dr.report_type,
            dr.item_name,
            dr.category,
            dr.description,
            dr.location,
            dr.incident_date.isoformat() if dr.incident_date else "",
            dr.contact_name,
            dr.contact,
            dr.status_when_deleted,
            dr.created_at.isoformat() if dr.created_at else "",
            dr.deleted_at.isoformat() if dr.deleted_at else "",
            dr.deleted_by or "",
        ])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        "attachment; filename=deleted_reports_history.csv"
    )
    return response

# ==================================================
# ADMIN: VIEW CLAIMS
# ==================================================
@app.route("/admin/claims")
@admin_required
def admin_claims():
    claims = Claim.query.order_by(
        Claim.created_at.desc(), Claim.id.desc()
    ).all()
    return render_template("admin_claims.html", claims=claims)

# ==================================================
# ADMIN: UPDATE CLAIM STATUS
# ==================================================
@app.route("/admin/claim/<int:claim_id>/status", methods=["POST"])
@admin_required
def admin_update_claim_status(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    new_status = get_report_form_value("status")
    if new_status not in CLAIM_STATUSES:
        flash("Invalid claim status.", "danger")
        return redirect(url_for("admin_claims"))

    if claim.report.status == "Archived" and new_status == "Approved":
        flash("Cannot approve a claim for an archived report.", "warning")
        return redirect(url_for("admin_claims"))

    old_status = claim.status
    report = claim.report

    try:
        claim.status = new_status
        if new_status == "Approved":
            report.status = "Returned"
            other_pending = Claim.query.filter(
                Claim.report_id == report.id,
                Claim.status == "Pending",
                Claim.id != claim.id,
            ).all()
            for c in other_pending:
                c.status = "Rejected"
        elif new_status == "Rejected":
            remaining_pending = Claim.query.filter(
                Claim.report_id == report.id,
                Claim.status == "Pending",
                Claim.id != claim.id,
            ).count()
            if remaining_pending == 0 and report.status == "Pending Claim":
                report.status = "Open"

        if old_status != new_status:
            if new_status == "Approved":
                create_notification(
                    title="Claim Approved",
                    message=f"Claim #{claim_id} for '{report.item_name}' was approved.",
                    notification_type="success",
                    report_id=report.id,
                )
            elif new_status == "Rejected":
                create_notification(
                    title="Claim Rejected",
                    message=f"Claim #{claim_id} for '{report.item_name}' was rejected.",
                    notification_type="warning",
                    report_id=report.id,
                )

        db.session.commit()
        flash("Claim status updated successfully.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Claim status update failed")
        flash("Unable to update claim status.", "danger")
    return redirect(url_for("admin_claims"))

# ==================================================
# ADMIN: NOTIFICATIONS
# ==================================================
@app.route("/notifications")
@admin_required
def notifications_page():
    notifications = Notification.query.order_by(
        Notification.created_at.desc(), Notification.id.desc()
    ).all()
    unread_count = Notification.query.filter_by(is_read=False).count()
    return render_template(
        "notifications.html",
        notifications=notifications,
        unread_count=unread_count,
    )

@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@admin_required
def mark_notification_read(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    try:
        notification.is_read = True
        db.session.commit()
        flash("Notification marked as read.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to mark notification as read")
        flash("Unable to update notification.", "danger")
    return redirect(url_for("notifications_page"))

@app.route("/notifications/read-all", methods=["POST"])
@admin_required
def mark_all_notifications_read():
    try:
        Notification.query.filter_by(is_read=False).update(
            {"is_read": True}, synchronize_session=False
        )
        db.session.commit()
        flash("All notifications marked as read.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to mark all as read")
        flash("Unable to update notifications.", "danger")
    return redirect(url_for("notifications_page"))

@app.route("/notifications/<int:notification_id>/delete", methods=["POST"])
@admin_required
def delete_notification(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    try:
        db.session.delete(notification)
        db.session.commit()
        flash("Notification deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to delete notification")
        flash("Unable to delete notification.", "danger")
    return redirect(url_for("notifications_page"))

# ==================================================
# ADMIN: CSV EXPORT
# ==================================================
@app.route("/admin/export.csv")
@admin_required
def export_reports():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Type", "Item", "Category", "Description", "Location",
        "Incident Date", "Contact Name", "Contact", "Status", "Created At",
    ])
    reports = Report.query.order_by(
        Report.created_at.desc(), Report.id.desc()
    ).all()
    for report in reports:
        writer.writerow([
            report.id,
            report.report_type,
            report.item_name,
            report.category,
            report.description,
            report.location,
            report.incident_date.isoformat() if report.incident_date else "",
            report.contact_name,
            report.contact,
            report.status,
            report.created_at.isoformat() if report.created_at else "",
        ])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        "attachment; filename=findhub_reports.csv"
    )
    return response

# ==================================================
# ADMIN LOGOUT
# ==================================================
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

# ==================================================
# ERROR HANDLERS
# ==================================================
@app.errorhandler(413)
def file_too_large(_error):
    flash("The uploaded file is too large. Maximum size is 5 MB.", "danger")
    return redirect(request.referrer or url_for("new_report"))

@app.errorhandler(404)
def page_not_found(_error):
    if (BASE_DIR / "templates" / "404.html").exists():
        return render_template("404.html"), 404
    return "Page not found.", 404

# ==================================================
# SECURITY HEADERS
# ==================================================
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# ==================================================
# RUN
# ==================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
