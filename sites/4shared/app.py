"""4shared mirror for the WebHarbor offline benchmark."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


SITE_SLUG = "4shared"
SITE_NAME = "4shared"
SITE_PORT = 40026
BENCHMARK_PASSWORD = "TestPass123!"
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
RUNTIME_DB_PATH = INSTANCE_DIR / "4shared.db"
SEED_DB_PATH = SEED_DIR / "4shared.db"
PASSWORD_NAMESPACE = "webharbor-4shared-v1"

PREMIUM_PLANS = {
    "100": {"label": "Premium 100 GB", "account_plan": "Premium", "storage_mb": 102400, "annual": 77.88},
    "500": {"label": "Premium 500 GB", "account_plan": "Premium 500 GB", "storage_mb": 512000, "annual": 119.88},
    "1000": {"label": "Premium 1 TB", "account_plan": "Premium 1 TB", "storage_mb": 1048576, "annual": 155.88},
}

UPLOAD_CATEGORY_BY_EXTENSION = {
    "aac": "Music", "flac": "Music", "m4a": "Music", "mp3": "Music", "ogg": "Music", "wav": "Music",
    "avi": "Video", "mkv": "Video", "mov": "Video", "mp4": "Video", "webm": "Video",
    "gif": "Images", "jpeg": "Images", "jpg": "Images", "png": "Images", "webp": "Images",
    "epub": "Books", "mobi": "Books",
    "7z": "Archives", "rar": "Archives", "tar": "Archives", "zip": "Archives",
    "apk": "Apps", "dmg": "Apps", "exe": "Apps", "msi": "Apps",
}

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
SEED_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY="webharbor-4shared-deterministic-development-key",
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{RUNTIME_DB_PATH}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Log in to manage files and folders."


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def stable_password_hash(password: str) -> str:
    return hashlib.sha256(f"{PASSWORD_NAMESPACE}:{password}".encode()).hexdigest()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "file"


def safe_next(target: str | None, fallback: str) -> str:
    if not target or "\\" in target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


app.jinja_env.filters["filesize"] = human_size


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    location = db.Column(db.String(120), default="")
    bio = db.Column(db.Text, default="")
    plan = db.Column(db.String(32), default="Free")
    storage_limit_mb = db.Column(db.Integer, default=15360)
    joined_at = db.Column(db.DateTime, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = stable_password_hash(password)

    def check_password(self, password: str) -> bool:
        return secrets.compare_digest(self.password_hash, stable_password_hash(password))

    @property
    def storage_used(self) -> int:
        return sum(item.size_bytes for item in self.files if not item.deleted)


class Folder(db.Model):
    __tablename__ = "folders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folders.id", ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref=db.backref("folders", cascade="all, delete-orphan"), foreign_keys=[user_id])
    parent = db.relationship("Folder", remote_side=[id], backref="children")
    __table_args__ = (db.UniqueConstraint("user_id", "parent_id", "name", name="uq_folder_parent_name"),)


class FileItem(db.Model):
    __tablename__ = "files"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("folders.id", ondelete="SET NULL"), index=True)
    filename = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(260), unique=True, nullable=False, index=True)
    category = db.Column(db.String(32), nullable=False, index=True)
    extension = db.Column(db.String(12), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default="")
    tags = db.Column(db.String(400), default="")
    license_name = db.Column(db.String(100), default="")
    uploader_name = db.Column(db.String(120), nullable=False)
    public = db.Column(db.Boolean, default=True, nullable=False, index=True)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    deleted = db.Column(db.Boolean, default=False, nullable=False)
    thumbnail = db.Column(db.String(240), default="")
    preview_text = db.Column(db.Text, default="")
    uploaded_at = db.Column(db.DateTime, nullable=False, index=True)
    modified_at = db.Column(db.DateTime, nullable=False)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    rating = db.Column(db.Float, default=4.5, nullable=False)

    owner = db.relationship("User", backref=db.backref("files", cascade="all, delete-orphan"))
    folder = db.relationship("Folder", backref="files")

    @property
    def stem(self) -> str:
        return self.filename.rsplit(".", 1)[0]


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref=db.backref("favorites", cascade="all, delete-orphan"))
    file = db.relationship("FileItem", backref=db.backref("favorite_rows", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("user_id", "file_id", name="uq_favorite_user_file"),)


class SavedFile(db.Model):
    __tablename__ = "saved_files"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref=db.backref("saved_files", cascade="all, delete-orphan"))
    file = db.relationship("FileItem")
    __table_args__ = (db.UniqueConstraint("user_id", "file_id", name="uq_saved_user_file"),)


class DownloadLog(db.Model):
    __tablename__ = "downloads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    file_id = db.Column(db.Integer, db.ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    downloaded_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref="downloads")
    file = db.relationship("FileItem", backref="download_rows")


class SharedLink(db.Model):
    __tablename__ = "shared_links"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    token = db.Column(db.String(48), unique=True, nullable=False, index=True)
    permission = db.Column(db.String(24), default="view")
    label = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref=db.backref("shared_links", cascade="all, delete-orphan"))
    file = db.relationship("FileItem", backref="share_links")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    body = db.Column(db.String(600), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref="comments")
    file = db.relationship("FileItem", backref=db.backref("comments", order_by="Comment.created_at.desc()"))


class PlanOrder(db.Model):
    __tablename__ = "plan_orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_name = db.Column(db.String(40), nullable=False)
    billing_period = db.Column(db.String(24), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)
    status = db.Column(db.String(24), default="Active", nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship("User", backref="plan_orders")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def public_files_query():
    return FileItem.query.filter_by(public=True, deleted=False)


STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is", "it", "by", "with"}


def scored_search(query: str, items: list[FileItem]) -> list[FileItem]:
    tokens = [token for token in re.split(r"\W+", query.lower()) if len(token) > 1 and token not in STOP_WORDS]
    if not tokens:
        return items
    ranked = []
    for item in items:
        title = item.filename.lower()
        blob = " ".join((item.filename, item.description, item.tags, item.category, item.extension, item.uploader_name)).lower()
        score = sum(4 if token in title else 1 for token in tokens if token in blob)
        if score:
            ranked.append((item, score))
    ranked.sort(key=lambda row: (-row[1], -row[0].download_count, row[0].filename.lower()))
    return [item for item, _score in ranked]


def owned_file_or_404(file_id: int) -> FileItem:
    item = db.session.get(FileItem, file_id)
    if not item or item.owner_id != current_user.id:
        abort(404)
    return item


def viewable_file_or_404(file_id: int) -> FileItem:
    """A file the current user is allowed to act on: public, or their own private one.

    Never a trashed file. Used by every route that writes a row referencing a file
    the user does not necessarily own (favorite / comment / share), so that another
    account's private filename can never surface through those surfaces.
    """
    item = db.get_or_404(FileItem, file_id)
    owner_is_current = current_user.is_authenticated and item.owner_id == current_user.id
    if item.deleted or (not item.public and not owner_is_current):
        abort(404)
    return item


def bounded_int(raw, low: int, high: int) -> int | None:
    """A plain decimal integer inside [low, high], else None. SQLite enforces neither."""
    value = (raw or "").strip()
    if not value.isdigit():
        return None
    number = int(value)
    return number if low <= number <= high else None


def owned_folder_id_or_abort(raw) -> int | None:
    """'' means the account root; anything else must be one of this user's folders.

    A non-numeric value is a client error (400), not a silent fall back to the root.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if not value.isdigit():
        abort(400)
    folder_id = int(value)
    if not Folder.query.filter_by(id=folder_id, user_id=current_user.id).first():
        abort(404)
    return folder_id


