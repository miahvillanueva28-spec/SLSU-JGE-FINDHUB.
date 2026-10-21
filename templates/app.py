
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from flask import url_for, send_from_directory, abort
from werkzeug.utils import secure_filename

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB

# Gamitin ang UPLOAD_FOLDER na naka-configure na sa app.py.
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)


def allowed_file(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_PHOTO_EXTENSIONS
    )


def photo_src(photo):
    """Return a display URL for Cloudinary or a locally saved photo."""
    if not photo:
        return None

    photo = str(photo).strip()

    if photo.startswith(("https://", "http://")):
        parsed = urlparse(photo)

        # Permit only valid HTTP(S) URLs.
        if parsed.scheme in ("https", "http") and parsed.netloc:
            return photo

        return None

    # Local filenames only; never accept arbitrary filesystem paths.
    filename = Path(photo).name

    if filename != photo:
        return None

    return url_for("uploaded_photo", filename=filename)


def save_photo(file):
    """Save a photo to Cloudinary on deployment or local storage otherwise."""
    if not file or not file.filename:
        return None

    original_name = secure_filename(file.filename)

    if not allowed_file(original_name):
        raise ValueError("Use PNG, JPG, JPEG, GIF, or WEBP images only.")

    # Check the actual uploaded bytes, not only the filename.
    file.stream.seek(0, os.SEEK_END)
    file_size = file.stream.tell()
    file.stream.seek(0)

    if file_size == 0:
        raise ValueError("The selected photo is empty.")

    if file_size > MAX_PHOTO_SIZE:
        raise ValueError("The photo must be 5 MB or smaller.")

    if os.environ.get("CLOUDINARY_URL"):
        import cloudinary
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            file,
            folder="slsu-jge-findhub",
            resource_type="image",
        )

        image_url = result.get("secure_url")
        if not image_url:
            raise RuntimeError("Cloudinary did not return an image URL.")

        return image_url

    # Vercel's filesystem is not permanent storage.
    if os.environ.get("VERCEL") == "1":
        raise RuntimeError(
            "Photo storage is not configured. Add CLOUDINARY_URL "
            "to your deployment environment variables."
        )

    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{secrets.token_hex(16)}.{extension}"

    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def delete_photo(photo):
    """Delete local photos only; Cloudinary photos need separate deletion."""
    if not photo or str(photo).startswith(("https://", "http://")):
        return

    filename = Path(str(photo)).name
    if filename != str(photo):
        return

    path = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.isfile(path):
        os.remove(path)