def allocate_file_slug(filename: str, user_id: int) -> str:
    """`<slug>-<user>`, then the lowest free `-N` suffix.

    Derived from the rows that exist rather than from a wall-clock counter, so a
    second upload of the same name (in the same second, or after the first was
    trashed) gets a fresh slug instead of violating files.slug UNIQUE.
    """
    base = f"{slugify(filename)}-{user_id}"
    taken = {row[0] for row in db.session.query(FileItem.slug).filter(FileItem.slug.like(f"{base}%")).all()}
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


@app.context_processor
def common_context():
    categories = ["Music", "Video", "Apps", "Images", "Books", "Documents", "Archives"]
    favorite_ids = set()
    if current_user.is_authenticated:
        favorite_ids = {row.file_id for row in current_user.favorites}
    return {"nav_categories": categories, "favorite_ids": favorite_ids, "site_port": SITE_PORT}


@app.route("/")
def index():
    # index.html renders the hero, the drop zone and the app band only; it lists no
    # files, so the homepage runs no catalog queries.
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()[:120]
    category_name = request.args.get("category", "All Files").strip()[:32]
    sort = request.args.get("sort", "relevance")
    items = public_files_query().all()
    if category_name and category_name != "All Files":
        items = [item for item in items if item.category.lower() == category_name.lower()]
    items = scored_search(query, items)
    if sort == "downloads":
        items.sort(key=lambda item: (-item.download_count, item.filename.lower()))
    elif sort == "newest":
        items.sort(key=lambda item: (-item.uploaded_at.timestamp(), item.filename.lower()))
    elif sort == "size":
        items.sort(key=lambda item: (-item.size_bytes, item.filename.lower()))
    return render_template("search.html", files=items, query=query, category=category_name, sort=sort)


@app.route("/category/<category>")
def category(category: str):
    display = category.replace("-", " ").title()
    files = public_files_query().filter(db.func.lower(FileItem.category) == display.lower()).order_by(FileItem.download_count.desc(), FileItem.id.asc()).all()
    if not files:
        abort(404)
    return render_template("category.html", files=files, category=display)


@app.route("/file/<slug>")
def file_detail(slug: str):
    item = FileItem.query.filter_by(slug=slug, deleted=False).first_or_404()
    if not item.public and (not current_user.is_authenticated or item.owner_id != current_user.id):
        abort(404)
    related = public_files_query().filter(FileItem.category == item.category, FileItem.id != item.id).order_by(FileItem.download_count.desc(), FileItem.id.asc()).limit(6).all()
    return render_template("file_detail.html", file=item, related=related)


@app.route("/preview/<int:file_id>")
def preview(file_id: int):
    item = db.get_or_404(FileItem, file_id)
    if item.deleted or (not item.public and (not current_user.is_authenticated or item.owner_id != current_user.id)):
        abort(404)
    return render_template("preview.html", file=item)


@app.post("/download/<int:file_id>")
def download(file_id: int):
    item = db.get_or_404(FileItem, file_id)
    if item.deleted or (not item.public and (not current_user.is_authenticated or item.owner_id != current_user.id)):
        abort(404)
    item.download_count += 1
    db.session.add(DownloadLog(user_id=current_user.id if current_user.is_authenticated else None, file_id=item.id, downloaded_at=datetime.utcnow()))
    db.session.commit()
    return render_template("download_ready.html", file=item)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:160]
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(safe_next(request.args.get("next"), url_for("account")))
        flash("The email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()[:120]
        email = request.form.get("email", "").strip().lower()[:160]
        password = request.form.get("password", "")
        if len(display_name) < 2 or "@" not in email or len(password) < 8:
            flash("Enter a name, valid email, and password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(email=email, display_name=display_name, joined_at=datetime.utcnow())
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to 4shared. Your account is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.get("/account")
@login_required
def account():
    recent_files = FileItem.query.filter_by(owner_id=current_user.id, deleted=False).order_by(FileItem.modified_at.desc()).limit(6).all()
    recent_downloads = DownloadLog.query.filter_by(user_id=current_user.id).order_by(DownloadLog.downloaded_at.desc()).limit(6).all()
    return render_template("account.html", recent_files=recent_files, recent_downloads=recent_downloads)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()[:120]
        if len(name) < 2:
            flash("Display name must have at least two characters.", "error")
        else:
            current_user.display_name = name
            current_user.location = request.form.get("location", "").strip()[:120]
            current_user.bio = request.form.get("bio", "").strip()[:500]
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.get("/my-files")
@login_required
def my_files():
    folder_id = request.args.get("folder", type=int)
    active_folder = None
    if folder_id:
        active_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()
    folders = Folder.query.filter_by(user_id=current_user.id, parent_id=folder_id).order_by(Folder.name).all()
    files = FileItem.query.filter_by(owner_id=current_user.id, folder_id=folder_id, deleted=False).order_by(FileItem.filename).all()
    all_folders = Folder.query.filter_by(user_id=current_user.id).order_by(Folder.name).all()
    return render_template("my_files.html", folders=folders, files=files, active_folder=active_folder, all_folders=all_folders)


@app.post("/folder/new")
@login_required
def folder_new():
    name = request.form.get("name", "").strip()[:120]
    parent_id = owned_folder_id_or_abort(request.form.get("parent_id"))
    if not name:
        flash("Folder name is required.", "error")
    elif Folder.query.filter_by(user_id=current_user.id, parent_id=parent_id, name=name).first():
        flash("A folder with that name already exists here.", "error")
    else:
        db.session.add(Folder(user_id=current_user.id, parent_id=parent_id, name=name, created_at=datetime.utcnow()))
        db.session.commit()
        flash(f"Folder ‘{name}’ created.", "success")
    return redirect(url_for("my_files", folder=parent_id) if parent_id else url_for("my_files"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    folders = Folder.query.filter_by(user_id=current_user.id).order_by(Folder.name).all()
    if request.method == "POST":
        filename = request.form.get("filename", "").strip()[:220]
        category_name = request.form.get("category", "auto")[:32]
        description = request.form.get("description", "").strip()[:1000]
        folder_id = owned_folder_id_or_abort(request.form.get("folder_id"))
        size_kb = bounded_int(request.form.get("size_kb"), 1, 4096)
        visibility = (request.form.get("visibility") or "").strip()
        if not filename or "." not in filename:
            flash("Enter a filename with an extension, such as notes.pdf.", "error")
            return render_template("upload.html", folders=folders), 400
        if size_kb is None:
            flash("Enter a size in KB between 1 and 4096.", "error")
            return render_template("upload.html", folders=folders), 400
        if visibility not in {"private", "public"}:
            flash("Choose whether this file is private or public.", "error")
            return render_template("upload.html", folders=folders), 400
        extension = filename.rsplit(".", 1)[1].lower()[:12]
        if category_name == "auto":
            category_name = UPLOAD_CATEGORY_BY_EXTENSION.get(extension, "Documents")
        elif category_name not in {"Music", "Video", "Apps", "Images", "Books", "Documents", "Archives"}:
            category_name = "Documents"
        item = FileItem(
            owner_id=current_user.id, folder_id=folder_id, filename=filename,
            slug=allocate_file_slug(filename, current_user.id),
            category=category_name, extension=extension, mime_type="application/octet-stream",
            size_bytes=size_kb * 1024,
            description=description, tags="personal upload", license_name="Private",
            uploader_name=current_user.display_name, public=visibility == "public",
            uploaded_at=datetime.utcnow(), modified_at=datetime.utcnow(), preview_text=description,
        )
        try:
            db.session.add(item)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That upload collided with an existing record. Try again.", "error")
            return render_template("upload.html", folders=folders), 409
        flash(f"{filename} uploaded.", "success")
        return redirect(url_for("my_files", folder=folder_id) if folder_id else url_for("my_files"))
    return render_template("upload.html", folders=folders)


@app.post("/file/<int:file_id>/rename")
@login_required
def rename_file(file_id: int):
    item = owned_file_or_404(file_id)
    filename = request.form.get("filename", "").strip()[:220]
    if not filename or "." not in filename:
        flash("Enter a complete filename.", "error")
    else:
        item.filename = filename
        item.extension = filename.rsplit(".", 1)[1].lower()[:12]
        item.modified_at = datetime.utcnow()
        db.session.commit()
        flash("File renamed.", "success")
    return redirect(url_for("my_files", folder=item.folder_id) if item.folder_id else url_for("my_files"))


@app.post("/file/<int:file_id>/move")
@login_required
def move_file(file_id: int):
    item = owned_file_or_404(file_id)
    folder_id = owned_folder_id_or_abort(request.form.get("folder_id"))
    item.folder_id = folder_id
    item.modified_at = datetime.utcnow()
    db.session.commit()
    flash("File moved.", "success")
    return redirect(url_for("my_files", folder=folder_id) if folder_id else url_for("my_files"))


@app.post("/file/<int:file_id>/delete")
@login_required
def delete_file(file_id: int):
    item = owned_file_or_404(file_id)
    item.deleted = True
    item.modified_at = datetime.utcnow()
    db.session.commit()
    flash("File moved to Trash.", "success")
    return redirect(url_for("my_files"))


@app.get("/trash")
@login_required
def trash():
    files = FileItem.query.filter_by(owner_id=current_user.id, deleted=True).order_by(FileItem.modified_at.desc()).all()
    return render_template("trash.html", files=files)


@app.post("/file/<int:file_id>/restore")
@login_required
def restore_file(file_id: int):
    item = owned_file_or_404(file_id)
    item.deleted = False
    item.modified_at = datetime.utcnow()
    db.session.commit()
    flash("File restored.", "success")
    return redirect(url_for("trash"))


@app.post("/file/<int:file_id>/favorite")
@login_required
def toggle_favorite(file_id: int):
    item = viewable_file_or_404(file_id)
    row = Favorite.query.filter_by(user_id=current_user.id, file_id=item.id).first()
    if row:
        db.session.delete(row)
        flash("Removed from favorites.", "success")
    else:
        db.session.add(Favorite(user_id=current_user.id, file_id=item.id, created_at=datetime.utcnow()))
        flash("Added to favorites.", "success")
    db.session.commit()
    return redirect(safe_next(request.form.get("next"), url_for("file_detail", slug=item.slug)))


@app.get("/favorites")
@login_required
def favorites():
    rows = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    return render_template("favorites.html", files=[row.file for row in rows if not row.file.deleted])


@app.post("/file/<int:file_id>/save")
@login_required
def save_file(file_id: int):
    item = db.get_or_404(FileItem, file_id)
    if not item.public or item.deleted:
        abort(404)
    if not SavedFile.query.filter_by(user_id=current_user.id, file_id=item.id).first():
        db.session.add(SavedFile(user_id=current_user.id, file_id=item.id, created_at=datetime.utcnow()))
        db.session.commit()
    flash("Saved to My 4shared.", "success")
    return redirect(url_for("file_detail", slug=item.slug))


@app.get("/saved")
@login_required
def saved():
    rows = SavedFile.query.filter_by(user_id=current_user.id).order_by(SavedFile.created_at.desc()).all()
    return render_template("favorites.html", files=[row.file for row in rows], title="Saved files")


@app.route("/file/<int:file_id>/share", methods=["GET", "POST"])
@login_required
def share_file(file_id: int):
    item = viewable_file_or_404(file_id)
    links = SharedLink.query.filter_by(user_id=current_user.id, file_id=item.id).order_by(SharedLink.created_at.desc()).all()
    if request.method == "POST":
        permission = (request.form.get("permission") or "").strip()
        if permission not in {"view", "download"}:
            flash("Choose a link permission.", "error")
            return render_template("share.html", file=item, links=links), 400
        token = secrets.token_urlsafe(12)
        link = SharedLink(user_id=current_user.id, file_id=item.id, token=token, permission=permission,
                          label=request.form.get("label", "").strip()[:120], created_at=datetime.utcnow())
        db.session.add(link)
        db.session.commit()
        flash("Share link created.", "success")
        return redirect(url_for("share_file", file_id=item.id))
    return render_template("share.html", file=item, links=links)


@app.get("/shared/<token>")
def shared(token: str):
    link = SharedLink.query.filter_by(token=token).first_or_404()
    if link.file.deleted:
        abort(404)
    return render_template("shared.html", link=link, file=link.file)


@app.post("/file/<int:file_id>/comment")
@login_required
def add_comment(file_id: int):
    item = viewable_file_or_404(file_id)
    body = request.form.get("body", "").strip()[:600]
    if len(body) < 2:
        flash("Comment cannot be empty.", "error")
    else:
        db.session.add(Comment(user_id=current_user.id, file_id=item.id, body=body, created_at=datetime.utcnow()))
        db.session.commit()
        flash("Comment posted.", "success")
    return redirect(url_for("file_detail", slug=item.slug))


@app.get("/activity")
@login_required
def activity():
    downloads = DownloadLog.query.filter_by(user_id=current_user.id).order_by(DownloadLog.downloaded_at.desc()).all()
    shares = SharedLink.query.filter_by(user_id=current_user.id).order_by(SharedLink.created_at.desc()).all()
    return render_template("activity.html", downloads=downloads, shares=shares)


@app.get("/premium")
def premium():
    return render_template("premium.html")


@app.route("/premium/checkout", methods=["GET", "POST"])
@login_required
def premium_checkout():
    # No silent fallback: a missing or unknown plan is a 404, never the first plan.
    plan_key = (request.values.get("plan") or "").strip()
    if plan_key not in PREMIUM_PLANS:
        abort(404)
    plan = PREMIUM_PLANS[plan_key]
    period = "annual"
    amount = plan[period]
    if request.method == "POST":
        card = re.sub(r"\D", "", request.form.get("card_number", ""))
        holder = request.form.get("cardholder", "").strip()
        if len(card) != 16 or len(holder) < 2:
            flash("Enter the demo 16-digit card number and cardholder name.", "error")
        else:
            order = PlanOrder(user_id=current_user.id, plan_name=plan["label"], billing_period=period,
                              amount=amount, card_last4=card[-4:], created_at=datetime.utcnow())
            current_user.plan = plan["account_plan"]
            current_user.storage_limit_mb = plan["storage_mb"]
            db.session.add(order)
            db.session.commit()
            return render_template("premium_confirmed.html", order=order, plan=plan)
    return render_template("premium_checkout.html", period=period, amount=amount, plan=plan, plan_key=plan_key)


@app.get("/help")
def help_center():
    return render_template("help.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/press-room")
def press_room():
    return render_template("press_room.html")


@app.get("/blog")
def blog():
    return render_template("blog.html")


@app.route("/convert/<source_format>-to-pdf", methods=["GET", "POST"])
def convert_to_pdf(source_format: str):
    allowed_formats = {"doc", "pptx", "docx", "xls", "ppt", "xlsx", "cbr", "txt", "pps", "rtf", "cbz", "fb2", "epub", "djvu"}
    if source_format not in allowed_formats:
        abort(404)
    converted_name = None
    if request.method == "POST":
        filename = request.form.get("filename", "").strip()[:220]
        if not filename.lower().endswith(f".{source_format}"):
            flash(f"Choose a .{source_format} file record to convert.", "error")
        else:
            converted_name = f"{filename.rsplit('.', 1)[0]}.pdf"
    return render_template("converter.html", source_format=source_format, converted_name=converted_name)


@app.get("/_health")
def health():
    return {"ok": True, "site": SITE_SLUG, "files": public_files_query().count()}


@app.errorhandler(400)
def bad_request(_error):
    return render_template("400.html"), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    db.session.rollback()
    return render_template("500.html"), 500


def initialize_database() -> None:
    with app.app_context():
        db.create_all()
        from seed_data import seed_benchmark_users, seed_database
        seed_database()
        seed_benchmark_users()


initialize_database()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", SITE_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)
