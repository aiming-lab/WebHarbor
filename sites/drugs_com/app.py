"""Drugs.com mirror — Flask app for the WebHarbor benchmark.

Full mirror with drug catalog, A-Z index, drug detail pages, search,
interaction checker, pill identifier, conditions/classes, news, accounts,
reviews, and a "My Med List" save feature.
"""
import os
import json
import re
import secrets
import string
import hashlib
import threading
import time
from datetime import datetime, timedelta
from itertools import combinations
import difflib
from urllib.parse import urlsplit

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    abort, session, g,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required,
    current_user,
)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from email_validator import EmailNotValidError, validate_email
from markupsafe import escape
from sqlalchemy import event, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)


def _load_runtime_secret_key():
    """Keep sessions stable across restart, but rotate them on a full reset."""
    configured = os.environ.get("DRUGS_COM_SECRET_KEY")
    if configured:
        return configured

    secret_path = os.path.join(BASE_DIR, "instance", ".secret_key")
    try:
        with open(secret_path, encoding="utf-8") as secret_file:
            stored = secret_file.read().strip()
        if len(stored) >= 32:
            return stored
    except FileNotFoundError:
        pass

    generated = secrets.token_hex(32)
    try:
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        # A simultaneous process won creation; use its completed value.
        for _ in range(50):
            with open(secret_path, encoding="utf-8") as secret_file:
                stored = secret_file.read().strip()
            if len(stored) >= 32:
                return stored
            time.sleep(0.01)
        raise RuntimeError("runtime secret key file was not initialized")
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(generated)
    return generated

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.url_map.strict_slashes = False
app.config["SECRET_KEY"] = _load_runtime_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(BASE_DIR, "instance", "drugs_com.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1_000_000
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
_sqlite_write_lock = threading.RLock()
_NON_SQLITE_MUTATING_ENDPOINTS = {
    "login",
    "register",
    "interaction_checker",
    "api_interaction_check",
    "symptom_checker",
    "contact",
}


@app.before_request
def _serialize_sqlite_writes():
    """SQLite has one writer; queue mutating HTTP requests in this process."""
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.endpoint not in _NON_SQLITE_MUTATING_ENDPOINTS
    ):
        # Consume the bounded request body before taking the database lock so
        # a slow client upload cannot stall unrelated mutations site-wide.
        request.get_data(cache=True)
        _sqlite_write_lock.acquire()
        g._sqlite_write_lock_held = True


@app.teardown_request
def _release_sqlite_write_lock(_error):
    if getattr(g, "_sqlite_write_lock_held", False):
        g._sqlite_write_lock_held = False
        _sqlite_write_lock.release()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


def slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _password_validation_error(password):
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password.encode("utf-8")) > 72:
        return "Password must be 72 bytes or fewer."
    return None


_MAX_INTERACTION_DRUGS = 20
_MAX_INTERACTION_NAME_LENGTH = 120
_MAX_QUERY_TEXT_LENGTH = 200
_MAX_FILTER_TEXT_LENGTH = 120
_MAX_QUERY_PARAMETER_COUNT = 100
_MAX_QUERY_PARAMETER_LENGTH = 2_048
_MAX_PAGE_NUMBER = 100_000


@app.before_request
def _bound_query_parameters():
    """Reject oversized query strings before templates can reflect them."""
    pairs = list(request.args.items(multi=True))
    if len(pairs) > _MAX_QUERY_PARAMETER_COUNT:
        abort(400)
    if any(
        len(key) > _MAX_FILTER_TEXT_LENGTH
        or len(value) > _MAX_QUERY_PARAMETER_LENGTH
        for key, value in pairs
    ):
        abort(400)


def _bounded_query_arg(name, default="", max_length=_MAX_QUERY_TEXT_LENGTH):
    """Read a query parameter without allowing reflected-response amplification."""
    value = request.args.get(name, default)
    value = default if value is None else value
    if not isinstance(value, str) or len(value) > max_length:
        abort(400)
    return value


def _bounded_page_arg():
    """Return a positive page number whose SQL offset cannot overflow SQLite."""
    raw_page = request.args.get("page", "1")
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        abort(400)
    if not 1 <= page <= _MAX_PAGE_NUMBER:
        abort(400)
    return page


def _normalize_interaction_names(raw_names):
    """Validate and normalize a bounded list of interaction-check inputs."""
    if not isinstance(raw_names, (list, tuple)):
        return None
    if len(raw_names) > _MAX_INTERACTION_DRUGS:
        return None
    names = []
    for raw_name in raw_names:
        if not isinstance(raw_name, str):
            return None
        name = raw_name.strip()
        if len(name) > _MAX_INTERACTION_NAME_LENGTH:
            return None
        if name:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), default="")
    last_name = db.Column(db.String(80), default="")
    preferences_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("DrugReview", backref="user", lazy=True)
    saved_drugs = db.relationship("SavedDrug", backref="user", lazy=True)

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw):
        try:
            return bcrypt.check_password_hash(self.password_hash, raw)
        except ValueError:
            # bcrypt 5 rejects inputs over 72 bytes instead of truncating.
            return False

    def get_id(self):
        """Bind session and remember cookies to the current password hash."""
        fingerprint = hashlib.sha256(
            (self.password_hash or "").encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.id}:{fingerprint}"

    @property
    def preferences(self):
        try:
            value = json.loads(self.preferences_json or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def set_preferences(self, preferences):
        self.preferences_json = json.dumps(preferences, sort_keys=True)


class DrugClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    drugs = db.relationship("Drug", backref="drug_class", lazy=True)


class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    generic_name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    brand_names_json = db.Column(db.Text, default="[]")
    drug_class_id = db.Column(db.Integer, db.ForeignKey("drug_class.id"))
    availability = db.Column(db.String(40), default="Rx")
    csa_schedule = db.Column(db.String(40), default="Not a controlled drug")
    pregnancy_risk = db.Column(db.String(80), default="Consult your doctor")
    pronunciation = db.Column(db.String(120))
    description = db.Column(db.Text)
    uses = db.Column(db.Text)
    warnings = db.Column(db.Text)
    dosage = db.Column(db.Text)
    side_effects = db.Column(db.Text)
    interactions_text = db.Column(db.Text)
    faq_json = db.Column(db.Text, default="[]")
    avg_rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    conditions_json = db.Column(db.Text, default="[]")
    related_drugs_json = db.Column(db.Text, default="[]")
    reviewer_name = db.Column(db.String(120), default="Drugs.com editorial team")
    reviewer_credential = db.Column(db.String(120), default="PharmD")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def brand_names(self):
        try:
            return json.loads(self.brand_names_json or "[]")
        except Exception:
            return []

    @property
    def faq(self):
        try:
            return json.loads(self.faq_json or "[]")
        except Exception:
            return []

    @property
    def conditions_list(self):
        try:
            return json.loads(self.conditions_json or "[]")
        except Exception:
            return []

    @property
    def related_drugs(self):
        try:
            return json.loads(self.related_drugs_json or "[]")
        except Exception:
            return []


class DrugImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    imprint = db.Column(db.String(80))
    shape = db.Column(db.String(40))
    color = db.Column(db.String(40))
    strength = db.Column(db.String(80))
    manufacturer = db.Column(db.String(120))
    drug = db.relationship("Drug", backref="images")


class DrugInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_a_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    drug_b_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    severity = db.Column(db.String(20), default="unknown")
    description = db.Column(db.Text)
    drug_a = db.relationship("Drug", foreign_keys=[drug_a_id])
    drug_b = db.relationship("Drug", foreign_keys=[drug_b_id])


class DrugReview(db.Model):
    __table_args__ = (
        db.UniqueConstraint("drug_id", "user_id", name="uq_drug_review_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    condition_treated = db.Column(db.String(120))
    helpful_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    drug = db.relationship("Drug", backref="reviews")


class Condition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    drug_count = db.Column(db.Integer, default=0)


class DrugCondition(db.Model):
    __table_args__ = (
        db.UniqueConstraint("drug_id", "condition_id", name="uq_drug_condition"),
    )

    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    condition_id = db.Column(db.Integer, db.ForeignKey("condition.id"), nullable=False)


class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    body = db.Column(db.Text)
    source = db.Column(db.String(120), default="Drugs.com")
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)

    @property
    def slug(self):
        s = re.sub(r"[^a-z0-9]+", "-", (self.title or "").lower()).strip("-")
        return s or f"article-{self.id}"


class SavedDrug(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", "drug_id", name="uq_saved_drug_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey("drug.id"), nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    drug = db.relationship("Drug")


def _public_reviews_query():
    """Reviews whose owners have not opted out of public display."""
    public_preference = db.func.json_extract(
        User.preferences_json, "$.public_reviews"
    )
    return (
        DrugReview.query.join(User, User.id == DrugReview.user_id)
        .filter(db.or_(public_preference.is_(None), public_preference != 0))
    )


def _refresh_drug_review_stats(drug):
    """Refresh the public aggregate cached on a drug row."""
    ratings = [
        row[0]
        for row in (
            _public_reviews_query()
            .filter(DrugReview.drug_id == drug.id)
            .with_entities(DrugReview.rating)
            .all()
        )
    ]
    drug.review_count = len(ratings)
    drug.avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0


_LOCK_STRIPES = 64
_saved_drug_locks = tuple(threading.Lock() for _ in range(_LOCK_STRIPES))
_user_settings_locks = tuple(threading.Lock() for _ in range(_LOCK_STRIPES))
_review_votes = {}
_review_votes_lock = threading.Lock()
_MAX_REVIEW_VOTES = 10_000
_MAX_REVIEW_VOTE_RECORDS = 110_000
_REVIEW_VOTES_PREFERENCE = "_review_votes"
_REVIEW_VOTES_SESSION = "_review_votes"
_REVIEW_VOTER_SESSION = "_review_voter_user_id"
_REVIEW_BROWSER_SESSION = "_review_browser_id"
_SERVER_BACKED_SESSION_VOTES = {"Y": "yes", "N": "no"}
_MAX_REVIEW_VOTES_PER_SESSION = 1_000
_MAX_REVIEW_SESSION_COOKIE_BYTES = 2_500


def _saved_drug_lock(user_id, drug_id):
    """Return the process-local lock for one user's saved-drug row."""
    return _saved_drug_locks[hash((user_id, drug_id)) % _LOCK_STRIPES]


def _user_settings_lock(user_id):
    """Serialize read-modify-write updates of one user's preference JSON."""
    return _user_settings_locks[hash(user_id) % _LOCK_STRIPES]


def _valid_review_votes(value, limit=None):
    """Return a bounded, well-formed review-id -> yes/no vote mapping."""
    if not isinstance(value, dict):
        return {}
    votes = {}
    for review_identity, vote in value.items():
        key = str(review_identity)
        parts = key.split("-", 1)
        vote = _SERVER_BACKED_SESSION_VOTES.get(vote, vote)
        if all(part.isdigit() for part in parts) and vote in {"yes", "no"}:
            votes[key] = vote
            if limit is not None and len(votes) >= limit:
                break
    return votes


def _server_backed_session_vote_ids(value):
    """Return signed-cookie votes known to have had a server-ledger row.

    Legacy cookies contain ``yes``/``no``. Current entries use compact
    ``Y``/``N`` values so a missing server row can be distinguished from a
    legacy vote whose helpful count may still be present.
    """
    if not isinstance(value, dict):
        return set()
    valid_votes = _valid_review_votes(value)
    return {
        str(identity)
        for identity, vote in value.items()
        if str(identity) in valid_votes and vote in _SERVER_BACKED_SESSION_VOTES
    }


def _encode_session_review_votes(votes, server_backed):
    encoded = {}
    for identity, vote in votes.items():
        if identity in server_backed:
            encoded[identity] = "Y" if vote == "yes" else "N"
        else:
            encoded[identity] = vote
    return encoded


def _prune_review_votes(value, limit=_MAX_REVIEW_VOTES_PER_SESSION):
    """Canonicalize live review votes and bound the returned ledger.

    Older ledgers used the bare review id while current ledgers include the
    creation timestamp so a deleted SQLite row cannot transfer its vote to a
    later row that reuses the id.  Treat both spellings as one logical vote;
    when both are present, the current spelling wins.
    """
    votes = _valid_review_votes(value, _MAX_REVIEW_VOTES)
    if not votes:
        return {}
    review_ids = {_review_id_from_vote_identity(key) for key in votes}
    reviews = []
    review_ids = list(review_ids)
    for offset in range(0, len(review_ids), 500):
        reviews.extend(
            DrugReview.query.filter(
                DrugReview.id.in_(review_ids[offset:offset + 500])
            ).all()
        )
    current = {review.id: _review_vote_identity(review) for review in reviews}
    canonical_votes = {}
    for key, vote in votes.items():
        review_id = _review_id_from_vote_identity(key)
        current_identity = current.get(review_id)
        if current_identity is None or (
            "-" in key and current_identity != key
        ):
            continue
        if current_identity not in canonical_votes or key == current_identity:
            canonical_votes[current_identity] = vote

    result = {}
    for key, vote in canonical_votes.items():
        if limit is not None and len(result) >= limit:
            break
        result[key] = vote
    return result


def _review_vote_identity(review):
    """Identify a specific review row even if SQLite later reuses its id."""
    created = review.created_at or datetime.min
    return f"{review.id}-{created.strftime('%Y%m%d%H%M%S%f')}"


def _review_id_from_vote_identity(identity):
    return int(str(identity).split("-", 1)[0])


def _remember_review_vote(
    votes,
    review_identity,
    vote,
    limit=None,
):
    """Update a vote mapping without allowing unbounded cookie/JSON growth."""
    key = str(review_identity)
    if key not in votes and limit is not None and len(votes) >= limit:
        return False
    votes[key] = vote
    return True


def _review_votes_fit_session(votes, server_backed=()):
    """Ensure an anonymous vote ledger still fits in a browser cookie."""
    serializer = app.session_interface.get_signing_serializer(app)
    if serializer is None:
        return False
    payload = dict(session)
    payload[_REVIEW_VOTES_SESSION] = _encode_session_review_votes(
        votes, set(server_backed)
    )
    return len(serializer.dumps(payload)) <= _MAX_REVIEW_SESSION_COOKIE_BYTES


def _previous_review_voter_id():
    """Return the account id that most recently logged out in this browser."""
    raw_user_id = session.get(_REVIEW_VOTER_SESSION)
    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        return None


def _review_session_key(create=False):
    """Return a browser-scoped key for the process-local race ledger."""
    csrf_token = session.get("csrf_token")
    if isinstance(csrf_token, str) and csrf_token:
        return "csrf:" + csrf_token
    browser_id = session.get(_REVIEW_BROWSER_SESSION)
    if not (
        isinstance(browser_id, str)
        and len(browser_id) == 32
        and all(character in string.hexdigits for character in browser_id)
    ):
        if not create:
            return None
        browser_id = secrets.token_hex(16)
        session[_REVIEW_BROWSER_SESSION] = browser_id
    return "review:" + browser_id


def _anonymous_review_vote_table_exists():
    return db.session.execute(text(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'anonymous_review_vote'"
    )).scalar() is not None


def _anonymous_review_vote_columns():
    if not _anonymous_review_vote_table_exists():
        return set()
    return {
        row[1]
        for row in db.session.execute(text(
            "PRAGMA table_info(anonymous_review_vote)"
        )).all()
    }


def _anonymous_review_vote_has_claim_column():
    return "claimed_user_id" in _anonymous_review_vote_columns()


def _ensure_anonymous_review_vote_table():
    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS anonymous_review_vote ("
        "voter_key TEXT NOT NULL, review_identity TEXT NOT NULL, "
        "vote TEXT NOT NULL CHECK (vote IN ('yes', 'no')), "
        "claimed_user_id INTEGER, "
        "updated_at INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (voter_key, review_identity))"
    ))
    columns = _anonymous_review_vote_columns()
    if "claimed_user_id" not in columns:
        db.session.execute(text(
            "ALTER TABLE anonymous_review_vote "
            "ADD COLUMN claimed_user_id INTEGER"
        ))
    if "updated_at" not in columns:
        db.session.execute(text(
            "ALTER TABLE anonymous_review_vote "
            "ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0"
        ))
    db.session.execute(text(
        "UPDATE anonymous_review_vote SET updated_at = unixepoch() "
        "WHERE updated_at = 0"
    ))


def _server_review_votes(review_session_key):
    """Load this browser's restart-safe anonymous vote ledger."""
    if not review_session_key or not _anonymous_review_vote_table_exists():
        return {}
    _ensure_anonymous_review_vote_table()
    claim_filter = " AND claimed_user_id IS NULL"
    rows = db.session.execute(
        text(
            "SELECT review_identity, vote FROM anonymous_review_vote "
            "WHERE voter_key = :voter_key" + claim_filter
            + " ORDER BY updated_at, rowid"
        ),
        {"voter_key": review_session_key},
    ).all()
    return _valid_review_votes(dict(rows), _MAX_REVIEW_VOTES_PER_SESSION)


def _server_review_vote_record(review_session_key, review_identity):
    if not review_session_key or not _anonymous_review_vote_table_exists():
        return None
    _ensure_anonymous_review_vote_table()
    row = db.session.execute(
        text(
            "SELECT vote, claimed_user_id FROM anonymous_review_vote "
            "WHERE voter_key = :voter_key AND review_identity = :identity"
        ),
        {"voter_key": review_session_key, "identity": review_identity},
    ).first()
    return tuple(row) if row is not None else None


def _server_review_vote_was_claimed(review_session_key, review_identity):
    record = _server_review_vote_record(
        review_session_key, review_identity
    )
    return record is not None and record[1] is not None


def _remember_server_review_vote(review_session_key, review_identity, vote):
    """Persist an anonymous choice atomically with its helpful-count delta."""
    _ensure_anonymous_review_vote_table()
    existing = db.session.execute(
        text(
            "SELECT 1 FROM anonymous_review_vote "
            "WHERE voter_key = :voter_key AND review_identity = :identity"
        ),
        {"voter_key": review_session_key, "identity": review_identity},
    ).scalar()
    total = db.session.execute(text(
        "SELECT COUNT(*) FROM anonymous_review_vote"
    )).scalar_one()
    if existing is None and total >= _MAX_REVIEW_VOTE_RECORDS:
        return False
    db.session.execute(
        text(
            "INSERT INTO anonymous_review_vote "
            "(voter_key, review_identity, vote, updated_at) "
            "VALUES (:voter_key, :identity, :vote, "
            "(SELECT COALESCE(MAX(updated_at), 0) + 1 "
            "FROM anonymous_review_vote)) "
            "ON CONFLICT(voter_key, review_identity) "
            "DO UPDATE SET vote = excluded.vote, updated_at = "
            "(SELECT COALESCE(MAX(updated_at), 0) + 1 "
            "FROM anonymous_review_vote) "
            "WHERE claimed_user_id IS NULL"
        ),
        {
            "voter_key": review_session_key,
            "identity": review_identity,
            "vote": vote,
        },
    )
    return True


def _claim_server_review_votes(review_session_key, user_id):
    if not review_session_key or not _anonymous_review_vote_table_exists():
        return False
    _ensure_anonymous_review_vote_table()
    result = db.session.execute(
        text(
            "UPDATE anonymous_review_vote SET claimed_user_id = :user_id, "
            "updated_at = (SELECT COALESCE(MAX(updated_at), 0) + 1 "
            "FROM anonymous_review_vote) "
            "WHERE voter_key = :voter_key AND claimed_user_id IS NULL"
        ),
        {"voter_key": review_session_key, "user_id": user_id},
    )
    return bool(result.rowcount)


def _clear_session_review_votes(review_session_key):
    """Clear the signed-cookie and process-local ledgers for this browser."""
    session.pop(_REVIEW_VOTES_SESSION, None)
    if review_session_key:
        for key in [
            key
            for key in _review_votes
            if key[:2] == ("session", review_session_key)
        ]:
            del _review_votes[key]


def _undo_session_review_votes(session_votes):
    """Undo anonymous yes-counts before discarding an unclaimable ledger."""
    review_ids = {
        _review_id_from_vote_identity(identity)
        for identity, vote in session_votes.items()
        if vote == "yes"
    }
    for review_id in review_ids:
        DrugReview.query.filter(DrugReview.id == review_id).update(
            {
                DrugReview.helpful_count: db.func.max(
                    0,
                    db.func.coalesce(DrugReview.helpful_count, 0) - 1,
                )
            },
            synchronize_session=False,
        )


def _claim_session_review_votes(user):
    """Merge this browser's anonymous votes into a newly authenticated user.

    Authenticated votes live in the existing preferences JSON so deduplication
    survives a site restart without adding a table that would mutate the seed
    database on boot. If the account had already voted, its earlier choice
    wins and any duplicate anonymous "yes" increment is removed.
    """
    previous_voter_id = _previous_review_voter_id()
    session.pop(_REVIEW_VOTER_SESSION, None)
    raw_session_votes = session.get(_REVIEW_VOTES_SESSION)
    session_votes = _valid_review_votes(raw_session_votes)
    server_backed_votes = _server_backed_session_vote_ids(raw_session_votes)
    review_session_key = _review_session_key(create=bool(session_votes))
    with _review_votes_lock:
        for review_identity, vote in _server_review_votes(
            review_session_key
        ).items():
            _remember_review_vote(session_votes, review_identity, vote)
            server_backed_votes.add(review_identity)
        if review_session_key:
            for key, vote in _review_votes.items():
                if key[:2] == ("session", review_session_key):
                    _remember_review_vote(
                        session_votes,
                        key[-1],
                        vote,
                    )
                    server_backed_votes.add(key[-1])
        session_votes = _prune_review_votes(session_votes)
        for review_identity in list(session_votes):
            if _server_review_vote_was_claimed(
                review_session_key, review_identity
            ):
                session_votes.pop(review_identity, None)
        if not session_votes:
            _clear_session_review_votes(review_session_key)
            return
        for review_identity, vote in session_votes.items():
            server_record = _server_review_vote_record(
                review_session_key, review_identity
            )
            if (
                server_record is None
                and review_identity in server_backed_votes
                and vote == "yes"
            ):
                review = db.session.get(
                    DrugReview,
                    _review_id_from_vote_identity(review_identity),
                )
                if (
                    review is not None
                    and _review_vote_identity(review) == review_identity
                ):
                    DrugReview.query.filter(
                        DrugReview.id == review.id
                    ).update(
                        {
                            DrugReview.helpful_count: db.func.coalesce(
                                DrugReview.helpful_count, 0
                            ) + 1
                        },
                        synchronize_session=False,
                    )
            if not _remember_server_review_vote(
                review_session_key, review_identity, vote
            ):
                _undo_session_review_votes(session_votes)
                # Existing rows must become tombstones before the browser
                # ledger is cleared; otherwise a later stale-cookie replay
                # could find a live "yes" row whose count was just undone.
                _claim_server_review_votes(review_session_key, -1)
                _clear_session_review_votes(review_session_key)
                db.session.commit()
                return
        # Post-logout votes are genuinely anonymous. A return to the same
        # account may reconcile them normally; a different account must not
        # inherit them, so discard their ledger and undo any yes increments.
        if previous_voter_id is not None and previous_voter_id != user.id:
            _undo_session_review_votes(session_votes)
            _claim_server_review_votes(review_session_key, -1)
            _clear_session_review_votes(review_session_key)
            db.session.commit()
            return
        with _user_settings_lock(user.id):
            db.session.refresh(user)
            preferences = user.preferences.copy()
            user_votes = _prune_review_votes(
                preferences.get(_REVIEW_VOTES_PREFERENCE),
                _MAX_REVIEW_VOTES,
            )
            for review_identity, anonymous_vote in session_votes.items():
                review = db.session.get(
                    DrugReview,
                    _review_id_from_vote_identity(review_identity),
                )
                if review is None or (
                    "-" in review_identity
                    and _review_vote_identity(review) != review_identity
                ):
                    continue
                current_identity = _review_vote_identity(review)
                if review.user_id == user.id:
                    # A genuinely anonymous browser cannot be recognized as
                    # the author until login. Remove that anonymous self-vote
                    # instead of claiming it for the owner.
                    user_votes.pop(str(review.id), None)
                    user_votes.pop(current_identity, None)
                    if anonymous_vote == "yes":
                        DrugReview.query.filter(
                            DrugReview.id == review.id
                        ).update(
                            {
                                DrugReview.helpful_count: db.func.max(
                                    0,
                                    db.func.coalesce(
                                        DrugReview.helpful_count, 0
                                    ) - 1,
                                )
                            },
                            synchronize_session=False,
                        )
                    continue
                legacy_user_vote = user_votes.pop(str(review.id), None)
                previous_user_vote = user_votes.get(
                    current_identity,
                    legacy_user_vote,
                )
                if previous_user_vote is None:
                    remembered = _remember_review_vote(
                        user_votes,
                        current_identity,
                        anonymous_vote,
                        _MAX_REVIEW_VOTES_PER_SESSION,
                    )
                    if not remembered and anonymous_vote == "yes":
                        DrugReview.query.filter(
                            DrugReview.id == review.id
                        ).update(
                            {
                                DrugReview.helpful_count: db.func.max(
                                    0,
                                    db.func.coalesce(
                                        DrugReview.helpful_count, 0
                                    ) - 1,
                                )
                            },
                            synchronize_session=False,
                        )
                elif anonymous_vote == "yes":
                    DrugReview.query.filter(DrugReview.id == review.id).update(
                        {
                            DrugReview.helpful_count: db.func.max(
                                0,
                                db.func.coalesce(
                                    DrugReview.helpful_count, 0
                                ) - 1,
                            )
                        },
                        synchronize_session=False,
                    )
            preferences[_REVIEW_VOTES_PREFERENCE] = user_votes
            user.set_preferences(preferences)
            _claim_server_review_votes(review_session_key, user.id)
            _clear_session_review_votes(review_session_key)
            db.session.commit()


@login_manager.user_loader
def load_user(uid):
    raw_id, separator, fingerprint = str(uid).partition(":")
    if not separator or not raw_id.isdigit() or not fingerprint:
        return None
    user = db.session.get(User, int(raw_id))
    if user is None:
        return None
    expected = user.get_id().partition(":")[2]
    return user if secrets.compare_digest(fingerprint, expected) else None


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
DRUG_CLASSES = [
    ("Nonsteroidal anti-inflammatory drugs", "NSAIDs reduce pain, inflammation, and fever by inhibiting cyclooxygenase enzymes."),
    ("Analgesics", "Analgesics relieve pain. They include opioid and non-opioid options."),
    ("Opioids", "Opioids are strong pain relievers that work on opioid receptors in the central nervous system."),
    ("Anticonvulsants", "Anticonvulsants treat seizures and are also used for nerve pain and mood disorders."),
    ("ACE inhibitors", "ACE inhibitors lower blood pressure by blocking the conversion of angiotensin I to angiotensin II."),
    ("Beta blockers", "Beta blockers slow the heart and reduce blood pressure by blocking adrenaline."),
    ("Calcium channel blockers", "Calcium channel blockers relax blood vessels and lower blood pressure."),
    ("Statins", "Statins lower cholesterol by inhibiting HMG-CoA reductase."),
    ("ARBs", "Angiotensin II receptor blockers lower blood pressure by blocking angiotensin II."),
    ("Diuretics", "Diuretics help the body remove excess salt and water through urine."),
    ("Anticoagulants", "Anticoagulants prevent dangerous blood clots."),
    ("Antiplatelet drugs", "Antiplatelet drugs prevent platelets from sticking together."),
    ("Biguanides", "Biguanides reduce glucose production in the liver. Metformin is the most common."),
    ("GLP-1 receptor agonists", "GLP-1 agonists improve blood sugar control and are used for type 2 diabetes and obesity."),
    ("SGLT2 inhibitors", "SGLT2 inhibitors lower blood sugar by causing the kidneys to remove glucose in urine."),
    ("DPP-4 inhibitors", "DPP-4 inhibitors increase insulin release after meals."),
    ("Insulins", "Insulin is a hormone replacement used to control blood glucose in diabetes."),
    ("SSRIs", "Selective serotonin reuptake inhibitors treat depression and anxiety."),
    ("SNRIs", "Serotonin and norepinephrine reuptake inhibitors treat depression, anxiety, and pain."),
    ("Atypical antidepressants", "Atypical antidepressants work via novel mechanisms."),
    ("Benzodiazepines", "Benzodiazepines treat anxiety, seizures, and insomnia."),
    ("Atypical antipsychotics", "Atypical antipsychotics treat schizophrenia, bipolar disorder, and other conditions."),
    ("Mood stabilizers", "Mood stabilizers manage bipolar disorder."),
    ("Tricyclic antidepressants", "TCAs treat depression and certain pain conditions."),
    ("Penicillins", "Penicillins are beta-lactam antibiotics."),
    ("Macrolides", "Macrolide antibiotics treat respiratory and skin infections."),
    ("Fluoroquinolones", "Fluoroquinolones treat a broad range of bacterial infections."),
    ("Tetracyclines", "Tetracyclines treat bacterial infections, acne, and other conditions."),
    ("Cephalosporins", "Cephalosporins are beta-lactam antibiotics related to penicillins."),
    ("Lincosamides", "Lincosamide antibiotics like clindamycin treat anaerobic and gram-positive infections."),
    ("Thyroid hormones", "Thyroid hormone replacements treat hypothyroidism."),
    ("Bronchodilators", "Bronchodilators relax airway muscles, easing breathing."),
    ("Leukotriene modifiers", "Leukotriene modifiers reduce asthma and allergy symptoms."),
    ("Corticosteroids", "Corticosteroids reduce inflammation and suppress the immune system."),
    ("Muscle relaxants", "Muscle relaxants reduce muscle spasms and pain."),
    ("Antiemetics", "Antiemetics prevent and treat nausea and vomiting."),
    ("PDE5 inhibitors", "PDE5 inhibitors treat erectile dysfunction and pulmonary hypertension."),
    ("5-alpha-reductase inhibitors", "5-ARIs treat benign prostatic hyperplasia and male pattern hair loss."),
    ("Alpha blockers", "Alpha blockers relax smooth muscle, helping with BPH and high blood pressure."),
    ("DMARDs", "Disease-modifying antirheumatic drugs slow autoimmune disease progression."),
    ("TNF inhibitors", "TNF inhibitors are biologics that block tumor necrosis factor."),
    ("Triptans", "Triptans treat migraine and cluster headaches."),
    ("Sleep aids", "Sleep aids help with short-term insomnia."),
    ("Opioid antagonists", "Opioid antagonists block opioid receptors; used for overdose reversal."),
    ("Stimulants", "Stimulants treat ADHD and narcolepsy."),
    ("Xanthine oxidase inhibitors", "Xanthine oxidase inhibitors lower uric acid in gout."),
    ("Retinoids", "Retinoids treat severe acne and other skin conditions."),
    ("Antihistamines", "Antihistamines relieve allergy symptoms by blocking histamine."),
    ("Proton pump inhibitors", "PPIs reduce stomach acid production."),
    ("H2 blockers", "H2 blockers reduce stomach acid by blocking histamine H2 receptors."),
    ("Decongestants", "Decongestants relieve nasal congestion."),
    ("Cough suppressants", "Cough suppressants reduce coughing."),
    ("Antimalarials", "Antimalarials treat malaria and certain autoimmune diseases."),
    ("Antimetabolites", "Antimetabolites disrupt cell metabolism; used in cancer and autoimmune diseases."),
    ("Monoclonal antibodies", "Monoclonal antibodies target specific molecules in disease."),
    ("Supplements", "Dietary supplements provide nutrients or substances like melatonin."),
    ("Antivirals", "Antivirals treat viral infections by inhibiting viral replication."),
    ("Antifungals", "Antifungals treat fungal infections."),
    ("Sulfonamides", "Sulfonamide antibiotics inhibit bacterial folate synthesis."),
    ("Nitroimidazoles", "Nitroimidazole antibiotics treat anaerobic bacterial and protozoal infections."),
    ("Immunosuppressants", "Immunosuppressants reduce immune system activity to prevent transplant rejection or treat autoimmune disease."),
    ("Biologics", "Biologic drugs are produced from living cells and target specific immune pathways."),
    ("Cardiac glycosides", "Cardiac glycosides increase cardiac contractility; digoxin is the prototype."),
    ("Nitrates", "Nitrates dilate blood vessels and are used in angina."),
    ("Antiarrhythmics", "Antiarrhythmics treat irregular heart rhythms."),
    ("Inhaled corticosteroids", "Inhaled corticosteroids reduce airway inflammation in asthma and COPD."),
    ("Anticholinergic bronchodilators", "Anticholinergic bronchodilators relax airway smooth muscle in COPD and asthma."),
    ("Nasal corticosteroids", "Nasal corticosteroids reduce nasal inflammation in allergic rhinitis."),
    ("Antidiarrheals", "Antidiarrheals slow intestinal motility and treat diarrhea."),
    ("Laxatives", "Laxatives relieve constipation."),
    ("Prokinetics", "Prokinetics enhance gastrointestinal motility."),
    ("Antacids", "Antacids neutralize stomach acid."),
    ("Anxiolytics", "Anxiolytics relieve anxiety; non-benzodiazepine options include buspirone."),
    ("Bisphosphonates", "Bisphosphonates strengthen bone and treat osteoporosis."),
    ("SERMs", "Selective estrogen receptor modulators act selectively on estrogen receptors."),
    ("Estrogens", "Estrogens are female sex hormones used in hormone therapy and contraception."),
    ("Progestogens", "Progestogens are female sex hormones used in contraception and hormone therapy."),
    ("Androgens", "Androgens are male sex hormones used for hypogonadism."),
    ("Contraceptives", "Contraceptives prevent pregnancy."),
    ("Fertility agents", "Fertility agents stimulate ovulation."),
    ("Prostaglandins", "Prostaglandins are hormone-like substances used in obstetrics and ophthalmology."),
    ("Antithyroid agents", "Antithyroid agents block thyroid hormone synthesis."),
    ("Topical corticosteroids", "Topical corticosteroids reduce skin inflammation."),
    ("Topical antibiotics", "Topical antibiotics treat localized bacterial skin infections."),
    ("Topical retinoids", "Topical retinoids treat acne and photoaging."),
    ("Acne treatments", "Acne treatments include benzoyl peroxide and other topical agents."),
    ("Ophthalmic beta blockers", "Ophthalmic beta blockers lower intraocular pressure in glaucoma."),
    ("Ophthalmic prostaglandins", "Ophthalmic prostaglandin analogues lower intraocular pressure."),
    ("Ophthalmic antibiotics", "Ophthalmic antibiotics treat bacterial eye infections."),
    ("Ophthalmic alpha agonists", "Ophthalmic alpha agonists lower intraocular pressure in glaucoma."),
    ("Hormones", "Hormones regulate physiological processes; includes oxytocin and calcitonin."),
    ("Iron supplements", "Iron supplements treat iron-deficiency anemia."),
    ("Vitamins", "Vitamins treat or prevent vitamin deficiencies."),
    ("ADHD non-stimulants", "Non-stimulant ADHD medications work via norepinephrine modulation."),
    ("Partial opioid agonists", "Partial opioid agonists treat opioid use disorder and pain."),
    ("Glycopeptide antibiotics", "Glycopeptide antibiotics treat serious gram-positive infections, including resistant strains, by inhibiting bacterial cell wall synthesis."),
    ("Antigout agents", "Antigout agents relieve or prevent gout flares by reducing inflammation or lowering uric acid."),
    ("Sulfonylureas", "Sulfonylureas lower blood sugar in type 2 diabetes by stimulating insulin release from the pancreas."),
    ("Urinary anti-infectives", "Urinary anti-infectives treat urinary tract infections, often concentrating in the urine rather than the bloodstream."),
    ("NMDA receptor antagonists", "NMDA receptor antagonists block glutamate signaling and are used to treat moderate to severe Alzheimer's disease."),
    ("Antibiotics", "Antibiotics kill or inhibit the growth of bacteria and are used to treat bacterial infections."),
    ("Amyloid beta-directed antibodies", "Amyloid beta-directed antibodies clear amyloid plaques from the brain and are used to slow early Alzheimer's disease."),
    ("Cholesterol absorption inhibitors", "Cholesterol absorption inhibitors lower LDL cholesterol by blocking its absorption in the small intestine."),
    ("Gallstone solubilizing agents", "Gallstone solubilizing agents dissolve cholesterol-based gallstones and are used for gallbladder and liver conditions."),
]


DRUGS_DATA = [
    # (generic_name, class_name, availability, csa, pronunciation, brand_names, conditions)
    ("ibuprofen", "Nonsteroidal anti-inflammatory drugs", "Rx and/or OTC", "Not a controlled drug", "eye-bue-PROE-fen", ["Advil", "Motrin", "Nuprin"], ["pain", "fever", "arthritis", "migraine"]),
    ("naproxen", "Nonsteroidal anti-inflammatory drugs", "Rx and/or OTC", "Not a controlled drug", "na-PROX-en", ["Aleve", "Naprosyn", "Anaprox"], ["pain", "arthritis", "gout"]),
    ("aspirin", "Nonsteroidal anti-inflammatory drugs", "OTC", "Not a controlled drug", "AS-pir-in", ["Bayer", "Bufferin", "Ecotrin"], ["pain", "fever", "heart_disease"]),
    ("meloxicam", "Nonsteroidal anti-inflammatory drugs", "Rx", "Not a controlled drug", "mel-OX-i-kam", ["Mobic", "Vivlodex"], ["arthritis", "pain"]),
    ("celecoxib", "Nonsteroidal anti-inflammatory drugs", "Rx", "Not a controlled drug", "sel-e-KOX-ib", ["Celebrex"], ["arthritis", "pain"]),
    ("acetaminophen", "Analgesics", "OTC", "Not a controlled drug", "a-seet-a-MIN-oh-fen", ["Tylenol", "Panadol"], ["pain", "fever"]),
    ("tramadol", "Opioids", "Rx", "C-IV", "TRAM-a-dol", ["Ultram", "ConZip"], ["pain"]),
    ("oxycodone", "Opioids", "Rx", "C-II", "ox-i-KOE-done", ["OxyContin", "Roxicodone", "Percocet"], ["pain"]),
    ("hydrocodone", "Opioids", "Rx", "C-II", "hye-droe-KOE-done", ["Vicodin", "Norco", "Lortab"], ["pain"]),
    ("gabapentin", "Anticonvulsants", "Rx", "Not a controlled drug", "GA-ba-PEN-tin", ["Neurontin", "Gralise"], ["epilepsy", "pain"]),
    ("pregabalin", "Anticonvulsants", "Rx", "C-V", "pre-GAB-a-lin", ["Lyrica"], ["pain", "epilepsy"]),
    ("lisinopril", "ACE inhibitors", "Rx", "Not a controlled drug", "lyse-IN-oh-pril", ["Zestril", "Prinivil"], ["hypertension", "heart_disease"]),
    ("enalapril", "ACE inhibitors", "Rx", "Not a controlled drug", "e-NAL-a-pril", ["Vasotec"], ["hypertension", "heart_disease"]),
    ("ramipril", "ACE inhibitors", "Rx", "Not a controlled drug", "RAM-i-pril", ["Altace"], ["hypertension", "heart_disease"]),
    ("captopril", "ACE inhibitors", "Rx", "Not a controlled drug", "KAP-toe-pril", ["Capoten"], ["hypertension", "heart_disease"]),
    ("benazepril", "ACE inhibitors", "Rx", "Not a controlled drug", "ben-AY-ze-pril", ["Lotensin"], ["hypertension"]),
    ("metoprolol", "Beta blockers", "Rx", "Not a controlled drug", "me-TOE-proe-lol", ["Lopressor", "Toprol XL"], ["hypertension", "heart_disease"]),
    ("amlodipine", "Calcium channel blockers", "Rx", "Not a controlled drug", "am-LOE-di-peen", ["Norvasc"], ["hypertension"]),
    ("atorvastatin", "Statins", "Rx", "Not a controlled drug", "a-TOR-va-sta-tin", ["Lipitor"], ["high_cholesterol", "heart_disease"]),
    ("rosuvastatin", "Statins", "Rx", "Not a controlled drug", "roe-SOO-va-sta-tin", ["Crestor"], ["high_cholesterol"]),
    ("losartan", "ARBs", "Rx", "Not a controlled drug", "loe-SAR-tan", ["Cozaar"], ["hypertension"]),
    ("carvedilol", "Beta blockers", "Rx", "Not a controlled drug", "KAR-ve-dil-ol", ["Coreg"], ["heart_disease", "hypertension"]),
    ("hydrochlorothiazide", "Diuretics", "Rx", "Not a controlled drug", "hye-droe-klor-oh-THYE-a-zide", ["Microzide"], ["hypertension"]),
    ("furosemide", "Diuretics", "Rx", "Not a controlled drug", "fur-OH-se-mide", ["Lasix"], ["heart_disease", "hypertension"]),
    ("warfarin", "Anticoagulants", "Rx", "Not a controlled drug", "WAR-far-in", ["Coumadin", "Jantoven"], ["heart_disease"]),
    ("clopidogrel", "Antiplatelet drugs", "Rx", "Not a controlled drug", "kloh-PID-oh-grel", ["Plavix"], ["heart_disease"]),
    ("spironolactone", "Diuretics", "Rx", "Not a controlled drug", "speer-on-oh-LAK-tone", ["Aldactone"], ["hypertension", "heart_disease"]),
    ("metformin", "Biguanides", "Rx", "Not a controlled drug", "met-FOR-min", ["Glucophage", "Fortamet", "Glumetza"], ["diabetes", "obesity"]),
    ("semaglutide", "GLP-1 receptor agonists", "Rx", "Not a controlled drug", "sem-a-GLOO-tide", ["Ozempic", "Wegovy", "Rybelsus"], ["diabetes", "obesity"]),
    ("tirzepatide", "GLP-1 receptor agonists", "Rx", "Not a controlled drug", "tir-ZEP-a-tide", ["Mounjaro", "Zepbound"], ["diabetes", "obesity"]),
    ("empagliflozin", "SGLT2 inhibitors", "Rx", "Not a controlled drug", "em-pa-gli-FLOE-zin", ["Jardiance"], ["diabetes", "heart_disease"]),
    ("sitagliptin", "DPP-4 inhibitors", "Rx", "Not a controlled drug", "sit-a-GLIP-tin", ["Januvia"], ["diabetes"]),
    ("insulin glargine", "Insulins", "Rx", "Not a controlled drug", "IN-su-lin GLAR-jeen", ["Lantus", "Basaglar", "Toujeo"], ["diabetes"]),
    ("sertraline", "SSRIs", "Rx", "Not a controlled drug", "SER-tra-leen", ["Zoloft"], ["depression", "anxiety"]),
    ("escitalopram", "SSRIs", "Rx", "Not a controlled drug", "es-sye-TAL-oh-pram", ["Lexapro"], ["depression", "anxiety"]),
    ("fluoxetine", "SSRIs", "Rx", "Not a controlled drug", "floo-OX-e-teen", ["Prozac", "Sarafem"], ["depression", "anxiety"]),
    ("duloxetine", "SNRIs", "Rx", "Not a controlled drug", "doo-LOX-e-teen", ["Cymbalta"], ["depression", "pain"]),
    ("bupropion", "Atypical antidepressants", "Rx", "Not a controlled drug", "byoo-PROE-pee-on", ["Wellbutrin", "Zyban"], ["depression"]),
    ("venlafaxine", "SNRIs", "Rx", "Not a controlled drug", "ven-la-FAX-een", ["Effexor"], ["depression", "anxiety"]),
    ("alprazolam", "Benzodiazepines", "Rx", "C-IV", "al-PRAY-zoe-lam", ["Xanax"], ["anxiety"]),
    ("clonazepam", "Benzodiazepines", "Rx", "C-IV", "kloe-NAZ-e-pam", ["Klonopin"], ["anxiety", "epilepsy"]),
    ("lorazepam", "Benzodiazepines", "Rx", "C-IV", "lor-AZ-e-pam", ["Ativan"], ["anxiety"]),
    ("quetiapine", "Atypical antipsychotics", "Rx", "Not a controlled drug", "kwe-TYE-a-peen", ["Seroquel"], ["schizophrenia", "bipolar_disorder"]),
    ("aripiprazole", "Atypical antipsychotics", "Rx", "Not a controlled drug", "ay-ri-PIP-ray-zole", ["Abilify"], ["schizophrenia", "bipolar_disorder", "depression"]),
    ("lithium", "Mood stabilizers", "Rx", "Not a controlled drug", "LITH-ee-um", ["Lithobid", "Eskalith"], ["bipolar_disorder"]),
    ("amitriptyline", "Tricyclic antidepressants", "Rx", "Not a controlled drug", "a-mee-TRIP-ti-leen", ["Elavil"], ["depression", "pain"]),
    ("amoxicillin", "Penicillins", "Rx", "Not a controlled drug", "a-mox-i-SIL-in", ["Amoxil", "Moxatag"], ["bacterial_infections"]),
    ("azithromycin", "Macrolides", "Rx", "Not a controlled drug", "az-ith-roe-MYE-sin", ["Zithromax", "Z-Pak"], ["bacterial_infections"]),
    ("ciprofloxacin", "Fluoroquinolones", "Rx", "Not a controlled drug", "sip-roe-FLOX-a-sin", ["Cipro"], ["bacterial_infections"]),
    ("doxycycline", "Tetracyclines", "Rx", "Not a controlled drug", "dox-i-SYE-kleen", ["Vibramycin", "Doryx"], ["bacterial_infections", "acne"]),
    ("clindamycin", "Lincosamides", "Rx", "Not a controlled drug", "klin-da-MYE-sin", ["Cleocin"], ["bacterial_infections", "acne"]),
    ("cephalexin", "Cephalosporins", "Rx", "Not a controlled drug", "sef-a-LEX-in", ["Keflex"], ["bacterial_infections"]),
    ("levothyroxine", "Thyroid hormones", "Rx", "Not a controlled drug", "lee-voe-thye-ROX-een", ["Synthroid", "Levoxyl"], ["hypothyroidism"]),
    ("albuterol", "Bronchodilators", "Rx", "Not a controlled drug", "al-BUE-ter-ol", ["ProAir", "Ventolin", "Proventil"], ["asthma"]),
    ("montelukast", "Leukotriene modifiers", "Rx", "Not a controlled drug", "mon-te-LOO-kast", ["Singulair"], ["asthma", "allergies"]),
    ("prednisone", "Corticosteroids", "Rx", "Not a controlled drug", "PRED-ni-sone", ["Deltasone", "Rayos"], ["arthritis", "allergies", "lupus"]),
    ("cyclobenzaprine", "Muscle relaxants", "Rx", "Not a controlled drug", "sye-kloe-BEN-za-preen", ["Flexeril", "Amrix"], ["pain"]),
    ("ondansetron", "Antiemetics", "Rx", "Not a controlled drug", "on-DAN-se-tron", ["Zofran"], ["cancer"]),
    ("sildenafil", "PDE5 inhibitors", "Rx", "Not a controlled drug", "sil-DEN-a-fil", ["Viagra", "Revatio"], ["erectile_dysfunction"]),
    ("finasteride", "5-alpha-reductase inhibitors", "Rx", "Not a controlled drug", "fi-NAS-teer-ide", ["Proscar", "Propecia"], ["bph"]),
    ("tamsulosin", "Alpha blockers", "Rx", "Not a controlled drug", "tam-SOO-loe-sin", ["Flomax"], ["bph"]),
    ("doxazosin", "Alpha blockers", "Rx", "Not a controlled drug", "dox-AY-zoe-sin", ["Cardura"], ["hypertension", "bph"]),
    ("diclofenac", "Nonsteroidal anti-inflammatory drugs", "Rx and/or OTC", "Not a controlled drug", "dye-KLOE-fen-ak", ["Voltaren", "Cataflam", "Cambia"], ["pain", "arthritis"]),
    ("memantine", "NMDA receptor antagonists", "Rx", "Not a controlled drug", "me-MAN-teen", ["Namenda", "Namenda XR"], ["dementia", "alzheimers"]),
    ("naltrexone", "Opioid antagonists", "Rx", "Not a controlled drug", "nal-TREX-one", ["Vivitrol", "ReVia"], ["addiction", "opioid_dependence"]),
    ("trimethoprim", "Antibiotics", "Rx", "Not a controlled drug", "trye-METH-oh-prim", ["Primsol", "Proloprim"], ["bacterial_infections"]),
    ("lecanemab", "Amyloid beta-directed antibodies", "Rx", "Not a controlled drug", "le-KAN-e-mab", ["Leqembi"], ["alzheimers"]),
    ("hydroxychloroquine", "Antimalarials", "Rx", "Not a controlled drug", "hye-drox-ee-KLOR-oh-kwin", ["Plaquenil"], ["lupus", "arthritis"]),
    ("methotrexate", "Antimetabolites", "Rx", "Not a controlled drug", "meth-oh-TREX-ate", ["Trexall", "Otrexup"], ["arthritis", "psoriasis", "cancer"]),
    ("adalimumab", "TNF inhibitors", "Rx", "Not a controlled drug", "a-da-LIM-ue-mab", ["Humira"], ["arthritis", "crohns_disease", "psoriasis"]),
    ("dupilumab", "Monoclonal antibodies", "Rx", "Not a controlled drug", "doo-PIL-ue-mab", ["Dupixent"], ["eczema", "asthma"]),
    ("sumatriptan", "Triptans", "Rx", "Not a controlled drug", "soo-ma-TRIP-tan", ["Imitrex"], ["migraine"]),
    ("zolpidem", "Sleep aids", "Rx", "C-IV", "zole-PI-dem", ["Ambien"], ["insomnia"]),
    ("naloxone", "Opioid antagonists", "Rx and/or OTC", "Not a controlled drug", "nal-OX-one", ["Narcan", "Evzio"], []),
    ("methylphenidate", "Stimulants", "Rx", "C-II", "meth-il-FEN-i-date", ["Ritalin", "Concerta"], ["adhd"]),
    ("colchicine", "Antigout agents", "Rx", "Not a controlled drug", "KOL-chi-seen", ["Colcrys", "Mitigare"], ["gout"]),
    ("allopurinol", "Xanthine oxidase inhibitors", "Rx", "Not a controlled drug", "al-oh-PURE-i-nol", ["Zyloprim"], ["gout"]),
    ("isotretinoin", "Retinoids", "Rx", "Not a controlled drug", "eye-soe-tret-IN-oh-in", ["Accutane", "Claravis"], ["acne"]),
    ("diphenhydramine", "Antihistamines", "OTC", "Not a controlled drug", "dye-fen-HYE-dra-meen", ["Benadryl"], ["allergies", "insomnia"]),
    ("loratadine", "Antihistamines", "OTC", "Not a controlled drug", "lor-AT-a-deen", ["Claritin", "Alavert"], ["allergies"]),
    ("cetirizine", "Antihistamines", "OTC", "Not a controlled drug", "se-TIR-i-zeen", ["Zyrtec"], ["allergies"]),
    ("omeprazole", "Proton pump inhibitors", "Rx and/or OTC", "Not a controlled drug", "oh-MEP-ra-zole", ["Prilosec"], ["acid_reflux"]),
    ("famotidine", "H2 blockers", "Rx and/or OTC", "Not a controlled drug", "fa-MOE-ti-deen", ["Pepcid"], ["acid_reflux"]),
    ("melatonin", "Supplements", "OTC", "Not a controlled drug", "mel-a-TOE-nin", ["Natrol Melatonin"], ["insomnia"]),
    ("pseudoephedrine", "Decongestants", "OTC", "Not a controlled drug", "soo-doe-e-FED-rin", ["Sudafed"], ["allergies"]),
    ("dextromethorphan", "Cough suppressants", "OTC", "Not a controlled drug", "dex-troe-meth-OR-fan", ["Robitussin DM", "Delsym"], []),
    ("citalopram", "SSRIs", "Rx", "Not a controlled drug", "sye-TAL-oh-pram", ["Celexa"], ["depression", "anxiety"]),
    ("trazodone", "Atypical antidepressants", "Rx", "Not a controlled drug", "TRAZ-oh-done", ["Desyrel", "Oleptro"], ["depression", "insomnia"]),
    ("lamotrigine", "Anticonvulsants", "Rx", "Not a controlled drug", "la-MOE-tri-jeen", ["Lamictal"], ["epilepsy", "bipolar_disorder"]),
    ("topiramate", "Anticonvulsants", "Rx", "Not a controlled drug", "toe-PYRE-a-mate", ["Topamax"], ["epilepsy", "migraine"]),
    ("verapamil", "Calcium channel blockers", "Rx", "Not a controlled drug", "ver-AP-a-mil", ["Calan", "Verelan"], ["hypertension", "heart_disease"]),
    # --- Expanded catalog ---
    ("methylprednisolone", "Corticosteroids", "Rx", "Not a controlled drug", "meth-il-pred-NIS-oh-lone", ["Medrol", "Solu-Medrol"], ["arthritis", "allergies", "lupus"]),
    ("dexamethasone", "Corticosteroids", "Rx", "Not a controlled drug", "dex-a-METH-a-sone", ["Decadron", "DexPak"], ["arthritis", "allergies", "cancer"]),
    ("hydrocortisone", "Topical corticosteroids", "Rx and/or OTC", "Not a controlled drug", "hye-droe-KOR-ti-sone", ["Cortizone-10", "Cortaid"], ["eczema", "psoriasis"]),
    ("triamcinolone", "Topical corticosteroids", "Rx", "Not a controlled drug", "trye-am-SIN-oh-lone", ["Kenalog", "Aristocort"], ["eczema", "psoriasis", "allergies"]),
    ("cyclosporine", "Immunosuppressants", "Rx", "Not a controlled drug", "sye-kloe-SPOR-een", ["Neoral", "Sandimmune", "Gengraf"], ["psoriasis", "arthritis"]),
    ("tacrolimus", "Immunosuppressants", "Rx", "Not a controlled drug", "ta-KROE-li-mus", ["Prograf", "Astagraf XL"], ["eczema"]),
    ("mycophenolate", "Immunosuppressants", "Rx", "Not a controlled drug", "mye-koe-FEN-oh-late", ["CellCept", "Myfortic"], ["lupus"]),
    ("rituximab", "Biologics", "Rx", "Not a controlled drug", "ri-TUX-i-mab", ["Rituxan"], ["arthritis", "cancer", "lupus"]),
    ("insulin aspart", "Insulins", "Rx", "Not a controlled drug", "IN-su-lin AS-part", ["NovoLog", "Fiasp"], ["diabetes"]),
    ("insulin lispro", "Insulins", "Rx", "Not a controlled drug", "IN-su-lin LYE-sproe", ["Humalog", "Admelog"], ["diabetes"]),
    ("canagliflozin", "SGLT2 inhibitors", "Rx", "Not a controlled drug", "kan-a-gli-FLOE-zin", ["Invokana"], ["diabetes"]),
    ("dapagliflozin", "SGLT2 inhibitors", "Rx", "Not a controlled drug", "dap-a-gli-FLOE-zin", ["Farxiga"], ["diabetes", "heart_disease"]),
    ("liraglutide", "GLP-1 receptor agonists", "Rx", "Not a controlled drug", "lir-a-GLOO-tide", ["Victoza", "Saxenda"], ["diabetes", "obesity"]),
    ("glipizide", "Sulfonylureas", "Rx", "Not a controlled drug", "GLIP-i-zide", ["Glucotrol"], ["diabetes"]),
    ("pravastatin", "Statins", "Rx", "Not a controlled drug", "PRA-va-sta-tin", ["Pravachol"], ["high_cholesterol"]),
    ("simvastatin", "Statins", "Rx", "Not a controlled drug", "SIM-va-sta-tin", ["Zocor"], ["high_cholesterol"]),
    ("ezetimibe", "Cholesterol absorption inhibitors", "Rx", "Not a controlled drug", "ez-ET-i-mibe", ["Zetia"], ["high_cholesterol"]),
    ("valsartan", "ARBs", "Rx", "Not a controlled drug", "val-SAR-tan", ["Diovan"], ["hypertension", "heart_disease"]),
    ("olmesartan", "ARBs", "Rx", "Not a controlled drug", "ole-me-SAR-tan", ["Benicar"], ["hypertension"]),
    ("irbesartan", "ARBs", "Rx", "Not a controlled drug", "ir-be-SAR-tan", ["Avapro"], ["hypertension"]),
    ("atenolol", "Beta blockers", "Rx", "Not a controlled drug", "a-TEN-oh-lol", ["Tenormin"], ["hypertension", "heart_disease"]),
    ("propranolol", "Beta blockers", "Rx", "Not a controlled drug", "proe-PRAN-oh-lol", ["Inderal"], ["hypertension", "migraine"]),
    ("bisoprolol", "Beta blockers", "Rx", "Not a controlled drug", "bis-OH-proe-lol", ["Zebeta"], ["hypertension", "heart_disease"]),
    ("diltiazem", "Calcium channel blockers", "Rx", "Not a controlled drug", "dil-TYE-a-zem", ["Cardizem", "Tiazac"], ["hypertension", "heart_disease"]),
    ("nifedipine", "Calcium channel blockers", "Rx", "Not a controlled drug", "nye-FED-i-peen", ["Procardia", "Adalat"], ["hypertension"]),
    ("digoxin", "Cardiac glycosides", "Rx", "Not a controlled drug", "di-JOX-in", ["Lanoxin"], ["heart_disease"]),
    ("nitroglycerin", "Nitrates", "Rx", "Not a controlled drug", "nye-troe-GLI-ser-in", ["Nitrostat", "Nitro-Dur", "Nitrolingual"], ["heart_disease"]),
    ("isosorbide", "Nitrates", "Rx", "Not a controlled drug", "eye-soe-SOR-bide", ["Isordil", "Imdur"], ["heart_disease"]),
    ("amiodarone", "Antiarrhythmics", "Rx", "Not a controlled drug", "a-MEE-oh-da-rone", ["Cordarone", "Pacerone"], ["heart_disease"]),
    ("apixaban", "Anticoagulants", "Rx", "Not a controlled drug", "a-PIX-a-ban", ["Eliquis"], ["blood_clots", "heart_disease"]),
    ("rivaroxaban", "Anticoagulants", "Rx", "Not a controlled drug", "riv-a-ROX-a-ban", ["Xarelto"], ["blood_clots"]),
    ("dabigatran", "Anticoagulants", "Rx", "Not a controlled drug", "da-BIG-a-tran", ["Pradaxa"], ["blood_clots"]),
    ("enoxaparin", "Anticoagulants", "Rx", "Not a controlled drug", "ee-nox-a-PA-rin", ["Lovenox"], ["blood_clots"]),
    ("pantoprazole", "Proton pump inhibitors", "Rx", "Not a controlled drug", "pan-TOE-pra-zole", ["Protonix"], ["acid_reflux"]),
    ("esomeprazole", "Proton pump inhibitors", "Rx and/or OTC", "Not a controlled drug", "es-oh-MEP-ra-zole", ["Nexium"], ["acid_reflux"]),
    ("lansoprazole", "Proton pump inhibitors", "Rx and/or OTC", "Not a controlled drug", "lan-SOE-pra-zole", ["Prevacid"], ["acid_reflux"]),
    ("ranitidine", "H2 blockers", "Rx", "Not a controlled drug", "ra-NI-ti-deen", ["Zantac"], ["acid_reflux"]),
    ("metoclopramide", "Prokinetics", "Rx", "Not a controlled drug", "met-oh-kloe-PRA-mide", ["Reglan"], ["acid_reflux", "nausea"]),
    ("loperamide", "Antidiarrheals", "OTC", "Not a controlled drug", "loe-PER-a-mide", ["Imodium"], ["diarrhea"]),
    ("bisacodyl", "Laxatives", "OTC", "Not a controlled drug", "bis-AK-oh-dil", ["Dulcolax"], ["constipation"]),
    ("polyethylene glycol", "Laxatives", "OTC", "Not a controlled drug", "pol-ee-ETH-i-leen GLYE-kol", ["MiraLax"], ["constipation"]),
    ("docusate", "Laxatives", "OTC", "Not a controlled drug", "DOK-yoo-sate", ["Colace"], ["constipation"]),
    ("calcium carbonate", "Antacids", "OTC", "Not a controlled drug", "KAL-see-um KAR-bon-ate", ["Tums", "Caltrate"], ["acid_reflux", "vitamin_deficiency"]),
    ("magnesium oxide", "Supplements", "OTC", "Not a controlled drug", "mag-NEE-zee-um OX-ide", ["Mag-Ox"], ["vitamin_deficiency", "constipation"]),
    ("fexofenadine", "Antihistamines", "OTC", "Not a controlled drug", "fex-oh-FEN-a-deen", ["Allegra"], ["allergies"]),
    ("hydroxyzine", "Antihistamines", "Rx", "Not a controlled drug", "hye-DROX-i-zeen", ["Vistaril", "Atarax"], ["anxiety", "allergies"]),
    ("fluticasone", "Nasal corticosteroids", "Rx and/or OTC", "Not a controlled drug", "floo-TIK-a-sone", ["Flonase", "Flovent"], ["allergies", "asthma"]),
    ("budesonide", "Inhaled corticosteroids", "Rx", "Not a controlled drug", "byoo-DES-oh-nide", ["Pulmicort", "Rhinocort"], ["asthma", "copd"]),
    ("tiotropium", "Anticholinergic bronchodilators", "Rx", "Not a controlled drug", "ty-oh-TROE-pee-um", ["Spiriva"], ["copd", "asthma"]),
    ("ipratropium", "Anticholinergic bronchodilators", "Rx", "Not a controlled drug", "i-pra-TROE-pee-um", ["Atrovent"], ["copd", "asthma"]),
    ("salmeterol", "Bronchodilators", "Rx", "Not a controlled drug", "sal-MEE-ter-ol", ["Serevent"], ["asthma", "copd"]),
    ("levofloxacin", "Fluoroquinolones", "Rx", "Not a controlled drug", "lee-voe-FLOX-a-sin", ["Levaquin"], ["bacterial_infections"]),
    ("moxifloxacin", "Fluoroquinolones", "Rx", "Not a controlled drug", "mox-i-FLOX-a-sin", ["Avelox"], ["bacterial_infections"]),
    ("trimethoprim-sulfamethoxazole", "Sulfonamides", "Rx", "Not a controlled drug", "trye-METH-oh-prim sul-fa-meth-OX-a-zole", ["Bactrim", "Septra"], ["bacterial_infections"]),
    ("metronidazole", "Nitroimidazoles", "Rx", "Not a controlled drug", "me-troe-NI-da-zole", ["Flagyl"], ["bacterial_infections"]),
    ("nitrofurantoin", "Urinary anti-infectives", "Rx", "Not a controlled drug", "nye-troe-fyoor-AN-toyn", ["Macrobid", "Macrodantin"], ["bacterial_infections"]),
    ("penicillin", "Penicillins", "Rx", "Not a controlled drug", "pen-i-SIL-in", ["Penicillin VK"], ["bacterial_infections"]),
    ("ampicillin", "Penicillins", "Rx", "Not a controlled drug", "am-pi-SIL-in", ["Principen"], ["bacterial_infections"]),
    ("amoxicillin-clavulanate", "Penicillins", "Rx", "Not a controlled drug", "a-mox-i-SIL-in klav-yoo-LAN-ate", ["Augmentin"], ["bacterial_infections"]),
    ("ceftriaxone", "Cephalosporins", "Rx", "Not a controlled drug", "sef-trye-AX-one", ["Rocephin"], ["bacterial_infections"]),
    ("vancomycin", "Glycopeptide antibiotics", "Rx", "Not a controlled drug", "van-koe-MYE-sin", ["Vancocin"], ["bacterial_infections"]),
    ("fluconazole", "Antifungals", "Rx", "Not a controlled drug", "floo-KOE-na-zole", ["Diflucan"], ["fungal_infections"]),
    ("terbinafine", "Antifungals", "Rx and/or OTC", "Not a controlled drug", "ter-BIN-a-feen", ["Lamisil"], ["fungal_infections"]),
    ("ketoconazole", "Antifungals", "Rx and/or OTC", "Not a controlled drug", "kee-toe-KOE-na-zole", ["Nizoral"], ["fungal_infections"]),
    ("nystatin", "Antifungals", "Rx", "Not a controlled drug", "nye-STAT-in", ["Mycostatin"], ["fungal_infections"]),
    ("acyclovir", "Antivirals", "Rx", "Not a controlled drug", "ay-SYE-kloe-veer", ["Zovirax"], ["herpes"]),
    ("valacyclovir", "Antivirals", "Rx", "Not a controlled drug", "val-ay-SYE-kloe-veer", ["Valtrex"], ["herpes"]),
    ("oseltamivir", "Antivirals", "Rx", "Not a controlled drug", "oh-sel-TAM-i-veer", ["Tamiflu"], ["influenza"]),
    ("tenofovir", "Antivirals", "Rx", "Not a controlled drug", "te-NOE-foe-veer", ["Viread"], ["viral_infections"]),
    ("tadalafil", "PDE5 inhibitors", "Rx", "Not a controlled drug", "tah-DAL-a-fil", ["Cialis", "Adcirca"], ["erectile_dysfunction", "bph"]),
    ("vardenafil", "PDE5 inhibitors", "Rx", "Not a controlled drug", "var-DEN-a-fil", ["Levitra"], ["erectile_dysfunction"]),
    ("morphine", "Opioids", "Rx", "C-II", "MOR-feen", ["MS Contin", "Roxanol"], ["pain"]),
    ("fentanyl", "Opioids", "Rx", "C-II", "FEN-ta-nil", ["Duragesic", "Sublimaze"], ["pain"]),
    ("codeine", "Opioids", "Rx", "C-II", "KOE-deen", ["Codeine sulfate"], ["pain"]),
    ("buprenorphine", "Partial opioid agonists", "Rx", "C-III", "byoo-pre-NOR-feen", ["Suboxone", "Subutex"], ["opioid_dependence", "pain"]),
    ("methadone", "Opioids", "Rx", "C-II", "METH-a-done", ["Dolophine", "Methadose"], ["opioid_dependence", "pain"]),
    ("amphetamine-dextroamphetamine", "Stimulants", "Rx", "C-II", "am-FET-a-meen dex-troe-am-FET-a-meen", ["Adderall"], ["adhd"]),
    ("lisdexamfetamine", "Stimulants", "Rx", "C-II", "lis-dex-am-FET-a-meen", ["Vyvanse"], ["adhd"]),
    ("atomoxetine", "ADHD non-stimulants", "Rx", "Not a controlled drug", "at-oh-MOX-e-teen", ["Strattera"], ["adhd"]),
    ("guanfacine", "ADHD non-stimulants", "Rx", "Not a controlled drug", "GWAN-fa-seen", ["Intuniv", "Tenex"], ["adhd", "hypertension"]),
    ("valproic acid", "Anticonvulsants", "Rx", "Not a controlled drug", "val-PROE-ik AS-id", ["Depakote", "Depakene"], ["epilepsy", "bipolar_disorder", "migraine"]),
    ("levetiracetam", "Anticonvulsants", "Rx", "Not a controlled drug", "lee-ve-tye-RA-se-tam", ["Keppra"], ["epilepsy"]),
    ("carbamazepine", "Anticonvulsants", "Rx", "Not a controlled drug", "kar-ba-MAZ-e-peen", ["Tegretol", "Carbatrol"], ["epilepsy", "bipolar_disorder"]),
    ("phenytoin", "Anticonvulsants", "Rx", "Not a controlled drug", "FEN-i-toyn", ["Dilantin"], ["epilepsy"]),
    ("paroxetine", "SSRIs", "Rx", "Not a controlled drug", "pa-ROX-e-teen", ["Paxil"], ["depression", "anxiety"]),
    ("mirtazapine", "Atypical antidepressants", "Rx", "Not a controlled drug", "mir-TAZ-a-peen", ["Remeron"], ["depression"]),
    ("olanzapine", "Atypical antipsychotics", "Rx", "Not a controlled drug", "oh-LAN-za-peen", ["Zyprexa"], ["schizophrenia", "bipolar_disorder"]),
    ("risperidone", "Atypical antipsychotics", "Rx", "Not a controlled drug", "ris-PER-i-done", ["Risperdal"], ["schizophrenia", "bipolar_disorder"]),
    ("haloperidol", "Atypical antipsychotics", "Rx", "Not a controlled drug", "ha-loe-PER-i-dol", ["Haldol"], ["schizophrenia"]),
    ("ziprasidone", "Atypical antipsychotics", "Rx", "Not a controlled drug", "zi-PRAS-i-done", ["Geodon"], ["schizophrenia", "bipolar_disorder"]),
    ("diazepam", "Benzodiazepines", "Rx", "C-IV", "dye-AZ-e-pam", ["Valium"], ["anxiety", "muscle_spasm"]),
    ("temazepam", "Benzodiazepines", "Rx", "C-IV", "tem-AZ-e-pam", ["Restoril"], ["insomnia"]),
    ("buspirone", "Anxiolytics", "Rx", "Not a controlled drug", "byoo-SPYE-rone", ["Buspar"], ["anxiety"]),
    ("eszopiclone", "Sleep aids", "Rx", "C-IV", "es-zoe-PIK-lone", ["Lunesta"], ["insomnia"]),
    ("methocarbamol", "Muscle relaxants", "Rx", "Not a controlled drug", "meth-oh-KAR-ba-mol", ["Robaxin"], ["muscle_spasm", "pain"]),
    ("baclofen", "Muscle relaxants", "Rx", "Not a controlled drug", "BAK-loe-fen", ["Lioresal", "Gablofen"], ["muscle_spasm"]),
    ("tizanidine", "Muscle relaxants", "Rx", "Not a controlled drug", "tye-ZAN-i-deen", ["Zanaflex"], ["muscle_spasm"]),
    ("carisoprodol", "Muscle relaxants", "Rx", "C-IV", "kar-eye-soe-PROE-dol", ["Soma"], ["muscle_spasm", "pain"]),
    ("alendronate", "Bisphosphonates", "Rx", "Not a controlled drug", "a-LEN-droe-nate", ["Fosamax"], ["osteoporosis"]),
    ("risedronate", "Bisphosphonates", "Rx", "Not a controlled drug", "ris-ED-roe-nate", ["Actonel"], ["osteoporosis"]),
    ("zoledronic acid", "Bisphosphonates", "Rx", "Not a controlled drug", "zoe-le-DROE-nik AS-id", ["Reclast", "Zometa"], ["osteoporosis", "cancer"]),
    ("raloxifene", "SERMs", "Rx", "Not a controlled drug", "ral-OX-i-feen", ["Evista"], ["osteoporosis"]),
    ("calcitonin", "Hormones", "Rx", "Not a controlled drug", "kal-si-TOE-nin", ["Miacalcin", "Fortical"], ["osteoporosis"]),
    ("estradiol", "Estrogens", "Rx", "Not a controlled drug", "es-tra-DYE-ol", ["Estrace", "Vivelle-Dot"], ["menopause", "contraception"]),
    ("progesterone", "Progestogens", "Rx", "Not a controlled drug", "proe-JES-ter-one", ["Prometrium"], ["menopause", "contraception"]),
    ("testosterone", "Androgens", "Rx", "C-III", "tes-TOS-ter-one", ["AndroGel", "Testim"], ["low_testosterone"]),
    ("ethinyl estradiol-norethindrone", "Contraceptives", "Rx", "Not a controlled drug", "ETH-in-il es-tra-DYE-ol nor-eth-IN-drone", ["Ortho-Novum", "Loestrin"], ["contraception"]),
    ("levonorgestrel", "Contraceptives", "OTC", "Not a controlled drug", "lee-voe-nor-JES-trel", ["Plan B", "Mirena"], ["contraception"]),
    ("norethindrone", "Progestogens", "Rx", "Not a controlled drug", "nor-eth-IN-drone", ["Aygestin"], ["contraception", "menopause"]),
    ("clomiphene", "Fertility agents", "Rx", "Not a controlled drug", "KLOE-mi-feen", ["Clomid"], []),
    ("misoprostol", "Prostaglandins", "Rx", "Not a controlled drug", "mye-soe-PROST-ole", ["Cytotec"], []),
    ("oxytocin", "Hormones", "Rx", "Not a controlled drug", "ox-i-TOE-sin", ["Pitocin"], []),
    ("methimazole", "Antithyroid agents", "Rx", "Not a controlled drug", "meth-IM-a-zole", ["Tapazole"], ["hyperthyroidism"]),
    ("propylthiouracil", "Antithyroid agents", "Rx", "Not a controlled drug", "proe-pil-thye-oh-YOOR-a-sil", ["PTU"], ["hyperthyroidism"]),
    ("desiccated thyroid", "Thyroid hormones", "Rx", "Not a controlled drug", "DES-i-kay-ted THYE-roid", ["Armour Thyroid", "Nature-Throid"], ["hypothyroidism"]),
    ("mupirocin", "Topical antibiotics", "Rx", "Not a controlled drug", "myoo-PEER-oh-sin", ["Bactroban"], ["bacterial_infections"]),
    ("bacitracin", "Topical antibiotics", "OTC", "Not a controlled drug", "bas-i-TRAY-sin", ["Neosporin"], ["bacterial_infections"]),
    ("tretinoin", "Topical retinoids", "Rx", "Not a controlled drug", "TRET-i-noyn", ["Retin-A", "Renova"], ["acne"]),
    ("adapalene", "Topical retinoids", "Rx and/or OTC", "Not a controlled drug", "a-DAP-a-leen", ["Differin"], ["acne"]),
    ("benzoyl peroxide", "Acne treatments", "OTC", "Not a controlled drug", "BEN-zoe-il per-OX-ide", ["Clearasil", "PanOxyl"], ["acne"]),
    ("timolol", "Ophthalmic beta blockers", "Rx", "Not a controlled drug", "TYE-moe-lol", ["Timoptic", "Istalol"], ["glaucoma"]),
    ("latanoprost", "Ophthalmic prostaglandins", "Rx", "Not a controlled drug", "la-TAN-oh-prost", ["Xalatan"], ["glaucoma"]),
    ("bimatoprost", "Ophthalmic prostaglandins", "Rx", "Not a controlled drug", "bi-MAT-oh-prost", ["Lumigan", "Latisse"], ["glaucoma"]),
    ("brimonidine", "Ophthalmic alpha agonists", "Rx", "Not a controlled drug", "bri-MOE-ni-deen", ["Alphagan"], ["glaucoma"]),
    ("ofloxacin ophthalmic", "Ophthalmic antibiotics", "Rx", "Not a controlled drug", "oh-FLOX-a-sin", ["Ocuflox"], ["bacterial_infections"]),
    ("tobramycin ophthalmic", "Ophthalmic antibiotics", "Rx", "Not a controlled drug", "toe-bra-MYE-sin", ["Tobrex"], ["bacterial_infections"]),
    ("vitamin D3", "Vitamins", "OTC", "Not a controlled drug", "VYE-ta-min D3", ["D-Vi-Sol", "Drisdol"], ["vitamin_deficiency", "osteoporosis"]),
    ("folic acid", "Vitamins", "OTC", "Not a controlled drug", "FOE-lik AS-id", ["Folvite"], ["vitamin_deficiency", "anemia"]),
    ("ferrous sulfate", "Iron supplements", "OTC", "Not a controlled drug", "FER-us SUL-fate", ["Slow FE", "Feosol"], ["anemia"]),
    ("vitamin B12", "Vitamins", "OTC", "Not a controlled drug", "VYE-ta-min B12", ["Cyanoject", "Nascobal"], ["vitamin_deficiency", "anemia"]),
    ("multivitamin", "Vitamins", "OTC", "Not a controlled drug", "mul-tee-VYE-ta-min", ["Centrum", "One A Day"], ["vitamin_deficiency"]),
    # DMARDs (bring class from 0 to 3)
    ("sulfasalazine", "DMARDs", "Rx", "Not a controlled drug", "sul-fa-SAL-a-zeen", ["Azulfidine"], ["arthritis", "crohns_disease"]),
    ("leflunomide", "DMARDs", "Rx", "Not a controlled drug", "le-FLOO-no-mide", ["Arava"], ["arthritis"]),
    ("tofacitinib", "DMARDs", "Rx", "Not a controlled drug", "toe-fa-SYE-ti-nib", ["Xeljanz"], ["arthritis", "psoriasis"]),
    # Tetracyclines (1 -> 3)
    ("minocycline", "Tetracyclines", "Rx", "Not a controlled drug", "mi-noe-SYE-kleen", ["Minocin", "Solodyn"], ["acne", "bacterial_infections"]),
    ("tetracycline", "Tetracyclines", "Rx", "Not a controlled drug", "tet-ra-SYE-kleen", ["Sumycin"], ["bacterial_infections", "acne"]),
    # Macrolides (1 -> 3)
    ("clarithromycin", "Macrolides", "Rx", "Not a controlled drug", "kla-RITH-roe-mye-sin", ["Biaxin"], ["bacterial_infections"]),
    ("erythromycin", "Macrolides", "Rx", "Not a controlled drug", "er-ith-roe-MYE-sin", ["Ery-Tab", "Erythrocin"], ["bacterial_infections", "acne"]),
    # Triptans (1 -> 4)
    ("rizatriptan", "Triptans", "Rx", "Not a controlled drug", "rye-za-TRIP-tan", ["Maxalt"], ["migraine"]),
    ("eletriptan", "Triptans", "Rx", "Not a controlled drug", "el-e-TRIP-tan", ["Relpax"], ["migraine"]),
    ("zolmitriptan", "Triptans", "Rx", "Not a controlled drug", "zole-mi-TRIP-tan", ["Zomig"], ["migraine"]),
    # SNRIs (2 -> 4)
    ("desvenlafaxine", "SNRIs", "Rx", "Not a controlled drug", "des-ven-la-FAX-een", ["Pristiq", "Khedezla"], ["depression"]),
    ("milnacipran", "SNRIs", "Rx", "Not a controlled drug", "mil-NA-si-pran", ["Savella"], ["pain"]),
    # Thyroid hormones (2 -> 3)
    ("liothyronine", "Thyroid hormones", "Rx", "Not a controlled drug", "lye-oh-THYE-roe-neen", ["Cytomel"], ["hypothyroidism"]),
    # Bronchodilators (2 -> 3)
    ("formoterol", "Bronchodilators", "Rx", "Not a controlled drug", "for-MOE-te-rol", ["Foradil", "Perforomist"], ["asthma", "copd"]),
    # Diuretics (3 -> 5)
    ("chlorthalidone", "Diuretics", "Rx", "Not a controlled drug", "klor-THAL-i-done", ["Thalitone"], ["hypertension"]),
    ("indapamide", "Diuretics", "Rx", "Not a controlled drug", "in-DAP-a-mide", ["Lozol"], ["hypertension", "heart_disease"]),
    # Sleep aids (2 -> 4)
    ("ramelteon", "Sleep aids", "Rx", "Not a controlled drug", "ra-MEL-tee-on", ["Rozerem"], ["insomnia"]),
    ("suvorexant", "Sleep aids", "Rx", "C-IV", "soo-voe-REX-ant", ["Belsomra"], ["insomnia"]),
    # J drugs
    ("janumet", "Biguanides", "Rx", "Not a controlled drug", "JAN-yoo-met", ["Sitagliptin/Metformin"], ["diabetes"]),
    # U drugs
    ("ursodiol", "Gallstone solubilizing agents", "Rx", "Not a controlled drug", "ur-SOE-dee-ol", ["Actigall", "URSO 250"], ["gallstones"]),
    ("umeclidinium", "Anticholinergic bronchodilators", "Rx", "Not a controlled drug", "ue-mek-li-DIN-ee-um", ["Incruse Ellipta"], ["copd"]),
    ("ulipristal", "Progestogens", "Rx", "Not a controlled drug", "ue-LIP-ri-stal", ["Ella"], ["contraception"]),
    # Y drugs
    ("yaz", "Contraceptives", "Rx", "Not a controlled drug", "YAZ", ["Drospirenone/Ethinyl estradiol"], ["contraception"]),
    ("yasmin", "Contraceptives", "Rx", "Not a controlled drug", "YAZ-min", ["Drospirenone/Ethinyl estradiol"], ["contraception"]),
]


CONDITIONS_DATA = [
    ("pain", "Pain", "Pain is an unpleasant sensory and emotional experience. Many drugs treat acute and chronic pain."),
    ("fever", "Fever", "Fever is a temporary increase in body temperature, often due to illness."),
    ("hypertension", "Hypertension (High Blood Pressure)", "Hypertension is a long-term condition where blood pressure in the arteries is persistently elevated."),
    ("diabetes", "Diabetes (Type 2)", "Type 2 diabetes is a chronic condition that affects how the body metabolizes glucose."),
    ("depression", "Depression", "Depression is a mood disorder causing persistent feelings of sadness and loss of interest."),
    ("anxiety", "Anxiety", "Anxiety disorders involve excessive worry or fear that interferes with daily activities."),
    ("high_cholesterol", "High Cholesterol", "High cholesterol increases the risk of heart disease and stroke."),
    ("heart_disease", "Heart Disease", "Heart disease describes a range of conditions affecting the heart."),
    ("asthma", "Asthma", "Asthma is a condition in which airways narrow and swell, causing breathing difficulty."),
    ("allergies", "Allergies", "Allergies are immune system reactions to substances that are usually harmless."),
    ("arthritis", "Arthritis", "Arthritis is inflammation of one or more joints, causing pain and stiffness."),
    ("adhd", "ADHD", "Attention-deficit/hyperactivity disorder affects attention, impulse control, and activity levels."),
    ("bipolar_disorder", "Bipolar Disorder", "Bipolar disorder causes extreme mood swings including emotional highs and lows."),
    ("schizophrenia", "Schizophrenia", "Schizophrenia is a serious mental disorder affecting thoughts, feelings, and behavior."),
    ("epilepsy", "Epilepsy", "Epilepsy is a neurological disorder marked by recurrent seizures."),
    ("insomnia", "Insomnia", "Insomnia is difficulty falling or staying asleep."),
    ("erectile_dysfunction", "Erectile Dysfunction", "Erectile dysfunction is the inability to achieve or maintain an erection."),
    ("hypothyroidism", "Hypothyroidism", "Hypothyroidism is an underactive thyroid gland producing insufficient hormone."),
    ("bacterial_infections", "Bacterial Infections", "Bacterial infections are illnesses caused by harmful bacteria."),
    ("acne", "Acne", "Acne is a skin condition that occurs when hair follicles become plugged with oil and dead skin cells."),
    ("gout", "Gout", "Gout is a form of inflammatory arthritis caused by uric acid crystals in joints."),
    ("migraine", "Migraine", "Migraine is a neurological condition causing intense headaches."),
    ("acid_reflux", "Acid Reflux (GERD)", "GERD occurs when stomach acid frequently flows back into the esophagus."),
    ("bph", "Benign Prostatic Hyperplasia", "BPH is a noncancerous enlargement of the prostate gland."),
    ("cancer", "Cancer", "Cancer is a disease in which abnormal cells divide uncontrollably and destroy body tissue."),
    ("lupus", "Lupus", "Lupus is a systemic autoimmune disease where the immune system attacks tissues."),
    ("crohns_disease", "Crohn's Disease", "Crohn's disease is a chronic inflammatory bowel disease."),
    ("psoriasis", "Psoriasis", "Psoriasis is a skin disease causing red, itchy, scaly patches."),
    ("eczema", "Eczema", "Eczema is a condition that makes skin red and itchy."),
    ("obesity", "Obesity", "Obesity is a complex disease involving an excessive amount of body fat."),
    ("osteoporosis", "Osteoporosis", "Osteoporosis is a condition that weakens bones, making them fragile and more likely to break."),
    ("glaucoma", "Glaucoma", "Glaucoma is a group of eye conditions that damage the optic nerve, often due to high intraocular pressure."),
    ("copd", "COPD", "Chronic obstructive pulmonary disease is a chronic inflammatory lung disease that causes airflow obstruction."),
    ("hyperthyroidism", "Hyperthyroidism", "Hyperthyroidism is an overactive thyroid gland producing excess thyroid hormone."),
    ("herpes", "Herpes", "Herpes infections are caused by herpes simplex virus and produce painful cold sores or genital lesions."),
    ("influenza", "Influenza (Flu)", "Influenza is a contagious respiratory illness caused by influenza viruses."),
    ("fungal_infections", "Fungal Infections", "Fungal infections are diseases caused by fungi, ranging from superficial skin infections to invasive disease."),
    ("viral_infections", "Viral Infections", "Viral infections are illnesses caused by viruses such as HIV, hepatitis, or herpes."),
    ("constipation", "Constipation", "Constipation is infrequent or difficult bowel movements."),
    ("gallstones", "Gallstones", "Gallstones are hardened deposits that can form in the gallbladder and may cause pain or block bile flow."),
    ("diarrhea", "Diarrhea", "Diarrhea is the passage of loose or watery stools."),
    ("nausea", "Nausea and Vomiting", "Nausea and vomiting can result from many causes including infections, medications, and motion sickness."),
    ("opioid_dependence", "Opioid Use Disorder", "Opioid use disorder is a chronic medical condition characterized by problematic opioid use."),
    ("contraception", "Contraception", "Contraception refers to methods used to prevent pregnancy."),
    ("menopause", "Menopause", "Menopause is the time that marks the end of a woman's menstrual cycles."),
    ("low_testosterone", "Low Testosterone", "Low testosterone (hypogonadism) is a condition in which the body produces insufficient testosterone."),
    ("muscle_spasm", "Muscle Spasm", "Muscle spasms are involuntary contractions of one or more muscles that can be painful."),
    ("blood_clots", "Blood Clots (Thrombosis)", "Blood clots can block veins or arteries and cause serious complications such as stroke or pulmonary embolism."),
    ("anemia", "Anemia", "Anemia is a condition in which the blood lacks enough healthy red blood cells to carry oxygen."),
    ("vitamin_deficiency", "Vitamin Deficiency", "Vitamin deficiencies occur when the body lacks sufficient amounts of essential vitamins."),
    ("dementia", "Dementia / Alzheimer's Disease", "Dementia is a general term for a decline in mental ability severe enough to interfere with daily life. Alzheimer's disease is the most common cause."),
    ("addiction", "Substance Use Disorder / Addiction", "Addiction is a chronic disorder involving compulsive substance use despite harmful consequences."),
    ("alzheimers", "Alzheimer's Disease", "Alzheimer's disease is a progressive neurological disorder that causes the brain to shrink and brain cells to die."),
]


PILL_IMAGES_DATA = [
    # (generic_name, imprint, shape, color, strength, manufacturer)
    ("ibuprofen", "I-2", "Oval", "White", "200 mg", "Advil"),
    ("ibuprofen", "44-291", "Round", "Brown", "200 mg", "LNK International"),
    ("ibuprofen", "IP 466", "Oval", "White", "800 mg", "Amneal Pharmaceuticals"),
    ("acetaminophen", "TYLENOL 500", "Oblong", "White", "500 mg", "McNeil"),
    ("acetaminophen", "L484", "Oblong", "White", "500 mg", "Kroger"),
    ("metformin", "M 500", "Round", "White", "500 mg", "Mylan"),
    ("metformin", "Z 70", "Oval", "White", "1000 mg", "Zydus"),
    ("lisinopril", "10 MG", "Oval", "White", "10 mg", "Lupin"),
    ("lisinopril", "M L24", "Round", "Pink", "20 mg", "Mylan"),
    ("atorvastatin", "PD 156", "Oval", "White", "20 mg", "Pfizer"),
    ("atorvastatin", "A 10", "Oval", "White", "10 mg", "Apotex"),
    ("amlodipine", "G 1530", "Round", "White", "5 mg", "Greenstone"),
    ("amoxicillin", "AMOX 500", "Capsule", "Pink/Buff", "500 mg", "Sandoz"),
    ("azithromycin", "PLIVA 333", "Round", "Pink", "250 mg", "Pliva"),
    ("ciprofloxacin", "CIPRO 500", "Oblong", "White", "500 mg", "Bayer"),
    ("sertraline", "ZOLOFT 50", "Oblong", "Blue", "50 mg", "Pfizer"),
    ("sertraline", "G 4900", "Oblong", "Blue", "100 mg", "Greenstone"),
    ("fluoxetine", "PROZAC 20", "Capsule", "Green/Yellow", "20 mg", "Eli Lilly"),
    ("alprazolam", "XANAX 0.5", "Oval", "Peach", "0.5 mg", "Pfizer"),
    ("alprazolam", "G 372", "Oval", "Blue", "1 mg", "Greenstone"),
    ("oxycodone", "M 30", "Round", "Blue", "30 mg", "Mallinckrodt"),
    ("hydrocodone", "M367", "Oblong", "White", "10/325 mg", "Mallinckrodt"),
    ("tramadol", "AN 627", "Round", "White", "50 mg", "Amneal"),
    ("gabapentin", "IP 102", "Capsule", "Yellow", "300 mg", "Amneal"),
    ("levothyroxine", "M L 4", "Round", "Yellow", "50 mcg", "Mylan"),
    ("warfarin", "TV 5", "Round", "Pink", "5 mg", "Teva"),
    ("prednisone", "WESTWARD 477", "Round", "White", "20 mg", "West-Ward"),
    ("omeprazole", "57", "Capsule", "Purple", "20 mg", "Dr. Reddy's"),
    ("loratadine", "L612", "Round", "White", "10 mg", "Perrigo"),
    ("cetirizine", "Z 10", "Round", "White", "10 mg", "Zyrtec"),
    ("zolpidem", "TEVA 73", "Round", "Pink", "5 mg", "Teva"),
    ("clonazepam", "C 1", "Round", "Yellow", "0.5 mg", "Accord"),
    ("methylphenidate", "M 5", "Round", "Yellow", "5 mg", "Mallinckrodt"),
    ("warfarin", "COUMADIN 1", "round", "pink", "1mg", "Bristol-Myers Squibb"),
    ("warfarin", "COUMADIN 2", "round", "lavender", "2mg", "Bristol-Myers Squibb"),
    ("warfarin", "COUMADIN 5", "round", "peach", "5mg", "Bristol-Myers Squibb"),
    ("warfarin", "COUMADIN 10", "round", "white", "10mg", "Bristol-Myers Squibb"),
    ("clopidogrel", "75", "round", "pink", "75mg", "Sanofi-Aventis"),
    ("furosemide", "LASIX 40", "round", "white", "40mg", "Sanofi-Aventis"),
    ("furosemide", "LASIX 80", "oval", "white", "80mg", "Sanofi-Aventis"),
    ("prednisone", "DELTASONE 5", "round", "white", "5mg", "Pfizer"),
    ("prednisone", "DELTASONE 20", "round", "peach", "20mg", "Pfizer"),
    ("metformin", "GLUCOPHAGE 500", "oval", "white", "500mg", "Bristol-Myers Squibb"),
    ("rosuvastatin", "CRESTOR 10", "round", "pink", "10mg", "AstraZeneca"),
    ("rosuvastatin", "CRESTOR 20", "round", "pink", "20mg", "AstraZeneca"),
    ("losartan", "COZAAR 50", "oval", "white", "50mg", "Merck"),
    ("metoprolol", "LOPRESSOR 50", "round", "pink", "50mg", "Novartis"),
    ("carvedilol", "COREG 6.25", "oval", "white", "6.25mg", "GlaxoSmithKline"),
    ("amlodipine", "NORVASC 5", "diamond", "white", "5mg", "Pfizer"),
    ("amlodipine", "NORVASC 10", "round", "white", "10mg", "Pfizer"),
    ("hydrochlorothiazide", "HYDRODIURIL 25", "round", "peach", "25mg", "Merck"),
    ("pantoprazole", "PROTONIX 20", "oval", "yellow", "20mg", "Wyeth"),
    ("pantoprazole", "PROTONIX 40", "oval", "yellow", "40mg", "Wyeth"),
    ("famotidine", "PEPCID 20", "oval", "brown", "20mg", "Merck"),
    ("ondansetron", "ZOFRAN 4", "oval", "white", "4mg", "GlaxoSmithKline"),
    ("ondansetron", "ZOFRAN 8", "oval", "yellow", "8mg", "GlaxoSmithKline"),
    ("cetirizine", "ZYRTEC 10", "oval", "white", "10mg", "UCB"),
    ("loratadine", "CLARITIN 10", "round", "white", "10mg", "Bayer"),
    ("montelukast", "SINGULAIR 10", "round", "beige", "10mg", "Merck"),
    ("ciprofloxacin", "CIPRO 500", "oval", "white", "500mg", "Bayer"),
    ("doxycycline", "VIBRAMYCIN 100", "capsule", "blue/white", "100mg", "Pfizer"),
    ("fluconazole", "DIFLUCAN 150", "oval", "pink", "150mg", "Pfizer"),
    ("acyclovir", "ZOVIRAX 400", "oval", "blue", "400mg", "GlaxoSmithKline"),
    ("tamsulosin", "FLOMAX 0.4", "capsule", "olive/orange", "0.4mg", "Boehringer Ingelheim"),
    ("tadalafil", "CIALIS 10", "oval", "yellow", "10mg", "Eli Lilly"),
    ("sildenafil", "VIAGRA 50", "diamond", "blue", "50mg", "Pfizer"),
    ("sildenafil", "VIAGRA 100", "diamond", "blue", "100mg", "Pfizer"),
    ("oxycodone", "OC 10", "round", "white", "10mg", "Purdue Pharma"),
    ("methylphenidate", "RITALIN 10", "round", "white", "10mg", "Novartis"),
    ("amphetamine", "ADDERALL 20", "round", "orange", "20mg", "Teva"),
    ("lithium", "LITHOBID 300", "capsule", "pink", "300mg", "Noven"),
    ("valproic acid", "DEPAKOTE 250", "oval", "salmon", "250mg", "AbbVie"),
    ("lamotrigine", "LAMICTAL 100", "oval", "white", "100mg", "GlaxoSmithKline"),
    ("levetiracetam", "KEPPRA 500", "oval", "yellow", "500mg", "UCB"),
    ("duloxetine", "CYMBALTA 30", "capsule", "white/blue", "30mg", "Eli Lilly"),
    ("venlafaxine", "EFFEXOR 75", "capsule", "peach", "75mg", "Pfizer"),
    ("bupropion", "WELLBUTRIN 150", "round", "purple", "150mg", "GlaxoSmithKline"),
    ("trazodone", "DESYREL 100", "round", "white", "100mg", "Mead Johnson"),
    ("escitalopram", "LEXAPRO 10", "round", "white", "10mg", "Forest Labs"),
    ("quetiapine", "SEROQUEL 100", "round", "yellow", "100mg", "AstraZeneca"),
    ("quetiapine", "SEROQUEL 300", "oval", "white", "300mg", "AstraZeneca"),
    ("olanzapine", "ZYPREXA 5", "round", "white", "5mg", "Eli Lilly"),
    ("aripiprazole", "ABILIFY 10", "round", "pink", "10mg", "Otsuka"),
    ("clonazepam", "KLONOPIN 1", "round", "blue", "1mg", "Roche"),
    ("lorazepam", "ATIVAN 1", "round", "white", "1mg", "Wyeth"),
    ("diazepam", "VALIUM 5", "round", "yellow", "5mg", "Roche"),
    ("buspirone", "BUSPAR 15", "oval", "white", "15mg", "Bristol-Myers Squibb"),
    ("pregabalin", "LYRICA 75", "capsule", "white/orange", "75mg", "Pfizer"),
    ("celecoxib", "CELEBREX 200", "capsule", "white/gold", "200mg", "Pfizer"),
    ("naproxen", "ALEVE 220", "oval", "blue", "220mg", "Bayer"),
    ("cyclobenzaprine", "FLEXERIL 10", "round", "yellow", "10mg", "McNeil"),
    ("colchicine", "COLCRYS 0.6", "oval", "purple", "0.6mg", "Takeda"),
    ("allopurinol", "ZYLOPRIM 300", "round", "white", "300mg", "Aspen"),
    ("alendronate", "FOSAMAX 70", "oval", "white", "70mg", "Merck"),
    ("estradiol", "ESTRACE 1", "round", "pink", "1mg", "Warner Chilcott"),
    ("levothyroxine", "SYNTHROID 100", "oval", "yellow", "100mcg", "AbbVie"),
    ("levothyroxine", "SYNTHROID 50", "oval", "white", "50mcg", "AbbVie"),
    ("methimazole", "TAPAZOLE 10", "round", "white", "10mg", "Monarch"),
    ("finasteride", "PROSCAR 5", "round", "blue", "5mg", "Merck"),
    ("finasteride", "PROPECIA 1", "oval", "tan", "1mg", "Merck"),
    ("spironolactone", "ALDACTONE 25", "round", "white", "25mg", "Pfizer"),
    ("digoxin", "LANOXIN 0.25", "round", "white", "0.25mg", "GlaxoSmithKline"),
    ("lisinopril", "ZESTRIL 10", "round", "pink", "10mg", "AstraZeneca"),
    ("atorvastatin", "LIPITOR 20", "oval", "white", "20mg", "Pfizer"),
    ("atorvastatin", "LIPITOR 40", "oval", "white", "40mg", "Pfizer"),
]


INTERACTIONS_DATA = [
    ("ibuprofen", "warfarin", "major", "Concurrent use of ibuprofen and warfarin significantly increases the risk of serious bleeding. NSAIDs inhibit platelet function and can cause GI ulceration; warfarin already increases bleeding risk."),
    ("ibuprofen", "aspirin", "moderate", "Ibuprofen can interfere with the cardioprotective antiplatelet effect of low-dose aspirin. If both are needed, take ibuprofen at least 8 hours before or 30 minutes after aspirin."),
    ("warfarin", "aspirin", "major", "Combining warfarin with aspirin substantially increases bleeding risk. Concurrent use should only occur under close medical supervision."),
    ("sertraline", "tramadol", "major", "Combining sertraline (SSRI) with tramadol can cause serotonin syndrome — a potentially life-threatening reaction. Symptoms include agitation, hallucinations, rapid heart rate, fever."),
    ("fluoxetine", "tramadol", "major", "Fluoxetine combined with tramadol may cause serotonin syndrome. Also, fluoxetine inhibits CYP2D6, reducing tramadol's analgesic effect."),
    ("alprazolam", "oxycodone", "major", "Combining benzodiazepines with opioids can result in profound sedation, respiratory depression, coma, and death."),
    ("alprazolam", "hydrocodone", "major", "Concurrent use of alprazolam and hydrocodone increases the risk of fatal respiratory depression."),
    ("metoprolol", "verapamil", "major", "Combining a beta blocker with a non-dihydropyridine calcium channel blocker can cause severe bradycardia, hypotension, and heart block."),
    ("ciprofloxacin", "warfarin", "major", "Ciprofloxacin can substantially increase warfarin's anticoagulant effect, raising INR and bleeding risk."),
    ("lithium", "ibuprofen", "major", "NSAIDs reduce renal lithium clearance, potentially leading to lithium toxicity. Monitor lithium levels closely."),
    ("metformin", "ciprofloxacin", "moderate", "Fluoroquinolones may disturb blood glucose, causing either hypo- or hyperglycemia in patients on metformin."),
    ("prednisone", "ibuprofen", "major", "Combining corticosteroids with NSAIDs substantially increases the risk of GI ulceration and bleeding."),
    ("sildenafil", "isosorbide", "major", "Combining PDE5 inhibitors with nitrates can cause severe, potentially fatal hypotension."),
    ("clopidogrel", "omeprazole", "moderate", "Omeprazole inhibits CYP2C19 and can reduce the antiplatelet effect of clopidogrel. Consider pantoprazole instead."),
    ("simvastatin", "amiodarone", "major", "Amiodarone can increase simvastatin levels, raising the risk of severe muscle injury (rhabdomyolysis)."),
    ("escitalopram", "tramadol", "major", "Combining SSRIs with tramadol may precipitate serotonin syndrome."),
    ("duloxetine", "tramadol", "major", "Both drugs increase serotonin levels; concurrent use can cause serotonin syndrome."),
    ("methotrexate", "ibuprofen", "major", "NSAIDs can reduce methotrexate clearance, leading to severe methotrexate toxicity including pancytopenia."),
    ("levothyroxine", "omeprazole", "moderate", "Reduced gastric acidity from PPIs can impair levothyroxine absorption. Separate dosing and monitor TSH."),
    ("amlodipine", "simvastatin", "moderate", "Amlodipine increases simvastatin exposure; limit simvastatin dose to 20 mg when used with amlodipine."),
    ("furosemide", "lisinopril", "moderate", "ACE inhibitors plus diuretics may cause symptomatic hypotension, especially with first doses."),
    ("clonazepam", "hydrocodone", "major", "Benzodiazepine plus opioid combinations carry a serious risk of respiratory depression and death."),
    ("lorazepam", "oxycodone", "major", "Concurrent benzodiazepine and opioid use can cause profound CNS and respiratory depression."),
    ("aripiprazole", "fluoxetine", "moderate", "Fluoxetine inhibits CYP2D6 and may increase aripiprazole levels. Dose adjustments may be needed."),
    ("hydrochlorothiazide", "lithium", "major", "Thiazide diuretics reduce lithium clearance and can cause lithium toxicity."),
    # --- Additional major interactions ---
    ("warfarin", "ibuprofen", "major", "NSAIDs can displace warfarin from plasma proteins and inhibit platelet function, greatly increasing bleeding risk."),
    ("digoxin", "amiodarone", "major", "Amiodarone increases digoxin serum levels by inhibiting P-glycoprotein, raising the risk of digoxin toxicity. Reduce digoxin dose by 30-50%."),
    ("simvastatin", "clarithromycin", "major", "Clarithromycin strongly inhibits CYP3A4, dramatically increasing simvastatin exposure and the risk of severe myopathy and rhabdomyolysis. Avoid combination."),
    ("carbamazepine", "valproic acid", "major", "Carbamazepine induces metabolism of valproic acid, reducing its levels; valproate can also raise carbamazepine's active metabolite. Levels of both require monitoring."),
    ("phenytoin", "warfarin", "major", "Phenytoin and warfarin interact bidirectionally: initial increase in INR followed by reduced anticoagulant effect; phenytoin levels may rise. Monitor closely."),
    ("sertraline", "tryptophan", "major", "Combining SSRIs with tryptophan can precipitate serotonin syndrome with agitation, hyperthermia, and autonomic instability."),
    ("phenelzine", "sertraline", "major", "MAOIs combined with SSRIs can cause life-threatening serotonin syndrome. A 14-day washout is required between agents."),
    ("phenelzine", "fluoxetine", "major", "Combining MAOIs with fluoxetine carries a serious risk of serotonin syndrome. A 5-week washout after fluoxetine is required before starting an MAOI."),
    ("tranylcypromine", "sertraline", "major", "MAOIs combined with SSRIs can precipitate fatal serotonin syndrome. Avoid combination."),
    ("methylphenidate", "phenelzine", "major", "Stimulants combined with MAOIs can trigger hypertensive crisis. Contraindicated."),
    ("amphetamine", "phenelzine", "major", "Amphetamines combined with MAOIs can cause severe hypertensive crisis. Contraindicated."),
    ("bupropion", "tramadol", "major", "Both lower the seizure threshold; concurrent use substantially increases seizure risk."),
    ("buspirone", "phenelzine", "major", "Buspirone with MAOIs can elevate blood pressure dangerously and contribute to serotonin syndrome."),
    ("fluoxetine", "tamoxifen", "major", "Fluoxetine strongly inhibits CYP2D6, reducing conversion of tamoxifen to its active metabolite endoxifen and potentially decreasing efficacy in breast cancer treatment."),
    ("paroxetine", "tamoxifen", "major", "Paroxetine strongly inhibits CYP2D6, reducing tamoxifen's active metabolite and potentially decreasing antineoplastic efficacy."),
    ("pregabalin", "oxycodone", "major", "Gabapentinoids combined with opioids substantially increase the risk of profound sedation and respiratory depression."),
    ("pregabalin", "hydrocodone", "major", "Concurrent pregabalin and opioids can produce severe CNS and respiratory depression."),
    ("alprazolam", "hydromorphone", "major", "Benzodiazepine plus opioid combinations carry a black-box risk of fatal respiratory depression."),
    ("diazepam", "oxycodone", "major", "Concurrent benzodiazepine and opioid use can cause profound CNS depression and death."),
    ("metronidazole", "alcohol", "major", "Metronidazole inhibits aldehyde dehydrogenase; combination with alcohol causes a disulfiram-like reaction (flushing, vomiting, tachycardia)."),
    ("warfarin", "fluconazole", "major", "Fluconazole inhibits CYP2C9, substantially increasing warfarin's anticoagulant effect and bleeding risk."),
    ("simvastatin", "gemfibrozil", "major", "Gemfibrozil dramatically increases simvastatin exposure and the risk of rhabdomyolysis. Avoid combination."),
    ("colchicine", "clarithromycin", "major", "Clarithromycin inhibits CYP3A4 and P-glycoprotein, markedly increasing colchicine levels with potential for fatal toxicity. Avoid combination."),
    ("methotrexate", "trimethoprim", "major", "Trimethoprim potentiates methotrexate's antifolate effect, risking pancytopenia and severe bone marrow suppression."),
    ("tadalafil", "isosorbide", "major", "PDE5 inhibitors combined with nitrates can cause severe, life-threatening hypotension. Contraindicated."),
    ("vardenafil", "isosorbide", "major", "PDE5 inhibitors with any nitrate are contraindicated due to risk of profound hypotension."),

    # --- Moderate interactions ---
    ("metformin", "alcohol", "moderate", "Alcohol increases the risk of lactic acidosis in patients on metformin and can cause hypoglycemia. Limit alcohol intake."),
    ("lisinopril", "potassium", "moderate", "ACE inhibitors raise serum potassium; concurrent potassium supplements can produce dangerous hyperkalemia. Monitor levels."),
    ("atorvastatin", "fluconazole", "moderate", "Fluconazole inhibits CYP3A4, increasing atorvastatin levels and the risk of myopathy."),
    ("sertraline", "alcohol", "moderate", "Combining SSRIs with alcohol enhances CNS depression and may worsen depressive symptoms."),
    ("alprazolam", "alcohol", "moderate", "Concurrent use produces additive CNS depression, impaired coordination, and serious risk of overdose."),
    ("gabapentin", "alcohol", "moderate", "Alcohol enhances gabapentin's sedative effects and risk of psychomotor impairment."),
    ("quetiapine", "alcohol", "moderate", "Quetiapine plus alcohol produces additive sedation and orthostatic hypotension."),
    ("lisinopril", "spironolactone", "moderate", "ACE inhibitors plus potassium-sparing diuretics can cause hyperkalemia. Monitor potassium and renal function."),
    ("levothyroxine", "calcium", "moderate", "Calcium carbonate binds levothyroxine in the gut, reducing absorption. Separate dosing by 4 hours."),
    ("levothyroxine", "iron", "moderate", "Iron supplements impair levothyroxine absorption. Separate by at least 4 hours and monitor TSH."),
    ("doxycycline", "calcium carbonate", "moderate", "Antacids and calcium products chelate doxycycline, reducing oral absorption. Separate by 2-3 hours."),
    ("clindamycin", "rocuronium", "moderate", "Clindamycin can prolong neuromuscular blockade with nondepolarizing agents."),
    ("furosemide", "gentamicin", "moderate", "Loop diuretics combined with aminoglycosides increase the risk of ototoxicity and nephrotoxicity."),
    ("spironolactone", "lisinopril", "moderate", "Combining potassium-sparing diuretics with ACE inhibitors elevates hyperkalemia risk; monitor potassium."),
    ("prednisone", "naproxen", "moderate", "Corticosteroids and NSAIDs together substantially increase GI ulceration and bleeding risk."),
    ("prednisone", "metformin", "moderate", "Corticosteroids elevate blood glucose, potentially reducing the effectiveness of metformin and other diabetes medications."),
    ("prednisone", "insulin", "moderate", "Corticosteroids antagonize insulin's glucose-lowering effect; insulin dose adjustment may be needed."),
    ("hydroxychloroquine", "azithromycin", "moderate", "Both agents prolong the QT interval; concurrent use raises the risk of torsades de pointes."),
    ("tamsulosin", "sildenafil", "moderate", "Combined alpha-blocker and PDE5 inhibitor use can produce symptomatic hypotension. Stagger doses."),
    ("finasteride", "warfarin", "moderate", "Finasteride may modestly affect warfarin's anticoagulant effect; monitor INR after initiation."),
    ("trazodone", "alcohol", "moderate", "Trazodone and alcohol have additive sedative effects and increase orthostatic hypotension risk."),
    ("lithium", "hydrochlorothiazide", "moderate", "Thiazides reduce renal lithium clearance, raising levels into the toxic range. Monitor lithium closely."),
    ("valproic acid", "aspirin", "moderate", "Aspirin displaces valproate from plasma proteins and inhibits its metabolism, raising free valproate levels."),
    ("lamotrigine", "valproic acid", "moderate", "Valproate inhibits lamotrigine glucuronidation, doubling its half-life. Lamotrigine doses must be halved when added to valproate."),
    ("levetiracetam", "alcohol", "moderate", "Alcohol enhances the CNS-depressant effects of levetiracetam."),
    ("celecoxib", "warfarin", "moderate", "Celecoxib inhibits CYP2C9 and platelet-independent bleeding risk; INR may rise. Monitor closely."),
    ("naproxen", "warfarin", "moderate", "Naproxen increases bleeding risk via platelet inhibition and GI irritation in patients on warfarin."),
    ("aspirin", "clopidogrel", "moderate", "Dual antiplatelet therapy increases bleeding risk; combination is often intentional after stenting but requires monitoring."),
    ("metformin", "topiramate", "moderate", "Topiramate's carbonic anhydrase inhibition combined with metformin increases the risk of metabolic acidosis."),
    ("fluoxetine", "alcohol", "moderate", "Alcohol potentiates SSRI sedation and may worsen depressive symptoms."),
    ("escitalopram", "alcohol", "moderate", "Alcohol enhances CNS depressant effects of escitalopram and may aggravate depression."),
    ("citalopram", "azithromycin", "moderate", "Both prolong the QT interval; combination may increase the risk of arrhythmia."),
    ("amiodarone", "warfarin", "moderate", "Amiodarone inhibits CYP2C9, increasing warfarin's effect; warfarin dose typically needs reduction by 30-50%."),
    ("rifampin", "warfarin", "moderate", "Rifampin induces CYP enzymes, reducing warfarin levels and anticoagulant effect; INR may drop."),
    ("rifampin", "oral contraceptives", "moderate", "Rifampin induces hepatic metabolism, reducing oral contraceptive efficacy. Use a backup method."),
    ("phenytoin", "fluconazole", "moderate", "Fluconazole inhibits CYP2C9, increasing phenytoin levels and the risk of toxicity."),
    ("metoprolol", "fluoxetine", "moderate", "Fluoxetine inhibits CYP2D6, raising metoprolol levels and the risk of bradycardia or hypotension."),
    ("propranolol", "verapamil", "moderate", "Beta blocker plus non-dihydropyridine calcium channel blocker can produce bradycardia and AV block."),
    ("diltiazem", "simvastatin", "moderate", "Diltiazem inhibits CYP3A4, increasing simvastatin levels; limit simvastatin to 10 mg/day."),
    ("atorvastatin", "clarithromycin", "moderate", "Clarithromycin can increase atorvastatin levels; consider holding the statin during the antibiotic course."),
    ("omeprazole", "diazepam", "moderate", "Omeprazole inhibits CYP2C19, prolonging diazepam half-life and enhancing sedation."),
    ("sumatriptan", "sertraline", "moderate", "Combination of triptans with SSRIs may increase the risk of serotonin syndrome."),
    ("losartan", "potassium", "moderate", "Angiotensin receptor blockers raise serum potassium; concurrent supplementation may cause hyperkalemia."),
    ("losartan", "spironolactone", "moderate", "ARBs combined with potassium-sparing diuretics increase hyperkalemia risk; monitor potassium."),
    ("digoxin", "verapamil", "moderate", "Verapamil increases digoxin levels by inhibiting P-glycoprotein; reduce digoxin dose and monitor."),
    ("digoxin", "furosemide", "moderate", "Furosemide-induced hypokalemia potentiates digoxin toxicity; monitor potassium."),
    ("warfarin", "amoxicillin", "moderate", "Broad-spectrum antibiotics can disrupt vitamin K-producing gut flora, modestly raising INR."),
    ("warfarin", "acetaminophen", "moderate", "High or sustained acetaminophen doses can increase INR in patients on warfarin."),
    ("hydrochlorothiazide", "ibuprofen", "moderate", "NSAIDs blunt the antihypertensive and diuretic effects of thiazides and may worsen renal function."),
    ("lisinopril", "ibuprofen", "moderate", "NSAIDs reduce the antihypertensive effect of ACE inhibitors and may impair renal function."),
    ("clopidogrel", "esomeprazole", "moderate", "Esomeprazole inhibits CYP2C19 activation of clopidogrel; consider an alternative PPI such as pantoprazole."),
    ("methotrexate", "naproxen", "moderate", "NSAIDs reduce renal clearance of methotrexate; high-dose methotrexate combinations should be avoided."),
    ("levothyroxine", "ferrous sulfate", "moderate", "Iron salts impair levothyroxine absorption; separate dosing by 4 hours."),
    ("ciprofloxacin", "calcium carbonate", "moderate", "Polyvalent cations chelate fluoroquinolones, reducing absorption. Separate by 2 hours before or 6 hours after."),
    ("ciprofloxacin", "tizanidine", "moderate", "Ciprofloxacin inhibits CYP1A2, markedly elevating tizanidine levels with risk of hypotension and somnolence."),

    # --- Minor interactions ---
    ("ibuprofen", "atorvastatin", "minor", "Mild possible elevation of CK; rarely clinically significant. Monitor for muscle symptoms."),
    ("omeprazole", "magnesium hydroxide", "minor", "Long-term PPI use may modestly reduce magnesium absorption; supplementation rarely needed."),
    ("calcium carbonate", "ferrous sulfate", "minor", "Calcium can modestly reduce iron absorption. Separate dosing by 1-2 hours if both are needed."),
    ("acetaminophen", "alcohol", "minor", "Chronic alcohol use combined with regular acetaminophen modestly increases the risk of hepatotoxicity. Limit to recommended doses."),
    ("cetirizine", "alcohol", "minor", "Cetirizine has minimal sedation but alcohol can produce additive drowsiness in sensitive individuals."),
    ("loratadine", "alcohol", "minor", "Loratadine is non-sedating but rare additive drowsiness with alcohol is possible."),
    ("montelukast", "phenobarbital", "minor", "Phenobarbital may modestly induce montelukast metabolism, slightly reducing exposure."),
    ("doxycycline", "calcium", "minor", "Dairy and calcium products can modestly reduce doxycycline absorption when taken simultaneously."),
    ("ciprofloxacin", "caffeine", "minor", "Ciprofloxacin inhibits caffeine metabolism, potentially enhancing caffeine effects such as jitteriness."),
    ("metformin", "cimetidine", "minor", "Cimetidine modestly reduces renal metformin clearance; clinical significance is generally low."),
    ("famotidine", "ketoconazole", "minor", "H2 blockers raise gastric pH, modestly reducing ketoconazole absorption. Separate dosing when possible."),
    ("aspirin", "ibuprofen", "minor", "Ibuprofen taken before low-dose aspirin can blunt antiplatelet effect; usually managed with timing rather than avoidance."),
    ("simvastatin", "grapefruit", "minor", "Grapefruit juice modestly increases simvastatin exposure; limit intake while on the medication."),
    ("naproxen", "caffeine", "minor", "Combination may slightly enhance analgesic effect; clinically minor."),
    ("pseudoephedrine", "caffeine", "minor", "Additive stimulant effects may produce mild jitteriness or increased heart rate."),
    ("diphenhydramine", "alcohol", "minor", "Additive sedation; effect is usually mild at typical OTC doses."),
    ("ranitidine", "iron", "minor", "Reduced gastric acidity may slightly impair iron absorption; clinically minor."),
    ("aluminum hydroxide", "ciprofloxacin", "minor", "Aluminum binds fluoroquinolones; small reductions in absorption are clinically minor with appropriate timing."),
    ("vitamin k", "warfarin", "minor", "Routine dietary vitamin K does not require avoidance; consistency of intake is more important than absolute amount."),
    ("green tea", "warfarin", "minor", "Green tea contains modest vitamin K and may slightly affect INR; keep intake consistent."),
]


NEWS_DATA = [
    ("FDA Approves New GLP-1 Agonist for Weight Management", "New Drug Approvals", "The U.S. Food and Drug Administration today approved a new once-weekly glucagon-like peptide-1 (GLP-1) receptor agonist for chronic weight management in adults with obesity (body mass index of 30 kg/m^2 or greater) or overweight (BMI of 27 kg/m^2 or greater) in the presence of at least one weight-related comorbidity such as hypertension, dyslipidemia, type 2 diabetes, obstructive sleep apnea, or established cardiovascular disease.\n\nApproval was based on two pivotal phase 3 randomized, double-blind, placebo-controlled trials enrolling a combined population of more than 4,500 adults. After 68 weeks of treatment in combination with a reduced-calorie diet and increased physical activity, participants randomized to the highest dose of the new agent lost an average of 15 to 17 percent of body weight compared with approximately 2 to 3 percent in the placebo group. Secondary endpoints, including waist circumference, systolic blood pressure, glycated hemoglobin (in participants with prediabetes), and lipid parameters, also improved significantly relative to placebo.\n\nThe medication is administered as a once-weekly subcutaneous injection using a prefilled pen. Dose escalation occurs over 16 weeks to mitigate gastrointestinal adverse effects, which are the most common reason for discontinuation. The most frequently reported adverse reactions during the trials were nausea, diarrhea, vomiting, constipation, and abdominal pain; the majority were mild to moderate and tended to diminish with continued therapy.\n\nThe label carries a boxed warning regarding thyroid C-cell tumors observed in rodent carcinogenicity studies, with contraindications in patients who have a personal or family history of medullary thyroid carcinoma or multiple endocrine neoplasia syndrome type 2. Additional warnings cover pancreatitis, gallbladder disease, acute kidney injury related to dehydration, hypoglycemia when used with insulin or sulfonylureas, and diabetic retinopathy complications in patients with a prior history of retinopathy.\n\nThe FDA emphasized that the new agent is intended as an adjunct to lifestyle modification, not a replacement, and that the cardiovascular and renal benefits demonstrated for related GLP-1 agents are being evaluated in ongoing outcomes trials. Public health officials welcomed the approval but cautioned that access, insurance coverage, and supply will continue to shape real-world impact."),
    ("FDA Approves Updated Influenza Vaccines for 2025-2026 Season", "New Drug Approvals", "The FDA has approved the composition of inactivated, recombinant, and live attenuated influenza vaccine formulations for the 2025-2026 Northern Hemisphere influenza season, following recommendations from the agency's Vaccines and Related Biological Products Advisory Committee and the World Health Organization.\n\nThe quadrivalent egg-based and cell-based vaccines target an updated A(H1N1)pdm09-like strain, a continuing A(H3N2)-like strain, and B/Victoria-lineage and B/Yamagata-lineage components, although the inclusion of the B/Yamagata lineage remains under active review by global advisory bodies given limited recent circulation of that lineage. The high-dose and adjuvanted formulations for adults 65 years and older are also updated to match the selected strains.\n\nManufacturers are expected to begin shipping doses to distributors and pharmacies in late summer, with broad availability for routine immunization beginning in September. The Centers for Disease Control and Prevention recommends annual influenza vaccination for everyone 6 months of age and older who does not have a contraindication, with particular emphasis on people at higher risk for severe disease, including older adults, pregnant people, young children, and individuals with chronic medical conditions.\n\nThe FDA emphasized that no safety signals beyond those described in current product labeling were identified during the review. Common adverse reactions remain injection-site soreness, mild fever, headache, and myalgia, typically lasting one to two days. Severe allergic reactions are rare, and updated guidance permits vaccination of most individuals with egg allergy without special precautions for current vaccines.\n\nProviders are encouraged to plan for co-administration with COVID-19 boosters and RSV preventive products where indicated, and to use the upcoming season to address persistent gaps in vaccination coverage among children, pregnant patients, and adults with chronic conditions."),
    ("FDA Approves First Generic of Popular Migraine Medication", "New Drug Approvals", "The FDA today approved the first generic version of a widely used calcitonin gene-related peptide (CGRP) receptor antagonist for the acute treatment of migraine with or without aura in adults. The approval is expected to expand affordable access to a class of agents that has reshaped acute migraine therapy over the past several years.\n\nApproval was based on a comprehensive review of bioequivalence data demonstrating that the generic product achieves comparable rate and extent of absorption to the reference listed drug within established statistical limits. Dissolution and stability data, as well as inactive-ingredient and manufacturing reviews, were also part of the application.\n\nThe medication is indicated for acute treatment of migraine attacks and is taken orally at the onset of an attack. Unlike triptans, CGRP receptor antagonists do not cause vasoconstriction, and they may be appropriate for patients with cardiovascular contraindications to triptans or for those who have failed or cannot tolerate triptan therapy.\n\nCommon adverse reactions in the original development program included nausea, fatigue, and dizziness, typically mild and transient. The label warns about hypersensitivity reactions, including dyspnea and rash, and notes drug interactions with strong CYP3A4 inducers and inhibitors.\n\nThe generic launch is anticipated within the coming quarter, pending resolution of any remaining patent and exclusivity considerations. Health-system pharmacists and payers welcomed the approval, noting that out-of-pocket cost remains a significant barrier for many migraine patients despite the demonstrated efficacy of newer acute treatments. Neurologists emphasized that broader access could meaningfully reduce reliance on butalbital-containing combinations and opioid analgesics, both of which remain associated with risks of medication-overuse headache and dependence."),
    ("New SGLT2 Inhibitor Approved for Chronic Kidney Disease", "New Drug Approvals", "The FDA has expanded approval of a sodium-glucose cotransporter 2 (SGLT2) inhibitor to include adults with chronic kidney disease (CKD) at risk of progression, with or without type 2 diabetes. The new indication is based on a large randomized, placebo-controlled cardiovascular and renal outcomes trial enrolling more than 4,000 patients with estimated glomerular filtration rates between 25 and 75 mL/min/1.73 m^2 and clinically significant albuminuria.\n\nOver a median follow-up of approximately 2.4 years, the SGLT2 inhibitor produced a statistically significant reduction in the primary composite endpoint of sustained decline in eGFR, end-stage kidney disease, or cardiovascular or renal death. Hospitalization for heart failure and all-cause mortality also favored the active treatment arm. Subgroup analyses suggested consistent benefit across baseline eGFR strata, albuminuria categories, and diabetes status.\n\nThe medication is administered orally once daily. Common adverse reactions include genital mycotic infections, urinary tract infections, increased urination, and volume depletion-related events, particularly during initiation in patients on concurrent loop diuretics. Rare but serious adverse events include diabetic ketoacidosis (which can occur at near-normal glucose levels), necrotizing fasciitis of the perineum (Fournier gangrene), and acute kidney injury during intercurrent illness.\n\nClinicians are advised to assess volume status, renal function, and electrolytes before initiation and during therapy, and to consider temporarily withholding the medication during acute illness, prolonged fasting, or perioperative periods. The new indication aligns U.S. labeling with international guidelines that increasingly position SGLT2 inhibitors as foundational therapy for CKD irrespective of diabetes status, alongside renin-angiotensin system blockade, nonsteroidal mineralocorticoid receptor antagonists where appropriate, and aggressive cardiovascular risk-factor management."),
    ("FDA Approves Biosimilar for Common Biologic", "New Drug Approvals", "The FDA has approved a new biosimilar to a widely prescribed tumor necrosis factor (TNF) inhibitor used in the treatment of multiple chronic inflammatory and autoimmune conditions. The approval covers all of the reference product's licensed indications, including rheumatoid arthritis, juvenile idiopathic arthritis, psoriatic arthritis, ankylosing spondylitis, adult and pediatric Crohn's disease, ulcerative colitis, plaque psoriasis, and hidradenitis suppurativa.\n\nThe biosimilarity determination was based on a totality-of-evidence review including analytical characterization, nonclinical pharmacology and toxicology, clinical pharmacokinetics in healthy volunteers, and a confirmatory comparative clinical trial in patients with moderate-to-severe plaque psoriasis. No clinically meaningful differences in efficacy, safety, or immunogenicity were demonstrated relative to the reference product.\n\nAn interchangeability designation, which would permit pharmacy-level substitution without prescriber intervention in most states, was not part of this initial approval and remains subject to additional switching study data currently under FDA review.\n\nProduct labeling carries the same boxed warning as the reference product for serious infections, including tuberculosis reactivation, invasive fungal infections, and opportunistic bacterial and viral infections, as well as the risk of malignancy, particularly lymphoma in children and adolescents. Screening for latent tuberculosis and hepatitis B prior to initiation remains required.\n\nMarket entry timing and pricing strategy are expected to be shaped by patent dynamics, payer formulary placement, and rebate negotiations. Health-system pharmacists and payers expressed hope that expanded biosimilar competition would meaningfully reduce treatment costs, which can exceed $50,000 per year per patient with the reference product. Patient advocacy organizations urged manufacturers, payers, and prescribers to ensure that any switches between products are accompanied by clear communication and clinical monitoring."),
    ("Study: Statins May Reduce Risk of Severe COVID-19", "Medical", "A large observational cohort study published this week reports that adults receiving statin therapy at the time of SARS-CoV-2 infection had a modestly reduced risk of hospitalization, intensive care unit admission, and in-hospital mortality compared with matched, non-statin-using controls. The findings add to a growing but still mixed evidence base regarding the potential effect of statins on COVID-19 outcomes.\n\nThe analysis pooled electronic health record data from multiple large health systems covering more than 200,000 adults with confirmed SARS-CoV-2 infection during the study period. After propensity-score matching for age, sex, comorbidities, socioeconomic markers, vaccination status, and concomitant medications, statin users had a relative reduction of approximately 18 to 22 percent in the composite endpoint of severe disease. The effect was most pronounced in patients with baseline cardiovascular disease and diabetes.\n\nProposed mechanisms include anti-inflammatory and immunomodulatory effects of statins, stabilization of vascular endothelium, and modulation of the lipid raft architecture that SARS-CoV-2 may use during cellular entry. However, the authors and accompanying editorialists cautioned that observational data cannot establish causation and that residual confounding by indication and by healthy-user effects remains a concern.\n\nNo guidelines currently recommend initiating statin therapy specifically for COVID-19 prevention or treatment, and randomized trials of statins in this setting have produced inconsistent results. Clinicians are advised to continue statins in patients with established indications and not to discontinue them during acute illness unless contraindicated.\n\nThe findings underscore the value of leveraging large health-system datasets to identify potential therapeutic signals during pandemic responses, while reinforcing that randomized evidence remains the standard for changing clinical practice."),
    ("Doctors Caution Against Combining NSAIDs With Blood Thinners", "Medical", "Clinicians and pharmacists are renewing warnings about the substantial bleeding risk associated with combining nonsteroidal anti-inflammatory drugs (NSAIDs) such as ibuprofen, naproxen, diclofenac, and meloxicam with oral anticoagulants including warfarin and direct oral anticoagulants (DOACs) like apixaban, rivaroxaban, dabigatran, and edoxaban. The caution follows analyses of real-world bleeding events and emergency department presentations linked to over-the-counter analgesic use among anticoagulated patients.\n\nNSAIDs increase bleeding risk through several mechanisms: reversible inhibition of platelet cyclooxygenase-1 impairs platelet aggregation; gastric mucosal injury increases the risk of upper gastrointestinal hemorrhage; and renal effects can precipitate volume retention and elevated blood pressure that compounds bleeding risk. When added to oral anticoagulation, the risk of clinically significant gastrointestinal and intracranial hemorrhage can be doubled or more, according to multiple cohort analyses.\n\nThe message is particularly important during respiratory illness seasons, when many patients self-treat fever and musculoskeletal pain with over-the-counter NSAID-containing products without realizing that combination cold-and-flu remedies often include ibuprofen or naproxen. Topical NSAIDs, while generally lower-risk than oral formulations, are not entirely free of systemic absorption and should be discussed with prescribers in patients on chronic anticoagulation.\n\nRecommended alternatives include acetaminophen at doses not exceeding 3 grams per day in adults without hepatic impairment, non-pharmacologic measures such as ice, heat, and physical therapy, and, when an NSAID is judged necessary, the shortest duration at the lowest effective dose with concurrent proton pump inhibitor cover for gastrointestinal protection.\n\nPatients on anticoagulants are urged to discuss all over-the-counter analgesics with their pharmacist before purchase and to report any signs of bleeding-melena, hematemesis, bruising, hematuria, or new headache-promptly to their prescriber."),
    ("Researchers Identify New Risk Factors for Type 2 Diabetes", "Medical", "A multi-center prospective cohort study published this week has identified several previously underappreciated risk factors that meaningfully increase the long-term risk of developing type 2 diabetes mellitus, including persistent short sleep duration, irregular meal timing, exposure to certain ambient air pollutants, and disrupted circadian rhythms associated with rotating shift work.\n\nThe analysis followed more than 60,000 adults without diabetes at baseline for a median of 9.7 years. After adjustment for established risk factors-including age, family history, body mass index, physical activity, and dietary patterns-each of the newly characterized exposures was independently associated with a 15 to 35 percent increase in the relative risk of incident type 2 diabetes. Combinations of exposures showed additive effects, with the highest-risk participants experiencing more than double the incidence observed in the lowest-risk group.\n\nThe investigators also identified several novel genetic variants associated with insulin resistance and beta-cell function in genome-wide association substudies, and demonstrated gene-environment interactions suggesting that some lifestyle exposures confer greater risk in genetically susceptible individuals.\n\nThe findings have implications for clinical risk assessment, population-level prevention strategies, and individual lifestyle counseling. The authors recommend that primary care clinicians incorporate questions about sleep duration, shift work, and meal timing into routine diabetes risk assessments alongside traditional factors, and that public health policy continue to address environmental exposures such as fine particulate matter.\n\nEditorialists noted that while the modifiable lifestyle factors offer concrete intervention targets-prioritizing adequate sleep, consistent meal timing, and reducing avoidable air pollution exposure-broader determinants such as occupational schedules and neighborhood air quality require structural rather than purely individual solutions."),
    ("Long-term SSRI Use Linked to Bone Density Changes", "Medical", "New longitudinal research published this week suggests a possible association between long-term use of selective serotonin reuptake inhibitors (SSRIs) and accelerated declines in bone mineral density (BMD), particularly at the femoral neck and lumbar spine in postmenopausal women and older men. The findings add to a growing body of observational evidence regarding potential skeletal effects of chronic SSRI therapy.\n\nThe study followed more than 5,000 adults aged 50 and older with serial dual-energy X-ray absorptiometry (DXA) scans over a median of seven years. After adjustment for age, body mass index, smoking, alcohol use, glucocorticoid exposure, and underlying psychiatric and medical comorbidities, participants on continuous SSRI therapy for more than two years experienced approximately 0.4 to 0.6 percent greater annualized BMD loss at the hip than non-users, with a smaller signal at the spine. Incident hip and vertebral fractures were also modestly more common among long-term SSRI users.\n\nProposed mechanisms include serotonin-mediated effects on osteoblast and osteoclast activity, falls-related fracture risk associated with SSRI side effects, and potential confounding by indication, as untreated depression itself is associated with reduced physical activity and bone health.\n\nThe authors emphasized that the absolute increase in fracture risk attributable to SSRIs in any individual patient appears small and must be weighed against the substantial morbidity and mortality of untreated mood and anxiety disorders. They do not recommend discontinuing SSRIs for skeletal reasons but suggest that clinicians consider fall-prevention strategies, ensure adequate calcium and vitamin D intake, screen for osteoporosis according to standard guidelines, and engage in shared decision-making about long-term therapy in patients with multiple skeletal risk factors."),
    ("Hospital-acquired Infections Decline With Updated Guidelines", "Medical", "National surveillance data released this week show that rates of several common hospital-acquired infections (HAIs)-including central line-associated bloodstream infections (CLABSI), catheter-associated urinary tract infections (CAUTI), Clostridioides difficile infection (CDI), and methicillin-resistant Staphylococcus aureus (MRSA) bacteremia-have declined meaningfully over the past two years across U.S. acute-care hospitals following implementation of updated infection prevention guidelines and antimicrobial stewardship programs.\n\nThe data, compiled by the Centers for Disease Control and Prevention's National Healthcare Safety Network, show year-over-year declines ranging from 9 percent for CDI to nearly 18 percent for CLABSI when standardized for case mix and reporting volume. Ventilator-associated events decreased modestly. The improvements partially reverse setbacks observed during peak periods of the COVID-19 pandemic, when staffing shortages, surge conditions, and personal protective equipment constraints contributed to rising HAI rates.\n\nKey interventions associated with the declines include standardized central line insertion and maintenance bundles, daily reassessment of indwelling catheter necessity, hand hygiene auditing with rapid feedback, environmental cleaning programs using fluorescent markers or adenosine triphosphate (ATP) monitoring, and antimicrobial stewardship interventions that reduce broad-spectrum antibiotic exposure and downstream Clostridioides difficile risk.\n\nHospital leaders cautioned that progress remains uneven across institutions, with smaller community hospitals and facilities serving high-acuity populations continuing to face challenges. Workforce shortages, particularly in infection prevention and critical care nursing, remain a significant barrier to sustained gains.\n\nFederal officials reiterated that public reporting of HAI rates, payment-program incentives tied to safety performance, and continued investment in infection prevention infrastructure are essential to building on recent improvements and to preparing for the next pandemic threat."),
    ("FDA Issues Safety Alert on Certain Recalled Blood Pressure Medications", "FDA Alerts", "The FDA has issued a safety alert and announced a voluntary nationwide recall of specific lots of valsartan-containing antihypertensive products after routine surveillance testing detected trace amounts of a probable human carcinogen, N-nitrosodimethylamine (NDMA), above the agency's interim acceptable intake limit. The affected lots include both single-ingredient valsartan tablets and certain valsartan-hydrochlorothiazide combination products from one manufacturer.\n\nThe FDA emphasized that the immediate cardiovascular risk of abruptly discontinuing antihypertensive therapy is generally greater than the small theoretical cancer risk associated with limited exposure to the impurity. Patients are advised not to stop taking their medication without first consulting their prescriber or pharmacist and arranging a replacement supply with an unaffected lot or alternative agent.\n\nLot numbers, expiration dates, and product images are available on the FDA recall portal. Pharmacies have been instructed to quarantine affected stock, return product per the manufacturer's instructions, and proactively contact patients who may have received affected lots. Health-system pharmacists are working with prescribers to facilitate timely transition to alternative angiotensin receptor blockers (such as losartan or olmesartan), angiotensin-converting enzyme inhibitors, or calcium channel blockers based on patient comorbidities and prior tolerance.\n\nThe agency reiterated that it continues to investigate the root cause of nitrosamine impurities across multiple drug classes, including additional sartans, ranitidine (previously withdrawn), metformin, varenicline, and several others, and has implemented enhanced testing requirements for finished products and active pharmaceutical ingredients sourced from foreign facilities.\n\nPatients with questions are encouraged to contact their pharmacy first, then their prescriber, and to report any product-quality concerns or adverse events through the FDA's MedWatch program."),
    ("FDA Warns About Unapproved Online Sales of Weight-loss Drugs", "FDA Alerts", "The FDA has issued a public health alert warning consumers about counterfeit, adulterated, and unapproved versions of popular GLP-1 receptor agonist weight-loss medications being sold through online pharmacies, telehealth platforms, social media marketplaces, and unlicensed compounding operations. The alert follows a surge in adverse event reports linked to products marketed as semaglutide or tirzepatide but found, upon laboratory analysis, to contain incorrect active ingredients, undeclared substances, inappropriate dosing, or no active ingredient at all.\n\nThe agency described several common patterns of risk. Some products purport to be brand-name injections at substantially discounted prices and are shipped from overseas without the safety and quality controls applied to FDA-approved products. Others are marketed as compounded semaglutide or tirzepatide but use a salt form (such as semaglutide sodium or tirzepatide acetate) that is not the same active pharmaceutical ingredient evaluated for safety and efficacy in the approved products. Still others are entirely counterfeit, repurposing legitimate packaging or vial labels.\n\nReports received by the FDA's MedWatch program include severe hypoglycemia, prolonged vomiting and dehydration, suspected pancreatitis, injection-site infections, and hospitalization. The agency has issued warning letters to multiple online sellers and is coordinating with international regulatory partners to disrupt the supply chain.\n\nConsumers are urged to purchase prescription weight-loss medications only from licensed U.S. pharmacies, to use the FDA's BeSafeRx tool to verify pharmacy legitimacy, to discuss any compounded alternative with their prescriber, and to report suspected counterfeit products through MedWatch. Healthcare providers are encouraged to specifically ask patients about the source of GLP-1 medications and to remain vigilant for atypical clinical presentations that may reflect counterfeit or adulterated product exposure."),
    ("FDA Strengthens Boxed Warning for Quinolone Antibiotics", "FDA Alerts", "The FDA has further strengthened the boxed warning on fluoroquinolone antibiotics-including ciprofloxacin, levofloxacin, moxifloxacin, ofloxacin, and gemifloxacin-to more prominently describe the risk of aortic aneurysm and aortic dissection, in addition to previously highlighted risks of tendon rupture, peripheral neuropathy, central nervous system effects, hypoglycemia, and disabling, potentially permanent adverse effects involving multiple body systems.\n\nThe updated labeling reflects accumulated postmarket safety data, including large epidemiologic studies showing approximately a twofold increase in the relative risk of aortic aneurysm or dissection in fluoroquinolone-exposed patients compared with matched controls. Absolute risk remains low overall, but risk is meaningfully elevated in patients with known aortic aneurysm, those with risk factors such as hypertension, peripheral atherosclerotic vascular disease, or connective tissue disorders (including Marfan syndrome and Ehlers-Danlos syndrome), and older adults.\n\nThe FDA reiterated that, because of the cumulative risks across multiple organ systems, fluoroquinolones should be reserved for serious bacterial infections without alternative treatment options when used for acute uncomplicated urinary tract infection, acute sinusitis, or acute exacerbations of chronic bronchitis. For these indications, the risks generally outweigh the benefits when adequate alternatives exist.\n\nProviders are advised to avoid fluoroquinolones, when feasible, in patients with known or suspected aortic disease and to consider alternative agents in older adults and others at elevated risk. Patients on fluoroquinolones who develop sudden, severe chest, abdominal, or back pain should seek immediate emergency evaluation.\n\nThe agency continues to monitor postmarket safety and has signaled that additional labeling actions could follow if new safety signals emerge."),
    ("FDA Recalls Eye Drops Due to Contamination Concerns", "FDA Alerts", "The FDA has announced a voluntary nationwide recall of several lots of over-the-counter artificial tear and lubricating eye drop products following identification of potential bacterial contamination during a routine manufacturing facility inspection. The affected products include certain single-dose preservative-free formulations and multi-dose bottled products distributed under multiple private-label brands but manufactured at a common facility.\n\nThe contamination concern centers on a multidrug-resistant strain of Pseudomonas aeruginosa, which has been linked in prior recalls of related products to severe ocular infections, vision loss requiring enucleation in a small number of patients, and bloodstream infections in immunocompromised individuals. While no confirmed infections have yet been associated with the currently recalled lots, the FDA is acting out of an abundance of caution following the identification of environmental contamination at the manufacturing site.\n\nConsumers are advised to immediately stop using affected products, to dispose of them per manufacturer instructions, and to monitor for symptoms of ocular infection-eye redness, pain, discharge, blurred vision, light sensitivity, or feeling that something is in the eye. Anyone experiencing these symptoms after use of a recalled product should seek prompt evaluation by an ophthalmologist or urgent care provider.\n\nThe agency reminded consumers that ophthalmic products should be obtained only from reputable sources, that single-dose preservative-free formulations should be discarded after one use, and that multi-dose bottles should never be shared or used past the labeled in-use period after opening. Pharmacists have been advised to quarantine affected stock and to assist patients in selecting unaffected alternatives.\n\nThe FDA continues to investigate the root cause and is coordinating with state public health authorities, the Centers for Disease Control and Prevention, and the manufacturer regarding corrective actions."),
    ("FDA Warns of Counterfeit Ozempic in Distribution Channels", "FDA Alerts", "The FDA has identified counterfeit Ozempic (semaglutide) injection products that appear to have entered the legitimate U.S. drug supply chain and is warning patients, pharmacies, and wholesalers to be alert for suspicious products. The counterfeits, recovered from limited but geographically dispersed channels, mimic the appearance of authentic 1 mg prefilled pens but bear an unauthorized lot number and have been found, in initial laboratory analysis, to contain incorrect or undeclared substances.\n\nThe agency has provided specific lot identifiers and visual cues to help distinguish authentic from counterfeit product, including packaging differences in the carton, irregularities in the pen label, missing or altered serial numbers, and inconsistencies in the needle assembly. Pharmacists are urged to quarantine product from the identified lot pending verification, to obtain Ozempic only from authorized wholesalers, and to scrutinize unusual purchasing offers, particularly those at substantial discounts to wholesale acquisition cost.\n\nAdverse event reports associated with the suspect product include unexpected hypoglycemia, injection-site reactions, and one report of a sterile abscess that progressed to require surgical drainage. No confirmed deaths have been linked to the counterfeits at this time, but the agency is treating the investigation as a high priority and is coordinating with the manufacturer, distributors, and state boards of pharmacy.\n\nPatients are advised to inspect their Ozempic packaging upon receipt, to confirm that the lot number does not match the identified counterfeit lots, and to contact their pharmacy or the manufacturer's patient support line with concerns. Anyone who has used a suspected counterfeit product and experienced adverse effects should seek medical care and report the event through the FDA's MedWatch program.\n\nThe FDA reiterated longstanding guidance that prescription medications should be obtained only from licensed U.S. pharmacies and that products purchased through unverified online sellers or social media advertisements carry substantial risks of being counterfeit, adulterated, or substandard."),
    ("Phase 3 Trial Begins for Novel Alzheimer's Disease Therapy", "Clinical Trials", "A multinational pharmaceutical sponsor has announced the initiation of a global phase 3 clinical trial evaluating a novel anti-amyloid monoclonal antibody for the treatment of early symptomatic Alzheimer's disease. The trial is designed to enroll approximately 1,800 participants with mild cognitive impairment or mild dementia due to Alzheimer's disease and confirmed amyloid pathology on positron emission tomography (PET) imaging or cerebrospinal fluid biomarkers.\n\nThe randomized, double-blind, placebo-controlled study will compare the investigational antibody, administered by intravenous infusion every four weeks, with matching placebo over a treatment period of 18 months. The primary efficacy endpoint is change from baseline in the Clinical Dementia Rating-Sum of Boxes (CDR-SB) score, a global measure of cognitive and functional decline. Secondary endpoints include change in Alzheimer's Disease Assessment Scale-Cognitive subscale (ADAS-Cog), Alzheimer's Disease Cooperative Study Activities of Daily Living scale, amyloid PET burden, plasma phosphorylated tau-217 levels, and incidence of amyloid-related imaging abnormalities (ARIA).\n\nThe sponsor reports that earlier-phase studies demonstrated dose-dependent reductions in cerebral amyloid plaque, with a tolerability profile consistent with other agents in the class. ARIA-edema (ARIA-E) and ARIA-microhemorrhage (ARIA-H) remain the principal safety concerns and will be monitored with serial MRI scans according to a structured protocol. Apolipoprotein E genotyping will be performed at screening and used to stratify monitoring intensity.\n\nEnrollment will occur at more than 200 sites across North America, Europe, Asia, and Latin America. The sponsor has committed to including underrepresented populations in dementia trials and has implemented site selection and outreach strategies aimed at increasing the diversity of trial participants.\n\nResults are expected within approximately three years of completion of enrollment. The trial is one of several late-phase studies in the rapidly evolving disease-modifying therapy landscape for Alzheimer's disease and will help inform the comparative effectiveness, safety, and value of emerging treatment options."),
    ("Clinical Trial Shows Promise for New Long-acting Insulin", "Clinical Trials", "A once-weekly basal insulin formulation has demonstrated comparable glycemic efficacy and a favorable hypoglycemia profile relative to daily basal insulin glargine U-100 in a phase 3 randomized clinical trial of adults with type 2 diabetes who require basal insulin therapy. The findings, presented this week at a major endocrinology meeting and published simultaneously, support the potential for substantially reduced injection burden in patients managing type 2 diabetes.\n\nThe 52-week open-label, parallel-group trial randomized approximately 1,000 insulin-naïve participants with type 2 diabetes inadequately controlled on oral antihyperglycemic agents to once-weekly investigational insulin or once-daily insulin glargine, each titrated to achieve fasting glucose targets. The primary endpoint of change in glycated hemoglobin (A1c) from baseline to week 52 demonstrated noninferiority of the weekly insulin, with mean A1c reductions of approximately 1.4 percentage points in both arms.\n\nLevel 2 and 3 hypoglycemia rates were numerically lower with the weekly formulation, and patient-reported outcomes related to treatment satisfaction and convenience favored the weekly arm. Weight change and overall adverse event profiles were similar between groups. Injection-site reactions and mild dosing-day-related glucose variability were reported with the weekly insulin and were typically mild.\n\nThe pharmacokinetic profile of the weekly insulin is engineered to provide steady-state basal coverage with attenuated peak-trough variation, achieved through albumin binding and reduced clearance. Dose adjustment algorithms used in the trial were designed to limit the risk of accumulated hypoglycemia during titration.\n\nInvestigators noted that the trial population was limited to adults with type 2 diabetes; dedicated studies in type 1 diabetes are ongoing and will help clarify the role of weekly basal insulin in that population, where higher glycemic variability and greater hypoglycemia risk warrant additional caution. The investigational product is under regulatory review and could become available in the coming year pending agency action."),
    ("Cancer Immunotherapy Trial Reports Encouraging Survival Results", "Clinical Trials", "Updated results from an ongoing international phase 3 trial show clinically meaningful improvements in overall survival with a combination immunotherapy regimen for patients with advanced unresectable or metastatic melanoma. The findings, presented at a major oncology meeting and simultaneously published in a leading journal, are expected to influence first-line treatment guidelines for this aggressive disease.\n\nThe trial randomized approximately 950 treatment-naïve patients to receive a programmed cell death-1 (PD-1) inhibitor in combination with a lymphocyte-activation gene 3 (LAG-3) antagonist, versus PD-1 inhibitor monotherapy. At a median follow-up of approximately 40 months, the combination arm demonstrated a statistically significant improvement in overall survival, with a hazard ratio of approximately 0.76. Median progression-free survival and objective response rates also favored the combination.\n\nSubgroup analyses indicated benefit across most prespecified strata, including BRAF mutation status, baseline lactate dehydrogenase levels, and PD-L1 expression categories. Patients with brain metastases at baseline-a population traditionally with poor outcomes-also derived survival benefit.\n\nThe combination was associated with higher rates of immune-related adverse events, including thyroiditis, hepatitis, colitis, pneumonitis, and rare cases of myocarditis. Treatment discontinuation due to adverse events occurred in approximately 18 percent of combination-arm patients compared with 11 percent in the monotherapy arm. The investigators emphasized the importance of multidisciplinary management of immune-related toxicities, including early recognition and treatment with corticosteroids per established algorithms.\n\nDiscussants at the meeting noted that the results add to a growing portfolio of immunotherapy combinations transforming melanoma outcomes, but underscored the need for biomarker development to identify patients most likely to benefit and least likely to experience serious toxicity. Cost-effectiveness analyses and equitable access considerations will be important for translating trial benefits into broad population-level impact."),
    ("Researchers Begin Trial of Oral GLP-1 for Obesity", "Clinical Trials", "Investigators have begun enrollment in a global phase 3 trial evaluating a once-daily oral glucagon-like peptide-1 (GLP-1) receptor agonist for chronic weight management in adults with obesity or overweight and at least one weight-related comorbidity. The trial reflects a broader industry effort to develop oral formulations of GLP-1 agents, which have historically required subcutaneous injection.\n\nThe randomized, double-blind, placebo-controlled study plans to enroll approximately 2,400 participants across North America, Europe, Asia, and Latin America. Participants will be randomized to one of two oral doses of the investigational agent or to matching placebo, with all groups receiving structured lifestyle intervention including reduced-calorie diet, physical activity counseling, and behavioral support. The primary endpoint is percent change in body weight from baseline to week 68; key secondary endpoints include the proportion of participants achieving 5, 10, 15, and 20 percent weight reduction, change in waist circumference, and change in cardiometabolic risk factors.\n\nThe investigational agent uses an absorption-enhancer technology to overcome the low oral bioavailability characteristic of peptide therapeutics. Earlier-phase studies suggested weight reductions in a range broadly comparable to injectable GLP-1 agents at the highest doses, with a similar gastrointestinal adverse event profile.\n\nSafety monitoring will include cardiovascular events, pancreatitis, gallbladder disease, suicidal ideation and behavior, and thyroid C-cell tumor signals. The sponsor has also incorporated a cardiovascular outcomes substudy in a high-risk subset to inform potential expanded indications.\n\nResults are anticipated in approximately two years. An oral GLP-1 option, if approved, could meaningfully expand access by addressing injection-related barriers, simplifying supply chain and storage requirements, and potentially reducing manufacturing complexity. However, the requirement for careful dosing conditions (fasting state and limited water intake at administration) may pose adherence challenges that the trial design specifically intends to evaluate."),
    ("Trial Investigates Microbiome Therapy for Recurrent C. difficile", "Clinical Trials", "Investigators are enrolling adult participants in a phase 3 randomized controlled trial of an investigational live oral microbiome therapeutic for the prevention of recurrent Clostridioides difficile infection (CDI). Recurrent CDI affects approximately 20 to 35 percent of patients following an initial episode and represents a major source of morbidity, healthcare cost, and antimicrobial use.\n\nThe trial will enroll approximately 600 adults who have completed standard-of-care antibiotic therapy (vancomycin or fidaxomicin) for a confirmed CDI episode and have at least one recurrence within the prior six months. Participants will be randomized to receive a defined consortium of Firmicutes-rich bacterial spores or matching placebo capsules following completion of antibiotic therapy. The primary endpoint is recurrence of CDI through week 8, with longer-term follow-up to one year for durability of effect.\n\nThe investigational therapeutic, derived from rigorously screened healthy donor stool, undergoes a proprietary purification and ethanol-treatment process to enrich for spore-forming Firmicutes while inactivating potential pathogens, eggs, and viruses. Earlier-phase trials demonstrated meaningful reductions in CDI recurrence relative to placebo with a favorable safety profile.\n\nSafety monitoring will include all-cause infections, allergic and gastrointestinal adverse events, and screening for transmissible pathogens despite the manufacturing controls. The trial protocol includes detailed adverse event adjudication and microbiome composition tracking in a substudy designed to identify pharmacodynamic correlates of clinical response.\n\nIf the trial confirms efficacy, the therapeutic would join a small but growing class of microbiome-based products that have transformed the management of recurrent CDI. Investigators emphasized that prevention of CDI through antimicrobial stewardship, careful evaluation of the necessity of acid-suppressing medications, and infection prevention practices remain the most impactful interventions at a population level, even as new therapeutics become available for established disease."),

    # --- FDA Alerts (expanded) ---
    ("FDA Issues Safety Communication About Acetaminophen and Liver Risk", "FDA Alerts", "The U.S. Food and Drug Administration today issued a renewed Drug Safety Communication reminding clinicians and consumers about the risk of severe liver injury associated with acetaminophen at doses above 4 grams per day in adults.\n\nThe agency reviewed adverse event reports from the past three years and identified hundreds of cases of acute liver failure, many of which involved unintentional overdose from concurrent use of multiple acetaminophen-containing products. Combination cold-and-flu remedies, prescription opioid-acetaminophen tablets, and over-the-counter pain relievers were frequently implicated.\n\nThe FDA recommends that healthcare providers review a patient's full medication list before prescribing additional acetaminophen products, with particular attention to patients who consume alcohol regularly or who have pre-existing liver disease. Consumers are urged to read the active ingredients panel on every product and to avoid exceeding 3 grams per day without medical supervision.\n\nLabeling updates affecting prescription combination products will be implemented within the next six months. The FDA continues to evaluate whether further regulatory action is warranted."),
    ("FDA Approves New Label Warnings for SGLT2 Inhibitor Class", "FDA Alerts", "The FDA has required updated labeling across the SGLT2 inhibitor class to highlight the risk of euglycemic diabetic ketoacidosis, a condition in which patients develop ketoacidosis despite blood glucose levels that appear near-normal.\n\nThe class, which includes dapagliflozin, empagliflozin, and canagliflozin, has been the subject of mounting postmarket reports describing ketoacidosis presentations that delay diagnosis because patients lack the marked hyperglycemia clinicians expect. Several cases occurred perioperatively or during acute illness.\n\nThe updated Warnings and Precautions section advises clinicians to assess for ketoacidosis in any patient on an SGLT2 inhibitor presenting with nausea, vomiting, abdominal pain, fatigue, or shortness of breath, regardless of glucose level. The label also recommends withholding the medication for at least three days prior to scheduled surgery.\n\nThe FDA emphasized that the cardiovascular and renal benefits of SGLT2 inhibitors continue to outweigh the risks for appropriately selected patients."),
    ("FDA Alerts Providers About Ongoing Shortage of Amoxicillin Oral Suspension", "FDA Alerts", "The FDA has added amoxicillin oral suspension to its drug shortage list, citing supply constraints affecting multiple manufacturers heading into the respiratory illness season.\n\nPediatric formulations are most affected, and the agency is working with manufacturers to expedite production. In the interim, the FDA suggests clinicians consider therapeutic alternatives such as amoxicillin tablets or capsules where appropriate, compounded suspensions from licensed pharmacies, or alternative first-line antibiotics for specific indications.\n\nPharmacists are encouraged to check wholesaler availability daily and to communicate proactively with prescribers when substitutions are required. The FDA reiterated that the shortage does not reflect a safety concern with the drug itself."),
    ("Recall Notice: Multiple Lots of Levothyroxine Recalled Due to Subpotency", "FDA Alerts", "A manufacturer has initiated a voluntary nationwide recall of several lots of levothyroxine sodium tablets after stability testing revealed the product may be subpotent prior to its labeled expiration date.\n\nSubpotent levothyroxine can result in inadequate thyroid hormone replacement, with potential consequences including fatigue, weight gain, cold intolerance, and, in pregnant patients, adverse fetal outcomes. No serious adverse events have been confirmed at this time.\n\nPatients should not stop taking their medication abruptly but should contact their pharmacy to determine whether their supply is affected and to arrange replacement. Healthcare providers are advised to recheck TSH levels in patients who report new or worsening hypothyroid symptoms after using a recalled lot."),
    ("FDA Strengthens Cardiac Warning for Azithromycin", "FDA Alerts", "The FDA has strengthened the cardiac warning on azithromycin labeling following a comprehensive review of QT-interval data and reports of fatal arrhythmias in at-risk patients.\n\nThe updated warning more clearly identifies populations at elevated risk, including patients with known QT prolongation, hypokalemia, hypomagnesemia, clinically significant bradycardia, or concurrent use of Class IA or III antiarrhythmics. Clinicians are urged to consider alternative antibiotics for these patients when feasible.\n\nThe agency stressed that azithromycin remains an important option for many infections and that the absolute risk of serious arrhythmia is low in patients without predisposing conditions."),
    ("Safety Communication: Long-Term Proton Pump Inhibitor Use Linked to Fracture Risk", "FDA Alerts", "The FDA today reiterated its longstanding safety communication regarding the association between long-term, high-dose proton pump inhibitor use and an increased risk of fractures of the hip, wrist, and spine.\n\nReview of additional observational data and meta-analyses continues to support the association, particularly for users of more than one year and those over age 50. The mechanism is not fully established but may involve reduced calcium absorption and altered bone remodeling.\n\nThe agency recommends that clinicians prescribe the lowest effective dose for the shortest duration consistent with the condition being treated and periodically reassess the ongoing need for therapy. Over-the-counter PPI products remain limited to 14-day courses up to three times per year."),
    ("FDA Requires New Boxed Warning for Janus Kinase Inhibitor Class", "FDA Alerts", "The FDA has required a new boxed warning across the Janus kinase (JAK) inhibitor class addressing increased risks of serious cardiovascular events, malignancy, thrombosis, and mortality observed in a large postmarket safety trial.\n\nThe boxed warning applies to tofacitinib, baricitinib, and upadacitinib when used for chronic inflammatory conditions. The FDA also limited certain indications to patients who have had an inadequate response or intolerance to one or more TNF blockers.\n\nProviders should discuss the updated risk profile with patients prior to initiation and document an informed treatment decision. Patients currently on JAK inhibitors should not discontinue therapy without consulting their prescriber."),
    ("MedWatch: Lamotrigine Associated With Severe Skin Reactions Including Stevens-Johnson Syndrome", "FDA Alerts", "The FDA's MedWatch program has issued a reminder regarding the risk of life-threatening cutaneous reactions, including Stevens-Johnson syndrome and toxic epidermal necrolysis, associated with lamotrigine, particularly during the first two to eight weeks of therapy.\n\nRisk is increased with rapid dose titration, concurrent valproate use, and prior history of antiepileptic drug-related rash. Pediatric patients appear to be at higher relative risk than adults.\n\nProviders are reminded to follow the recommended titration schedule precisely, to counsel patients to report any rash immediately, and to discontinue lamotrigine at the first sign of rash unless clearly unrelated to the drug."),
    ("FDA Drug Safety Communication: NSAIDs and Risk of Renal Impairment in Older Adults", "FDA Alerts", "The FDA has issued an updated Drug Safety Communication regarding the risk of acute kidney injury and chronic renal impairment in older adults taking nonsteroidal anti-inflammatory drugs, particularly at higher doses or for prolonged periods.\n\nThe communication highlights additional risk in patients with pre-existing chronic kidney disease, heart failure, cirrhosis, volume depletion, or concomitant use of ACE inhibitors, ARBs, or diuretics-the so-called 'triple whammy' combination.\n\nClinicians are encouraged to consider acetaminophen, topical NSAIDs, or non-pharmacologic strategies where appropriate, and to monitor renal function and blood pressure in patients who require systemic NSAID therapy."),
    ("Postmarket Drug Safety Information: Citalopram and QT Prolongation", "FDA Alerts", "The FDA has reaffirmed prescribing restrictions for citalopram based on continued postmarket evidence of dose-dependent QT-interval prolongation.\n\nThe maximum recommended dose remains 40 mg per day for most adults and 20 mg per day for patients older than 60, those with hepatic impairment, poor CYP2C19 metabolizers, or those taking concurrent CYP2C19 inhibitors. Doses above these limits are not recommended in any population.\n\nProviders should obtain a baseline ECG in patients with cardiovascular risk factors and correct hypokalemia and hypomagnesemia before initiation."),

    # --- New Drug Approvals (expanded) ---
    ("FDA Approves Lecanemab for Early Alzheimer's Disease", "New Drug Approvals", "The FDA has granted traditional approval to lecanemab, an anti-amyloid monoclonal antibody, for the treatment of mild cognitive impairment or mild dementia due to Alzheimer's disease in patients with confirmed amyloid pathology.\n\nApproval was based on a confirmatory phase 3 trial that demonstrated a statistically significant slowing of clinical decline on the Clinical Dementia Rating-Sum of Boxes scale over 18 months. Imaging studies showed substantial reductions in cerebral amyloid plaque burden.\n\nThe label carries a boxed warning for amyloid-related imaging abnormalities (ARIA), and prescribers must enroll in a structured monitoring program that includes serial MRI scans during the initial dosing period."),
    ("FDA Grants Breakthrough Therapy Designation to Novel Gene Therapy for Sickle Cell Disease", "New Drug Approvals", "The FDA has granted Breakthrough Therapy Designation to an investigational gene therapy for severe sickle cell disease, citing preliminary trial data showing a meaningful reduction in vaso-occlusive crises.\n\nThe one-time therapy uses CRISPR-based editing of autologous hematopoietic stem cells to reactivate fetal hemoglobin production. Patients in the lead-in cohort have remained free of severe pain crises for more than two years following infusion.\n\nThe designation will expedite the FDA's review of the eventual Biologics License Application and provides for closer agency engagement during late-stage development."),
    ("FDA Approves First Generic of Suboxone Sublingual Film", "New Drug Approvals", "The FDA has approved the first generic version of buprenorphine/naloxone sublingual film for the maintenance treatment of opioid use disorder, expanding affordable access to a medication central to outpatient addiction care.\n\nThe approval follows a rigorous review of bioequivalence and dissolution data. Public health officials welcomed the expanded supply, citing persistent gaps in medication for opioid use disorder despite the elimination of the X-waiver requirement.\n\nThe generic product is expected to reach pharmacies within the next quarter."),
    ("FDA Approves Adalimumab Biosimilar, Bringing Cost Relief", "New Drug Approvals", "A new adalimumab biosimilar has received FDA approval and is expected to launch later this year, joining a growing market of adalimumab competitors.\n\nThe biosimilar is approved for all indications of the reference product, including rheumatoid arthritis, psoriatic arthritis, ankylosing spondylitis, Crohn's disease, ulcerative colitis, plaque psoriasis, and hidradenitis suppurativa. Interchangeability designation will require additional switching study data currently under review.\n\nPayer formulary placement and rebate dynamics will largely determine the actual savings realized by patients."),
    ("FDA Approves New Indication: Semaglutide for Reduction of Cardiovascular Events", "New Drug Approvals", "The FDA has approved a new indication for semaglutide injection: reduction of major adverse cardiovascular events in adults with established cardiovascular disease and either obesity or overweight.\n\nThe approval is based on a large cardiovascular outcomes trial showing a 20% relative reduction in the composite endpoint of cardiovascular death, nonfatal myocardial infarction, and nonfatal stroke versus placebo over a median follow-up of about three years.\n\nThe new indication marks the first time a weight-management medication has demonstrated and obtained labeling for cardiovascular benefit independent of diabetes status."),
    ("FDA Approves Cystic Fibrosis Triple Combination Therapy for Children Ages 2-5", "New Drug Approvals", "The FDA has approved the elexacaftor/tezacaftor/ivacaftor combination for pediatric patients with cystic fibrosis aged 2 through 5 years who have at least one F508del mutation or another responsive mutation.\n\nThe pediatric approval was supported by safety and pharmacokinetic data from an open-label trial, in which young children showed sweat chloride reductions consistent with those previously observed in older patients.\n\nClinicians emphasize that early initiation of CFTR modulator therapy may meaningfully alter the long-term trajectory of lung disease."),
    ("Accelerated Approval Granted to New Therapy for Duchenne Muscular Dystrophy", "New Drug Approvals", "The FDA has granted accelerated approval to a new exon-skipping therapy for ambulatory pediatric patients with Duchenne muscular dystrophy and a confirmed mutation amenable to exon 53 skipping.\n\nApproval was based on a surrogate endpoint-an increase in dystrophin protein-considered reasonably likely to predict clinical benefit. Continued approval is contingent on results from an ongoing confirmatory trial assessing motor function outcomes.\n\nThe therapy is administered as weekly intravenous infusions and joins a growing class of mutation-specific options for this devastating childhood disease."),
    ("FDA Approves Fixed-Dose Combination of Empagliflozin and Linagliptin", "New Drug Approvals", "The FDA has approved a single-tablet fixed-dose combination of empagliflozin and linagliptin for use as an adjunct to diet and exercise in adults with type 2 diabetes.\n\nThe combination pairs an SGLT2 inhibitor with a DPP-4 inhibitor, providing complementary mechanisms of action and the convenience of once-daily dosing. Approval was supported by trials demonstrating significant A1c reductions versus either component alone.\n\nThe fixed-dose product is not indicated for type 1 diabetes or for treatment of diabetic ketoacidosis."),

    # --- Medical (expanded) ---
    ("Large Trial Finds Empagliflozin Reduces Cardiovascular Events by 14% in High-Risk Patients", "Medical", "A randomized trial of nearly 7,000 patients with type 2 diabetes and established cardiovascular disease has found that empagliflozin reduced the composite endpoint of cardiovascular death, nonfatal myocardial infarction, and nonfatal stroke by 14% compared with placebo over a median 3.1 years of follow-up.\n\nMortality benefits were driven primarily by a 38% reduction in cardiovascular death and a 35% reduction in hospitalization for heart failure. The renal composite endpoint was also improved.\n\nThe results, replicated in subsequent trials of the SGLT2 inhibitor class, have transformed the management of type 2 diabetes in patients with cardiovascular and renal comorbidities."),
    ("Research: Long-Term ACE Inhibitor Use May Affect Kidney Function in Subset of Patients", "Medical", "A large observational cohort study has identified a subset of patients in whom long-term ACE inhibitor use is associated with a gradual decline in estimated glomerular filtration rate, particularly among patients with baseline CKD stage 3b or higher.\n\nThe authors caution that the observational design cannot establish causation and note that the cardioprotective and antiproteinuric benefits of ACE inhibition remain well established for most patients.\n\nClinicians are reminded to monitor renal function and potassium periodically and to individualize therapy in patients with advanced kidney disease."),
    ("Metformin Shows Reduced Cancer Incidence in Large Diabetes Cohort", "Medical", "A pooled analysis of long-term diabetes registry data has found that patients with type 2 diabetes treated with metformin had a modestly lower incidence of several common cancers, including colorectal, breast, and pancreatic cancer, compared with patients on other glucose-lowering therapies.\n\nThe association persisted after adjustment for body mass index, smoking status, and duration of diabetes, though residual confounding cannot be excluded. Several proposed mechanisms, including AMPK activation and reduced insulin/IGF-1 signaling, remain under investigation.\n\nDespite intriguing observational data, metformin is not currently recommended for cancer prevention outside of clinical trials."),
    ("Statin Therapy Reduces Stroke Risk Even Among Patients With Low Baseline LDL", "Medical", "Secondary analyses of a large primary prevention trial suggest that statin therapy reduces ischemic stroke risk even among patients with LDL cholesterol below 100 mg/dL at baseline.\n\nThe benefit was consistent across age groups and was apparent within the first two years of therapy. The authors hypothesize that pleiotropic effects on endothelial function and plaque stabilization may contribute beyond LDL lowering alone.\n\nGuidelines continue to recommend statin therapy decisions based on absolute cardiovascular risk rather than LDL threshold alone."),
    ("GLP-1 Receptor Agonists Show Sustained Weight Loss Benefits at Two Years", "Medical", "Long-term follow-up data from extension studies of GLP-1 receptor agonist trials show that the substantial weight loss observed in initial trials is largely maintained at two years among patients who continue therapy, with mean weight reductions of 12-17% from baseline depending on the agent and dose.\n\nDiscontinuation is associated with substantial regain, underscoring that obesity is a chronic disease requiring chronic management. Common side effects-nausea, vomiting, and diarrhea-tend to diminish over time but may limit tolerability in some patients.\n\nAccess and affordability remain significant barriers for many patients eligible for therapy."),
    ("New Research on Antidepressant Efficacy Across Patient Subgroups", "Medical", "A network meta-analysis encompassing more than 500 trials has provided updated comparative-efficacy estimates for second-generation antidepressants in adults with major depressive disorder.\n\nWhile differences between agents were modest in head-to-head comparisons, escitalopram and sertraline emerged as favorable options in terms of the balance between efficacy and acceptability. Effects in subgroups defined by symptom severity and prior treatment response varied meaningfully.\n\nThe authors emphasize that antidepressant selection should remain individualized based on patient comorbidities, side effect profile, drug interactions, and patient preference."),
    ("Antibiotics and the Gut Microbiome: What Recent Research Shows", "Medical", "A growing body of research has documented that even short courses of broad-spectrum antibiotics can produce lasting changes in the gut microbiome, with full recovery sometimes taking months.\n\nClinical correlates of antibiotic-induced dysbiosis under active investigation include Clostridioides difficile infection, antibiotic-associated diarrhea, and potential downstream effects on immune and metabolic function.\n\nThe findings reinforce stewardship principles: prescribe antibiotics only when indicated, choose the narrowest-spectrum effective agent, and use the shortest duration supported by evidence."),
    ("Opioid Crisis Update: Revised Prescribing Guidelines Aim to Reduce Misuse Without Undertreatment", "Medical", "Updated CDC guidelines for opioid prescribing emphasize a more flexible, individualized approach to pain management compared with earlier iterations, while retaining a strong recommendation to maximize nonopioid and nonpharmacologic therapies first.\n\nThe revisions address concerns that prior numeric thresholds were sometimes applied rigidly, leading to abrupt tapers and inadequately treated pain in patients on stable long-term therapy. Shared decision-making and careful monitoring remain central.\n\nThe guidelines do not apply to active cancer treatment, palliative care, or end-of-life care."),
    ("Cannabis and Drug Interactions: What Patients Should Know", "Medical", "Pharmacologists are increasingly raising awareness of clinically meaningful interactions between cannabis products and prescription medications, particularly those metabolized by CYP3A4, CYP2C9, and CYP2C19.\n\nCannabidiol (CBD) is a notable inhibitor of several CYP enzymes and can elevate concentrations of clobazam, warfarin, tacrolimus, and others. THC may add to sedation from benzodiazepines, opioids, and certain antidepressants.\n\nPatients are encouraged to disclose all cannabis use-medical or recreational-to their prescribers and pharmacists so that interaction risks can be evaluated."),
    ("Proton Pump Inhibitors: Weighing Benefits and Risks for Long-Term Use", "Medical", "Long-term proton pump inhibitor (PPI) therapy provides important benefit for patients with severe reflux, Barrett's esophagus, and risk factors for upper GI bleeding, but observational data have linked extended use to a range of potential harms including B12 deficiency, hypomagnesemia, fractures, and certain infections.\n\nThe absolute increase in risk for any individual outcome is small, but the cumulative effect across millions of long-term users is clinically meaningful. Periodic reassessment of the indication is appropriate.\n\nIn many patients with uncomplicated reflux, dose reduction, on-demand dosing, or transition to H2 blockers may be viable strategies."),
    ("COVID-19 Treatment Updates: Antiviral Effectiveness in 2025", "Medical", "Updated effectiveness data from real-world studies confirm that nirmatrelvir-ritonavir reduces hospitalization and death among high-risk outpatients with COVID-19, though absolute benefit is smaller in vaccinated patients than was observed in the original placebo-controlled trial.\n\nDrug-drug interactions, particularly with statins, antiarrhythmics, and immunosuppressants, continue to require careful review prior to prescribing. Remdesivir remains an option for hospitalized patients and some high-risk outpatients who cannot take nirmatrelvir-ritonavir.\n\nMonoclonal antibody therapies have largely fallen out of use due to loss of activity against currently circulating variants."),
    ("ADHD Medication Shortages: Causes and What Patients Should Do", "Medical", "Persistent shortages of stimulant medications used to treat attention-deficit/hyperactivity disorder continue to disrupt care for many patients, with shortages reflecting a combination of increased demand, manufacturing constraints, and DEA quota limitations on controlled substances.\n\nThe FDA and DEA have taken several steps to expand supply, but patients and prescribers are encouraged to plan ahead, call pharmacies in advance to confirm stock, and discuss alternative formulations or non-stimulant therapies where clinically appropriate.\n\nAbrupt discontinuation of stimulants is generally not associated with physiologic withdrawal, but may produce a return of ADHD symptoms that affect daily functioning."),

    # --- Clinical Trials (expanded) ---
    ("Phase 3 Trial of Tirzepatide Shows Substantial Weight Loss in Patients Without Diabetes", "Clinical Trials", "A 72-week phase 3 trial of tirzepatide in adults with obesity or overweight and at least one weight-related comorbidity has reported mean weight reductions of approximately 20% at the highest dose, with concurrent improvements in cardiometabolic risk factors.\n\nThe most common adverse events were gastrointestinal-nausea, diarrhea, and constipation-which were typically transient and dose-related. Trial discontinuation due to adverse events was modest.\n\nThe results expand the evidence base supporting GIP/GLP-1 dual agonism as a strategy for chronic weight management."),
    ("Combination Therapy Outperforms Standard of Care in Advanced Renal Cell Carcinoma Trial", "Clinical Trials", "A phase 3 trial evaluating a combination of an immune checkpoint inhibitor plus a tyrosine kinase inhibitor has reported improved progression-free survival and overall response rate compared with sunitinib monotherapy in patients with previously untreated advanced renal cell carcinoma.\n\nGrade 3 or higher adverse events were more frequent with the combination, and discontinuation rates were correspondingly higher. Patient selection and toxicity management will be key considerations in adoption.\n\nThe findings are expected to inform updated treatment guidelines for advanced renal cell carcinoma."),
    ("Landmark NEJM Trial Demonstrates Dapagliflozin Benefit in Heart Failure With Preserved Ejection Fraction", "Clinical Trials", "Results published in the New England Journal of Medicine from a large randomized trial show that dapagliflozin reduced the composite primary endpoint of worsening heart failure or cardiovascular death in patients with heart failure and preserved or mildly reduced ejection fraction.\n\nBenefit was consistent across ejection fraction subgroups and irrespective of diabetes status. Renal endpoints and quality-of-life measures also favored dapagliflozin.\n\nThe trial adds to a growing body of evidence supporting SGLT2 inhibitors as foundational therapy across the full spectrum of heart failure."),
    ("Personalized Dosing of Vancomycin Improves Outcomes in Critically Ill Patients", "Clinical Trials", "A pragmatic randomized trial comparing AUC-guided personalized dosing of vancomycin with traditional trough-based dosing in critically ill adults has reported reduced rates of acute kidney injury and improved early target attainment.\n\nThe AUC-guided strategy used Bayesian software-assisted dose adjustment from limited blood samples. Implementation required pharmacy infrastructure and clinician training but did not increase length of stay.\n\nProfessional societies have increasingly endorsed AUC-based monitoring for vancomycin, and this trial provides prospective support for the approach."),
    ("Clinical Data Supports Expanded Use of Direct Oral Anticoagulants in Elderly Patients", "Clinical Trials", "An age-stratified analysis of a large direct oral anticoagulant (DOAC) trial has reported favorable efficacy and safety in patients aged 75 and older with nonvalvular atrial fibrillation, with reduced rates of intracranial hemorrhage compared with warfarin.\n\nThe analysis controlled for baseline frailty, renal function, and concurrent antiplatelet use. The authors note that careful dose selection-particularly accounting for renal impairment and drug interactions-remains essential in older adults.\n\nThe findings support continued use of DOACs as first-line anticoagulants in most elderly patients with atrial fibrillation."),
    ("Gene Therapy Combined With Enzyme Replacement Shows Promise in Pompe Disease Trial", "Clinical Trials", "Interim results from an early-phase trial combining adeno-associated virus-mediated gene therapy with reduced-frequency enzyme replacement therapy in patients with late-onset Pompe disease have reported improvements in respiratory function and biomarkers of disease activity.\n\nThe combination approach is designed to provide sustained enzyme expression while bridging the early treatment period with conventional enzyme replacement. Larger studies are planned to confirm durability and to refine dosing.\n\nThe trial illustrates an emerging trend of combining gene-based therapies with established treatments to optimize patient outcomes."),

    # --- Health (new category) ---
    ("Understanding Your Prescription: What Beta-Blockers Do and How They Work", "Health", "Beta-blockers are a widely prescribed class of medications used to treat conditions including high blood pressure, certain abnormal heart rhythms, heart failure, angina, and migraine prophylaxis.\n\nThe medications work by blocking the action of adrenaline and similar hormones at beta-adrenergic receptors, slowing the heart rate and reducing the force of cardiac contraction. Different beta-blockers have differing selectivity for various receptor subtypes, which affects their side effect profiles and choice for specific conditions.\n\nCommon side effects include fatigue, cold extremities, and, less commonly, depressed mood or sexual dysfunction. Beta-blockers should generally not be stopped abruptly, especially in patients with coronary artery disease, as rebound effects can occur."),
    ("Drug-Food Interactions: Common Combinations to Avoid", "Health", "Many widely used medications can interact meaningfully with foods or beverages, sometimes producing unexpected changes in drug effect or risk of side effects.\n\nGrapefruit juice can elevate blood levels of certain statins, calcium channel blockers, and immunosuppressants by inhibiting intestinal CYP3A4. Leafy greens high in vitamin K can reduce the effectiveness of warfarin if consumed inconsistently. Tyramine-containing foods such as aged cheeses can produce dangerous blood pressure elevations in patients taking MAO inhibitors.\n\nPatients are encouraged to ask their pharmacist about food interactions when starting any new medication, and to maintain consistent dietary patterns when on warfarin or other interaction-prone drugs."),
    ("Medication Adherence: Practical Strategies to Never Miss a Dose", "Health", "Suboptimal medication adherence is among the most common preventable causes of poor outcomes in chronic disease, accounting for substantial avoidable morbidity and healthcare cost.\n\nPractical strategies that have been shown to improve adherence include using pill organizers, setting daily phone reminders, pairing medication doses with established daily routines, consolidating to once-daily formulations when available, and using automatic refill or 90-day mail-order programs.\n\nPatients should communicate openly with their providers about barriers to taking medication-cost, side effects, complexity of the regimen, or doubts about effectiveness-so that adjustments can be made before adherence problems lead to worsening disease."),
    ("Polypharmacy Risks: When Multiple Medications Become Dangerous", "Health", "Polypharmacy, generally defined as the concurrent use of five or more medications, becomes increasingly common with age and the accumulation of chronic conditions. The risk of clinically significant drug-drug interactions, additive side effects, and prescribing cascades rises sharply with each added medication.\n\nPeriodic comprehensive medication reviews-sometimes called 'brown bag' visits when patients bring all of their medications including over-the-counter products and supplements-can identify deprescribing opportunities. Tools such as the Beers Criteria highlight medications that are potentially inappropriate in older adults.\n\nThe goal is not necessarily fewer medications but the right medications, used at the right doses, for the right durations."),
    ("Medication Safety During Pregnancy: What Is Safe and What Is Not", "Health", "Pregnancy creates physiologic changes that can alter drug absorption, distribution, metabolism, and excretion, and many medications cross the placenta and can affect the developing fetus.\n\nSome medications-folic acid, levothyroxine, certain antihypertensives, and many antibiotics-are safe and important during pregnancy. Others-warfarin, ACE inhibitors, ARBs, methotrexate, isotretinoin, and several antiepileptic drugs-are known teratogens and should generally be avoided.\n\nWomen of reproductive age taking chronic medications should discuss preconception planning with their provider, as some medication changes are best made before conception. Decisions during pregnancy should balance the risk of medication exposure against the risk of untreated maternal disease."),
    ("How to Safely Discontinue SSRIs Without Withdrawal Symptoms", "Health", "Abrupt discontinuation of selective serotonin reuptake inhibitors (SSRIs)-particularly paroxetine and venlafaxine-can produce a discontinuation syndrome characterized by flu-like symptoms, sensory disturbances ('brain zaps'), dizziness, irritability, and sleep disturbance.\n\nA gradual taper over several weeks, with smaller dose reductions toward the end of the taper, generally allows discontinuation with minimal symptoms. Hyperbolic tapering using compounded smaller doses or liquid formulations may be appropriate for patients who experience symptoms with conventional tapering.\n\nDiscontinuation should be undertaken in collaboration with the prescriber and ideally with monitoring for return of depressive or anxiety symptoms."),
    ("Generic vs. Brand-Name Drugs: Are They Really the Same?", "Health", "FDA-approved generic medications contain the same active ingredient, strength, dosage form, and route of administration as their brand-name counterparts, and must demonstrate bioequivalence-meaning comparable rate and extent of absorption-within tightly defined statistical limits.\n\nFor the vast majority of medications, generic and brand-name products are clinically interchangeable. A small number of agents with narrow therapeutic indices-such as warfarin, levothyroxine, and certain antiepileptic drugs-warrant additional caution, and some patients may notice differences when switching among products from different manufacturers.\n\nGenerics typically cost 80-85% less than the brand-name equivalent and account for the majority of prescriptions filled in the United States."),
    ("Pill Splitting: Which Medications Can Safely Be Cut in Half?", "Health", "Pill splitting can be a reasonable way to reduce medication cost when prescribers and patients use it appropriately. Tablets that are scored, immediate-release, and not enteric-coated are generally suitable for splitting.\n\nMedications that should not be split include extended- or controlled-release products, enteric-coated tablets, capsules, sublingual products, and many oncology and hormonal therapies, as splitting can alter pharmacokinetics or expose the user to hazardous drug residues.\n\nPatients considering pill splitting should ask their pharmacist for guidance and use a dedicated pill splitter to improve accuracy."),

    # --- FDA Alerts (additional dated entries) ---
    ("FDA Issues Warning About Rare but Serious Liver Injury Risk with Xeljanz (Tofacitinib)", "FDA Alerts", "The U.S. Food and Drug Administration today issued a Drug Safety Communication describing a rare but serious risk of drug-induced liver injury in patients treated with tofacitinib (Xeljanz), a Janus kinase (JAK) inhibitor approved for rheumatoid arthritis, psoriatic arthritis, and ulcerative colitis.\n\nThe agency reviewed postmarket adverse event reports and identified a small number of cases of severe hepatocellular injury, including a subset that progressed to acute liver failure requiring transplantation. Most affected patients were on concomitant hepatotoxic medications such as methotrexate, and several had pre-existing chronic liver disease.\n\nThe FDA is requiring labeling updates that emphasize baseline and periodic monitoring of liver enzymes during therapy, with specific guidance to interrupt treatment for transaminase elevations greater than five times the upper limit of normal and to discontinue permanently if drug-induced liver injury is confirmed.\n\nClinicians are advised to counsel patients about symptoms of liver injury-fatigue, nausea, right upper quadrant discomfort, jaundice, and dark urine-and to instruct them to seek prompt evaluation if these occur. The agency reiterated that JAK inhibitors carry a class boxed warning for serious infections, malignancy, thrombosis, and cardiovascular events, and that the new hepatic findings add to the overall risk profile that should be discussed during shared decision-making.",
     "FDA Drug Safety Communication", "2024-01-15T00:00:00"),
    ("FDA Updates Labeling for Fluoroquinolone Antibiotics to Strengthen Warnings", "FDA Alerts", "The FDA has finalized labeling updates across the fluoroquinolone antibiotic class-including ciprofloxacin, levofloxacin, moxifloxacin, and ofloxacin-to strengthen warnings about the risk of tendon rupture, tendinitis, and peripheral neuropathy.\n\nThe updated Warnings and Precautions section emphasizes that tendon disorders, including Achilles tendon rupture, can occur within hours of starting therapy and up to several months after discontinuation. Risk is increased in patients older than 60, those on concomitant corticosteroids, and recipients of solid organ transplants.\n\nThe agency reiterated guidance issued in prior communications that fluoroquinolones should be reserved for serious bacterial infections without alternative treatment options when used for acute uncomplicated cystitis, acute sinusitis, or acute exacerbations of chronic bronchitis. Clinicians are advised to discontinue the antibiotic at the first sign of tendon pain, swelling, or inflammation and to avoid exercise of the affected area until tendon disorder is ruled out.\n\nThe FDA also reminded providers of the potential for disabling and potentially permanent adverse effects involving tendons, muscles, joints, nerves, and the central nervous system, which can occur together in the same patient.",
     "FDA Drug Safety Communication", "2023-11-08T00:00:00"),
    ("FDA Safety Communication: Increased Risk of Cardiovascular Events with Testosterone Replacement Therapy", "FDA Alerts", "The FDA issued a Safety Communication today summarizing findings from a large postmarket cardiovascular outcomes trial of testosterone replacement therapy in men with hypogonadism.\n\nThe trial enrolled middle-aged and older men with established or high risk of cardiovascular disease and symptomatic hypogonadism. Treatment with topical testosterone met the prespecified non-inferiority margin for the primary major adverse cardiovascular event endpoint but was associated with numerically higher rates of atrial fibrillation, pulmonary embolism, and acute kidney injury compared with placebo.\n\nProduct labeling will be updated to reflect these findings and to reinforce that testosterone replacement is indicated only for men with confirmed hypogonadism on the basis of symptoms and unequivocally low morning serum testosterone concentrations, not for age-related decline in testosterone or nonspecific symptoms.\n\nThe FDA recommends that prescribers discuss the updated benefit-risk profile with patients prior to initiation, monitor hematocrit and prostate-specific antigen periodically, and reassess the ongoing need for therapy at regular intervals.",
     "FDA Drug Safety Communication", "2024-02-20T00:00:00"),
    ("FDA Requires New Boxed Warning for Oral Ketoconazole Due to Risk of Serious Hepatotoxicity", "FDA Alerts", "The FDA has required a new boxed warning for oral ketoconazole tablets describing the risk of serious, potentially fatal hepatotoxicity, adrenal insufficiency, and clinically significant drug-drug interactions through CYP3A4 inhibition and QT-interval prolongation.\n\nOral ketoconazole is no longer indicated for the treatment of onychomycosis, cutaneous dermatophyte infections, or candidiasis when other antifungal agents are available. Acceptable indications are now limited to certain endemic mycoses-including blastomycosis, coccidioidomycosis, histoplasmosis, chromomycosis, and paracoccidioidomycosis-in patients who have failed or cannot tolerate other therapy.\n\nThe boxed warning advises baseline liver function testing, weekly testing during the first month of therapy, and monthly testing thereafter, with discontinuation for transaminase elevations or clinical signs of hepatitis. The labeling lists numerous contraindicated coadministered drugs based on CYP3A4 inhibition.\n\nTopical and shampoo formulations of ketoconazole are not affected by this action and retain their existing safety profile.",
     "FDA Drug Safety Communication", "2023-09-12T00:00:00"),

    # --- New Drug Approvals (additional dated entries) ---
    ("FDA Approves Lecanemab (Leqembi) for Early Alzheimer's Disease", "New Drug Approvals", "The FDA today granted traditional approval to lecanemab-irmb (Leqembi), an anti-amyloid monoclonal antibody, for the treatment of mild cognitive impairment or mild dementia due to Alzheimer's disease in patients with confirmed amyloid-beta pathology.\n\nApproval was based on a confirmatory 18-month, randomized, double-blind, placebo-controlled phase 3 trial in 1,795 participants. Treatment with lecanemab produced a statistically significant 27% slowing of clinical decline on the Clinical Dementia Rating-Sum of Boxes scale and substantial reductions in cerebral amyloid plaque on PET imaging.\n\nThe label carries a boxed warning for amyloid-related imaging abnormalities (ARIA), which include ARIA-E (edema or effusion) and ARIA-H (microhemorrhage or superficial siderosis). ARIA was more frequent in apolipoprotein E epsilon-4 homozygotes, and the FDA recommends genotyping prior to initiation.\n\nLecanemab is administered by intravenous infusion every two weeks. Prescribers must enroll in a structured MRI monitoring program with scans prior to the fifth, seventh, and fourteenth infusions to detect ARIA. The medication is intended for patients with mild cognitive impairment or mild dementia due to Alzheimer's disease, the population studied in the trials.",
     "FDA News Release", "2023-07-06T00:00:00"),
    ("FDA Approves Tirzepatide (Zepbound) for Chronic Weight Management", "New Drug Approvals", "The FDA today approved tirzepatide (Zepbound) injection for chronic weight management in adults with obesity (body mass index 30 kg/m^2 or greater) or overweight (BMI 27 kg/m^2 or greater) in the presence of at least one weight-related comorbid condition such as hypertension, dyslipidemia, type 2 diabetes mellitus, obstructive sleep apnea, or cardiovascular disease.\n\nTirzepatide is a once-weekly, dual glucose-dependent insulinotropic polypeptide (GIP) and glucagon-like peptide-1 (GLP-1) receptor agonist already marketed under the brand name Mounjaro for type 2 diabetes. The weight-management approval is based on two pivotal phase 3 trials in which participants treated with the highest doses lost an average of approximately 18 to 21 percent of body weight over 72 weeks compared with about 3 percent in the placebo group.\n\nThe most common adverse reactions were gastrointestinal, including nausea, diarrhea, vomiting, constipation, and abdominal discomfort, typically occurring during dose escalation. The label includes a boxed warning regarding thyroid C-cell tumors observed in rodents and contraindications in patients with a personal or family history of medullary thyroid carcinoma or multiple endocrine neoplasia syndrome type 2.\n\nTirzepatide should be used in conjunction with reduced-calorie diet and increased physical activity.",
     "FDA News Release", "2023-11-08T00:00:00"),
    ("FDA Approves Nirsevimab (Beyfortus) for Prevention of RSV in Infants", "New Drug Approvals", "The FDA today approved nirsevimab-alip (Beyfortus), a long-acting monoclonal antibody, for the prevention of respiratory syncytial virus (RSV) lower respiratory tract disease in neonates and infants born during or entering their first RSV season, and in children up to 24 months of age who remain vulnerable to severe RSV disease through their second RSV season.\n\nUnlike vaccines, nirsevimab provides passive immunity through a single intramuscular dose that delivers preformed neutralizing antibody against the RSV F protein. The extended half-life confers protection for at least five months, covering a typical RSV season.\n\nApproval was based on three randomized, placebo-controlled trials demonstrating reductions of approximately 70 to 75 percent in medically attended RSV lower respiratory tract infection through 150 days after dosing. Hospitalizations for RSV were also significantly reduced.\n\nThe most common adverse reactions were rash and injection-site reactions. The Centers for Disease Control and Prevention's Advisory Committee on Immunization Practices is expected to issue recommendations on routine use in infants. Public health officials hailed the approval as a meaningful advance against the leading cause of infant hospitalization in the United States.",
     "FDA News Release", "2023-07-17T00:00:00"),
    ("FDA Approves First Cell-Based Gene Therapy for Sickle Cell Disease", "New Drug Approvals", "The FDA today approved two cell-based gene therapies for the treatment of sickle cell disease in patients 12 years and older with recurrent vaso-occlusive crises, marking the first approval of a CRISPR/Cas9 gene-edited therapy in the United States.\n\nThe first product uses CRISPR/Cas9 to edit a patient's own hematopoietic stem cells to reduce expression of BCL11A, thereby reactivating fetal hemoglobin production. The second product uses a lentiviral vector to add a modified beta-globin gene that produces anti-sickling hemoglobin. Both are administered as one-time intravenous infusions following myeloablative conditioning chemotherapy.\n\nIn pivotal trials, the majority of treated patients achieved freedom from severe vaso-occlusive crises during the primary evaluation period, a clinically meaningful endpoint for a disease characterized by recurrent acute pain episodes, end-organ damage, and reduced life expectancy.\n\nThe therapies carry risks associated with conditioning chemotherapy, including infertility and an increased lifetime risk of malignancy, and require treatment at qualified centers with expertise in stem cell transplantation. Long-term follow-up studies are required as part of the approvals.",
     "FDA News Release", "2023-12-08T00:00:00"),

    # --- Clinical Trials (additional dated entries) ---
    ("Phase 3 Trial Shows Semaglutide Reduces Risk of Major Cardiovascular Events", "Clinical Trials", "Results from a large international phase 3 cardiovascular outcomes trial published this week demonstrated that once-weekly subcutaneous semaglutide significantly reduced the risk of major adverse cardiovascular events in adults with overweight or obesity and established cardiovascular disease but without diabetes.\n\nThe trial randomized more than 17,000 participants to semaglutide 2.4 mg weekly or matching placebo, in addition to standard of care, and followed them for a median of about three years. The primary composite endpoint of cardiovascular death, nonfatal myocardial infarction, or nonfatal stroke occurred in 6.5% of the semaglutide group compared with 8.0% of the placebo group, a 20% relative risk reduction.\n\nSecondary endpoints including heart failure events and all-cause mortality also favored the semaglutide arm. The safety profile was consistent with prior experience: gastrointestinal adverse events were the most common reason for discontinuation, and rates of pancreatitis and gallbladder disease were modestly higher with semaglutide.\n\nInvestigators noted that the cardiovascular benefit appeared early and was sustained, suggesting mechanisms beyond weight loss alone. The findings are expected to influence guideline recommendations and reimbursement discussions for GLP-1 receptor agonists in patients with cardiovascular disease and obesity.",
     "Drugs.com Clinical Trial News", "2023-08-25T00:00:00"),
    ("Clinical Trial Results: Pembrolizumab Improves Survival in Early-Stage Triple-Negative Breast Cancer", "Clinical Trials", "A landmark phase 3 trial published this week reported that neoadjuvant and adjuvant pembrolizumab combined with chemotherapy significantly improved event-free survival and overall survival in patients with high-risk early-stage triple-negative breast cancer.\n\nThe trial enrolled approximately 1,170 patients with newly diagnosed stage II or stage III triple-negative breast cancer who were randomized to receive neoadjuvant pembrolizumab plus chemotherapy followed by adjuvant pembrolizumab or to receive neoadjuvant chemotherapy plus placebo followed by adjuvant placebo. After a median follow-up of about five years, overall survival at five years was 86.6% in the pembrolizumab arm versus 81.7% in the placebo arm, a statistically significant improvement.\n\nPathologic complete response rates were also higher with pembrolizumab. Immune-related adverse events occurred in a minority of patients and were managed according to established algorithms; the most common were endocrinopathies and dermatologic reactions.\n\nThe authors concluded that the addition of pembrolizumab to chemotherapy represents a new standard of care for this aggressive subtype of breast cancer, which has historically lacked targeted therapeutic options.",
     "Drugs.com Clinical Trial News", "2023-10-13T00:00:00"),
    ("New Study Finds Aspirin No Longer Recommended for Primary Prevention in Adults Over 60", "Clinical Trials", "Updated analyses from multiple randomized trials and a refreshed systematic review have led major guideline bodies to recommend against the routine use of low-dose aspirin for primary prevention of cardiovascular disease in adults aged 60 years and older.\n\nThe pooled evidence indicates that in older adults without established atherosclerotic cardiovascular disease, the modest reduction in nonfatal cardiovascular events is offset by an increased risk of clinically significant bleeding, particularly gastrointestinal and intracranial hemorrhage. Net benefit appears neutral or unfavorable in this age group.\n\nFor adults aged 40 to 59 with elevated 10-year cardiovascular risk and low bleeding risk, the decision to initiate aspirin should be individualized through shared decision-making, weighing potential benefits against bleeding risk and patient preferences.\n\nThe updated recommendations do not apply to patients with established cardiovascular disease, for whom aspirin remains a cornerstone of secondary prevention. Patients currently taking aspirin for primary prevention are encouraged to discuss continuation with their clinician rather than discontinuing abruptly.",
     "Drugs.com Clinical Trial News", "2023-04-26T00:00:00"),
    ("Trial Results: Combination Therapy Doubles Response Rate in Treatment-Resistant Depression", "Clinical Trials", "A phase 3 randomized controlled trial published this week reported that the combination of an oral antidepressant with adjunctive intranasal esketamine achieved response rates approximately twice as high as antidepressant plus placebo in patients with treatment-resistant major depressive disorder.\n\nThe trial enrolled adults who had failed to respond to at least two prior antidepressant trials of adequate dose and duration in the current depressive episode. Participants were randomized to receive a newly initiated oral antidepressant plus intranasal esketamine or the same antidepressant plus placebo nasal spray, administered twice weekly for four weeks followed by less frequent maintenance dosing.\n\nThe primary endpoint of change in Montgomery-Asberg Depression Rating Scale total score at four weeks favored the esketamine arm with a clinically meaningful effect size. Response and remission rates were approximately doubled. Sustained benefit was observed through the maintenance phase.\n\nDissociation, sedation, and transient increases in blood pressure were the most common adverse effects and required observation in a certified treatment center for at least two hours after each dose. The findings reinforce the role of glutamatergic agents as an option for patients who have not benefited from monoaminergic antidepressants.",
     "Drugs.com Clinical Trial News", "2024-01-30T00:00:00"),

    # --- Medical / Consumer (additional dated entries) ---
    ("Study Links Long-Term Use of Proton Pump Inhibitors to Increased Risk of Kidney Disease", "Medical", "A large cohort study published this week reported an association between long-term use of proton pump inhibitors (PPIs) and an increased risk of chronic kidney disease and progression to end-stage renal disease.\n\nThe investigators analyzed health-system data from more than 250,000 adults newly started on PPIs and compared their outcomes with matched controls started on histamine-2 receptor antagonists. After adjustment for baseline kidney function, comorbidities, and concurrent medications, PPI users had a higher risk of incident chronic kidney disease over a median follow-up of about five years. The association was stronger with longer cumulative duration of use.\n\nWhile the study is observational and cannot establish causation, the findings are consistent with prior reports linking PPIs to acute interstitial nephritis and add to growing evidence supporting cautious, indication-driven use.\n\nClinicians are encouraged to prescribe PPIs at the lowest effective dose for the shortest necessary duration, to periodically reassess the ongoing need for therapy, and to consider deprescribing in patients without a clear continued indication. Over-the-counter PPI use should remain limited to short courses for occasional heartburn.",
     "Drugs.com Medical News", "2023-12-05T00:00:00"),
    ("Researchers Identify Gene Variant That Increases Statin-Related Muscle Pain Risk", "Medical", "Researchers have identified a common genetic variant in the SLCO1B1 gene that substantially increases the risk of statin-associated muscle symptoms and, in some cases, severe myopathy, particularly with higher doses of simvastatin and atorvastatin.\n\nThe variant reduces the function of an organic anion transporter responsible for hepatic uptake of statins, leading to higher systemic exposure and increased muscle toxicity. In a meta-analysis of pharmacogenomic studies, carriers of two reduced-function alleles had several-fold higher odds of statin-associated muscle symptoms compared with non-carriers.\n\nClinical pharmacogenomics guidelines now recommend lower starting doses or alternative statins-such as rosuvastatin or pravastatin, which are less affected by SLCO1B1 polymorphisms-for patients with reduced-function genotypes. Genotype-guided prescribing is being incorporated into preemptive testing panels at several academic medical centers.\n\nClinicians should consider pharmacogenomic testing for patients who experience recurrent statin intolerance and should reassure those without intolerance that the absolute risk of serious muscle injury remains low.",
     "Drugs.com Medical News", "2023-10-22T00:00:00"),
    ("Acetaminophen During Pregnancy May Affect Child's Neurodevelopment, Study Finds", "Medical", "A large prospective cohort study published this week reported a modest association between prenatal acetaminophen exposure and an increased risk of attention-deficit/hyperactivity disorder and autism spectrum disorder in offspring, particularly with longer cumulative use during pregnancy.\n\nThe study followed more than 70,000 mother-child pairs from early pregnancy through early childhood, capturing detailed information on maternal acetaminophen use and child neurodevelopmental outcomes. After adjustment for indication, maternal health, and other confounders, longer durations of prenatal acetaminophen exposure were associated with a modest increase in the risk of these outcomes.\n\nThe authors and accompanying editorialists emphasized that the absolute risk remains small and that acetaminophen continues to be the preferred analgesic and antipyretic during pregnancy because alternatives such as NSAIDs are contraindicated in the third trimester. Untreated maternal fever and pain themselves carry risks to the developing fetus.\n\nThe recommended approach is to use the lowest effective dose for the shortest duration needed to address a specific clinical indication, and to consult an obstetric provider before regular or prolonged use during pregnancy.",
     "Drugs.com Medical News", "2023-06-18T00:00:00"),
    ("Generic Drug Shortages Continue to Impact Patients Nationwide, FDA Reports", "Medical", "The FDA's latest drug shortage report describes ongoing shortages affecting more than 100 generic medications, including several first-line antibiotics, oncology agents, sterile injectables, and pediatric formulations of common antimicrobials and analgesics.\n\nThe root causes are multifactorial and include manufacturing quality issues, consolidated production of low-margin generics among a small number of facilities, raw material supply disruptions, and demand surges associated with respiratory illness seasons. Several shortages affecting injectable chemotherapy agents have forced oncology programs to ration doses or substitute alternative regimens.\n\nThe agency is working with manufacturers to expedite inspections, qualify alternative suppliers, and exercise regulatory flexibilities such as temporary importation of foreign-approved products. Congressional proposals to incentivize redundant manufacturing capacity and to require greater supply-chain transparency are under active consideration.\n\nPharmacists and prescribers are encouraged to monitor FDA and ASHP shortage lists, communicate proactively with patients about potential substitutions, and report local shortages to the FDA. Patients experiencing difficulty filling a prescription should not discontinue therapy without first consulting their pharmacist or prescriber.",
     "Drugs.com Medical News", "2024-03-01T00:00:00"),
]


_COND_DISPLAY: dict[str, str] = {
    "pain": "pain", "hypertension": "high blood pressure", "high_blood_pressure": "high blood pressure",
    "high_cholesterol": "high cholesterol", "heart_disease": "heart disease", "diabetes": "diabetes",
    "type2_diabetes": "type 2 diabetes", "type1_diabetes": "type 1 diabetes",
    "depression": "depression", "anxiety": "anxiety", "ocd": "OCD", "ptsd": "PTSD",
    "panic_disorder": "panic disorder", "social_anxiety": "social anxiety disorder",
    "pmdd": "PMDD", "seizures": "seizures", "epilepsy": "epilepsy",
    "neuropathic_pain": "neuropathic pain", "restless_legs": "restless legs syndrome",
    "fibromyalgia": "fibromyalgia", "obesity": "weight management",
    "weight_management": "weight management", "asthma": "asthma", "copd": "COPD",
    "acid_reflux": "acid reflux", "gerd": "GERD", "infection": "bacterial infection",
    "urinary_tract_infection": "urinary tract infections", "pneumonia": "pneumonia",
    "edema": "edema", "atrial_fibrillation": "atrial fibrillation",
    "deep_vein_thrombosis": "blood clots", "pulmonary_embolism": "pulmonary embolism",
    "thyroid": "thyroid condition", "hypothyroidism": "hypothyroidism",
    "insomnia": "insomnia", "sleep_disorder": "sleep problems", "gout": "gout",
    "rheumatoid_arthritis": "rheumatoid arthritis", "osteoporosis": "osteoporosis",
    "migraine": "migraines", "nausea": "nausea", "fever": "fever",
    "inflammation": "inflammation", "general": "my condition",
}


def _humanize_cond(slug: str) -> str:
    return _COND_DISPLAY.get(slug, slug.replace("_", " "))


REVIEW_TEMPLATES = [
    ("Worked great for my condition", 9, "I was prescribed this for {cond} and have had excellent results. Minimal side effects so far. Highly recommend talking to your doctor about this option."),
    ("Took a while to kick in", 7, "It took about 4 weeks before I really noticed a difference treating my {cond}. Once it started working, the effect has been consistent. Some mild side effects at first."),
    ("Game changer", 10, "This medication has been a game changer for managing my {cond}. I feel like myself again after years of struggling. The side effects were minimal for me."),
    ("Not for me", 3, "Tried this for {cond} for 6 weeks and the side effects outweighed the benefits. Switched to something else. Everyone reacts differently though."),
    ("Mixed feelings", 5, "Some days it helps with my {cond}, other days less so. Side effects include some drowsiness. Talk with your doctor about whether this fits your situation."),
    ("Effective but watch dosage", 8, "Effective treatment for {cond}, but you really need to follow dosing instructions carefully. I had to adjust mine with my doctor's help."),
    ("Worked for a while", 6, "Helped with my {cond} for about a year, then I felt the effects wear off. Doctor is adjusting my treatment plan."),
    ("Best medication I've tried", 10, "Out of several medications I've tried for {cond}, this has been the most effective with the fewest side effects. Quality of life vastly improved."),
    ("Cautious recommendation", 7, "It works for my {cond} but the cost is significant. Insurance covered most of it. Be sure to discuss generics."),
    ("Side effects too much", 2, "The side effects were too disruptive for my daily life, even though it did help with {cond}. Discontinued after a few weeks."),
    ("Changed my life", 10, "After years of struggling with {cond}, this medication has truly changed my life. I feel like a completely different person and can finally enjoy daily activities again."),
    ("Minimal side effects", 9, "Been taking this for treating {cond} and it works great with very minimal side effects. Much better than the previous medication I was on."),
    ("Gradual improvement", 7, "It took several weeks before I noticed any improvement in my {cond}, but once it kicked in, the difference was noticeable. Staying patient was key."),
    ("Mixed results", 5, "This drug helped somewhat with my {cond} but I'm still experiencing breakthrough symptoms. My doctor and I are still adjusting the dosage."),
    ("Difficult adjustment period", 6, "The first two weeks treating {cond} were rough with side effects, but things settled down and now it seems to be working. Stick with it if you can."),
    ("Better than expected", 8, "I was skeptical but this has exceeded my expectations for managing {cond}. Following up with my doctor regularly has made all the difference."),
    ("Not right for me", 3, "Unfortunately this medication wasn't a good fit for my {cond}. I experienced too many side effects and had to discontinue. Everyone is different."),
    ("Consistent results", 9, "Very reliable medication. My {cond} has been under consistent control since starting this treatment. My doctor is pleased with my lab results."),
    ("Insurance hassle but worth it", 8, "Had some trouble getting this covered for {cond} but my doctor fought for it. Now that I'm on it, I understand why - it works really well."),
    ("Mild but effective", 7, "Nothing dramatic but steadily effective for my {cond}. Fewer side effects than alternatives I've tried. Would recommend discussing with your doctor."),
]

_PREGNANCY_RISK: dict[str, str] = {
    # Category D / X — contraindicated or significant fetal risk
    "lisinopril": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "enalapril": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "ramipril": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "captopril": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "benazepril": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "losartan": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "valsartan": "Category D - Fetal toxicity; discontinue when pregnancy detected",
    "warfarin": "Category X - Contraindicated; causes fetal warfarin syndrome",
    "isotretinoin": "Category X - Absolutely contraindicated; causes severe birth defects",
    "methotrexate": "Category X - Contraindicated; causes fetal death/malformations",
    "thalidomide": "Category X - Contraindicated; causes severe limb defects",
    "testosterone": "Category X - Contraindicated; causes virilization of female fetus",
    "finasteride": "Category X - Contraindicated in women; causes male fetal genital abnormalities",
    "lithium": "Category D - Cardiac malformations (Ebstein anomaly); risk/benefit discussion required",
    "valproic acid": "Category D - Neural tube defects, cognitive impairment; avoid if possible",
    "carbamazepine": "Category D - Neural tube defects and other birth defects",
    "phenytoin": "Category D - Fetal hydantoin syndrome",
    "topiramate": "Category D - Cleft palate and other birth defects",
    # Category C — risk cannot be ruled out
    "metformin": "Category B - Generally considered safe; often used in gestational diabetes",
    "ibuprofen": "Category C (avoid in 3rd trimester) - May cause premature ductus arteriosus closure",
    "naproxen": "Category C (avoid in 3rd trimester) - May cause premature ductus arteriosus closure",
    "meloxicam": "Category C (avoid in 3rd trimester) - NSAID; avoid near term",
    "celecoxib": "Category C (avoid in 3rd trimester) - NSAID; avoid near term",
    "aspirin": "Category D in 3rd trimester - Low-dose aspirin (81 mg) may be used under supervision",
    "sertraline": "Category C - Neonatal adaptation syndrome; benefits often outweigh risks",
    "fluoxetine": "Category C - Neonatal adaptation syndrome; discuss risk/benefit",
    "escitalopram": "Category C - Neonatal adaptation syndrome; discuss risk/benefit",
    "paroxetine": "Category D - Cardiac defects (ASD/VSD) reported; avoid if possible",
    "duloxetine": "Category C - Neonatal adaptation syndrome; use with caution",
    "venlafaxine": "Category C - Neonatal adaptation syndrome; discuss risk/benefit",
    "bupropion": "Category C - Use only if clearly needed; neonatal seizures reported",
    "alprazolam": "Category D - Neonatal withdrawal and floppy infant syndrome",
    "diazepam": "Category D - Neonatal withdrawal and floppy infant syndrome",
    "lorazepam": "Category D - Neonatal withdrawal; avoid chronic use",
    "clonazepam": "Category D - Neonatal withdrawal; avoid chronic use",
    "oxycodone": "Category C - Neonatal opioid withdrawal syndrome; avoid near term",
    "hydrocodone": "Category C - Neonatal opioid withdrawal syndrome; avoid near term",
    "tramadol": "Category C - Neonatal withdrawal; avoid in late pregnancy",
    "gabapentin": "Category C - Limited human data; use only if clearly needed",
    "pregabalin": "Category C - Limited human data; use only if clearly needed",
    "atorvastatin": "Category X - Contraindicated; cholesterol needed for fetal development",
    "rosuvastatin": "Category X - Contraindicated; cholesterol needed for fetal development",
    "simvastatin": "Category X - Contraindicated; cholesterol needed for fetal development",
    "amlodipine": "Category C - Limited data; use only if clearly needed",
    "metoprolol": "Category C - Fetal bradycardia and growth restriction possible",
    "carvedilol": "Category C - Beta-blocker; fetal bradycardia possible",
    "hydrochlorothiazide": "Category B - Generally safe; monitor fetal growth",
    "furosemide": "Category C - Use only if clearly needed; monitor fetus",
    "spironolactone": "Category C - Anti-androgenic effects; limited data",
    "omeprazole": "Category C - Generally considered safe in pregnancy",
    "esomeprazole": "Category C - Generally considered safe in pregnancy",
    "pantoprazole": "Category C - Generally considered safe in pregnancy",
    "ranitidine": "Category B - Generally considered safe",
    "famotidine": "Category B - Generally considered safe",
    "ondansetron": "Category B - Commonly used for nausea/vomiting of pregnancy",
    "levothyroxine": "Category A - Essential for fetal brain development; continue therapy",
    "insulin": "Category B - Preferred antidiabetic in pregnancy",
    "semaglutide": "Category C - Limited data; discontinue when pregnancy recognized",
    "methotrexate": "Category X - Absolutely contraindicated",
    "prednisone": "Category C - Short-term use generally acceptable; avoid near term",
    "amoxicillin": "Category B - Generally considered safe",
    "azithromycin": "Category B - Generally considered safe",
    "ciprofloxacin": "Category C - Avoid if possible; alternative preferred",
    "levofloxacin": "Category C - Avoid if possible; joint/cartilage concerns in animal studies",
    "doxycycline": "Category D - Tooth discoloration and bone inhibition; avoid after 2nd trimester",
    "acetaminophen": "Category B - Preferred analgesic/antipyretic in pregnancy",
    "zolpidem": "Category C - Neonatal withdrawal; avoid chronic use near term",
    "trazodone": "Category C - Limited data; use only if clearly needed",
    "quetiapine": "Category C - Neonatal extrapyramidal symptoms possible",
    "olanzapine": "Category C - Neonatal extrapyramidal symptoms possible",
    "methylphenidate": "Category C - Limited data; avoid if possible",
    "apixaban": "Category B - Bleeding risk; avoid near term",
    "rivaroxaban": "Category C - Bleeding risk; avoid near term",
    "clopidogrel": "Category B - Limited data; use only if clearly needed",
}


BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "username": "alice_j", "first_name": "Alice", "last_name": "Johnson", "password": "TestPass123!"},
    {"email": "bob.c@test.com", "username": "bob_c", "first_name": "Bob", "last_name": "Chen", "password": "TestPass123!"},
    {"email": "carol.d@test.com", "username": "carol_d", "first_name": "Carol", "last_name": "Davis", "password": "TestPass123!"},
    {"email": "david.k@test.com", "username": "david_k", "first_name": "David", "last_name": "Kim", "password": "TestPass123!"},
]


# ---------------------------------------------------------------------------
# OpenFDA fetch
# ---------------------------------------------------------------------------
def _openfda_label_matches(query_generic, label):
    """Verify a label's own openfda.generic_name actually corresponds to the
    queried drug. FDA's search endpoint does fuzzy/tokenized matching and can
    return an unrelated drug's label for a query with no exact match (e.g.
    querying "polyethylene glycol" has been observed to return a Naproxen
    label) -- accepting such a result blindly would seed the wrong drug's
    entire uses/warnings/dosage/side_effects text.
    """
    openfda = label.get("openfda") or {}
    fda_names = openfda.get("generic_name") or []
    if not fda_names:
        return False

    # A token match alone is not enough for a monotherapy query. For example,
    # OpenFDA currently returns a sitagliptin/metformin combination label for
    # both `sitagliptin` and `metformin`, and a lisinopril/HCTZ label for
    # `hydrochlorothiazide`. Accepting those labels would silently describe a
    # different product. Every hyphenated generic in DRUGS_DATA is an explicit
    # combination product; non-hyphenated queries must resolve to one active
    # substance and a non-combination generic name.
    query_is_combination = "-" in query_generic
    substances = [s for s in openfda.get("substance_name") or [] if s]
    if not query_is_combination:
        if len(substances) > 1:
            return False
        combination_markers = re.compile(r"\b(?:and|with)\b|[/;+]", re.IGNORECASE)
        if any(combination_markers.search(name or "") for name in fda_names):
            return False

    q = query_generic.lower().replace("-", " ").strip()
    q_tokens = set(q.split())
    for name in fda_names:
        n = (name or "").lower().replace("-", " ").strip()
        if not n:
            continue
        if q == n or q in n or n in q:
            return True
        n_tokens = set(n.split())
        if q_tokens and (q_tokens <= n_tokens or n_tokens <= q_tokens):
            return True
    return False


def fetch_openfda_label(generic):
    """Fetch label info from OpenFDA. Returns dict or None on any failure,
    including a fetched label whose own generic name doesn't match the query."""
    if not HAS_REQUESTS:
        return None
    try:
        r = requests.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": f"openfda.generic_name:{generic}", "limit": 1},
            timeout=4,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results", [])
        if not results:
            return None
        if not _openfda_label_matches(generic, results[0]):
            return None
        return results[0]
    except Exception:
        return None


def first(text_field):
    if not text_field:
        return None
    if isinstance(text_field, list):
        return text_field[0] if text_field else None
    return str(text_field)


def truncate(text, n=2400):
    if not text:
        return text
    text = str(text).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "..."


def _trunc_at_sentence(text, max_chars=600):
    """Truncate text at the last sentence boundary within max_chars."""
    if not text:
        return text
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    chunk = text[:max_chars]
    for sep in (". ", "! ", "? "):
        pos = chunk.rfind(sep)
        if pos > max_chars // 3:
            return chunk[:pos + 1]
    return chunk.rsplit(" ", 1)[0] + "..."


def synthetic_content(generic, cls_name, conditions):
    """Generate realistic synthetic content when OpenFDA isn't available."""
    cond_text = ", ".join(conditions) if conditions else "various medical conditions"
    return {
        "description": f"{generic.capitalize()} is a {cls_name.lower()} medication used to treat {cond_text}. It works by addressing the underlying biological processes associated with these conditions.",
        "uses": f"{generic.capitalize()} is indicated for the treatment of {cond_text}. Your doctor may prescribe this medication for other purposes not listed here. Always follow your healthcare provider's instructions regarding indications and proper use.",
        "warnings": f"Do not use {generic} if you are allergic to it or to similar medications. Tell your doctor about all your medical conditions, especially kidney or liver problems, heart disease, and any history of allergic reactions. Inform your doctor if you are pregnant or breastfeeding. Stop taking {generic} and contact your doctor immediately if you experience severe allergic reactions, unusual bleeding, severe abdominal pain, or signs of a serious skin reaction.",
        "dosage": f"The dose of {generic} should be individualized based on the patient's condition, age, and response to therapy. Follow the directions on your prescription label. Do not take more or less than prescribed. If you miss a dose, take it as soon as you remember. Do not double up on doses.",
        "side_effects": f"Common side effects of {generic} may include headache, nausea, dizziness, drowsiness, and gastrointestinal upset. Less common but serious side effects include allergic reactions (rash, swelling, difficulty breathing), changes in mood or behavior, and unusual bleeding. Contact your healthcare provider if any side effect persists or worsens.",
        "interactions_text": f"{generic.capitalize()} can interact with many other medications. Tell your doctor about all prescription and over-the-counter medications, vitamins, and herbal supplements you take. Pay particular attention to interactions with anticoagulants, NSAIDs, antidepressants, and certain antibiotics.",
    }


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def seed_drug_classes():
    existing = {c.name for c in DrugClass.query.all()}
    for name, desc in DRUG_CLASSES:
        if name in existing:
            continue
        db.session.add(DrugClass(name=name, slug=slugify(name), description=desc))
    db.session.commit()


def seed_conditions():
    existing = {c.slug for c in Condition.query.all()}
    for slug, name, desc in CONDITIONS_DATA:
        if slug in existing:
            continue
        db.session.add(Condition(name=name, slug=slug, description=desc))
    db.session.commit()


DRUG_CONTENT_OVERRIDES = {
    "ciprofloxacin": {
        "description": "Ciprofloxacin (Cipro) is a broad-spectrum fluoroquinolone antibiotic active against both gram-negative and gram-positive organisms. Oral tablets are available as immediate-release (250, 500, 750 mg) and extended-release (500, 1000 mg) formulations.",
        "uses": "Ciprofloxacin is indicated for urinary tract infections (including complicated UTIs and pyelonephritis), lower respiratory tract infections, skin and soft tissue infections, bone and joint infections, intra-abdominal infections (in combination with metronidazole), infectious diarrhea, typhoid fever, uncomplicated cervical and urethral gonorrhea, chronic bacterial prostatitis, inhalational anthrax (post-exposure prophylaxis), and plague. It is a key treatment option for drug-resistant gram-negative organisms.",
        "warnings": "FDA BOXED WARNING: Fluoroquinolones, including ciprofloxacin, have been associated with disabling and potentially irreversible serious adverse reactions that have occurred together, including tendinitis and tendon rupture, peripheral neuropathy, and central nervous system effects. Discontinue ciprofloxacin immediately at first signs of tendon pain, swelling, or inflammation; peripheral neuropathy (pain, burning, tingling, numbness, weakness); or CNS reactions (convulsions, toxic psychosis, increased intracranial pressure). Reserve ciprofloxacin for infections that have no alternative treatment options. Ciprofloxacin may exacerbate muscle weakness in patients with myasthenia gravis. Risk of aortic aneurysm and dissection is increased, particularly in elderly patients and those with risk factors for aortic disease. Serious and occasionally fatal hypersensitivity reactions have been reported after the first dose. Clostridium difficile-associated diarrhea (CDAD) has been reported. Ciprofloxacin may prolong the QT interval. Avoid use in children, adolescents, and pregnant women due to arthropathic risk. Limit sun/UV light exposure due to photosensitivity risk.",
        "side_effects": "Common: nausea, diarrhea, abnormal liver function tests, vomiting, abdominal pain or discomfort, headache, restlessness. Serious: tendon rupture (particularly Achilles tendon, risk increased in patients older than 60 years, on corticosteroids, or with organ transplants), peripheral neuropathy (may be irreversible), CNS effects (confusion, tremors, hallucinations, depression, seizures), QT prolongation and torsades de pointes, Clostridioides difficile-associated colitis, hepatic failure, anaphylaxis, severe skin reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis), aortic aneurysm and dissection.",
        "dosage": "Uncomplicated UTI: 250 mg every 12 hours for 3 days (IR) or 500 mg once daily for 3 days (XR). Complicated UTI / pyelonephritis: 500 mg every 12 hours for 7-14 days (IR) or 1000 mg once daily for 7-14 days (XR). Lower respiratory tract infection: 500-750 mg every 12 hours for 7-14 days. Skin and soft tissue infections: 500-750 mg every 12 hours for 7-14 days. Bone/joint: 500-750 mg every 12 hours for 4-8 weeks. Prostatitis: 500 mg every 12 hours for 28 days. Take immediate-release tablets with or without food; extended-release tablets with main meal. Avoid antacids, calcium, iron, and dairy products within 2 hours of immediate-release ciprofloxacin.",
        "before_taking": "Do not take ciprofloxacin if you are allergic to ciprofloxacin, other fluoroquinolones (such as levofloxacin, moxifloxacin, norfloxacin), or any of its components. Tell your doctor if you have tendon problems, myasthenia gravis, QT interval prolongation or hypokalemia/hypomagnesemia, seizure disorder or CNS disease, diabetes, kidney or liver disease, joint problems, or aortic aneurysm. Avoid antacids containing magnesium or aluminum, calcium-containing products (including dairy), sucralfate, iron, or zinc within 2 hours before or 6 hours after taking ciprofloxacin, as they impair absorption. Limit caffeine and avoid excessive sun exposure.",
    },
    "levofloxacin": {
        "description": "Levofloxacin (Levaquin) is a broad-spectrum fluoroquinolone antibiotic available as oral tablets (250, 500, 750 mg) and intravenous solution.",
        "uses": "Levofloxacin is indicated for community-acquired pneumonia (including penicillin-resistant Streptococcus pneumoniae), nosocomial pneumonia, acute bacterial exacerbation of chronic bronchitis, acute bacterial sinusitis, complicated and uncomplicated skin infections, complicated UTI and pyelonephritis, chronic bacterial prostatitis, and inhalational anthrax (post-exposure). It is also used in combination regimens for tuberculosis.",
        "warnings": "FDA BOXED WARNING: Serious, disabling, and potentially permanent side effects including tendinitis, tendon rupture, peripheral neuropathy, and CNS effects. Reserve for infections with no alternative treatment options. Risk of exacerbating myasthenia gravis. QT prolongation and torsades de pointes reported. Aortic aneurysm and dissection risk increased. Hypoglycemia and hyperglycemia, including hypoglycemic coma, have been reported (especially in elderly diabetics). Clostridioides difficile-associated diarrhea reported.",
        "side_effects": "Common: nausea, headache, diarrhea, insomnia, constipation, dizziness. Serious: tendon rupture, peripheral neuropathy, CNS effects, QT prolongation, severe hypoglycemia, hepatotoxicity, CDAD.",
        "dosage": "Community-acquired pneumonia (mild-moderate): 500 mg once daily for 7-14 days; (multi-drug-resistant S. pneumoniae): 750 mg once daily for 5 days. Nosocomial pneumonia: 750 mg once daily for 7-14 days. Skin infections: 500-750 mg once daily for 7-14 days. UTI/pyelonephritis: 250-750 mg once daily for 3-10 days. Take without regard to meals; avoid antacids and multivitamins within 2 hours.",
    },
    "metformin": {
        "before_taking": "You should not take metformin if you are allergic to metformin, have severe kidney disease (eGFR below 30 mL/min/1.73 m^2), or have metabolic acidosis or diabetic ketoacidosis. Tell your doctor if you have moderate kidney problems, liver disease, heart failure, a history of alcohol abuse, or are scheduled for surgery or any procedure using iodinated contrast dye. Inform your doctor if you are pregnant, planning pregnancy, or breastfeeding.",
        "uses": "Metformin is a biguanide antidiabetic used to treat type 2 diabetes mellitus. It works by decreasing hepatic glucose production, decreasing intestinal absorption of glucose, and improving insulin sensitivity by increasing peripheral glucose uptake and utilization. Metformin is often the first-line medication for type 2 diabetes, particularly in overweight patients. It may also be used for polycystic ovary syndrome (PCOS).",
        "description": "Metformin (Glucophage) is an oral diabetes medicine that helps control blood sugar levels. It is the most widely used drug for type 2 diabetes and is often prescribed alongside lifestyle changes.",
        "warnings": "Lactic acidosis: Metformin can cause a rare but serious condition called lactic acidosis, a buildup of lactic acid in the blood. Symptoms include weakness, unusual muscle pain, trouble breathing, unusual drowsiness, stomach discomfort, nausea, vomiting, or feeling cold. Seek emergency care immediately. Discontinue if renal impairment (eGFR <30), contrast dye procedures, or surgery requiring anesthesia.",
        "side_effects": "Common side effects include nausea, vomiting, diarrhea, stomach upset, and metallic taste (especially when first starting the medication). These usually improve over time. Serious: lactic acidosis (rare), vitamin B12 deficiency with long-term use.",
        "dosage": "Adults: Initial dose 500 mg twice daily or 850 mg once daily with meals. Increase by 500 mg weekly or 850 mg every 2 weeks as tolerated. Maximum dose: 2550 mg/day. Extended-release: 500-1000 mg once daily with evening meal, max 2000-2500 mg/day. Pediatric (10+ years): 500 mg twice daily, max 2000 mg/day.",
        "interactions_text": "Metformin can interact with several medications that affect renal function or blood glucose. Carbonic anhydrase inhibitors (topiramate, zonisamide, acetazolamide) may increase the risk of lactic acidosis — consider more frequent monitoring. Drugs that reduce metformin clearance by inhibiting renal tubular transporters (OCT2/MATE) include dolutegravir, ranolazine, vandetanib, and cimetidine — use caution and monitor for metformin toxicity. Iodinated contrast agents: hold metformin at the time of or prior to iodinated contrast procedures and restart 48 hours after, only if renal function is stable. Alcohol potentiates the effect of metformin on lactate metabolism — warn patients against excessive alcohol use. Drugs that cause hyperglycemia (thiazides, corticosteroids, thyroid products, estrogens, phenytoin, nicotinic acid, sympathomimetics, calcium channel blockers, isoniazid) may lead to loss of glycemic control. Insulin secretagogues or insulin combined with metformin may increase hypoglycemia risk.",
    },
    "omeprazole": {
        "uses": "Omeprazole is a proton pump inhibitor (PPI) indicated for the treatment of gastroesophageal reflux disease (GERD), erosive esophagitis, duodenal and gastric ulcers, pathological hypersecretory conditions including Zollinger-Ellison syndrome, and for the eradication of Helicobacter pylori infection in combination with appropriate antibiotics. It is also used to reduce the risk of gastric ulcers in patients on continuous NSAID therapy and, in over-the-counter strengths, for the short-term self-treatment of frequent heartburn occurring two or more days per week.",
        "description": "Omeprazole (Prilosec) is an oral proton pump inhibitor that suppresses gastric acid secretion by irreversibly inhibiting the H+/K+ ATPase enzyme system at the secretory surface of gastric parietal cells. It is available by prescription and as an over-the-counter product.",
        "warnings": "Long-term use, especially at higher doses (one year or longer), may increase the risk of osteoporosis-related fractures of the hip, wrist, or spine. PPI therapy has been associated with hypomagnesemia, vitamin B12 deficiency, acute interstitial nephritis, Clostridioides difficile-associated diarrhea, and cutaneous and systemic lupus erythematosus. Symptomatic response to omeprazole does not preclude the presence of gastric malignancy. Do not use OTC omeprazole for more than 14 days every 4 months without consulting a healthcare provider.",
        "side_effects": "Common: headache, abdominal pain, nausea, diarrhea, vomiting, flatulence, and constipation. Serious but less common: acute interstitial nephritis, Clostridioides difficile-associated diarrhea, hypomagnesemia, vitamin B12 deficiency with long-term use, bone fractures, and cutaneous lupus erythematosus. Stop and seek care for severe diarrhea, signs of low magnesium (tremors, muscle cramps, seizures), or rash.",
        "dosage": "Adults: GERD without erosive esophagitis - 20 mg once daily for up to 4 weeks. Erosive esophagitis - 20 mg once daily for 4 to 8 weeks, with maintenance at 20 mg daily. Duodenal ulcer - 20 mg daily for 4 weeks. Gastric ulcer - 40 mg daily for 4 to 8 weeks. H. pylori eradication - 20 mg twice daily for 10 days with amoxicillin and clarithromycin. Take 30 to 60 minutes before a meal; swallow capsules whole. OTC: 20 mg once daily for 14 days for frequent heartburn.",
    },
    "ibuprofen": {
        "before_taking": "You should not take ibuprofen if you are allergic to ibuprofen, aspirin, or any other NSAID. Tell your doctor if you have ever had a stomach ulcer, gastrointestinal bleeding, heart disease, high blood pressure, congestive heart failure, asthma, kidney or liver disease, or a bleeding or clotting disorder. Ibuprofen should not be used in the third trimester of pregnancy; talk to your doctor if you are pregnant, planning pregnancy, or breastfeeding.",
        "uses": "Ibuprofen is a nonsteroidal anti-inflammatory drug (NSAID) used to reduce fever and treat mild to moderate pain from headache, dental pain, menstrual cramps, muscle aches, arthritis, and minor injuries. It works by inhibiting cyclooxygenase (COX-1 and COX-2) enzymes, decreasing production of prostaglandins that mediate inflammation and pain. Both prescription and over-the-counter strengths are available.",
        "description": "Ibuprofen (Advil, Motrin) is an oral NSAID with analgesic, antipyretic, and anti-inflammatory properties. It is widely used for short-term relief of pain and fever and chronically for inflammatory conditions such as osteoarthritis and rheumatoid arthritis.",
        "warnings": "NSAIDs including ibuprofen can increase the risk of serious cardiovascular thrombotic events, including myocardial infarction and stroke, which can be fatal. Risk may increase with duration of use and in patients with cardiovascular disease. Ibuprofen can also cause serious gastrointestinal bleeding, ulceration, and perforation of the stomach or intestines, which can occur at any time without warning symptoms. Avoid in third-trimester pregnancy and in patients with severe renal impairment, active peptic ulcer disease, or known hypersensitivity to aspirin or other NSAIDs.",
        "side_effects": "Common: dyspepsia, nausea, abdominal pain, heartburn, diarrhea, constipation, dizziness, headache, and rash. Serious: gastrointestinal bleeding, peptic ulceration, renal impairment, hypertension, fluid retention, heart failure exacerbation, hepatotoxicity, anaphylaxis, severe skin reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis). Stop and seek care for black or bloody stools, vomiting blood, chest pain, shortness of breath, slurred speech, or facial swelling.",
        "dosage": "Adults (OTC): 200-400 mg every 4 to 6 hours as needed; do not exceed 1200 mg in 24 hours without medical supervision. Adults (Rx): 400-800 mg every 6 to 8 hours; maximum 3200 mg/day. Pediatric (6 months and older): 5-10 mg/kg every 6 to 8 hours, maximum 40 mg/kg/day. Take with food or milk to reduce GI upset. Use the lowest effective dose for the shortest duration consistent with treatment goals.",
    },
    "acetaminophen": {
        "uses": "Acetaminophen is an analgesic and antipyretic used to relieve mild to moderate pain from headache, muscle aches, menstrual cramps, backache, toothache, and minor arthritis pain, and to reduce fever. Unlike NSAIDs, it has little anti-inflammatory activity and works centrally, likely through inhibition of central prostaglandin synthesis and modulation of the endocannabinoid and serotonergic systems.",
        "description": "Acetaminophen (Tylenol, paracetamol) is an oral and rectal analgesic-antipyretic available over the counter and in many combination products. It is the most widely used pain reliever worldwide and the first-line agent for fever and mild pain in most patients, including children and pregnant women.",
        "warnings": "Acetaminophen can cause severe, sometimes fatal, hepatotoxicity, especially at doses exceeding 4 grams in 24 hours, with chronic alcohol use, in patients with hepatic impairment, or when combined with other acetaminophen-containing products. Many prescription combination analgesics and cold/flu products contain acetaminophen; check all labels to avoid duplication. Serious skin reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis, acute generalized exanthematous pustulosis) have been reported rarely.",
        "side_effects": "Common: usually well tolerated at therapeutic doses; rare nausea, rash. Serious: hepatotoxicity (dose-related), acute liver failure, severe cutaneous adverse reactions, thrombocytopenia, and anaphylaxis. Overdose may produce minimal early symptoms followed by delayed hepatic necrosis. Seek emergency care after any suspected overdose; N-acetylcysteine is most effective when given within 8-10 hours.",
        "dosage": "Adults and children 12 years and older: 325-1000 mg every 4 to 6 hours as needed; do not exceed 4 grams (4000 mg) in 24 hours. Many guidelines recommend a maximum of 3 grams/day for chronic use or in patients at risk of hepatotoxicity. Pediatric: 10-15 mg/kg every 4 to 6 hours, not to exceed 5 doses or 75 mg/kg in 24 hours.",
    },
    "aspirin": {
        "uses": "Aspirin (acetylsalicylic acid) is an NSAID used for the relief of mild to moderate pain, fever, and inflammation, and at low doses for the secondary prevention of cardiovascular events (myocardial infarction, ischemic stroke) by irreversibly inhibiting platelet cyclooxygenase-1 and reducing thromboxane A2-mediated platelet aggregation. It is also used in acute coronary syndromes and after coronary stenting.",
        "description": "Aspirin is an oral salicylate available over the counter and by prescription. Low-dose aspirin (81 mg) is widely used for antiplatelet effects, while higher analgesic doses (325-650 mg) are used for pain and fever.",
        "warnings": "Aspirin should not be given to children or teenagers recovering from viral infections (flu, chickenpox) due to the risk of Reye syndrome. It increases the risk of gastrointestinal bleeding, peptic ulceration, and intracranial hemorrhage. Avoid in patients with bleeding disorders, active peptic ulcer disease, severe hepatic or renal impairment, or aspirin-exacerbated respiratory disease. Discontinue 7-10 days before elective surgery unless cardiology advises continuation.",
        "side_effects": "Common: dyspepsia, nausea, heartburn, easy bruising. Serious: GI bleeding, peptic ulcer, hemorrhagic stroke, tinnitus and reversible hearing loss at high doses, salicylism (overdose), bronchospasm in aspirin-sensitive asthmatics, angioedema, and Reye syndrome in children.",
        "dosage": "Analgesic/antipyretic (adults): 325-650 mg every 4 to 6 hours as needed; maximum 4 grams/day. Cardiovascular prevention: 75-100 mg once daily (commonly 81 mg). Acute coronary syndrome: 162-325 mg chewed at symptom onset. Take with food or a full glass of water to reduce GI irritation.",
    },
    "gabapentin": {
        "before_taking": "You should not take gabapentin if you are allergic to gabapentin. Tell your doctor if you have kidney disease (you may need a lower dose), depression or mood disorders, suicidal thoughts, diabetes, breathing problems such as COPD, or a history of drug or alcohol abuse. Do not combine gabapentin with opioids or other CNS depressants without medical guidance, and tell your doctor if you are pregnant or breastfeeding. Do not stop gabapentin abruptly, as this can trigger withdrawal symptoms or seizures.",
        "uses": "Gabapentin is an anticonvulsant and analgesic used as adjunctive therapy for partial seizures with or without secondary generalization, for the management of postherpetic neuralgia, and (gabapentin enacarbil) for moderate-to-severe restless legs syndrome. It is also widely used off-label for diabetic peripheral neuropathy and other neuropathic pain. It binds to the alpha-2-delta subunit of voltage-gated calcium channels, reducing excitatory neurotransmitter release.",
        "description": "Gabapentin (Neurontin) is an oral GABA analogue, though it does not act directly at GABA receptors. It is renally eliminated and requires dose adjustment in renal impairment.",
        "warnings": "Gabapentin can cause serious, life-threatening, or fatal respiratory depression when combined with opioids, benzodiazepines, or other CNS depressants, or in patients with underlying respiratory impairment. It carries a class warning for suicidal thoughts and behavior with antiepileptic drugs. Abrupt discontinuation may precipitate withdrawal symptoms or seizures; taper over at least one week. Dose adjustment is required for creatinine clearance below 60 mL/min.",
        "side_effects": "Common: somnolence, dizziness, ataxia, fatigue, peripheral edema, weight gain, and blurred vision. Serious: respiratory depression (especially with CNS depressants), DRESS/multiorgan hypersensitivity, anaphylaxis and angioedema, suicidal ideation, and rarely myopathy. Drug-induced dependence and misuse have been reported.",
        "dosage": "Postherpetic neuralgia (adults): 300 mg on day 1, 300 mg twice on day 2, 300 mg three times on day 3; titrate up to 1800 mg/day in three divided doses (maximum 3600 mg/day). Partial seizures (adults and children 12+): 300 mg three times daily, titrated to 1800 mg/day. Adjust dose for renal impairment.",
    },
    "alprazolam": {
        "before_taking": "You should not take alprazolam if you are allergic to alprazolam or other benzodiazepines (such as diazepam, lorazepam, clonazepam), or if you have narrow-angle glaucoma. Tell your doctor if you have liver or kidney disease, breathing problems such as COPD or sleep apnea, depression, a history of suicidal thoughts, or a history of drug or alcohol abuse. Do not combine with opioids, alcohol, or other CNS depressants without explicit medical guidance, and tell your doctor if you are pregnant or breastfeeding.",
        "uses": "Alprazolam is a short-acting benzodiazepine indicated for the management of generalized anxiety disorder and for the treatment of panic disorder, with or without agoraphobia. It enhances the inhibitory effect of GABA at GABA-A receptors, producing anxiolytic, sedative, hypnotic, anticonvulsant, and muscle-relaxant effects.",
        "description": "Alprazolam (Xanax) is a Schedule IV controlled substance available as immediate-release and extended-release oral tablets and an oral solution. It has a relatively rapid onset and short half-life compared with longer-acting benzodiazepines.",
        "warnings": "Concomitant use of benzodiazepines and opioids may result in profound sedation, respiratory depression, coma, and death; reserve combined use for patients with no adequate alternative. Alprazolam carries a high risk of dependence, abuse, and misuse. Abrupt discontinuation or rapid dose reduction can cause acute withdrawal, including seizures and life-threatening reactions; taper gradually. Avoid in pregnancy (associated with neonatal sedation and withdrawal) and in patients with severe respiratory insufficiency or acute narrow-angle glaucoma.",
        "side_effects": "Common: drowsiness, fatigue, ataxia, slurred speech, memory impairment, dizziness, decreased libido, dry mouth, and constipation. Serious: respiratory depression, paradoxical reactions (agitation, rage), dependence and withdrawal, rebound anxiety, suicidal ideation, and cognitive impairment in older adults with increased fall and fracture risk.",
        "dosage": "Anxiety (adults, immediate-release): 0.25-0.5 mg three times daily; titrate to maximum 4 mg/day in divided doses. Panic disorder (immediate-release): start 0.5 mg three times daily; mean effective dose 5-6 mg/day, maximum 10 mg/day. Extended-release (panic disorder): 0.5-1 mg once daily, increase by no more than 1 mg every 3-4 days to 3-6 mg/day. Use lowest effective dose in older adults and patients with hepatic impairment.",
    },
    "tramadol": {
        "uses": "Tramadol is a centrally acting analgesic indicated for the management of moderate to moderately severe pain in adults for whom alternative treatments are inadequate. It is a mu-opioid receptor agonist and also inhibits reuptake of serotonin and norepinephrine.",
        "description": "Tramadol is a Schedule IV controlled substance available as immediate-release and extended-release oral formulations. It has weaker mu-receptor affinity than morphine but additional monoaminergic activity contributing to analgesia.",
        "warnings": "Tramadol carries risks of addiction, abuse, and misuse that can lead to overdose and death. Serious, life-threatening, or fatal respiratory depression may occur, especially during initiation or dose escalation, and is increased with concomitant use of benzodiazepines, alcohol, or other CNS depressants. Tramadol lowers seizure threshold, particularly at high doses, in patients with epilepsy, head trauma, or those taking serotonergic or other seizure-lowering medications. Risk of serotonin syndrome with serotonergic drugs. Contraindicated in children under 12 and for postoperative analgesia after tonsillectomy or adenoidectomy in those under 18.",
        "side_effects": "Common: nausea, vomiting, constipation, dizziness, somnolence, headache, dry mouth, and sweating. Serious: respiratory depression, seizures, serotonin syndrome, adrenal insufficiency, severe hypotension, anaphylaxis, neonatal opioid withdrawal syndrome, and physical dependence.",
        "dosage": "Immediate-release (adults): 50-100 mg every 4 to 6 hours as needed; maximum 400 mg/day. In patients not requiring rapid onset, start 25 mg daily and titrate by 25 mg every 3 days to 25 mg four times daily, then increase by 50 mg every 3 days to 50 mg four times daily. Extended-release: 100 mg once daily, titrate by 100 mg every 5 days to maximum 300 mg/day. Reduce dose in renal or hepatic impairment.",
    },
    "amoxicillin": {
        "before_taking": "You should not take amoxicillin if you are allergic to amoxicillin or to any penicillin or cephalosporin antibiotic. Tell your doctor if you have kidney disease, mononucleosis, asthma, a history of any type of allergy, or a history of diarrhea caused by antibiotics. Inform your doctor if you are pregnant or breastfeeding, and tell your healthcare provider about all other medicines you take, including hormonal birth control, which may be less effective during treatment.",
        "uses": "Amoxicillin is a broad-spectrum aminopenicillin antibiotic indicated for the treatment of infections caused by susceptible strains of gram-positive and some gram-negative bacteria, including otitis media, sinusitis, pharyngitis, lower respiratory tract infections, urinary tract infections, skin and soft tissue infections, and as part of multidrug regimens for Helicobacter pylori eradication. It inhibits bacterial cell wall synthesis by binding to penicillin-binding proteins.",
        "description": "Amoxicillin is an oral beta-lactam antibiotic available as capsules, tablets, chewable tablets, and oral suspension. It is acid-stable and well absorbed orally with bioavailability of approximately 75-90 percent.",
        "warnings": "Serious and occasionally fatal hypersensitivity (anaphylactic) reactions have been reported in patients on penicillin therapy; obtain a careful history of allergy to penicillins, cephalosporins, or other allergens before initiating. Clostridioides difficile-associated diarrhea has been reported. A high percentage of patients with mononucleosis develop a rash; avoid amoxicillin in suspected mononucleosis. Adjust dose in severe renal impairment.",
        "side_effects": "Common: diarrhea, nausea, vomiting, rash, and vaginal candidiasis. Serious: anaphylaxis, severe cutaneous reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis, DRESS, acute generalized exanthematous pustulosis), Clostridioides difficile colitis, hepatic dysfunction, interstitial nephritis, and hematologic abnormalities (anemia, thrombocytopenia, eosinophilia).",
        "dosage": "Adults (mild-moderate infection): Usual dose is 250 mg every 8 hours or 500 mg every 8 hours (for more severe infections). Extended-release formulations: 500-875 mg every 12 hours. Severe infection or lower respiratory: 875 mg every 12 hours or 500 mg every 8 hours. Pediatric: 20-45 mg/kg/day in divided doses every 8-12 hours depending on infection severity; higher doses (80-90 mg/kg/day) for acute otitis media. H. pylori: 1 g twice daily with a PPI and clarithromycin for 10-14 days.",
    },
    "metoprolol": {
        "uses": "Metoprolol is a cardioselective beta-1 adrenergic receptor blocker used to treat hypertension, angina pectoris, and to reduce mortality and hospitalization in patients with stable, symptomatic chronic heart failure with reduced ejection fraction. The immediate-release tartrate salt is also indicated for early and long-term treatment of myocardial infarction. It is also used for rate control in atrial fibrillation and for migraine prophylaxis.",
        "description": "Metoprolol is available as immediate-release tartrate (Lopressor) and extended-release succinate (Toprol XL) oral tablets, and as an intravenous formulation. It is hepatically metabolized via CYP2D6.",
        "warnings": "Do not abruptly discontinue metoprolol, particularly in patients with ischemic heart disease, as exacerbation of angina, myocardial infarction, and ventricular arrhythmias may occur; taper over 1 to 2 weeks. Use cautiously in patients with bronchospastic disease, decompensated heart failure, peripheral vascular disease, diabetes (may mask hypoglycemia), pheochromocytoma (use only with concurrent alpha-blockade), and thyrotoxicosis. Contraindicated in severe bradycardia, second- or third-degree AV block without pacemaker, decompensated heart failure, and cardiogenic shock.",
        "side_effects": "Common: fatigue, dizziness, bradycardia, hypotension, depression, cold extremities, diarrhea, and shortness of breath. Serious: heart failure exacerbation, severe bradycardia or AV block, bronchospasm, masking of hypoglycemia, and rebound hypertension or angina with abrupt withdrawal.",
        "dosage": "Hypertension (tartrate): 100 mg/day in single or divided doses, titrated weekly; usual range 100-450 mg/day. Hypertension (succinate ER): 25-100 mg once daily, titrated to maximum 400 mg/day. Heart failure (succinate ER): start 12.5-25 mg once daily, double every 2 weeks as tolerated to target 200 mg once daily. Angina (tartrate): 100 mg/day in two divided doses, up to 400 mg/day.",
    },
    "warfarin": {
        "before_taking": "You should not take warfarin if you are allergic to warfarin, are pregnant (except in select patients with mechanical heart valves), have a bleeding disorder, recent or planned major surgery, uncontrolled high blood pressure, active bleeding, or a recent stroke. Tell your doctor about all medical conditions including liver or kidney disease, congestive heart failure, diabetes, recent trauma, or a history of falls. Many prescription, over-the-counter, herbal, and dietary items (especially vitamin K-rich foods) interact with warfarin; share a complete list with your healthcare provider before starting therapy.",
        "uses": "Warfarin is an oral anticoagulant indicated for the prophylaxis and treatment of venous thromboembolism (deep vein thrombosis and pulmonary embolism), prevention of stroke and systemic embolism in atrial fibrillation and after mechanical heart valve replacement, and reduction of recurrent myocardial infarction and thromboembolic events after myocardial infarction. It inhibits vitamin K epoxide reductase, reducing synthesis of vitamin K-dependent clotting factors II, VII, IX, and X.",
        "description": "Warfarin (Coumadin, Jantoven) is a coumarin derivative requiring routine INR monitoring. Mechanical heart valves still require warfarin rather than direct oral anticoagulants.",
        "warnings": "BLACK BOX WARNING - BLEEDING RISK: Warfarin can cause major or fatal bleeding. Bleeding is more likely to occur during the starting period and with a higher dose (resulting in a higher INR). Risk factors for bleeding include high intensity of anticoagulation (INR greater than 4.0), age 65 or older, highly variable INRs, history of gastrointestinal bleeding, hypertension, cerebrovascular disease, serious heart disease, anemia, malignancy, trauma, renal impairment, certain genetic factors (such as CYP2C9 and VKORC1 polymorphisms), long duration of warfarin therapy, and concomitant antiplatelet drugs, NSAIDs, SSRIs, or other drugs that affect hemostasis. Regular monitoring of INR should be performed on all treated patients. Patients at high risk of bleeding may benefit from more frequent INR monitoring, careful dose adjustment, and shorter duration of therapy. Instruct patients about prevention measures to minimize bleeding risk and to immediately report signs and symptoms of bleeding (unusual bruising, pink or red urine, black or bloody stools, severe headache, joint pain or swelling, prolonged bleeding from cuts, heavier-than-normal menstrual bleeding). Other serious adverse reactions: tissue necrosis and gangrene of skin and other tissues (especially in patients with protein C or S deficiency, typically within the first few days of therapy), systemic atheroemboli and cholesterol microemboli (purple toes syndrome), heparin-induced thrombocytopenia (HIT), and calciphylaxis. Warfarin crosses the placenta, causes fetal hemorrhage and is teratogenic (warfarin embryopathy: nasal hypoplasia, stippled epiphyses, CNS abnormalities); contraindicated in pregnancy except in women with mechanical heart valves at high risk of thromboembolism. Many drug, dietary (vitamin K), herbal, and disease-state interactions can dramatically alter INR; review all concomitant therapy at every visit.",
        "side_effects": "Common: bruising, minor bleeding (epistaxis, gum bleeding), nausea. Serious: major hemorrhage (intracranial, gastrointestinal, retroperitoneal), warfarin-induced skin necrosis, purple toe syndrome, cholesterol microembolization, calciphylaxis, and hypersensitivity reactions.",
        "dosage": "Individualize based on INR. Typical adult starting dose: 2-5 mg once daily, with INR monitoring every 1-3 days during initiation. Target INR depends on indication: 2.0-3.0 for most indications (VTE, atrial fibrillation, bioprosthetic valves) and 2.5-3.5 for mechanical mitral valves and certain high-risk situations. Many drug, dietary (vitamin K), and disease interactions; monitor closely with any change.",
    },
    "hydrocodone": {
        "uses": "Hydrocodone (in extended-release single-entity products) is indicated for the management of pain severe enough to require daily, around-the-clock, long-term opioid treatment in patients for whom alternative options are inadequate. Combination products with acetaminophen or ibuprofen are used for short-term management of acute moderate-to-severe pain. It also has antitussive activity in some combination products.",
        "description": "Hydrocodone is a semi-synthetic opioid agonist; single-entity hydrocodone products are Schedule II controlled substances. It is metabolized via CYP2D6 to hydromorphone (a more potent active metabolite) and via CYP3A4 to norhydrocodone.",
        "warnings": "Hydrocodone exposes patients and other users to risks of addiction, abuse, and misuse that can lead to overdose and death. Life-threatening respiratory depression may occur, particularly with dose initiation or titration. Concomitant use with benzodiazepines or other CNS depressants may result in profound sedation, respiratory depression, coma, and death. Accidental ingestion of even one dose by children can be fatal. Prolonged use during pregnancy can result in neonatal opioid withdrawal syndrome. CYP3A4 interactions can produce fatal overdose.",
        "side_effects": "Common: constipation, nausea, vomiting, somnolence, dizziness, pruritus, dry mouth, and headache. Serious: respiratory depression, profound sedation, hypotension, adrenal insufficiency, severe constipation or ileus, seizures, anaphylaxis, dependence, and neonatal withdrawal.",
        "dosage": "Combination immediate-release products (e.g., 5/325 hydrocodone/acetaminophen): one to two tablets every 4 to 6 hours as needed, limited by total acetaminophen of 4 g/day or less. Extended-release single-entity (opioid-naive): start 10 mg every 12 hours; titrate slowly. Use lowest effective dose for shortest duration.",
    },
    "oxycodone": {
        "uses": "Oxycodone is a strong opioid analgesic indicated for the management of pain severe enough to require an opioid analgesic and for which alternative treatments are inadequate. Immediate-release formulations are used for acute moderate-to-severe pain; extended-release formulations are used for chronic pain requiring around-the-clock therapy.",
        "description": "Oxycodone is a Schedule II controlled substance and a mu-opioid receptor agonist with some kappa activity. It is metabolized via CYP3A4 and CYP2D6 (the latter producing the active metabolite oxymorphone).",
        "warnings": "Oxycodone carries risks of addiction, abuse, and misuse; life-threatening respiratory depression; neonatal opioid withdrawal syndrome with prolonged use in pregnancy; and life-threatening interactions with benzodiazepines, other CNS depressants, and CYP3A4 inhibitors. Accidental ingestion can be fatal in children. Adrenal insufficiency and severe hypotension may occur. Long-term use may produce hypogonadism.",
        "side_effects": "Common: constipation, nausea, vomiting, somnolence, dizziness, pruritus, headache, dry mouth, and sweating. Serious: respiratory depression, severe hypotension, adrenal insufficiency, seizures, ileus, anaphylaxis, physical dependence, and neonatal opioid withdrawal.",
        "dosage": "Immediate-release (opioid-naive adults): 5-15 mg every 4 to 6 hours as needed for pain. Extended-release (opioid-naive): start 10 mg every 12 hours; titrate based on response and tolerability. Reduce starting doses in elderly, debilitated patients, and those with hepatic or renal impairment. Avoid alcohol with extended-release formulations.",
    },
    "naproxen": {
        "before_taking": "You should not take naproxen if you are allergic to naproxen, aspirin, or other NSAIDs, or if you have had asthma or a severe allergic reaction triggered by aspirin or NSAIDs. Tell your doctor if you have heart disease, high blood pressure, a history of heart attack or stroke, stomach ulcers or bleeding, kidney or liver disease, or fluid retention. Avoid naproxen in the third trimester of pregnancy, and tell your doctor if you take blood thinners, low-dose aspirin for heart protection, or other NSAIDs.",
        "uses": "Naproxen is a propionic acid NSAID used to relieve pain, swelling, and stiffness from osteoarthritis, rheumatoid arthritis, juvenile idiopathic arthritis, ankylosing spondylitis, tendinitis, bursitis, acute gout, primary dysmenorrhea, and mild-to-moderate acute pain. Lower-strength formulations are available over the counter for self-treatment of minor pain and fever.",
        "description": "Naproxen (Aleve, Naprosyn) is an oral nonselective COX inhibitor with a longer half-life than ibuprofen, allowing twice-daily dosing. Naproxen sodium is more rapidly absorbed than the free acid form.",
        "warnings": "NSAIDs may cause an increased risk of serious cardiovascular thrombotic events including myocardial infarction and stroke; risk is dose-dependent and increases with longer use. NSAIDs cause an increased risk of serious gastrointestinal adverse events including bleeding, ulceration, and perforation. Avoid in third-trimester pregnancy. Renal toxicity and hyperkalemia, hepatic effects, fluid retention and edema, hypertension, and serious skin reactions can occur. Naproxen may interfere with the cardioprotective effect of low-dose aspirin.",
        "side_effects": "Common: dyspepsia, heartburn, nausea, abdominal pain, constipation, headache, dizziness, drowsiness, and tinnitus. Serious: GI bleeding and ulceration, renal impairment, cardiovascular thrombotic events, hepatotoxicity, severe skin reactions, and anaphylaxis.",
        "dosage": "Adults (OTC, naproxen sodium): 220 mg every 8 to 12 hours; do not exceed 660 mg in 24 hours without medical supervision. Adults (Rx, naproxen base): 250-500 mg twice daily; acute gout 750 mg once then 250 mg every 8 hours until attack subsides; maximum 1500 mg/day for limited duration. Use the lowest effective dose for the shortest duration.",
    },
    "furosemide": {
        "uses": "Furosemide is a loop diuretic indicated for the treatment of edema associated with congestive heart failure, cirrhosis of the liver, and renal disease including the nephrotic syndrome, and for the treatment of hypertension. It acts by inhibiting reabsorption of sodium and chloride at the ascending loop of Henle and distal renal tubule.",
        "description": "Furosemide (Lasix) is available as oral tablets, oral solution, and as an intravenous and intramuscular injection. Onset of diuresis is within 30-60 minutes (oral) or 5 minutes (IV).",
        "warnings": "Furosemide is a potent diuretic that, if given in excessive amounts, can lead to profound diuresis with water and electrolyte depletion; careful medical supervision is required. Risk of ototoxicity (usually reversible) with rapid IV administration or high doses, especially in renal impairment or with other ototoxic drugs. Hypokalemia, hyponatremia, hypomagnesemia, hypocalcemia, and metabolic alkalosis may occur. Risk of dehydration and prerenal azotemia. Sulfonamide hypersensitivity may cross-react.",
        "side_effects": "Common: increased urination, dizziness, orthostatic hypotension, hypokalemia, hyperuricemia, hyperglycemia, photosensitivity, and rash. Serious: severe electrolyte disturbances, ototoxicity, acute kidney injury, severe hypotension, pancreatitis, agranulocytosis, and Stevens-Johnson syndrome.",
        "dosage": "Edema (adults): initial 20-80 mg as a single dose; may be repeated or increased by 20-40 mg every 6-8 hours. Hypertension: 40 mg twice daily; adjust according to response. IV: 20-40 mg slow IV push; give over 1-2 minutes. Pediatric: 1-2 mg/kg/dose, maximum 6 mg/kg.",
    },
    "atorvastatin": {
        "before_taking": "You should not take atorvastatin if you are allergic to atorvastatin or other statins, have active liver disease, or are pregnant or breastfeeding. Tell your doctor if you have a history of liver problems, kidney disease, diabetes, thyroid disorders, muscle pain or weakness, or drink more than two alcoholic beverages daily. Share a complete medication list with your provider, particularly other lipid-lowering drugs, certain antibiotics or antifungals, HIV protease inhibitors, and cyclosporine, which can raise the risk of muscle injury.",
        "uses": "Atorvastatin is an HMG-CoA reductase inhibitor (statin) indicated as an adjunct to diet to reduce elevated LDL cholesterol, total cholesterol, triglycerides, and apolipoprotein B, and to increase HDL cholesterol in primary hyperlipidemia and mixed dyslipidemia. It also reduces the risk of myocardial infarction, stroke, revascularization procedures, and angina in patients with multiple cardiovascular risk factors or established coronary heart disease.",
        "description": "Atorvastatin (Lipitor) is an oral statin metabolized by CYP3A4. It has a long half-life among statins and can be administered at any time of day.",
        "warnings": "Statins can cause myopathy and rhabdomyolysis, including rare cases of immune-mediated necrotizing myopathy. Risk is increased with higher doses, advanced age, hypothyroidism, renal impairment, and concomitant use of strong CYP3A4 inhibitors, fibrates, or niacin. Elevations in hepatic transaminases have been reported; discontinue if persistent elevations greater than 3 times the upper limit of normal. Atorvastatin is contraindicated in pregnancy and breastfeeding.",
        "side_effects": "Common: myalgia, arthralgia, diarrhea, nasopharyngitis, urinary tract infection, and elevated transaminases. Serious: rhabdomyolysis with myoglobinuric acute kidney injury, immune-mediated necrotizing myopathy, hepatic failure, hyperglycemia and new-onset type 2 diabetes, and hypersensitivity reactions.",
        "dosage": "Adults: initial dose 10-20 mg once daily (40 mg in patients requiring greater than 45 percent LDL reduction); usual range 10-80 mg once daily. Pediatric (10-17 years, heterozygous familial hypercholesterolemia): 10 mg once daily, may increase to 20 mg/day. Take at any time of day, with or without food.",
    },
    "lisinopril": {
        "before_taking": "You should not take lisinopril if you are allergic to lisinopril, have ever had angioedema after taking an ACE inhibitor or ARB, or are pregnant. Tell your doctor if you have kidney disease, liver disease, diabetes, high potassium levels, heart problems, or a history of dialysis. Avoid potassium supplements and salt substitutes containing potassium unless directed, and inform your doctor before any surgery or before starting NSAIDs, which can reduce kidney function when combined with lisinopril.",
        "uses": "Lisinopril is an angiotensin-converting enzyme (ACE) inhibitor indicated for the treatment of hypertension in adults and pediatric patients 6 years and older, as adjunctive therapy in heart failure to reduce signs and symptoms, and to improve survival in hemodynamically stable patients within 24 hours of acute myocardial infarction. It is also used to slow the progression of diabetic nephropathy.",
        "description": "Lisinopril is a long-acting, once-daily oral ACE inhibitor that does not require hepatic activation. It is excreted unchanged in the urine and requires dose adjustment in renal impairment.",
        "warnings": "BLACK BOX WARNING - FETAL TOXICITY: When pregnancy is detected, discontinue lisinopril as soon as possible. Drugs that act directly on the renin-angiotensin system can cause injury and death to the developing fetus. Lisinopril is classified as FDA Pregnancy Category D. There is positive evidence of human fetal risk based on adverse reaction reports, including oligohydramnios, fetal renal dysfunction, hypotension, pulmonary hypoplasia, skull hypoplasia, and neonatal death. Exposure during the second and third trimesters is particularly dangerous. Angioedema of the face, extremities, lips, tongue, glottis, or larynx has occurred at any time during therapy and may be fatal, particularly in Black patients and in patients with a history of angioedema from any cause. Hyperkalemia and acute kidney injury may occur, especially in patients with renal artery stenosis, severe heart failure, volume depletion, dehydration, or concurrent potassium-sparing diuretics, potassium supplements, salt substitutes, or NSAIDs. Symptomatic hypotension may occur after the first dose, especially in volume- or salt-depleted patients. Rare cases of neutropenia, agranulocytosis, hepatic failure, and cholestatic jaundice have been reported.",
        "side_effects": "Common: dry persistent cough, dizziness, headache, fatigue, hypotension, and hyperkalemia. Serious: angioedema (including intestinal), acute kidney injury, severe hyperkalemia, neutropenia and agranulocytosis (rare), hepatic failure, and symptomatic hypotension after the first dose.",
        "dosage": "Hypertension (adults): 10 mg once daily; usual maintenance 20-40 mg once daily, maximum 80 mg/day. Heart failure: start 5 mg once daily, titrate to maximum 40 mg/day. Acute MI: 5 mg within 24 hours, then 5 mg after 24 hours, 10 mg after 48 hours, and 10 mg once daily thereafter for 6 weeks. Reduce starting dose in renal impairment.",
    },
    "amlodipine": {
        "before_taking": "You should not take amlodipine if you are allergic to amlodipine or other dihydropyridine calcium channel blockers. Tell your doctor if you have severe aortic stenosis, severe coronary artery disease, congestive heart failure, liver disease, or low blood pressure. Inform your doctor if you are pregnant, planning pregnancy, or breastfeeding, and share a complete list of medications, since amlodipine can interact with simvastatin, certain antifungals, and other CYP3A4-affecting drugs.",
        "uses": "Amlodipine is a long-acting dihydropyridine calcium channel blocker indicated for the treatment of hypertension, chronic stable angina, and confirmed or suspected vasospastic (Prinzmetal) angina. It produces vasodilation by inhibiting calcium influx into vascular smooth muscle, lowering peripheral vascular resistance.",
        "description": "Amlodipine (Norvasc) is an oral once-daily antihypertensive with a long half-life (30-50 hours) allowing smooth 24-hour blood pressure control. It is hepatically metabolized.",
        "warnings": "Symptomatic hypotension is possible, particularly in patients with severe aortic stenosis. Acute exacerbation of angina or myocardial infarction can occur, especially in patients with severe obstructive coronary artery disease, after starting or increasing the dose. Use cautiously in patients with severe hepatic impairment; start at the lowest dose and titrate slowly. Worsening heart failure has been reported in patients with severe heart failure.",
        "side_effects": "Common: peripheral edema (dose-related), flushing, palpitations, dizziness, headache, fatigue, and nausea. Serious: symptomatic hypotension, reflex tachycardia, worsening angina or MI on initiation, gingival hyperplasia, and hepatic enzyme elevations.",
        "dosage": "Hypertension (adults): 5 mg once daily; titrate over 7-14 days to maximum 10 mg once daily. Elderly, small or fragile patients, or those with hepatic impairment: start 2.5 mg once daily. Pediatric (6-17 years, hypertension): 2.5-5 mg once daily. Angina: 5-10 mg once daily.",
    },
    "sertraline": {
        "before_taking": "You should not take sertraline if you are allergic to sertraline, are taking pimozide, or have used an MAO inhibitor within the past 14 days. Tell your doctor if you have liver or kidney disease, bipolar disorder, seizures, low sodium levels, bleeding or clotting problems, glaucoma, or a history of suicidal thoughts or behavior. Inform your doctor if you are pregnant or breastfeeding, and discuss the risks of combining sertraline with other serotonergic drugs (such as triptans, tramadol, or St. John's wort) and with NSAIDs or anticoagulants that may increase bleeding risk.",
        "uses": "Sertraline is a selective serotonin reuptake inhibitor (SSRI) indicated for the treatment of major depressive disorder, obsessive-compulsive disorder (in adults and children 6 years and older), panic disorder, post-traumatic stress disorder, social anxiety disorder, and premenstrual dysphoric disorder. It selectively inhibits presynaptic serotonin reuptake with minimal effect on norepinephrine and dopamine.",
        "description": "Sertraline (Zoloft) is an oral SSRI available as tablets and oral concentrate. It is one of the most commonly prescribed antidepressants and is generally well tolerated.",
        "warnings": "BLACK BOX WARNING - SUICIDAL THOUGHTS AND BEHAVIORS: Antidepressants increased the risk of suicidal thoughts and behavior in pediatric and young adult patients in short-term studies. Closely monitor all antidepressant-treated patients of any age for clinical worsening and emergence of suicidal thoughts and behaviors, especially during initial therapy and during dose changes. Sertraline is not approved for use in pediatric patients except for patients with obsessive-compulsive disorder. Serotonin syndrome can occur, particularly with concomitant serotonergic agents (MAOIs, triptans, tramadol, linezolid, methylene blue, St. John's wort); symptoms include mental status changes, autonomic instability, neuromuscular abnormalities, and gastrointestinal symptoms. Do not use within 14 days of an MAOI. Activation of mania or hypomania may occur in patients with bipolar disorder; screen before initiation. Hyponatremia (SIADH), especially in elderly and volume-depleted patients, and increased bleeding risk with NSAIDs, aspirin, or anticoagulants have been reported. QT prolongation has occurred at higher doses. Avoid abrupt discontinuation to prevent discontinuation syndrome (dizziness, paresthesias, insomnia, irritability). Use during late pregnancy may cause neonatal complications including persistent pulmonary hypertension.",
        "side_effects": "Common: nausea, diarrhea, dry mouth, insomnia, somnolence, dizziness, fatigue, tremor, sexual dysfunction, and increased sweating. Serious: serotonin syndrome, suicidal ideation, mania, seizures, hyponatremia, QT prolongation at high doses, and discontinuation syndrome on abrupt cessation.",
        "dosage": "Depression and OCD (adults): start 50 mg once daily; titrate at intervals of no less than one week to maximum 200 mg/day. Panic disorder, PTSD, social anxiety: start 25 mg once daily for one week, then 50 mg/day, up to 200 mg/day. PMDD: 50 mg daily continuously or during luteal phase only. Pediatric OCD (6-12 years): start 25 mg daily; (13-17 years): start 50 mg daily.",
    },
    "levothyroxine": {
        "before_taking": "You should not take levothyroxine if you are allergic to levothyroxine or thyroid hormone products, have untreated thyrotoxicosis, or an uncorrected adrenal insufficiency. Tell your doctor if you have heart disease, coronary artery disease, high blood pressure, diabetes, osteoporosis, adrenal or pituitary gland problems, or any blood-clotting disorder. Take levothyroxine on an empty stomach with water and separate it by at least four hours from calcium, iron, antacids, and certain other medications that reduce its absorption.",
        "uses": "Levothyroxine is a synthetic form of thyroxine (T4) used as replacement therapy in primary, secondary, and tertiary hypothyroidism, including congenital hypothyroidism and after thyroidectomy or radioiodine therapy. It is also used as an adjunct to surgery and radioiodine in the management of well-differentiated thyroid cancer and to suppress TSH in certain patients with thyroid nodules or goiter.",
        "description": "Levothyroxine (Synthroid, Levoxyl, Tirosint) is an oral and intravenous thyroid hormone replacement. Oral absorption is best with an empty stomach and consistent timing each day.",
        "warnings": "Thyroid hormones, including levothyroxine, are not indicated for the treatment of obesity or weight loss; large doses, especially with sympathomimetic amines, may produce serious or life-threatening toxicity. Use cautiously in elderly patients and those with cardiovascular disease (coronary artery disease, arrhythmias) and start at lower doses. Over-replacement can precipitate or worsen atrial fibrillation and accelerate bone loss leading to osteoporosis in postmenopausal women.",
        "side_effects": "At appropriate doses, side effects are generally those of hyperthyroidism: tachycardia, palpitations, arrhythmias, tremor, anxiety, insomnia, heat intolerance, weight loss, increased appetite, diarrhea, menstrual irregularities, and bone loss with long-term over-replacement. Allergic reactions to tablet dyes are possible (use dye-free formulation if needed).",
        "dosage": "Adult hypothyroidism: typical full replacement 1.6 mcg/kg/day; younger healthy adults may start at full estimated dose. Elderly or cardiac disease: start 12.5-25 mcg/day and titrate every 6-8 weeks based on TSH. Pediatric doses are weight-based and higher per kg in infants (10-15 mcg/kg/day). Take on an empty stomach, 30-60 minutes before breakfast, with water; separate from calcium, iron, antacids, and certain other drugs by at least 4 hours.",
    },
    "fluoxetine": {
        "uses": "Fluoxetine is a long-acting SSRI indicated for major depressive disorder, obsessive-compulsive disorder, bulimia nervosa, panic disorder, and (in combination with olanzapine) acute depressive episodes associated with bipolar I disorder and treatment-resistant depression. Pediatric indications include MDD (8 years and older) and OCD (7 years and older).",
        "description": "Fluoxetine (Prozac) and its active metabolite norfluoxetine have long half-lives (1-3 days and 4-16 days respectively), allowing once-weekly dosing of a delayed-release formulation and a relatively benign discontinuation profile compared with shorter-acting SSRIs.",
        "warnings": "Increased risk of suicidal thinking and behavior in children, adolescents, and young adults. Risk of serotonin syndrome with other serotonergic agents and MAOIs; allow at least 14 days between MAOI discontinuation and fluoxetine, and 5 weeks after stopping fluoxetine before starting an MAOI. QT prolongation has been reported. Hyponatremia (SIADH) and bleeding risk (especially with NSAIDs and anticoagulants) may occur.",
        "side_effects": "Common: nausea, headache, insomnia, somnolence, anxiety, nervousness, decreased appetite, weight loss, diarrhea, dry mouth, and sexual dysfunction. Serious: serotonin syndrome, suicidality, mania, seizures, QT prolongation and torsades, hyponatremia, hypoglycemia in diabetics, and angle-closure glaucoma.",
        "dosage": "MDD/OCD (adults): start 20 mg once daily in the morning; may increase after several weeks to maximum 80 mg/day. Bulimia: 60 mg once daily in the morning. Panic disorder: 10 mg/day for one week then 20 mg/day. Pediatric MDD (8-17 years): 10-20 mg/day. Once-weekly delayed-release (90 mg) may be used for maintenance MDD in stable patients.",
        "before_taking": "You should not take fluoxetine if you are allergic to fluoxetine, are taking pimozide or thioridazine, or have used an MAO inhibitor within the past 14 days (or plan to use one within 5 weeks of stopping fluoxetine). Tell your doctor if you have liver disease, seizures or epilepsy, diabetes, bipolar disorder, a history of suicidal thoughts, low sodium, narrow-angle glaucoma, or a history of sexual dysfunction. Inform your doctor if you are pregnant or breastfeeding, and discuss any other serotonergic drugs you take.",
    },
    "semaglutide": {
        "description": "Semaglutide is a glucagon-like peptide-1 (GLP-1) receptor agonist available as a once-weekly subcutaneous injection (Ozempic for type 2 diabetes, Wegovy for chronic weight management) and as once-daily oral tablets (Rybelsus for type 2 diabetes).",
        "uses": "Semaglutide (Ozempic) is indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes mellitus, and to reduce the risk of major adverse cardiovascular events in adults with type 2 diabetes and established cardiovascular disease. Semaglutide (Wegovy) is indicated for chronic weight management in adults with obesity (BMI ≥30) or overweight (BMI ≥27) with at least one weight-related comorbidity, as an adjunct to a reduced-calorie diet and increased physical activity. Semaglutide (Rybelsus) is the oral formulation indicated for glycemic control in adults with type 2 diabetes.",
        "warnings": "Semaglutide carries a BOXED WARNING for thyroid C-cell tumors: in rodents, GLP-1 receptor agonists have caused thyroid C-cell tumors; it is unknown whether semaglutide causes these tumors in humans, including medullary thyroid carcinoma (MTC). Contraindicated in patients with a personal or family history of MTC or Multiple Endocrine Neoplasia syndrome type 2 (MEN 2). Pancreatitis (acute and chronic) has been reported; discontinue if pancreatitis is suspected. Diabetic retinopathy complications, including vision loss, have been reported. Risk of hypoglycemia with concomitant insulin or sulfonylurea. Acute kidney injury has been reported. Hypersensitivity reactions including anaphylaxis have occurred. Avoid use in pregnancy.",
        "side_effects": "Very common: nausea, vomiting, diarrhea, constipation, abdominal pain. These GI effects are most pronounced during dose escalation and generally decrease over time. Serious: pancreatitis, diabetic retinopathy complications, hypoglycemia (with insulin or sulfonylurea), acute kidney injury, anaphylaxis, gallbladder disease (cholelithiasis, cholecystitis), suicidal ideation and behavior (reported with weight-loss drugs generally). Injection-site reactions with subcutaneous formulations.",
        "dosage": "Ozempic (type 2 diabetes): Start 0.25 mg once weekly for 4 weeks, then 0.5 mg once weekly; may increase to 1 mg once weekly after at least 4 weeks; maximum 2 mg once weekly. Wegovy (weight management): Start 0.25 mg once weekly, increase by 0.25 mg every 4 weeks to maintenance dose of 2.4 mg once weekly. Rybelsus (oral): 3 mg once daily for 30 days, then 7 mg once daily; may increase to 14 mg once daily. Take Rybelsus on an empty stomach with up to 4 oz of water at least 30 minutes before the first food or drink of the day.",
        "before_taking": "You should not take semaglutide if you or a family member has ever had medullary thyroid carcinoma (MTC) or Multiple Endocrine Neoplasia syndrome type 2 (MEN 2), or if you are allergic to semaglutide or any of its ingredients. Tell your doctor if you have a history of pancreatitis, gallbladder disease, diabetic retinopathy, kidney disease, liver disease, or depression or suicidal thoughts. Tell your doctor about all medications you take, especially insulin or sulfonylureas (which increase hypoglycemia risk), and any orally administered medications (Rybelsus may affect their absorption). Semaglutide should not be used during pregnancy; use effective contraception and inform your doctor if you become pregnant.",
    },
    "omeprazole": {
        "before_taking": "You should not take omeprazole if you are allergic to omeprazole, other proton pump inhibitors (such as lansoprazole, pantoprazole, esomeprazole), or any of its ingredients. Tell your doctor if you have liver disease, low magnesium levels, osteoporosis or bone fractures, lupus, or are scheduled for certain gastric or endoscopic tests. Inform your doctor if you are taking methotrexate, HIV medications (such as atazanavir, nelfinavir), clopidogrel, or warfarin, as omeprazole can affect their effectiveness. Tell your doctor if you are pregnant or breastfeeding. OTC omeprazole is intended only for self-treatment of frequent heartburn for up to 14 days; do not use for more than 3 fourteen-day treatment courses per year without consulting a healthcare provider.",
    },
    "aspirin": {
        "before_taking": "You should not take aspirin if you are allergic to aspirin or other salicylates, or if your child or teenager has or is recovering from chickenpox or a flu-like illness (risk of Reye syndrome). Tell your doctor if you have a bleeding disorder, active peptic ulcer, severe kidney or liver disease, uncontrolled high blood pressure, heart failure, gout, or aspirin-exacerbated respiratory disease (nasal polyps with asthma). Aspirin interacts with anticoagulants, other NSAIDs, corticosteroids, and methotrexate. Do not take aspirin in the third trimester of pregnancy. Consult your healthcare provider before starting or stopping low-dose aspirin for cardiovascular prevention.",
    },
    "rosuvastatin": {
        "description": "Rosuvastatin (Crestor) is a fully synthetic, high-potency HMG-CoA reductase inhibitor (statin) available as 5, 10, 20, and 40 mg tablets. It produces greater LDL reduction per milligram than most other statins.",
        "uses": "Rosuvastatin is indicated as an adjunct to diet to reduce elevated total cholesterol, LDL-C, apolipoprotein B, non-HDL cholesterol, and triglycerides, and to increase HDL-C in adults with primary hyperlipidemia or mixed dyslipidemia. It is also indicated for hypertriglyceridemia, primary dysbetalipoproteinemia (Type III hyperlipoproteinemia), and to slow the progression of atherosclerosis. In patients without clinically evident coronary heart disease but with multiple cardiovascular risk factors, rosuvastatin is indicated to reduce the risk of myocardial infarction and stroke (JUPITER trial indication).",
        "warnings": "Rosuvastatin is contraindicated in patients with active liver disease or unexplained persistent elevations in serum transaminases, in pregnant women and women who may become pregnant, and in nursing mothers. Myopathy and rhabdomyolysis with acute renal failure have been reported — risk is increased with higher doses, Asian ancestry, hypothyroidism, renal impairment, and concurrent use of cyclosporine, gemfibrozil, or niacin. Discontinue immediately at first signs of unexplained muscle pain, tenderness, or weakness. Monitor liver enzymes before initiation. Rosuvastatin can increase blood glucose; monitor in diabetic patients.",
        "side_effects": "Common: headache, myalgia, abdominal pain, nausea, and constipation. Serious: rhabdomyolysis and myopathy (dose-dependent), hepatic enzyme elevations, immune-mediated necrotizing myopathy (rare), new-onset diabetes, and angioedema (rare).",
        "dosage": "Primary hyperlipidemia: 10-20 mg once daily; range 5-40 mg/day. Patients of Asian ancestry: start 5 mg once daily. Heterozygous familial hypercholesterolemia (HeFH): 10-40 mg once daily. Homozygous FH: 20-40 mg once daily. Pediatric HeFH (10-17 years): 5-20 mg/day. Take with or without food, at any time of day. Maximum dose 40 mg/day in most patients.",
        "before_taking": "You should not take rosuvastatin if you are pregnant, may become pregnant, or are breastfeeding, as statins can harm the fetus. Do not take rosuvastatin if you have active liver disease or unexplained elevated liver enzymes, or if you are allergic to rosuvastatin or any ingredient. Tell your doctor if you have a history of liver disease, kidney disease, diabetes, hypothyroidism, or are of Asian ancestry (requires lower starting dose). Tell your doctor about all medications you take, especially cyclosporine, gemfibrozil, niacin, azole antifungals, and protease inhibitors, as these can increase the risk of muscle problems.",
    },
    "losartan": {
        "description": "Losartan (Cozaar) is an angiotensin II receptor blocker (ARB) that selectively blocks the AT1 receptor, lowering blood pressure through vasodilation and reduced aldosterone secretion. It was the first ARB approved in the United States.",
        "uses": "Losartan is indicated for the treatment of hypertension in adults and children 6 years and older, to reduce the risk of stroke in patients with hypertension and left ventricular hypertrophy (LVH), and to slow the progression of diabetic nephropathy in patients with type 2 diabetes and elevated serum creatinine and proteinuria. In the LIFE trial, losartan reduced the combined risk of stroke, MI, and cardiovascular death compared with atenolol in hypertensive patients with LVH.",
        "warnings": "Like ACE inhibitors, ARBs including losartan are contraindicated in pregnancy due to fetal toxicity (oligohydramnios, fetal renal dysfunction, pulmonary hypoplasia, and neonatal death). When pregnancy is detected, discontinue immediately. Losartan is also contraindicated with aliskiren in patients with diabetes. Hyperkalemia may occur, especially in patients with renal impairment, diabetes, or on potassium-sparing diuretics. Acute renal failure can occur in bilateral renal artery stenosis. Hypotension, especially after the first dose, may occur in volume-depleted patients.",
        "side_effects": "Common: dizziness, fatigue, hyperkalemia (especially in renal impairment), and hypotension. Unlike ACE inhibitors, losartan does not cause cough. Serious: angioedema (rare, less frequent than with ACE inhibitors), acute kidney injury, severe hyperkalemia, and fetal toxicity in pregnancy.",
        "dosage": "Hypertension (adults): 50 mg once daily; usual maintenance 25-100 mg once daily (may be given in two divided doses). LVH risk reduction: 50 mg once daily with hydrochlorothiazide 12.5 mg; titrate to losartan 100 mg + hydrochlorothiazide 25 mg. Diabetic nephropathy: 50 mg once daily, titrate to 100 mg once daily. May be taken with or without food.",
        "before_taking": "You should not take losartan if you are pregnant (Category D) — discontinue as soon as pregnancy is detected. Do not take losartan with aliskiren if you have diabetes. Tell your doctor if you have kidney disease or a single kidney, renal artery stenosis, liver disease, heart failure, dehydration, or low blood pressure. Tell your doctor about potassium supplements or salt substitutes, NSAIDs, diuretics, and lithium. Inform your doctor if you are breastfeeding.",
    },
    "azithromycin": {
        "description": "Azithromycin (Zithromax, Z-Pak) is a macrolide antibiotic that inhibits bacterial protein synthesis by binding the 50S ribosomal subunit. It has a long tissue half-life (68 hours), allowing shorter treatment courses than most antibiotics.",
        "uses": "Azithromycin is indicated for community-acquired pneumonia (mild to moderate), acute exacerbations of chronic bronchitis, pharyngitis/tonsillitis (as an alternative to first-line therapy), skin and skin-structure infections (uncomplicated), urethritis and cervicitis due to Chlamydia trachomatis or Neisseria gonorrhoeae, and acute otitis media in pediatric patients. It is also used for prevention and treatment of Mycobacterium avium complex (MAC) in HIV patients.",
        "warnings": "Serious allergic reactions, including anaphylaxis and serious skin reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis), have occurred. Azithromycin can cause QT interval prolongation and cases of torsades de pointes, particularly in patients with known QT prolongation, hypokalemia, hypomagnesemia, bradycardia, or taking other QT-prolonging drugs. Clostridioides difficile-associated diarrhea has been reported. Liver disease, including hepatic necrosis and hepatic failure resulting in death, has been reported. Exacerbation of myasthenia gravis has occurred. Use caution in patients with liver disease.",
        "side_effects": "Common: diarrhea/loose stools, nausea, abdominal pain, and vomiting (especially with higher doses). Serious: QT prolongation and torsades de pointes, Clostridioides difficile colitis, hepatotoxicity, allergic reactions including anaphylaxis, severe skin reactions, and exacerbation of myasthenia gravis.",
        "dosage": "Community-acquired pneumonia (adult, mild-moderate): 500 mg on Day 1, then 250 mg once daily on Days 2-5 (Z-Pak). Pharyngitis (adults): 500 mg on Day 1, then 250 mg/day for 4 days. Acute otitis media (pediatric, 6 months+): 30 mg/kg as single dose or 10 mg/kg once daily for 3 days or 10 mg/kg on Day 1 then 5 mg/kg/day for 4 days. Genital chlamydia/gonorrhea: 1 g single dose. Take tablets with or without food; avoid antacids within 2 hours.",
        "before_taking": "You should not take azithromycin if you are allergic to azithromycin, erythromycin, or other macrolide antibiotics, or if you have a history of cholestatic jaundice or hepatic dysfunction associated with azithromycin. Tell your doctor if you have liver disease, kidney disease, myasthenia gravis, or a history of QT prolongation or cardiac arrhythmias. Tell your doctor about all medications you take, particularly antacids (reduce absorption), QT-prolonging drugs, and warfarin (azithromycin can increase INR). Inform your doctor if you are pregnant or breastfeeding.",
    },
    "escitalopram": {
        "description": "Escitalopram (Lexapro) is an S-enantiomer of citalopram — the most selective SSRI available, with high specificity for the serotonin transporter (SERT) and minimal effects on other receptors. Available as 5, 10, and 20 mg tablets and oral solution.",
        "uses": "Escitalopram is indicated for the acute and maintenance treatment of major depressive disorder (MDD) in adults and adolescents 12 years and older, and for the acute treatment of generalized anxiety disorder (GAD) in adults. It is frequently used off-label for social anxiety disorder, panic disorder, OCD, and PTSD due to its favorable tolerability profile.",
        "warnings": "BLACK BOX WARNING — SUICIDAL THOUGHTS AND BEHAVIORS: Antidepressants increase the risk of suicidal thinking and behavior in pediatric and young adult patients in short-term studies. Closely monitor all patients, especially during initiation and dose changes. Serotonin syndrome may occur with concomitant serotonergic drugs (MAOIs, triptans, tramadol, fentanyl, lithium, St. John's wort, linezolid, methylene blue); do not use with or within 14 days of an MAOI. QT prolongation and torsades de pointes have been reported — avoid with concomitant QT-prolonging drugs. Hyponatremia (SIADH) and increased bleeding risk with NSAIDs and anticoagulants have been reported.",
        "side_effects": "Common: nausea, insomnia, somnolence, dizziness, sweating, dry mouth, decreased libido, ejaculation disorder, and fatigue. Serious: serotonin syndrome, QT prolongation and torsades de pointes, suicidal ideation, mania, seizures, hyponatremia, and discontinuation syndrome on abrupt cessation.",
        "dosage": "MDD and GAD (adults): 10 mg once daily; may increase to 20 mg once daily after a minimum of one week. Elderly patients: 10 mg once daily maximum recommended dose. Adolescents 12-17 years (MDD): 10 mg once daily; may increase to 20 mg after 3 weeks. Hepatic impairment: 10 mg once daily (maximum). May be taken with or without food, at any time of day.",
        "before_taking": "You should not take escitalopram if you are allergic to escitalopram or citalopram, if you are taking or have taken an MAOI within the past 14 days, or if you are taking pimozide. Tell your doctor if you have heart disease, a history of QT prolongation or electrolyte abnormalities, seizures, bipolar disorder, a history of suicidal thoughts, or liver or kidney disease. Inform your doctor about all serotonergic drugs you take (including tramadol, triptans, St. John's wort), anticoagulants, and NSAIDs. Discuss the risks if you are pregnant or breastfeeding.",
    },
    "duloxetine": {
        "description": "Duloxetine (Cymbalta) is a serotonin-norepinephrine reuptake inhibitor (SNRI) that inhibits both serotonin (SERT) and norepinephrine (NET) transporters with comparable potency. Available as delayed-release capsules of 20, 30, and 60 mg.",
        "uses": "Duloxetine is FDA-approved for major depressive disorder, generalized anxiety disorder, diabetic peripheral neuropathic pain, fibromyalgia, and chronic musculoskeletal pain (including chronic low back pain and chronic pain from osteoarthritis). It is one of the few antidepressants with regulatory approval for pain indications.",
        "warnings": "BLACK BOX WARNING — SUICIDAL THOUGHTS AND BEHAVIORS in pediatric and young adult patients. Do not use within 14 days of an MAOI; allow at least 5 days after stopping duloxetine before starting an MAOI. Hepatotoxicity (including liver failure, fatal cases) has been reported — avoid in patients with substantial alcohol use or pre-existing liver disease. Serotonin syndrome can occur with concomitant serotonergic agents. Abrupt discontinuation can cause discontinuation syndrome (dizziness, nausea, headache, paresthesias, vomiting, irritability, nightmares); taper when stopping. Blood pressure increases may occur; monitor blood pressure. Urinary retention has been reported.",
        "side_effects": "Common: nausea, dry mouth, somnolence, fatigue, constipation, dizziness, sweating, decreased appetite, and sexual dysfunction. Serious: hepatotoxicity, serotonin syndrome, mania, seizures, hyponatremia, increased blood pressure, urinary retention, severe skin reactions, and discontinuation syndrome.",
        "dosage": "MDD: 40-60 mg/day in one or two divided doses (range 40-120 mg/day). GAD: 60 mg once daily (start at 30 mg/day for one week). Fibromyalgia: 60 mg once daily. Diabetic neuropathic pain: 60 mg once daily. Chronic musculoskeletal pain: 60 mg once daily. Swallow capsules whole; do not crush or chew. May be taken with or without food.",
        "before_taking": "You should not take duloxetine if you are allergic to duloxetine, have uncontrolled narrow-angle glaucoma, or have taken an MAOI within the past 14 days. Tell your doctor if you have liver disease or drink more than 3 alcoholic beverages per day (hepatotoxicity risk), kidney disease, bipolar disorder, a history of seizures, hypertension, bleeding problems, urinary retention, or a history of suicidal thoughts. Tell your doctor about all serotonergic drugs (tramadol, triptans, lithium, linezolid, methylene blue, St. John's wort) and anticoagulants or NSAIDs you take.",
    },
    "clonazepam": {
        "description": "Clonazepam (Klonopin) is a benzodiazepine anticonvulsant and anxiolytic that enhances GABA activity by binding to GABA-A receptors. Available as 0.5, 1, and 2 mg tablets and orally disintegrating tablets (wafers).",
        "uses": "Clonazepam is FDA-approved for the treatment of panic disorder (with or without agoraphobia) and as an adjunct for absence seizures (petit mal) and Lennox-Gastaut syndrome in adults and children. It is frequently used off-label for social anxiety disorder, restless legs syndrome, REM sleep behavior disorder, and as an adjunct in bipolar disorder.",
        "warnings": "FDA BOXED WARNING: Concurrent use of benzodiazepines and opioids may result in profound sedation, respiratory depression, coma, and death. Reserve concurrent prescribing for use in patients for whom alternative treatment options are inadequate. Use the lowest effective doses for the shortest duration. Clonazepam has significant potential for abuse, addiction, and physical dependence; assess for these risks before prescribing. Abrupt discontinuation after prolonged use can cause a life-threatening withdrawal syndrome including seizures; taper gradually. Elderly patients are particularly sensitive to CNS depression, falls, and cognitive impairment.",
        "side_effects": "Common: drowsiness, ataxia, dizziness, fatigue, cognitive impairment, depression, and coordination problems. Serious: respiratory depression (especially with opioids or alcohol), CNS depression, paradoxical reactions (agitation, aggression), physical dependence, and severe withdrawal syndrome on abrupt discontinuation.",
        "dosage": "Panic disorder (adults): 0.25 mg twice daily; titrate to 1 mg/day. Target dose 1 mg/day. Seizures (adults): 1.5 mg/day in 3 divided doses; titrate up to 20 mg/day if needed. Pediatric seizures (up to 10 years): 0.01-0.03 mg/kg/day in 2-3 divided doses; titrate to maximum 0.1-0.2 mg/kg/day. Take with or without food. Wafers dissolve in the mouth; no water needed.",
        "before_taking": "You should not take clonazepam if you are allergic to clonazepam or other benzodiazepines, have significant liver disease, or narrow-angle glaucoma. Tell your doctor about all CNS depressants you take, especially opioids — this combination can be fatal. Tell your doctor if you have a history of drug or alcohol abuse or addiction, depression, suicidal thoughts, respiratory disease (COPD, sleep apnea), kidney or liver disease, myasthenia gravis, or porphyria. Do not stop clonazepam abruptly as severe withdrawal, including seizures, may occur. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "lorazepam": {
        "description": "Lorazepam (Ativan) is an intermediate-acting benzodiazepine with anxiolytic, sedative, anticonvulsant, and amnestic properties. Available as 0.5, 1, and 2 mg tablets, oral solution, and injectable formulation.",
        "uses": "Lorazepam tablets are indicated for the management of anxiety disorders and for short-term relief of anxiety symptoms associated with depression. Injectable lorazepam is used as preanesthetic medication, for treatment of status epilepticus, and for procedural sedation. Oral lorazepam is also frequently used for insomnia, alcohol withdrawal, nausea from chemotherapy (off-label), and acute agitation.",
        "warnings": "FDA BOXED WARNING: Concurrent use with opioids can cause profound sedation, respiratory depression, coma, and death. Physical and psychological dependence develop rapidly — lorazepam should be used at the lowest effective dose for the shortest duration possible. Abrupt discontinuation after prolonged use can cause severe withdrawal including seizures; taper gradually. Lorazepam may cause respiratory depression, especially when combined with other CNS depressants. Cognitive impairment, falls, and paradoxical reactions (agitation, hostility) may occur, particularly in elderly patients.",
        "side_effects": "Common: sedation, dizziness, weakness, ataxia, and cognitive impairment. Serious: respiratory depression (especially with opioids or alcohol), paradoxical reactions (agitation, aggression), anterograde amnesia, dependence and withdrawal syndrome, and falls in elderly.",
        "dosage": "Anxiety (adults): 2-6 mg/day in 2-3 divided doses (usual: 2-3 mg twice daily). Insomnia (adults): 2-4 mg at bedtime. Elderly or debilitated: start 1-2 mg/day in divided doses. Duration of use: generally not more than 2-4 weeks. Take with or without food.",
        "before_taking": "You should not take lorazepam if you are allergic to lorazepam or other benzodiazepines, have acute narrow-angle glaucoma, or severe respiratory insufficiency (except in monitored settings). Tell your doctor if you take opioids, alcohol, or other CNS depressants (life-threatening combination), have a history of substance abuse, depression, suicidal thoughts, respiratory disease, kidney or liver disease, or porphyria. Do not stop abruptly if you've been taking it regularly. Inform your doctor if you are pregnant (neonatal withdrawal risk) or breastfeeding.",
    },
    "quetiapine": {
        "description": "Quetiapine (Seroquel) is an atypical antipsychotic of the dibenzothiazepine class that antagonizes multiple neurotransmitter receptors including dopamine D2, serotonin 5-HT2A, histamine H1, and alpha-1 adrenergic receptors. Available as immediate-release tablets (25-400 mg) and extended-release tablets (Seroquel XR, 50-400 mg).",
        "uses": "Quetiapine is FDA-approved for schizophrenia (adults and adolescents 13+), bipolar disorder type I (acute manic episodes, depressive episodes, and maintenance — both as monotherapy and adjunct to lithium or divalproex), and as an adjunct to antidepressants in major depressive disorder (extended-release formulation). Off-label uses include anxiety disorders, PTSD, sleep disorders, and delirium.",
        "warnings": "BLACK BOX WARNING: Elderly patients with dementia-related psychosis treated with antipsychotics are at an increased risk of death. Quetiapine is not approved for the treatment of dementia-related psychosis. BLACK BOX WARNING: Antidepressants increase the risk of suicidal thinking and behavior in pediatric and young adult patients when used for depression (XR formulation). Quetiapine can cause metabolic changes including hyperglycemia, dyslipidemia, and weight gain — monitor glucose and lipids. Neuroleptic malignant syndrome (NMS) and tardive dyskinesia may occur. Hypotension and syncope (especially during initiation), somnolence, falls, and orthostatic hypotension are common. QT interval prolongation and cataracts have been reported; periodic eye examinations are recommended.",
        "side_effects": "Common: drowsiness, dry mouth, dizziness, constipation, weight gain, increased appetite, fatigue, and nasal congestion. Serious: metabolic syndrome (weight gain, hyperglycemia, dyslipidemia), tardive dyskinesia, NMS, orthostatic hypotension, QT prolongation, new-onset diabetes, hypothyroidism, and leukopenia/agranulocytosis.",
        "dosage": "Schizophrenia (adults): 150-750 mg/day in divided doses (IR) or once daily (XR). Start 25 mg twice daily, increase by 25-50 mg/day. Bipolar mania: 400-800 mg/day; start 50 mg twice daily. Bipolar depression: 300 mg once daily at bedtime (IR or XR). MDD adjunct (XR): 50-300 mg once daily at bedtime. Avoid abrupt discontinuation. Take IR tablets with or without food; take XR tablets without food or with a light meal.",
        "before_taking": "Tell your doctor if you have a history of heart disease or QT prolongation, diabetes (quetiapine can increase blood glucose), liver disease, seizures, thyroid problems, low blood pressure, or a history of cataracts. Quetiapine can cause substantial weight gain and metabolic effects; discuss monitoring plans with your doctor. Do not drive or operate heavy machinery until you know how quetiapine affects you — somnolence is common. Avoid alcohol, which increases sedation. Tell your doctor if you are pregnant or breastfeeding (neonatal extrapyramidal effects and withdrawal may occur after third-trimester exposure).",
    },
    "prednisone": {
        "description": "Prednisone is an oral corticosteroid (glucocorticoid) that is converted to prednisolone in the liver. It is available as immediate-release tablets (1-50 mg), delayed-release tablets, and oral solution.",
        "uses": "Prednisone is used for a wide range of conditions requiring anti-inflammatory or immunosuppressive therapy, including severe allergic reactions, asthma exacerbations, COPD exacerbations, autoimmune diseases (rheumatoid arthritis, lupus, inflammatory bowel disease, multiple sclerosis), nephrotic syndrome, organ transplant rejection prophylaxis, and certain cancers (lymphoma, leukemia). It is one of the most widely used anti-inflammatory medications.",
        "warnings": "Long-term use of corticosteroids causes adrenal suppression — do not stop abruptly after prolonged use; taper gradually to allow adrenal recovery. Long-term or high-dose use causes osteoporosis, Cushing syndrome, hyperglycemia, immunosuppression with increased infection risk (including unusual/opportunistic infections), hypertension, peptic ulcers, cataracts and glaucoma, psychiatric effects (mood changes, insomnia, psychosis), growth suppression in children, and cardiovascular disease. Avoid live vaccines during therapy. Moderate to high doses can worsen or unmask infections — screen for tuberculosis and ensure vaccinations are current before starting. NSAIDs combined with corticosteroids greatly increase GI ulceration risk.",
        "side_effects": "Common: increased appetite and weight gain, fluid retention, mood changes (euphoria, irritability, insomnia), elevated blood glucose, increased blood pressure, and GI upset. Long-term serious effects: osteoporosis, avascular necrosis of the hip, cataracts, glaucoma, Cushing syndrome, adrenal insufficiency, and immunosuppression. Psychiatric: mood swings, depression, psychosis (particularly at higher doses).",
        "dosage": "Doses vary widely by indication. Anti-inflammatory/allergic: 5-60 mg once daily or divided. Acute asthma: 40-60 mg/day for 5-7 days. Autoimmune conditions: individualized, often tapered over weeks. Short bursts (5-7 days) usually do not require tapering. Take with food to reduce GI irritation. Alternate-day dosing reduces adrenal suppression for long-term therapy.",
        "before_taking": "Tell your doctor if you have diabetes (prednisone raises blood sugar), osteoporosis, high blood pressure, glaucoma, cataracts, peptic ulcer disease, liver disease, active infections, psychiatric disorders, or a history of tuberculosis. Do not take live vaccines while on prednisone. Tell your doctor about all medications you take — NSAIDs, warfarin, diuretics, and antidiabetics are among those with important interactions. Do not stop prednisone abruptly after prolonged use — adrenal crisis can occur. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "bupropion": {
        "description": "Bupropion (Wellbutrin, Zyban) is a norepinephrine-dopamine reuptake inhibitor (NDRI) and nicotinic acetylcholine receptor antagonist. It is structurally unrelated to SSRIs and SNRIs and has a distinct pharmacological and side-effect profile. Available as immediate-release (IR), sustained-release (SR), and extended-release (XL) formulations.",
        "uses": "Bupropion is FDA-approved for major depressive disorder (MDD), seasonal affective disorder (SAD), and as an aid to smoking cessation (Zyban). Off-label uses include ADHD (in adults and children), bipolar depression (as an adjunct), sexual dysfunction related to SSRI use, and weight management. Bupropion is often preferred in patients who cannot tolerate sexual dysfunction or weight gain from SSRIs.",
        "warnings": "BLACK BOX WARNING: Antidepressants increase the risk of suicidal thinking and behavior in pediatric and young adult patients. BLACK BOX WARNING (Zyban): Serious neuropsychiatric reactions including changes in behavior, hostility, agitation, depressed mood, and suicidal ideation have occurred during treatment of smoking cessation. Bupropion lowers the seizure threshold in a dose-dependent manner; the risk is increased with eating disorders (anorexia, bulimia), prior head trauma, CNS tumors, high doses, abrupt alcohol/benzodiazepine withdrawal, and concomitant drugs that lower seizure threshold. Do not exceed 450 mg/day (Wellbutrin XL); take divided doses for other formulations. Hypertension has occurred, especially in patients already on nicotine replacement therapy for smoking cessation. Angle-closure glaucoma may occur.",
        "side_effects": "Common: dry mouth, insomnia, nausea, headache, dizziness, constipation, agitation/anxiety, tremor, and increased sweating. Bupropion does NOT typically cause sexual dysfunction or weight gain — unlike SSRIs, it may produce modest weight loss. Serious: seizures (dose-related), hypertension, angle-closure glaucoma, severe neuropsychiatric reactions (in smoking cessation).",
        "dosage": "MDD — Wellbutrin IR: 100 mg three times daily; maximum 450 mg/day. Wellbutrin SR: 150 mg twice daily; maximum 400 mg/day. Wellbutrin XL: 150-300 mg once daily in the morning; maximum 450 mg/day. SAD (XL only): 150 mg once daily in the morning, may increase to 300 mg. Smoking cessation (Zyban SR): start 150 mg once daily for 3 days, then 150 mg twice daily for 7-12 weeks.",
        "before_taking": "You should not take bupropion if you have a seizure disorder, an eating disorder (anorexia or bulimia), or have taken an MAOI within the past 14 days. Do not use both Wellbutrin and Zyban simultaneously (both contain bupropion). Tell your doctor if you have bipolar disorder, a history of head injury, a brain tumor, kidney or liver disease, diabetes (bupropion affects blood glucose), or hypertension. Tell your doctor about all medications you take — CYP2D6-metabolized drugs (tamoxifen, many antidepressants), drugs that lower seizure threshold, and nicotine replacement products all interact. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "hydrochlorothiazide": {
        "description": "Hydrochlorothiazide (HCTZ, Microzide) is a thiazide diuretic that inhibits sodium and chloride reabsorption in the distal convoluted tubule of the kidney, increasing urinary excretion of water and electrolytes.",
        "uses": "Hydrochlorothiazide is indicated for the treatment of hypertension (as monotherapy or in combination with other antihypertensives) and for edema associated with congestive heart failure, hepatic cirrhosis, and renal dysfunction, including the nephrotic syndrome. It is commonly combined with ACE inhibitors (lisinopril, enalapril), ARBs (losartan, valsartan), and beta-blockers in fixed-dose combination products.",
        "warnings": "Electrolyte imbalances are common — hypokalemia, hyponatremia, hypochloremia, hypomagnesemia, and hypercalcemia may occur. Monitor electrolytes and renal function, especially in patients on digoxin (hypokalemia increases digoxin toxicity), lithium (thiazides reduce lithium clearance, increasing toxicity), or with concurrent diuretic therapy. Hyperglycemia may occur; use caution in diabetic patients. Gout may be precipitated or worsened. Thiazides can cause photosensitivity. Avoid in anuria. Sulfonamide allergy cross-reactivity is possible. Avoid high doses in elderly patients due to fall risk.",
        "side_effects": "Common: increased urination, hypokalemia, dizziness, muscle cramps, weakness, and headache. Serious: severe electrolyte disturbances (life-threatening hyponatremia, hypokalemia), digoxin toxicity (via hypokalemia), hyperuricemia and gout, hyperglycemia, cholesterol elevation, photosensitivity, and acute pancreatitis (rare).",
        "dosage": "Hypertension: 12.5-25 mg once daily; maximum 50 mg/day. Edema: 25-100 mg once daily or twice daily. Take in the morning to avoid nighttime urination. Monitor electrolytes, renal function, glucose, and uric acid periodically.",
        "before_taking": "You should not take hydrochlorothiazide if you have anuria (no urine output) or if you are allergic to sulfonamide-derived medications or thiazide diuretics. Tell your doctor if you have kidney disease, liver disease, diabetes, gout, lupus, low blood potassium, or high blood calcium. Tell your doctor if you take lithium, digoxin, NSAIDs, corticosteroids, or other diuretics. Avoid excessive sun exposure — HCTZ increases photosensitivity and has been linked to an increased risk of non-melanoma skin cancer with long-term use. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "doxycycline": {
        "description": "Doxycycline is a broad-spectrum tetracycline antibiotic that inhibits protein synthesis by binding to the 30S ribosomal subunit. Available as hyclate and monohydrate salt formulations, in immediate-release capsules/tablets and delayed-release capsules.",
        "uses": "Doxycycline is indicated for respiratory tract infections (including community-acquired pneumonia caused by susceptible organisms), skin and soft tissue infections, sexually transmitted infections (chlamydia, gonorrhea, syphilis), Lyme disease, rickettsia, malaria prophylaxis, Rocky Mountain spotted fever, acne vulgaris, anthrax prophylaxis, and as an alternative to other antibiotics in penicillin-allergic patients.",
        "warnings": "Do not give doxycycline to children under 8 years of age (permanent tooth discoloration and bone growth inhibition). Doxycycline can cause photosensitivity — avoid excessive sun or UV light exposure and use sunscreen. Esophageal irritation and ulceration have occurred — take with adequate water and remain upright for at least 30 minutes. Clostridioides difficile-associated diarrhea has been reported. Use cautiously in patients with hepatic impairment. Avoid antacids, dairy products, and iron supplements within 2 hours of doxycycline as they impair absorption. Category D in pregnancy (tooth discoloration, bone inhibition).",
        "side_effects": "Common: nausea, vomiting, diarrhea, esophageal irritation, and photosensitivity. Serious: Clostridioides difficile colitis, esophageal ulceration, severe skin reactions (SJS/TEN), pseudotumor cerebri (intracranial hypertension), and hepatotoxicity (rare).",
        "dosage": "Most infections (adults): 100 mg every 12 hours or 200 mg on Day 1, then 100 mg once daily. Severe infections: 100 mg twice daily. Acne: 50-100 mg twice daily. Malaria prophylaxis: 100 mg once daily starting 1-2 days before travel. STIs: 100 mg twice daily for 7 days (chlamydia) or 21 days (syphilis). Take with a full glass of water; avoid antacids and dairy 2 hours before/after.",
        "before_taking": "You should not take doxycycline if you are allergic to doxycycline or other tetracyclines, or if the patient is a child under 8 years of age. Tell your doctor if you have liver disease, kidney disease, esophageal problems, intracranial hypertension (pseudotumor cerebri), or myasthenia gravis. Avoid antacids, dairy products, and iron within 2 hours before or after. Separate from oral retinoids due to intracranial hypertension risk. Doxycycline may reduce oral contraceptive efficacy — use additional contraception. Inform your doctor if you are pregnant (Category D) or breastfeeding.",
    },
    "valsartan": {
        "description": "Valsartan (Diovan) is an angiotensin II receptor blocker (ARB) that selectively antagonizes the AT1 receptor subtype, blocking the vasoconstrictive and aldosterone-secreting effects of angiotensin II.",
        "uses": "Valsartan is indicated for hypertension (alone or with other antihypertensives), heart failure (NYHA Class II-IV, to reduce cardiovascular death and hospitalizations), and post-myocardial infarction left ventricular dysfunction or failure (to reduce CV mortality in stable patients with left ventricular failure or dysfunction following a heart attack).",
        "warnings": "Valsartan can cause fetal harm — discontinue immediately if pregnancy is detected (black box warning). Do not use valsartan with aliskiren in patients with diabetes. Do not combine with ACE inhibitors or aliskiren due to increased risk of hypotension, hyperkalemia, and renal impairment. Monitor serum potassium, renal function, and blood pressure. Hypotension may occur, especially in volume-depleted patients (on diuretics, low-salt diet). Use caution in patients with renal artery stenosis — ARBs can precipitate acute renal failure.",
        "side_effects": "Common: dizziness, hypotension, headache, fatigue, hyperkalemia, and elevated serum creatinine. Serious: fetal toxicity, acute renal failure, angioedema (less common than with ACE inhibitors), severe hypotension, and hyperkalemia.",
        "dosage": "Hypertension: 80-160 mg once daily; maximum 320 mg/day. Heart failure: starting dose 40 mg twice daily, titrate to 160 mg twice daily as tolerated. Post-MI: starting dose 20 mg twice daily, titrate to 160 mg twice daily over several weeks.",
        "before_taking": "You should not take valsartan if you are pregnant, if you have diabetes and are also taking aliskiren, or if you are allergic to valsartan or other ARBs. Tell your doctor if you have kidney disease, liver disease, heart failure, or renal artery stenosis. Tell your doctor about all medications — especially ACE inhibitors, aliskiren, potassium supplements, potassium-sparing diuretics, NSAIDs, and lithium. Avoid becoming dehydrated. Use effective contraception and contact your doctor immediately if you become pregnant.",
    },
    "carvedilol": {
        "description": "Carvedilol (Coreg) is a non-selective beta-adrenergic blocker with additional alpha-1 blocking activity, producing vasodilation in addition to reduced heart rate and contractility. It is available in immediate-release (Coreg) and extended-release (Coreg CR) formulations.",
        "uses": "Carvedilol is indicated for mild to severe chronic heart failure (reduced ejection fraction), left ventricular dysfunction following myocardial infarction (in clinically stable patients), and hypertension. It reduces mortality and hospitalization in heart failure patients.",
        "warnings": "Do not abruptly stop carvedilol — taper gradually to avoid rebound hypertension, angina, and myocardial infarction (especially in patients with coronary artery disease). Carvedilol can worsen heart failure during initiation — start at low doses and uptitrate slowly. Avoid in patients with decompensated heart failure requiring IV inotropes, severe bradycardia, second or third-degree AV block (without pacemaker), or severe hepatic impairment. Can mask hypoglycemic symptoms in diabetics. May worsen peripheral arterial disease and Raynaud's syndrome. Bronchospasm can occur in asthma or COPD patients.",
        "side_effects": "Common: dizziness, fatigue, hypotension, bradycardia, weight gain, diarrhea, and hyperglycemia. Serious: worsening heart failure, severe bradycardia, AV block, hepatotoxicity (rare but reported), and bronchospasm.",
        "dosage": "Heart failure: 3.125 mg twice daily with food for 2 weeks; double dose every 2 weeks as tolerated to 25 mg (≤85 kg) or 50 mg (>85 kg) twice daily. Post-MI LV dysfunction: 6.25 mg twice daily, titrated to 25 mg twice daily. Hypertension: 6.25 mg twice daily, maximum 25 mg twice daily. Take with food to slow absorption and reduce orthostatic hypotension.",
        "before_taking": "You should not take carvedilol if you have decompensated heart failure requiring intravenous heart medications, a slow heart rate (sick sinus syndrome, AV block without a pacemaker), or severe liver disease. Tell your doctor if you have asthma or COPD, diabetes (carvedilol masks hypoglycemia symptoms), peripheral artery disease, pheochromocytoma, thyroid disease, or myasthenia gravis. Do not stop carvedilol suddenly. Tell your doctor about all medications — especially other heart medications, diabetes drugs, CYP2D6 inhibitors (fluoxetine, paroxetine), and rifampin.",
    },
    "spironolactone": {
        "description": "Spironolactone (Aldactone) is a potassium-sparing diuretic and selective aldosterone receptor antagonist. It blocks the action of aldosterone in the distal nephron, reducing sodium retention and potassium excretion.",
        "uses": "Spironolactone is indicated for primary hyperaldosteronism (Conn syndrome), heart failure with reduced ejection fraction (to reduce mortality and hospitalization), hypertension, hypokalemia prevention with other diuretics, edema associated with cirrhosis, nephrotic syndrome, and congestive heart failure. It is also widely used off-label for acne vulgaris, female pattern hair loss, and polycystic ovary syndrome (anti-androgenic effects).",
        "warnings": "Spironolactone can cause life-threatening hyperkalemia — monitor serum potassium, especially with concurrent ACE inhibitors, ARBs, NSAIDs, or potassium supplements. Avoid in patients with severe renal impairment (eGFR <30). Spironolactone has antiandrogenic effects — gynecomastia and impotence in men; menstrual irregularities in women. Tumorigenic in rats at high doses (clinical significance uncertain). Use caution in patients with adrenal insufficiency or significant hepatic impairment.",
        "side_effects": "Common: hyperkalemia, gynecomastia (in men), breast tenderness, menstrual irregularities, dizziness, headache, nausea, and muscle cramps. Serious: severe hyperkalemia, hyponatremia, agranulocytosis (rare), and renal impairment.",
        "dosage": "Heart failure: 25 mg once daily; may increase to 50 mg once daily if tolerated and potassium remains <5.0 mEq/L. Hypertension: 25-100 mg once daily. Edema: 25-200 mg/day in single or divided doses. Primary hyperaldosteronism: 100-400 mg/day. Acne (off-label): 50-200 mg once daily. Take with food to improve absorption and minimize GI upset.",
        "before_taking": "You should not take spironolactone if you have Addison's disease, severe kidney disease (unable to make urine), or high potassium levels, or if you are taking eplerenone. Tell your doctor if you have kidney disease, liver disease, or heart disease. Tell your doctor about all medications — ACE inhibitors, ARBs, NSAIDs, potassium supplements, digoxin, and lithium all interact significantly. Spironolactone can cause birth defects (feminization of male fetuses) — use effective contraception. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "methylphenidate": {
        "description": "Methylphenidate (Ritalin, Concerta, Metadate, Quillichew) is a central nervous system (CNS) stimulant that blocks the reuptake of norepinephrine and dopamine into the presynaptic neuron, increasing their concentration in the synaptic cleft. It is a Schedule II controlled substance.",
        "uses": "Methylphenidate is indicated for attention-deficit hyperactivity disorder (ADHD) in children (age ≥6), adolescents, and adults, and for narcolepsy. It improves attention, focus, hyperactivity, and impulse control in ADHD. It is available in multiple formulations including immediate-release (Ritalin), sustained-release (Ritalin SR), and extended-release products (Concerta, Metadate CD, Quillichew ER, Jornay PM).",
        "warnings": "Methylphenidate has a high potential for abuse and dependence (Schedule II). Serious cardiovascular events including sudden death have been reported in patients with pre-existing structural cardiac abnormalities or other serious heart problems. Screen for cardiac disease before prescribing. Methylphenidate can increase blood pressure and heart rate — use caution in hypertension. New or worsening psychiatric symptoms (psychosis, mania, aggression, suicidal ideation) can emerge — monitor closely. May suppress growth in pediatric patients with long-term use — monitor height and weight. Contraindicated with MAOIs (within 14 days) and in patients with hypersensitivity to methylphenidate.",
        "side_effects": "Common: decreased appetite, weight loss, insomnia, headache, stomach upset, nausea, irritability, anxiety, and increased heart rate and blood pressure. Serious: cardiovascular events, psychiatric adverse effects (psychosis, mania), growth suppression in children, peripheral vasculopathy (including Raynaud's phenomenon), and priapism (rare).",
        "dosage": "ADHD (children 6-12): Ritalin IR 5 mg twice daily before breakfast and lunch; increase by 5-10 mg weekly; maximum 60 mg/day. Adolescents/adults: start low and titrate. Concerta (extended-release): 18 mg once daily in the morning; maximum 72 mg/day. Take the last dose before 6 PM to minimize insomnia. Concerta tablets must be swallowed whole.",
        "before_taking": "You should not take methylphenidate if you have taken an MAOI in the past 14 days, have glaucoma, marked anxiety or tension, motor tics or Tourette's syndrome, or are known to be hypersensitive to methylphenidate. Tell your doctor if you have heart disease, high blood pressure, heart defects, a family history of sudden death, a history of psychosis or bipolar disorder, substance use disorder, seizures, or thyroid disease. Inform all healthcare providers that you take methylphenidate — it interacts with blood pressure medications, antidepressants, blood thinners, and seizure medications. This medication is a controlled substance with abuse potential.",
    },
    "aripiprazole": {
        "description": "Aripiprazole (Abilify) is an atypical antipsychotic with a unique mechanism: partial agonism at D2 and D3 dopamine receptors and 5-HT1A serotonin receptors, and antagonism at 5-HT2A receptors. This partial agonism produces both dopamine stabilization (in hyperdopaminergic states) and agonism (in hypodopaminergic states).",
        "uses": "Aripiprazole is indicated for schizophrenia (adults and adolescents ≥13), bipolar I disorder (manic or mixed episodes, as monotherapy or adjunct to lithium or valproate; maintenance treatment), major depressive disorder (adjunctive therapy with antidepressants), irritability associated with autistic disorder (pediatric patients 6-17), and Tourette's disorder (pediatric 6-18). Injectable formulations (Abilify Maintena, Aristada) are approved for schizophrenia.",
        "warnings": "Elderly patients with dementia-related psychosis treated with antipsychotics are at increased risk of death (black box warning). Antidepressant use has increased suicidal thinking and behavior in short-term studies in pediatric patients (black box warning for adjunctive MDD use). Neuroleptic malignant syndrome (NMS) can be fatal — discontinue if suspected. Tardive dyskinesia (TD) — persistent, potentially irreversible involuntary movements. Metabolic changes including weight gain, dyslipidemia, and hyperglycemia. Orthostatic hypotension. Seizures. Leukopenia/neutropenia. Dysphagia. Pathological gambling and other compulsive behaviors have been reported.",
        "side_effects": "Common: weight gain, akathisia (restlessness), somnolence, nausea, constipation, insomnia, anxiety, headache, dizziness, and blurred vision. Serious: NMS, tardive dyskinesia, metabolic syndrome, orthostatic hypotension, seizures, and impulse-control disorders (compulsive gambling, binge eating, hypersexuality).",
        "dosage": "Schizophrenia (adults): 10-15 mg once daily; adjust to 10-30 mg/day. Bipolar I mania: 15 mg once daily; range 15-30 mg/day. MDD adjunct: 2-5 mg/day starting dose; range 2-15 mg/day. ASD irritability: 2 mg/day starting; range 5-15 mg/day. Can be taken with or without food. Reduce dose by 50% with CYP2D6 inhibitors (fluoxetine, paroxetine); reduce by 50% with CYP3A4 inhibitors (ketoconazole); double dose with CYP3A4 inducers (carbamazepine).",
        "before_taking": "You should not take aripiprazole if you are allergic to it. Tell your doctor if you have heart disease, low blood pressure, seizures, diabetes, high cholesterol, liver disease, or a personal or family history of diabetes. Tell your doctor about all medications — many drugs affect aripiprazole metabolism through CYP2D6 and CYP3A4 pathways. Avoid alcohol. Monitor for signs of tardive dyskinesia. If you notice unusual urges to gamble or other compulsive behaviors, contact your doctor immediately. Inform your doctor if you are pregnant, planning to become pregnant, or breastfeeding.",
    },
    "lithium": {
        "description": "Lithium carbonate (Lithobid, Eskalith) and lithium citrate are mood-stabilizing drugs whose precise mechanism of action in bipolar disorder is not fully understood. Proposed mechanisms include inhibition of inositol monophosphatase and GSK-3β, neuroprotective effects, and modulation of multiple neurotransmitter systems.",
        "uses": "Lithium is indicated for the treatment and prevention of manic episodes of bipolar disorder (manic-depressive illness), and for maintenance therapy to decrease the frequency and severity of manic episodes. It is also used off-label for bipolar depression, schizoaffective disorder, augmentation of antidepressant therapy in unipolar depression, and reduction of suicidal behavior.",
        "warnings": "Lithium has a narrow therapeutic index — toxicity can occur at levels close to therapeutic levels. Maintain serum lithium concentrations between 0.6-1.2 mEq/L (acute mania up to 1.5 mEq/L). Toxicity signs include tremor, ataxia, drowsiness, confusion, nausea, diarrhea, and cardiac arrhythmias — can be fatal. Dehydration, sodium restriction, and concurrent diuretic use (especially thiazides) dramatically increase lithium levels — extreme caution required. NSAIDs and ACE inhibitors/ARBs also raise lithium levels. Monitor renal function, thyroid function, and serum lithium levels regularly. Long-term use can cause nephrogenic diabetes insipidus and hypothyroidism. Teratogenic (Ebstein's anomaly) — Category D.",
        "side_effects": "Common: fine hand tremor, polyuria/polydipsia (nephrogenic DI), nausea, diarrhea, weight gain, cognitive blunting, acne, and hypothyroidism. Signs of toxicity (coarse tremor, ataxia, confusion, slurred speech, nausea/vomiting) require immediate evaluation. Serious: lithium toxicity (potentially fatal), nephrogenic diabetes insipidus, hypothyroidism, hypercalcemia, cardiac arrhythmias, and chronic kidney disease with long-term use.",
        "dosage": "Immediate-release: 300 mg three times daily, titrated to achieve therapeutic serum levels. Extended-release (Lithobid): 450-900 mg twice daily. Target serum levels: acute mania 0.8-1.2 mEq/L; maintenance 0.6-0.8 mEq/L. Draw trough level 12 hours after last dose. Check levels 5-7 days after dose changes and quarterly when stable. Take with food or milk. Maintain consistent sodium intake and adequate hydration.",
        "before_taking": "You should not take lithium if you have severe kidney disease, severe cardiovascular disease, severe dehydration, severe sodium depletion, or if you are hypersensitive to lithium. Tell your doctor if you have kidney disease, heart disease, thyroid disease, Parkinson's disease, or any condition requiring a low-sodium diet. Tell your doctor about all medications — NSAIDs, ACE inhibitors, ARBs, thiazide diuretics, metronidazole, and fluoxetine all increase lithium levels. Drink adequate fluids and maintain consistent salt intake. Avoid drastic changes in activity level or diet. Inform your doctor immediately if you develop diarrhea, vomiting, or excessive sweating (dehydration increases toxicity risk). Use effective contraception.",
    },
    "venlafaxine": {
        "description": "Venlafaxine (Effexor, Effexor XR) is a serotonin-norepinephrine reuptake inhibitor (SNRI) that inhibits the neuronal uptake of serotonin, norepinephrine, and (at high doses) dopamine. Available in immediate-release (Effexor) and extended-release (Effexor XR) formulations.",
        "uses": "Venlafaxine extended-release is FDA-approved for major depressive disorder (MDD), generalized anxiety disorder (GAD), social anxiety disorder (SAD/social phobia), and panic disorder. Venlafaxine immediate-release is approved for MDD only. Off-label uses include ADHD, fibromyalgia, hot flashes (menopausal), neuropathic pain, and migraine prevention.",
        "warnings": "Antidepressants increase the risk of suicidal thinking and behavior in children, adolescents, and young adults (black box warning) — monitor closely. Serotonin syndrome risk — especially when combined with other serotonergic drugs, MAOIs, triptans, fentanyl, or tramadol. Do not use within 14 days of MAOIs. Discontinuation syndrome is common and can be severe with venlafaxine — taper slowly (weeks to months). Venlafaxine can increase blood pressure (especially at higher doses ≥150 mg/day) and heart rate — monitor. Hyponatremia (SIADH) can occur. Activation of mania/hypomania in bipolar patients. Glaucoma (angle-closure). Bleeding risk with concurrent NSAIDs/anticoagulants.",
        "side_effects": "Common: nausea (especially early), headache, dizziness, insomnia, somnolence, dry mouth, constipation, sweating, increased blood pressure, sexual dysfunction (decreased libido, delayed orgasm, erectile dysfunction), and weight loss. Serious: suicidality, serotonin syndrome, hypertensive crisis, discontinuation syndrome, SIADH/hyponatremia, and bleeding.",
        "dosage": "MDD (XR): 75 mg once daily with food; may increase to 225 mg/day at ≥4-day intervals; maximum 375 mg/day (IR). GAD/SAD/Panic (XR): 75 mg once daily; may increase to 225 mg/day. Swallow XR capsules whole or open and sprinkle on applesauce (do not chew). Reduce dose by 50% with moderate hepatic impairment; reduce by 25-50% with renal impairment.",
        "before_taking": "You should not take venlafaxine if you have taken an MAOI in the past 14 days. Do not start an MAOI within 7 days of stopping venlafaxine. Tell your doctor if you have heart disease or high blood pressure (venlafaxine raises BP), glaucoma (angle-closure risk), bleeding problems, seizures, bipolar disorder, hyponatremia, liver or kidney disease. Tell your doctor about all medications — MAOIs, triptans, tramadol, fentanyl, lithium, and other serotonergic drugs increase serotonin syndrome risk. NSAIDs and anticoagulants increase bleeding risk. Do not stop venlafaxine suddenly — taper gradually. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "trazodone": {
        "description": "Trazodone (Desyrel, Oleptro) is a serotonin antagonist and reuptake inhibitor (SARI) antidepressant with additional alpha-1 adrenergic and histamine-1 receptor antagonism, which contributes to its sedative properties.",
        "uses": "Trazodone is FDA-approved for major depressive disorder. Due to its pronounced sedative effects, it is very widely used off-label for insomnia at low doses (25-100 mg), often preferred over benzodiazepines due to lower dependence potential. Other off-label uses include anxiety disorders and agitation associated with dementia.",
        "warnings": "Antidepressants increase the risk of suicidal thinking and behavior in children, adolescents, and young adults (black box warning). Priapism (prolonged, painful erection) has been associated with trazodone — can require surgical intervention; discontinue immediately and seek emergency care. Serotonin syndrome risk with concomitant serotonergic agents. Orthostatic hypotension and syncope are common, especially early in therapy — rise slowly from sitting/lying position. QT prolongation and cardiac arrhythmias. Not recommended during the acute recovery phase of myocardial infarction.",
        "side_effects": "Common: drowsiness/somnolence, dizziness, headache, dry mouth, nausea, blurred vision, constipation, and orthostatic hypotension. Serious: priapism (men), serotonin syndrome, QT prolongation and cardiac arrhythmias, and hyponatremia (SIADH).",
        "dosage": "Depression: 150 mg/day in divided doses after meals; increase by 50 mg every 3-7 days; maximum 600 mg/day (inpatients), 400 mg/day (outpatients). Insomnia (off-label): 25-100 mg at bedtime. Extended-release (Oleptro): 150 mg once daily at bedtime; maximum 375 mg/day. Take immediate-release with food to reduce dizziness. Do not crush/chew extended-release tablets.",
        "before_taking": "You should not take trazodone if you have recently had a heart attack or are hypersensitive to trazodone. Do not use with MAOIs or within 14 days of stopping an MAOI. Tell your doctor if you have heart disease, QT prolongation, low potassium or magnesium, liver or kidney disease, bipolar disorder, or a history of bleeding problems. Tell your doctor about all medications — linezolid, methylene blue, other serotonergic agents, and drugs that prolong QT interval interact. Men should seek emergency care for an erection lasting longer than 4 hours (priapism). Avoid alcohol. Rise slowly to prevent falls from dizziness/hypotension. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "amoxicillin": {
        "description": "Amoxicillin (Amoxil, Trimox) is a broad-spectrum aminopenicillin antibiotic that inhibits bacterial cell wall synthesis by binding to penicillin-binding proteins (PBPs). It is bactericidal and has activity against many gram-positive and some gram-negative organisms.",
        "uses": "Amoxicillin is indicated for mild to moderate infections caused by susceptible organisms: ear infections (otitis media), sinusitis, pharyngitis/tonsillitis (Group A strep), lower respiratory tract infections, skin infections, urinary tract infections (UTIs), and Helicobacter pylori eradication (as part of combination therapy with clarithromycin and a PPI). Amoxicillin-clavulanate (Augmentin) extends coverage to beta-lactamase-producing organisms.",
        "warnings": "Serious and occasionally fatal hypersensitivity (anaphylactic) reactions have been reported — cross-sensitivity with cephalosporins and carbapenems occurs in some patients. Amoxicillin causes a high rate of rash in patients with infectious mononucleosis (EBV) or lymphocytic leukemia — it is not a penicillin allergy. Clostridioides difficile-associated diarrhea (CDAD) has been reported. Superinfection with nonsusceptible organisms (Candida, resistant bacteria) may occur with prolonged use. Reduces oral contraceptive efficacy (use backup contraception).",
        "side_effects": "Common: diarrhea, nausea, rash, and vomiting. Serious: anaphylaxis/severe hypersensitivity, C. difficile colitis, Stevens-Johnson syndrome, and hepatotoxicity (with amoxicillin-clavulanate).",
        "dosage": "Adults (mild-moderate infection): Usual dose is 250 mg every 8 hours or 500 mg every 8 hours for more severe infections. Extended-release: 500-875 mg every 12 hours. H. pylori eradication: 1,000 mg twice daily with clarithromycin 500 mg and omeprazole 20 mg for 14 days. Children: 25-45 mg/kg/day in divided doses (higher doses 80-90 mg/kg/day for acute otitis media). Take with or without food. Complete the full prescribed course even if symptoms improve.",
        "before_taking": "You should not take amoxicillin if you have a documented allergy to penicillin antibiotics. Tell your doctor if you have a cephalosporin or carbapenem allergy, kidney disease, mononucleosis (you will develop a rash), phenylketonuria (PKU) — some formulations contain phenylalanine. Tell your doctor if you take oral contraceptives (use backup contraception), anticoagulants (warfarin — INR may increase), methotrexate, or probenecid. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "omeprazole": {
        "description": "Omeprazole (Prilosec, Prilosec OTC) is a proton pump inhibitor (PPI) that irreversibly inhibits H+/K+-ATPase (the proton pump) in gastric parietal cells, reducing both basal and stimulated gastric acid secretion by up to 97%.",
        "uses": "Omeprazole is indicated for gastroesophageal reflux disease (GERD), erosive esophagitis, Zollinger-Ellison syndrome, H. pylori eradication (in combination with antibiotics), prevention of NSAID-associated gastric ulcer in at-risk patients, and active duodenal and gastric ulcers. OTC formulation is indicated for frequent heartburn (two or more days per week).",
        "warnings": "Long-term PPI use (>1 year) is associated with hypomagnesemia, vitamin B12 deficiency, and increased fracture risk. C. difficile-associated diarrhea has been reported with PPI use. Acute interstitial nephritis (rare but serious). PPIs may reduce clopidogrel antiplatelet effectiveness (CYP2C19 interaction) — discuss with your doctor. Fundic gland polyps can develop with long-term use. Avoid use beyond 14 days OTC without medical supervision. PPIs should not be used for immediate symptom relief — onset of acid suppression takes 1-4 days.",
        "side_effects": "Common: headache, diarrhea, nausea, abdominal pain, constipation, and flatulence. Long-term use: hypomagnesemia (muscle spasms, irregular heartbeat), vitamin B12 deficiency, increased fracture risk (hip, wrist, spine). Serious: C. difficile colitis, acute interstitial nephritis, and severe hypomagnesemia.",
        "dosage": "GERD: 20 mg once daily for 4-8 weeks. Erosive esophagitis: 20-40 mg once daily for 4-8 weeks. Maintenance: 20 mg once daily. H. pylori: 20-40 mg twice daily with antibiotics for 10-14 days. OTC: 20 mg once daily for 14 days; may repeat after 4 months. Take 30-60 minutes before a meal. Swallow whole; may open delayed-release capsule and sprinkle on applesauce.",
        "before_taking": "You should not take omeprazole OTC for more than 14 days without consulting a doctor, or if you have difficulty swallowing or if you have blood in stool. Tell your doctor if you take clopidogrel, methotrexate, antiretroviral medications (rilpivirine), warfarin, or digoxin. Tell your doctor if you have liver disease, low magnesium, or osteoporosis. If you are taking OTC omeprazole and symptoms worsen or do not improve after 14 days, consult a doctor. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "aspirin": {
        "description": "Aspirin (acetylsalicylic acid, Bayer Aspirin, Ecotrin, Bufferin) is a nonsteroidal anti-inflammatory drug (NSAID) and antiplatelet agent that irreversibly inhibits cyclooxygenase (COX-1 and COX-2) enzymes, reducing production of prostaglandins and thromboxane A2.",
        "uses": "Aspirin is used for pain relief (headache, dental pain, menstrual cramps, muscle aches), fever reduction, and inflammation. Low-dose aspirin (81 mg) is widely used for secondary prevention of cardiovascular events (heart attack, stroke) in patients with established cardiovascular disease, and for primary prevention in selected high-risk patients as directed by a physician. Aspirin is also a component of antiplatelet regimens following coronary stent placement.",
        "warnings": "Aspirin increases the risk of serious gastrointestinal bleeding and ulceration — this risk increases with higher doses, concurrent NSAIDs, alcohol use, anticoagulants, or corticosteroids. Aspirin should not be given to children or teenagers with viral illness due to Reye's syndrome risk. Avoid aspirin within 7 days of certain surgical procedures. NSAIDs including aspirin can increase the risk of serious cardiovascular thrombotic events, including heart attack and stroke. Aspirin can cause serious allergic reactions including asthma and anaphylaxis in aspirin-sensitive individuals. Avoid in the third trimester of pregnancy.",
        "side_effects": "Common: upset stomach, heartburn, nausea, and easy bruising. Serious: gastrointestinal bleeding, peptic ulcer, severe allergic reaction (aspirin-exacerbated respiratory disease), tinnitus/hearing loss (with high doses), Reye's syndrome (in children), and hemorrhagic stroke.",
        "dosage": "Pain/fever: 325-650 mg every 4-6 hours as needed; maximum 4,000 mg/day. Cardiovascular prevention (low dose): 75-100 mg once daily (typically 81 mg). Take with food, milk, or a full glass of water to reduce GI upset. Enteric-coated formulations (Ecotrin) reduce stomach irritation. Chew 325 mg tablet immediately during suspected acute MI (do not use enteric-coated for this purpose).",
        "before_taking": "Do not give aspirin to children or teenagers who have a viral illness (chickenpox, flu) due to Reye's syndrome risk. You should not take aspirin if you have bleeding disorders, recent surgery, active ulcers, or severe kidney/liver disease. Tell your doctor if you take warfarin, other NSAIDs, corticosteroids, or antiplatelet drugs. Avoid aspirin in the third trimester of pregnancy. If you have aspirin-exacerbated respiratory disease (aspirin allergy with asthma/nasal polyps), avoid all NSAIDs. Tell your dentist and surgeon that you take aspirin before any procedure.",
    },
    "albuterol": {
        "description": "Albuterol (salbutamol, ProAir HFA, Ventolin HFA, Proventil HFA, AccuNeb) is a short-acting beta-2 adrenergic bronchodilator that relaxes smooth muscle in the airways by stimulating beta-2 receptors, causing bronchodilation within minutes.",
        "uses": "Albuterol inhaler (metered-dose inhaler and nebulizer solution) is indicated for the treatment or prevention of bronchospasm in patients aged ≥2 years with reversible obstructive airway disease (asthma, COPD), and for prevention of exercise-induced bronchospasm. It is considered a 'rescue inhaler' for acute asthma attacks and should not replace long-term controller medications (inhaled corticosteroids).",
        "warnings": "Albuterol can cause paradoxical bronchospasm — if this occurs, discontinue and use an alternative. Excessive use of rescue inhalers may indicate poorly controlled asthma requiring a step-up in therapy. Cardiovascular effects (increased heart rate, elevated blood pressure) can occur — use caution in patients with cardiovascular disease, hypertension, hyperthyroidism, or diabetes. Hypokalemia can occur with high doses. Do not use albuterol as a substitute for inhaled corticosteroids in persistent asthma — it treats symptoms, not inflammation. Check inhaler technique regularly.",
        "side_effects": "Common: tremor, nervousness, headache, tachycardia (rapid heart rate), palpitations, dizziness, throat irritation, cough, and hypokalemia. Serious: paradoxical bronchospasm, severe cardiovascular effects (in overdose), hypokalemia, and hypersensitivity reactions.",
        "dosage": "Adults and children ≥4 years (MDI): 1-2 inhalations (90 mcg/inhalation) every 4-6 hours as needed; 2 inhalations 15-30 minutes before exercise (for EIB). Nebulizer solution (2.5 mg/3 mL): one vial inhaled via nebulizer 3-4 times daily. Shake MDI well before use. Prime new inhalers or those unused for 2+ weeks.",
        "before_taking": "Tell your doctor if you have heart disease, high blood pressure, hyperthyroidism, diabetes, seizures, or if you are allergic to albuterol or other sympathomimetic drugs. Tell your doctor about all medications — beta-blockers (propranolol, atenolol) may reduce effectiveness; MAOIs and tricyclic antidepressants increase cardiovascular effects; diuretics worsen hypokalemia. Albuterol is generally safe during pregnancy. If your rescue inhaler is needed more than 2 days per week, your asthma may not be well-controlled — consult your doctor.",
    },
    "amlodipine": {
        "description": "Amlodipine (Norvasc) is a dihydropyridine calcium channel blocker (CCB) that inhibits the influx of calcium ions through L-type voltage-gated calcium channels in vascular smooth muscle and cardiac muscle, producing peripheral vasodilation and reduced cardiac afterload.",
        "uses": "Amlodipine is indicated for hypertension (alone or in combination with other antihypertensives) and for chronic stable angina and vasospastic (Prinzmetal's) angina. It is one of the most widely prescribed antihypertensives worldwide and is a first-line option in guidelines for hypertension treatment, particularly in Black patients and elderly patients.",
        "warnings": "Symptomatic hypotension, especially upon initiation, can occur in patients with severe aortic stenosis. Worsening angina and acute MI have been reported following dose initiation or increase — titrate slowly. Use caution in patients with severe hepatic impairment (amlodipine is extensively metabolized by the liver — start with 2.5 mg). Peripheral edema (ankle swelling) is a common dose-dependent adverse effect. Amlodipine does not require routine electrolyte monitoring unlike diuretics, making it convenient for long-term use.",
        "side_effects": "Common: peripheral edema (dose-dependent, most common side effect), flushing, headache, dizziness, fatigue, palpitations, and nausea. Serious: excessive hypotension, worsening angina, and rarely, liver enzyme elevation.",
        "dosage": "Hypertension/Angina: starting dose 5 mg once daily; may increase to 10 mg once daily after 7-14 days. Hepatic impairment: start with 2.5 mg once daily. Elderly patients: start with 2.5 mg once daily. May be taken with or without food at any time of day.",
        "before_taking": "Tell your doctor if you have severe aortic stenosis, heart failure, liver disease, or if you are allergic to amlodipine or other dihydropyridine calcium channel blockers. Tell your doctor about all medications — simvastatin dose should not exceed 20 mg/day with amlodipine (CYP3A4 interaction). Grapefruit juice can increase amlodipine levels — avoid large amounts. Do not stop amlodipine abruptly if used for angina. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "ciprofloxacin": {
        "description": "Ciprofloxacin (Cipro, Cipro XR) is a broad-spectrum fluoroquinolone antibiotic that inhibits bacterial DNA gyrase (topoisomerase II) and topoisomerase IV, enzymes essential for bacterial DNA replication, repair, and transcription.",
        "uses": "Ciprofloxacin is indicated for urinary tract infections (complicated and uncomplicated), acute uncomplicated pyelonephritis, lower respiratory tract infections (including pneumonia in hospitalized patients), skin and soft tissue infections, bone and joint infections, intra-abdominal infections (with metronidazole), infectious diarrhea, typhoid fever, anthrax prophylaxis, and gonorrhea (limited use due to resistance). It provides excellent activity against gram-negative bacteria including Pseudomonas aeruginosa.",
        "warnings": "Fluoroquinolones including ciprofloxacin are associated with disabling and potentially irreversible serious adverse reactions that may occur together: tendinitis and tendon rupture (Achilles tendon most common), peripheral neuropathy, and central nervous system effects (black box warning). Exacerbation of myasthenia gravis can be life-threatening. Aortic aneurysm dissection/rupture has been reported. QT prolongation risk. Avoid in children <18 years for most indications (affects developing cartilage). Reserve ciprofloxacin for infections where no adequate alternative exists. C. difficile diarrhea has been reported. Sun/UV photosensitivity.",
        "side_effects": "Common: nausea, diarrhea, abdominal discomfort, vomiting, headache, and rash. Serious: tendinitis/tendon rupture (especially in elderly, those on corticosteroids, kidney/heart/lung transplant recipients), peripheral neuropathy, CNS effects (seizures, anxiety, psychosis), QT prolongation, C. difficile colitis, photosensitivity, and severe hypersensitivity reactions.",
        "dosage": "UTI (uncomplicated, IR): 250 mg twice daily for 3 days. Complicated UTI/pyelonephritis (IR): 500 mg twice daily for 7-14 days. Respiratory/skin infections: 500-750 mg twice daily. XR formulation: 500-1000 mg once daily for UTI/pyelonephritis. Take 2 hours before or 6 hours after antacids, dairy, or iron supplements (reduces absorption). Complete the full course.",
        "before_taking": "You should not take ciprofloxacin if you have a history of tendon problems with fluoroquinolones, myasthenia gravis, or are hypersensitive to ciprofloxacin or other fluoroquinolones. Avoid in children under 18 (except for anthrax/plague). Tell your doctor if you have kidney disease, seizures, QT prolongation, a history of aortic aneurysm, or are on corticosteroids. Avoid antacids, dairy products, calcium supplements, and iron within 2 hours before or 6 hours after taking ciprofloxacin. Avoid excessive sun exposure. Inform your doctor immediately if you experience tendon pain or swelling, numbness or tingling, or mental/mood changes. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "diazepam": {
        "description": "Diazepam (Valium) is a long-acting benzodiazepine that potentiates the effect of gamma-aminobutyric acid (GABA) at the GABA-A receptor by binding to the benzodiazepine site, increasing the frequency of chloride channel opening. It has anxiolytic, anticonvulsant, muscle-relaxant, sedative, and amnestic properties. It is a Schedule IV controlled substance.",
        "uses": "Diazepam is indicated for anxiety disorders (short-term relief of anxiety symptoms), acute alcohol withdrawal (delirium tremens, tremor, impending acute delirium tremens), muscle spasm (as adjunct therapy), status epilepticus and severe recurrent convulsive seizures (injectable/rectal formulations), and preoperative sedation/anxiety.",
        "warnings": "Diazepam carries black box warnings: concomitant use with opioids can result in profound sedation, respiratory depression, coma, and death (black box warning); and physical dependence and addiction can develop (Schedule IV). Abrupt discontinuation after prolonged use can cause severe withdrawal (seizures, psychosis, death) — taper gradually. Tolerance develops with continued use, limiting long-term efficacy for anxiety. Elderly patients are at increased risk of falls, sedation, and cognitive impairment (see Beers Criteria). Avoid in patients with sleep apnea, severe hepatic disease, or acute angle-closure glaucoma.",
        "side_effects": "Common: drowsiness, fatigue, muscle weakness, ataxia, memory impairment, and confusion. Serious: respiratory depression (especially with opioids or alcohol), paradoxical reactions (excitement, agitation), dependence/addiction, withdrawal seizures, and falls in the elderly.",
        "dosage": "Anxiety: 2-10 mg 2-4 times daily. Alcohol withdrawal: 10 mg 3-4 times daily initially, reducing to 5 mg 3-4 times daily. Muscle spasm: 2-10 mg 3-4 times daily. Use the lowest effective dose for the shortest duration. Extended use beyond 4 weeks is generally not recommended for anxiety.",
        "before_taking": "You should not take diazepam if you have severe respiratory insufficiency, severe hepatic insufficiency, myasthenia gravis, sleep apnea, or acute angle-closure glaucoma. Do not take diazepam with opioid medications without very close medical supervision. Tell your doctor about all medications — especially opioids, alcohol, antihistamines, antidepressants, antipsychotics, and other CNS depressants. Diazepam is habit-forming — take only as directed. Do not stop diazepam suddenly after regular use. Avoid alcohol completely. Do not drive or operate machinery until you know how diazepam affects you. Diazepam is Category D in pregnancy — avoid if possible. Not recommended during breastfeeding.",
    },
    "gabapentin": {
        "description": "Gabapentin (Neurontin, Gralise, Horizant) is an anticonvulsant and analgesic that structurally resembles GABA but does not bind to GABA receptors; instead it binds to the alpha-2-delta subunit of voltage-gated calcium channels in the CNS, reducing excitatory neurotransmitter release.",
        "uses": "Gabapentin (Neurontin) is FDA-approved for postherpetic neuralgia (PHN) and as adjunctive therapy for partial-onset seizures (with or without secondary generalization) in patients ≥3 years. Horizant (extended-release) is approved for restless legs syndrome (RLS) and PHN. Gralise is approved for PHN. Gabapentin is widely used off-label for neuropathic pain, fibromyalgia, hot flashes, anxiety, and adjunct pain management.",
        "warnings": "Gabapentin has additive CNS depressant effects when combined with opioids, benzodiazepines, alcohol, or other CNS depressants, potentially causing respiratory depression and death. Multiple states have classified gabapentin as a controlled substance due to abuse potential (not federally scheduled). Suicidal ideation/behavior has been reported with antiepileptic drugs. Gabapentin can cause somnolence, dizziness, and ataxia that impair driving/machinery operation. Respiratory depression can occur in patients with respiratory disease or with CNS depressants. Require dose adjustment in renal impairment. Abrupt withdrawal can precipitate seizures.",
        "side_effects": "Common: dizziness, somnolence, ataxia, fatigue, nystagmus, tremor, weight gain, peripheral edema, and dry mouth. Serious: respiratory depression (with CNS depressants), suicidal ideation, Stevens-Johnson syndrome (rare), and hypersensitivity reactions (DRESS).",
        "dosage": "PHN (Neurontin): 300 mg on Day 1, 300 mg twice daily on Day 2, 300 mg three times daily on Day 3; titrate to 1,800-3,600 mg/day in 3 divided doses. Epilepsy adjunct (adults): 300-1,200 mg three times daily; maximum 3,600 mg/day. RLS (Horizant): 600 mg once daily at 5 PM. Dose reduction required for renal impairment (CrCl-based). Take with or without food.",
        "before_taking": "Tell your doctor if you have kidney disease (dose reduction required), respiratory disease, a history of depression or suicidal thoughts, or substance use disorder. Tell your doctor if you take opioid pain medications, benzodiazepines, sleep aids, or alcohol — combined use markedly increases the risk of respiratory depression. Do not stop gabapentin suddenly if used for seizures. Gabapentin can cause dizziness and drowsiness — avoid driving until you know how it affects you. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "metoprolol": {
        "description": "Metoprolol is a selective beta-1 adrenergic receptor blocker available as metoprolol succinate (Toprol-XL, extended-release) and metoprolol tartrate (Lopressor, immediate-release). It reduces heart rate, blood pressure, and cardiac output.",
        "uses": "Metoprolol tartrate (Lopressor) is indicated for hypertension, stable angina, and acute myocardial infarction. Metoprolol succinate (Toprol-XL) is indicated for hypertension, stable angina, and heart failure with reduced ejection fraction (to reduce mortality and hospitalization). Beta-blockers are first-line therapy for many cardiac conditions and are commonly used for rate control in atrial fibrillation.",
        "warnings": "Do not abruptly stop metoprolol — taper over 1-2 weeks to avoid rebound hypertension, angina exacerbation, and myocardial infarction risk, especially in patients with coronary artery disease. Metoprolol may mask hypoglycemic tachycardia in diabetics. Can worsen peripheral arterial disease. May cause or worsen heart block in susceptible patients. Bronchospasm can occur in asthmatics/COPD patients even with selective beta-1 agents at higher doses. Use caution in patients with pheochromocytoma (alpha-blockade first), myasthenia gravis, and hepatic impairment.",
        "side_effects": "Common: fatigue, dizziness, bradycardia, hypotension, shortness of breath, depression, decreased exercise tolerance, cold extremities, and erectile dysfunction. Serious: severe bradycardia/heart block, bronchospasm, worsening heart failure during uptitration, and hypoglycemia masking.",
        "dosage": "Hypertension/Angina (tartrate IR): 100-450 mg/day in divided doses. Hypertension (succinate XL): 25-200 mg once daily. Heart failure (succinate XL): 12.5-25 mg once daily, titrate to target dose of 200 mg/day. Take tartrate with or without food; take succinate extended-release with or without food, swallow whole.",
        "before_taking": "You should not take metoprolol if you have sick sinus syndrome, second or third-degree AV block (without pacemaker), decompensated heart failure requiring IV therapy, or severe bradycardia. Do not stop metoprolol suddenly. Tell your doctor if you have asthma or COPD, diabetes (masks hypoglycemia), peripheral artery disease, pheochromocytoma, or myasthenia gravis. Tell your doctor about all medications — especially other heart/blood pressure medications, antidepressants, clonidine, and alpha-blockers. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "simvastatin": {
        "description": "Simvastatin (Zocor) is an HMG-CoA reductase inhibitor (statin) that competitively inhibits 3-hydroxy-3-methylglutaryl-coenzyme A reductase, the rate-limiting enzyme in cholesterol biosynthesis in the liver, reducing LDL-cholesterol, total cholesterol, and triglycerides.",
        "uses": "Simvastatin is indicated to reduce the risk of cardiovascular events (MI, stroke, revascularization) in patients with established cardiovascular disease or high risk. It is also indicated to reduce elevated LDL-C, total cholesterol, and triglycerides, and to increase HDL-C in patients with primary hyperlipidemia or mixed dyslipidemia. It is used in children ≥10 years with heterozygous familial hypercholesterolemia.",
        "warnings": "Myopathy and rhabdomyolysis are dose-related — the 80 mg dose is restricted to patients already on it for 12+ months without evidence of myopathy (FDA restriction since 2011). The 80 mg dose should not be prescribed to new patients. Simvastatin has more drug interactions than other statins due to extensive CYP3A4 metabolism — strong CYP3A4 inhibitors (itraconazole, ketoconazole, erythromycin, clarithromycin, HIV protease inhibitors, gemfibrozil, niacin ≥1g/day, cyclosporine, amlodipine ≥10 mg) increase myopathy risk significantly. Simvastatin is contraindicated in pregnancy (Category X). Liver enzyme elevations can occur — evaluate if signs of liver disease develop.",
        "side_effects": "Common: headache, abdominal pain, nausea, constipation, and myalgia (muscle aches). Serious: myopathy and rhabdomyolysis (dose-dependent, more common at 80 mg), liver enzyme elevations, and new-onset diabetes.",
        "dosage": "Starting dose: 10-20 mg once daily in the evening. High-risk patients: 40 mg once daily. Maximum: 40 mg once daily (80 mg only for established patients). Take in the evening — HMG-CoA reductase activity peaks at night. Drug interaction limits: 10 mg/day with amlodipine or ranolazine; 20 mg/day with amiodarone, verapamil, or diltiazem.",
        "before_taking": "You should not take simvastatin if you are pregnant, breastfeeding, or planning to become pregnant (use effective contraception), if you have active liver disease, or if you take strong CYP3A4 inhibitors listed above. Tell your doctor if you have kidney disease, thyroid disease, diabetes, or a personal or family history of muscle disease. Tell your doctor about all medications, supplements, and grapefruit juice consumption. Stop simvastatin and contact your doctor immediately if you have unexplained muscle pain, tenderness, or weakness (especially with fever or dark urine). Inform your doctor if you are pregnant.",
    },
    "fluoxetine": {
        "description": "Fluoxetine (Prozac, Sarafem, Selfemra) is a selective serotonin reuptake inhibitor (SSRI) — the first SSRI approved in the United States (1987). It has a uniquely long half-life (~1-6 days for fluoxetine; ~4-16 days for active metabolite norfluoxetine), making it the most forgiving SSRI regarding missed doses and allowing once-weekly dosing for maintenance.",
        "uses": "Fluoxetine is FDA-approved for major depressive disorder (MDD; adults and pediatric patients ≥8 years), obsessive-compulsive disorder (OCD; adults and pediatric patients ≥7 years), bulimia nervosa, panic disorder, and bipolar I depression (as combination therapy with olanzapine — Symbyax). It is also used off-label for premenstrual dysphoric disorder (PMDD), PTSD, social anxiety disorder, and generalized anxiety disorder.",
        "warnings": "Antidepressants increase the risk of suicidal thinking and behavior in children, adolescents, and young adults in short-term studies (black box warning) — monitor closely during first few weeks. Serotonin syndrome risk with concomitant serotonergic drugs, MAOIs, linezolid, methylene blue. Do not use within 14 days of MAOIs; wait 5 weeks after stopping fluoxetine before starting MAOIs (due to long half-life). Fluoxetine is a potent CYP2D6 inhibitor — elevates levels of many drugs including tricyclics, antipsychotics, and tamoxifen. Activation of mania/hypomania. QT prolongation. Hyponatremia (SIADH). Bleeding risk with NSAIDs/anticoagulants. Angle-closure glaucoma.",
        "side_effects": "Common: nausea (especially early), headache, insomnia, drowsiness, dry mouth, diarrhea, decreased appetite, sweating, tremor, and sexual dysfunction (decreased libido, delayed orgasm). Serious: serotonin syndrome, suicidality, hyponatremia, severe allergic reactions, pulmonary reactions, and QT prolongation.",
        "dosage": "MDD/OCD (adults): 20 mg once daily in the morning; may increase to 40-60 mg/day after 4 weeks. MDD (pediatric, ≥8 years): 10-20 mg/day. Bulimia nervosa: 60 mg once daily in the morning. Panic disorder: 10 mg/day initially; target 20-60 mg/day. Weekly dosing (Prozac Weekly): 90 mg capsule once weekly, starting 7 days after last daily 20 mg dose. Take in the morning to minimize insomnia.",
        "before_taking": "You should not take fluoxetine if you have taken an MAOI in the past 14 days, or are taking thioridazine or pimozide. Do not start an MAOI within 5 weeks of stopping fluoxetine. Tell your doctor if you have bipolar disorder, seizures, diabetes (can affect blood sugar), liver disease, narrow-angle glaucoma, bleeding problems, or hyponatremia. Tell your doctor about ALL medications — fluoxetine is a potent CYP2D6 inhibitor that significantly raises levels of many drugs. Tamoxifen efficacy may be reduced — discuss with your oncologist. Do not stop fluoxetine suddenly without talking to your doctor. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "gabapentin": {
        "description": "Gabapentin (Neurontin, Gralise, Horizant) is an anticonvulsant and analgesic that structurally resembles GABA but does not bind to GABA receptors; instead it binds to the alpha-2-delta subunit of voltage-gated calcium channels in the CNS, reducing excitatory neurotransmitter release.",
        "uses": "Gabapentin (Neurontin) is FDA-approved for postherpetic neuralgia (PHN) and as adjunctive therapy for partial-onset seizures (with or without secondary generalization) in patients ≥3 years. Horizant (extended-release) is approved for restless legs syndrome (RLS) and PHN. Gralise is approved for PHN. Gabapentin is widely used off-label for neuropathic pain, fibromyalgia, hot flashes, anxiety, and adjunct pain management.",
        "warnings": "Gabapentin has additive CNS depressant effects when combined with opioids, benzodiazepines, alcohol, or other CNS depressants, potentially causing respiratory depression and death. Multiple states have classified gabapentin as a controlled substance due to abuse potential (not federally scheduled). Suicidal ideation/behavior has been reported with antiepileptic drugs. Gabapentin can cause somnolence, dizziness, and ataxia that impair driving/machinery operation. Respiratory depression can occur in patients with respiratory disease or with CNS depressants. Requires dose adjustment in renal impairment. Abrupt withdrawal can precipitate seizures.",
        "side_effects": "Common: dizziness, somnolence, ataxia, fatigue, nystagmus, tremor, weight gain, peripheral edema, and dry mouth. Serious: respiratory depression (with CNS depressants), suicidal ideation, Stevens-Johnson syndrome (rare), and hypersensitivity reactions (DRESS).",
        "dosage": "PHN (Neurontin): 300 mg on Day 1, 300 mg twice daily on Day 2, 300 mg three times daily on Day 3; titrate to 1,800-3,600 mg/day in 3 divided doses. Epilepsy adjunct (adults): 300-1,200 mg three times daily; maximum 3,600 mg/day. RLS (Horizant): 600 mg once daily at 5 PM. Dose reduction required for renal impairment (CrCl-based). Take with or without food.",
        "before_taking": "Tell your doctor if you have kidney disease (dose reduction required), respiratory disease, a history of depression or suicidal thoughts, or substance use disorder. Tell your doctor if you take opioid pain medications, benzodiazepines, sleep aids, or alcohol — combined use markedly increases the risk of respiratory depression. Do not stop gabapentin suddenly if used for seizures. Gabapentin can cause dizziness and drowsiness — avoid driving until you know how it affects you. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "pregabalin": {
        "description": "Pregabalin (Lyrica, Lyrica CR) is an anticonvulsant and neuropathic pain agent that binds to the alpha-2-delta subunit of voltage-gated calcium channels, similar to gabapentin but with greater potency and more predictable absorption. It is a Schedule V controlled substance.",
        "uses": "Pregabalin is FDA-approved for neuropathic pain associated with diabetic peripheral neuropathy, postherpetic neuralgia, fibromyalgia, neuropathic pain associated with spinal cord injury, and as adjunct therapy for partial-onset seizures in patients ≥1 month. It is also approved for generalized anxiety disorder in Europe.",
        "warnings": "Pregabalin (Schedule V) has abuse potential — some patients develop euphoria and physical dependence. CNS depression (dizziness, somnolence) is dose-dependent — avoid driving/machinery until effects are known. Additive CNS/respiratory depression with opioids, benzodiazepines, and alcohol. Suicidal ideation risk (antiepileptic class warning). Peripheral edema, weight gain, and blurred vision are common. Angioedema (swelling of face, mouth, neck — potentially life-threatening) and hypersensitivity reactions. May cause creatine kinase elevation and myopathy. Reduce dose with renal impairment.",
        "side_effects": "Common: dizziness, somnolence, weight gain, peripheral edema, blurred vision, dry mouth, and concentration difficulties. Serious: angioedema, respiratory depression (with CNS depressants), suicidal ideation, myopathy, thrombocytopenia, and PR interval prolongation.",
        "dosage": "Diabetic neuropathy: 50-100 mg 3 times daily (start 50 mg TID); maximum 300 mg/day. PHN: 75-150 mg twice daily or 50-100 mg three times daily; maximum 300-600 mg/day. Fibromyalgia: 75 mg twice daily initially; maximum 225 mg twice daily (450 mg/day). Seizures (adjunct): 150-600 mg/day in 2-3 divided doses. Reduce dose proportionally to creatine clearance in renal impairment. Discontinue gradually over at least 1 week.",
        "before_taking": "You should not take pregabalin if you are allergic to it. Tell your doctor if you have heart failure or fluid retention, kidney disease, a history of drug or alcohol abuse, depression or suicidal thoughts, or a bleeding disorder. Tell your doctor if you take opioids, benzodiazepines, alcohol, or other CNS depressants (respiratory depression risk). Tell your doctor if you take ACE inhibitors (edema risk) or thiazolidinediones (weight gain and edema). Do not stop pregabalin suddenly — taper gradually. Pregabalin is a controlled substance (Schedule V). Inform your doctor if you are pregnant or breastfeeding.",
    },
    "warfarin": {
        "description": "Warfarin (Coumadin, Jantoven) is a vitamin K antagonist oral anticoagulant that inhibits the hepatic synthesis of vitamin K-dependent clotting factors (II, VII, IX, X) and anticoagulant proteins C and S. It requires regular INR monitoring due to its narrow therapeutic index and numerous drug and food interactions.",
        "uses": "Warfarin is indicated for the treatment and prophylaxis of venous thromboembolism (DVT and pulmonary embolism), atrial fibrillation (to prevent systemic embolism, including stroke), prosthetic heart valve thromboembolism prophylaxis, and secondary prevention of systemic embolism after myocardial infarction.",
        "warnings": "The most serious risk of warfarin is hemorrhage (black box warning) — bleeding can occur at any site. Monitor INR regularly — target range is typically 2.0-3.0 (higher for mechanical heart valves). Many drugs, foods (especially vitamin K-rich vegetables like leafy greens, kale, spinach), and health conditions significantly alter INR. Skin necrosis (protein C/S deficiency) can occur early in therapy. Warfarin is highly teratogenic (fetal warfarin syndrome, spontaneous abortion) — contraindicated in pregnancy except for mechanical heart valves. Purple toe syndrome has been reported. VKORC1 and CYP2C9 genetic variants significantly affect warfarin dosing.",
        "side_effects": "Common: minor bleeding (bruising, nosebleeds, gum bleeding), and INR fluctuations. Serious: major hemorrhage (intracranial, GI, retroperitoneal), skin necrosis, purple toe syndrome, and hypersensitivity reactions.",
        "dosage": "Starting dose varies by individual; typical 2-5 mg/day with INR monitoring. Adjust dose based on INR results. Target INR 2.0-3.0 for most indications; 2.5-3.5 for mechanical prosthetic heart valves. Allow 2-3 days between dose changes before re-checking INR. Take at the same time each day — often in the late afternoon/evening.",
        "before_taking": "You should not take warfarin if you are pregnant (except mechanical heart valves), have active bleeding, recent surgery of the CNS or eye, subacute bacterial endocarditis, or poor adherence to medical follow-up. Tell your doctor about ALL medications including OTC drugs, vitamins, and herbal supplements — hundreds of drugs interact with warfarin. Maintain a consistent intake of vitamin K-containing foods (green leafy vegetables) — do not eliminate them, just be consistent. Avoid alcohol (increases bleeding risk and alters INR). Tell your dentist and surgeon that you take warfarin before any procedure. Carry a medical alert card.",
    },
    "tramadol": {
        "description": "Tramadol (Ultram, Ultram ER, ConZip) is a centrally acting synthetic opioid analgesic with a dual mechanism: weak mu-opioid receptor agonism and inhibition of serotonin and norepinephrine reuptake (SNRI activity). It is a Schedule IV controlled substance.",
        "uses": "Tramadol is indicated for the management of pain severe enough to require an opioid analgesic and for which alternative treatments are inadequate. Extended-release formulations are for around-the-clock management of moderate to severe chronic pain in opioid-tolerant patients.",
        "warnings": "Tramadol has multiple serious black box warnings: addiction, abuse, and misuse (Schedule IV); life-threatening respiratory depression; neonatal opioid withdrawal syndrome; interaction with CNS depressants (especially benzodiazepines) causing profound sedation, respiratory depression, coma, and death; and serotonin syndrome when combined with other serotonergic drugs. Tramadol lowers the seizure threshold — risk increases with dose, in patients with epilepsy, or with concomitant medications that lower seizure threshold. Contraindicated in patients <12 years old, and in patients <18 years old following tonsillectomy/adenoidectomy. CYP2D6 ultra-rapid metabolizers face life-threatening serotonin syndrome or overdose. Avoid tramadol with MAOIs (risk of fatal serotonin syndrome).",
        "side_effects": "Common: nausea, constipation, dizziness, headache, somnolence, vomiting, and pruritus. Serious: respiratory depression, serotonin syndrome (especially with SSRIs, SNRIs, MAOIs, triptans), seizures, anaphylaxis, dependence and addiction.",
        "dosage": "Adults: 50-100 mg every 4-6 hours as needed; maximum 400 mg/day (300 mg/day in elderly ≥75). Extended-release (ER): 100-300 mg once daily (opioid-tolerant patients). Start at lowest effective dose. Avoid in patients with hepatic impairment (reduce frequency) or severe renal impairment (CrCl <30: 50-100 mg every 12 hours; max 200 mg/day). Swallow ER tablets/capsules whole.",
        "before_taking": "You should not take tramadol if you have taken an MAOI in the past 14 days, have severe respiratory depression, acute or severe bronchial asthma, or gastrointestinal obstruction. Do not give tramadol to children under 12, or to children/adolescents under 18 after certain surgeries. Tell your doctor if you have a seizure disorder, head injury, liver or kidney disease, depression or mental illness, or a personal/family history of substance use disorder. Tell your doctor about ALL medications — SSRIs, SNRIs, MAOIs, tricyclics, and triptans all increase serotonin syndrome risk. Avoid alcohol and other CNS depressants. Do not stop tramadol suddenly — taper to avoid withdrawal. This is a controlled substance.",
    },
    "levofloxacin": {
        "description": "Levofloxacin (Levaquin) is a broad-spectrum fluoroquinolone antibiotic that inhibits bacterial DNA gyrase (topoisomerase II) and topoisomerase IV, with activity against gram-positive organisms (including Streptococcus pneumoniae), gram-negative organisms (including Pseudomonas aeruginosa), and atypical pathogens (Legionella, Mycoplasma, Chlamydia).",
        "uses": "Levofloxacin is indicated for community-acquired pneumonia (including drug-resistant S. pneumoniae), nosocomial pneumonia, acute bacterial exacerbation of chronic bronchitis, acute bacterial sinusitis, complicated and uncomplicated skin/soft tissue infections, complicated and uncomplicated urinary tract infections (UTIs), acute pyelonephritis, and inhalational anthrax (post-exposure prophylaxis and treatment). It is also used for plague and tuberculosis (as second-line therapy).",
        "warnings": "Fluoroquinolones including levofloxacin carry black box warnings for disabling and potentially irreversible adverse reactions: tendinitis and tendon rupture (Achilles tendon most common, especially in patients ≥60 years, on corticosteroids, or organ transplant recipients), peripheral neuropathy (potentially irreversible), and CNS effects. Worsening of myasthenia gravis (potentially life-threatening, avoid if possible). Aortic aneurysm dissection/rupture has been reported. QT prolongation and torsades de pointes. C. difficile diarrhea. Blood glucose disturbances in diabetics. Photosensitivity. Reserve for infections where no adequate alternative exists.",
        "side_effects": "Common: nausea, diarrhea, headache, insomnia, constipation, and dizziness. Serious: tendinitis/tendon rupture, peripheral neuropathy, CNS effects (seizures, psychosis, tremors), QT prolongation, C. difficile colitis, severe hypersensitivity reactions, photosensitivity, and hypoglycemia/hyperglycemia.",
        "dosage": "CAP (mild-moderate): 500 mg once daily for 7-14 days, or 750 mg once daily for 5 days. Nosocomial pneumonia: 750 mg once daily for 7-14 days. UTI (uncomplicated): 250 mg once daily for 3 days. Complicated UTI/pyelonephritis: 250 mg once daily for 10 days, or 750 mg once daily for 5 days. Sinusitis: 500 mg once daily for 10-14 days, or 750 mg once daily for 5 days. Take 2 hours before or 2 hours after antacids, dairy, or iron supplements. Dose reduction required for renal impairment.",
        "before_taking": "You should not take levofloxacin if you have a history of serious adverse reactions to fluoroquinolones (tendon rupture, neuropathy, CNS effects), myasthenia gravis, or are hypersensitive to levofloxacin or other fluoroquinolones. Tell your doctor if you are ≥60 years, on corticosteroids, have had a kidney, heart, or lung transplant (all increase tendon rupture risk). Tell your doctor if you have kidney disease, seizure disorder, QT prolongation, hypokalemia, or diabetes. Avoid antacids, dairy, and iron supplements near dose time. Avoid excessive sun exposure. Stop levofloxacin and contact your doctor immediately if you develop tendon pain, weakness, numbness, tingling, or mental/mood changes. This antibiotic is reserved for serious infections — reserve for situations where safer alternatives are not appropriate.",
    },
    "levothyroxine": {
        "description": "Levothyroxine (Synthroid, Levoxyl, Tirosint, Unithroid) is a synthetic form of thyroxine (T4), the primary hormone secreted by the thyroid gland. It is converted peripherally to the active form triiodothyronine (T3).",
        "uses": "Levothyroxine is the treatment of choice for hypothyroidism (primary, secondary, tertiary, and subclinical). It is also used as a TSH-suppressive therapy in the management of thyroid cancer (post-thyroidectomy), thyroid goiter, and thyroid nodules. Levothyroxine is essential for normal growth and development, metabolism, protein synthesis, and cardiovascular function.",
        "warnings": "Levothyroxine is not a treatment for obesity or weight loss — doses within the range of daily hormonal requirements are ineffective for weight loss; larger doses carry serious cardiac and other risks (black box warning). Use caution in patients with cardiovascular disease — start at lower doses (12.5-25 mcg) in elderly patients and those with coronary artery disease; levothyroxine can precipitate angina, arrhythmias, and MI in susceptible individuals. Close monitoring of TSH is required with dose changes. Over-replacement (TSH suppression) increases risk of osteoporosis and atrial fibrillation. Under-replacement leads to persistent hypothyroid symptoms. Many drugs affect levothyroxine absorption — take on an empty stomach.",
        "side_effects": "At therapeutic doses: generally well tolerated when TSH is in normal range. Signs of over-replacement (too much): palpitations, tachycardia, heat intolerance, sweating, weight loss, insomnia, anxiety, diarrhea, tremors. Signs of under-replacement (too little): fatigue, weight gain, cold intolerance, dry skin, constipation, depression, bradycardia.",
        "dosage": "Adults (full replacement): 1.6 mcg/kg/day (IBW) once daily. Elderly or cardiac patients: start 12.5-25 mcg/day, increase by 12.5-25 mcg every 4-6 weeks. Recheck TSH 4-8 weeks after any dose change; annual monitoring when stable. Take on an empty stomach 30-60 minutes before breakfast; consistently at the same time each day. Many formulations (Synthroid, Levoxyl, Tirosint) are NOT bioequivalent — do not switch brands without physician guidance.",
        "before_taking": "Tell your doctor about all medications — many reduce levothyroxine absorption: calcium supplements, iron, antacids, bile acid sequestrants (cholestyramine), omeprazole/PPIs, sucralfate, and soy products should be taken 4 hours apart from levothyroxine. Certain drugs increase levothyroxine metabolism (phenytoin, rifampin, carbamazepine). Tell your doctor if you have heart disease, adrenal insufficiency (treat with corticosteroids before levothyroxine), diabetes (may change insulin/OHA requirements), or osteoporosis. Inform your doctor if you are pregnant — dose requirements increase early in pregnancy; do not stop levothyroxine during pregnancy.",
        "interactions_text": "Levothyroxine interacts with many drugs that affect its absorption, metabolism, or thyroid hormone levels. Absorption-reducing agents should be taken at least 4 hours apart from levothyroxine: calcium carbonate, ferrous sulfate, cholestyramine (Questran), colestipol, colesevelam, sucralfate, aluminum and magnesium hydroxide antacids, sevelamer, lanthanum carbonate, and proton pump inhibitors (omeprazole, lansoprazole).\n\nDrugs that increase levothyroxine clearance (may require dose increase): phenytoin, carbamazepine, rifampin, phenobarbital, and ritonavir stimulate hepatic metabolism. Estrogen-containing oral contraceptives and hormone replacement therapy increase thyroxine-binding globulin (TBG), which may increase total T4 requirements in hypothyroid patients on replacement therapy.\n\nDrugs that decrease TSH or affect thyroid hormone levels: glucocorticoids, dopamine, and octreotide may reduce TSH secretion. Amiodarone contains large amounts of iodine and can cause hypothyroidism or hyperthyroidism — thyroid function requires close monitoring. Lithium inhibits thyroid hormone synthesis and release. Tyrosine kinase inhibitors (sunitinib, sorafenib) and immunotherapy agents can cause thyroiditis.\n\nEffect of levothyroxine on other drugs: levothyroxine may enhance the anticoagulant effect of warfarin — monitor INR closely when starting, stopping, or changing levothyroxine doses. Levothyroxine may increase the sensitivity to tricyclic antidepressants. Levothyroxine may affect insulin or oral hypoglycemic requirements in diabetic patients — monitor blood glucose.",
    },
    "alprazolam": {
        "description": "Alprazolam (Xanax, Xanax XR, Niravam) is a short-acting triazolobenzodiazepine that potentiates GABA-A receptor activity, producing anxiolytic, sedative, muscle-relaxant, and anticonvulsant effects. It is a Schedule IV controlled substance.",
        "uses": "Alprazolam is FDA-approved for generalized anxiety disorder (GAD) and panic disorder (with or without agoraphobia). It is one of the most prescribed psychotropic medications in the United States. Despite its widespread use, guidelines generally recommend short-term use only due to dependence and tolerance development.",
        "warnings": "Black box warnings: concomitant use with opioids (including cough products) can result in profound sedation, respiratory depression, coma, and death; physical dependence and addiction can occur with regular use (Schedule IV). Abrupt discontinuation after prolonged use can cause severe withdrawal syndrome including seizures, psychosis, and rebound anxiety — can be life-threatening; always taper gradually. Alprazolam has a short half-life (~11 hours) compared to longer-acting benzodiazepines, making interdose withdrawal and dependence more likely. Tolerance to anxiolytic effects can develop within weeks. Avoid in patients with sleep apnea, severe hepatic disease, glaucoma, or significant respiratory depression. Elderly patients are at increased risk of falls, sedation, and cognitive impairment.",
        "side_effects": "Common: sedation, dizziness, impaired coordination, memory impairment, slurred speech, and paradoxical reactions (agitation, irritability — more common in elderly). Serious: respiratory depression (especially with opioids/alcohol), dependence and withdrawal syndrome (including seizures), rebound anxiety, and cognitive impairment with long-term use.",
        "dosage": "Anxiety: 0.25-0.5 mg three times daily; maximum 4 mg/day. Panic disorder: 0.5 mg three times daily, titrated to 1-10 mg/day (average 5-6 mg/day). Use lowest effective dose for shortest duration. Extended-release (Xanax XR): 0.5-1 mg once daily at bedtime, titrate to 3-6 mg/day for panic disorder. Reduce dose by 50% in hepatic impairment.",
        "before_taking": "You should not take alprazolam if you have narrow-angle glaucoma, severe respiratory insufficiency, sleep apnea, severe hepatic insufficiency, or are concurrently taking itraconazole or ketoconazole (strong CYP3A4 inhibitors). Do not take alprazolam with opioids unless under very close medical supervision. Tell your doctor if you have a history of substance abuse, depression, bipolar disorder, or kidney/liver disease. Avoid alcohol entirely. Do not stop alprazolam suddenly — taper gradually to avoid withdrawal seizures and rebound anxiety. Do not drive or operate machinery until you know how alprazolam affects you. This is a controlled substance (Schedule IV). Inform your doctor if you are pregnant or breastfeeding.",
    },
    "oxycodone": {
        "description": "Oxycodone (OxyContin, Roxicodone, Percocet when combined with acetaminophen) is a semisynthetic opioid analgesic derived from thebaine, acting primarily on mu-opioid receptors in the CNS and peripheral tissues. It is a Schedule II controlled substance with high potential for abuse and dependence.",
        "uses": "Oxycodone is indicated for the management of pain severe enough to require an opioid analgesic and for which alternative treatments are inadequate. Extended-release oxycodone (OxyContin) is reserved for around-the-clock management of severe chronic pain in opioid-tolerant patients only — it is NOT intended for as-needed (PRN) pain management.",
        "warnings": "Black box warnings: addiction, abuse, misuse; life-threatening respiratory depression; accidental ingestion (even one dose can be fatal in non-opioid-tolerant persons, especially children); neonatal opioid withdrawal syndrome; interaction with benzodiazepines and other CNS depressants (profound sedation, respiratory depression, coma, death); and cytochrome P450 interactions (CYP3A4 inhibitors increase oxycodone levels). OxyContin 60 mg, 80 mg, and 160 mg tablets are for opioid-tolerant patients only. Never crush, cut, or dissolve extended-release tablets — releases entire dose at once, potentially fatal. REMS program required for prescribers.",
        "side_effects": "Common: constipation, nausea, somnolence, dizziness, vomiting, headache, dry mouth, sweating, and pruritus. Serious: respiratory depression, cardiovascular effects (hypotension, bradycardia), serotonin syndrome (with serotonergic drugs), adrenal insufficiency, severe constipation/bowel obstruction, and overdose.",
        "dosage": "Immediate-release (Roxicodone): 5-15 mg every 4-6 hours as needed for opioid-naïve patients. OxyContin (ER): opioid-naïve patients: 10 mg every 12 hours. Titrate dose based on pain control and tolerability. Reduce dose by 50% in hepatic or renal impairment. Take ER tablets whole with water — do not crush, chew, or dissolve.",
        "before_taking": "You should not take oxycodone if you have significant respiratory depression, acute or severe bronchial asthma, gastrointestinal obstruction, or hypersensitivity to oxycodone. Do not give OxyContin to children under 11 years or to opioid non-tolerant patients. Tell your doctor if you have head injury, liver or kidney disease, seizures, adrenal gland problems, prostate or urinary problems, Addison's disease, thyroid disease, or a personal/family history of substance use disorder. Tell your doctor about ALL medications — benzodiazepines and CNS depressants are especially dangerous combined with opioids. Store oxycodone securely and away from others. Dispose of unused opioids properly. This is a Schedule II controlled substance.",
    },
    "zolpidem": {
        "description": "Zolpidem (Ambien, Ambien CR, Edluar, Intermezzo, Zolpimist) is a non-benzodiazepine hypnotic of the imidazopyridine class used for the short-term treatment of insomnia. It acts selectively on GABA-A receptors containing the α1 subunit to produce sedation.",
        "uses": "Zolpidem is indicated for the short-term treatment of insomnia characterized by difficulties with sleep initiation (immediate-release) or sleep maintenance (extended-release Ambien CR). Intermezzo sublingual tablets are indicated for middle-of-the-night awakening when at least 4 hours of sleep time remain.",
        "warnings": "FDA BOXED WARNING: Complex sleep behaviors including sleep-walking, sleep-driving, and other activities while not fully awake have been reported with zolpidem; some resulted in serious injuries and death. Discontinue immediately if a complex sleep behavior occurs. Zolpidem is a Schedule IV controlled substance with abuse and dependence potential. Use the lowest effective dose. Risk of next-morning impairment is high — do not drive or operate machinery the morning after use. CNS depression is additive with alcohol and other CNS depressants. Respiratory depression can occur in patients with compromised respiratory function. Avoid in patients with severe hepatic impairment. Anaphylaxis and angioedema have been reported after the first dose.",
        "side_effects": "Common: drowsiness, dizziness, diarrhea, drugged feeling, headache. Serious: complex sleep behaviors (sleep-walking, sleep-driving, sleep-cooking — may occur even with no prior history), anterograde amnesia, hallucinations, depression and suicidal thoughts, next-morning impairment, respiratory depression, anaphylaxis.",
        "dosage": "Immediate-release (Ambien): Women: 5 mg at bedtime; Men: 5-10 mg at bedtime. Extended-release (Ambien CR): Women: 6.25 mg; Men: 6.25-12.5 mg at bedtime. Intermezzo: 1.75 mg (women) or 3.5 mg (men) sublingually for middle-of-the-night awakening. Take only when you have 7-8 hours (IR) or at least 4 hours (Intermezzo) remaining before planned awakening. Use the lowest effective dose. Do not take with or right after a meal.",
        "before_taking": "You should not take zolpidem if you have ever had a complex sleep behavior (sleep-walking, sleep-driving, etc.) after taking a sleep medicine. Tell your doctor if you have liver disease, kidney disease, myasthenia gravis, sleep apnea or other breathing problems, depression, or a history of mental illness, suicidal thoughts, or drug or alcohol abuse. Do not combine with alcohol, opioids, benzodiazepines, or other CNS depressants. Women and older adults are more sensitive to zolpidem effects; use the lowest effective dose. Do not drive the morning after taking zolpidem. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "sildenafil": {
        "description": "Sildenafil (Viagra for erectile dysfunction; Revatio for pulmonary arterial hypertension) is a phosphodiesterase type 5 (PDE5) inhibitor. It enhances smooth muscle relaxation and vasodilation by increasing cyclic GMP levels in vascular smooth muscle.",
        "uses": "Sildenafil (Viagra) is indicated for the treatment of erectile dysfunction (ED) in adult men. Sildenafil (Revatio) is indicated for the treatment of pulmonary arterial hypertension (WHO Group I) to improve exercise ability and delay clinical worsening.",
        "warnings": "Sildenafil is CONTRAINDICATED with nitrates in any form (nitroglycerin, isosorbide mononitrate/dinitrate) because the combination can cause a severe, potentially fatal drop in blood pressure. Also contraindicated with riociguat (Adempas) and with guanylate cyclase stimulators. Use with caution in patients with cardiovascular disease, anatomical deformity of the penis, conditions predisposing to priapism (sickle cell anemia, multiple myeloma, leukemia), or bleeding disorders. Sudden vision loss (NAION — non-arteritic anterior ischemic optic neuropathy) and sudden hearing loss have been reported. Hypotension may occur, especially when combined with alpha-blockers or antihypertensives.",
        "side_effects": "Common: headache, flushing, indigestion, nasal congestion, dizziness, back pain, myalgia, abnormal vision (color tinge, blurred vision, increased light sensitivity). Serious: priapism (painful erection lasting more than 4 hours — seek emergency care immediately), sudden vision loss, sudden hearing loss, severe hypotension (especially with nitrates), Stevens-Johnson syndrome.",
        "dosage": "Erectile dysfunction (Viagra): 50 mg taken as needed approximately 1 hour before sexual activity; range 25-100 mg; maximum once daily. Lower starting dose (25 mg) recommended in patients over 65, with hepatic impairment, severe renal impairment, or on CYP3A4 inhibitors (e.g., ritonavir, ketoconazole). Pulmonary arterial hypertension (Revatio): 5 mg or 20 mg three times daily, approximately 4-6 hours apart.",
        "before_taking": "You should not take sildenafil if you take nitrates for chest pain or heart problems (including nitroglycerin, isosorbide mononitrate, isosorbide dinitrate), riociguat, or if you are allergic to sildenafil. Tell your doctor if you have heart disease, low or high blood pressure, heart failure, stroke, liver or kidney disease, a bleeding disorder, stomach ulcers, retinitis pigmentosa, a history of priapism, Peyronie's disease, or sickle cell disease. Tell your doctor about all medications, especially alpha-blockers (tamsulosin, doxazosin), antifungals, HIV medications, and other ED medications. Alcohol increases the risk of side effects.",
    },
    "tadalafil": {
        "description": "Tadalafil (Cialis for erectile dysfunction and benign prostatic hyperplasia; Adcirca for pulmonary arterial hypertension) is a long-acting PDE5 inhibitor with a half-life of approximately 17.5 hours, allowing once-daily dosing.",
        "uses": "Tadalafil (Cialis) is indicated for erectile dysfunction (ED) and for the signs and symptoms of benign prostatic hyperplasia (BPH). It may be used in patients with both ED and BPH. Tadalafil (Adcirca) is indicated for pulmonary arterial hypertension.",
        "warnings": "CONTRAINDICATED with nitrates and guanylate cyclase stimulators (riociguat) due to risk of severe hypotension. Use caution in patients with cardiovascular disease or on antihypertensives/alpha-blockers. Sudden vision loss (NAION) and sudden hearing loss have been reported. Priapism (prolonged erection >4 hours) has been reported — seek immediate medical care.",
        "side_effects": "Common: headache, dyspepsia, back pain, myalgia, flushing, nasal congestion, limb pain. Serious: priapism, sudden vision loss (NAION), sudden hearing loss, severe hypotension with nitrates.",
        "dosage": "ED (as needed): 10 mg prior to sexual activity; range 5-20 mg; maximum once per day. ED (once daily): 2.5 mg once daily; may increase to 5 mg. BPH: 5 mg once daily. Pulmonary arterial hypertension (Adcirca): 40 mg once daily. Dose adjustment needed for renal or hepatic impairment and for CYP3A4 inhibitors.",
        "before_taking": "Contraindicated with nitrates and riociguat. Tell your doctor if you have cardiovascular disease, hypotension, liver or kidney disease, stroke history, bleeding disorders, retinitis pigmentosa, or priapism history. Not recommended for patients with severe hepatic impairment. Alcohol and grapefruit juice may increase side effects.",
    },
    "cetirizine": {
        "description": "Cetirizine (Zyrtec) is a second-generation antihistamine (H1 receptor antagonist) that is minimally sedating. It is available OTC as 5 mg and 10 mg tablets, 5 mg/5 mL syrup, and 10 mg chewable tablets.",
        "uses": "Cetirizine is indicated for the relief of symptoms associated with seasonal allergic rhinitis (hay fever), perennial allergic rhinitis, and chronic idiopathic urticaria (hives) in adults and children ≥2 years of age. It relieves sneezing, runny nose, itchy/watery eyes, and nasal/throat itching.",
        "warnings": "Use with caution in patients with renal or hepatic impairment (dose reduction may be needed). Although less sedating than older antihistamines, cetirizine may still cause drowsiness in some patients — use caution when driving or operating heavy machinery. Avoid alcohol and other CNS depressants. May cause urinary retention in patients with prostate hypertrophy or bladder obstruction.",
        "side_effects": "Common: somnolence (drowsiness), dry mouth, fatigue, headache, dizziness, pharyngitis, nausea, abdominal pain. Less common: urinary retention (especially in elderly men), palpitations. Allergic reactions including anaphylaxis have rarely been reported.",
        "dosage": "Adults and children ≥6 years: 5-10 mg once daily. Children 2-5 years: 2.5 mg once daily (may increase to 2.5 mg twice daily). Children 6-23 months: 2.5 mg once daily (by prescription). Patients with renal impairment (CrCl 11-31 mL/min) or on dialysis: 5 mg once daily. OTC use: one 10 mg tablet daily; do not exceed this dose.",
        "before_taking": "Tell your doctor if you have kidney or liver disease, or problems urinating due to an enlarged prostate or bladder problems. Cetirizine can cause drowsiness; avoid alcohol and other sedating medications. Cetirizine is considered safe in pregnancy (Category B) and limited amounts pass into breast milk. Ask your healthcare provider before use if pregnant or breastfeeding.",
    },
    "loratadine": {
        "description": "Loratadine (Claritin, Alavert) is a second-generation, non-sedating antihistamine (H1 receptor antagonist) available OTC as 10 mg tablets, 5 mg chewable tablets, and 5 mg/5 mL syrup.",
        "uses": "Loratadine is indicated for the relief of nasal and non-nasal symptoms of seasonal and perennial allergic rhinitis (hay fever), and for the treatment of chronic idiopathic urticaria (hives) in adults and children ≥2 years.",
        "warnings": "Loratadine is generally non-sedating at recommended doses but may rarely cause drowsiness. Use with caution in patients with hepatic impairment or renal impairment (dose interval adjustment recommended). Avoid alcohol.",
        "side_effects": "Common: headache, somnolence (less common than older antihistamines), dry mouth, fatigue, nervousness (in children), abdominal pain. At recommended doses, loratadine is generally non-sedating.",
        "dosage": "Adults and children ≥6 years: 10 mg once daily. Children 2-5 years: 5 mg once daily. Patients with hepatic failure or GFR <30 mL/min: 10 mg every other day. Take with or without food.",
        "before_taking": "Tell your doctor if you have liver or kidney disease. Loratadine is considered safe in pregnancy (Category B). It is excreted in breast milk; consult your doctor before use if breastfeeding. No significant interactions with alcohol at recommended doses, but caution is still advised.",
    },
    "diphenhydramine": {
        "description": "Diphenhydramine (Benadryl, ZzzQuil, Unisom) is a first-generation H1 antihistamine with significant anticholinergic and sedative properties. Available OTC as 25 mg and 50 mg tablets, capsules, liquid, and topical formulations.",
        "uses": "Diphenhydramine is used for allergic reactions (allergic rhinitis, urticaria, anaphylaxis adjunct), motion sickness, nausea, vomiting, nighttime sleep aid, and mild Parkinson's symptoms. Topical formulations are used for itch relief from minor skin irritations.",
        "warnings": "Diphenhydramine causes significant sedation and MUST NOT be used while driving or operating machinery. It has potent anticholinergic effects (dry mouth, urinary retention, constipation, blurred vision, confusion) — avoid in elderly patients (Beers Criteria potentially inappropriate medication), patients with glaucoma, urinary retention, benign prostatic hyperplasia, or dementia. Do not use with other CNS depressants or alcohol. Do not use in children under 2 years — risk of fatal respiratory depression. Tolerance to sedative effects develops; not recommended for long-term sleep use.",
        "side_effects": "Common: sedation/drowsiness (prominent), dry mouth, urinary retention, constipation, blurred vision, confusion (especially in elderly), thickening of bronchial secretions, dizziness, paradoxical excitability in children.",
        "dosage": "Allergic reactions: 25-50 mg every 4-6 hours; maximum 300 mg/day. Sleep aid: 50 mg at bedtime (25 mg for elderly). Motion sickness: 25-50 mg 30 minutes before travel, then every 4-6 hours. Children 6-11 years: 12.5-25 mg every 4-6 hours; maximum 150 mg/day.",
        "before_taking": "Do not give to children under 2 years. Avoid in elderly patients, patients with glaucoma, enlarged prostate, urinary obstruction, dementia, COPD, asthma, or sleep apnea. Do not combine with alcohol, sedatives, tranquilizers, or other antihistamines. Diphenhydramine is not recommended for long-term or nightly use as a sleep aid.",
    },
    "ondansetron": {
        "description": "Ondansetron (Zofran) is a selective 5-HT3 receptor antagonist (serotonin antagonist) antiemetic available as oral tablets (4 mg, 8 mg), orally disintegrating tablets (ODT), and IV/IM injection.",
        "uses": "Ondansetron is indicated for the prevention of nausea and vomiting associated with highly and moderately emetogenic cancer chemotherapy, radiation therapy, and post-operative nausea and vomiting (PONV). It is widely used off-label for nausea/vomiting due to gastroenteritis and pregnancy (hyperemesis gravidarum).",
        "warnings": "Ondansetron can cause QT interval prolongation and dose-dependent increases in PR and QRS intervals — avoid in patients with congenital long QT syndrome, electrolyte abnormalities (hypokalemia, hypomagnesemia), or on drugs known to prolong QT. Serotonin syndrome has been reported, particularly when combined with other serotonergic drugs. Avoid use in patients with known hypersensitivity to ondansetron. A 32 mg single IV dose is no longer recommended due to QT prolongation risk. May mask signs of bowel obstruction — use with caution in patients with intestinal obstruction.",
        "side_effects": "Common: headache, constipation, diarrhea, dizziness, fatigue, injection-site reactions. Serious: QT prolongation and torsades de pointes, serotonin syndrome, anaphylaxis/hypersensitivity reactions.",
        "dosage": "Chemotherapy-induced N/V: 8 mg PO 30 minutes before chemotherapy, then 8 mg 8 hours later, then 8 mg every 12 hours for 1-2 days; or 24 mg IV 30 minutes prior to highly emetogenic chemotherapy. PONV prevention: 4 mg IV or 16 mg PO 1 hour before anesthesia. Gastroenteritis (off-label): 4-8 mg PO or IV as single dose.",
        "before_taking": "Tell your doctor if you have QT prolongation or other heart rhythm problems, electrolyte imbalances, liver disease, or phenylketonuria (ODT tablets contain phenylalanine). Tell your doctor about all medications, especially other serotonergic drugs (SSRIs, triptans, tramadol), antiarrhythmics, or drugs known to prolong QT interval. Ondansetron is generally considered safe in pregnancy for nausea and vomiting.",
    },
    "apixaban": {
        "description": "Apixaban (Eliquis) is an oral direct factor Xa inhibitor anticoagulant. It is available as 2.5 mg and 5 mg tablets and does not require routine INR monitoring.",
        "uses": "Apixaban is indicated for reduction of risk of stroke and systemic embolism in non-valvular atrial fibrillation; treatment of deep vein thrombosis (DVT) and pulmonary embolism (PE); reduction in the risk of recurrent DVT and PE; and prophylaxis of DVT following hip or knee replacement surgery.",
        "warnings": "FDA BOXED WARNING: Premature discontinuation of apixaban increases the risk of thrombotic events. There is also a risk of epidural or spinal hematoma with neuraxial anesthesia or spinal puncture, which may result in long-term or permanent paralysis — monitor patients frequently for signs and symptoms of neurological impairment. Apixaban is not recommended in patients with severe renal impairment (CrCl <15 mL/min) or on dialysis. Use with caution in patients with hepatic impairment. No approved reversal agent was available for many years; andexanet alfa (Andexxa) is now FDA-approved for reversal of apixaban anticoagulation in life-threatening bleeding.",
        "side_effects": "Common: hemorrhage (bleeding at any site), nausea, anemia. Serious: major hemorrhage including intracranial hemorrhage, GI bleeding, epidural/spinal hematoma with neuraxial procedures.",
        "dosage": "Atrial fibrillation: 5 mg twice daily (2.5 mg twice daily if 2 of 3 criteria present: age ≥80, weight ≤60 kg, serum creatinine ≥1.5 mg/dL). DVT/PE treatment: 10 mg twice daily for 7 days, then 5 mg twice daily. DVT/PE recurrence prophylaxis: 2.5 mg twice daily after at least 6 months of treatment. Post-surgical prophylaxis (hip/knee): 2.5 mg twice daily starting 12-24 hours post-surgery.",
        "before_taking": "Do not take apixaban if you are allergic to it or have active pathological bleeding. Tell your doctor about all medications — many drugs interact with apixaban including aspirin, NSAIDs, other anticoagulants, antiplatelet agents, antifungals (ketoconazole, itraconazole), HIV protease inhibitors, rifampin, and carbamazepine. Tell your doctor if you have kidney or liver disease, recent surgery or trauma, or if you are pregnant or breastfeeding (not recommended). Do not stop taking apixaban without consulting your doctor.",
    },
    "rivaroxaban": {
        "description": "Rivaroxaban (Xarelto) is an oral direct factor Xa inhibitor anticoagulant available as 2.5, 10, 15, and 20 mg tablets and 1 mg/mL granules for oral suspension.",
        "uses": "Rivaroxaban is indicated for reduction of stroke and systemic embolism risk in non-valvular atrial fibrillation; treatment and prevention of recurrence of DVT and PE; prophylaxis of DVT after hip or knee replacement surgery; reduction of major cardiovascular events in patients with chronic CAD or PAD (with aspirin); and reduction of risk of major thrombotic vascular events in patients with acute or history of ACS or PAD.",
        "warnings": "FDA BOXED WARNING: Premature discontinuation increases the risk of thrombotic events. Risk of epidural/spinal hematoma with neuraxial anesthesia. Rivaroxaban with combined P-gp and strong CYP3A4 inhibitors (e.g., ketoconazole, ritonavir) or inducers (rifampin) should be avoided. Not recommended in patients with CrCl <15 mL/min.",
        "side_effects": "Common: bleeding (any site), back pain, wound secretion, pain in extremity, muscle spasm, nausea. Serious: major hemorrhage (GI, intracranial), epidural/spinal hematoma.",
        "dosage": "Atrial fibrillation: 20 mg once daily with evening meal (15 mg once daily for CrCl 15-50 mL/min). DVT/PE treatment: 15 mg twice daily with food for 21 days, then 20 mg once daily with food. DVT/PE recurrence prophylaxis: 10 mg once daily. Post-surgical prophylaxis: 10 mg once daily. CAD/PAD (with aspirin 75-100 mg): 2.5 mg twice daily.",
        "before_taking": "Contraindicated with active pathological bleeding and severe hypersensitivity. Tell your doctor about all medications — P-gp and CYP3A4 inhibitors/inducers significantly affect rivaroxaban levels. Avoid in pregnancy; use effective contraception. Not recommended during breastfeeding. Do not discontinue without consulting your doctor.",
    },
    "atenolol": {
        "description": "Atenolol (Tenormin) is a selective beta-1 adrenergic blocker (cardioselective beta blocker) available as 25, 50, and 100 mg tablets. Unlike non-selective beta blockers, atenolol has minimal effect on beta-2 receptors at therapeutic doses.",
        "uses": "Atenolol is indicated for hypertension (high blood pressure), angina pectoris (chest pain), and management of hemodynamically stable patients with definite or suspected acute myocardial infarction. It is also used off-label for rate control in atrial fibrillation, prevention of migraines, and management of heart failure (though metoprolol succinate or carvedilol are preferred for heart failure).",
        "warnings": "Do not abruptly discontinue atenolol — rapid withdrawal may worsen angina and precipitate myocardial infarction; taper over 1-2 weeks. Use with extreme caution in patients with reactive airway disease (asthma, COPD); although cardioselective at low doses, selectivity is lost at higher doses. Atenolol may mask signs of hypoglycemia in diabetics. Use caution in peripheral vascular disease, Raynaud's phenomenon, pheochromocytoma (pre-treat with alpha-blocker), and thyrotoxicosis (may mask symptoms). Dose reduction required in renal impairment (CrCl <35 mL/min).",
        "side_effects": "Common: bradycardia, fatigue, dizziness, cold extremities, hypotension, nausea, diarrhea. Serious: bronchospasm (particularly in asthmatic patients), rebound angina or MI with abrupt withdrawal, heart block, worsening heart failure.",
        "dosage": "Hypertension: 50 mg once daily; may increase to 100 mg once daily after 1-2 weeks. Angina: 50 mg once daily; may increase to 100 mg once daily or 200 mg once daily. Post-MI: 50 mg twice daily for 6-9 days or until discharge, then 100 mg once daily for at least 1 year. Renal impairment: CrCl 15-35 mL/min: maximum 50 mg/day; CrCl <15 mL/min: maximum 25 mg/day.",
        "before_taking": "Do not use if you have a slow heart rate, heart block greater than first degree (without pacemaker), uncontrolled heart failure, or cardiogenic shock. Tell your doctor about asthma, COPD, peripheral artery disease, diabetes, kidney disease, thyroid disorders, pheochromocytoma, or Raynaud's phenomenon. Do not stop taking atenolol abruptly. Tell your surgeon and anesthesiologist before any surgery.",
    },
    "propranolol": {
        "description": "Propranolol (Inderal, Inderal LA, InnoPran XL) is a non-selective beta-adrenergic blocker that blocks both beta-1 (cardiac) and beta-2 (pulmonary/vascular) receptors. Available as immediate-release (10, 20, 40, 60, 80 mg) and extended-release capsules.",
        "uses": "Propranolol is indicated for hypertension, angina pectoris, reduction of cardiovascular mortality after MI, atrial fibrillation (rate control), essential tremor, prevention of migraine headaches, hypertrophic obstructive cardiomyopathy (HOCM), pheochromocytoma (adjunctive), and certain cardiac arrhythmias.",
        "warnings": "Do not abruptly discontinue — may cause rebound angina or myocardial infarction, especially in patients with ischemic heart disease; taper over 1-2 weeks. Non-selective beta blockade causes bronchospasm — AVOID in asthma or COPD. May mask symptoms of hypoglycemia in diabetics. Propranolol is extensively metabolized by CYP2D6; significant drug interactions with CYP2D6 inhibitors (fluoxetine, paroxetine). Avoid in decompensated heart failure, cardiogenic shock, bradycardia, or AV block greater than first degree without pacemaker.",
        "side_effects": "Common: fatigue, bradycardia, cold extremities, hypotension, dizziness, nausea, vivid dreams/nightmares (due to CNS penetration). Serious: bronchospasm, rebound angina/MI on abrupt withdrawal, severe hypoglycemia masking, worsening heart failure, AV block.",
        "dosage": "Hypertension: IR 40-80 mg twice daily up to 640 mg/day. ER: 80 mg once daily up to 640 mg/day. Angina: IR 80-320 mg/day in 2-4 doses. Essential tremor: 40 mg twice daily up to 320 mg/day. Migraine prevention: 80-240 mg/day in divided doses. Post-MI: 180-240 mg/day in 3-4 divided doses. Pheochromocytoma: 60 mg/day in divided doses (after alpha-blocker initiated).",
        "before_taking": "Contraindicated with asthma or reactive airway disease, cardiogenic shock, sinus bradycardia, AV block >1st degree without pacemaker, and decompensated heart failure. Tell your doctor about COPD, diabetes, thyroid disease, kidney or liver disease, Raynaud's phenomenon, or peripheral artery disease. Never stop propranolol abruptly. Inform your anesthesiologist before surgery.",
    },
    "montelukast": {
        "description": "Montelukast (Singulair) is a leukotriene receptor antagonist (LTRA) available as 10 mg film-coated tablets, 5 mg chewable tablets, and 4 mg chewable tablets or granules for children.",
        "uses": "Montelukast is indicated for the prophylaxis and chronic treatment of asthma in adults and pediatric patients ≥1 year of age, for prevention of exercise-induced bronchoconstriction (EIB) in patients ≥6 years, and for relief of symptoms of seasonal and perennial allergic rhinitis.",
        "warnings": "FDA BOXED WARNING: Serious neuropsychiatric events including agitation, aggressive behavior, anxiety, depression, dream abnormalities and hallucinations, insomnia, irritability, restlessness, suicidal thinking and behavior, and tremor have been reported. Prescribers should weigh the risks and benefits; discontinue if neuropsychiatric events occur. Montelukast is not a bronchodilator and should NOT be used to treat acute asthma attacks — patients should have appropriate rescue bronchodilators available. Do not substitute for inhaled corticosteroids; do not abruptly discontinue corticosteroids.",
        "side_effects": "Common: headache, upper respiratory tract infection, fever, abdominal pain, cough, diarrhea, otitis media, influenza, rhinorrhea. Serious: neuropsychiatric events (suicidality, depression, aggression, hallucinations), eosinophilic granulomatosis with polyangiitis (Churg-Strauss), anaphylaxis, angioedema, Stevens-Johnson syndrome.",
        "dosage": "Asthma (adults ≥15 years) and allergic rhinitis: 10 mg once daily in the evening. Asthma (6-14 years): 5 mg chewable tablet once daily in the evening. Asthma (2-5 years): 4 mg chewable tablet or granules once daily in the evening. Asthma (12-23 months): 4 mg oral granules once daily. Exercise-induced bronchoconstriction: 10 mg (adults) at least 2 hours before exercise (do not take additional dose within 24 hours).",
        "before_taking": "Tell your doctor if you have a history of depression, behavioral problems, or other mental health conditions — montelukast carries a boxed warning for serious neuropsychiatric events. Montelukast is not indicated for acute asthma attacks; always carry rescue inhaler (short-acting beta agonist). Tell your doctor if you are pregnant or breastfeeding. Aspirin-sensitive patients should avoid aspirin and NSAIDs while taking montelukast.",
    },
    "fluticasone": {
        "description": "Fluticasone propionate (Flonase Allergy Relief — OTC; Flovent for asthma) and fluticasone furoate (Flonase Sensimist, Arnuity Ellipta) are inhaled and intranasal corticosteroids with potent anti-inflammatory activity.",
        "uses": "Fluticasone nasal spray (Flonase) is indicated for management of nasal symptoms of seasonal and perennial allergic and non-allergic rhinitis in adults and children ≥2 years. Fluticasone inhaler (Flovent) is indicated for maintenance treatment of asthma as prophylactic therapy.",
        "warnings": "Inhaled and intranasal corticosteroids may cause HPA-axis suppression, particularly with long-term use or high doses; use the lowest effective dose. Candida albicans infections of the mouth and pharynx have been reported with inhaled fluticasone — patients should rinse mouth after inhalation. Risk of reduced growth velocity in pediatric patients with prolonged use. Bone density loss may occur with long-term use. Not a bronchodilator — do not use for rescue treatment of acute asthma attacks.",
        "side_effects": "Nasal spray: headache, epistaxis (nosebleed), nasal burning/stinging, throat irritation, nausea. Inhaler: oral candidiasis, dysphonia (hoarseness), throat irritation, bronchospasm (paradoxical). Systemic (with high doses): HPA suppression, growth retardation in children, cataracts, glaucoma, osteoporosis.",
        "dosage": "Allergic rhinitis (Flonase — adults): 2 sprays per nostril once daily; may reduce to 1 spray per nostril once daily when controlled. Children 4-11 years: 1 spray per nostril once daily. Asthma (Flovent HFA — adults not on ICS): 88 mcg twice daily; range 88-880 mcg twice daily depending on severity.",
        "before_taking": "Tell your doctor if you have an active infection (bacterial, viral, or fungal), tuberculosis, osteoporosis, cataracts or glaucoma, or if you are switching from an oral corticosteroid (adrenal suppression risk). Rinse your mouth after using the inhaler to reduce risk of oral candidiasis. Intranasal fluticasone is generally considered safe in pregnancy (Category B). Fluticasone has minimal systemic absorption at recommended doses.",
    },
    "pantoprazole": {
        "description": "Pantoprazole (Protonix) is a proton pump inhibitor (PPI) available as 20 mg and 40 mg delayed-release oral tablets and IV formulation. It irreversibly inhibits the gastric H+/K+ ATPase enzyme, blocking gastric acid secretion.",
        "uses": "Pantoprazole is indicated for erosive esophagitis associated with gastroesophageal reflux disease (GERD), maintenance of healing of erosive esophagitis, reduction of risk of upper GI bleeding in critically ill patients (IV formulation), and pathological hypersecretory conditions including Zollinger-Ellison syndrome.",
        "warnings": "Long-term PPI use (especially >1 year) has been associated with hypomagnesemia, bone fracture risk (particularly hip, wrist, spine), Clostridioides difficile-associated diarrhea, vitamin B12 deficiency, acute interstitial nephritis, and fundic gland polyps. Use the lowest effective dose for the shortest duration. PPIs may mask symptoms of gastric malignancy. May interfere with absorption of drugs requiring gastric acid for absorption (ketoconazole, iron salts, erlotinib, mycophenolate). Pantoprazole is metabolized by CYP2C19 — interactions with clopidogrel are of concern (though evidence is less strong than with omeprazole).",
        "side_effects": "Common: headache, diarrhea, nausea, abdominal pain, vomiting, flatulence, injection-site reactions (IV). Serious: Clostridioides difficile colitis, hypomagnesemia (with long-term use), bone fractures, acute interstitial nephritis, vitamin B12 deficiency, cutaneous and systemic lupus erythematosus.",
        "dosage": "GERD/erosive esophagitis: 40 mg once daily for 8 weeks; maintenance: 40 mg once daily. Zollinger-Ellison: 40 mg twice daily, adjust based on acid output. IV: 40-80 mg IV once or twice daily. Take oral tablets 30-60 minutes before a meal.",
        "before_taking": "Tell your doctor if you have liver disease, low magnesium levels, osteoporosis, or lupus. Tell your doctor about all medications — pantoprazole may interact with methotrexate, HIV medications (rilpivirine, atazanavir), clopidogrel, warfarin, and drugs requiring acidic pH for absorption. Long-term use (>1 year) requires monitoring of magnesium and vitamin B12 levels. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "famotidine": {
        "description": "Famotidine (Pepcid, Pepcid AC) is an H2 receptor antagonist that reduces gastric acid secretion. Available OTC and prescription as 10, 20, and 40 mg tablets and oral suspension.",
        "uses": "Famotidine is indicated for duodenal ulcer (active and maintenance), gastric ulcer, gastroesophageal reflux disease (GERD), erosive esophagitis, and pathological hypersecretory conditions including Zollinger-Ellison syndrome. OTC formulations are used for heartburn relief and prevention.",
        "warnings": "Dose reduction required in renal impairment (reduce dose or increase dosing interval when CrCl <50 mL/min). May cause confusion, particularly in elderly or renally impaired patients. Famotidine may mask symptoms of gastric malignancy — rule out malignancy before initiating treatment. Unlike PPIs, famotidine does not significantly affect CYP enzymes, so drug-drug interactions are fewer.",
        "side_effects": "Common: headache, dizziness, constipation, diarrhea. Less common: elevated liver enzymes, confusion, agitation (especially in elderly), hallucinations (particularly in renally impaired patients). Serious: hypersensitivity reactions, QT prolongation (at high IV doses).",
        "dosage": "Duodenal ulcer (active): 40 mg once daily at bedtime or 20 mg twice daily for 4-8 weeks. Maintenance: 20 mg once daily at bedtime. GERD: 20 mg twice daily for up to 6 weeks. Heartburn (OTC): 10-20 mg 15-60 minutes before eating; maximum 20 mg twice daily. Renal impairment (CrCl <50 mL/min): 20 mg at bedtime or increase dosing interval.",
        "before_taking": "Tell your doctor if you have kidney disease (dose adjustment needed), liver disease, or are taking any other medications that may affect the kidney. Unlike PPIs, famotidine does not significantly affect CYP2C19 or CYP3A4, making drug interactions less of a concern. Famotidine is generally considered safe in pregnancy. Inform your doctor if you are breastfeeding.",
    },
    "metronidazole": {
        "description": "Metronidazole (Flagyl) is a nitroimidazole antibiotic and antiprotozoal agent available as 250 mg and 500 mg tablets, 375 mg capsules, topical gel (0.75%), vaginal gel, and IV formulation.",
        "uses": "Metronidazole is indicated for anaerobic bacterial infections (intra-abdominal infections, gynecologic infections, skin and skin structure infections, bone and joint infections, CNS infections, endocarditis, septicemia), Clostridioides difficile-associated diarrhea (CDAD), bacterial vaginosis, trichomoniasis, amebiasis, and giardiasis. It is a component of H. pylori eradication regimens.",
        "warnings": "Metronidazole is potentially mutagenic and carcinogenic in animal studies; avoid unnecessary use or prolonged administration. CONTRAINDICATED with disulfiram (can cause psychotic reactions) and during the first trimester of pregnancy (risk of teratogenicity). DISULFIRAM-LIKE REACTION occurs with alcohol — avoid all alcohol during treatment and for at least 3 days after completing treatment. CNS toxicity (encephalopathy, cerebellar ataxia, peripheral neuropathy) may occur, particularly with prolonged therapy. Discontinue if abnormal neurological signs develop.",
        "side_effects": "Common: nausea, metallic taste, vomiting, headache, dizziness, anorexia. Serious: disulfiram-like reaction with alcohol, peripheral neuropathy (with prolonged use), CNS toxicity (encephalopathy, seizures, cerebellar syndrome), Clostridioides difficile colitis (rare — can cause the disease it treats for C. diff CDAD), severe allergic reactions.",
        "dosage": "Anaerobic infections: 500 mg IV every 6-8 hours or 500-750 mg PO three times daily for 7-14 days. CDAD: 500 mg PO three times daily for 10-14 days (first recurrence; vancomycin or fidaxomicin preferred for initial episode). Bacterial vaginosis: 500 mg PO twice daily for 7 days or 5 g vaginal gel once daily for 5 days. Trichomoniasis: 2 g PO single dose (treat partner simultaneously). H. pylori eradication: 500 mg three times daily as part of combination therapy.",
        "before_taking": "Avoid metronidazole in the first trimester of pregnancy. Do not drink alcohol during treatment or for at least 3 days after — risk of severe disulfiram-like reaction (flushing, vomiting, tachycardia). Tell your doctor if you have liver disease (dose reduction needed), kidney disease, seizure disorder, blood disorders, or peripheral neuropathy. Tell your doctor about all medications — metronidazole inhibits CYP2C9 (increasing warfarin effect) and interacts with lithium, disulfiram, and cyclosporine.",
    },
    "amphetamine-dextroamphetamine": {
        "description": "Amphetamine/dextroamphetamine (Adderall, Adderall XR) is a central nervous system stimulant (mixed amphetamine salts) consisting of 75% dextroamphetamine and 25% levoamphetamine. Available as immediate-release (Adderall, 5-30 mg) and extended-release capsules (Adderall XR, 5-30 mg). Schedule II controlled substance.",
        "uses": "Adderall is indicated for the treatment of Attention Deficit Hyperactivity Disorder (ADHD) in children ≥3 years and adults, and narcolepsy. It is the most widely prescribed stimulant medication for ADHD, acting by increasing the release and blocking the reuptake of dopamine and norepinephrine.",
        "warnings": "FDA BOXED WARNING: High potential for abuse and dependence. Schedule II controlled substance. Misuse may cause sudden death and serious cardiovascular adverse reactions. Sudden death has been reported in patients with structural cardiac abnormalities or other serious heart problems. Avoid use in patients with known structural cardiac abnormalities, cardiomyopathy, serious heart rhythm abnormalities, or other serious cardiac problems. Do not use with MAO inhibitors or within 14 days of MAO inhibitor use — can cause hypertensive crisis. May cause psychiatric adverse events including psychosis, mania, and aggression, particularly in patients with pre-existing psychiatric conditions. Growth suppression has been reported in children — monitor growth.",
        "side_effects": "Common: decreased appetite, insomnia, headache, dry mouth, abdominal pain, increased blood pressure and heart rate, irritability, emotional lability, weight loss. Serious: sudden cardiac death (in patients with structural heart abnormalities), hypertensive crisis (with MAOIs), psychosis, mania, aggressive behavior, seizures, peripheral vasculopathy including Raynaud's phenomenon, priapism.",
        "dosage": "ADHD (Adderall IR): Adults: Start 5 mg once or twice daily; increase weekly by 5 mg; usual range 5-40 mg/day in divided doses. Children 6-17 years: Start 5 mg once or twice daily. Adderall XR: Adults: 20 mg once daily in the morning; range 5-60 mg/day. Children 6-17 years: 10 mg once daily in the morning; range 5-30 mg/day. Take in the morning; avoid afternoon doses to prevent insomnia.",
        "before_taking": "Not recommended in patients with structural heart defects, cardiomyopathy, or serious arrhythmias. Do not take within 14 days of an MAOI. Tell your doctor about heart disease, high blood pressure, history of psychosis or bipolar disorder, Tourette syndrome, glaucoma, anxiety, or a history of drug abuse. Monitor height and weight in children. Adderall is a Schedule II controlled substance; misuse can cause addiction. Avoid during pregnancy if possible.",
    },
    "clopidogrel": {
        "description": "Clopidogrel (Plavix) is an oral antiplatelet drug (thienopyridine P2Y12 receptor antagonist) available as 75 mg and 300 mg tablets. It is a prodrug that requires hepatic CYP2C19-mediated activation to its active thiol metabolite.",
        "uses": "Clopidogrel is indicated for reduction of atherothrombotic events (MI, stroke, vascular death) in patients with recent MI, recent stroke, or established peripheral arterial disease, and in patients with acute coronary syndrome (NSTEMI or STEMI managed with PCI). It is often combined with aspirin (dual antiplatelet therapy — DAPT) after coronary stent placement.",
        "warnings": "FDA BOXED WARNING: Diminished antiplatelet effect in patients who are CYP2C19 poor metabolizers — consider alternative treatment. Clopidogrel is metabolized to its active form by CYP2C19; PPI co-administration (especially omeprazole, esomeprazole) significantly reduces active metabolite levels and may increase cardiovascular risk (especially pantoprazole and rabeprazole are less problematic). Increased risk of bleeding with aspirin, NSAIDs, warfarin, and other anticoagulants. Discontinue 5 days before elective surgery. Thrombotic thrombocytopenic purpura (TTP) has been reported, sometimes within 2 weeks of starting treatment.",
        "side_effects": "Common: bleeding (any site), epistaxis, GI hemorrhage, purpura/bruising, hematuria. Serious: major hemorrhage (intracranial, GI), thrombotic thrombocytopenic purpura (TTP), hypersensitivity reactions (anaphylaxis, angioedema, serum sickness).",
        "dosage": "Recent MI, stroke, or PAD: 75 mg once daily. ACS (unstable angina/NSTEMI): loading dose 300-600 mg, then 75 mg once daily (usually with aspirin). ACS (STEMI, with or without PCI): loading dose 300 mg, then 75 mg once daily. Post-PCI/stent: 75 mg once daily for at least 12 months with aspirin. Take with or without food.",
        "before_taking": "Tell your doctor if you have active bleeding (peptic ulcer, intracranial hemorrhage), liver disease, or kidney disease. Tell your doctor about all medications — especially PPIs (omeprazole/esomeprazole significantly reduce clopidogrel effect), aspirin, NSAIDs, warfarin, and other anticoagulants. Test for CYP2C19 poor metabolizer status if available — alternative agents (prasugrel, ticagrelor) may be preferred. Discontinue 5 days before elective surgery. Do not stop clopidogrel abruptly after stent placement — risk of in-stent thrombosis.",
    },
    "hydroxychloroquine": {
        "description": "Hydroxychloroquine (Plaquenil) is an antimalarial and disease-modifying antirheumatic drug (DMARD) available as 200 mg tablets. It is the hydroxylated derivative of chloroquine with a better safety profile.",
        "uses": "Hydroxychloroquine is indicated for treatment and suppression of malaria (Plasmodium vivax, P. malariae, P. ovale, and susceptible strains of P. falciparum), treatment of systemic lupus erythematosus (SLE), and treatment of rheumatoid arthritis (RA). It is considered first-line therapy for SLE and is often used in combination with other DMARDs for RA.",
        "warnings": "Risk of irreversible retinopathy (bull's eye maculopathy) with long-term use — baseline ophthalmologic exam required before starting, then annually after 5 years (or earlier in high-risk patients based on annual dose >5 mg/kg, renal disease, or tamoxifen use). QT interval prolongation has been reported. Risk of hypoglycemia in patients taking antidiabetic agents. Do not use in patients with pre-existing retinopathy or macular disease.",
        "side_effects": "Common: nausea, vomiting, diarrhea, abdominal cramps, headache, dizziness, skin rash, pruritus. Serious: retinopathy (irreversible, bull's eye pattern), QT prolongation, cardiomyopathy (rare), severe skin reactions (Stevens-Johnson syndrome, toxic epidermal necrolysis), aplastic anemia, agranulocytosis, hypoglycemia.",
        "dosage": "Malaria prophylaxis: 400 mg once weekly, 1-2 weeks before travel and 4 weeks after return. Malaria treatment: 800 mg initially, then 400 mg at 6, 24, and 48 hours. SLE: 200-400 mg/day in 1-2 doses (do not exceed 5 mg/kg/day). Rheumatoid arthritis: 400-600 mg/day initially; maintenance 200-400 mg/day. Take with food or milk to reduce GI upset.",
        "before_taking": "Requires baseline eye exam before starting and annual follow-up for retinopathy monitoring. Tell your doctor if you have pre-existing retinal or visual field changes, liver disease, kidney disease, G6PD deficiency, porphyria, or psoriasis (can precipitate acute attack). Tell your doctor about antidiabetic medications (hypoglycemia risk). Hydroxychloroquine is generally considered safe in pregnancy and is recommended for use in pregnant women with SLE and RA.",
    },
    "budesonide": {
        "description": "Budesonide is an inhaled, intranasal, or oral corticosteroid with potent anti-inflammatory activity and high first-pass hepatic metabolism (low systemic bioavailability with inhaled/oral enteric-coated formulations). Brands include Pulmicort (inhaled), Rhinocort (nasal), and Entocort EC/Uceris (oral, for GI conditions).",
        "uses": "Inhaled budesonide (Pulmicort): maintenance treatment of asthma in adults and children. Nasal budesonide (Rhinocort): treatment of seasonal and perennial allergic rhinitis. Oral budesonide (Entocort EC): induction of remission in mild-to-moderate Crohn's disease affecting the ileum and/or ascending colon; (Uceris): induction of remission in mild-to-moderate ulcerative colitis.",
        "warnings": "Inhaled and intranasal corticosteroids may cause HPA-axis suppression, adrenal insufficiency, reduced growth velocity in children, and osteoporosis with long-term use. Not a bronchodilator — not for rescue treatment of acute asthma attacks. Rinse mouth after inhaled use to prevent oral candidiasis. Strong CYP3A4 inhibitors (ketoconazole, itraconazole) significantly increase systemic budesonide exposure. Switching from systemic to inhaled corticosteroids can unmask adrenal insufficiency.",
        "side_effects": "Inhaled: oral candidiasis, hoarseness, throat irritation. Nasal: epistaxis, nasal irritation. Oral (for GI): headache, nausea, abdominal pain, respiratory infection. Systemic (with high doses): HPA suppression, adrenal insufficiency, cataracts, glaucoma, osteoporosis.",
        "dosage": "Asthma (Pulmicort Flexhaler): 180-360 mcg twice daily, up to 720 mcg twice daily. Asthma (nebulization — children 12 months-8 years): 0.5-1 mg once or twice daily. Allergic rhinitis (Rhinocort Aqua): 1-4 sprays per nostril once daily. Crohn's disease (Entocort EC): 9 mg once daily in the morning for up to 8 weeks; maintenance 6 mg once daily for up to 3 months.",
        "before_taking": "Tell your doctor if you have a current infection (bacterial, viral, fungal, or parasitic), tuberculosis, liver disease, osteoporosis, cataracts or glaucoma, or adrenal gland problems. Do not stop oral budesonide abruptly. Tell your doctor about strong CYP3A4 inhibitors (ketoconazole, itraconazole, ritonavir) — these significantly increase budesonide levels. Monitor growth in children on long-term inhaled budesonide. Inform your doctor if you are pregnant or breastfeeding.",
    },
    "fentanyl": {
        "description": "Fentanyl is a potent synthetic opioid analgesic (Schedule II controlled substance) approximately 100 times more potent than morphine. Available as transdermal patches (Duragesic, 12-100 mcg/hr), buccal tablets (Fentora), sublingual tablets/spray (Abstral, Subsys), lozenges/lollipops (Actiq), nasal spray (Lazanda), and IV/IM injection.",
        "uses": "Transdermal fentanyl (Duragesic) is indicated for management of pain severe enough to require daily, around-the-clock, long-term opioid treatment in opioid-tolerant patients who cannot be managed by other means. Transmucosal fentanyl products (Actiq, Fentora, Abstral, Subsys, Lazanda) are indicated only for breakthrough cancer pain in opioid-tolerant patients already on a scheduled opioid regimen.",
        "warnings": "FDA BOXED WARNINGS: Addiction, abuse, and misuse; life-threatening respiratory depression; accidental ingestion (even one patch can be fatal in a child); neonatal opioid withdrawal syndrome; cytochrome P450 3A4 interactions (CYP3A4 inhibitors can increase fentanyl levels causing fatal respiratory depression); risks of concomitant use with benzodiazepines or other CNS depressants. Transdermal patches are only for opioid-tolerant patients — not for acute or intermittent pain. Do not expose patches to external heat sources (heating pads, electric blankets, heat lamps, saunas) — increases fentanyl absorption and can cause overdose. REMS program required. Illicitly manufactured fentanyl is a major driver of the opioid overdose epidemic.",
        "side_effects": "Common: constipation, nausea, vomiting, somnolence, dizziness, headache, sweating, dry mouth, confusion, application site reactions (patches). Serious: respiratory depression, apnea, severe hypotension, bradycardia, opioid withdrawal, adrenal insufficiency.",
        "dosage": "Transdermal (opioid-tolerant patients only): Start with lowest patch dose (12 mcg/hr) and titrate; change every 72 hours (some patients require 48-hour dosing). Transmucosal products: highly variable, titrate individually. All fentanyl products have complex dosing — refer to product-specific prescribing information.",
        "before_taking": "Fentanyl transdermal and transmucosal products are ONLY for opioid-tolerant patients — not for opioid-naive patients, acute pain, or post-operative pain. Never share fentanyl; store securely away from children. Dispose of patches by folding adhesive side together and flushing. Do not use with alcohol, benzodiazepines, or CNS depressants. Do not apply external heat to patches. Carry naloxone (Narcan) and ensure household members know how to use it.",
    },
    "morphine": {
        "description": "Morphine (MS Contin, Kadian, Morphabond) is a natural opioid analgesic derived from opium (Schedule II controlled substance). Available as immediate-release tablets, extended-release tablets/capsules, oral solution, and injectable formulations.",
        "uses": "Morphine is indicated for the management of pain severe enough to require opioid treatment and for which alternative treatments are inadequate. Extended-release morphine is for around-the-clock management of severe chronic pain in opioid-tolerant patients. Morphine is also used in palliative care for dyspnea and for acute severe pain (IV/IM).",
        "warnings": "FDA BOXED WARNINGS: Addiction, abuse, and misuse; life-threatening respiratory depression; accidental ingestion; neonatal opioid withdrawal syndrome; interactions with CNS depressants including benzodiazepines. Extended-release morphine is for opioid-tolerant patients only. Do not crush or chew extended-release tablets — may cause rapid release and fatal overdose. Reduce dose in renal and hepatic impairment. Active metabolite (morphine-6-glucuronide) accumulates in renal failure.",
        "side_effects": "Common: constipation, nausea, vomiting, somnolence, dizziness, pruritus (particularly with IV use), sweating, dry mouth. Serious: respiratory depression, severe hypotension, opioid-induced hyperalgesia, adrenal insufficiency, androgen deficiency.",
        "dosage": "IR tablets: Opioid-naive adults: 15-30 mg every 4 hours as needed. ER (MS Contin): Initial: 15-30 mg every 8-12 hours; titrate to pain control. ER capsules (Kadian): once or twice daily. Use opioid equianalgesic tables when rotating from another opioid. Reduce dose by 50% in moderate-severe hepatic or renal impairment.",
        "before_taking": "Not for acute or mild pain, for opioid-naive patients (ER formulations), or in patients with respiratory depression, bowel obstruction, or hypersensitivity to morphine. Tell your doctor about kidney disease (active metabolite accumulates), liver disease, seizures, breathing problems, adrenal disease, thyroid disorders, or substance use disorder. Do not combine with alcohol, benzodiazepines, or CNS depressants.",
    },
    "codeine": {
        "description": "Codeine is a naturally occurring opioid and prodrug (Schedule II/III depending on formulation) that is metabolized by CYP2D6 to morphine. Available as 15, 30, and 60 mg tablets and in combination products with acetaminophen or ibuprofen.",
        "uses": "Codeine is indicated for mild to moderately severe pain (as a single agent or in combination) and as an antitussive (cough suppressant). Many codeine-acetaminophen combination products are Schedule III. Plain codeine tablets are Schedule II.",
        "warnings": "FDA BOXED WARNINGS: Respiratory depression and death in children; ultra-rapid CYP2D6 metabolizers convert codeine to morphine at an accelerated rate, leading to life-threatening respiratory depression or death — deaths have occurred in pediatric patients, particularly post-tonsillectomy/adenoidectomy. Codeine is CONTRAINDICATED in children under 12 years for pain and under 18 years post-tonsillectomy/adenoidectomy for pain. Not recommended for nursing mothers (ultra-rapid metabolizers can pass high morphine levels to breast milk). Addiction, abuse, misuse, and dependence potential. Neonatal opioid withdrawal syndrome with prolonged use in pregnancy.",
        "side_effects": "Common: constipation, nausea, vomiting, drowsiness, light-headedness, dizziness, sedation. Serious: respiratory depression (especially in CYP2D6 ultra-rapid metabolizers and children), dependence, withdrawal.",
        "dosage": "Pain (adults): 15-60 mg every 4-6 hours as needed; maximum 360 mg/day. Cough (adults): 10-20 mg every 4-6 hours; maximum 120 mg/day. Contraindicated in children <12 years for pain.",
        "before_taking": "Contraindicated in children under 12 for pain, children under 18 post-tonsillectomy/adenoidectomy, and breastfeeding mothers who are CYP2D6 ultra-rapid metabolizers. Consider CYP2D6 genotyping if available. Tell your doctor about respiratory problems, liver disease, kidney disease, thyroid disorders, adrenal problems, seizures, or substance use disorder.",
    },
    "acyclovir": {
        "description": "Acyclovir (Zovirax) is a guanosine analogue antiviral active against herpesviruses including HSV-1, HSV-2, and varicella-zoster virus (VZV). Available as 200, 400, 800 mg tablets, oral suspension, topical cream, and IV injection.",
        "uses": "Acyclovir is indicated for treatment of acute herpes zoster (shingles), initial and recurrent genital herpes (HSV-2), chickenpox (varicella), and mucocutaneous HSV in immunocompromised patients. It is used prophylactically to suppress recurrent genital herpes. IV acyclovir is used for herpes simplex encephalitis and severe herpes infections.",
        "warnings": "Renal impairment and renal failure have been reported with IV acyclovir (due to crystalline nephropathy) — ensure adequate hydration during IV use. Oral acyclovir may also cause crystalline nephropathy at high doses; maintain adequate hydration. Thrombotic thrombocytopenic purpura/hemolytic uremic syndrome (TTP/HUS) has been reported in severely immunocompromised patients at high doses. CNS adverse events (confusion, hallucinations, agitation, seizures, coma) have been reported, more commonly in elderly or renally impaired patients.",
        "side_effects": "Oral: nausea, vomiting, headache, diarrhea, malaise. IV: renal failure/crystalline nephropathy (with inadequate hydration), phlebitis (injection site), elevated BUN/creatinine, CNS effects (confusion, hallucinations). Topical: burning, stinging, pruritus at application site.",
        "dosage": "Genital herpes (initial): 200 mg 5 times/day or 400 mg three times/day for 7-10 days. Genital herpes (recurrent): 200 mg 5 times/day or 400 mg three times/day for 5 days. Chronic suppression: 400 mg twice daily. Herpes zoster: 800 mg 5 times/day for 7-10 days. Chickenpox (children ≥2 years and adults): 20 mg/kg (max 800 mg) 4 times/day for 5 days. Adjust dose for renal impairment.",
        "before_taking": "Tell your doctor if you have kidney disease (dose reduction required), dehydration, or a compromised immune system. Maintain adequate hydration during acyclovir treatment. Tell your doctor about all medications — acyclovir may increase nephrotoxicity with other nephrotoxic drugs and can decrease renal clearance of drugs excreted by the kidney. Acyclovir is considered compatible with pregnancy and breastfeeding for herpes suppression.",
    },
    "doxycycline": {
        "description": "Doxycycline (Vibramycin, Doryx, Oracea, Acticlate) is a broad-spectrum tetracycline antibiotic available as 50, 75, 100, and 150 mg tablets and capsules. It has better oral bioavailability and longer half-life than tetracycline.",
        "uses": "Doxycycline is indicated for respiratory tract infections (pneumonia, including atypical pathogens), urinary tract infections, skin and soft tissue infections, sexually transmitted infections (chlamydia, gonorrhea, syphilis), Lyme disease, Rocky Mountain spotted fever and other rickettsial infections, malaria prophylaxis, brucellosis, and periodontitis. It is a key agent for community-acquired pneumonia and is first-line for community-acquired MRSA skin infections.",
        "warnings": "Do not use in children under 8 years (binds to developing teeth and bones, causing permanent tooth discoloration and enamel hypoplasia, and can impair bone growth). Do not use in pregnant women after the 4th month of pregnancy for the same reasons. Photosensitivity reactions are common — avoid prolonged sun exposure and use sunscreen. Esophageal irritation and ulceration can occur — take with adequate fluid and remain upright for 30 minutes after taking. Pseudotumor cerebri (intracranial hypertension) has been reported.",
        "side_effects": "Common: nausea, vomiting, diarrhea, esophageal irritation, photosensitivity, skin rash. Serious: esophageal ulceration (take with full glass of water, remain upright), intracranial hypertension (pseudotumor cerebri), Clostridioides difficile-associated diarrhea, severe skin reactions (Stevens-Johnson syndrome), hepatotoxicity.",
        "dosage": "Most infections (adults): 100 mg twice daily on first day, then 100 mg once or twice daily. More severe infections: 100 mg twice daily throughout. Malaria prophylaxis: 100 mg once daily starting 1-2 days before travel, during travel, and for 4 weeks after. Acne (low-dose, Oracea): 40 mg once daily in the morning. Take with food or milk to reduce GI side effects.",
        "before_taking": "Do not use in children under 8 years or in the second half of pregnancy. Take with a full glass of water and remain upright for 30 minutes to prevent esophageal ulceration. Avoid prolonged sun exposure — use sunscreen. Antacids, calcium, iron, zinc, and bismuth subsalicylate reduce doxycycline absorption — take 2-3 hours apart. Tell your doctor if you have liver disease, kidney disease, or myasthenia gravis.",
    },
    "azithromycin": {
        "description": "Azithromycin (Zithromax, Z-Pak) is a macrolide antibiotic with an unusually long tissue half-life (68 hours), allowing once-daily dosing and short course treatment. Available as 250 mg and 500 mg tablets, oral suspension, and IV injection.",
        "uses": "Azithromycin is indicated for community-acquired pneumonia (mild-moderate, in appropriate patients), acute bacterial exacerbations of COPD, acute otitis media, pharyngitis/tonsillitis (second-line), skin and soft tissue infections, sexually transmitted infections (chlamydia, gonorrhea — in combination), and disseminated Mycobacterium avium complex (MAC) disease in HIV patients.",
        "warnings": "Azithromycin has been associated with QT interval prolongation and rare cases of fatal cardiac arrhythmias (torsades de pointes) — avoid in patients with known QT prolongation, hypokalemia, hypomagnesemia, bradycardia, or taking Class IA or III antiarrhythmics. Hepatotoxicity including hepatic necrosis and failure has occurred. Exacerbation of myasthenia gravis has been reported. Clostridioides difficile-associated diarrhea has been reported.",
        "side_effects": "Common: diarrhea, nausea, abdominal pain, vomiting, headache. Serious: QT prolongation, torsades de pointes, hepatotoxicity (jaundice, hepatic necrosis, hepatic failure), Clostridioides difficile colitis, severe allergic reactions (anaphylaxis, Stevens-Johnson syndrome, toxic epidermal necrolysis).",
        "dosage": "Community-acquired pneumonia (mild): 500 mg on day 1, then 250 mg once daily on days 2-5 (Z-Pak). STI (chlamydia): 1 g single oral dose. Gonorrhea: azithromycin 1 g + ceftriaxone 500 mg IM (dual therapy). COPD exacerbation: 500 mg on day 1, then 250 mg on days 2-5. MAC prophylaxis in HIV: 1.2 g once weekly.",
        "before_taking": "Tell your doctor if you have QT prolongation or cardiac arrhythmias, electrolyte imbalances, liver disease, myasthenia gravis, or kidney disease. Tell your doctor about antacids containing aluminum or magnesium (take azithromycin at least 1 hour before or 2 hours after). Tell your doctor about warfarin (azithromycin may increase INR), antiarrhythmics, and other drugs that prolong QT. Azithromycin is generally considered safe in pregnancy.",
    },
    "glipizide": {
        "description": "Glipizide (Glucotrol, Glucotrol XL) is a second-generation sulfonylurea oral hypoglycemic agent available as 5 mg and 10 mg immediate-release tablets and 2.5, 5, and 10 mg extended-release tablets.",
        "uses": "Glipizide is indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes mellitus. It stimulates insulin secretion from pancreatic beta cells by binding to the sulfonylurea receptor (SUR1) and closing ATP-sensitive potassium channels.",
        "warnings": "RISK OF CARDIOVASCULAR MORTALITY: Based on UGDP study, sulfonylureas may carry increased cardiovascular mortality compared to diet alone or diet plus insulin. Hypoglycemia is the primary adverse effect — risk is increased with missed meals, strenuous exercise, renal impairment, hepatic impairment, elderly patients, and drug interactions (see below). Glipizide is not recommended in patients with severe renal or hepatic impairment. SIADH-related hyponatremia has been reported.",
        "side_effects": "Common: hypoglycemia (especially in elderly, with missed meals, or impaired renal/hepatic function), nausea, diarrhea, dizziness, headache. Serious: severe hypoglycemia (can be prolonged — requires IV glucose), hemolytic anemia and other blood dyscrasias, hepatic failure, severe hyponatremia (SIADH).",
        "dosage": "IR tablets: Initial: 5 mg once daily 30 minutes before breakfast; geriatric/hepatic impairment: 2.5 mg. Titrate in 2.5-5 mg increments at weekly intervals; usual range 2.5-20 mg/day; divided doses for doses >15 mg/day; maximum 40 mg/day. XL tablets: Initial: 5 mg once daily with breakfast; maximum 20 mg once daily.",
        "before_taking": "Do not use glipizide in type 1 diabetes, diabetic ketoacidosis, or allergy to sulfonylureas. Tell your doctor about kidney disease, liver disease, adrenal or pituitary insufficiency, G6PD deficiency, or thyroid disease. Many drugs interact with glipizide: NSAIDs, fluconazole, clarithromycin, and certain antibiotics increase hypoglycemia risk; rifampin, diuretics, corticosteroids, and beta-blockers can impair glycemic control or mask hypoglycemia symptoms. Instruct patients to carry a fast-acting glucose source.",
    },
    "lamotrigine": {
        "description": "Lamotrigine (Lamictal) is an antiepileptic and mood stabilizer available as 25, 50, 100, 150, 200, and 250 mg tablets, orally disintegrating tablets (ODT), chewable dispersible tablets, and extended-release tablets.",
        "uses": "Lamotrigine is indicated for partial-onset seizures and primary generalized tonic-clonic seizures in adults and children ≥2 years (as monotherapy or adjunctive therapy), Lennox-Gastaut syndrome (adjunctive therapy), and maintenance treatment of bipolar I disorder to delay time to mood episodes in adults.",
        "warnings": "FDA BOXED WARNING: Serious skin reactions including Stevens-Johnson syndrome (SJS) and toxic epidermal necrolysis (TEN) have been reported, with some fatalities. Risk is higher in children, those on valproate (which markedly increases lamotrigine levels), and those taking lamotrigine at doses exceeding recommended initial doses. Discontinue at first sign of rash unless clearly not drug-related. Do NOT restart lamotrigine in patients who discontinued due to rash. Multiorgan hypersensitivity reactions (also called Drug Reaction with Eosinophilia and Systemic Symptoms — DRESS) have occurred. Suicidal behavior and ideation have been reported with antiepileptic drugs.",
        "side_effects": "Common: dizziness, headache, diplopia (double vision), ataxia, nausea, blurred vision, somnolence, rhinitis. Serious: SJS, TEN, DRESS, aseptic meningitis, hemophagocytic lymphohistiocytosis (HLH), worsening of seizures.",
        "dosage": "Dose depends on concomitant medications (valproate significantly increases levels; enzyme-inducing AEDs significantly decrease levels). Monotherapy (not on enzyme inducers or valproate): 25 mg once daily × 2 weeks, then 50 mg once daily × 2 weeks, then increase by 50 mg/day every 1-2 weeks; target 225-375 mg/day in 2 divided doses. With valproate: start very low (12.5-25 mg every other day × 2 weeks) and titrate very slowly.",
        "before_taking": "Tell your doctor if you have liver or kidney disease, heart problems, or a history of rash from antiepileptic drugs. Do not stop lamotrigine abruptly (risk of breakthrough seizures). Tell your doctor about all medications, especially valproic acid/valproate (doubles lamotrigine levels), oral contraceptives (reduce lamotrigine levels), carbamazepine, phenytoin, phenobarbital, and primidone. Inform your doctor if you are pregnant — lamotrigine is often used in pregnancy but levels fluctuate significantly with hormonal changes.",
    },
    "topiramate": {
        "description": "Topiramate (Topamax, Trokendi XR, Qudexy XR) is a broad-spectrum antiepileptic drug and migraine prophylaxis agent available as 25, 50, 100, and 200 mg tablets and extended-release capsules.",
        "uses": "Topiramate is indicated as monotherapy or adjunctive therapy for partial-onset or primary generalized tonic-clonic seizures in adults and children ≥2 years, adjunctive therapy for Lennox-Gastaut syndrome, and prophylaxis of migraine headaches in adults and adolescents ≥12 years. It is also used off-label (in combination with phentermine as Qsymia) for chronic weight management.",
        "warnings": "Risk of metabolic acidosis (non-anion gap) — can increase serum chloride and decrease bicarbonate; monitor in patients on ketogenic diet, metformin, or with renal disease. Cognitive adverse effects are common ('Dope-a-max') — slowed word retrieval, difficulty concentrating, and memory problems. Kidney stones occur in 1-2% (maintain adequate hydration). Acute closed-angle glaucoma and acute myopia have been reported — discontinue if sudden vision changes occur. Oligohidrosis and hyperthermia (decreased sweating in hot weather) have been reported, particularly in children. Teratogenic — associated with oral clefts and is FDA Pregnancy Category D; requires REMS program for use with phentermine. Suicidal ideation reported with antiepileptics.",
        "side_effects": "Common: cognitive dysfunction (word-finding problems, slowed thinking), weight loss, paresthesia (tingling hands/feet), fatigue, somnolence, dizziness, nausea, diarrhea, anorexia. Serious: metabolic acidosis, kidney stones, acute myopia/glaucoma, oligohidrosis and hyperthermia, psychiatric symptoms, suicidal ideation, teratogenicity.",
        "dosage": "Epilepsy (adjunctive, adults): 25-50 mg/day initially, titrate slowly over 5-7 weeks to 200-400 mg/day in 2 divided doses. Migraine prophylaxis: 25 mg once daily at night × 1 week, increase to 25 mg twice daily × 1 week, then 50 mg twice daily × 1 week, target 50 mg twice daily. Take with adequate fluids throughout the day.",
        "before_taking": "Tell your doctor if you have kidney disease, liver disease, metabolic acidosis, kidney stones, glaucoma, or a history of suicidal thoughts. Drink plenty of water to reduce kidney stone risk. Inform your doctor and avoid heat exposure — topiramate decreases sweating and can cause overheating. Avoid alcohol and other CNS depressants. Topiramate reduces oral contraceptive effectiveness at doses >200 mg/day — use additional contraception. Do not take during pregnancy if avoidable — risk of oral clefts in the fetus.",
    },
    "valproic acid": {
        "description": "Valproic acid (Depakene, Depakote as valproate sodium/divalproex, Depakote ER) is a broad-spectrum antiepileptic, mood stabilizer, and migraine prophylaxis agent. Available as 250 mg capsules, 250 mg/5 mL syrup, and as divalproex sodium delayed-release tablets (125-500 mg) and ER tablets.",
        "uses": "Valproic acid/divalproex is indicated for complex partial seizures, simple and complex absence seizures, and as adjunctive therapy for multiple seizure types. Depakote is indicated for acute manic or mixed episodes in bipolar disorder and for prevention of migraine headaches.",
        "warnings": "FDA BOXED WARNINGS: (1) Hepatotoxicity — potentially fatal hepatic failure has occurred, especially in children under 2 years and those with mitochondrial disorders (Alpers' disease, POLG mutation). Monitor LFTs closely. (2) Teratogenicity — valproate is associated with major congenital malformations (neural tube defects in 1-2%, cardiac defects, cleft palate), reduced IQ and autism spectrum disorder in children exposed in utero. ABSOLUTELY CONTRAINDICATED in pregnancy for migraine prophylaxis. Should only be used in pregnancy for epilepsy when benefits clearly outweigh risks. (3) Pancreatitis — potentially fatal, occurring at any time during treatment. Valproate increases lamotrigine levels (potentially causing toxicity) and interacts with carbapenem antibiotics (which dramatically reduce valproate levels).",
        "side_effects": "Common: nausea, vomiting, diarrhea, abdominal pain, weight gain, tremor, hair loss, somnolence, dizziness, thrombocytopenia. Serious: hepatotoxicity (especially children <2 years), pancreatitis, hyperammonemic encephalopathy (with or without hepatic dysfunction; can be precipitated by carbapenem antibiotics or topiramate), teratogenicity, DRESS, SJS/TEN.",
        "dosage": "Epilepsy: initial 10-15 mg/kg/day in 2-3 divided doses; increase by 5-10 mg/kg/week to seizure control or intolerable adverse effects; usual maintenance 1000-2000 mg/day. Acute mania: initial 750 mg/day in divided doses; maximum 60 mg/kg/day. Migraine prophylaxis: 250 mg twice daily; may increase to 1000 mg/day. Monitor serum levels (therapeutic 50-100 mcg/mL for epilepsy).",
        "before_taking": "Valproate is CONTRAINDICATED in hepatic disease, urea cycle disorders (hyperammonemia risk), and mitochondrial disorders. Absolutely contraindicated during pregnancy for migraine prophylaxis. For epilepsy: requires careful risk-benefit discussion with REMS counseling; use effective contraception. Tell your doctor about liver disease, pancreatitis, kidney disease, bleeding disorders, or carnitine deficiency. Monitor CBC, LFTs, and serum levels. Tell your doctor about all medications — valproate interactions are extensive.",
    },
    "phenytoin": {
        "description": "Phenytoin (Dilantin, Phenytek) is a hydantoin antiepileptic drug available as 30 mg and 100 mg extended-release capsules, 50 mg chewable tablets, and IV injection. It has complex, non-linear (Michaelis-Menten) pharmacokinetics — small dose changes can cause large changes in serum levels.",
        "uses": "Phenytoin is indicated for the control of tonic-clonic (grand mal) and complex partial (psychomotor, temporal lobe) seizures, and prevention and treatment of seizures occurring during or following neurosurgery. IV phenytoin is used for status epilepticus.",
        "warnings": "Non-linear pharmacokinetics make dosing complex — small dose increases can cause disproportionate level increases and toxicity. Signs of toxicity: nystagmus, ataxia, mental status changes. Phenytoin has extensive drug interactions — as a potent CYP enzyme inducer, it reduces levels of many drugs. Long-term use causes gingival hyperplasia, hirsutism, coarsening of facial features, peripheral neuropathy, and bone disease. Cardiac arrhythmias and hypotension can occur with rapid IV administration — maximum IV rate 50 mg/min in adults (25 mg/min in elderly or patients with cardiovascular disease). Purple glove syndrome with IV infiltration. DRESS and SJS/TEN have been reported.",
        "side_effects": "Dose-related toxicity: nystagmus (earliest), ataxia, slurred speech, confusion, lethargy, coma (at very high levels). Chronic: gingival hyperplasia (poor dental hygiene worsens), hirsutism, coarsening of facial features, peripheral neuropathy, bone disease, folate deficiency. Serious: DRESS, SJS/TEN, hepatotoxicity, blood dyscrasias, purple glove syndrome (IV).",
        "dosage": "Loading dose (non-emergent): 15-20 mg/kg PO in 3 divided doses every 2-6 hours; reduces risk of GI intolerance. Status epilepticus (IV): 15-20 mg/kg at ≤50 mg/min (≤25 mg/min in elderly or cardiac disease). Maintenance: 300 mg/day (100 mg 3 times daily); adjust to achieve therapeutic level 10-20 mcg/mL. Monitor levels — free levels are more relevant in hypoalbuminemia.",
        "before_taking": "Tell your doctor if you have liver disease, cardiac arrhythmias, or porphyria. Phenytoin has extensive drug interactions — it induces CYP3A4, CYP2C9, and CYP2C19, reducing levels of numerous medications. Conversely, many drugs alter phenytoin levels. Monitor serum levels and signs of toxicity. Do not stop phenytoin abruptly (risk of status epilepticus). Inform your doctor if you are pregnant — phenytoin is teratogenic (fetal hydantoin syndrome).",
    },
    "levetiracetam": {
        "description": "Levetiracetam (Keppra, Keppra XR) is a broad-spectrum antiepileptic drug with a unique mechanism (binding to synaptic vesicle protein SV2A). Available as 250, 500, 750, and 1000 mg tablets, 500 and 1000 mg ER tablets, 100 mg/mL oral solution, and IV injection.",
        "uses": "Levetiracetam is indicated as adjunctive therapy for partial-onset seizures in adults and children ≥1 month, myoclonic seizures in juvenile myoclonic epilepsy (adults and adolescents ≥12 years), and primary generalized tonic-clonic seizures in adults and children ≥6 years. It is widely used as first-line and adjunctive therapy due to its tolerability and lack of major drug interactions.",
        "warnings": "Psychiatric adverse events including aggression, irritability, agitation, anxiety, depression, hostility, and suicidal ideation occur in approximately 13% of patients. Monitor for behavioral changes. Levetiracetam can cause somnolence, fatigue, coordination difficulties, and dizziness. Dose reduction required in renal impairment (primarily renally eliminated). Withdrawal seizures can occur with abrupt discontinuation. Suicidal behavior and ideation have been reported with antiepileptic drugs generally.",
        "side_effects": "Common: somnolence, dizziness, fatigue, weakness, infection. Psychiatric: irritability, aggression, depression, anxiety, hostility — particularly in patients with prior psychiatric history. Serious: suicidal ideation/behavior, serious skin reactions (SJS, TEN — rare), blood pressure changes.",
        "dosage": "Partial-onset seizures (adults): Start 500 mg twice daily; increase by 500 mg/day every 2 weeks as needed; maximum 1500 mg twice daily (3000 mg/day). XR tablets: 1000 mg once daily; maximum 3000 mg once daily. Reduce dose proportionally in renal impairment (CrCl 30-50: max 1000 mg bid; CrCl <30: max 500 mg bid).",
        "before_taking": "Tell your doctor if you have kidney disease (dose adjustment needed), psychiatric history, or are at risk for suicide or self-harm. Monitor for behavioral changes, especially early in treatment. Do not stop levetiracetam abruptly. Levetiracetam has minimal drug interactions — a major advantage over older antiepileptics. Considered relatively safe in pregnancy compared to other antiepileptics.",
    },
    "carbamazepine": {
        "description": "Carbamazepine (Tegretol, Tegretol XR, Carbatrol, Epitol) is an iminostilbene antiepileptic drug and mood stabilizer available as 100 mg chewable tablets, 200 mg tablets, 100-400 mg ER tablets/capsules, and 100 mg/5 mL suspension.",
        "uses": "Carbamazepine is indicated for epilepsy (partial seizures, tonic-clonic seizures, mixed seizure patterns), trigeminal neuralgia, and acute manic and mixed episodes of bipolar I disorder. It is a first-line agent for focal (partial) seizures and trigeminal neuralgia.",
        "warnings": "FDA BOXED WARNINGS: (1) Serious and sometimes fatal dermatological reactions including SJS and TEN. HLA-B*1502 allele (present in some Asian populations) is strongly associated with risk of SJS/TEN — screen Asian patients before initiating. (2) Aplastic anemia and agranulocytosis — perform CBC before initiation and periodically during therapy. Carbamazepine is a potent inducer of CYP3A4 and numerous other drug-metabolizing enzymes — interactions are extensive and clinically significant. Hyponatremia (SIADH) is common. Carbamazepine induces its own metabolism (auto-induction) — serum levels decrease over the first weeks of therapy and stabilize.",
        "side_effects": "Common: drowsiness, dizziness, diplopia, ataxia, nausea, vomiting, hyponatremia. Serious: SJS, TEN, DRESS, aplastic anemia, agranulocytosis, hepatotoxicity, cardiac conduction disturbances, SIADH, teratogenicity (neural tube defects).",
        "dosage": "Epilepsy (adults): Start 200 mg twice daily; increase by 200 mg/day weekly as needed; usual maintenance 800-1200 mg/day in 3-4 divided doses for IR or 2 divided doses for ER. Trigeminal neuralgia: Start 100 mg twice daily; increase by 100 mg every 12 hours; usual maintenance 400-800 mg/day. Bipolar mania: Start 200-400 mg/day; usual range 400-1600 mg/day. Monitor serum levels (therapeutic 4-12 mcg/mL for epilepsy).",
        "before_taking": "Screen for HLA-B*1502 allele in patients of Asian ancestry before initiating. Do not use with MAO inhibitors, or within 14 days of MAO inhibitors. Tell your doctor about liver disease, kidney disease, cardiac conduction problems, glaucoma, blood disorders, or history of bone marrow suppression. Carbamazepine has extensive drug interactions — it significantly reduces levels of many drugs including oral contraceptives, warfarin, certain HIV medications, and numerous others. Teratogenic — associated with neural tube defects; use effective contraception.",
    },
    "insulin glargine": {
        "description": "Insulin glargine (Lantus, Toujeo, Basaglar) is a long-acting insulin analogue that provides a relatively flat, peakless basal insulin profile lasting approximately 24 hours (Lantus/Basaglar) or up to 36 hours (Toujeo 300 U/mL).",
        "uses": "Insulin glargine is indicated to improve glycemic control in adults and pediatric patients ≥6 years with type 1 diabetes mellitus, and adults with type 2 diabetes mellitus who require basal (long-acting) insulin.",
        "warnings": "Hypoglycemia is the most common adverse effect — risk is increased with missed meals, strenuous exercise, excessive dose, renal or hepatic impairment, or concomitant hypoglycemic agents. DO NOT dilute or mix insulin glargine with any other insulin or solution — mixing changes the pharmacokinetic profile and can clog needles. Insulin glargine is NOT for IV use. Use of thiazolidinediones with insulin may result in fluid retention and heart failure. Monitor blood glucose frequently. Lipodystrophy (lipoatrophy or lipohypertrophy) can occur at injection sites — rotate injection sites.",
        "side_effects": "Common: hypoglycemia, injection site reactions (lipodystrophy, pain, redness, swelling), weight gain, peripheral edema. Serious: severe hypoglycemia, hypokalemia (insulin drives potassium intracellularly), anaphylaxis.",
        "dosage": "Type 1 diabetes: Typically 30-50% of total daily insulin requirement as basal insulin; remainder as short/rapid-acting insulin with meals. Type 2 diabetes (new to insulin): 0.1-0.2 units/kg once daily or 10 units once daily; titrate by 2 units every 3 days to fasting glucose target. Administer subcutaneously once daily at any time of day but at the same time each day.",
        "before_taking": "Do not mix with other insulins. Rotate injection sites within the same body region to prevent lipodystrophy. Adjust dose during illness, increased activity, pregnancy, or with changes in diet. Monitor blood glucose regularly; adjust dose as directed. Store unopened vials in refrigerator; opened vials/pens may be stored at room temperature for 28-56 days (product-specific). Hypoglycemia can occur — always have fast-acting glucose available. Inform your doctor if you are pregnant (insulin requirements change significantly during pregnancy).",
    },
    "naloxone": {
        "description": "Naloxone (Narcan, Kloxxado, RiVive) is a pure opioid antagonist that rapidly reverses opioid overdose. Available as nasal spray (4 mg, 8 mg), auto-injector (0.4 mg/0.4 mL), and IV/IM/SC injection. Narcan nasal spray 4 mg is available OTC.",
        "uses": "Naloxone is indicated for complete or partial reversal of opioid depression, including respiratory depression, induced by natural or synthetic opioids. Used in emergency management of opioid overdose. Also available as a take-home rescue medication for patients on opioids and their family members.",
        "warnings": "Naloxone precipitates acute withdrawal in opioid-dependent patients (nausea, vomiting, diaphoresis, tachycardia, hypertension, seizures — generally not life-threatening, but cardiovascular events have occurred with abrupt reversal). Duration of action of many opioids exceeds naloxone duration (30-90 minutes for naloxone) — always seek emergency medical care after using naloxone; repeated doses may be needed, especially with long-acting opioids (methadone, fentanyl patches). In neonates with opioid withdrawal, abrupt reversal can cause seizures.",
        "side_effects": "Common (due to precipitated withdrawal): nausea, vomiting, diaphoresis, tachycardia, hypertension, agitation, irritability. Serious: pulmonary edema, cardiac arrhythmias, and hypertension (with abrupt reversal of opioid in opioid-dependent patients).",
        "dosage": "Opioid overdose (Narcan nasal spray): 4 mg intranasal in one nostril; if no response, give second dose after 2-3 minutes in other nostril; repeat as needed. Always call 911. Opioid overdose (IV/IM/SC): 0.4-2 mg IV/IM/SC every 2-3 minutes as needed; maximum 10 mg. Suspected opioid overdose in children: 0.01 mg/kg IV/IM; repeat as needed.",
        "before_taking": "Naloxone is only indicated for opioid overdose — it does not work for non-opioid overdose (e.g., benzodiazepines, alcohol). After using naloxone, always call 911 immediately — the person may need repeated doses and ongoing medical care. Naloxone is safe to use even if you are unsure whether opioids are involved. Naloxone is now available without a prescription (OTC) in all U.S. states. People on opioid therapy should have naloxone available at home.",
    },
    "buprenorphine": {
        "description": "Buprenorphine is a partial opioid agonist (Schedule III controlled substance) available as sublingual/buccal films and tablets (Suboxone with naloxone, Subutex alone), extended-release injectable (Sublocade, Brixtra), and transdermal patch (Butrans) for chronic pain.",
        "uses": "Buprenorphine (with naloxone — Suboxone, Zubsolv) is indicated for opioid use disorder (OUD) as a medication-assisted treatment (MAT), to suppress opioid withdrawal symptoms and cravings. Buprenorphine alone (Subutex) is used in pregnancy for OUD. Sublocade (monthly injectable) is for OUD maintenance. Butrans transdermal patch is for chronic pain requiring around-the-clock opioid analgesia.",
        "warnings": "As a partial opioid agonist with high receptor affinity, buprenorphine can precipitate opioid withdrawal if given to opioid-dependent patients who have not yet entered moderate withdrawal — COWS (Clinical Opiate Withdrawal Scale) ≥8 required before first dose. Buprenorphine has a 'ceiling effect' on respiratory depression, making it safer than full agonists, but high doses combined with CNS depressants (benzodiazepines, alcohol) can still cause respiratory depression and death. Neonatal opioid withdrawal syndrome occurs with use during pregnancy.",
        "side_effects": "Common: nausea, constipation, headache, diaphoresis, insomnia, sublingual numbness/burning. Serious: respiratory depression (with CNS depressants), precipitated withdrawal (if given too early), hepatotoxicity (rare), allergic reactions.",
        "dosage": "OUD (Suboxone): Induction: start with 2 mg/0.5 mg or 4 mg/1 mg after moderate withdrawal (COWS ≥8); total day 1 dose 8 mg/2 mg sublingual. Maintenance: 16 mg/4 mg once daily; range 4-24 mg/day. Sublocade: 300 mg SC monthly × 2 months, then 100 mg SC monthly. Pain (Butrans transdermal): 5-20 mcg/hr patch weekly.",
        "before_taking": "For OUD: Do not take first dose until you are in moderate opioid withdrawal (COWS ≥8) to avoid precipitated withdrawal. Tell your doctor about liver disease, respiratory problems, benzodiazepine use or addiction, and all medications. Do not combine with benzodiazepines, alcohol, or CNS depressants. Buprenorphine is the preferred treatment for OUD in pregnancy (versus methadone — individual circumstances vary). Buprenorphine is now available without a special DEA waiver from any licensed prescriber.",
    },
    "oseltamivir": {
        "description": "Oseltamivir (Tamiflu) is an oral neuraminidase inhibitor antiviral active against influenza A and B viruses. Available as 30, 45, and 75 mg capsules and 6 mg/mL oral suspension.",
        "uses": "Oseltamivir is indicated for treatment of acute, uncomplicated influenza in patients 14 days and older who have been symptomatic for no more than 48 hours, and for prophylaxis of influenza in patients 1 year and older. For treatment to be effective, it must be started within 48 hours of symptom onset. It is also used off-label in severe or hospitalized influenza regardless of symptom duration.",
        "warnings": "Benefit of treatment is most pronounced when started within 24-48 hours of symptom onset. Neuropsychiatric events including self-injury and delirium have been reported in patients with influenza receiving oseltamivir, particularly in pediatric patients — although causal relationship is unclear. Live attenuated influenza vaccine (FluMist) should not be given within 2 weeks before or 48 hours after oseltamivir use. Bacterial superinfection may occur with influenza — oseltamivir has no antibacterial activity.",
        "side_effects": "Common: nausea, vomiting (improved if taken with food), headache, abdominal pain. Serious: neuropsychiatric events (delirium, self-injury — mechanism unclear), hepatitis, severe skin reactions (SJS, erythema multiforme — very rare).",
        "dosage": "Treatment (adults and adolescents ≥13 years): 75 mg twice daily for 5 days, starting within 48 hours of symptom onset. Treatment (children 1-12 years): weight-based dosing (30-75 mg twice daily). Prophylaxis (adults and adolescents ≥13 years): 75 mg once daily for at least 10 days (postexposure) or throughout community outbreak period (up to 6 weeks). Take with or without food; taking with food reduces nausea.",
        "before_taking": "Tell your doctor if you have kidney disease (dose reduction required for CrCl <60 mL/min). Start within 48 hours of flu symptom onset for treatment to be effective. Take with food or milk if nausea occurs. Do not use live attenuated influenza vaccine within 2 weeks before or 48 hours after oseltamivir. Report any unusual behavior or self-injury in patients (especially children) taking oseltamivir.",
    },
    "warfarin": {
        "description": "Warfarin (Coumadin, Jantoven) is an oral vitamin K antagonist anticoagulant. It inhibits the synthesis of vitamin K-dependent clotting factors (II, VII, IX, X) and anticoagulant proteins C and S. Requires regular INR monitoring.",
        "uses": "Warfarin is indicated for prophylaxis and treatment of venous thrombosis and pulmonary embolism, atrial fibrillation with risk of embolism, prevention of thromboembolic complications with cardiac valve replacement, and reduction of risk of death, recurrent MI, and thromboembolic events after MI.",
        "warnings": "FDA BOXED WARNING: Bleeding risk including life-threatening hemorrhage. Risk factors for bleeding include high intensity anticoagulation (INR >4), advanced age, uncontrolled hypertension, cerebrovascular disease, prior bleeding, and concomitant antiplatelet agents or NSAIDs. Warfarin has extensive drug and food interactions — hundreds of medications alter INR, and vitamin K intake significantly affects anticoagulation. Genetic polymorphisms in CYP2C9 (metabolism) and VKORC1 (target) affect dose requirements. Tissue necrosis and skin necrosis (warfarin-induced skin necrosis) can occur, particularly in patients with protein C or S deficiency. Warfarin crosses the placenta and is TERATOGENIC — contraindicated in pregnancy. Carry a medical alert card.",
        "side_effects": "Common: bleeding at any site, bruising, nausea, abdominal pain. Serious: major hemorrhage (intracranial, GI, retroperitoneal), warfarin-induced skin necrosis, purple toe syndrome, cholesterol microembolism.",
        "dosage": "Initial dose is highly patient-specific; typical starting dose 2-5 mg/day. Adjust dose based on target INR: most indications INR 2.0-3.0; mechanical heart valves 2.5-3.5. Monitor INR regularly (weekly at initiation, then monthly when stable). Lower starting doses (1-2 mg/day) in elderly, Asian patients, or those with hepatic impairment or bleeding risk.",
        "before_taking": "Tell your doctor about all prescription and OTC medications, vitamins, supplements, and herbal products — hundreds of drugs interact with warfarin. Maintain a consistent dietary vitamin K intake (do not drastically change intake of leafy greens). Avoid alcohol excess. Tell your doctor if you are pregnant or planning pregnancy — warfarin is teratogenic and is contraindicated in pregnancy (use heparin or LMWH instead). Get INR checked as scheduled. Inform all healthcare providers (including dentists) that you take warfarin.",
    },
    "adalimumab": {
        "description": "Adalimumab (Humira) is a fully human monoclonal antibody that targets tumor necrosis factor-alpha (TNF-α), a cytokine involved in systemic inflammation. Available as prefilled syringes and pens (10-40 mg). After the expiration of Humira's US exclusivity, multiple biosimilars are now available.",
        "uses": "Adalimumab is indicated for moderate-to-severe rheumatoid arthritis, psoriatic arthritis, ankylosing spondylitis, moderate-to-severe Crohn's disease, ulcerative colitis, moderate-to-severe plaque psoriasis, hidradenitis suppurativa, non-infectious intermediate, posterior, and panuveitis, and juvenile idiopathic arthritis.",
        "warnings": "FDA BOXED WARNINGS: (1) Serious infections — patients treated with adalimumab are at increased risk for developing serious infections including tuberculosis, bacterial sepsis, invasive fungal infections, and other opportunistic infections. Discontinue if a serious infection develops. Screen for latent TB before initiating and treat if detected. (2) Malignancy — lymphoma and other malignancies, some fatal, have been reported. Hepatosplenic T-cell lymphoma (HSTCL) has occurred mainly in adolescent and young adult males with Crohn's disease or ulcerative colitis treated with TNF blockers in combination with azathioprine or 6-mercaptopurine. Do not use adalimumab in patients with active infections. Reactivation of hepatitis B has occurred; screen for HBV before use. New or worsening heart failure has been reported. Demyelinating disease (optic neuritis, multiple sclerosis) has been reported.",
        "side_effects": "Common: injection site reactions, upper respiratory tract infections, headache, rash, sinusitis, nausea. Serious: serious infections (sepsis, TB, invasive fungal infections), malignancies (lymphoma, HSTCL), demyelinating disorders, heart failure worsening, hepatitis B reactivation, autoimmune reactions (lupus-like syndrome), severe allergic reactions.",
        "dosage": "Rheumatoid arthritis: 40 mg every other week SC (subcutaneous); may increase to 40 mg weekly if inadequate response and not on methotrexate. Crohn's disease: 160 mg SC on day 1 (4 injections), then 80 mg on day 15, then 40 mg every other week starting day 29. Plaque psoriasis: 80 mg SC initially, then 40 mg every other week starting 1 week after initial dose. Dosing varies by indication.",
        "before_taking": "Screen for latent TB before starting adalimumab. Test for HBV infection before initiating. Do not start if you have an active infection. Update all vaccinations before starting (no live vaccines during therapy). Tell your doctor if you have history of recurrent infections, TB exposure, heart failure, demyelinating disease, liver disease, lymphoma, or psoriasis worsening. Adalimumab is compatible with pregnancy for many indications.",
    },
    "celecoxib": {
        "description": "Celecoxib (Celebrex) is a selective cyclooxygenase-2 (COX-2) inhibitor NSAID available as 50, 100, 200, and 400 mg capsules. Unlike non-selective NSAIDs, celecoxib has reduced GI toxicity at therapeutic doses.",
        "uses": "Celecoxib is indicated for relief of signs and symptoms of osteoarthritis, rheumatoid arthritis, ankylosing spondylitis, acute pain in adults, primary dysmenorrhea, and familial adenomatous polyposis (reduction of polyp formation).",
        "warnings": "FDA BOXED WARNINGS: (1) Cardiovascular risk — NSAIDs including celecoxib increase the risk of serious thrombotic events, MI, and stroke (can be fatal). Risk is increased with longer duration of use and higher doses. Contraindicated for CABG surgery peri-operative pain. (2) GI risk — NSAIDs can cause serious GI adverse events including bleeding, ulceration, and perforation, which can be fatal. Celecoxib has lower GI toxicity than non-selective NSAIDs but risk is not zero. Avoid in patients with sulfonamide allergy (celecoxib contains a sulfonamide moiety). Fluid retention, edema, and worsening hypertension occur. Renal toxicity can occur in patients with volume depletion or on diuretics/ACE inhibitors/ARBs.",
        "side_effects": "Common: dyspepsia, diarrhea, abdominal pain, nausea, headache, dizziness, fluid retention, hypertension. Serious: MI, stroke, GI perforation/bleeding/ulceration, renal failure, hepatotoxicity, severe skin reactions (SJS, TEN), anaphylaxis.",
        "dosage": "Osteoarthritis: 200 mg once daily or 100 mg twice daily. Rheumatoid arthritis: 100-200 mg twice daily. Acute pain/dysmenorrhea: 400 mg initially, then 200 mg twice daily as needed. Ankylosing spondylitis: 200 mg once daily; may increase to 400 mg daily. Familial adenomatous polyposis: 400 mg twice daily with food.",
        "before_taking": "Contraindicated in sulfonamide allergy, peri-operative CABG pain, and active GI bleeding. Tell your doctor about cardiovascular disease, heart failure, hypertension, kidney disease, liver disease, dehydration, asthma, aspirin-exacerbated respiratory disease, or bleeding disorders. Avoid alcohol. Do not use during pregnancy (especially third trimester — premature closure of ductus arteriosus). Celecoxib interacts with warfarin, lithium, ACE inhibitors, ARBs, and furosemide.",
    },
    "cephalexin": {
        "description": "Cephalexin (Keflex) is a first-generation oral cephalosporin antibiotic available as 250, 333, 500, and 750 mg capsules and 125 mg/5 mL and 250 mg/5 mL oral suspension.",
        "uses": "Cephalexin is indicated for respiratory tract infections, otitis media, skin and skin structure infections, bone infections, and genitourinary tract infections caused by susceptible organisms. It is commonly used for uncomplicated skin and soft tissue infections (including cellulitis), streptococcal pharyngitis, and urinary tract infections.",
        "warnings": "Use with caution in patients with penicillin allergy — approximately 1-2% cross-reactivity. Contraindicated in known hypersensitivity to cephalosporins. Clostridium difficile-associated diarrhea has been reported. Renal impairment may require dose reduction. Cephalexin may reduce the effectiveness of oral contraceptives.",
        "side_effects": "Common: diarrhea, nausea, vomiting, dyspepsia, abdominal pain. Less common: headache, agitation, confusion (rare). Serious: anaphylaxis (cross-reactivity with penicillin), Clostridioides difficile colitis, hemolytic anemia, renal toxicity (rare).",
        "dosage": "Adults: 250-500 mg every 6 hours or 500 mg every 12 hours depending on infection. Strep pharyngitis: 500 mg twice daily for 10 days. Skin/soft tissue: 500 mg every 12 hours for 7 days. Children: 25-50 mg/kg/day in 2-4 divided doses. Take with or without food.",
        "before_taking": "Tell your doctor if you have penicillin allergy (small cross-reactivity risk), kidney disease, intestinal disease (colitis), or are pregnant or breastfeeding (generally considered safe). Tell your doctor about all medications — cephalexin may interact with probenecid, metformin, and may reduce oral contraceptive effectiveness (use backup contraception).",
    },
    "citalopram": {
        "description": "Citalopram (Celexa) is a selective serotonin reuptake inhibitor (SSRI) antidepressant available as 10, 20, and 40 mg tablets and 10 mg/5 mL oral solution.",
        "uses": "Citalopram is FDA-approved for treatment of major depressive disorder (MDD) in adults. It is also widely used off-label for generalized anxiety disorder, panic disorder, obsessive-compulsive disorder, and post-traumatic stress disorder.",
        "warnings": "FDA BOXED WARNING: Antidepressants increased the risk of suicidal thinking and behavior (suicidality) in children, adolescents, and young adults (ages 18-24) in short-term studies of major depressive disorder and other psychiatric disorders. Monitor for worsening depression, suicidal ideation, or unusual changes in behavior, especially during the first few months. Citalopram causes dose-dependent QT interval prolongation — maximum recommended dose is 40 mg/day (20 mg/day in patients over 60 years, with hepatic impairment, or on CYP2C19 inhibitors such as omeprazole). Serotonin syndrome can occur, especially with MAO inhibitors or other serotonergic agents. Do not use with MAO inhibitors; allow at least 14 days between stopping MAO inhibitor and starting citalopram.",
        "side_effects": "Common: nausea, diarrhea, dry mouth, somnolence, insomnia, diaphoresis, tremor, dizziness, sexual dysfunction (decreased libido, delayed orgasm, erectile dysfunction). Serious: serotonin syndrome, QT prolongation/torsades de pointes, SIADH/hyponatremia (especially in elderly), abnormal bleeding, mania in bipolar disorder.",
        "dosage": "Adults: Start 20 mg once daily; may increase to 40 mg once daily after at least 1 week. Maximum 40 mg/day. Over 60 years, hepatic impairment, or on CYP2C19 inhibitors: maximum 20 mg/day. Give once daily, morning or evening. Antidepressant effect typically requires 1-4 weeks.",
        "before_taking": "Do not take with MAO inhibitors (allow 14 days washout). Tell your doctor about bipolar disorder, seizure disorder, kidney or liver disease, bleeding disorders, QT prolongation, hyponatremia, or glaucoma. Tell your doctor about all medications — especially NSAIDs, warfarin, triptans, lithium, tramadol, and other serotonergic agents. Do not abruptly stop citalopram — taper to avoid discontinuation syndrome. Tell your doctor if pregnant or breastfeeding.",
    },
    "clarithromycin": {
        "description": "Clarithromycin (Biaxin, Biaxin XL) is a macrolide antibiotic and potent CYP3A4 inhibitor available as 250 and 500 mg tablets, extended-release 500 mg tablets (Biaxin XL), and 125 mg/5 mL and 250 mg/5 mL oral suspension.",
        "uses": "Clarithromycin is indicated for pharyngitis/tonsillitis, acute maxillary sinusitis, acute bacterial exacerbations of chronic bronchitis, community-acquired pneumonia, uncomplicated skin and skin structure infections, H. pylori eradication (in combination), disseminated Mycobacterium avium complex (MAC) disease in HIV patients, and acute otitis media.",
        "warnings": "Clarithromycin is a potent CYP3A4 inhibitor — extensive drug interactions (increases levels of many drugs including statins, increasing rhabdomyolysis risk; benzodiazepines; colchicine; certain antiarrhythmics). QT interval prolongation and cardiac arrhythmias (torsades de pointes) have been reported. Hepatotoxicity including hepatic necrosis and failure has occurred. Avoid in patients with known QT prolongation or on Class IA or III antiarrhythmics. Exacerbation of myasthenia gravis has been reported. Clarithromycin is teratogenic in animal studies — avoid in the first trimester of pregnancy.",
        "side_effects": "Common: diarrhea, nausea, abnormal taste (metallic/bitter), abdominal pain, dyspepsia, headache. Serious: QT prolongation, hepatotoxicity, Clostridioides difficile colitis, severe skin reactions, exacerbation of myasthenia gravis.",
        "dosage": "Pharyngitis: 250 mg twice daily for 10 days. Community-acquired pneumonia: 250-500 mg twice daily for 7-14 days (IR) or 1000 mg once daily for 7 days (XL). H. pylori (triple therapy): 500 mg twice daily for 10-14 days with amoxicillin and PPI. MAC prophylaxis in HIV: 500 mg twice daily. Take with or without food (XL tablet: take with food).",
        "before_taking": "Do not use in patients with known QT prolongation or on drugs that prolong QT interval. Tell your doctor about liver or kidney disease, myasthenia gravis, and all medications — clarithromycin is a potent CYP3A4 inhibitor with numerous clinically significant interactions. Avoid high-dose statins (simvastatin, lovastatin) during clarithromycin therapy (rhabdomyolysis risk). Do not use in first trimester of pregnancy.",
    },
    "clindamycin": {
        "description": "Clindamycin (Cleocin) is a lincosamide antibiotic active against gram-positive organisms and anaerobes. Available as 75, 150, and 300 mg oral capsules, 75 mg/5 mL oral solution, vaginal cream/ovule, and topical gel/lotion/solution.",
        "uses": "Clindamycin is indicated for serious infections caused by susceptible anaerobic bacteria and susceptible gram-positive organisms, including pneumonia, septicemia, intra-abdominal infections, female pelvic/genital tract infections, bone and joint infections, and skin and soft tissue infections. It is commonly used for community-acquired MRSA skin infections, pelvic inflammatory disease, and (topically) for bacterial vaginosis and acne.",
        "warnings": "FDA BOXED WARNING: Clostridium difficile-associated diarrhea (CDAD) — clindamycin has one of the highest rates of C. diff infection of any antibiotic. CDAD has been observed up to 2 months post-antibiotic treatment. If diarrhea occurs, consider CDAD. Discontinue clindamycin and initiate appropriate therapy if CDAD is confirmed. Do not use clindamycin for trivial infections. Use clindamycin for serious infections only.",
        "side_effects": "Common: diarrhea, abdominal pain, nausea, vomiting, metallic taste (IV). Serious: CDAD (potentially life-threatening), anaphylaxis, severe skin reactions (SJS, TEN), esophageal ulceration (capsules — take with full glass of water).",
        "dosage": "Serious infections (oral): 150-450 mg every 6 hours. MRSA skin infection: 300-450 mg three times daily for 5-7 days. Bacterial vaginosis (vaginal cream): one applicatorful intravaginally once daily for 3-7 days. Bacterial vaginosis (ovule): one ovule intravaginally once at bedtime for 3 days. Acne (topical): apply thin film twice daily.",
        "before_taking": "Tell your doctor about a history of antibiotic-associated colitis or GI disease. Take oral capsules with a full glass of water to prevent esophageal irritation. Report diarrhea immediately — it may signal C. diff infection. Clindamycin is generally considered safe in pregnancy and is used for bacterial vaginosis treatment during pregnancy. Tell your doctor about kidney or liver disease.",
    },
    "amitriptyline": {
        "description": "Amitriptyline (Elavil — brand discontinued, generics available) is a tricyclic antidepressant (TCA) with sedating, anticholinergic, and norepinephrine/serotonin reuptake inhibitory properties. Available as 10, 25, 50, 75, 100, and 150 mg tablets.",
        "uses": "Amitriptyline is FDA-approved for treatment of major depressive disorder. Off-label uses (extensive): neuropathic pain (diabetic neuropathy, postherpetic neuralgia), migraine prophylaxis, fibromyalgia, interstitial cystitis, functional GI disorders (IBS), insomnia, and chronic low back pain. Often used at low doses (10-25 mg) for pain and sleep even when doses required for depression (150-300 mg) would not be tolerated.",
        "warnings": "FDA BOXED WARNING: Antidepressants increase suicidal risk in children, adolescents, and young adults. TCAs can be lethal in overdose — cardiotoxic (wide-complex tachycardia, QRS widening, ventricular arrhythmias). Do not prescribe large quantities. Potent anticholinergic effects — contraindicated in acute narrow-angle glaucoma, urinary retention, and myocardial infarction recovery. Significant QT prolongation. Do not use with MAO inhibitors (hypertensive crisis, serotonin syndrome).",
        "side_effects": "Common: sedation (significant), dry mouth, constipation, urinary retention, blurred vision, weight gain, orthostatic hypotension, tachycardia, sexual dysfunction. Serious: cardiac arrhythmias (especially with overdose), seizures, confusion/delirium (especially in elderly), serotonin syndrome (with serotonergic drugs).",
        "dosage": "Depression: Start 25-75 mg/day at bedtime; increase gradually to 150-300 mg/day. Neuropathic pain/migraine prophylaxis: 10-75 mg at bedtime. Insomnia: 10-25 mg at bedtime. Elderly: Start 10 mg at bedtime; do not exceed 100 mg/day (Beers Criteria — amitriptyline is generally inappropriate in elderly patients due to high anticholinergic burden).",
        "before_taking": "Not recommended for elderly patients due to high anticholinergic burden (Beers Criteria). Contraindicated with MAO inhibitors, in the acute recovery period after MI, or in patients with narrow-angle glaucoma, urinary retention, or significant cardiac conduction disease. Tell your doctor about seizure disorder, thyroid disease, liver disease, prostate problems, and all medications. Do not abruptly discontinue — taper to avoid withdrawal. Avoid alcohol.",
    },
    "colchicine": {
        "description": "Colchicine (Colcrys, Mitigare, Gloperba) is an anti-inflammatory alkaloid derived from the autumn crocus plant. Available as 0.6 mg tablets and 0.6 mg/5 mL oral solution.",
        "uses": "Colchicine is indicated for prophylaxis and treatment of acute gout flares, and for treatment of familial Mediterranean fever (FMF) in adults and children ≥4 years. Off-label uses include pericarditis (acute and prevention of recurrence), periocarditis, and Behçet's disease.",
        "warnings": "Fatal colchicine toxicity has occurred with therapeutic doses in patients with renal or hepatic impairment and in patients on P-glycoprotein (P-gp) or strong CYP3A4 inhibitors (e.g., clarithromycin, cyclosporine, ketoconazole). Bone marrow suppression (leukopenia, aplastic anemia, thrombocytopenia) can occur. Neuromuscular toxicity (myopathy, neuropathy) has been reported. AVOID concurrent use with P-gp or strong CYP3A4 inhibitors in patients with renal or hepatic impairment — can be fatal. Dose adjustment required in renal or hepatic impairment.",
        "side_effects": "Common: diarrhea, nausea, vomiting, abdominal cramping. Serious: bone marrow suppression (leukopenia, agranulocytosis, thrombocytopenia), neuromuscular toxicity (myopathy, neuropathy), multi-organ failure and death (in overdose or with inhibitor interactions in renally impaired patients).",
        "dosage": "Acute gout flare: 1.2 mg at first sign of flare, then 0.6 mg 1 hour later (maximum 1.8 mg over 1 hour); wait at least 3 days before repeat. Gout prophylaxis: 0.6 mg once or twice daily. FMF: 1.2-2.4 mg/day in 1-2 doses. Dose reduction in renal impairment and with P-gp or CYP3A4 inhibitors.",
        "before_taking": "Tell your doctor if you have kidney disease, liver disease, or blood disorders. Tell your doctor about ALL medications — especially clarithromycin, cyclosporine, ketoconazole, azithromycin, verapamil, and statins (increased rhabdomyolysis risk). Do not use with strong CYP3A4 inhibitors or P-gp inhibitors if you have renal or hepatic impairment. Monitor CBC with long-term use.",
    },
    "cyclobenzaprine": {
        "description": "Cyclobenzaprine (Flexeril, Amrix) is a centrally-acting skeletal muscle relaxant structurally related to tricyclic antidepressants. Available as 5 and 10 mg tablets and 15 and 30 mg extended-release capsules.",
        "uses": "Cyclobenzaprine is indicated as an adjunct to rest and physical therapy for relief of muscle spasm associated with acute, painful musculoskeletal conditions. It is not indicated for spasticity associated with spinal cord disease or cerebral palsy.",
        "warnings": "Cyclobenzaprine has significant anticholinergic and CNS-depressant effects — similar concerns as TCAs. Do not use with MAO inhibitors (may cause serious adverse reactions including hyperpyrexia, convulsions, death). QT interval prolongation can occur. Use with extreme caution in patients with urinary retention, angle-closure glaucoma, arrhythmias, hyperthyroidism, or heart block. Sedation is prominent — do not drive or operate machinery. Use for no more than 2-3 weeks.",
        "side_effects": "Common: drowsiness (very common), dry mouth, dizziness, fatigue, constipation, blurred vision, headache. Serious: cardiac arrhythmias, serotonin syndrome (with serotonergic drugs), anticholinergic effects, confusion/delirium (especially in elderly — Beers Criteria potentially inappropriate).",
        "dosage": "Acute musculoskeletal pain: 5 mg three times daily; may increase to 10 mg three times daily. ER capsules: 15 mg once daily; may increase to 30 mg once daily. Use for a maximum of 2-3 weeks; not established for longer use.",
        "before_taking": "Do not use with MAO inhibitors. Avoid in elderly patients (Beers Criteria — anticholinergic burden, sedation, fall risk). Tell your doctor about heart disease, thyroid disorders, glaucoma, urinary retention, liver disease, or seizure history. Avoid alcohol and other CNS depressants. Do not drive or operate heavy machinery. Not for long-term use.",
    },
    "allopurinol": {
        "description": "Allopurinol (Zyloprim) is a xanthine oxidase inhibitor that reduces serum uric acid levels by blocking uric acid synthesis. Available as 100 mg and 300 mg tablets.",
        "uses": "Allopurinol is indicated for management of gout and prevention of hyperuricemia associated with gout, leukemia, lymphoma, and solid tumor malignancies undergoing chemotherapy. It is a first-line agent for chronic gout management and prevention of gout flares.",
        "warnings": "Serious and potentially fatal skin reactions including Stevens-Johnson syndrome (SJS) and toxic epidermal necrolysis (TEN) have been reported. Risk is increased in patients with HLA-B*5801 allele (common in Han Chinese, Thai, and Korean populations) — genetic screening is recommended in these populations before initiating allopurinol. Do not initiate allopurinol during an acute gout flare — wait until the flare has resolved. Initiating allopurinol can precipitate acute gout flares early in therapy — use prophylactic colchicine or low-dose NSAID during the first 3-6 months. Reduce dose in renal impairment.",
        "side_effects": "Common: skin rash (can be first sign of serious reaction — discontinue immediately), gout flares (early in therapy), nausea, diarrhea. Serious: SJS, TEN, DRESS, vasculitis, bone marrow suppression, hepatotoxicity, renal failure.",
        "dosage": "Gout: Start 100 mg once daily; increase by 100 mg every 1-4 weeks until serum uric acid <6 mg/dL (target <5 mg/dL in tophaceous gout); usual maintenance 200-300 mg/day for mild gout, 400-600 mg/day for moderate-severe gout; maximum 800 mg/day. Take after meals. Tumor lysis prophylaxis: 600-800 mg/day in divided doses for 2-3 days.",
        "before_taking": "Do not start during an active gout flare. Test for HLA-B*5801 in patients of Han Chinese, Thai, or Korean descent before starting. Tell your doctor about kidney disease (dose reduction required), liver disease, or heart failure. Tell your doctor about all medications — allopurinol significantly increases the toxicity of azathioprine and 6-mercaptopurine (reduce dose by 67-75%); also interacts with ampicillin/amoxicillin (increased rash risk) and warfarin.",
    },
    "amiodarone": {
        "description": "Amiodarone (Pacerone, Cordarone) is a class III antiarrhythmic drug with complex pharmacology (also has class I, II, and IV activity). It has an extremely long half-life (40-55 days) and significant multi-organ toxicity profile. Available as 100 and 200 mg tablets and IV formulation.",
        "uses": "Amiodarone is indicated for life-threatening recurrent ventricular fibrillation and hemodynamically unstable ventricular tachycardia that do not respond to other antiarrhythmics. It is used off-label for atrial fibrillation rate and rhythm control. Due to toxicity, it is generally reserved for refractory arrhythmias when other agents have failed.",
        "warnings": "FDA BOXED WARNINGS: (1) Pulmonary toxicity — amiodarone causes potentially fatal pulmonary toxicity in 10-17% of patients. Baseline and periodic pulmonary function testing and chest X-ray required. (2) Hepatotoxicity — liver damage with hepatocellular necrosis, cirrhosis, and death have occurred. Monitor LFTs. (3) Proarrhythmia — amiodarone can cause new or worsened arrhythmias. Multiple serious organ toxicities require monitoring: thyroid dysfunction (both hypo- and hyperthyroidism), corneal microdeposits (in virtually all patients), optic neuropathy/neuritis (can lead to blindness), peripheral neuropathy, and photosensitivity. Extensive drug interactions — amiodarone inhibits CYP2C9, CYP2D6, CYP3A4, and P-gp, dramatically increasing levels of many drugs (warfarin, digoxin, statins, many others).",
        "side_effects": "Common: photosensitivity, nausea, vomiting, corneal microdeposits, tremor, ataxia, peripheral neuropathy, thyroid dysfunction. Serious: pulmonary toxicity, hepatotoxicity, proarrhythmia, optic neuritis/neuropathy, hypo-/hyperthyroidism.",
        "dosage": "Ventricular arrhythmia (oral): Loading dose 800-1600 mg/day in 2-3 doses for 1-3 weeks; then 600-800 mg/day for 1 month; maintenance 200-400 mg/day. IV (in-hospital): 150 mg over 10 minutes, then 360 mg over 6 hours, then 540 mg over next 18 hours. Atrial fibrillation (off-label): 200 mg once daily.",
        "before_taking": "Amiodarone should only be used for life-threatening arrhythmias when other treatments fail. Requires baseline chest X-ray, pulmonary function tests, LFTs, thyroid function tests (TSH), and ophthalmologic exam, with periodic monitoring. Tell your doctor about liver disease, thyroid disease, lung disease, and all medications (extensive interactions). Amiodarone reduces warfarin dose requirement by 30-50% and increases digoxin levels. Avoid sun exposure or use protective clothing/sunscreen.",
    },
    "dexamethasone": {
        "description": "Dexamethasone is a potent, long-acting synthetic glucocorticoid corticosteroid approximately 25 times more potent than hydrocortisone with minimal mineralocorticoid activity. Available as 0.5, 0.75, 1, 1.5, 2, 4, and 6 mg tablets and oral solution, topical cream/ointment, ophthalmic, and injectable formulations.",
        "uses": "Dexamethasone is used for many inflammatory and autoimmune conditions: allergic states, cerebral edema, rheumatic disorders, collagen diseases, dermatological conditions, respiratory diseases (asthma, COPD exacerbations), endocrine disorders, GI and hematologic disorders, neoplastic diseases, and shock. It is used for COVID-19 in patients requiring supplemental oxygen. Also used in the dexamethasone suppression test for Cushing's syndrome diagnosis and for fetal lung maturation in preterm labor.",
        "warnings": "Long-term corticosteroid use causes HPA-axis suppression and adrenal insufficiency — do not stop abruptly after prolonged use (taper to prevent adrenal crisis). Corticosteroids can mask signs of infection and impair immune response. Risk of opportunistic infections including reactivation of tuberculosis, herpes, and disseminated varicella. Serious adverse effects with long-term use: osteoporosis (supplement calcium and vitamin D), avascular necrosis (especially femoral head), Cushing's syndrome, peptic ulcer, hyperglycemia, psychiatric disturbances (psychosis, mood changes), growth suppression in children, cataracts, and glaucoma.",
        "side_effects": "Short-term: hyperglycemia, insomnia, mood changes (euphoria, anxiety, psychosis), increased appetite, weight gain, fluid retention. Long-term: Cushingoid appearance, osteoporosis, avascular necrosis, adrenal suppression, immunosuppression, cataracts, glaucoma, peptic ulcer, growth suppression.",
        "dosage": "Dosing is highly variable by indication. Anti-inflammatory (adults): 0.75-9 mg/day in 2-4 divided doses. Cerebral edema: 10 mg IV initially, then 4 mg IV every 6 hours. COVID-19: 6 mg once daily for up to 10 days. Fetal lung maturation: 6 mg IM every 12 hours for 4 doses.",
        "before_taking": "Tell your doctor about any active or recent infections, diabetes (corticosteroids raise blood glucose), osteoporosis, peptic ulcer, glaucoma, psychiatric history, or heart disease. Do not receive live vaccines while on immunosuppressive doses. Do not stop abruptly after prolonged use — taper under medical supervision. Monitor blood glucose, blood pressure, and bone density with long-term use. Take with food to reduce GI upset.",
    },
    "diltiazem": {
        "description": "Diltiazem (Cardizem, Tiazac, Cartia XT) is a non-dihydropyridine calcium channel blocker (benzothiazepine class) that reduces heart rate, slows AV conduction, and relaxes vascular smooth muscle. Available as immediate-release tablets (30, 60, 90, 120 mg) and multiple extended-release formulations.",
        "uses": "Diltiazem is indicated for angina pectoris (stable and vasospastic/Prinzmetal's), hypertension, and atrial fibrillation/atrial flutter (rate control). IV diltiazem is used for acute rate control in atrial fibrillation and for converting paroxysmal supraventricular tachycardia.",
        "warnings": "Contraindicated in sick sinus syndrome (without pacemaker), second- or third-degree AV block (without pacemaker), atrial fibrillation or flutter associated with accessory bypass tract (e.g., WPW syndrome), severe hypotension, and acute MI with pulmonary congestion. Can worsen heart failure. Diltiazem is a moderate CYP3A4 inhibitor — significant drug interactions (increases levels of cyclosporine, tacrolimus, statins, carbamazepine, digoxin, and many others). Monitor heart rate and blood pressure.",
        "side_effects": "Common: headache, dizziness, edema (lower extremity), bradycardia, first-degree AV block, flushing, nausea, rash. Serious: second/third-degree AV block, severe bradycardia, heart failure exacerbation, hepatotoxicity (rare), severe skin reactions.",
        "dosage": "Hypertension (ER): 120-240 mg once daily; maximum 540 mg/day. Angina (ER): 120-320 mg once daily. Rate control in AF (oral, ER): 120-360 mg/day. IV rate control: 0.25 mg/kg IV bolus over 2 minutes; may repeat 0.35 mg/kg after 15 minutes; followed by 5-15 mg/hr infusion.",
        "before_taking": "Tell your doctor about heart failure, conduction defects, liver disease, and all medications. Diltiazem inhibits CYP3A4 — avoid high-dose statins (simvastatin, lovastatin), and adjust doses of cyclosporine, tacrolimus, and other CYP3A4 substrates. Do not use grapefruit juice. Diltiazem is category C in pregnancy.",
    },
    "digoxin": {
        "description": "Digoxin (Lanoxin) is a cardiac glycoside derived from Digitalis lanata. It has a narrow therapeutic index and requires careful monitoring of serum levels. Available as 0.0625, 0.125, and 0.25 mg tablets, oral solution, and injection.",
        "uses": "Digoxin is indicated for heart failure (to improve symptoms and reduce hospitalizations, primarily as adjunctive therapy) and for ventricular rate control in atrial fibrillation. It is a positive inotrope and negative chronotrope/dromotrope.",
        "warnings": "NARROW THERAPEUTIC INDEX — digoxin toxicity can be life-threatening. Therapeutic range: 0.5-0.9 ng/mL for heart failure; toxicity risk increases above 2 ng/mL. Signs of toxicity: nausea, vomiting, visual disturbances (yellow-green halos, blurred vision), and cardiac arrhythmias (any arrhythmia possible, including AV block, accelerated junctional rhythm, ventricular tachycardia). Hypokalemia, hypomagnesemia, and hypercalcemia increase digoxin toxicity risk — monitor electrolytes. Renal impairment significantly reduces digoxin clearance — dose adjustment essential. Many drug interactions affect digoxin levels: amiodarone, verapamil, quinidine, spironolactone, cyclosporine, and macrolide antibiotics increase digoxin levels.",
        "side_effects": "Therapeutic: rare adverse effects. Toxicity: nausea, vomiting, anorexia, visual disturbances (yellow/green halos, altered color vision, blurred vision), headache, fatigue, confusion; cardiac: any arrhythmia (PVCs, AV block, accelerated junctional rhythm, atrial tachycardia with AV block, ventricular tachycardia/fibrillation).",
        "dosage": "Heart failure: Loading dose not typically used; start 0.125-0.25 mg once daily; elderly: 0.0625-0.125 mg once daily. Atrial fibrillation: 0.25 mg once daily with dose adjusted based on response and serum levels. Renal impairment: significant dose reduction required (digoxin is primarily renally excreted). Monitor digoxin levels 6-8 hours after a dose (steady-state after 5-7 days).",
        "before_taking": "Tell your doctor about kidney disease (major dose adjustment needed), thyroid disorders, electrolyte imbalances, and all medications. Monitor potassium, magnesium, and calcium — hypokalemia increases toxicity risk. Drugs that increase digoxin levels: amiodarone (reduce digoxin dose by 50%), verapamil, quinidine, cyclosporine, clarithromycin. Drugs that decrease digoxin absorption: antacids, cholestyramine, metoclopramide. Learn the signs of digoxin toxicity.",
    },
    "finasteride": {
        "description": "Finasteride (Proscar 5 mg for BPH; Propecia 1 mg for male pattern baldness) is a 5-alpha reductase inhibitor that blocks conversion of testosterone to dihydrotestosterone (DHT). DHT is responsible for prostate growth and androgenetic alopecia.",
        "uses": "Finasteride 5 mg (Proscar) is indicated for treatment of symptomatic benign prostatic hyperplasia (BPH) to reduce the risk of acute urinary retention and the need for BPH-related surgery. Finasteride 1 mg (Propecia) is indicated for treatment of male pattern hair loss (androgenetic alopecia) in men.",
        "warnings": "Finasteride is CONTRAINDICATED in women of childbearing potential and in pregnancy — it can cause abnormalities of external genitalia in male fetuses. Women should not handle crushed or broken finasteride tablets. Prostate-specific antigen (PSA) levels decrease by approximately 50% — adjust PSA interpretation accordingly when screening for prostate cancer. Postmarketing reports of persistent sexual dysfunction (erectile dysfunction, decreased libido, ejaculatory disorders) after discontinuation; rarely, suicidal ideation has been reported. Increased risk of high-grade prostate cancer was observed in the PCPT trial, though causal relationship uncertain.",
        "side_effects": "Common: decreased libido, ejaculatory disorder (decreased semen volume), erectile dysfunction, breast tenderness/enlargement (gynecomastia). Serious: persistent sexual dysfunction after discontinuation (post-finasteride syndrome — though causality debated), hypersensitivity reactions, depression/suicidal ideation.",
        "dosage": "BPH (Proscar): 5 mg once daily; may take 6-12 months to see maximum benefit. Male pattern baldness (Propecia): 1 mg once daily; continued use required to maintain benefit — hair loss resumes within 12 months of stopping. Take with or without food.",
        "before_taking": "Absolutely contraindicated in women who are or may become pregnant. Women should not handle crushed or broken tablets. Men: tell your doctor about liver disease (dose adjustment may be needed), prostate cancer. Tell your doctor if you notice any breast lumps, nipple discharge, or breast pain. Tell your doctor about medications — finasteride is metabolized by CYP3A4.",
    },
    "fluconazole": {
        "description": "Fluconazole (Diflucan) is a triazole antifungal available as 50, 100, 150, and 200 mg capsules, 10 and 40 mg/mL oral suspension, and IV injection. It acts by inhibiting fungal CYP51 (lanosterol 14-α-demethylase), blocking ergosterol synthesis.",
        "uses": "Fluconazole is indicated for vaginal candidiasis (single-dose 150 mg), oropharyngeal and esophageal candidiasis, cryptococcal meningitis (treatment and suppression in AIDS patients), systemic Candida infections (peritonitis, pneumonia, UTI, bloodstream infections), and prophylaxis of candidiasis in immunocompromised patients.",
        "warnings": "Fluconazole is a potent CYP2C9 and CYP3A4 inhibitor — extensive drug interactions. Can substantially increase warfarin levels (INR monitoring essential). Also increases levels of statins (myopathy risk), sulfonylureas (hypoglycemia), phenytoin, cyclosporine, tacrolimus, and many others. QT interval prolongation and torsades de pointes have been reported. Hepatotoxicity has occurred. High-dose fluconazole (400-800 mg/day) is TERATOGENIC — associated with limb shortening, craniofacial abnormalities, and cardiac defects; avoid in first trimester. Single-dose 150 mg for vaginal candidiasis may be used in pregnancy after careful risk-benefit assessment.",
        "side_effects": "Common: headache, nausea, abdominal pain, diarrhea, rash. Serious: hepatotoxicity (elevated LFTs, rarely hepatic failure), QT prolongation, severe skin reactions (SJS, TEN — with systemic treatment), teratogenicity at high doses.",
        "dosage": "Vaginal candidiasis: single 150 mg oral dose. Oropharyngeal candidiasis: 200 mg on day 1, then 100 mg once daily for ≥14 days. Esophageal candidiasis: 200-400 mg on day 1, then 100-200 mg once daily for at least 3 weeks. Systemic candidiasis: 400-800 mg loading dose, then 200-400 mg once daily. Take with or without food.",
        "before_taking": "Tell your doctor about liver or kidney disease, QT prolongation, and all medications — fluconazole has many significant drug interactions (warfarin, oral hypoglycemics, statins, phenytoin, tacrolimus, cyclosporine). Avoid grapefruit juice. Do not use systemic/high-dose fluconazole in pregnancy (especially first trimester). The single 150 mg dose for vaginal yeast infection during pregnancy — consult your doctor.",
    },
    "esomeprazole": {
        "description": "Esomeprazole (Nexium) is the S-enantiomer of omeprazole and a proton pump inhibitor (PPI) available OTC and prescription as 20 and 40 mg capsules and packets for oral suspension. It irreversibly inhibits gastric H+/K+-ATPase.",
        "uses": "Esomeprazole is indicated for GERD treatment and erosive esophagitis healing/maintenance, H. pylori eradication (in combination), reduction of NSAID-associated gastric ulcer risk, pathological hypersecretory conditions (Zollinger-Ellison syndrome). OTC formulation is for frequent heartburn treatment.",
        "warnings": "Same concerns as all PPIs: long-term use associated with hypomagnesemia, bone fracture risk, Clostridioides difficile-associated diarrhea, vitamin B12 deficiency, acute interstitial nephritis, fundic gland polyps. Use for the shortest effective duration. May interfere with absorption of ketoconazole, itraconazole, iron salts, erlotinib, and mycophenolate. Unlike omeprazole, esomeprazole has less effect on clopidogrel activation (though both are CYP2C19 inhibitors).",
        "side_effects": "Common: headache, diarrhea, nausea, abdominal pain, flatulence. Serious: CDAD, hypomagnesemia, bone fractures (hip, wrist, spine), acute interstitial nephritis, lupus erythematosus (cutaneous/systemic).",
        "dosage": "GERD/erosive esophagitis: 20-40 mg once daily for 4-8 weeks; maintenance 20 mg once daily. H. pylori eradication: 40 mg twice daily with clarithromycin and amoxicillin for 10-14 days. OTC (frequent heartburn): 20 mg once daily for 14 days, up to 3 courses per year. Take 1 hour before a meal.",
        "before_taking": "Tell your doctor about liver disease, low magnesium, osteoporosis, or lupus. Same interactions as omeprazole — interact with methotrexate, rilpivirine, atazanavir, and drugs requiring acidic pH for absorption. Long-term use requires monitoring of magnesium and vitamin B12.",
    },
    "metoclopramide": {
        "description": "Metoclopramide (Reglan) is a dopamine antagonist prokinetic and antiemetic available as 5 and 10 mg tablets, oral solution, and injectable formulation.",
        "uses": "Metoclopramide is indicated for symptomatic GERD (short-term — up to 12 weeks), gastroparesis (diabetic and idiopathic), and prevention and treatment of nausea and vomiting associated with chemotherapy, surgery, and postpartum states. Also used for nausea of pregnancy.",
        "warnings": "FDA BOXED WARNING: Tardive dyskinesia — chronic use of metoclopramide can cause tardive dyskinesia (involuntary repetitive movements of the face, tongue, lips, and extremities), which may be irreversible. Risk increases with longer duration and higher doses. Discontinue metoclopramide in patients who develop tardive dyskinesia. Do not use for longer than 12 weeks. Also risk of extrapyramidal reactions (acute dystonic reactions, akathisia, parkinsonism) and neuroleptic malignant syndrome.",
        "side_effects": "Common: drowsiness, fatigue, restlessness, diarrhea. Serious: tardive dyskinesia (irreversible — boxed warning), extrapyramidal reactions (acute dystonia, especially in young patients), neuroleptic malignant syndrome, QT prolongation, methemoglobinemia (high doses in neonates).",
        "dosage": "Gastroparesis: 10 mg up to 4 times daily before meals and at bedtime for up to 12 weeks. GERD: 10-15 mg up to 4 times daily before meals and at bedtime for up to 12 weeks. Chemotherapy-induced nausea: 1-2 mg/kg IV 30 minutes before chemotherapy (high-dose protocol). Pregnancy nausea (off-label): 5-10 mg every 6-8 hours.",
        "before_taking": "Do not use for longer than 12 weeks. Do not use in patients with GI bleeding, obstruction, or perforation, pheochromocytoma, epilepsy, or Parkinson's disease (dopamine antagonist worsens PD). Tell your doctor about kidney disease (dose reduction needed), liver disease, hypertension. Do not use with other dopamine antagonists or serotonergic drugs. Diphenhydramine 25 mg IM/IV can treat acute dystonic reactions.",
    },
    "trimethoprim-sulfamethoxazole": {
        "description": "Trimethoprim-sulfamethoxazole (TMP-SMX; Bactrim, Septra) is a combination antibiotic consisting of trimethoprim and sulfamethoxazole (a sulfonamide) in a fixed 1:5 ratio. Available as single-strength (80/400 mg), double-strength DS (160/800 mg) tablets, and oral suspension.",
        "uses": "TMP-SMX is indicated for urinary tract infections, acute otitis media, acute exacerbations of chronic bronchitis, Pneumocystis jirovecii pneumonia (PCP) treatment and prophylaxis in immunocompromised patients, traveler's diarrhea, shigellosis, and community-acquired MRSA skin and soft tissue infections.",
        "warnings": "TMP-SMX contains a sulfonamide — contraindicated in patients with sulfonamide allergy. Serious skin reactions including SJS and TEN have occurred. Bone marrow suppression (megaloblastic anemia, granulocytopenia, thrombocytopenia) — risk increased with folate deficiency, renal impairment, or concurrent use of other folate antagonists (methotrexate). Hyperkalemia is common — TMP blocks renal potassium secretion; risk increased with high-potassium diets, renal impairment, or concurrent use of ACE inhibitors, ARBs, potassium-sparing diuretics. Avoid in the third trimester of pregnancy (risk of neonatal hyperbilirubinemia and kernicterus) and in infants <2 months. Photosensitivity occurs — use sunscreen.",
        "side_effects": "Common: nausea, vomiting, rash, photosensitivity, hyperkalemia (trimethoprim blocks renal K+ excretion), increased serum creatinine (TMP blocks tubular secretion of creatinine without reducing GFR). Serious: SJS, TEN, DRESS, bone marrow suppression, megaloblastic anemia, hepatotoxicity, aseptic meningitis.",
        "dosage": "UTI (uncomplicated): 1 DS tablet (160/800 mg) twice daily for 3 days. UTI (complicated): 1 DS tablet twice daily for 7-14 days. Community-acquired MRSA skin infection: 1-2 DS tablets twice daily for 5-10 days. PCP prophylaxis (HIV): 1 DS tablet once daily or 1 SS tablet once daily. PCP treatment: 15-20 mg/kg/day (trimethoprim component) in 3-4 divided doses IV or oral for 21 days.",
        "before_taking": "Contraindicated with sulfonamide allergy, significant renal or hepatic impairment, folate deficiency. Avoid in the third trimester of pregnancy and in nursing mothers. Tell your doctor about kidney disease, liver disease, G6PD deficiency, blood disorders, and all medications — TMP-SMX interacts with warfarin (increases INR), methotrexate (increases toxicity), ACE inhibitors and ARBs (hyperkalemia), oral hypoglycemics (potentiates hypoglycemia), and phenytoin.",
    },
    "nitroglycerin": {
        "description": "Nitroglycerin (NTG; Nitrostat, Nitrolingual, Nitro-Dur, Nitro-Bid) is a nitrovasodilator that releases nitric oxide, causing smooth muscle relaxation and vasodilation of both venous and arterial vasculature. Available as sublingual tablets, sublingual spray, transdermal patches, topical ointment, and IV solution.",
        "uses": "Nitroglycerin is indicated for acute relief and prophylaxis of angina pectoris (chest pain) due to coronary artery disease. IV nitroglycerin is used for hypertensive urgency/emergency, acute heart failure, and unstable angina. Transdermal and oral forms are used for chronic stable angina prevention.",
        "warnings": "CONTRAINDICATED with PDE5 inhibitors (sildenafil, tadalafil, vardenafil, avanafil) — combination causes severe, potentially fatal hypotension. Also contraindicated with riociguat. Hypotension is the major adverse effect — more pronounced with upright posture, alcohol, and other vasodilators. Tolerance to the hemodynamic effects develops within 24-48 hours of continuous exposure — a nitrate-free interval of 10-12 hours daily is required to prevent tolerance. Severe headache is common, particularly with initiation.",
        "side_effects": "Common: headache (often severe — most common), hypotension, flushing, dizziness, tachycardia/palpitations. Serious: severe hypotension (syncope), methemoglobinemia (rare, with high doses IV).",
        "dosage": "Acute angina (sublingual): 0.3-0.4 mg tablet (Nitrostat) or 1-2 metered sprays (Nitrolingual) under the tongue; may repeat every 5 minutes up to 3 doses in 15 minutes. If pain persists after 3 doses, seek emergency care immediately. Angina prophylaxis: 0.3-0.6 mg SL 5-10 minutes before activities that may provoke angina. Transdermal patch: 0.1-0.8 mg/hr applied once daily; remove for 10-12 hours daily to prevent tolerance.",
        "before_taking": "NEVER take nitroglycerin if you have taken sildenafil (Viagra), tadalafil (Cialis), vardenafil (Levitra), or avanafil (Stendra) within 24-48 hours (depending on product). Tell your doctor about low blood pressure, dehydration, severe anemia, glaucoma, or use of erectile dysfunction medications or riociguat. Sit or lie down when taking sublingual nitroglycerin — hypotension can cause fainting. Store sublingual tablets in original glass container away from light and heat.",
    },
    "tamsulosin": {
        "description": "Tamsulosin (Flomax) is a selective alpha-1A/D adrenergic receptor antagonist that relaxes smooth muscle in the prostate and bladder neck, improving urinary flow in benign prostatic hyperplasia (BPH). Available as 0.4 mg capsules.",
        "uses": "Tamsulosin is indicated for the treatment of signs and symptoms of benign prostatic hyperplasia (BPH) to improve urinary flow and reduce symptoms of hesitancy, urgency, weak stream, and nocturia. It is the most commonly prescribed alpha-blocker for BPH.",
        "warnings": "Orthostatic hypotension and syncope can occur, especially with the first dose and with concurrent antihypertensive therapy or PDE5 inhibitors — patients should avoid driving or hazardous activities for 12 hours after the first dose or any dose increase. Intraoperative Floppy Iris Syndrome (IFIS) has been reported during cataract surgery — inform the ophthalmologist before cataract surgery if tamsulosin has ever been used. Priapism (rare) has been reported. Not for use in women.",
        "side_effects": "Common: dizziness, orthostatic hypotension, rhinitis, ejaculatory dysfunction (retrograde ejaculation or reduced ejaculation volume — in up to 18% of patients), headache, back pain. Serious: syncope (first-dose effect), IFIS (with cataract surgery), priapism.",
        "dosage": "0.4 mg once daily taken approximately 30 minutes after the same meal each day. May increase to 0.8 mg once daily after 2-4 weeks if response inadequate.",
        "before_taking": "Tell your ophthalmologist before ANY cataract surgery that you take or have ever taken tamsulosin. Take the first dose when you can sit or lie down for 12 hours. Tell your doctor if you take antihypertensives, PDE5 inhibitors (sildenafil, tadalafil), or other alpha-blockers. Avoid driving or hazardous activity for the first 12 hours after starting tamsulosin or increasing dose. Not for use in women or children.",
    },
    "melatonin": {
        "description": "Melatonin is an endogenous hormone produced by the pineal gland that regulates circadian rhythm and the sleep-wake cycle. Available OTC as 0.3-10 mg tablets, gummies, and extended-release formulations. The physiologic dose is 0.3-0.5 mg; most OTC products contain pharmacologic doses (1-10 mg).",
        "uses": "Melatonin is used OTC for short-term insomnia, jet lag, shift-work disorder, and delayed sleep phase syndrome (DSPS). Higher-dose prescription melatonin (Circadin 2 mg ER — not available in the US) is approved in Europe for primary insomnia in adults ≥55 years.",
        "warnings": "Melatonin is generally considered safe for short-term use. Drowsiness is common — do not drive or operate machinery for 4-5 hours after taking. May interact with fluvoxamine (significantly increases melatonin levels), carbamazepine, rifampin (decrease levels), anticoagulants (monitor INR), antidiabetic drugs, and immunosuppressants. Limited data in pregnancy and breastfeeding — avoid. Theoretical concern about melatonin use during adolescence affecting puberty (based on animal data). Quality control of OTC supplements is variable — melatonin content may differ significantly from label claims.",
        "side_effects": "Common: daytime drowsiness, dizziness, headache, nausea, irritability. Less common: vivid dreams, short-term depression, abdominal cramps. Generally well-tolerated.",
        "dosage": "Insomnia/sleep onset: 0.5-5 mg at bedtime (physiologic dose 0.3-0.5 mg may be most effective for sleep). Jet lag: 0.5-5 mg at destination bedtime for 2-4 days. Shift-work sleep disorder: 1-5 mg at desired bedtime. Start with the lowest effective dose.",
        "before_taking": "Melatonin is a dietary supplement — not regulated as strictly as a prescription drug. Consult your doctor before use if you take blood thinners, diabetes medications, immunosuppressants, or fluvoxamine. Do not use if pregnant or breastfeeding. Avoid use in children without medical supervision. Do not drive or operate machinery for 4-5 hours after taking.",
    },
    "loperamide": {
        "description": "Loperamide (Imodium) is a synthetic opioid that acts on gut opioid receptors to slow intestinal motility and reduce fecal water loss. Available OTC as 2 mg capsules and liquid. Unlike systemic opioids, loperamide does not cross the blood-brain barrier at normal doses.",
        "uses": "Loperamide is indicated for symptomatic relief of acute diarrhea and chronic diarrhea associated with inflammatory bowel disease. It reduces frequency of loose stools and the urgency of defecation.",
        "warnings": "Do not use loperamide for diarrhea accompanied by fever or blood in stool (may indicate bacterial infection requiring antibiotic treatment). Loperamide can cause serious cardiac adverse events (cardiac arrest, fatal arrhythmias) at excessive doses — only use as directed; do not exceed 8 mg/day OTC or 16 mg/day prescription. At supratherapeutic doses, loperamide has been misused by opioid-dependent individuals to self-treat withdrawal — this is associated with fatal arrhythmias. Avoid in patients with acute ulcerative colitis, toxic megacolon, and pseudomembranous colitis.",
        "side_effects": "Common: constipation, abdominal cramps, nausea, dry mouth. Serious: toxic megacolon (in patients with acute colitis), cardiac arrhythmias at excessive doses, QT prolongation at high doses.",
        "dosage": "Acute diarrhea (adults): 4 mg initially, then 2 mg after each unformed stool; maximum 8 mg/day OTC (16 mg/day prescription); use for no more than 2 days OTC. Children 6-8 years (44-59 lbs): 2 mg twice daily. Do not use OTC in children under 2 years.",
        "before_taking": "Do not use if diarrhea is accompanied by fever, blood in stool, or mucus — seek medical evaluation. Do not use in children under 2 years. Discontinue if constipation, abdominal distension, or ileus develops. Loperamide is a substrate of P-gp — P-gp inhibitors (ketoconazole, ritonavir, itraconazole) can increase loperamide levels and risk of cardiac arrhythmias. Never exceed the recommended dose.",
    },
    "risperidone": {
        "description": "Risperidone (Risperdal, Risperdal Consta ER injection) is a second-generation (atypical) antipsychotic that blocks dopamine D2 and serotonin 5-HT2A receptors. Available as 0.25, 0.5, 1, 2, 3, and 4 mg tablets, oral solution, orally disintegrating tablets (Risperdal M-Tab), and long-acting injectable (Risperdal Consta, Perseris).",
        "uses": "Risperidone is indicated for schizophrenia (adults and adolescents ≥13 years), acute manic or mixed episodes of bipolar I disorder (adults and children ≥10 years), and irritability associated with autistic disorder in children and adolescents 5-16 years.",
        "warnings": "FDA BOXED WARNING: Elderly patients with dementia-related psychosis treated with antipsychotics are at an increased risk of death — risperidone is NOT approved for dementia-related psychosis. Metabolic effects: hyperglycemia, diabetes mellitus, dyslipidemia, weight gain. Tardive dyskinesia — risk increases with duration of use. Neuroleptic malignant syndrome (NMS). QT prolongation. Orthostatic hypotension. Prolactin elevation (risperidone causes the highest prolactin elevation among atypical antipsychotics) — may cause galactorrhea, amenorrhea, gynecomastia, sexual dysfunction. Seizures. Use with caution in Parkinson's disease (worsens symptoms). Risperidone and its active metabolite paliperidone are primarily renally cleared — dose reduction in renal impairment.",
        "side_effects": "Common: extrapyramidal symptoms (dystonia, akathisia, parkinsonism, tardive dyskinesia), somnolence, insomnia, weight gain, headache, dizziness, hyperprolactinemia, fatigue, anxiety, constipation. Serious: NMS, tardive dyskinesia, QT prolongation, metabolic syndrome, sudden death in elderly dementia patients.",
        "dosage": "Schizophrenia (adults): Start 2 mg once daily or 1 mg twice daily; increase by 1-2 mg/day at intervals ≥24 hours; target 4-8 mg/day; maximum 16 mg/day. Bipolar mania: 2-3 mg once daily; range 1-6 mg/day. Autism irritability (children): Start 0.25 mg/day (<20 kg) or 0.5 mg/day (≥20 kg); target 0.5-2.5 mg/day (<20 kg) or 1-2.5 mg/day (≥20 kg).",
        "before_taking": "Tell your doctor about Parkinson's disease, Lewy body dementia (risperidone can cause severe reactions), cardiovascular disease, kidney or liver disease, QT prolongation, diabetes, seizures, or pregnancy. Monitor metabolic parameters (weight, glucose, lipids) at baseline and periodically. Not approved for dementia-related psychosis in elderly. Inform your doctor if you are pregnant — neonates exposed to antipsychotics in the third trimester have risks of extrapyramidal symptoms and withdrawal.",
    },
    "olanzapine": {
        "description": "Olanzapine (Zyprexa, Zyprexa Zydis, Zyprexa Relprevv ER injection) is a second-generation (atypical) antipsychotic that blocks dopamine D1/D2 and multiple other receptors (serotonin 5-HT2A/2C, muscarinic, histamine H1, adrenergic). Associated with the most significant metabolic adverse effects among atypical antipsychotics.",
        "uses": "Olanzapine is indicated for schizophrenia (adults and adolescents ≥13 years), acute treatment of manic or mixed episodes in bipolar I disorder, and maintenance treatment of bipolar I disorder. Combined with fluoxetine (Symbyax) for treatment-resistant depression and for depressive episodes of bipolar I disorder.",
        "warnings": "FDA BOXED WARNINGS: (1) Elderly dementia patients — increased risk of death; not approved for dementia-related psychosis. (2) Zyprexa Relprevv (ER injection) — post-injection delirium/sedation syndrome occurs in 0.07% of injections; patients must be monitored for 3 hours after each injection at a healthcare facility with emergency access. Metabolic syndrome is a significant concern — olanzapine causes the most weight gain and the highest rates of hyperglycemia and dyslipidemia of all atypical antipsychotics. Tardive dyskinesia, NMS, QT prolongation, orthostatic hypotension, and seizures can occur.",
        "side_effects": "Common: somnolence, weight gain (often substantial), metabolic effects (hyperglycemia, dyslipidemia), anticholinergic effects (dry mouth, constipation, urinary retention), dizziness, orthostatic hypotension, akathisia. Serious: NMS, tardive dyskinesia, severe metabolic syndrome/diabetes, QT prolongation, hepatotoxicity.",
        "dosage": "Schizophrenia (adults): Start 5-10 mg once daily; target 10 mg/day; range 10-20 mg/day. Bipolar mania: 10-15 mg once daily; range 5-20 mg/day. Adolescents (13-17 years): Start 2.5-5 mg once daily; target 10 mg/day. Monitor metabolic parameters at baseline, 4 weeks, 8 weeks, 12 weeks, then quarterly.",
        "before_taking": "Monitor blood glucose, lipids, and weight at baseline and regularly during treatment — olanzapine causes significant metabolic changes. Tell your doctor about diabetes, high cholesterol, cardiovascular disease, liver disease, Parkinson's disease, seizure disorder, glaucoma, urinary retention, or prostatic hypertrophy. Avoid alcohol. Not approved for dementia-related psychosis. Inform your doctor if you are pregnant.",
    },
    "paroxetine": {
        "description": "Paroxetine (Paxil, Paxil CR, Brisdelle) is a selective serotonin reuptake inhibitor (SSRI) with additional anticholinergic and norepinephrine reuptake inhibitory properties. Available as 10, 20, 30, and 40 mg tablets, controlled-release (12.5, 25, 37.5 mg), and oral suspension.",
        "uses": "Paroxetine is indicated for major depressive disorder, generalized anxiety disorder, panic disorder, OCD, PTSD, social anxiety disorder (social phobia), and premenstrual dysphoric disorder (PMDD). Brisdelle (7.5 mg) is indicated for moderate-to-severe vasomotor symptoms (hot flashes) associated with menopause.",
        "warnings": "FDA BOXED WARNING: Antidepressants increase suicidal risk in children, adolescents, and young adults. Paroxetine is a potent CYP2D6 inhibitor — increases levels of many drugs. MOST SIGNIFICANT SSRI DISCONTINUATION SYNDROME — paroxetine has the shortest half-life of major SSRIs and causes severe discontinuation syndrome if stopped abruptly (electric shock sensations, dizziness, insomnia, flu-like symptoms, anxiety, irritability). Taper very slowly. Paroxetine is FDA Pregnancy Category D — associated with neonatal adaptation syndrome and possibly cardiac malformations (especially VSD). Avoid in pregnancy, especially first trimester. Serotonin syndrome with serotonergic drugs. Do not use with MAO inhibitors.",
        "side_effects": "Common: nausea, somnolence, insomnia, sexual dysfunction (one of the highest rates among SSRIs), dry mouth, dizziness, sweating, weight gain. Serious: serotonin syndrome, severe discontinuation syndrome, suicidal ideation (young adults), hyponatremia (SIADH), abnormal bleeding.",
        "dosage": "Depression: 20 mg once daily, morning; range 20-50 mg/day. GAD, PTSD, social anxiety: 20 mg once daily; range 20-50 mg/day. Panic disorder: Start 10 mg once daily; range 10-60 mg/day. OCD: 20-60 mg/day. PMDD (Paxil CR): 12.5-25 mg/day. Taper dose very slowly when discontinuing — never stop abruptly.",
        "before_taking": "Avoid in pregnancy — associated with neonatal adaptation syndrome and possible cardiac malformations. Do not use with MAO inhibitors. Tell your doctor about bipolar disorder, seizure disorder, kidney or liver disease, glaucoma, bleeding disorders, and all medications (CYP2D6 inhibitor — interacts with many drugs including tamoxifen, reducing its efficacy). Taper very slowly when discontinuing.",
    },
    "mirtazapine": {
        "description": "Mirtazapine (Remeron, Remeron SolTab) is a noradrenergic and specific serotonergic antidepressant (NaSSA) with antihistamine properties. Available as 7.5, 15, 30, and 45 mg tablets and 15, 30, and 45 mg orally disintegrating tablets.",
        "uses": "Mirtazapine is FDA-approved for treatment of major depressive disorder. It is commonly used off-label for insomnia, appetite stimulation in cancer patients and the elderly, anxiety disorders, and prevention of nausea and vomiting (antiemetic effects). The sedating and appetite-stimulating effects are more pronounced at lower doses (7.5-15 mg).",
        "warnings": "FDA BOXED WARNING: Antidepressants increase suicidal risk in children, adolescents, and young adults. Mirtazapine has agranulocytosis risk (rare, approximately 1.5 per 1000 patients) — discontinue if fever, sore throat, or other signs of infection occur. Serotonin syndrome can occur with other serotonergic agents. Seizures. Mania. Do not use with MAO inhibitors.",
        "side_effects": "Common: somnolence (sedation is prominent, especially at low doses — often used therapeutically), increased appetite and weight gain (significant — one of the most weight-promoting antidepressants), dry mouth, constipation, dizziness. Serious: agranulocytosis (rare), serotonin syndrome, elevated cholesterol and triglycerides.",
        "dosage": "Start 15 mg once daily at bedtime; may increase by 15 mg every 1-2 weeks; range 15-45 mg/day once daily at bedtime. Note: sedation is paradoxically LESS at higher doses (15 mg most sedating; 30-45 mg less sedating due to increasing norepinephrine activity offsetting antihistamine effects).",
        "before_taking": "Tell your doctor about kidney or liver disease, seizure disorder, bipolar disorder, heart disease, or glaucoma. Do not use with MAO inhibitors. Tell your doctor about all medications — mirtazapine can increase the sedating effects of alcohol and CNS depressants significantly. Discontinue gradually to avoid withdrawal. Report fever, sore throat, or mouth sores immediately (possible agranulocytosis).",
    },
    "sumatriptan": {
        "description": "Sumatriptan (Imitrex) is a selective 5-HT1B/1D receptor agonist (triptan) for acute migraine treatment. Available as 25, 50, and 100 mg oral tablets, 4 mg and 6 mg SC autoinjector, and 5 mg and 20 mg nasal spray.",
        "uses": "Sumatriptan is indicated for acute treatment of migraine attacks with or without aura, and for acute treatment of cluster headache (SC injection formulation only).",
        "warnings": "CONTRAINDICATED in patients with ischemic coronary artery disease, coronary artery vasospasm (Prinzmetal's angina), peripheral vascular disease, ischemic bowel disease, cerebrovascular disease (stroke, TIA), hemiplegic or basilar migraine, uncontrolled hypertension, and within 24 hours of another 5-HT1 agonist or ergot-containing medication. Serotonin syndrome can occur with SSRIs, SNRIs, MAO inhibitors, or other serotonergic agents. Chest pain and tightness, sensations of pressure, warmth, or flushing are common and usually benign, but cardiac causes must be ruled out in patients at cardiovascular risk. Do not use within 14 days of MAO inhibitor use.",
        "side_effects": "Common: injection site reactions (SC), tingling, warmth/flushing, dizziness, drowsiness, chest pressure/tightness (usually benign but can indicate vasospasm), nausea. Serious: myocardial infarction (rare), stroke, coronary artery vasospasm, serotonin syndrome.",
        "dosage": "Oral: 25-100 mg; repeat in 2 hours if needed; maximum 200 mg/24 hours. SC: 4-6 mg SC; may repeat once after 1 hour; maximum 12 mg/24 hours. Nasal: 5-20 mg in one nostril; may repeat once after 2 hours; maximum 40 mg/24 hours. Take at onset of headache or aura.",
        "before_taking": "Do not take if you have cardiovascular disease, uncontrolled hypertension, hemiplegic or basilar migraine, or have taken ergotamines or another triptan within 24 hours. Tell your doctor about risk factors for heart disease, kidney disease, liver disease, seizures, or if you take SSRIs/SNRIs/MAOIs. Sumatriptan overuse (>10 days/month) can cause medication-overuse headache.",
    },
    "rizatriptan": {
        "description": "Rizatriptan (Maxalt, Maxalt-MLT) is a selective 5-HT1B/1D receptor agonist (triptan) for acute migraine treatment. Available as 5 and 10 mg tablets and 5 and 10 mg orally disintegrating tablets (MLT).",
        "uses": "Rizatriptan is indicated for acute treatment of migraine attacks with or without aura in adults and children ≥6 years.",
        "warnings": "Same contraindications as sumatriptan: cardiovascular disease, cerebrovascular disease, uncontrolled hypertension, hemiplegic/basilar migraine, within 24 hours of another triptan or ergotamine. Rizatriptan dose must be reduced to 5 mg (with a maximum of 15 mg/24 hours) in patients taking propranolol (propranolol increases rizatriptan levels approximately 70%).",
        "side_effects": "Common: dizziness, somnolence, fatigue, chest pressure/tightness (usually benign), nausea, dry mouth. Serious: cardiovascular events (rare), serotonin syndrome.",
        "dosage": "Adults: 5 or 10 mg; may repeat in 2 hours; maximum 30 mg/24 hours. With propranolol: 5 mg only; maximum 15 mg/24 hours. Children 6-17 years (by weight): 5 mg (<40 kg) or 10 mg (≥40 kg) single dose.",
        "before_taking": "Same precautions as sumatriptan. Important: reduce dose to 5 mg if taking propranolol. Maxalt-MLT: open package just before use, place on tongue, dissolve without water.",
    },
    "hydroxyzine": {
        "description": "Hydroxyzine (Vistaril, Atarax) is a first-generation antihistamine with anxiolytic, sedative, antiemetic, and anticholinergic properties. Available as 10, 25, 50 mg tablets/capsules and oral suspension, and IM injection.",
        "uses": "Hydroxyzine is indicated for symptomatic relief of anxiety and tension, sedation pre- and post-operatively, pruritus due to allergic conditions (urticaria, contact dermatitis, atopic dermatitis), and as an antiemetic. It is sometimes used as an alternative anxiolytic in patients where benzodiazepines are contraindicated.",
        "warnings": "Hydroxyzine carries a significant anticholinergic burden — avoid in elderly patients (Beers Criteria), patients with urinary retention, narrow-angle glaucoma, myasthenia gravis, or severe hepatic impairment. QT interval prolongation has been reported — avoid in patients with known QT prolongation or on drugs that prolong QT. Sedation is significant — do not drive or operate machinery. Not for IV use (can cause hemolysis, thrombosis, gangrene); IM injection only (deep into muscle).",
        "side_effects": "Common: sedation (prominent), dry mouth, constipation, blurred vision, urinary retention, dizziness. Serious: QT prolongation, anticholinergic toxidrome in overdose, confusion/delirium in elderly, anaphylaxis (rare).",
        "dosage": "Anxiety (oral): 50-100 mg 4 times daily. Pre-operative sedation: 50-100 mg IM. Pruritus: 25 mg 3-4 times daily. Children: 50 mg/day in divided doses (pruritus); 0.6 mg/kg IM for pre-operative sedation.",
        "before_taking": "Avoid in elderly patients due to anticholinergic effects and fall risk. Do not use IV — IM only for injectable form. Tell your doctor about glaucoma, urinary retention, prostatic hypertrophy, liver disease, QT prolongation, or kidney disease. Avoid alcohol and other CNS depressants. Do not drive. Inform your doctor if pregnant or breastfeeding.",
    },
    "buspirone": {
        "description": "Buspirone (Buspar — original brand discontinued, generics available) is an azapirone anxiolytic that acts as a partial agonist at 5-HT1A receptors and as a dopamine D2 antagonist. Available as 5, 7.5, 10, 15, and 30 mg tablets.",
        "uses": "Buspirone is indicated for the management of generalized anxiety disorder (GAD). Unlike benzodiazepines, it does not cause dependence, tolerance, or significant sedation, making it suitable for long-term anxiety management.",
        "warnings": "Buspirone does not have rapid anxiolytic effect — therapeutic benefit typically takes 2-4 weeks, making it unsuitable for acute anxiety or 'as needed' use. Do not use with MAO inhibitors (risk of hypertensive crisis). CYP3A4 inhibitors (erythromycin, itraconazole, nefazodone, grapefruit juice) significantly increase buspirone levels. Dizziness is the most common adverse effect — caution when driving. Previous benzodiazepine use: patients may not respond as well and may feel buspirone is 'not working' because it lacks the immediate benzodiazepine effect.",
        "side_effects": "Common: dizziness, nausea, headache, nervousness, lightheadedness, excitement, insomnia. Less common: blurred vision, tachycardia, sweating.",
        "dosage": "Initial: 7.5 mg twice daily; increase by 5 mg/day every 2-3 days as needed; usual range 20-30 mg/day in 2-3 divided doses; maximum 60 mg/day. Benefits may not be apparent for 2-4 weeks — advise patients to continue taking.",
        "before_taking": "Do not expect immediate relief — buspirone takes 2-4 weeks to work for anxiety. Do not use with MAO inhibitors. Avoid grapefruit juice and CYP3A4 inhibitors (increase buspirone levels). Inform your doctor of all medications. Buspirone does not prevent or treat benzodiazepine withdrawal — if switching from a benzodiazepine, taper the benzodiazepine slowly. Generally safe in elderly. Inform your doctor if pregnant or breastfeeding.",
    },
    "methylprednisolone": {
        "description": "Methylprednisolone (Medrol, Solu-Medrol, Depo-Medrol) is a synthetic glucocorticoid corticosteroid approximately 5 times more potent than hydrocortisone. Available as 2, 4, 8, 16, 32 mg oral tablets (Medrol Dosepak), and as sodium succinate for IV injection (Solu-Medrol) and acetate for IM injection (Depo-Medrol).",
        "uses": "Methylprednisolone is used for a wide range of inflammatory and autoimmune conditions, including allergic states, asthma and COPD exacerbations, rheumatic disorders (RA, SLE), multiple sclerosis (IV pulse therapy), dermatologic diseases, organ transplant rejection prevention/treatment, and severe acute hypersensitivity reactions.",
        "warnings": "Same general corticosteroid warnings as dexamethasone: HPA-axis suppression, adrenal insufficiency with abrupt discontinuation, immunosuppression and infection risk, peptic ulcer, hyperglycemia, psychiatric effects, osteoporosis, cataracts, and glaucoma. Medrol Dosepak (6-day taper) is used for acute inflammatory conditions — even this short course can cause significant adverse effects including severe psychiatric reactions, hyperglycemia, and sleep disturbances.",
        "side_effects": "Short-term: hyperglycemia, insomnia, mood changes, increased appetite, weight gain, fluid retention, headache. Long-term: Cushingoid features, osteoporosis, avascular necrosis, adrenal suppression, cataracts, growth suppression in children.",
        "dosage": "Medrol Dosepak (acute inflammation): 24 mg on day 1, decreasing by 4 mg/day over 6 days. MS exacerbation: 1 g IV once daily for 3-5 days. Asthma exacerbation: 40-60 mg/day PO or IV in 1-2 doses for 5-7 days. Organ transplant rejection: 500-1000 mg IV daily for 3 days. Dose depends on indication and severity.",
        "before_taking": "Same precautions as dexamethasone — take with food, do not stop abruptly, report signs of infection. Even short courses (Medrol Dosepak) can cause significant blood sugar elevations in diabetics. Monitor blood glucose. Tell your doctor about any infections (bacterial, viral, fungal), diabetes, osteoporosis, peptic ulcer, psychiatric history, heart disease, or glaucoma. Do not receive live vaccines while on immunosuppressive doses.",
    },
    "terbinafine": {
        "description": "Terbinafine (Lamisil) is an allylamine antifungal that inhibits fungal squalene epoxidase, blocking ergosterol synthesis. Available as 250 mg oral tablets and topical cream, gel, and spray (OTC).",
        "uses": "Oral terbinafine is indicated for onychomycosis (fungal nail infections) of toenails and fingernails due to dermatophytes, and for tinea capitis (ringworm of the scalp). Topical terbinafine is indicated for tinea pedis (athlete's foot), tinea corporis (ringworm), and tinea cruris (jock itch).",
        "warnings": "Oral terbinafine can cause hepatotoxicity including liver failure and death — obtain baseline LFTs before initiating; avoid in patients with pre-existing hepatic disease. Severe skin reactions (SJS, TEN, DRESS) have been reported. Taste and smell disturbances (ageusia, dysgeusia) can occur and may be long-lasting or permanent. Depression, anxiety, and psychiatric disorders have been reported. Terbinafine inhibits CYP2D6 — interacts with drugs metabolized by CYP2D6.",
        "side_effects": "Common: headache, diarrhea, rash, dyspepsia, liver enzyme elevations. Serious: hepatotoxicity (rare but potentially fatal), severe skin reactions (SJS, TEN), taste disturbances (may be prolonged), psychiatric effects (depression, anxiety).",
        "dosage": "Toenail onychomycosis: 250 mg once daily for 12 weeks. Fingernail onychomycosis: 250 mg once daily for 6 weeks. Tinea capitis (children): 3-6 mg/kg/day for 6 weeks. Topical (athlete's foot, ringworm, jock itch): apply once or twice daily for 1-4 weeks.",
        "before_taking": "Check liver function before starting oral terbinafine. Avoid in patients with pre-existing liver disease. Do not use with CYP2D6 substrates where dose adjustment is critical (tricyclics, certain antipsychotics, beta-blockers metabolized by CYP2D6). Report any new rash, jaundice, dark urine, taste changes, or mood changes. Oral terbinafine should be used with caution in patients with kidney impairment (CrCl <50 mL/min).",
    },
    "valacyclovir": {
        "description": "Valacyclovir (Valtrex) is the L-valyl ester prodrug of acyclovir that is rapidly converted to acyclovir after oral absorption. It provides significantly higher bioavailability than acyclovir, allowing less frequent dosing. Available as 500 mg and 1000 mg tablets.",
        "uses": "Valacyclovir is indicated for herpes zoster (shingles) treatment, genital herpes (initial and recurrent episodes, chronic suppression), and herpes labialis (cold sores). It is also used off-label for CMV prophylaxis in transplant recipients and for varicella (chickenpox) prevention in immunocompromised patients.",
        "warnings": "Thrombotic thrombocytopenic purpura/hemolytic uremic syndrome (TTP/HUS) has occurred in immunocompromised patients at high doses — use with caution. CNS adverse effects (agitation, hallucinations, confusion, encephalopathy, seizures, coma) have been reported, predominantly in patients with renal impairment — dose reduce in renal impairment. Valacyclovir does not cure herpes — suppressive therapy reduces but does not eliminate transmission.",
        "side_effects": "Common: nausea, headache, dizziness, vomiting, abdominal pain (usually mild). Serious: TTP/HUS (immunocompromised, high dose), CNS toxicity (encephalopathy, seizures — with renal impairment), acute renal failure.",
        "dosage": "Genital herpes (initial): 1000 mg twice daily for 10 days. Genital herpes (recurrent): 500 mg twice daily for 3 days. Chronic suppression (genital herpes): 500-1000 mg once daily. Herpes zoster: 1000 mg three times daily for 7 days (start within 72 hours of rash onset). Herpes labialis (cold sores): 2000 mg every 12 hours for 1 day. All doses require renal adjustment for CrCl <50 mL/min.",
        "before_taking": "Tell your doctor about kidney disease (significant dose adjustment required), HIV or other immunocompromising conditions. Maintain adequate hydration. Tell your doctor about all medications — valacyclovir may affect renal clearance of other drugs. Discuss with your doctor about suppressive therapy to reduce partner transmission risk — use condoms in addition.",
    },
    "isotretinoin": {
        "description": "Isotretinoin (Absorica, Accutane — original brand discontinued) is a naturally occurring retinoid (vitamin A derivative) that dramatically reduces sebaceous gland size and activity, making it the most effective treatment for severe acne. Available as 10, 20, 25, 30, 35, and 40 mg capsules. Dispensed only through the iPLEDGE REMS program.",
        "uses": "Isotretinoin is indicated for severe recalcitrant nodular acne that is unresponsive to conventional therapy including antibiotics. It is also used off-label for other dermatological conditions including rosacea, sebaceous hyperplasia, and gram-negative folliculitis.",
        "warnings": "FDA BOXED WARNINGS: (1) TERATOGENICITY — isotretinoin is severely teratogenic; major fetal abnormalities occur in 35% of exposed pregnancies. Patients who are pregnant or who may become pregnant must not take isotretinoin. iPLEDGE REMS requires females of childbearing potential to use two forms of contraception, complete monthly pregnancy tests, and register in the iPLEDGE program. Males must also register in iPLEDGE. (2) Psychiatric disorders — depression, psychosis, and suicidal ideation have been reported; monitor for mood changes. Isotretinoin causes hyperlipidemia (elevated triglycerides, decreased HDL) and elevated liver enzymes — monitor lipids and LFTs monthly. Inflammatory bowel disease (IBD) cases have been reported (causality unclear). Bone and muscle pain are common. Night blindness and dry eyes. Pseudotumor cerebri (intracranial hypertension) — do not use with tetracyclines (also risk factor).",
        "side_effects": "Very common: dry skin, chapped lips (cheilitis), nosebleeds, dry eyes, musculoskeletal pain, elevated lipids. Serious: teratogenicity, psychiatric effects (depression, suicidality), pseudotumor cerebri, pancreatitis, inflammatory bowel disease (uncertain causality), hearing impairment, night blindness.",
        "dosage": "Typically 0.5-1 mg/kg/day in 2 divided doses; total cumulative dose of 120-150 mg/kg achieves best outcomes and reduces relapse. Treatment course: usually 4-5 months. Take with food (fatty meal increases absorption). Dispensed in 30-day supplies through certified pharmacies only.",
        "before_taking": "Must enroll in iPLEDGE REMS program. Female patients must use two forms of contraception (including one primary form) for 1 month before, during, and 1 month after treatment. Monthly pregnancy tests required. Tell your doctor about personal or family history of psychiatric illness, IBD, elevated triglycerides, liver disease, diabetes, bone disorders, or contact lens use (dry eyes may make contact lenses intolerable). Do not donate blood during treatment or for 1 month after — teratogenicity risk to blood recipients. Avoid vitamin A supplements and tetracyclines during treatment. Avoid waxing, dermabrasion, or laser treatment during and for 6 months after treatment — skin fragility increases scarring risk.",
    },
    "tretinoin": {
        "description": "Tretinoin (Retin-A, Renova, Atralin) is an all-trans retinoic acid available topically as cream (0.025%, 0.05%, 0.1%), gel (0.01%, 0.025%, 0.05%), and micro-gel. Oral tretinoin (Vesanoid) is used for acute promyelocytic leukemia.",
        "uses": "Topical tretinoin is indicated for acne vulgaris. It is also widely used off-label for photoaging (fine wrinkles, mottled hyperpigmentation, rough skin texture) and other dermatological conditions. Oral tretinoin is indicated for induction of remission in acute promyelocytic leukemia (APL).",
        "warnings": "Topical tretinoin causes photosensitivity — avoid sun exposure; use sunscreen and protective clothing. Skin irritation (erythema, dryness, scaling, burning) is common during initiation; use less frequently and gradually increase. Do not use with other potentially irritating topical products (benzoyl peroxide in combination may cause irritation, though often used sequentially). Avoid contact with eyes, mouth, and mucous membranes. Topical tretinoin is Category C in pregnancy — avoid; use effective contraception.",
        "side_effects": "Common: skin irritation (erythema, peeling, stinging, dryness), photosensitivity, worsening of acne in first 2-6 weeks (purging phase). Serious: severe skin irritation (apply less frequently to reduce), teratogenicity (topical — low systemic absorption but category C).",
        "dosage": "Acne: apply a thin layer to affected area once daily at bedtime after washing and drying skin. Start with lower concentrations (0.025%) and increase gradually. Results typically seen after 8-12 weeks of consistent use.",
        "before_taking": "Always use sunscreen during the day while using topical tretinoin. Avoid waxing, dermabrasion, or chemical peels on treated areas. Start with the lowest concentration; apply every other night initially to reduce irritation. Do not use in pregnancy. Tretinoin may increase sensitivity to wind and cold. Avoid abrasive soaps and irritating skin products.",
    },
    "methotrexate": {
        "description": "Methotrexate (Trexall, Otrexup, Rasuvo) is an antimetabolite that inhibits dihydrofolate reductase, reducing cellular folate availability. At high doses, it is a cytotoxic chemotherapy agent; at low weekly doses, it is a disease-modifying antirheumatic drug (DMARD) and immunosuppressant.",
        "uses": "Methotrexate is indicated for: rheumatoid arthritis (cornerstone DMARD therapy), juvenile idiopathic arthritis, psoriasis (severe, recalcitrant), neoplastic diseases (ALL, NHL, osteosarcoma, breast cancer, head/neck cancer, lung cancer, choriocarcinoma), and ectopic pregnancy (medical management with IM injection).",
        "warnings": "FDA BOXED WARNINGS: (1) Toxic deaths — use only in life-threatening neoplastic diseases or severe psoriasis/RA when conventional therapy has failed and risks are carefully weighed. (2) Renal damage — can cause fatal renal failure at high doses; NSAIDs increase methotrexate toxicity by reducing renal clearance. (3) GI toxicity — diarrhea and ulcerative stomatitis require dose reduction; potentially fatal GI hemorrhage/perforation. (4) Hepatotoxicity — fibrosis and cirrhosis with long-term low-dose use; liver biopsy recommended after cumulative dose of 1.5 g. (5) Pulmonary toxicity — acute or chronic interstitial pneumonitis (methotrexate pneumonitis); monitor for cough/dyspnea. (6) Teratogenicity — embryotoxic and fetotoxic; causes fetal death or malformations. (7) Immunosuppression — opportunistic infections. Bone marrow suppression — monitor CBC weekly early in therapy. AVOID NSAIDs (especially indomethacin) with methotrexate — can increase levels to toxic range.",
        "side_effects": "Low-dose rheumatology/dermatology: nausea, oral ulcers (stomatitis), fatigue, elevated LFTs. Serious: hepatic fibrosis/cirrhosis, bone marrow suppression, methotrexate pneumonitis, renal failure, severe skin reactions (SJS, TEN).",
        "dosage": "Rheumatoid arthritis: 7.5-25 mg once weekly (oral, SC, or IM); folic acid 1-5 mg/day supplementation reduces toxicity. Psoriasis: 10-25 mg once weekly. Cancer: dosing is highly variable and protocol-dependent. ALWAYS take with folic acid supplementation when used for RA or psoriasis.",
        "before_taking": "Not for women of childbearing potential unless on reliable contraception — teratogenic. Avoid in pregnancy, breastfeeding, or planning pregnancy (within at least 3 months for males, 1 ovulatory cycle for females). Avoid alcohol (additive hepatotoxicity). Tell your doctor about kidney disease (major dose reduction required), liver disease, blood disorders, lung disease, peptic ulcer, and all medications — NSAIDs (especially indomethacin) significantly increase methotrexate toxicity. Supplement with folic acid to reduce side effects. Monitor CBC, LFTs, creatinine regularly.",
    },
    "tirzepatide": {
        "description": "Tirzepatide (Mounjaro for diabetes; Zepbound for weight management) is a novel dual GIP (glucose-dependent insulinotropic polypeptide) and GLP-1 receptor agonist administered as a once-weekly subcutaneous injection in 2.5, 5, 7.5, 10, 12.5, and 15 mg doses.",
        "uses": "Tirzepatide (Mounjaro) is indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes mellitus. Tirzepatide (Zepbound) is indicated for chronic weight management in adults with obesity (BMI ≥30) or overweight (BMI ≥27) with at least one weight-related comorbidity.",
        "warnings": "FDA BOXED WARNING (class effect): Thyroid C-cell tumors including medullary thyroid carcinoma (MTC) have been observed in animal studies; relevance to humans is unknown. Contraindicated in patients with a personal or family history of MTC or Multiple Endocrine Neoplasia type 2 (MEN 2). Pancreatitis has been reported. Hypoglycemia (usually with insulin or sulfonylureas). Diabetic retinopathy complications. Acute kidney injury (with dehydration from GI side effects). Hypersensitivity reactions. Avoid in pregnancy.",
        "side_effects": "Very common: nausea, vomiting, diarrhea, constipation, abdominal pain — GI effects are most pronounced during dose escalation. Serious: pancreatitis, diabetic retinopathy worsening, hypoglycemia (with insulin or sulfonylurea), thyroid C-cell tumors, acute kidney injury.",
        "dosage": "Type 2 diabetes (Mounjaro) / weight management (Zepbound): Start 2.5 mg SC once weekly for 4 weeks, then increase by 2.5 mg every 4 weeks as tolerated; target doses 5-15 mg once weekly. Inject in abdomen, thigh, or upper arm. Day of the week can vary; rotate injection sites.",
        "before_taking": "Contraindicated in patients with personal or family history of MTC or MEN 2. Do not use in type 1 diabetes or diabetic ketoacidosis. Tell your doctor about pancreatitis history, gallbladder disease, diabetic retinopathy, kidney disease, or depression/suicidal thoughts. Tell your doctor about all medications — particularly insulin and sulfonylureas (hypoglycemia risk). Do not use in pregnancy; use effective contraception. GI side effects are common — start with lowest dose and increase slowly.",
    },
    "liraglutide": {
        "description": "Liraglutide (Victoza for diabetes; Saxenda for weight management) is a GLP-1 receptor agonist (97% homology to human GLP-1) administered as a once-daily subcutaneous injection in 0.6, 1.2, and 1.8 mg doses (Victoza) or up to 3 mg (Saxenda).",
        "uses": "Liraglutide (Victoza) is indicated for glycemic control in type 2 diabetes and to reduce cardiovascular risk in type 2 diabetes patients with established cardiovascular disease. Liraglutide (Saxenda) is indicated for chronic weight management in adults and adolescents ≥12 years.",
        "warnings": "FDA BOXED WARNING: Thyroid C-cell tumors (same class warning as semaglutide and tirzepatide). Contraindicated with personal or family history of MTC or MEN 2. Pancreatitis, gallbladder disease, hypoglycemia with insulin/sulfonylurea, acute kidney injury, and suicidal ideation have been reported. Victoza does not cause weight loss to the same degree as Wegovy/Zepbound but has established cardiovascular benefit.",
        "side_effects": "Very common: nausea, vomiting, diarrhea, constipation. Common: injection site reactions, headache, hypoglycemia (with insulin/sulfonylurea). Serious: pancreatitis, thyroid tumors, gallbladder disease, acute kidney injury.",
        "dosage": "Type 2 diabetes (Victoza): Start 0.6 mg SC once daily for 1 week, then 1.2 mg; may increase to 1.8 mg. Weight management (Saxenda): Start 0.6 mg SC once daily; increase by 0.6 mg/week to target 3 mg/day. Inject in abdomen, thigh, or upper arm, regardless of meals.",
        "before_taking": "Contraindicated with personal or family history of MTC or MEN 2. Tell your doctor about pancreatitis history, gallbladder disease, kidney disease, depression, or suicidal thoughts. Do not use in type 1 diabetes or in pregnancy.",
    },
    "verapamil": {
        "description": "Verapamil (Calan, Verelan, Isoptin) is a non-dihydropyridine calcium channel blocker (phenylalkylamine class) that primarily affects the heart (reducing heart rate and AV conduction) and to a lesser extent vascular smooth muscle. Available as immediate-release tablets (40, 80, 120 mg), extended-release tablets/capsules, and IV injection.",
        "uses": "Verapamil is indicated for angina pectoris (stable, vasospastic/Prinzmetal's, unstable), hypertension, and supraventricular tachyarrhythmias (PSVT, atrial fibrillation/flutter rate control). IV verapamil terminates PSVT acutely.",
        "warnings": "Contraindicated in sick sinus syndrome without pacemaker, second- or third-degree AV block without pacemaker, WPW syndrome with atrial fibrillation (can accelerate ventricular rate via bypass tract), cardiogenic shock, severe left ventricular dysfunction, and hypotension. Do NOT give IV verapamil to patients who have received IV beta-blockers within several hours — risk of complete heart block, asystole. Verapamil is a CYP3A4 and P-gp inhibitor — increases levels of cyclosporine, tacrolimus, statins (myopathy risk), digoxin, carbamazepine, and many others. Constipation is very common.",
        "side_effects": "Common: constipation (most common — sometimes severe), headache, dizziness, flushing, peripheral edema, bradycardia. Serious: AV block, heart failure, severe bradycardia, hepatotoxicity (rare), severe constipation/ileus.",
        "dosage": "Angina/hypertension (IR): 80-120 mg three times daily; usual 240-360 mg/day. Hypertension (ER): 120-360 mg once daily. Atrial fibrillation (IR): 120-360 mg/day in divided doses. IV (PSVT): 5-10 mg IV over 2 minutes; may repeat 10 mg after 30 minutes if needed.",
        "before_taking": "Contraindicated with WPW syndrome and AF (risk of accelerated conduction), cardiogenic shock, severe LV dysfunction. Do not combine with IV beta-blockers. Verapamil is a P-gp and CYP3A4 inhibitor — reduces dose of cyclosporine, increases digoxin and statin levels. Avoid with colchicine in renal impairment. Grapefruit juice increases verapamil levels. Take with food to reduce GI effects.",
    },
    "amoxicillin-clavulanate": {
        "description": "Amoxicillin-clavulanate (Augmentin) is a combination antibiotic consisting of amoxicillin (aminopenicillin) plus clavulanate (a beta-lactamase inhibitor) that extends the spectrum to include beta-lactamase-producing organisms. Available as 250/125, 500/125, 875/125 mg tablets, and pediatric suspensions.",
        "uses": "Amoxicillin-clavulanate is indicated for sinusitis, otitis media, lower respiratory tract infections, urinary tract infections, skin and soft tissue infections, and bite wound infections (animal and human) caused by beta-lactamase-producing organisms that are resistant to amoxicillin alone.",
        "warnings": "Hepatotoxicity including cholestatic jaundice and hepatic necrosis has been reported, primarily with the clavulanate component — incidence is approximately 5-6 cases per 100,000 patients. Risk increases with longer duration and repeated courses. Use with caution in patients with hepatic impairment or previous amoxicillin-clavulanate-associated hepatotoxicity. GI side effects (diarrhea, nausea) are more common than with amoxicillin alone, due to clavulanate. C. diff-associated diarrhea has been reported.",
        "side_effects": "Common: diarrhea (more frequent than with amoxicillin alone, up to 25%), nausea, vomiting, rash. Serious: hepatotoxicity (cholestatic jaundice), Clostridioides difficile colitis, severe allergic reactions (anaphylaxis), severe skin reactions (SJS, TEN).",
        "dosage": "Adults: 875/125 mg every 12 hours or 500/125 mg every 8 hours for 7-14 days depending on indication. Sinusitis/more severe infections: 875/125 mg every 12 hours. Pediatrics: 45 mg/kg/day (amoxicillin component) in 2 divided doses. Take at the beginning of a meal to reduce GI effects.",
        "before_taking": "Cross-reactivity with penicillin allergy — use with caution in patients with penicillin allergy. Tell your doctor about liver disease (increased risk of hepatotoxicity), kidney disease, mononucleosis (rash risk), and all medications. Take with food to minimize GI side effects. Report jaundice, dark urine, or abdominal pain. Tell your doctor if you have had previous hepatic reactions to amoxicillin-clavulanate.",
    },
    "meloxicam": {
        "description": "Meloxicam (Mobic, Vivlodex) is a preferential COX-2 inhibitor NSAID available as 7.5 and 15 mg tablets, 7.5 mg/5 mL oral suspension, and 5 and 10 mg capsules (Vivlodex — bioavailability-optimized capsule).",
        "uses": "Meloxicam is indicated for relief of signs and symptoms of osteoarthritis and rheumatoid arthritis (adults), and juvenile rheumatoid arthritis (children ≥2 years). It is one of the most prescribed NSAIDs globally.",
        "warnings": "FDA BOXED WARNINGS: (1) Cardiovascular risk — NSAIDs increase the risk of serious cardiovascular thrombotic events, MI, and stroke. Risk may increase with higher doses and longer duration. Contraindicated for peri-operative CABG pain. (2) GI risk — can cause serious GI adverse events including bleeding, ulceration, and perforation. Risk is increased in elderly, patients with prior GI event, and with concomitant anticoagulants, corticosteroids, or antiplatelet drugs. Fluid retention and edema. Renal toxicity. Avoid in patients with sulfonamide allergy (controversial — structural similarity).",
        "side_effects": "Common: diarrhea, nausea, abdominal pain, dyspepsia, edema, headache, dizziness. Serious: GI hemorrhage, MI, stroke, renal failure, severe allergic reactions, SJS/TEN.",
        "dosage": "Osteoarthritis: 7.5 mg once daily; may increase to 15 mg once daily. Rheumatoid arthritis: 7.5-15 mg once daily. Take with food, milk, or antacids to reduce GI upset.",
        "before_taking": "Same contraindications as other NSAIDs — avoid in CABG peri-operative period, with history of GI bleeding/peptic ulcer, in third trimester of pregnancy, or with advanced renal disease. Tell your doctor about cardiovascular disease, hypertension, heart failure, kidney disease, liver disease, fluid retention, asthma, or bleeding disorders. Avoid with other NSAIDs, warfarin, ACE inhibitors/ARBs, and diuretics (interactions common). Do not use in third trimester of pregnancy.",
    },
    "ezetimibe": {
        "description": "Ezetimibe (Zetia) is a cholesterol absorption inhibitor that reduces intestinal cholesterol absorption by blocking the Niemann-Pick C1-Like 1 (NPC1L1) protein. Available as 10 mg tablets. Often combined with statins (Vytorin = ezetimibe + simvastatin; Liptruzet = ezetimibe + atorvastatin).",
        "uses": "Ezetimibe is indicated as adjunctive therapy for primary hyperlipidemia to reduce LDL-C, as an adjunct to diet to reduce LDL-C in patients with homozygous familial hypercholesterolemia (with statins), and for homozygous sitosterolemia.",
        "warnings": "Ezetimibe is generally well tolerated with few serious adverse effects. Hepatotoxicity — elevated LFTs have been reported (rare with ezetimibe alone but more common with statin combination — primarily due to statin). Myopathy/rhabdomyolysis can occur, especially in combination with statins (particularly with higher-dose statins). Ezetimibe may reduce the efficacy of fibric acid derivatives when combined. Bile acid sequestrants (cholestyramine) reduce ezetimibe absorption — take ezetimibe 2 hours before or 4 hours after.",
        "side_effects": "Common: headache, diarrhea, sinusitis, arthralgia, upper respiratory tract infection (similar to placebo in trials). Serious: myopathy/rhabdomyolysis (particularly with statins), hepatotoxicity (rare).",
        "dosage": "10 mg once daily, with or without food. Can be taken at any time of day. When combined with a statin or fenofibrate, take at the same time. When combined with a bile acid sequestrant, take ezetimibe 2 hours before or 4 hours after the sequestrant.",
        "before_taking": "Tell your doctor about liver disease (monitor LFTs when combined with statins), kidney disease, and all medications, especially statins, fibrates, and bile acid sequestrants. Ezetimibe reduces LDL by approximately 15-20% when used alone; more commonly used to enhance statin therapy. Not a replacement for statin therapy in most patients.",
    },
    "alendronate": {
        "description": "Alendronate (Fosamax, Binosto) is a nitrogen-containing bisphosphonate that inhibits osteoclast-mediated bone resorption. Available as 35 mg and 70 mg weekly tablets and 10 mg daily tablets for osteoporosis, and 5 mg and 10 mg daily for prevention and treatment of glucocorticoid-induced osteoporosis.",
        "uses": "Alendronate is indicated for treatment and prevention of osteoporosis in postmenopausal women, treatment of osteoporosis in men, treatment of glucocorticoid-induced osteoporosis, and treatment of Paget's disease of bone.",
        "warnings": "Esophageal adverse reactions (esophagitis, erosions, ulcers, and rarely strictures) can occur — must follow strict administration instructions. Patients must take alendronate with 6-8 oz plain water, remain upright for at least 30 minutes, and not eat/drink/take other medications for at least 30 minutes. Osteonecrosis of the jaw (ONJ) has been reported, primarily in cancer patients receiving IV bisphosphonates, but also with oral bisphosphonates. Atypical femoral fractures (subtrochanteric stress fractures) have been reported with long-term use. Renal impairment — avoid in patients with CrCl <35 mL/min.",
        "side_effects": "Common: abdominal pain, dyspepsia, diarrhea, constipation, musculoskeletal pain. Serious: esophageal reactions (esophagitis, ulcers — if administration instructions not followed), osteonecrosis of the jaw (ONJ), atypical femoral fractures (with long-term use), severe musculoskeletal pain, hypocalcemia.",
        "dosage": "Postmenopausal osteoporosis treatment: 10 mg once daily or 70 mg once weekly. Osteoporosis prevention: 5 mg once daily or 35 mg once weekly. Glucocorticoid-induced osteoporosis: 5-10 mg once daily. Take in the morning, immediately upon rising, with 6-8 oz plain water only. Do not lie down for at least 30 minutes. Wait at least 30 minutes before eating, drinking anything other than plain water, or taking other medications.",
        "before_taking": "Must be taken correctly — upright position, plain water only, 30-minute wait before eating or other medications — to prevent esophageal injury. Do not use if you cannot sit or stand upright for 30 minutes, have esophageal abnormalities (stricture, achalasia), or severe kidney disease (CrCl <35 mL/min). Correct hypocalcemia before starting — supplement with calcium and vitamin D. Tell your doctor about dental work planned — inform dentist you take alendronate (ONJ risk). Report any jaw pain, swelling, or thigh/groin pain.",
    },
    "sitagliptin": {
        "description": "Sitagliptin (Januvia) is a dipeptidyl peptidase-4 (DPP-4) inhibitor oral hypoglycemic agent. It prolongs the activity of incretin hormones (GLP-1 and GIP) by inhibiting the enzyme DPP-4 that normally inactivates them. Available as 25, 50, and 100 mg tablets.",
        "uses": "Sitagliptin is indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes mellitus, used as monotherapy or in combination with other antidiabetic agents. It is weight-neutral and has a low risk of hypoglycemia compared to sulfonylureas.",
        "warnings": "Acute pancreatitis has been reported — discontinue if pancreatitis is suspected. Hypersensitivity reactions (anaphylaxis, angioedema, SJS, bullous pemphigoid) have occurred. Heart failure — FDA safety communication: possible increased risk of heart failure with DPP-4 inhibitors (particularly saxagliptin and alogliptin; less clear for sitagliptin). Arthralgia (severe joint pain) has been reported — may be disabling; evaluate and consider discontinuation. Dose adjustment required in renal impairment.",
        "side_effects": "Common: upper respiratory tract infection, nasopharyngitis, headache. Serious: pancreatitis, hypersensitivity reactions (anaphylaxis, angioedema), severe arthralgia, bullous pemphigoid, heart failure.",
        "dosage": "100 mg once daily. Renal impairment: CrCl 30-45 mL/min: 50 mg once daily. CrCl <30 mL/min or ESRD on dialysis: 25 mg once daily. Take with or without food.",
        "before_taking": "Tell your doctor about pancreatitis history, kidney disease (dose adjustment required), heart failure, and all medications. Sitagliptin has low risk of hypoglycemia alone — hypoglycemia risk increases when combined with insulin or sulfonylureas. Report severe persistent abdominal pain (may indicate pancreatitis) or severe joint pain. Sitagliptin is generally weight-neutral and well tolerated.",
    },
    "dapagliflozin": {
        "description": "Dapagliflozin (Farxiga) is a sodium-glucose cotransporter 2 (SGLT2) inhibitor that blocks glucose reabsorption in the proximal renal tubule, increasing urinary glucose excretion. Available as 5 and 10 mg tablets.",
        "uses": "Dapagliflozin is indicated for type 2 diabetes (glycemic control and CV risk reduction in those with CV disease), heart failure with reduced ejection fraction (HFrEF) — regardless of diabetes status, heart failure with preserved ejection fraction (HFpEF), and chronic kidney disease (to reduce eGFR decline, ESKD, CV death, and hospitalization for heart failure).",
        "warnings": "Genital mycotic infections (yeast infections) and urinary tract infections are very common. Ketoacidosis (including euglycemic DKA — blood glucose may not be markedly elevated) has been reported — hold before major surgery and in serious illness. Fournier's gangrene (necrotizing fasciitis of the perineum) has been reported. Hypotension/volume depletion — due to osmotic diuresis. Acute kidney injury. Lower limb amputations have been reported with some SGLT2 inhibitors (particularly canagliflozin). Not recommended when eGFR <25 mL/min for glycemic control (can still be used for CV and renal indications at lower eGFR per updated labeling).",
        "side_effects": "Very common: genital mycotic infections (female > male), urinary tract infections. Serious: euglycemic DKA, Fournier's gangrene, acute kidney injury, UTIs, volume depletion/hypotension.",
        "dosage": "Type 2 diabetes: 5-10 mg once daily. Heart failure and CKD: 10 mg once daily. Take in the morning, with or without food.",
        "before_taking": "Tell your doctor about type 1 diabetes or tendency toward ketoacidosis (should not use), kidney disease, liver disease, bladder cancer (limited data — use with caution), recurrent UTIs or genital yeast infections, and all medications. Hold dapagliflozin at least 3 days before major surgery. Maintain adequate hydration. Monitor for signs of yeast infection, UTI, or ketoacidosis. Do not use in type 1 diabetes.",
    },
    "empagliflozin": {
        "description": "Empagliflozin (Jardiance) is an SGLT2 inhibitor that blocks glucose reabsorption in the proximal tubule. The first SGLT2 inhibitor to demonstrate cardiovascular mortality reduction in the EMPA-REG OUTCOME trial. Available as 10 and 25 mg tablets.",
        "uses": "Empagliflozin is indicated for type 2 diabetes to improve glycemic control and to reduce cardiovascular death in type 2 diabetes patients with established cardiovascular disease, and heart failure with reduced or preserved ejection fraction (regardless of diabetes status).",
        "warnings": "Same class warnings as dapagliflozin: genital yeast infections, UTIs, euglycemic DKA, Fournier's gangrene, volume depletion/hypotension, acute kidney injury. Hold before major surgery. Bone fractures have been reported with some SGLT2 inhibitors. Not recommended for glycemic control when eGFR <30 mL/min.",
        "side_effects": "Very common: genital mycotic infections, UTIs. Serious: euglycemic DKA, Fournier's gangrene, acute kidney injury, volume depletion.",
        "dosage": "Type 2 diabetes: 10 mg once daily in the morning; may increase to 25 mg/day. Heart failure: 10 mg once daily. Take with or without food.",
        "before_taking": "Same precautions as dapagliflozin. Hold 3 days before major surgery. Monitor for genital infections, UTIs, and ketoacidosis signs. The cardiovascular benefit in the EMPA-REG OUTCOME trial makes this a preferred agent for type 2 diabetes patients with established CV disease.",
    },
    "canagliflozin": {
        "description": "Canagliflozin (Invokana) was the first SGLT2 inhibitor approved in the US. Available as 100 and 300 mg tablets. It has the broadest SGLT2 vs. SGLT1 inhibition ratio concern, with additional intestinal SGLT1 inhibition at higher doses.",
        "uses": "Canagliflozin is indicated for type 2 diabetes and to reduce the risk of MACE (major adverse cardiovascular events) in type 2 diabetes with established cardiovascular disease, and to reduce the risk of ESKD, CV death, and hospitalizations in type 2 diabetes with diabetic nephropathy.",
        "warnings": "Same class warnings as other SGLT2 inhibitors, PLUS: increased risk of lower limb amputations (foot, toe, leg) — risk approximately doubled vs. placebo in the CANVAS trial. Assess vascular status and monitor lower extremities. Bone fractures — also increased in the CANVAS trial. Other: euglycemic DKA, Fournier's gangrene, UTIs, genital mycotic infections, volume depletion/hypotension, acute kidney injury.",
        "side_effects": "Very common: genital mycotic infections, UTIs. Serious: lower limb amputations (class concern — highest for canagliflozin), bone fractures, euglycemic DKA, Fournier's gangrene, acute kidney injury.",
        "dosage": "100 mg once daily before the first meal; may increase to 300 mg once daily. Not recommended when eGFR <30 mL/min for glycemic control (may continue 100 mg for CKD indication per updated labeling).",
        "before_taking": "Assess lower extremity status before starting and monitor regularly — increased amputation risk. Tell your doctor about peripheral artery disease, neuropathy, history of foot ulcers or amputations, or recurrent infections. Same precautions as other SGLT2 inhibitors. Hold before major surgery.",
    },
    "enoxaparin": {
        "description": "Enoxaparin (Lovenox) is a low molecular weight heparin (LMWH) derived from porcine intestinal mucosa. It is administered by subcutaneous injection and provides more predictable anticoagulation than unfractionated heparin without routine monitoring in most patients.",
        "uses": "Enoxaparin is indicated for DVT prophylaxis in medical, hip/knee replacement, and abdominal surgery patients; treatment of DVT (with or without PE); treatment of acute STEMI; unstable angina and NSTEMI; and outpatient treatment of DVT without PE.",
        "warnings": "FDA BOXED WARNING: Epidural or spinal hematoma with neuraxial anesthesia or lumbar puncture — monitor frequently for signs of neurological impairment. Dose-adjusted for renal impairment — significant accumulation in renal failure (anti-Xa levels recommended in CrCl <30 mL/min). Heparin-induced thrombocytopenia (HIT) can occur — monitor platelet counts. Use actual body weight for obese patients; monitoring anti-Xa levels recommended in patients at extremes of weight. Avoid in patients with active major bleeding or HIT history.",
        "side_effects": "Common: injection site ecchymosis/bruising, hemorrhage at any site, thrombocytopenia (HIT — rare but serious), elevated LFTs. Serious: major hemorrhage, HIT, epidural/spinal hematoma, anaphylaxis.",
        "dosage": "DVT prophylaxis (medical/surgical): 40 mg SC once daily or 30 mg SC twice daily. DVT/PE treatment: 1 mg/kg SC twice daily or 1.5 mg/kg SC once daily. STEMI: 30 mg IV bolus + 1 mg/kg SC, then 1 mg/kg SC twice daily for 8 days. All doses require renal adjustment for CrCl <30 mL/min.",
        "before_taking": "Tell your doctor about kidney disease (monitoring required, dose adjustment), active bleeding, HIT history, prosthetic heart valves, and all anticoagulants/antiplatelet agents. Inform your anesthesiologist about enoxaparin before neuraxial anesthesia. Enoxaparin is used in pregnancy (does not cross placenta — preferred anticoagulant in pregnancy).",
    },
    "nitrofurantoin": {
        "description": "Nitrofurantoin (Macrobid, Macrodantin) is an antibacterial agent specifically used for urinary tract infections. It is selectively concentrated in urine and has activity against most uropathogens including E. coli, S. saprophyticus, Enterococcus, Klebsiella, and Enterobacter.",
        "uses": "Nitrofurantoin is indicated for treatment of uncomplicated urinary tract infections (cystitis) caused by susceptible strains of E. coli and S. saprophyticus, and for prophylaxis/suppression of recurrent UTIs. It is a first-line option for uncomplicated UTIs in females.",
        "warnings": "Pulmonary reactions (acute and chronic) have been reported — acute reactions (fever, dyspnea, eosinophilia) usually resolve with discontinuation; chronic pulmonary toxicity (pulmonary fibrosis) is rare but can be fatal. Hepatic reactions including cholestatic jaundice, hepatitis, and hepatic necrosis have occurred. Peripheral neuropathy has been reported, primarily in patients with renal impairment. CONTRAINDICATED in patients with CrCl <30 mL/min (drug not effectively concentrated in urine and metabolites may accumulate). Avoid at term pregnancy (38-42 weeks) — risk of neonatal hemolytic anemia. Hemolytic anemia in G6PD-deficient patients.",
        "side_effects": "Common: nausea, headache, flatulence (less with macrocrystalline formulation — Macrobid). Serious: pulmonary toxicity (acute or chronic), hepatotoxicity, peripheral neuropathy, hemolytic anemia (G6PD deficiency).",
        "dosage": "Uncomplicated UTI (Macrobid): 100 mg twice daily for 5 days. Macrodantin: 50-100 mg four times daily for 7 days. Prophylaxis of recurrent UTIs: 50-100 mg once daily at bedtime. Take with food to reduce GI side effects and improve absorption.",
        "before_taking": "Contraindicated in patients with CrCl <30 mL/min — avoid in moderate-severe renal impairment and at term of pregnancy. Tell your doctor about kidney disease, liver disease, anemia, G6PD deficiency, and all medications. Take with food or milk. Not appropriate for upper UTI (pyelonephritis) — nitrofurantoin does not achieve adequate tissue levels. Urine may turn brown — reassure patients this is normal.",
    },
    "pseudoephedrine": {
        "description": "Pseudoephedrine (Sudafed) is an oral nasal decongestant and sympathomimetic amine that stimulates alpha-adrenergic receptors. Available as 30 and 60 mg IR tablets and 120 and 240 mg ER tablets. Sold behind pharmacy counter due to Combat Methamphetamine Epidemic Act of 2005.",
        "uses": "Pseudoephedrine is indicated for temporary relief of nasal congestion due to the common cold, allergic rhinitis (hay fever), upper respiratory tract infections, and sinusitis. It also provides relief of Eustachian tube congestion.",
        "warnings": "Use with caution in patients with hypertension, coronary artery disease, hyperthyroidism, diabetes, benign prostatic hyperplasia, or glaucoma. Do not use with MAO inhibitors — risk of hypertensive crisis. Avoid in patients with severe hypertension or severe coronary artery disease. Central nervous system stimulation (anxiety, insomnia, nervousness) is common. Urinary retention may occur in patients with BPH.",
        "side_effects": "Common: nervousness, restlessness, insomnia, dizziness, headache, increased heart rate, increased blood pressure, dry mouth. Serious: cardiac arrhythmias, severe hypertension, stroke (with excessive doses), urinary retention.",
        "dosage": "IR: 60 mg every 4-6 hours; maximum 240 mg/day. ER (12-hour): 120 mg every 12 hours. ER (24-hour): 240 mg once daily. Do not exceed recommended doses. Children: not recommended in children under 12 without physician guidance.",
        "before_taking": "Do not use with MAO inhibitors or within 14 days. Tell your doctor about high blood pressure, heart disease, thyroid disease, diabetes, enlarged prostate, kidney disease, or glaucoma. Limit caffeine intake (additive stimulant effects). Not recommended for chronic use. OTC decongestants should not be used for more than 7 days without physician evaluation.",
    },
    "dextromethorphan": {
        "description": "Dextromethorphan (DM; found in Robitussin DM, NyQuil, Mucinex DM, and many others) is an OTC antitussive (cough suppressant) and NMDA receptor antagonist. Available in many combination products. Also available as Nuedexta (with quinidine) for pseudobulbar affect.",
        "uses": "Dextromethorphan is used for temporary relief of cough due to minor throat and bronchial irritation (from colds, inhaled irritants). Nuedexta (dextromethorphan + quinidine) is indicated for pseudobulbar affect (involuntary emotional expression disorder).",
        "warnings": "Do not use with MAO inhibitors (risk of serious reaction including fever, high blood pressure, and serotonin syndrome). Abuse potential at high doses (dissociative/psychedelic effects) — particularly in adolescents (DXM abuse, 'robotripping'). Serotonin syndrome possible with SSRIs and other serotonergic drugs. Do not use for chronic cough (COPD, smoking, asthma) — see physician. Not recommended in children under 4 years. May cause drowsiness in some people.",
        "side_effects": "Therapeutic doses: nausea, dizziness, drowsiness. Abuse/overdose: confusion, hallucinations, dissociation, tachycardia, hypertension, hyperthermia.",
        "dosage": "Adults: 15-30 mg every 4 hours or 30 mg every 6-8 hours; maximum 120 mg/day. ER formulations: 60 mg twice daily. Do not exceed recommended doses.",
        "before_taking": "Do not use with MAO inhibitors. Tell your doctor about liver disease, kidney disease, and all medications (SSRIs, TCAs — serotonin syndrome risk). OTC products often contain multiple ingredients — check all ingredients before combining products. Not appropriate for cough associated with asthma, bronchitis, emphysema, or excessive phlegm.",
    },
    "dabigatran": {
        "description": "Dabigatran (Pradaxa) is an oral direct thrombin inhibitor (DTI) anticoagulant available as 75 mg, 110 mg, and 150 mg capsules. It does not require INR monitoring. Idarucizumab (Praxbind) is the FDA-approved reversal agent.",
        "uses": "Dabigatran is indicated for reduction of stroke and systemic embolism risk in non-valvular atrial fibrillation, treatment of DVT and PE in patients treated with parenteral anticoagulant for 5-10 days, and prevention of recurrence of DVT and PE, and prophylaxis of DVT after hip replacement surgery.",
        "warnings": "FDA BOXED WARNING: Premature discontinuation increases stroke risk. Risk of epidural/spinal hematoma with neuraxial anesthesia. Dabigatran is renally eliminated — reduced clearance in renal impairment (avoid or dose-adjust in CrCl <30 mL/min for most indications). P-glycoprotein inhibitors (dronedarone, ketoconazole, clarithromycin, amiodarone, verapamil) increase dabigatran levels — may require dose reduction. P-gp inducers (rifampin) reduce dabigatran levels. Significant interactions with antifungals, antibiotics, and antiarrhythmics.",
        "side_effects": "Common: bleeding (any site), GI symptoms (dyspepsia, nausea, abdominal pain — more common than with warfarin). Serious: major hemorrhage, GI bleeding, epidural/spinal hematoma.",
        "dosage": "Atrial fibrillation: 150 mg twice daily (CrCl >30); 75 mg twice daily (CrCl 15-30). DVT/PE treatment: 150 mg twice daily after parenteral anticoagulation for 5-10 days. Hip replacement prophylaxis: 110 mg on day of surgery (1-4 hours post-op), then 220 mg once daily for 28-35 days.",
        "before_taking": "Tell your doctor about kidney disease — dose reduction needed. Tell your doctor about all medications, especially P-gp inhibitors and inducers. Store in original package — dabigatran is moisture-sensitive; discard 4 months after opening. Antidote: idarucizumab (Praxbind) reverses dabigatran anticoagulation. Take with or without food to reduce GI symptoms.",
    },
    "ramipril": {
        "description": "Ramipril (Altace) is an ACE (angiotensin-converting enzyme) inhibitor prodrug converted to ramiprilat, the active form. Available as 1.25, 2.5, 5, and 10 mg capsules.",
        "uses": "Ramipril is indicated for hypertension, heart failure post-MI, and reduction of risk of MI, stroke, and cardiovascular death in patients ≥55 years with high cardiovascular risk (based on HOPE trial). It has strong evidence for cardiovascular protection beyond blood pressure lowering.",
        "warnings": "FDA BOXED WARNING: Ramipril can cause fetal/neonatal injury and death when used in the second and third trimester of pregnancy (fetal nephrotoxicity, oligohydramnios, limb contractures, pulmonary hypoplasia, neonatal hypotension, anuria). Discontinue immediately if pregnancy detected. Angioedema of the face, lips, tongue, larynx, or intestines can occur (potentially life-threatening laryngeal involvement) — higher risk in Black patients. Hyperkalemia, especially in patients with renal impairment, diabetes, or on potassium supplements/sparing diuretics. Renal function deterioration in patients with bilateral renal artery stenosis or single kidney.",
        "side_effects": "Common: cough (dry, persistent — class effect; affects 10-20% of patients; more common in women and Asian patients), dizziness, hypotension (first-dose effect, especially with diuretics), hyperkalemia, elevated creatinine. Serious: angioedema (can be life-threatening), severe hypotension, renal failure, neutropenia/agranulocytosis.",
        "dosage": "Hypertension: Start 2.5 mg once daily; maintenance 2.5-20 mg/day in 1-2 doses. Heart failure post-MI: Start 2.5 mg twice daily; target 5 mg twice daily. CV risk reduction: Start 2.5 mg once daily for 1 week, then 5 mg once daily for 3 weeks, then 10 mg once daily. Reduce starting dose in patients on diuretics or with renal impairment.",
        "before_taking": "Do not use in pregnancy — switch to another antihypertensive. Do not combine with other ACE inhibitors, ARBs, or aliskiren (increased risk of adverse effects). Tell your doctor about kidney disease, renal artery stenosis, hyperkalemia, liver disease, bilateral renal artery stenosis, previous ACE inhibitor-induced angioedema. If cough is intolerable, switch to an ARB (does not cause cough). Seek emergency care for angioedema (facial swelling, throat tightening).",
    },
    "enalapril": {
        "description": "Enalapril (Vasotec) is an ACE inhibitor prodrug converted to enalaprilat. Available as 2.5, 5, 10, and 20 mg tablets. Enalaprilat is available as IV injection for hypertensive urgency when oral therapy is not feasible.",
        "uses": "Enalapril is indicated for hypertension, heart failure (to reduce hospitalizations and mortality), and asymptomatic left ventricular dysfunction (to slow progression to symptomatic heart failure). It was among the first ACE inhibitors to demonstrate mortality benefit in heart failure (CONSENSUS and SOLVD trials).",
        "warnings": "Same class warnings as ramipril: teratogenicity (Category D), angioedema, hyperkalemia, renal function deterioration. Cough is a class effect (10-20% of patients). Do not combine with ARBs, other ACE inhibitors, or aliskiren. First-dose hypotension in patients who are volume-depleted or on diuretics.",
        "side_effects": "Same as ramipril: cough, dizziness, hypotension, hyperkalemia, elevated creatinine. Serious: angioedema, severe hypotension, renal failure, neutropenia.",
        "dosage": "Hypertension: Start 5 mg once daily (2.5 mg in patients on diuretics or with renal impairment); usual maintenance 10-40 mg/day in 1-2 doses. Heart failure: Start 2.5 mg twice daily; target 10-20 mg twice daily. Asymptomatic LV dysfunction: Start 2.5 mg twice daily; target 10 mg twice daily.",
        "before_taking": "Contraindicated in pregnancy. Same precautions as all ACE inhibitors — monitor potassium and creatinine, avoid with ARBs/aliskiren, watch for angioedema and first-dose hypotension. If dry cough is intolerable, switch to an ARB.",
    },
    "benazepril": {
        "description": "Benazepril (Lotensin) is an ACE inhibitor prodrug converted to benazeprilat. Available as 5, 10, 20, and 40 mg tablets. Also available in combination with amlodipine (Lotrel) and hydrochlorothiazide.",
        "uses": "Benazepril is indicated for hypertension in adults and children ≥6 years. It is also used off-label for heart failure, proteinuric renal disease, and diabetic nephropathy.",
        "warnings": "Same class warnings as other ACE inhibitors: teratogenicity (second/third trimester), angioedema, cough, hyperkalemia, renal function deterioration. Contraindicated with sacubitril (Entresto) due to risk of angioedema — allow 36-hour washout between stopping sacubitril and starting an ACE inhibitor.",
        "side_effects": "Cough (dry, persistent), dizziness, hypotension, headache, hyperkalemia. Serious: angioedema, severe hypotension, renal failure.",
        "dosage": "Hypertension (adults): Start 10 mg once daily; usual maintenance 20-40 mg/day in 1-2 doses; maximum 80 mg/day. Pediatric hypertension (≥6 years): 0.1-0.6 mg/kg/day. Renal impairment (CrCl <30 mL/min): Start 5 mg once daily.",
        "before_taking": "Same precautions as all ACE inhibitors. Do not use in pregnancy. Monitor potassium and creatinine. If cough is problematic, switch to an ARB. Do not combine with sacubitril — wait 36 hours. Check for bilateral renal artery stenosis.",
    },
    "olmesartan": {
        "description": "Olmesartan (Benicar) is an angiotensin II receptor blocker (ARB) available as 5, 20, and 40 mg tablets. Also available in combination with amlodipine (Azor), hydrochlorothiazide (Benicar HCT), and both (Tribenzor).",
        "uses": "Olmesartan is indicated for hypertension in adults and children ≥6 years. It is also used off-label for heart failure, diabetic nephropathy, and post-MI cardioprotection.",
        "warnings": "FDA BOXED WARNING: Like all ARBs, olmesartan can cause fetal/neonatal injury and death in the second and third trimester of pregnancy (same mechanism as ACE inhibitors — renin-angiotensin system blockade). SPRUE-LIKE ENTEROPATHY: olmesartan has been associated with severe, possibly immune-mediated enteropathy (villous atrophy, severe diarrhea, weight loss resembling celiac disease) after months to years of use — discontinue if this develops. Hyperkalemia. Renal function deterioration. Hypotension.",
        "side_effects": "Common: dizziness, headache, hyperkalemia, elevated creatinine. Serious: teratogenicity, sprue-like enteropathy (unique to olmesartan among ARBs), angioedema (rare), renal failure, hypotension.",
        "dosage": "Hypertension (adults): 20 mg once daily; may increase to 40 mg once daily after 2 weeks. Children 6-16 years: 10-20 mg once daily (≥35 kg) or 2.5-20 mg once daily (<35 kg).",
        "before_taking": "Do not use in pregnancy. Tell your doctor about kidney disease, liver disease, heart failure, dehydration, and all medications (especially potassium supplements, potassium-sparing diuretics, NSAIDs, other renin-angiotensin system blockers). Report severe diarrhea or significant weight loss — may indicate olmesartan-associated enteropathy.",
    },
    "irbesartan": {
        "description": "Irbesartan (Avapro) is an angiotensin II receptor blocker (ARB) available as 75, 150, and 300 mg tablets. Also available in combination with hydrochlorothiazide (Avalide).",
        "uses": "Irbesartan is indicated for hypertension, and for the treatment of diabetic nephropathy in patients with type 2 diabetes and hypertension (with evidence of renal disease: elevated serum creatinine and proteinuria). Irbesartan demonstrated renal protection in the IDNT trial.",
        "warnings": "Same class warnings as all ARBs: teratogenicity (second/third trimester), hyperkalemia, renal function deterioration. Avoid in patients with bilateral renal artery stenosis. Do not combine with ACE inhibitors or aliskiren.",
        "side_effects": "Common: dizziness, fatigue, diarrhea, hyperkalemia. Serious: teratogenicity, angioedema (rare), renal failure, hypotension.",
        "dosage": "Hypertension: 150 mg once daily; may increase to 300 mg once daily. Diabetic nephropathy: 300 mg once daily. Can take with or without food.",
        "before_taking": "Contraindicated in pregnancy. Tell your doctor about kidney disease, liver disease, heart failure, and all medications. Unlike ACE inhibitors, irbesartan does not cause cough.",
    },
    "atomoxetine": {
        "description": "Atomoxetine (Strattera) is a selective norepinephrine reuptake inhibitor (SNRI) non-stimulant medication for ADHD. Available as 10, 18, 25, 40, 60, 80, and 100 mg capsules. It is not a controlled substance.",
        "uses": "Atomoxetine is indicated for the treatment of Attention Deficit Hyperactivity Disorder (ADHD) in children ≥6 years, adolescents, and adults. As a non-stimulant, it is an option for patients who cannot tolerate or have contraindications to stimulants, or who have ADHD with comorbid anxiety or substance use disorder.",
        "warnings": "FDA BOXED WARNING: Suicidal ideation — atomoxetine increased the risk of suicidal ideation in short-term studies in children and adolescents with ADHD. Monitor for clinical worsening, suicidal ideation, and unusual changes in behavior. Hepatotoxicity (rare but serious hepatic injury has occurred — discontinue if jaundice or hepatic injury occurs). Cardiovascular effects: can increase heart rate and blood pressure — avoid in patients with cardiovascular disease or structural heart defects. Urinary retention and decreased urine flow. CYP2D6 inhibitors (paroxetine, fluoxetine, quinidine) substantially increase atomoxetine exposure.",
        "side_effects": "Common: decreased appetite, nausea, vomiting, dizziness, fatigue, constipation, dry mouth, insomnia, increased heart rate and blood pressure. Serious: suicidal ideation, hepatotoxicity, cardiovascular events (hypertension, tachycardia), urinary retention, priapism.",
        "dosage": "Children and adolescents ≤70 kg: Start 0.5 mg/kg/day for ≥3 days, then 1.2 mg/kg/day; maximum 1.4 mg/kg/day or 100 mg/day. Adults and children >70 kg: Start 40 mg/day; after ≥3 days increase to 80 mg/day; target 80-100 mg/day. CYP2D6 poor metabolizers or on CYP2D6 inhibitors: start at minimum dose and only increase if well tolerated after 4 weeks.",
        "before_taking": "Tell your doctor about heart disease, high blood pressure, urinary problems, liver disease, glaucoma, bipolar disorder, or family history of QT prolongation. Tell your doctor about all medications — especially paroxetine, fluoxetine, and MAO inhibitors (do not use within 14 days of MAOI). Atomoxetine may take 2-4 weeks for full effect. Unlike stimulants, it is not a controlled substance.",
    },
    "minocycline": {
        "description": "Minocycline (Minocin, Solodyn) is a broad-spectrum semisynthetic tetracycline antibiotic available as 50, 75, 100 mg capsules/tablets and extended-release tablets (Solodyn). It has excellent tissue penetration and unique activity against some MRSA strains.",
        "uses": "Minocycline is indicated for a wide range of infections including respiratory tract infections, urinary tract infections, skin and soft tissue infections, sexually transmitted infections (chlamydia, gonorrhea, syphilis), rickettsial diseases, acne vulgaris (inflammatory acne), and as alternative therapy for MRSA skin infections.",
        "warnings": "Same class concerns as doxycycline: avoid in children under 8 years (permanent tooth discoloration and enamel hypoplasia) and in the second half of pregnancy. Photosensitivity (less than doxycycline). Vestibular side effects (dizziness, vertigo, ataxia) are common and dose-dependent — unique to minocycline among tetracyclines. Autoimmune syndromes (drug-induced lupus, hepatitis, serum sickness-like syndrome) have been reported with prolonged use. Pseudotumor cerebri (intracranial hypertension) has been reported. Esophageal irritation — take with adequate water, remain upright.",
        "side_effects": "Common: nausea, vomiting, diarrhea, dizziness, vertigo (vestibular toxicity), photosensitivity, skin/mucous membrane hyperpigmentation (blue-grey discoloration with prolonged use). Serious: pseudotumor cerebri, drug-induced lupus, autoimmune hepatitis, SJS/TEN.",
        "dosage": "Most infections (adults): 200 mg initially, then 100 mg every 12 hours. Acne (Solodyn ER): weight-based once-daily dosing. Standard acne: 50-100 mg twice daily. Take with adequate fluid. Take with food to reduce GI effects.",
        "before_taking": "Avoid in children under 8 years and in the second half of pregnancy. Take upright with a full glass of water to prevent esophageal irritation. Avoid sun exposure and use sunscreen. Tell your doctor about autoimmune conditions, liver disease, kidney disease, or lupus. Antacids, calcium, iron, zinc, and bismuth reduce absorption — take 2-3 hours apart.",
    },
    "tetracycline": {
        "description": "Tetracycline (Sumycin) is the original tetracycline antibiotic available as 250 and 500 mg capsules. Due to significant drug and food interactions affecting bioavailability and the availability of better-tolerated alternatives (doxycycline, minocycline), tetracycline use has declined.",
        "uses": "Tetracycline is indicated for respiratory infections, skin/soft tissue infections, sexually transmitted infections, rickettsial diseases, H. pylori eradication, acne vulgaris, and as a broad-spectrum reserve antibiotic.",
        "warnings": "Avoid in children under 8 years (permanent tooth discoloration) and in the second half of pregnancy. Food (especially dairy), antacids, iron, calcium, magnesium, and zinc dramatically reduce tetracycline absorption (more so than doxycycline) — must be taken on an empty stomach. Photosensitivity. Esophageal ulceration. Pseudotumor cerebri.",
        "side_effects": "Nausea, vomiting, diarrhea, photosensitivity, esophageal irritation. Serious: pseudotumor cerebri, severe skin reactions, C. diff colitis.",
        "dosage": "500 mg four times daily or 250 mg four times daily for most infections. Take on an empty stomach (1 hour before or 2 hours after meals). Avoid dairy, antacids, iron supplements within 2-3 hours.",
        "before_taking": "Must be taken on an empty stomach and separate from dairy, antacids, iron, and calcium. Avoid in children under 8 and during pregnancy. Store away from light and moisture.",
    },
    "tacrolimus": {
        "description": "Tacrolimus (Prograf, Envarsus XR) is a calcineurin inhibitor immunosuppressant used in organ transplantation and for some autoimmune conditions. Available as 0.5, 1, and 5 mg capsules (Prograf), 0.75 and 4 mg extended-release tablets (Envarsus XR), and topical ointment (Protopic) for atopic dermatitis.",
        "uses": "Oral tacrolimus is indicated for prophylaxis of organ rejection in kidney, liver, and heart transplant recipients. Topical tacrolimus (Protopic) is indicated for moderate-to-severe atopic dermatitis in patients ≥2 years who are not adequately controlled with conventional therapies.",
        "warnings": "FDA BOXED WARNINGS (oral): (1) Malignancy and serious infections — immunosuppression increases risk of lymphoma and other malignancies, and opportunistic infections. (2) Nephrotoxicity and neurotoxicity — monitor renal function and neurological status closely. Narrow therapeutic index — requires frequent blood level monitoring. CYP3A4 and P-gp substrate — extensive drug interactions (CYP3A4 inhibitors such as azole antifungals, macrolides, calcium channel blockers dramatically increase levels; CYP3A4 inducers such as rifampin dramatically decrease levels). Avoid grapefruit and grapefruit juice. Hyperglycemia and new-onset diabetes after transplant (NODAT). Hyperkalemia. QT prolongation. FDA BOXED WARNING (topical Protopic): Long-term safety concerns regarding rare risk of malignancy — use minimum necessary to control symptoms; not for long-term continuous use.",
        "side_effects": "Common: nephrotoxicity, neurotoxicity (tremor, headache, insomnia, paresthesia), hypertension, hyperglycemia, hyperkalemia, GI effects. Serious: opportunistic infections, lymphoma, PTLD, nephrotoxicity, QT prolongation.",
        "dosage": "Transplant dosing is complex and highly individualized based on trough levels. Initial doses vary by organ and protocol; typical trough target ranges: kidney 5-15 ng/mL (early), 5-10 ng/mL (maintenance); liver 5-20 ng/mL (early). Topical (Protopic): apply thin layer to affected skin twice daily; discontinue when symptoms resolve.",
        "before_taking": "Oral tacrolimus requires frequent monitoring of blood levels, renal function, and electrolytes. Tell your doctor about all medications — extensive CYP3A4 interactions. Avoid grapefruit. Do not receive live vaccines. Topical: avoid eyes; apply only to affected areas; do not use in immunocompromised patients; do not use extensively or continuously long-term.",
    },
    "cyclosporine": {
        "description": "Cyclosporine (Sandimmune, Neoral, Restasis) is a calcineurin inhibitor immunosuppressant. Sandimmune and Neoral are NOT bioequivalent and should not be used interchangeably. Available as 25 and 100 mg capsules, 100 mg/mL oral solution, and IV injection. Restasis is an ophthalmic emulsion for dry eye.",
        "uses": "Oral cyclosporine is indicated for prophylaxis of organ rejection in kidney, liver, and heart transplant, rheumatoid arthritis (Neoral), and severe recalcitrant psoriasis (Neoral). Restasis ophthalmic is indicated for dry eye disease associated with inflammation.",
        "warnings": "FDA BOXED WARNINGS: (1) Nephrotoxicity — can cause severe renal insufficiency; monitor renal function. (2) Hypertension — new or worsening hypertension; monitor blood pressure and treat. (3) Malignancy and serious infections — increased risk of lymphoma and skin cancers. (4) Sandimmune has poor and erratic oral absorption — Sandimmune and Neoral are NOT interchangeable without blood level monitoring. Cyclosporine is a CYP3A4 and P-gp substrate AND inhibitor — extensive drug interactions (increases levels of statins — rhabdomyolysis risk; increases colchicine toxicity; increases methotrexate toxicity; interacts with many antibiotics, antifungals, and antivirals).",
        "side_effects": "Common: nephrotoxicity, hypertension, gingival hyperplasia, hirsutism, tremor, hyperlipidemia, nausea, headache. Serious: renal failure, malignancy, opportunistic infections, HUS/TTP (rare).",
        "dosage": "Transplant: 2.5-15 mg/kg/day in 2 divided doses; dose based on blood trough levels. RA (Neoral): 2.5 mg/kg/day in 2 divided doses; may increase to maximum 4 mg/kg/day. Psoriasis (Neoral): 2.5-5 mg/kg/day in 2 divided doses. Restasis eye drops: 1 drop twice daily.",
        "before_taking": "Sandimmune and Neoral are NOT interchangeable — do not switch without medical supervision. Frequent monitoring of blood levels, renal function, blood pressure, and potassium required. Tell your doctor about all medications — extensive interactions with CYP3A4 substrates and inhibitors. Avoid high-potassium foods; reduce sun exposure; maintain good dental hygiene (gingival hyperplasia). Do not take with grapefruit juice.",
    },
    "penicillin": {
        "description": "Penicillin (penicillin V potassium — Veetids; penicillin G — injectable) is the original natural beta-lactam antibiotic. Penicillin V (oral) is available as 250 and 500 mg tablets and 125 and 250 mg/5 mL oral suspension.",
        "uses": "Penicillin V is indicated for mild-to-moderate upper respiratory tract infections (streptococcal pharyngitis — first-line, otitis media), skin infections, and prophylaxis of rheumatic fever recurrence and pneumococcal infections. Penicillin G (injectable) is used for severe infections including syphilis, meningitis, and endocarditis.",
        "warnings": "Penicillin hypersensitivity — can range from mild rash to anaphylaxis. True penicillin anaphylaxis affects approximately 0.01% of treatment courses; skin testing is available for evaluation. Cross-reactivity with cephalosporins is estimated at 1-2% (lower than historically believed). Penicillin may reduce effectiveness of oral contraceptives (use backup method). Infectious mononucleosis significantly increases risk of ampicillin/amoxicillin rash — not penicillin V.",
        "side_effects": "Common: diarrhea, nausea, vomiting, rash. Serious: anaphylaxis (immediate hypersensitivity), serum sickness (delayed hypersensitivity), C. diff colitis, hemolytic anemia, neutropenia.",
        "dosage": "Streptococcal pharyngitis: 500 mg twice daily or 250 mg 4 times daily for 10 days. Rheumatic fever prophylaxis: 250 mg twice daily. Take with or without food.",
        "before_taking": "Tell your doctor if you have penicillin allergy. Penicillin allergy self-report is common but confirmed allergy on testing is much less common — consider allergy evaluation if penicillin would otherwise be preferred. Tell your doctor about kidney disease (dose adjustment for severe renal impairment) and all medications.",
    },
    "nifedipine": {
        "description": "Nifedipine (Procardia, Adalat CC, Nifediac CC) is a dihydropyridine calcium channel blocker (CCB) that primarily relaxes vascular smooth muscle. Available as immediate-release 10 and 20 mg capsules (not for hypertension), and extended-release 30, 60, 90 mg tablets.",
        "uses": "Extended-release nifedipine is indicated for hypertension and angina. Immediate-release nifedipine should NOT be used for hypertension — associated with adverse cardiovascular events. Short-acting nifedipine is sometimes used off-label for acute hypertensive episodes in pregnancy, Raynaud's phenomenon, and esophageal spasm.",
        "warnings": "FDA advisory: Short-acting nifedipine capsules should NOT be used for hypertension, hypertensive emergencies, or angina — associated with increased risk of MI and death. Excessive hypotension and reflex tachycardia can occur. Peripheral edema is common. CYP3A4 substrate — interactions with inhibitors (azole antifungals, erythromycin, grapefruit) increase levels; CYP3A4 inducers (rifampin, phenytoin, carbamazepine) decrease levels. Avoid grapefruit juice.",
        "side_effects": "Common: peripheral edema (ankle swelling), flushing, headache, dizziness, reflex tachycardia, nausea, constipation. Serious: excessive hypotension, angina (short-acting formulation in CAD), heart failure (short-acting).",
        "dosage": "Hypertension (ER only): 30-60 mg once daily; maximum 90 mg/day. Angina (ER): 30-90 mg once daily. Do not crush, chew, or break ER tablets. Do not use short-acting (liquid-filled capsule) formulations for hypertension.",
        "before_taking": "Use only extended-release formulations for hypertension or angina — do NOT use short-acting capsule formulations. Tell your doctor about heart failure, liver disease, and all medications. Avoid grapefruit juice. Do not stop abruptly — may precipitate angina.",
    },
    "haloperidol": {
        "description": "Haloperidol (Haldol) is a first-generation (typical) antipsychotic (butyrophenone class). Available as 0.5, 1, 2, 5, 10, 20 mg tablets, oral solution (2 mg/mL), IM injection (short-acting, Haldol lactate), and IM depot injection (Haldol Decanoate — monthly).",
        "uses": "Haloperidol is indicated for schizophrenia, acute agitation, tic disorders (Tourette syndrome), and as second-line treatment for behavioral problems in children with severe hyperactivity and combativeness. It is commonly used in hospital settings for acute agitation and delirium.",
        "warnings": "FDA BOXED WARNING: Elderly patients with dementia-related psychosis treated with antipsychotics are at an increased risk of death — haloperidol is NOT approved for dementia-related psychosis. High risk of extrapyramidal adverse effects (EPS): acute dystonic reactions (oculogyric crisis, torticollis, opisthotonus), akathisia, parkinsonism, tardive dyskinesia. Neuroleptic malignant syndrome (NMS). QT interval prolongation and torsades de pointes — IV haloperidol (off-label) is particularly associated with QT prolongation; avoid IV route or use with extreme caution. Hypotension. Seizure threshold lowering.",
        "side_effects": "Common: extrapyramidal symptoms (EPS — dystonia, akathisia, parkinsonism), tardive dyskinesia, sedation, hypotension, anticholinergic effects, hyperprolactinemia. Serious: NMS, QT prolongation/TdP, tardive dyskinesia, death in elderly dementia patients.",
        "dosage": "Schizophrenia/psychosis (oral): 0.5-20 mg/day in divided doses. Acute agitation (IM): 2-10 mg every 4-8 hours as needed. Haldol Decanoate (monthly depot): 10-20× the previous daily oral dose, given monthly IM. Start with the lowest effective dose, especially in elderly.",
        "before_taking": "Not approved for dementia-related psychosis. Diphenhydramine or benztropine is used to treat acute EPS (dystonic reactions). Monitor for tardive dyskinesia (involuntary movements). Tell your doctor about Parkinson's disease, QT prolongation, electrolyte abnormalities, liver disease, and seizure disorder. Avoid alcohol. Reduce dose in elderly.",
    },
    "baclofen": {
        "description": "Baclofen (Lioresal, Gablofen) is a centrally-acting gamma-aminobutyric acid B (GABA-B) receptor agonist muscle relaxant and antispasticity drug. Available as 5, 10, and 20 mg oral tablets and intrathecal injection (for spasticity).",
        "uses": "Baclofen is indicated for spasticity resulting from multiple sclerosis, spinal cord lesions/injuries, and cerebral palsy (intrathecal pump). Off-label uses include alcohol use disorder (reduces cravings), hiccups, trigeminal neuralgia, and neuropathic pain.",
        "warnings": "ABRUPT WITHDRAWAL is potentially life-threatening — can cause hallucinations, seizures, high fever, rhabdomyolysis, and even death. Do not abruptly discontinue; taper dose gradually. Intrathecal pump failure can cause severe baclofen withdrawal — medical emergency. CNS depression: sedation, dizziness, weakness are common — impairs driving. Renal impairment requires dose reduction (primarily renally eliminated). Seizure threshold may be lowered in epileptic patients.",
        "side_effects": "Common: drowsiness, dizziness, weakness, fatigue, nausea, headache, hypotension. Serious: withdrawal syndrome (hallucinations, seizures, fever, rhabdomyolysis — life-threatening with intrathecal pump), respiratory depression (with CNS depressants), seizures.",
        "dosage": "Spasticity (oral): Start 5 mg three times daily for 3 days; increase by 5 mg per dose every 3 days; usual dose 40-80 mg/day in divided doses; maximum 80 mg/day (up to 120 mg/day in exceptional cases). Intrathecal: highly variable, requires specialist management.",
        "before_taking": "Never stop baclofen abruptly — taper gradually over 1-2 weeks minimum. Tell your doctor about epilepsy (may lower seizure threshold), kidney disease, psychiatric illness, stroke, and all medications. Avoid alcohol and other CNS depressants. Do not drive until you know how baclofen affects you. Intrathecal pump patients: report pump malfunction symptoms immediately.",
    },
    "carisoprodol": {
        "description": "Carisoprodol (Soma) is a centrally-acting skeletal muscle relaxant (Schedule IV controlled substance) that is metabolized to meprobamate (also a Schedule IV controlled substance with sedative/anxiolytic properties).",
        "uses": "Carisoprodol is indicated for short-term (2-3 weeks) relief of discomfort associated with acute, painful musculoskeletal conditions in adults. Efficacy beyond 2-3 weeks has not been established.",
        "warnings": "Carisoprodol is a Schedule IV controlled substance due to its abuse, dependence, and addiction potential. Dependence, withdrawal, and abuse have been reported. Drug-seeking behavior is common. Cases of death have been reported following overdose (particularly with alcohol or CNS depressants). Sedation is significant — do not drive or operate machinery. Seizures have been reported during withdrawal. Patients with history of drug or alcohol abuse should be monitored carefully. Meprobamate (active metabolite) has barbiturate-like properties and can cause CNS depression.",
        "side_effects": "Common: drowsiness, dizziness, headache, nausea. Serious: dependence, withdrawal syndrome (seizures possible), addiction, severe CNS and respiratory depression (with alcohol/CNS depressants).",
        "dosage": "250-350 mg three times daily and at bedtime. Use for the shortest duration possible — no more than 2-3 weeks.",
        "before_taking": "Not recommended for patients with a history of drug or alcohol abuse (high abuse potential). Do not combine with alcohol, opioids, or other CNS depressants. Do not stop abruptly after prolonged use — withdrawal seizures possible. Not recommended in elderly patients (Beers Criteria — abuse potential and CNS effects). Maximum duration: 2-3 weeks.",
    },
    "vitamin D3": {
        "description": "Vitamin D3 (cholecalciferol; many OTC brands) is a fat-soluble vitamin produced by the skin upon UV exposure and found in dietary sources. Available OTC as 400, 1000, 2000, 5000, and 10000 IU capsules, tablets, and drops. Prescription formulations include 50000 IU capsules (Drisdol = vitamin D2; and vitamin D3 equivalents).",
        "uses": "Vitamin D3 supplementation is indicated for vitamin D deficiency, osteoporosis prevention (with calcium), hypoparathyroidism, vitamin D-dependent rickets, and as adjunctive treatment in patients at risk for bone loss. It is also widely used off-label for immunological, cardiometabolic, and other conditions.",
        "warnings": "Vitamin D toxicity (hypervitaminosis D) can occur with excessive supplementation — causes hypercalcemia, hypercalciuria, nausea, vomiting, polyuria, polydipsia, and potentially renal failure and calcifications. Routine supplementation with doses above 2000 IU/day for extended periods should be monitored. Patients on thiazide diuretics have higher risk of hypercalcemia. Caution with granulomatous diseases (sarcoidosis, TB) — may cause hypercalcemia without deficiency. Monitor 25-OH vitamin D and calcium levels during supplementation.",
        "side_effects": "Therapeutic doses: generally well tolerated. Excessive doses: hypercalcemia (weakness, fatigue, headache, nausea, vomiting, constipation, confusion, polyuria), hypercalciuria, kidney stones, renal failure, vascular and soft tissue calcifications.",
        "dosage": "Deficiency treatment (25-OH VitD <20 ng/mL): 50000 IU weekly for 8-12 weeks, then maintenance. Deficiency prevention: 600-800 IU/day (RDA); many adults require 1000-2000 IU/day for optimal levels. Target 25-OH vitamin D level: 30-50 ng/mL.",
        "before_taking": "Tell your doctor if you have granulomatous disease (sarcoidosis, tuberculosis, lymphoma), hyperparathyroidism, kidney disease, kidney stones, or heart disease. Monitor calcium and 25-OH vitamin D levels during supplementation — especially at higher doses. Take with food (fat-soluble vitamin — best absorbed with meals containing fat).",
    },
    "vitamin B12": {
        "description": "Vitamin B12 (cyanocobalamin, methylcobalamin) is an essential water-soluble vitamin required for DNA synthesis, myelin formation, and red blood cell production. Available OTC as oral tablets (100 mcg-5000 mcg), sublingual tablets, intranasal spray (Nascobal), and IM/SC injection (prescription).",
        "uses": "Vitamin B12 supplementation is indicated for pernicious anemia (intrinsic factor deficiency requiring IM injection or high-dose oral B12), vitamin B12 deficiency (from dietary inadequacy, malabsorption, strict vegan diet, metformin use, gastric surgery, advanced age), and maintenance therapy in patients with B12 deficiency.",
        "warnings": "Oral B12 is generally safe; high doses are excreted in urine (water-soluble). Anaphylactic reactions have occurred with parenteral cyanocobalamin. Hypokalemia can occur at the start of treatment for severe megaloblastic anemia (treat with potassium supplementation). IM injection contains benzyl alcohol — avoid in neonates (gasping syndrome). Smoking accelerates peripheral neuropathy in B12-deficient patients.",
        "side_effects": "Therapeutic doses: essentially no adverse effects. High doses: generally well tolerated. Parenteral: injection site reactions, anaphylaxis (rare).",
        "dosage": "Deficiency (oral — for B12 deficiency from malabsorption): 1000-2000 mcg daily (high-dose oral can overcome passive absorption even without intrinsic factor). Pernicious anemia (IM injection): 100-1000 mcg IM weekly for 4-8 weeks, then monthly maintenance. Vegetarians: 250-1000 mcg daily OTC supplementation. Metformin users: consider B12 monitoring and supplementation.",
        "before_taking": "IM injection is required for pernicious anemia (lacks intrinsic factor) — oral B12 may be effective at high doses but IM is more reliable. High-dose oral B12 (1000-2000 mcg daily) can also correct deficiency even in pernicious anemia via passive absorption. Metformin users should monitor B12 levels and supplement. Vegetarians and vegans are at risk for deficiency — supplement routinely.",
    },
    "folic acid": {
        "description": "Folic acid (folate; vitamin B9) is a water-soluble B vitamin essential for DNA synthesis, red blood cell formation, and fetal neural tube development. Available as 0.4 mg, 0.8 mg, and 1 mg OTC tablets, and prescription 1 mg tablets.",
        "uses": "Folic acid is indicated for prevention of neural tube defects (NTDs) when taken peri-conceptionally, treatment of megaloblastic anemia due to folic acid deficiency, and to reduce methotrexate-induced side effects in rheumatoid arthritis and psoriasis patients.",
        "warnings": "Folic acid can mask the hematological signs of vitamin B12 deficiency (megaloblastic anemia improves but neurological damage from B12 deficiency progresses) — always check B12 status before treating anemia with folic acid alone. High-dose folic acid (>1 mg/day) may reduce the anticonvulsant effect of phenytoin and other antiepileptics. Folic acid supplementation is generally safe.",
        "side_effects": "Generally well tolerated. Rare: rash, nausea, allergic reactions (particularly with parenteral formulations).",
        "dosage": "Neural tube defect prevention: 400-800 mcg daily starting at least 1 month before conception and through first trimester. Women with prior NTD pregnancy: 4-5 mg daily (prescription dose). Folate deficiency anemia: 1-5 mg/day. Methotrexate-associated adverse effect reduction: 1-5 mg/day (given on days not taking methotrexate).",
        "before_taking": "Always check vitamin B12 status before starting folic acid for anemia — untreated B12 deficiency can lead to irreversible neurological damage even as anemia improves with folic acid. High-dose folic acid may reduce seizure control — use with caution in epileptic patients.",
    },
    "magnesium oxide": {
        "description": "Magnesium oxide (Mag-Ox 400, Uro-Mag) is an OTC magnesium supplement and antacid available as 250-500 mg tablets and capsules. It has lower bioavailability compared to other magnesium salts (magnesium citrate, glycinate) but contains a high percentage of elemental magnesium.",
        "uses": "Magnesium oxide is used for magnesium supplementation (to prevent and treat hypomagnesemia), as an antacid for heartburn and dyspepsia, and as an osmotic laxative for constipation. Also used for migraine prevention, leg cramps, and premenstrual syndrome (off-label).",
        "warnings": "Hypermagnesemia can occur in patients with renal impairment — avoid routine supplementation in severe kidney disease (CrCl <30 mL/min). At high doses (antacid/laxative doses), magnesium oxide can cause diarrhea. Drug interactions: reduces absorption of fluoroquinolones, tetracyclines, bisphosphonates, and some drugs requiring acidic pH — take 2 hours apart.",
        "side_effects": "Common: diarrhea (dose-dependent), nausea, GI cramping. High doses/renal impairment: hypermagnesemia (lethargy, hypotension, bradycardia, loss of deep tendon reflexes, respiratory arrest).",
        "dosage": "Magnesium supplementation: 400-800 mg/day in divided doses. Antacid: 140 mg (Mag-Ox) 4 times/day. Constipation: 2-4 g in 8 oz water at bedtime.",
        "before_taking": "Avoid high doses in severe kidney disease. Take supplement doses separately from fluoroquinolones, tetracyclines, and other drugs that interact with divalent cations (2 hours apart). Magnesium citrate or glycinate may be better absorbed and less likely to cause diarrhea than magnesium oxide.",
    },
    "calcium carbonate": {
        "description": "Calcium carbonate (Tums, Os-Cal, Caltrate) is the most commonly used OTC calcium supplement and antacid. Available as 500-1250 mg tablets in various formulations. Contains approximately 40% elemental calcium.",
        "uses": "Calcium carbonate is used as a calcium supplement for osteoporosis prevention and treatment, hypocalcemia, and during pregnancy and lactation. As an antacid, it provides rapid but short-lived relief of heartburn and dyspepsia. Also used as a phosphate binder in end-stage renal disease.",
        "warnings": "Calcium carbonate requires stomach acid for optimal absorption — best absorbed with meals. Calcium carbonate antacid can cause constipation. Calcium-alkali syndrome (hypercalcemia, alkalosis, renal impairment) with excessive intake. Kidney stones — high calcium intake may increase stone risk in predisposed patients. Drug interactions: reduces absorption of iron, zinc, fluoroquinolones, tetracyclines, bisphosphonates, thyroid medications, and some HIV drugs — take 2+ hours apart. Potential cardiovascular risk with excessive supplemental calcium.",
        "side_effects": "Common: constipation, nausea, gas. High doses: hypercalcemia (weakness, confusion, polyuria, kidney stones), calcium-alkali syndrome (with prolonged high-dose use).",
        "dosage": "Antacid: 500-1000 mg up to 4 times daily as needed for heartburn. Calcium supplement: 1000-1200 mg elemental calcium daily in divided doses (usually 500 mg twice or three times daily — absorption decreases with doses >500 mg at once). Take with meals for optimal absorption.",
        "before_taking": "Take with meals to maximize absorption. Separate from iron supplements, fluoroquinolones, tetracyclines, bisphosphonates, and thyroid medications by at least 2 hours. Constipation is common — increase fluid and fiber intake. Do not exceed 2000-2500 mg/day total calcium (diet + supplements) without medical supervision.",
    },
    "ferrous sulfate": {
        "description": "Ferrous sulfate is the most commonly used OTC oral iron supplement. Available as 325 mg tablets (65 mg elemental iron) and liquid formulations. Other iron salt forms include ferrous gluconate (36 mg elemental iron/300 mg) and ferrous fumarate (99 mg/324 mg).",
        "uses": "Ferrous sulfate is indicated for treatment of iron deficiency anemia and prevention of iron deficiency in high-risk groups (pregnant women, infants, vegetarians). It replenishes iron stores and supports hemoglobin synthesis.",
        "warnings": "Iron overdose is a leading cause of accidental poisoning death in children — store away from children and keep child-proof caps. GI side effects (nausea, constipation, dark stools) are common. Iron absorption is reduced by food, dairy, antacids, calcium, zinc, coffee, tea, and many medications — take on empty stomach for best absorption (but take with food if GI intolerance). Ferrous sulfate interacts with fluoroquinolones, tetracyclines, levothyroxine, methyldopa, bisphosphonates, and carbidopa/levodopa — take 2+ hours apart.",
        "side_effects": "Common: nausea, constipation, dark/black stools, diarrhea, abdominal pain, heartburn. Overdose: vomiting, diarrhea, abdominal pain, GI bleeding, metabolic acidosis, hepatotoxicity, cardiovascular collapse.",
        "dosage": "Iron deficiency anemia (adults): 150-200 mg elemental iron/day in 2-3 divided doses. Prophylaxis during pregnancy: 27 mg elemental iron/day. Take on an empty stomach 1 hour before or 2 hours after meals for best absorption (with vitamin C to enhance absorption). If GI intolerance, take with food.",
        "before_taking": "Keep out of reach of children — iron overdose can be fatal. Take on an empty stomach with vitamin C (orange juice) to enhance absorption. Separate from antacids, calcium, dairy, tea, coffee, fluoroquinolones, tetracyclines, levothyroxine, and many other medications by at least 2 hours. Dark/black stools are normal and expected — do not confuse with GI bleeding (though test if concerned).",
    },
    "fexofenadine": {
        "description": "Fexofenadine (Allegra) is a second-generation, non-sedating antihistamine (H1 receptor antagonist). Available OTC as 60 mg twice-daily and 180 mg once-daily tablets and 30 mg/5 mL oral suspension.",
        "uses": "Fexofenadine is indicated for the relief of symptoms of seasonal and perennial allergic rhinitis (hay fever) in adults and children ≥6 months, and chronic idiopathic urticaria (hives) in adults and children ≥6 months.",
        "warnings": "Fexofenadine is one of the most non-sedating antihistamines — minimal CNS penetration. Avoid concurrent use with fruit juices (grapefruit, orange, apple) — significantly reduces fexofenadine bioavailability by approximately 36%. Also avoid concurrent antacids containing aluminum and magnesium — reduce absorption. Dose reduction in renal impairment.",
        "side_effects": "Common: headache, nausea, dizziness, fatigue. Less common: drowsiness (though significantly less than first-generation antihistamines). Generally well tolerated.",
        "dosage": "Adults and children ≥12 years: 60 mg twice daily or 180 mg once daily. Children 6-11 years: 30 mg twice daily. Children 6-23 months: 15 mg twice daily. Renal impairment: 60 mg once daily.",
        "before_taking": "Avoid taking with grapefruit, orange, or apple juice — reduces absorption. Take with water only. Tell your doctor about kidney disease. Fexofenadine is generally considered one of the safest antihistamines for use in patients who cannot afford any sedation. Considered safe in pregnancy (Category C) — discuss with your doctor.",
    },
    "methimazole": {
        "description": "Methimazole (Tapazole) is a thioamide antithyroid drug that inhibits thyroid hormone synthesis by blocking the enzyme thyroid peroxidase. Available as 5 and 10 mg tablets. It is the preferred antithyroid drug over propylthiouracil (PTU) for most patients with hyperthyroidism.",
        "uses": "Methimazole is indicated for hyperthyroidism (Graves' disease, toxic multinodular goiter, toxic adenoma) to control thyrotoxicosis before thyroid surgery or radioactive iodine therapy, and for long-term management of Graves' disease.",
        "warnings": "Agranulocytosis (severe decrease in white blood cells) is the most serious adverse effect — can be life-threatening. Incidence is approximately 0.1-0.5%; risk is dose-dependent and highest in the first few months of therapy. Patients must immediately stop methimazole and seek emergency evaluation for fever, sore throat, or mouth sores. Hepatotoxicity (cholestatic pattern, unlike PTU which causes hepatocellular injury). CONTRAINDICATED in the first trimester of pregnancy (crosses placenta; associated with embryopathy including aplasia cutis, choanal atresia — PTU preferred in first trimester).",
        "side_effects": "Common: rash, urticaria, arthralgias, fever, nausea. Serious: agranulocytosis (life-threatening — stop immediately if fever/sore throat), hepatotoxicity (cholestatic jaundice), ANCA-associated vasculitis.",
        "dosage": "Hyperthyroidism (mild): 5-15 mg once daily. Moderate-severe: 20-40 mg/day. After euthyroid state achieved (usually 4-8 weeks): taper to maintenance dose 5-15 mg/day. Check TFTs every 4-8 weeks. Monitor CBC regularly during first 6 months.",
        "before_taking": "Use PTU (not methimazole) in the first trimester of pregnancy. Tell your doctor about liver disease, blood disorders, or other autoimmune conditions. Immediately report fever, sore throat, mouth sores — may indicate agranulocytosis requiring emergency care and medication discontinuation. Monitor TFTs regularly. Avoid raw seafood and seaweed (iodine-rich foods) which can worsen hyperthyroidism.",
    },
    "propylthiouracil": {
        "description": "Propylthiouracil (PTU) is a thioamide antithyroid drug that inhibits thyroid hormone synthesis and peripheral T4 to T3 conversion. Available as 50 mg tablets. PTU is preferred over methimazole specifically in the first trimester of pregnancy due to lower risk of embryopathy.",
        "uses": "Propylthiouracil is indicated for hyperthyroidism, particularly as the preferred antithyroid drug during the first trimester of pregnancy, for thyroid storm (rapid T3 conversion inhibition), and in patients who cannot tolerate methimazole.",
        "warnings": "FDA BOXED WARNING: Severe liver injury and acute liver failure, including some deaths, have been reported with propylthiouracil. Due to hepatotoxicity risk, PTU is now second-line (methimazole preferred) for most patients; used primarily in first trimester of pregnancy and for thyroid storm. Same agranulocytosis risk as methimazole — stop immediately if fever or sore throat and obtain CBC.",
        "side_effects": "Common: rash, arthralgias, fever, nausea. Serious: agranulocytosis, severe hepatotoxicity (hepatocellular — more serious than methimazole cholestatic pattern; can be fatal), ANCA vasculitis.",
        "dosage": "Hyperthyroidism: 300-600 mg/day in 3 divided doses initially; taper to maintenance 100-150 mg/day in 2-3 divided doses. Thyroid storm: 500-1000 mg loading dose, then 250 mg every 4 hours.",
        "before_taking": "PTU is specifically preferred in first trimester of pregnancy (methimazole has teratogenicity in first trimester) — switch to methimazole after first trimester. Immediately report fever, sore throat, jaundice, or abdominal pain. Monitor LFTs and CBC regularly. Take in equal doses throughout the day.",
    },
    "lisdexamfetamine": {
        "description": "Lisdexamfetamine (Vyvanse) is a prodrug of dextroamphetamine (Schedule II controlled substance). It is converted to d-amphetamine after oral absorption, providing a smoother onset and potentially lower abuse potential than immediate-release amphetamine. Available as 20, 30, 40, 50, 60, 70 mg capsules and chewable tablets.",
        "uses": "Lisdexamfetamine is indicated for ADHD in adults and children ≥6 years, and for moderate-to-severe binge eating disorder (BED) in adults.",
        "warnings": "FDA BOXED WARNING: Same as other CNS stimulants — high potential for abuse and dependence. Cardiovascular: increased blood pressure and heart rate; avoid in structural cardiac abnormalities. Psychiatric: may worsen psychosis/mania in predisposed patients; new-onset psychotic/manic symptoms have been reported. Growth suppression in children. Peripheral vasculopathy including Raynaud's phenomenon. Do not use with MAO inhibitors (hypertensive crisis, serotonin syndrome). The pro-drug design does not eliminate abuse potential — can be misused parenterally by extracting dextroamphetamine.",
        "side_effects": "Common: decreased appetite, insomnia, dry mouth, headache, irritability, increased heart rate and blood pressure, weight loss. Serious: cardiovascular events (cardiac arrest, sudden death in CAD patients), psychosis/mania, peripheral vasculopathy, priapism.",
        "dosage": "ADHD (adults and children ≥6 years): Start 30 mg once daily in the morning; increase by 10-20 mg/week; maximum 70 mg/day. BED: Start 30 mg once daily; target 50-70 mg/day. Take in the morning to minimize insomnia.",
        "before_taking": "Same precautions as other amphetamine medications. Do not use with MAO inhibitors. Not recommended in patients with structural heart disease, cardiomyopathy, or serious cardiac arrhythmias. Tell your doctor about psychiatric history, cardiovascular disease, glaucoma, hyperthyroidism, or history of substance abuse. Monitor height, weight, and BP/HR in children.",
    },
    "desvenlafaxine": {
        "description": "Desvenlafaxine (Pristiq) is the major active metabolite of venlafaxine and an SNRI (serotonin-norepinephrine reuptake inhibitor). Available as 25, 50, and 100 mg extended-release tablets.",
        "uses": "Desvenlafaxine is FDA-approved for treatment of major depressive disorder (MDD) in adults.",
        "warnings": "FDA BOXED WARNING: Antidepressants increase suicidal risk in children, adolescents, and young adults. Serotonin syndrome with concomitant serotonergic drugs or MAO inhibitors. Discontinuation syndrome — taper slowly; do not abruptly stop. Increases blood pressure and heart rate. May worsen narrow-angle glaucoma. SIADH and hyponatremia. Abnormal bleeding. Mania activation in bipolar disorder.",
        "side_effects": "Common: nausea, dizziness, insomnia, hyperhidrosis (sweating), constipation, dry mouth, sexual dysfunction, increased blood pressure. Serious: serotonin syndrome, discontinuation syndrome, suicidal ideation, SIADH/hyponatremia, abnormal bleeding.",
        "dosage": "50 mg once daily is the recommended and usually effective dose. Maximum 400 mg/day (no additional benefit above 50 mg in clinical trials). Renal impairment: 50 mg every other day (severe). Hepatic impairment: 50 mg/day maximum. Do not crush, chew, or divide the tablets.",
        "before_taking": "Do not use with MAO inhibitors. Taper gradually when discontinuing — do not stop abruptly. Tell your doctor about bipolar disorder, seizure disorder, hypertension, heart disease, glaucoma, liver or kidney disease, and all medications. Monitor blood pressure at baseline and during treatment.",
    },
    "eszopiclone": {
        "description": "Eszopiclone (Lunesta) is a non-benzodiazepine hypnotic of the cyclopyrrolone class (Z-drug; Schedule IV controlled substance). Unlike zolpidem, eszopiclone is approved for short-term and longer-term use for insomnia. Available as 1, 2, and 3 mg tablets.",
        "uses": "Eszopiclone is indicated for treatment of insomnia characterized by difficulties in sleep onset and/or sleep maintenance.",
        "warnings": "Complex sleep behaviors (sleep-walking, sleep-driving, sleep-eating — FDA BOXED WARNING): Same class warning as zolpidem — complex behaviors while not fully awake have been reported; some have resulted in serious injuries and death. Discontinue if complex sleep behavior occurs. CNS depression — additive with alcohol and CNS depressants. Worsening depression and suicidal thinking. Dependence and abuse potential (Schedule IV). Rebound insomnia may occur on discontinuation. Next-morning impairment.",
        "side_effects": "Common: unpleasant taste (bitter metallic taste — very characteristic of eszopiclone), headache, somnolence, dizziness, dry mouth. Serious: complex sleep behaviors, respiratory depression, anaphylaxis/angioedema (after first dose), worsening depression.",
        "dosage": "Adults: 1-2 mg at bedtime initially; usual dose 2-3 mg. Elderly: start 1 mg; maximum 2 mg. Start with lowest effective dose. Reduce to 1 mg if severe hepatic impairment or concurrent strong CYP3A4 inhibitor use. Do not exceed 3 mg. Take immediately before bedtime with at least 7-8 hours remaining before planned waking.",
        "before_taking": "Same precautions as zolpidem. Do not take if you have had a complex sleep behavior from any sleep medicine. Do not drive until you know the next-morning effects. Avoid alcohol. CYP3A4 inhibitors increase eszopiclone levels. Use the lowest effective dose. Inform your doctor if pregnant or breastfeeding.",
    },
    "pravastatin": {
        "description": "Pravastatin (Pravachol) is an HMG-CoA reductase inhibitor (statin) that is hydrophilic and less lipophilic than most other statins. Available as 10, 20, 40, and 80 mg tablets. It is NOT significantly metabolized by CYP3A4, giving it fewer drug interactions than lipophilic statins.",
        "uses": "Pravastatin is indicated for reducing LDL-C, total cholesterol, and apolipoprotein B, and for increasing HDL-C in primary hypercholesterolemia and mixed dyslipidemia; reduction of risk of cardiovascular mortality, MI, and stroke in patients with prior MI or at high cardiovascular risk.",
        "warnings": "Same class myopathy and rhabdomyolysis risk as other statins — lower risk than lipophilic statins at equivalent doses. Drug interactions are fewer than CYP3A4-metabolized statins but still present: fibrates (particularly gemfibrozil) increase rhabdomyolysis risk; cyclosporine substantially increases pravastatin levels; colchicine increases myopathy risk; niacin increases myopathy risk. Liver enzyme elevations. Avoid or use with caution in patients with active liver disease.",
        "side_effects": "Common: headache, nausea, diarrhea, constipation, muscle pain. Serious: myopathy, rhabdomyolysis, hepatotoxicity, new-onset diabetes.",
        "dosage": "10-80 mg once daily, usually at bedtime. Maximum 40 mg/day in patients on cyclosporine or fibrates (gemfibrozil — avoid if possible). Can be taken at any time of day, with or without food.",
        "before_taking": "Same general precautions as other statins. Fewer CYP3A4 drug interactions than simvastatin or atorvastatin — a preferred statin in patients on interacting medications (cyclosporine, certain HIV/hepatitis drugs). Avoid during pregnancy and breastfeeding. Monitor LFTs. Report muscle pain or weakness promptly.",
    },
    "methadone": {
        "description": "Methadone (Dolophine, Methadose) is a long-acting synthetic opioid analgesic (Schedule II) with unique properties: very long and unpredictable half-life (8-59 hours), NMDA receptor antagonism, and complex pharmacokinetics. Used for both chronic pain and opioid use disorder (OUD) treatment.",
        "uses": "Methadone is indicated for detoxification and maintenance treatment of opioid use disorder (administered only in federally licensed opioid treatment programs for this indication), and for severe chronic pain when other treatments are inadequate.",
        "warnings": "FDA BOXED WARNINGS: (1) Respiratory depression — peak respiratory effects occur 72 hours after initiation; deaths from overdose occur when respiratory depression is underestimated. The initial dose must be conservative in opioid-naive patients. (2) QT prolongation — methadone prolongs the QT interval more than most opioids; torsades de pointes and cardiac arrest have occurred. Obtain baseline ECG and monitor QTc. (3) Drug interactions — CYP3A4, CYP2C9, CYP2D6 inhibitors increase methadone levels; inducers decrease levels. (4) Risk of fatal overdose with accidental ingestion by children. Methadone's long and unpredictable half-life makes it dangerous for dose adjustment — increases should be made no more often than every 3-7 days.",
        "side_effects": "Common: constipation, nausea, sweating, sedation. Serious: QT prolongation/torsades de pointes, respiratory depression, cardiac arrest.",
        "dosage": "OUD (opioid treatment program only): initial 20-30 mg; usual maintenance 60-120 mg once daily. Pain: 2.5-10 mg every 8-12 hours initially (much lower than equianalgesic dose from other opioids due to incomplete cross-tolerance); titrate very cautiously.",
        "before_taking": "For OUD: must be dispensed from a federally licensed opioid treatment program (OTP). For pain: start very low due to long half-life. Obtain baseline ECG and repeat during therapy — QTc >500 ms: review risk-benefit and reduce dose. Tell your doctor about cardiac arrhythmias, QT prolongation, electrolyte abnormalities, liver disease, kidney disease, and all medications.",
    },
    "bisoprolol": {
        "description": "Bisoprolol (Zebeta) is a highly selective beta-1 adrenergic receptor blocker (cardioselective at recommended doses) available as 5 and 10 mg tablets. In combination with hydrochlorothiazide: Ziac.",
        "uses": "Bisoprolol is indicated for hypertension. It is also commonly used off-label for heart failure (with reduced ejection fraction — strong evidence from CIBIS-II trial), rate control in atrial fibrillation, and angina.",
        "warnings": "Do not abruptly discontinue — risk of rebound angina and MI, especially in patients with ischemic heart disease. Use with caution in reactive airway disease — although highly cardioselective at low doses, beta-1 selectivity is not absolute. May mask signs of hypoglycemia. Dose reduction in hepatic or renal impairment.",
        "side_effects": "Common: bradycardia, fatigue, dizziness, cold extremities, headache, diarrhea. Serious: bronchospasm (less likely than non-selective beta-blockers), heart block, worsening heart failure, rebound angina/MI on abrupt withdrawal.",
        "dosage": "Hypertension: Start 5 mg once daily; may increase to 10-20 mg once daily. Heart failure (off-label): Start 1.25 mg once daily; double every 2 weeks as tolerated; target 10 mg once daily.",
        "before_taking": "Do not stop abruptly — taper over 1-2 weeks. Same precautions as atenolol — avoid in asthma, AV block, cardiogenic shock. Bisoprolol has the most evidence among beta-blockers for use in stable heart failure (with carvedilol and metoprolol succinate).",
    },
    "chlorthalidone": {
        "description": "Chlorthalidone (Thalitone) is a thiazide-like diuretic with a longer duration of action than hydrochlorothiazide (HCTZ). Available as 15 and 25 mg tablets. Many cardiovascular guidelines now prefer chlorthalidone over HCTZ due to superior blood pressure lowering and cardiovascular outcome evidence.",
        "uses": "Chlorthalidone is indicated for hypertension and edema associated with heart failure, renal disease, hepatic cirrhosis, or corticosteroid and estrogen therapy.",
        "warnings": "Same class risks as hydrochlorothiazide: electrolyte disturbances (hypokalemia, hyponatremia, hypomagnesemia, hypercalcemia), gout exacerbation (increases uric acid), hyperglycemia (can unmask or worsen diabetes), hyperlipidemia (small effect), photosensitivity, volume depletion. Chlorthalidone's longer half-life means that electrolyte disturbances may be more pronounced. Avoid in patients with anuria or sulfonamide allergy.",
        "side_effects": "Common: hypokalemia, hyponatremia, volume depletion, dizziness, headache, muscle cramps, increased blood glucose and uric acid. Serious: severe electrolyte disturbances, gout, hyponatremia with CNS effects.",
        "dosage": "Hypertension: 12.5-25 mg once daily (preferred: 12.5-25 mg). Edema: 25-100 mg once daily or alternate days. Lower doses than HCTZ achieve similar blood pressure effects — 25 mg chlorthalidone ≈ 50 mg HCTZ.",
        "before_taking": "Monitor potassium and other electrolytes. Supplement potassium as needed or use with a potassium-sparing agent. Tell your doctor about gout, diabetes, lupus, kidney disease, liver disease, and sulfonamide allergy. Take in the morning to avoid nocturia.",
    },
    "indapamide": {
        "description": "Indapamide (Lozol) is a thiazide-related diuretic with vasodilatory properties. Available as 1.25 and 2.5 mg tablets. Has been shown to preserve kidney function better than HCTZ in some studies.",
        "uses": "Indapamide is indicated for hypertension and edema associated with heart failure.",
        "warnings": "Same electrolyte disturbance profile as thiazides: hypokalemia, hyponatremia, hypomagnesemia. Hyponatremia risk may be particularly high in elderly patients. Volume depletion. QT prolongation at higher doses (related to hypokalemia).",
        "side_effects": "Common: headache, dizziness, hypokalemia, hyponatremia, fatigue, muscle cramps. Serious: severe hyponatremia (especially in elderly), severe hypokalemia, QT prolongation.",
        "dosage": "Hypertension: Start 1.25 mg once daily in the morning; may increase to 2.5 mg once daily. Edema (heart failure): 2.5 mg once daily.",
        "before_taking": "Monitor electrolytes, especially potassium and sodium. Elderly patients at higher risk for hyponatremia. Take in the morning to avoid nocturia. Tell your doctor about kidney disease, liver disease, diabetes, gout, or sulfonamide allergy.",
    },
    "sulfasalazine": {
        "description": "Sulfasalazine (Azulfidine) is a sulfonamide and salicylate combination available as 500 mg tablets and delayed-release (enteric-coated) tablets (Azulfidine EN-tabs). It is cleaved by colonic bacteria into sulfapyridine and 5-aminosalicylate (5-ASA).",
        "uses": "Sulfasalazine is indicated for mild-to-moderate ulcerative colitis (induction and maintenance of remission) and rheumatoid arthritis (DMARD therapy in RA patients not adequately controlled with NSAIDs).",
        "warnings": "Sulfonamide allergy — contains sulfapyridine; contraindicated in patients with sulfonamide allergy or salicylate allergy. Blood dyscrasias (agranulocytosis, aplastic anemia, hemolytic anemia) can occur — monitor CBC periodically. Folate deficiency — sulfasalazine inhibits folate absorption; supplement with folic acid. Orange-yellow discoloration of urine and skin is common and harmless. Hepatotoxicity. Lupus-like syndrome.",
        "side_effects": "Common: nausea, vomiting, diarrhea, anorexia, headache, orange-yellow urine discoloration, skin discoloration. Serious: blood dyscrasias, hepatotoxicity, sulfonamide hypersensitivity (SJS/TEN), folate deficiency, oligospermia (reversible male infertility), lupus-like syndrome.",
        "dosage": "UC: 3-4 g/day in divided doses for induction; 2 g/day for maintenance. RA: 2-3 g/day in divided doses (usually twice daily with food). Use enteric-coated formulation to reduce GI intolerance. Start at 500 mg/day and increase gradually.",
        "before_taking": "Contraindicated in sulfonamide or salicylate allergy, intestinal or urinary obstruction. Supplement with folic acid 1 mg/day. Monitor CBC and LFTs periodically. Stay well hydrated. Orange-yellow urine is expected — normal. Men of reproductive age: oligospermia is common but reversible upon discontinuation. Inform doctor about G6PD deficiency (hemolytic anemia risk).",
    },
    "tiotropium": {
        "description": "Tiotropium (Spiriva HandiHaler, Spiriva Respimat) is a long-acting anticholinergic bronchodilator (muscarinic antagonist, LAMA) administered once daily by inhalation. Available as 18 mcg dry powder capsules for inhalation (HandiHaler) and 1.25 and 2.5 mcg/actuation soft mist inhaler (Respimat).",
        "uses": "Tiotropium is indicated for maintenance treatment of COPD (chronic obstructive pulmonary disease), including reduction of COPD exacerbations, and maintenance treatment of asthma in patients ≥6 years (Respimat only, 2.5 mcg dose).",
        "warnings": "Not for acute bronchospasm (rescue use) — patients must have a short-acting bronchodilator for acute symptoms. Anticholinergic effects: urinary retention (particularly in patients with BPH), dry mouth, constipation, blurred vision. Do not use if swallowed — inhaled only. Avoid in patients with narrow-angle glaucoma (can worsen). Avoid contact with eyes — can precipitate acute angle-closure glaucoma.",
        "side_effects": "Common: dry mouth, constipation, urinary retention, blurred vision, pharyngitis, sinusitis. Serious: paradoxical bronchospasm, urinary retention (patients with BPH), acute narrow-angle glaucoma (if powder/mist contacts eyes).",
        "dosage": "COPD (HandiHaler): inhale contents of one 18 mcg capsule once daily using the HandiHaler device. COPD (Respimat): 5 mcg (2 actuations of 2.5 mcg) once daily. Asthma (Respimat): 2.5 mcg (2 actuations of 1.25 mcg) once daily.",
        "before_taking": "Not for acute relief — always carry short-acting bronchodilator. Tell your doctor about glaucoma, enlarged prostate, urinary retention, or kidney disease. Do not let mist or powder contact eyes — risk of precipitating acute angle-closure glaucoma. Rinse mouth after use. Capsules for HandiHaler are for inhalation only — do not swallow.",
    },
    "salmeterol": {
        "description": "Salmeterol (Serevent Diskus) is a long-acting beta-2 agonist (LABA) bronchodilator administered by inhalation. Available as 50 mcg/blister dry powder inhaler. Never used as monotherapy for asthma — must be combined with an inhaled corticosteroid (ICS).",
        "uses": "Salmeterol is indicated for maintenance treatment of asthma (always with ICS) and COPD (as monotherapy or with ICS). It provides bronchodilation for up to 12 hours.",
        "warnings": "FDA BOXED WARNING: Long-acting beta-2 agonists (LABAs) increase the risk of asthma-related death. Never use salmeterol as a monotherapy for asthma — only use in fixed-dose combination with an ICS (e.g., Advair = salmeterol + fluticasone) or ensure ICS is being used concurrently. Not for rescue therapy — patients must have a short-acting bronchodilator for acute symptoms. Cardiovascular effects: palpitations, increased heart rate, tremor.",
        "side_effects": "Common: headache, palpitations, tremor, throat irritation, upper respiratory infection. Serious: asthma-related death (monotherapy), cardiac arrhythmias, severe hypokalemia (rare at recommended doses), anaphylaxis.",
        "dosage": "Asthma (with ICS): 1 inhalation (50 mcg) twice daily (morning and evening). COPD: 1 inhalation (50 mcg) twice daily. For asthma, also use ICS separately or use a fixed combination product.",
        "before_taking": "NEVER use as monotherapy for asthma — must use with an ICS. Not for acute asthma attacks. Always carry short-acting rescue inhaler. Inform your doctor about heart disease, arrhythmias, seizures, diabetes, hypertension, or thyroid disease. Use fixed-dose combination products (Advair, Wixela, etc.) for convenience.",
    },
    "ipratropium": {
        "description": "Ipratropium (Atrovent HFA) is a short-acting inhaled anticholinergic (muscarinic antagonist, SAMA) bronchodilator. Available as metered-dose inhaler (17 mcg/actuation), nebulizer solution, and nasal spray (Atrovent Nasal).",
        "uses": "Ipratropium inhaler is indicated for maintenance treatment of bronchospasm associated with COPD. In combination with albuterol (DuoNeb, Combivent Respimat), it is used for COPD and for acute severe asthma in the emergency setting. Nasal spray is used for rhinorrhea associated with colds and allergic rhinitis.",
        "warnings": "Not the preferred rescue bronchodilator for acute asthma (albuterol is faster-acting and preferred); ipratropium has slower onset than beta-2 agonists. Anticholinergic effects: urinary retention (men with BPH), dry mouth, constipation. Avoid contact with eyes — can cause blurred vision and acute angle-closure glaucoma. Paradoxical bronchospasm can occur.",
        "side_effects": "Common: dry mouth, cough, throat irritation, urinary retention (BPH), constipation, blurred vision. Serious: acute angle-closure glaucoma (if spray contacts eyes), paradoxical bronchospasm, anaphylaxis.",
        "dosage": "COPD (MDI): 2-4 inhalations (34-68 mcg) 3-4 times daily. Nebulizer: 0.5 mg every 6-8 hours. Nasal spray: 2 sprays per nostril 2-3 times daily.",
        "before_taking": "Not for acute asthma attacks (albuterol is preferred). Tell your doctor about glaucoma, enlarged prostate, urinary retention, or kidney disease. Avoid spraying into eyes. Rinse mouth after use to reduce dry mouth.",
    },
    "vancomycin": {
        "description": "Vancomycin (Vancocin) is a glycopeptide antibiotic that inhibits bacterial cell wall synthesis by binding to D-Ala-D-Ala peptide chains. Available as IV injection and oral capsules (only for C. diff — not absorbed systemically). Requires therapeutic drug monitoring.",
        "uses": "IV vancomycin is indicated for serious infections caused by Gram-positive organisms including MRSA (methicillin-resistant Staphylococcus aureus), including bloodstream infections (bacteremia), endocarditis, osteomyelitis, pneumonia, and skin/soft tissue infections. Oral vancomycin is indicated for Clostridioides difficile-associated diarrhea (CDAD) — initial episode (preferred with fidaxomicin over metronidazole) and severe/complicated cases.",
        "warnings": "NEPHROTOXICITY and OTOTOXICITY are the major toxicities — risk increases with higher trough levels, longer duration, concurrent nephrotoxic agents (aminoglycosides, NSAIDs), and in elderly or renally impaired patients. Requires therapeutic drug monitoring (TDM): AUC/MIC-guided dosing is now preferred over trough-only monitoring to optimize efficacy and minimize toxicity. Red Man Syndrome — an infusion-related reaction (not a true allergy) characterized by flushing, erythema, pruritus, and possibly hypotension of the face, neck, and trunk when infused too rapidly — infuse over at least 60 minutes to prevent.",
        "side_effects": "Common: thrombophlebitis at IV site, Red Man Syndrome (infusion reaction). Serious: nephrotoxicity, ototoxicity (hearing loss — usually with high levels or prolonged therapy), neutropenia (with prolonged use), thrombocytopenia.",
        "dosage": "IV: 15-20 mg/kg every 8-12 hours; dose and interval adjusted based on renal function and AUC monitoring. Target AUC/MIC ≥400. Oral (C. diff): 125-500 mg four times daily for 10-14 days (not absorbed; acts locally in gut). Loading dose of 25-35 mg/kg for critically ill patients.",
        "before_taking": "IV vancomycin requires careful monitoring of renal function and drug levels. Infuse slowly over at least 60 minutes to prevent Red Man Syndrome (if it occurs, slow or pause infusion and administer antihistamine). Tell your doctor about kidney disease, hearing problems, other nephrotoxic medications, and previous vancomycin reactions. Monitor BUN, creatinine, vancomycin levels, CBC regularly.",
    },
    "ranitidine": {
        "description": "Ranitidine (Zantac) was an H2 receptor antagonist withdrawn from the US market in April 2020 due to FDA findings of unacceptable levels of the carcinogen N-nitrosodimethylamine (NDMA) in ranitidine products. Brand name Zantac was relaunched with an alternative ingredient (famotidine) in 2022. Ranitidine was widely used for GERD, peptic ulcer disease, and heartburn.",
        "uses": "Ranitidine was indicated for gastroesophageal reflux disease (GERD), peptic ulcer disease, and heartburn. Following market withdrawal, famotidine or PPIs are preferred alternatives for these indications.",
        "warnings": "RANITIDINE IS NO LONGER AVAILABLE IN THE US — withdrawn from the market in April 2020 due to NDMA contamination. Do not use if you have old ranitidine in your medicine cabinet — dispose of it properly. Current alternatives include famotidine (Pepcid), cimetidine, nizatidine, and proton pump inhibitors.",
        "side_effects": "Historical adverse effects included headache, dizziness, constipation, diarrhea, nausea. The main current concern is carcinogenic NDMA contamination of all ranitidine products.",
        "dosage": "No longer available. Alternatives: famotidine 20 mg twice daily (OTC) or 20-40 mg twice daily (prescription) for most indications previously treated with ranitidine.",
        "before_taking": "Do not use ranitidine — it has been recalled worldwide. Contact your pharmacist or doctor for alternatives. Safely dispose of any ranitidine you may have at home through a medication take-back program or by mixing with coffee grounds or kitty litter in a sealed bag before discarding.",
    },
    "ketoconazole": {
        "description": "Ketoconazole (Nizoral) is an imidazole antifungal that inhibits ergosterol synthesis. Available as 200 mg oral tablets (for serious systemic fungal infections), 2% shampoo (OTC/prescription for dandruff and tinea versicolor), and topical cream/gel.",
        "uses": "Oral ketoconazole is now a last-resort antifungal for systemic fungal infections only when other antifungals are not available or tolerated. Topical ketoconazole shampoo is widely used for dandruff (seborrheic dermatitis) and tinea versicolor.",
        "warnings": "FDA BOXED WARNING (oral): Serious hepatotoxicity, including some fatalities, has occurred with oral ketoconazole — restrict to infections where benefits clearly outweigh risks. QT prolongation — do not use with other QT-prolonging drugs. Multiple serious drug interactions — potent CYP3A4 inhibitor (dramatically increases levels of many drugs). Due to toxicity and interaction concerns, oral ketoconazole has largely been replaced by safer systemic antifungals (fluconazole, itraconazole, voriconazole). Topical formulations carry no significant systemic toxicity.",
        "side_effects": "Oral: nausea, vomiting, abdominal pain, adrenal insufficiency (inhibits cortisol synthesis). Serious: hepatotoxicity, QT prolongation, adrenal crisis. Topical: mild skin irritation, stinging, pruritus.",
        "dosage": "Oral (systemic infections, last resort): 200-400 mg once daily. Shampoo (dandruff): apply twice weekly for 4 weeks; then once weekly for maintenance. Topical cream: apply once or twice daily for 2-6 weeks.",
        "before_taking": "Oral ketoconazole should only be used as a last resort. Monitor LFTs closely — discontinue if abnormal liver tests. The topical shampoo and cream formulations are safe and effective for skin/scalp conditions. Tell your doctor about all medications if using oral form — extensive drug interactions.",
    },
    "ampicillin": {
        "description": "Ampicillin is a broad-spectrum aminopenicillin antibiotic available as 250 and 500 mg capsules, oral suspension, and IV/IM injection. Amoxicillin has better oral bioavailability and is preferred for most indications where oral therapy is appropriate.",
        "uses": "Ampicillin is indicated for urinary tract infections, gastrointestinal infections (H. pylori — in combination), meningitis and septicemia (IV — Listeria monocytogenes coverage), respiratory tract infections, skin and soft tissue infections, and enterococcal infections (with gentamicin for endocarditis). IV ampicillin is essential for Listeria and group B streptococcal infections.",
        "warnings": "Hypersensitivity reactions including anaphylaxis — cross-reactivity with penicillin. RASH — a maculopapular rash occurs in approximately 5-10% of patients; risk increases dramatically (>80%) in patients with infectious mononucleosis (EBV), CLL, or concurrent allopurinol use — this is not a true penicillin allergy. Clostridioides difficile-associated diarrhea.",
        "side_effects": "Common: diarrhea (higher incidence than other penicillins), nausea, rash (especially with mononucleosis). Serious: anaphylaxis, C. diff colitis, interstitial nephritis, seizures (high doses), hepatotoxicity.",
        "dosage": "Oral: 250-500 mg every 6 hours. IV: 1-2 g every 4-6 hours (more severe infections); meningitis: 2 g every 4 hours. Renal dose adjustment required for CrCl <30 mL/min.",
        "before_taking": "Tell your doctor about penicillin allergy, kidney disease, and infectious mononucleosis (high rash risk). For most oral uses, amoxicillin (better bioavailability) is preferred. IV ampicillin is important for Listeria coverage in meningitis, particularly in neonates, elderly, and immunocompromised patients.",
    },
    "ceftriaxone": {
        "description": "Ceftriaxone (Rocephin) is a third-generation cephalosporin antibiotic with broad gram-negative coverage and once-daily IV/IM dosing (half-life 6-9 hours, allowing once-daily dosing). Available as 250 mg, 500 mg, 1 g, and 2 g powder for injection.",
        "uses": "Ceftriaxone is indicated for lower respiratory tract infections (pneumonia), urinary tract infections, pelvic inflammatory disease, gonorrhea, bacterial meningitis, septicemia, bone and joint infections, skin and soft tissue infections, and surgical prophylaxis. It is the preferred treatment for community-acquired pneumonia requiring hospitalization (with azithromycin) and for bacterial meningitis.",
        "warnings": "Cross-reactivity with penicillin allergy (approximately 1-2%). Biliary pseudolithiasis (formation of calcium-ceftriaxone precipitates in bile) — avoid in neonates receiving calcium-containing IV solutions (risk of fatal cardiopulmonary complications with simultaneous administration of calcium and ceftriaxone). Do not co-administer with calcium-containing IV solutions in any patient. CDAD has been reported.",
        "side_effects": "Common: injection site reactions, diarrhea, rash. Serious: anaphylaxis, CDAD, biliary pseudolithiasis (sludging in gallbladder — usually asymptomatic, resolves after discontinuation), hemolytic anemia.",
        "dosage": "Most infections: 1-2 g IV/IM once daily. Severe infections/meningitis: 2 g IV every 12 hours. Gonorrhea: 500 mg IM single dose (≥150 kg: 1 g). Bacterial meningitis: 2 g IV every 12 hours.",
        "before_taking": "Tell your doctor about penicillin or cephalosporin allergy. Do not administer with calcium-containing IV solutions (including Ringer's lactate, Hartmann's solution) or give within 48 hours of the last dose of any calcium-containing solution. Urine and stools may be discolored — normal.",
    },
    "captopril": {
        "description": "Captopril (Capoten) is an ACE inhibitor used to treat hypertension, heart failure, left ventricular dysfunction after myocardial infarction, and diabetic nephropathy.",
        "uses": "Captopril is indicated for hypertension, heart failure (adjunctive therapy), left ventricular dysfunction after MI, and diabetic nephropathy (reduction of proteinuria). It blocks the renin-angiotensin-aldosterone system by inhibiting ACE, reducing angiotensin II and aldosterone levels.",
        "warnings": "Angioedema of the face, extremities, lips, tongue, glottis, or larynx may occur at any time — stop immediately and seek emergency care. Contraindicated in pregnancy (teratogenic: oligohydramnios, neonatal skull hypoplasia, renal failure, death). Hyperkalemia risk, especially with potassium supplements or potassium-sparing diuretics. Neutropenia/agranulocytosis reported in patients with renal impairment or collagen vascular disease — monitor WBC. First-dose hypotension, especially with volume depletion.",
        "side_effects": "Common: dry cough (up to 10%), rash, loss of taste, dizziness, fatigue. Serious: angioedema, hyperkalemia, acute kidney injury (especially with bilateral renal artery stenosis), neutropenia.",
        "dosage": "Hypertension: Initial 12.5-25 mg 2-3 times daily; usual 25-150 mg/day in 2-3 divided doses; max 450 mg/day. Heart failure: Initial 6.25-12.5 mg 3 times daily; target 50 mg 3 times daily. Post-MI LV dysfunction: 6.25 mg test dose, then 12.5 mg 3 times daily; target 50 mg 3 times daily. Take on empty stomach 1 hour before meals.",
        "before_taking": "Do not take captopril if pregnant or planning pregnancy. Tell your doctor if you have a history of angioedema, renal artery stenosis, kidney disease, liver disease, diabetes, or collagen vascular disease. Avoid potassium supplements and NSAIDs unless directed.",
    },
    "dupilumab": {
        "description": "Dupilumab (Dupixent) is a biologic monoclonal antibody targeting the IL-4Rα subunit, blocking IL-4 and IL-13 signaling. It is used for moderate-to-severe atopic dermatitis, asthma, chronic rhinosinusitis with nasal polyps, eosinophilic esophagitis, and prurigo nodularis.",
        "uses": "Dupilumab is indicated for moderate-to-severe atopic dermatitis in adults and pediatric patients ≥6 months whose disease is not adequately controlled with topical therapies; add-on maintenance therapy in moderate-to-severe asthma with eosinophilic phenotype or oral corticosteroid-dependent asthma; add-on maintenance therapy in adults with inadequately controlled chronic rhinosinusitis with nasal polyps (CRSwNP); eosinophilic esophagitis (EoE); and prurigo nodularis.",
        "warnings": "Do not use in patients with known hypersensitivity to dupilumab. Conjunctivitis and keratitis occur more frequently in atopic dermatitis patients. Avoid use of live vaccines during treatment. Parasitic infections: pre-treat if at risk before initiating therapy. Eosinophilia with some patients transitioning off systemic corticosteroids.",
        "side_effects": "Common: injection site reactions, conjunctivitis, blepharitis, oral herpes, other herpes infections, headache. Atopic dermatitis: conjunctivitis more frequent. Asthma: nasopharyngitis, oropharyngeal pain, eosinophilia.",
        "dosage": "Atopic dermatitis (adults, 12+): 600 mg initial (two 300 mg injections), then 300 mg every other week subcutaneously. Children 6 months-5 years (5-<15 kg): 200 mg q4w; (15-<30 kg): 300 mg q4w. Asthma/CRSwNP: 200-300 mg every 2 weeks. Administer subcutaneously into abdomen, thigh, or upper arm.",
        "before_taking": "Tell your doctor if you have a history of eye problems (conjunctivitis, keratitis), parasitic infections, or are scheduled for any live vaccine. Inform your doctor about all current medications including other biologics.",
    },
    "hydrocortisone": {
        "description": "Hydrocortisone is a topical corticosteroid available in various strengths (0.5%, 1%, 2.5%) as cream, ointment, lotion, and solution. Lower-strength formulations are available OTC; higher-strength preparations require a prescription.",
        "uses": "Hydrocortisone topical is used to relieve itching, redness, swelling, and discomfort of skin conditions such as eczema, psoriasis, insect bites, minor skin irritations, rashes, and allergic reactions. Oral/IV hydrocortisone is used for adrenal insufficiency, inflammatory conditions, allergic reactions, and as replacement therapy in adrenocortical insufficiency.",
        "warnings": "Do not use on the face, groin, or underarms unless directed by a doctor. Avoid contact with eyes. Do not use on infected skin (bacterial, fungal, or viral) unless co-administered with appropriate antimicrobials. Prolonged use can cause skin thinning, stretch marks, perioral dermatitis, rosacea, and systemic effects from absorption. Discontinue gradually for long-term systemic use.",
        "side_effects": "Topical: burning, itching, irritation, skin thinning, striae, acne, hypopigmentation, contact dermatitis. Systemic (high doses/prolonged use): Cushing's syndrome, HPA-axis suppression, hyperglycemia.",
        "dosage": "Topical: Apply thin film to affected area 2-4 times daily. OTC maximum strength 1%. Prescription formulations (2.5%) used for more severe conditions. Apply as directed; do not bandage tightly.",
        "before_taking": "Do not apply to open wounds. Tell your doctor about any skin infections, diabetes, or thin skin. For OTC use, do not use longer than 7 days without consulting a doctor.",
    },
    "triamcinolone": {
        "description": "Triamcinolone acetonide is a medium-potency topical corticosteroid (Kenalog) available as cream, ointment, lotion, spray, and dental paste. Injectable triamcinolone is used for intra-articular and intralesional injections.",
        "uses": "Triamcinolone topical is indicated for inflammatory and pruritic manifestations of corticosteroid-responsive dermatoses including eczema, psoriasis, and contact dermatitis. Injectable triamcinolone is used for allergic conditions, arthritis, bursitis, tendinitis, inflammatory skin lesions, and keloids.",
        "warnings": "Not for ophthalmic use. Avoid prolonged use on face, axilla, or groin. Systemic absorption can cause HPA axis suppression. Do not use with occlusive dressings unless directed. Injectable: should not be injected intravenously. Risk of infection with injectable formulations. Administer injectable form only by healthcare professionals.",
        "side_effects": "Topical: burning, itching, irritation, dryness, skin atrophy, striae, folliculitis, hypertrichosis. Systemic (from large areas, occlusion, or long-term use): HPA suppression, hyperglycemia, Cushing's syndrome.",
        "dosage": "Topical (0.025-0.5% cream/ointment): Apply 2-4 times daily as thin film. Intra-articular injection: 2.5-15 mg depending on joint size. Intralesional: 1-30 mg. Consult a specialist for injectable formulations.",
        "before_taking": "Tell your doctor about skin infections, diabetes, or history of adrenal problems. Do not use topical triamcinolone on the face for extended periods. Avoid live vaccines during systemic corticosteroid therapy.",
    },
    "mycophenolate": {
        "description": "Mycophenolate mofetil (CellCept) and mycophenolate sodium (Myfortic) are immunosuppressants used to prevent organ rejection in kidney, heart, and liver transplant patients.",
        "uses": "Mycophenolate is used in combination with cyclosporine and corticosteroids to prevent organ rejection in patients receiving allogeneic renal, cardiac, or hepatic transplants. It inhibits inosine monophosphate dehydrogenase (IMPDH), selectively suppressing lymphocyte proliferation.",
        "warnings": "FDA BOXED WARNING: Increased susceptibility to infections and possible development of lymphoma and other neoplasms. Use in pregnancy causes pregnancy loss and congenital malformations — use effective contraception. Do not administer live vaccines. Serious: progressive multifocal leukoencephalopathy (PML), pure red cell aplasia, GI perforations, and severe neutropenia.",
        "side_effects": "Common: diarrhea, nausea, vomiting, leukopenia, infection (bacterial, viral, fungal), anemia, hypertension. Serious: opportunistic infections (CMV, Pneumocystis jirovecii), lymphoma, PML, GI hemorrhage.",
        "dosage": "Renal transplant (mofetil): 1 g twice daily (oral or IV). Cardiac/hepatic transplant: 1.5 g twice daily. Mycophenolate sodium (Myfortic): 720 mg twice daily for renal transplant. Take on empty stomach for mofetil; Myfortic can be taken with food.",
        "before_taking": "Women of childbearing potential must use two forms of contraception. Tell your doctor if you have GI disease, active serious infection, or rare hereditary disorders of galactose intolerance.",
    },
    "rituximab": {
        "description": "Rituximab (Rituxan, MabThera) is an anti-CD20 monoclonal antibody used to treat non-Hodgkin's lymphoma, chronic lymphocytic leukemia, rheumatoid arthritis, granulomatosis with polyangiitis, microscopic polyangiitis, and pemphigus vulgaris.",
        "uses": "Rituximab is indicated for CD20-positive B-cell non-Hodgkin lymphomas (follicular, diffuse large B-cell), chronic lymphocytic leukemia (CLL), rheumatoid arthritis (with methotrexate), granulomatosis with polyangiitis (GPA) and microscopic polyangiitis (MPA), and pemphigus vulgaris.",
        "warnings": "FDA BOXED WARNINGS: Fatal infusion reactions can occur within 24 hours of infusion — have resuscitation equipment available. Severe mucocutaneous reactions including Stevens-Johnson syndrome, toxic epidermal necrolysis — discontinue if severe skin reaction develops. Hepatitis B virus (HBV) reactivation with fulminant hepatitis and fatal outcomes — screen all patients before treatment; monitor during and for several months after. Progressive multifocal leukoencephalopathy (PML) from JC virus — fatal outcomes reported.",
        "side_effects": "Common: infusion reactions (fever, chills, rigors, pruritus, urticaria, angioedema), fatigue, nausea, headache, infections. Serious: HBV reactivation, PML, severe infusion reactions, cardiac arrhythmias.",
        "dosage": "NHL (follicular, first-line): 375 mg/m² IV weekly ×4; as maintenance 375 mg/m² IV every 8 weeks. DLBCL: 375 mg/m² IV on day 1 of each chemotherapy cycle. CLL: 375 mg/m² cycle 1, then 500 mg/m² cycles 2-6. RA: 2 doses of 1000 mg IV separated by 2 weeks. Administered IV only by trained professionals.",
        "before_taking": "Screen for hepatitis B before treatment. Do not give live vaccines during or after treatment. Tell your doctor about heart disease, history of infections, or if you are pregnant or breastfeeding.",
    },
    "insulin-aspart": {
        "description": "Insulin aspart (NovoLog, NovoRapid, Fiasp) is a rapid-acting insulin analog used to control blood sugar in adults and children with diabetes mellitus.",
        "uses": "Insulin aspart is used to control blood glucose in patients with type 1 or type 2 diabetes mellitus. As a rapid-acting insulin, it is typically administered at mealtime to cover postprandial glucose excursions. It can also be used in insulin pumps (continuous subcutaneous insulin infusion).",
        "warnings": "Never share insulin pens, syringes, or needles. Monitor blood glucose closely; dosage adjustments required with illness, diet changes, or increased activity. Hypoglycemia is the most common adverse effect — recognize and treat promptly. Hypokalemia can occur. Not for IV administration (except in specific clinical settings under supervision). Not for treatment of diabetic ketoacidosis.",
        "side_effects": "Common: hypoglycemia, injection site reactions (lipoatrophy, lipohypertrophy), weight gain. Serious: severe hypoglycemia, hypokalemia, generalized allergy (rare).",
        "dosage": "Type 1 diabetes: total daily dose typically 0.5-1 unit/kg/day, with 50-70% as basal insulin and 30-50% as rapid-acting insulin given at meals. Inject subcutaneously 5-10 minutes before meal; Fiasp can be given 0-2 minutes before or 20 minutes after starting a meal. Dose individualized by patient blood glucose response.",
        "before_taking": "Tell your doctor about all medications you take, especially thiazolidinediones, GLP-1 agonists, and beta-blockers (which can mask hypoglycemia symptoms). Monitor blood glucose regularly and adjust for sick days, exercise, or dietary changes.",
    },
    "insulin-lispro": {
        "description": "Insulin lispro (Humalog, Admelog, Lyumjev) is a rapid-acting insulin analog used for glycemic control in adults and children with diabetes mellitus.",
        "uses": "Insulin lispro controls postprandial blood glucose in type 1 and type 2 diabetes. It has a faster onset (15 minutes) than regular human insulin and is typically injected immediately before meals. Available as U-100 and U-200 concentrations; U-200 is not for IV use.",
        "warnings": "Never share insulin delivery devices. Hyperglycemia may result if the dose is too low; hypoglycemia if too high. Confirm insulin type before injection — do not interchange with other insulin products without dose adjustment. U-200 concentration not for IV use and requires specific dose calculation. Monitor for hypokalemia in at-risk patients.",
        "side_effects": "Common: hypoglycemia, injection site reactions, weight gain. Serious: severe hypoglycemia, hypokalemia, anaphylaxis (rare).",
        "dosage": "Typically given 0-15 minutes before meals. Total daily dose individualized; typical starting dose 0.5 units/kg/day in type 1 diabetes. Lyumjev (faster-acting) can be injected 1-2 minutes before meals. Inject subcutaneously in abdomen, thigh, or upper arm; rotate sites.",
        "before_taking": "Confirm which insulin product you are using. Test blood glucose regularly. Tell your doctor about kidney or liver disease; dose adjustments may be needed. Avoid mixing with insulins other than NPH insulin without specific instructions.",
    },
    "isosorbide": {
        "description": "Isosorbide mononitrate (Imdur, Monoket) and isosorbide dinitrate (Isordil) are nitrates used to prevent angina pectoris. They dilate blood vessels to reduce the heart's workload.",
        "uses": "Isosorbide preparations are indicated for the prevention of angina pectoris caused by coronary artery disease. They are not indicated for the acute relief of an anginal attack (use sublingual nitroglycerin for acute attacks). Isosorbide mononitrate extended-release is used once daily; immediate-release formulations require an eccentric (asymmetric) dosing schedule to prevent nitrate tolerance.",
        "warnings": "Contraindicated with PDE5 inhibitors (sildenafil, tadalafil, vardenafil, avanafil) — severe hypotension may result, potentially fatal. Contraindicated with riociguat. Hypotension, syncope, and reflex tachycardia may occur, especially with first dose or upon standing. Headache is common and usually diminishes with continued therapy. Tolerance develops with continuous nitrate exposure — use eccentric dosing (provide nitrate-free interval of 10-12 hours).",
        "side_effects": "Common: headache (up to 50%, usually improves), dizziness, flushing, postural hypotension. Serious: severe hypotension, syncope, methemoglobinemia (rare).",
        "dosage": "Isosorbide mononitrate ER: 30-60 mg once daily (morning), max 240 mg/day. Isosorbide dinitrate (Isordil): 5-40 mg 2-3 times daily with an eccentric schedule (e.g., 7am, 12pm; avoid evening doses to prevent tolerance). Sublingual isosorbide dinitrate: 2.5-5 mg for acute angina prevention up to 15 min before activity.",
        "before_taking": "Tell your doctor if you take any ED medications (sildenafil/Viagra, tadalafil/Cialis, vardenafil/Levitra, avanafil/Stendra) or riociguat (Adempas) — combining these is potentially fatal. Avoid alcohol while taking nitrates. Rise slowly from sitting or lying positions.",
    },
    "lansoprazole": {
        "description": "Lansoprazole (Prevacid) is a proton pump inhibitor (PPI) that reduces gastric acid production by irreversibly inhibiting the H+/K+ ATPase proton pump in gastric parietal cells.",
        "uses": "Lansoprazole is indicated for duodenal and gastric ulcers, GERD and erosive esophagitis, Helicobacter pylori eradication (combination therapy), pathological hypersecretory conditions (Zollinger-Ellison syndrome), NSAID-associated ulcer treatment and prevention, and frequent heartburn (OTC, 15 mg). Pediatric approval for GERD and erosive esophagitis (≥1 year).",
        "warnings": "Hypomagnesemia has been reported with prolonged use. Clostridium difficile-associated diarrhea (CDAD) risk increases with PPI use. Risk of bone fractures of the hip, wrist, and spine with long-term, high-dose PPI therapy. Potential interference with vitamin B12 absorption with long-term therapy. Symptom relief does not rule out gastric malignancy. Acute interstitial nephritis has been reported.",
        "side_effects": "Common: headache, diarrhea, nausea, abdominal pain. Long-term: vitamin B12 deficiency, hypomagnesemia, bone fractures. Rare: CDAD, acute interstitial nephritis.",
        "dosage": "Duodenal ulcer: 15 mg once daily for 4 weeks. Gastric ulcer: 30 mg once daily for 4-8 weeks. GERD: 15-30 mg once daily for 4-8 weeks. Erosive esophagitis: 30 mg once daily for 8 weeks. H. pylori: 30 mg twice daily × 10-14 days (combination therapy). Take before eating (preferably in the morning).",
        "before_taking": "Tell your doctor if you take methotrexate, HIV medications (atazanavir, nelfinavir), clopidogrel, or warfarin. Do not take for longer than 14 days without consulting a doctor for OTC use.",
    },
    "bisacodyl": {
        "description": "Bisacodyl (Dulcolax) is a stimulant laxative that promotes peristalsis and intestinal fluid accumulation. It is available as tablets and rectal suppositories.",
        "uses": "Bisacodyl is used for the short-term relief of constipation and for bowel cleansing before surgical, colonoscopic, or radiological procedures. It stimulates the myenteric plexus in the intestinal wall, causing coordinated peristaltic contractions.",
        "warnings": "Do not use for longer than one week unless directed by a doctor. Avoid in cases of bowel obstruction, inflammatory bowel disease, appendicitis, or nausea/vomiting. Rectal suppositories should not be used with pre-existing rectal bleeding or hemorrhoids without medical advice. Prolonged use can lead to electrolyte imbalance, dehydration, and laxative dependence.",
        "side_effects": "Common: abdominal cramping, nausea, diarrhea, griping, rectal burning (suppositories). Serious: severe electrolyte imbalance with prolonged use.",
        "dosage": "Tablets: Adults and children ≥12 years: 5-15 mg (1-3 tablets) at bedtime; max 30 mg/day. Suppositories: Adults: 10 mg rectally once daily. Swallow tablets whole (do not crush or chew); do not take within 1 hour of milk or antacids.",
        "before_taking": "Tell your doctor if you have abdominal pain, nausea, vomiting, or if constipation has lasted more than 2 weeks. Not for daily, long-term use. Avoid milk and antacids within 1 hour of bisacodyl tablet.",
    },
    "polyethylene-glycol": {
        "description": "Polyethylene glycol 3350 (Miralax, GlycoLax) is an osmotic laxative that draws water into the colon to soften stool and increase bowel movement frequency.",
        "uses": "PEG 3350 is used for the treatment of occasional constipation in adults and children ≥17 years. It is also used in higher doses (electrolyte solution, GoLYTELY, MoviPrep) for bowel preparation before colonoscopy or GI procedures. The OTC formulation is generally used for 2-7 days at a time.",
        "warnings": "Do not use if you have bowel obstruction, inflammatory bowel disease, or megacolon. Infrequent but serious: cases of tremors, tics, and obsessive-compulsive behaviors have been reported in children — consult a pediatrician before use in children under 17. Use of high-dose electrolyte PEG solutions carries risk of fluid and electrolyte imbalance.",
        "side_effects": "Common: nausea, abdominal bloating, cramping, flatulence, diarrhea. Rare: urticaria, electrolyte abnormalities (large doses).",
        "dosage": "Constipation (OTC): 17 g (1 capful) in 4-8 oz of beverage once daily; onset in 1-3 days. May increase to 17 g twice daily under medical direction. Bowel prep (prescription): per product labeling.",
        "before_taking": "Tell your doctor if you have kidney problems before using PEG regularly. OTC use should not exceed 7 days without medical supervision. Check with a doctor before using in children.",
    },
    "docusate": {
        "description": "Docusate sodium (Colace, Dulcolax Stool Softener) is a stool softener that works by increasing water penetration into the stool. It is available OTC in capsule and liquid forms.",
        "uses": "Docusate is used as a stool softener to relieve occasional constipation and to prevent straining during bowel movements. It is often recommended after childbirth, surgery, or myocardial infarction to prevent Valsalva-associated complications.",
        "warnings": "Avoid use in patients with bowel obstruction. Should not be used simultaneously with mineral oil (may increase mineral oil absorption). Do not use more than 1 week without consulting a doctor. Not recommended as a laxative treatment for severe constipation.",
        "side_effects": "Generally well tolerated. Occasional: throat irritation (with liquid form), mild cramping, diarrhea, nausea.",
        "dosage": "Adults: 50-500 mg/day in 1-4 divided doses. Children 2-12 years: 50-150 mg/day. Children <2 years: 25 mg/day. Effects typically seen within 12-72 hours. Take with a full glass of water.",
        "before_taking": "Tell your doctor if you are taking mineral oil. Use for short-term relief only; do not use longer than 7 days unless directed.",
    },
    "moxifloxacin": {
        "description": "Moxifloxacin (Avelox, Vigamox) is a fourth-generation fluoroquinolone antibiotic with broad-spectrum activity including enhanced gram-positive and anaerobic coverage.",
        "uses": "Oral/IV moxifloxacin is indicated for community-acquired pneumonia, acute bacterial exacerbation of chronic bronchitis, complicated and uncomplicated skin infections, intra-abdominal infections (combination therapy), and acute bacterial sinusitis. Ophthalmic moxifloxacin (Vigamox) is used for bacterial conjunctivitis.",
        "warnings": "FDA BOXED WARNING: Disabling and potentially irreversible serious adverse reactions including tendinitis, tendon rupture, peripheral neuropathy, and CNS effects. QT prolongation: moxifloxacin is associated with significant QT prolongation — avoid in patients with known QT prolongation, uncorrected hypokalemia, or who are taking Class IA or III antiarrhythmics. Hepatotoxicity, including fatal cases, has been reported. Not recommended for UTIs due to variable activity against Pseudomonas and Enterococcus.",
        "side_effects": "Common: nausea, diarrhea, dizziness, headache. Serious: QT prolongation, tendon rupture, peripheral neuropathy, hepatotoxicity, severe skin reactions.",
        "dosage": "Community-acquired pneumonia / ABECB / skin infections: 400 mg orally once daily for 5-14 days. Intra-abdominal: 400 mg IV/PO once daily for 5-14 days. Take without regard to food; avoid antacids/multivitamins within 4 hours.",
        "before_taking": "Tell your doctor if you have QT prolongation, low potassium/magnesium, liver disease, myasthenia gravis, or tendon disorders. Avoid in patients taking class IA or III antiarrhythmics. Do not use for uncomplicated UTIs.",
    },
    "nystatin": {
        "description": "Nystatin (Mycostatin, Nilstat) is a polyene antifungal effective against Candida species. It is available as oral tablets, powder (for oral suspension), topical cream/ointment/powder, and vaginal tablets.",
        "uses": "Nystatin topical is used to treat cutaneous and mucocutaneous Candida infections including oral thrush, diaper rash, vaginal candidiasis, and skin candidiasis in skin folds. Oral nystatin is used for oral candidiasis (thrush) and intestinal Candida overgrowth. It is not absorbed systemically in oral forms.",
        "warnings": "Nystatin is not effective against systemic fungal infections; do not use for systemic candidiasis or fungi other than Candida. Topical products should not be used in the eyes. Vaginal tablets should not be used in children under 12 years without a doctor's guidance.",
        "side_effects": "Topical: occasional mild irritation, burning, itching. Oral: nausea, vomiting, diarrhea, abdominal pain (usually mild). Generally very well tolerated due to negligible systemic absorption.",
        "dosage": "Oral thrush (oral suspension/pastilles): 400,000-600,000 units 4 times daily; swish and swallow. Intestinal candidiasis: 500,000-1,000,000 units 3 times daily. Topical: apply 2-3 times daily to affected area. Vaginal tablets: 100,000 units intravaginally once daily for 2 weeks.",
        "before_taking": "Tell your doctor if you have any sensitivity to nystatin or polyene antifungals. Do not use to treat systemic or deep fungal infections. Continue treatment for full prescribed course even if symptoms improve.",
    },
    "tenofovir": {
        "description": "Tenofovir disoproxil fumarate (TDF, Viread) and tenofovir alafenamide (TAF, Vemlidy) are nucleotide reverse transcriptase inhibitors (NRTIs) used to treat HIV-1 infection and chronic hepatitis B.",
        "uses": "Tenofovir TDF is used in combination with other antiretrovirals for HIV-1 treatment and pre-exposure prophylaxis (PrEP) for HIV prevention. It is also approved as a single agent for chronic hepatitis B. TAF (Vemlidy) has better renal and bone safety and is used for hepatitis B and as a component of HIV regimens.",
        "warnings": "FDA BOXED WARNINGS (TDF): Lactic acidosis and severe hepatomegaly with steatosis, including fatal cases. Post-treatment exacerbation of hepatitis B — monitor HBV status for several months after stopping. Risk of nephrotoxicity and osteomalacia with prolonged TDF use; monitor renal function and bone density. For PrEP: confirm HIV-negative status before prescribing and test regularly.",
        "side_effects": "Common: nausea, vomiting, diarrhea, headache, fatigue, asthenia. Serious: lactic acidosis, hepatomegaly, nephrotoxicity (Fanconi syndrome), osteomalacia (bone pain, fractures), HBV flare on discontinuation.",
        "dosage": "HIV treatment and PrEP (TDF): 300 mg orally once daily with a meal. Hepatitis B (TDF): 300 mg once daily. TAF (Vemlidy for HBV): 25 mg once daily with food. Dose adjustment required for renal impairment.",
        "before_taking": "Tell your doctor if you have kidney disease, bone disease, or hepatitis B infection. Do not stop tenofovir without medical supervision if you have hepatitis B — severe flares can occur. Test HIV status before using for PrEP.",
    },
    "vardenafil": {
        "description": "Vardenafil (Levitra, Staxyn) is a phosphodiesterase type 5 (PDE5) inhibitor used to treat erectile dysfunction in men.",
        "uses": "Vardenafil is indicated for the treatment of erectile dysfunction (ED) in adult males. It works by enhancing the effect of nitric oxide released in response to sexual stimulation, relaxing smooth muscle in the penis and increasing blood flow.",
        "warnings": "Contraindicated with nitrates in any form (organic nitrates: nitroglycerin, isosorbide mono/dinitrate; recreational amyl nitrite 'poppers') — severe hypotension can be fatal. Contraindicated with guanylate cyclase stimulators (riociguat). Use with caution in patients with cardiovascular disease. Priapism (painful erection lasting more than 4 hours) requires immediate medical attention. Sudden hearing loss and visual disturbances (including non-arteritic anterior ischemic optic neuropathy, NAION) reported. QT prolongation risk (Levitra may prolong QT interval more than other PDE5 inhibitors).",
        "side_effects": "Common: headache, flushing, nasal congestion, dyspepsia, dizziness, vision changes (blue-tinged or blurred vision). Serious: severe hypotension with nitrates, priapism, NAION, sudden hearing loss.",
        "dosage": "Levitra tablets: 10 mg 60 minutes before sexual activity; range 5-20 mg; max 20 mg/day. Staxyn ODT: 10 mg 1 hour before activity (do not use with Levitra on same day; not interchangeable dose-for-dose). Do not take more than once daily.",
        "before_taking": "Tell your doctor if you take any nitrate medications. Tell your doctor about all cardiovascular problems, low blood pressure, liver or kidney disease, blood cell disorders (sickle cell anemia, leukemia, myeloma), or anatomical deformity of the penis. Avoid grapefruit juice (may increase vardenafil levels).",
    },
    "guanfacine": {
        "description": "Guanfacine (Intuniv ER, Tenex) is a selective alpha-2A adrenergic receptor agonist used for ADHD (extended-release) and hypertension (immediate-release).",
        "uses": "Guanfacine extended-release (Intuniv) is indicated for ADHD in children and adolescents ages 6-17, either as monotherapy or adjunctive to stimulant medications. Immediate-release guanfacine (Tenex) is used for hypertension in adults. Guanfacine modulates prefrontal cortex function to improve attention, impulse control, and working memory.",
        "warnings": "Hypotension and bradycardia can occur — monitor blood pressure and heart rate. Syncope has been reported. Sedation and somnolence, especially early in treatment. Do not abruptly discontinue (risk of rebound hypertension). CNS depression is additive with alcohol and other sedatives. Guanfacine has not been systematically evaluated in combination with all stimulant medications.",
        "side_effects": "Common: somnolence, headache, fatigue, upper abdominal pain, nausea, lethargy, irritability, dizziness, decreased appetite, dry mouth, hypotension, bradycardia. Serious: hypotension, syncope.",
        "dosage": "ADHD (Intuniv ER, children/adolescents 6-17 years): Start 1 mg once daily; target 0.05-0.12 mg/kg/day (range 1-7 mg/day); titrate weekly. Take at same time each day; do not crush, chew, or break. Hypertension (adults): 1 mg once daily at bedtime, max 3 mg/day.",
        "before_taking": "Tell your doctor about heart conditions, kidney or liver disease, depression, or low blood pressure. Avoid alcohol. Do not stop abruptly — taper the dose under medical supervision.",
    },
    "ziprasidone": {
        "description": "Ziprasidone (Geodon) is an atypical antipsychotic used for schizophrenia and bipolar disorder. It is a serotonin-dopamine receptor antagonist.",
        "uses": "Ziprasidone is indicated for the treatment of schizophrenia in adults, acute manic or mixed episodes in bipolar I disorder (oral), and agitation associated with schizophrenia (IM injection). It has some antidepressant activity due to serotonin 1A agonism.",
        "warnings": "FDA BOXED WARNING: Elderly patients with dementia-related psychosis treated with antipsychotics are at increased risk of death — ziprasidone is not approved for this use. QT prolongation: ziprasidone causes a dose-dependent QT prolongation. Avoid in patients with QTc >500 ms, known QT prolongation, cardiac arrhythmias, recent MI, or uncompensated heart failure. Concomitant use with drugs known to cause QT prolongation is contraindicated. Neuroleptic malignant syndrome (NMS), tardive dyskinesia, and metabolic effects reported.",
        "side_effects": "Common: drowsiness, dizziness, nausea, dyspepsia, constipation, EPS (restlessness, rigidity), rash, QT prolongation. Serious: NMS, tardive dyskinesia, severe allergic reactions, metabolic syndrome, hyperglycemia.",
        "dosage": "Schizophrenia: 20 mg twice daily with food; increase every 2 days if needed; range 20-100 mg twice daily. Bipolar disorder (acute): 40 mg twice daily on day 1, then 60-80 mg twice daily. IM (acute agitation): 10-20 mg; max 40 mg/day. Take oral doses with food (≥500 kcal) for adequate absorption.",
        "before_taking": "Tell your doctor if you have a history of QT prolongation, electrolyte imbalance (hypokalemia, hypomagnesemia), heart disease, or are taking other QT-prolonging drugs. Always take with food. Avoid alcohol.",
    },
    "temazepam": {
        "description": "Temazepam (Restoril) is a short-acting benzodiazepine hypnotic used for the short-term treatment of insomnia.",
        "uses": "Temazepam is indicated for the short-term treatment of insomnia characterized by difficulty falling asleep, frequent nocturnal awakenings, and/or early morning awakenings. Its use should generally be limited to 7-10 days; reevaluate if used for longer.",
        "warnings": "FDA BOXED WARNINGS: Concomitant use with opioids may result in profound sedation, respiratory depression, coma, and death — reserve combination for patients without adequate alternatives. Abuse, misuse, and addiction: risk of abuse even at recommended doses. Risk of physical and psychological dependence. Withdrawal reactions, including potentially life-threatening seizures, with abrupt discontinuation. Complex sleep behaviors (sleep-driving, sleep-walking, eating) while not fully awake — discontinue if any occur. Temazepam is a Schedule IV controlled substance.",
        "side_effects": "Common: drowsiness, dizziness, lightheadedness, headache, next-day residual sedation ('hangover' effect). Serious: respiratory depression (with opioids), paradoxical reactions (excitement, agitation), complex sleep behaviors, dependence.",
        "dosage": "Adults: 7.5-30 mg at bedtime. Elderly/debilitated: start 7.5 mg. Maximum 30 mg. Use the lowest effective dose. Do not exceed 7-10 consecutive days of use without reassessment.",
        "before_taking": "Do not combine with opioids, alcohol, or other CNS depressants. Tell your doctor about liver disease, respiratory problems, drug or alcohol dependence history, depression, or sleep apnea. Do not abruptly stop temazepam — taper gradually.",
    },
    "methocarbamol": {
        "description": "Methocarbamol (Robaxin) is a centrally acting muscle relaxant used for the relief of acute musculoskeletal pain and discomfort.",
        "uses": "Methocarbamol is indicated as an adjunct to rest and physical therapy for the relief of discomfort associated with acute, painful musculoskeletal conditions. Its mechanism is not completely understood but is attributed to general CNS depression rather than direct action on skeletal muscle or the neuromuscular junction.",
        "warnings": "May impair mental and physical abilities required for driving or operating machinery. CNS depressant effects are additive with alcohol and other CNS depressants. Use caution in patients with renal impairment (injectable form contains polyethylene glycol 300). May cause urine to change color (green, brown, or black) — benign.",
        "side_effects": "Common: drowsiness, dizziness, lightheadedness, nausea, headache, blurred vision. Rare: anaphylactic reactions, convulsions.",
        "dosage": "Adults: 1500 mg 4 times daily initially (for the first 2-3 days), then 750-1000 mg 4 times daily. Maximum: 8 g/day for the first 48-72 hours. Maintenance 4-4.5 g/day. Take with food if GI upset occurs.",
        "before_taking": "Tell your doctor if you have kidney or liver disease, myasthenia gravis, or a history of seizures. Avoid alcohol. Use caution when driving until you know how this medicine affects you.",
    },
    "tizanidine": {
        "description": "Tizanidine (Zanaflex) is a short-acting centrally acting alpha-2 adrenergic agonist used as a muscle relaxant to treat spasticity associated with multiple sclerosis, spinal cord injury, or stroke.",
        "uses": "Tizanidine is indicated for the management of increased muscle tone (spasticity) associated with multiple sclerosis, spinal cord injury, or other spastic conditions. It reduces spasticity by inhibiting motor neurons at the spinal cord level.",
        "warnings": "Risk of hypotension, including orthostatic hypotension and syncope — especially with the first dose or with dose increases. Hepatotoxicity: obtain liver function tests at baseline, 1, 3, and 6 months. Risk of QT prolongation and sedation. Tizanidine inhibited by fluvoxamine and ciprofloxacin — contraindicated combinations (major increase in tizanidine plasma levels). Tizanidine is a Schedule V controlled substance in some states; has abuse potential. Abrupt withdrawal can cause rebound hypertension and tachycardia.",
        "side_effects": "Common: drowsiness, dizziness, dry mouth, asthenia, hypotension, constipation, urinary tract infection. Serious: liver toxicity (rare), hallucinations, hypotension/syncope.",
        "dosage": "Start 2 mg orally once daily; increase by 2-4 mg per dose at 6-8 hour intervals as needed; max 36 mg/day (3 doses). Tablets and capsules not bioequivalent when administered with food — choose one formulation and stick to it (food or fasted) consistently.",
        "before_taking": "Do not take fluvoxamine or ciprofloxacin with tizanidine (dangerous drug interaction). Tell your doctor about liver disease, low blood pressure, or kidney problems. Rise slowly from seated or lying position. Do not abruptly stop tizanidine.",
    },
    "risedronate": {
        "description": "Risedronate (Actonel, Atelvia) is a bisphosphonate used to treat and prevent osteoporosis and Paget's disease of bone. It works by inhibiting osteoclast-mediated bone resorption.",
        "uses": "Risedronate is indicated for the treatment and prevention of postmenopausal osteoporosis, glucocorticoid-induced osteoporosis, osteoporosis in men, and Paget's disease of bone.",
        "warnings": "Esophageal reactions: osteonecrosis of the jaw and atypical femoral fractures reported with prolonged use. Must be taken with a full glass of plain water and patients must remain upright for 30 minutes after ingestion. Osteonecrosis of the jaw (ONJ) is rare but serious — maintain dental hygiene. Hypocalcemia must be corrected before initiating therapy.",
        "side_effects": "Common: abdominal pain, dyspepsia, constipation, nausea, diarrhea, headache, arthralgia, myalgia. Serious: esophageal ulceration or stricture (with improper use), ONJ, atypical femoral fractures.",
        "dosage": "Postmenopausal osteoporosis prevention/treatment: 5 mg daily, 35 mg weekly, 75 mg on two consecutive days monthly, or 150 mg monthly. Immediate-release: take first thing in the morning on empty stomach with plain water. Actonel DR (delayed-release): 35 mg weekly taken in the morning immediately after breakfast. Paget's disease: 30 mg once daily for 2 months.",
        "before_taking": "Take with plain water only — no coffee, juice, or mineral water. Remain upright (sitting or standing) for at least 30 minutes after taking. Tell your doctor about esophageal disorders, dental problems, kidney disease, or if you take calcium supplements or antacids.",
    },
    "zoledronic-acid": {
        "description": "Zoledronic acid (Reclast, Zometa) is a potent bisphosphonate administered intravenously for osteoporosis, Paget's disease, and hypercalcemia of malignancy.",
        "uses": "Reclast (5 mg/100 mL IV) is indicated for treatment and prevention of postmenopausal osteoporosis, glucocorticoid-induced osteoporosis, osteoporosis in men, and Paget's disease of bone. Zometa (4 mg/5 mL) is used for hypercalcemia of malignancy, multiple myeloma, and metastatic bone lesions from solid tumors.",
        "warnings": "Ensure adequate hydration before infusion (especially elderly patients). Renal impairment and renal failure can occur — monitor renal function; contraindicated if CrCl <35 mL/min (Reclast) or severe renal impairment (Zometa). Osteonecrosis of the jaw (ONJ) — perform dental exam before initiation. Atypical femoral fractures. Hypocalcemia — supplement with calcium and vitamin D. Musculoskeletal pain (sometimes severe and disabling).",
        "side_effects": "Common: post-dose flu-like symptoms (fever, chills, myalgia, arthralgia — usually within 3 days, diminish with subsequent doses), nausea, fatigue, headache. Serious: renal failure, ONJ, atypical femoral fracture, hypocalcemia.",
        "dosage": "Postmenopausal osteoporosis treatment (Reclast): 5 mg IV over at least 15 minutes once yearly. Prevention (postmenopausal): once every 2 years. Paget's disease: 5 mg IV single dose. Supplement with 1200-1500 mg calcium and 800-1200 IU vitamin D daily. Ensure adequate hydration before infusion.",
        "before_taking": "Tell your doctor about kidney disease, dental problems, low blood calcium, or if you are pregnant. Dental checkup recommended before starting. Adequate hydration is essential before each infusion.",
    },
    "raloxifene": {
        "description": "Raloxifene (Evista) is a selective estrogen receptor modulator (SERM) used to prevent and treat postmenopausal osteoporosis and to reduce the risk of invasive breast cancer in postmenopausal women with osteoporosis or high breast cancer risk.",
        "uses": "Raloxifene is indicated for the treatment and prevention of postmenopausal osteoporosis and for the reduction in risk of invasive breast cancer in postmenopausal women with osteoporosis or at high risk for invasive breast cancer. It has estrogen-agonist activity in bone (reduces bone loss) and estrogen-antagonist activity in breast and uterus.",
        "warnings": "FDA BOXED WARNING: Deep vein thrombosis (DVT) and pulmonary embolism (PE) have occurred — discontinue at least 72 hours before and during prolonged immobilization (surgery, prolonged bed rest). Fatal stroke risk increased in women with documented coronary heart disease or high risk of coronary events. Do not use in women who are pregnant or could become pregnant. Does not relieve hot flashes and may increase their frequency and severity.",
        "side_effects": "Common: hot flashes, leg cramps, peripheral edema, arthralgia, sweating, flu syndrome. Serious: VTE (DVT, PE), fatal stroke, retinal vein occlusion.",
        "dosage": "One 60 mg tablet orally once daily. May be taken without regard to meals. Supplement with calcium (1000-1500 mg/day) and vitamin D (400-800 IU/day).",
        "before_taking": "Tell your doctor about any history of blood clots, cardiovascular disease, or if you smoke. Avoid immobility during travel — do exercises to prevent clots. Not for women who may become pregnant.",
    },
    "calcitonin": {
        "description": "Calcitonin-salmon (Miacalcin, Fortical) is available as a nasal spray and injectable formulation. It is a hormone that inhibits osteoclast activity and is used for postmenopausal osteoporosis and Paget's disease.",
        "uses": "Nasal calcitonin is indicated for the treatment of postmenopausal osteoporosis in women more than 5 years post-menopause, in combination with adequate calcium and vitamin D intake. Injectable calcitonin is used for Paget's disease of bone and hypercalcemia (as a short-term supplement when more potent agents are not available).",
        "warnings": "Due to possible association with malignancy in long-term studies, calcitonin should be used only when other treatments are not appropriate. Nasal: rhinitis, nosebleed, and nasal irritation may occur; alternate nostrils daily. Anaphylaxis and allergic reactions reported. Hypocalcemia is a risk with injectable formulation.",
        "side_effects": "Nasal: rhinitis, nosebleed, nasal irritation. Injectable: nausea (common at injection site), facial flushing, headache, dizziness. Rare: anaphylaxis.",
        "dosage": "Postmenopausal osteoporosis (nasal): 200 IU (1 spray) intranasally once daily, alternating nostrils. Paget's disease (injectable): 100 IU subcutaneous or IM daily (can reduce to 50 IU/day or 100 IU 3 times/week once stabilized). Supplement calcium and vitamin D.",
        "before_taking": "Tell your doctor about salmon allergy (calcitonin-salmon). Alternate nasal spray nostrils daily. Supplement with calcium and vitamin D during treatment.",
    },
    "estradiol": {
        "description": "Estradiol (Estrace, Vivelle-Dot, Divigel, Climara) is a form of estrogen used for menopausal hormone therapy and other conditions. Available in oral tablets, transdermal patches, topical gel/spray, vaginal rings, and vaginal cream/tablet/suppository formulations.",
        "uses": "Estradiol is indicated for treatment of moderate-to-severe vasomotor symptoms (hot flashes) associated with menopause, vulval and vaginal atrophy (genitourinary syndrome of menopause), hypoestrogenism due to hypogonadism, castration, or primary ovarian failure, and prevention of postmenopausal osteoporosis. Estradiol 17-beta (Bijuva, Bijuve) is available in combined oral formulations.",
        "warnings": "FDA BOXED WARNINGS: Cardiovascular and other risks: estrogens with or without progestins should not be used to prevent cardiovascular disease or dementia. Endometrial cancer: unopposed estrogen increases risk in women with a uterus — add progestin to reduce risk. Breast cancer risk increased with estrogen-progestin combinations. VTE and pulmonary embolism risk increased. Stroke risk. Dementia: estrogen-alone use increased risk of probable dementia in postmenopausal women ≥65 years (WHIMS study).",
        "side_effects": "Common: breast tenderness/pain, headache, nausea, bloating, edema, vaginal discharge. Serious: VTE, stroke, breast cancer, endometrial cancer (with unopposed use), gallbladder disease.",
        "dosage": "Vasomotor symptoms (oral Estrace): 1-2 mg/day continuously or cyclically. Transdermal patches: 0.025-0.1 mg/day per patch; change every 3.5-7 days depending on product. Topical gel (Divigel 0.1%): 0.25-1 g once daily. Vaginal cream (Estrace): 2-4 g daily initially, then 1 g 1-3 times weekly for maintenance. Use lowest effective dose for shortest duration consistent with treatment goals.",
        "before_taking": "Tell your doctor about personal or family history of breast cancer, blood clots, stroke, liver disease, or endometrial cancer. Do not smoke during estrogen therapy. Women with a uterus should take progestogen to prevent endometrial cancer.",
    },
    "progesterone": {
        "description": "Progesterone (Prometrium, Crinone, Endometrin) is a natural progestogen hormone available in oral capsules, vaginal gel, and vaginal inserts. It is used as part of hormone replacement therapy and in assisted reproduction.",
        "uses": "Oral progesterone (Prometrium) is used to prevent endometrial hyperplasia in postmenopausal women with a uterus who are taking conjugated equine estrogen. Vaginal progesterone (Crinone, Endometrin) is used in assisted reproductive technology (ART) for luteal phase support and prevention of preterm birth in certain high-risk women.",
        "warnings": "Contains peanut oil (Prometrium) — contraindicated in patients with peanut allergy. Risk of cardiovascular disease, breast cancer, dementia in combined hormone therapy (estrogen + progestin) based on WHI data. Progesterone may impair mental alertness and coordination — take at bedtime. Medroxyprogesterone acetate (a synthetic progestin) is not equivalent to natural micronized progesterone.",
        "side_effects": "Common (oral): drowsiness, dizziness, bloating, breast tenderness, headache, mood changes. Vaginal: vaginal discharge, local irritation.",
        "dosage": "Endometrial hyperplasia prevention: 200 mg at bedtime for 12 days per 28-day cycle. ART/luteal support (vaginal gel 8%): 90 mg once daily. Preterm birth prevention (vaginal suppository): 90-200 mg daily from 16-24 weeks to 36 weeks.",
        "before_taking": "Tell your doctor about peanut allergy (Prometrium contains peanut oil), liver disease, blood clotting disorders, or history of breast or endometrial cancer. Take oral form at bedtime due to drowsiness.",
    },
    "testosterone": {
        "description": "Testosterone (AndroGel, Testim, Axiron, Depo-Testosterone, Natesto) is a controlled substance (Schedule III) androgen/anabolic steroid used for hypogonadism and delayed puberty in males.",
        "uses": "Testosterone is indicated for replacement therapy in conditions associated with a deficiency or absence of endogenous testosterone: primary hypogonadism (testicular failure) and hypogonadotropic hypogonadism (inadequate hypothalamic/pituitary function). Products include transdermal gel/solution, buccal system, nasal gel, injectable (cypionate, enanthate), and implantable pellets.",
        "warnings": "Contraindicated in prostate or breast carcinoma. FDA BOXED WARNING: Topical testosterone has potential for secondary exposure to children and women — keep children and women away from application sites. Risk of serious cardiovascular events. Edema with or without congestive heart failure may occur. Sleep apnea risk. Polycythemia (elevated RBC/hemoglobin/hematocrit). Drug abuse and dependence: testosterone is a Schedule III controlled substance.",
        "side_effects": "Common: acne, increased libido, oily skin, injection site pain (injectable), headache, polycythemia. Serious: cardiovascular events, hepatotoxicity (oral forms), priapism, virilization in women/children via secondary exposure, testicular atrophy, infertility.",
        "dosage": "Gel (AndroGel 1%): 50-100 mg/day topically to shoulders/upper arms/abdomen. Cypionate/enanthate (injectable): 50-400 mg IM every 2-4 weeks. Natesto (nasal): 11 mg (2 pump actuations per nostril) 3 times daily. Dose adjusted based on serum testosterone levels.",
        "before_taking": "Keep women and children away from skin contact with application sites. Tell your doctor about prostate issues, cardiovascular disease, sleep apnea, or polycythemia. Monitor PSA, hematocrit, and testosterone levels regularly.",
    },
    "ethinyl-estradiol-norethindrone": {
        "description": "Ethinyl estradiol/norethindrone (Ortho-Novum, Brevicon, Loestrin, Microgestin, Necon) is a combined oral contraceptive (COC) containing an estrogen and a progestin.",
        "uses": "Combined oral contraceptives are used for pregnancy prevention. Certain formulations have additional indications for the treatment of acne vulgaris, endometriosis (some products), and dysmenorrhea. They work primarily by inhibiting ovulation and secondarily by changes to cervical mucus and endometrial lining.",
        "warnings": "FDA BOXED WARNING: Cigarette smoking increases the risk of serious cardiovascular events from combination oral contraceptive use — this risk increases with age, particularly in women over 35, and with heavy smoking. Contraindicated in women with: uncontrolled hypertension, cardiovascular disease or history of cardiovascular events, thromboembolic disorders, liver disease, unexplained vaginal bleeding, breast or reproductive organ malignancies, migraine with aura. Risk of VTE, stroke, MI.",
        "side_effects": "Common: nausea, breakthrough bleeding/spotting, breast tenderness, headache, decreased libido, mood changes. Serious: VTE, stroke, myocardial infarction, hypertension, hepatic adenoma (rare), cholelithiasis.",
        "dosage": "Take one active tablet at the same time daily for 21-28 days. 28-day packs include 7 hormone-free placebo tablets for cycle continuity. Begin on day 1 of period or first Sunday after period starts (Sunday start). Use backup contraception for the first 7 days if not starting on day 1 of cycle. Missed pills: follow prescribing information for single vs. consecutive missed pills.",
        "before_taking": "Tell your doctor if you smoke, have high blood pressure, migraines with aura, blood clots, liver disease, or breast cancer. Use backup contraception when also using certain antibiotics (rifampin) or anticonvulsants. Take at the same time daily to maximize effectiveness.",
    },
    "levonorgestrel": {
        "description": "Levonorgestrel is a synthetic progestin used in emergency contraception (Plan B, Next Choice), low-dose oral contraceptive pills, and intrauterine devices (Mirena, Kyleena, Liletta, Skyla).",
        "uses": "Emergency contraception: levonorgestrel 1.5 mg is used to reduce the chance of pregnancy after unprotected sex or contraceptive failure. Most effective when taken as soon as possible (within 72 hours; can be used up to 120 hours). Levonorgestrel IUDs (Mirena, Kyleena, Liletta, Skyla) provide long-term contraception (3-8 years depending on product) and Mirena also treats heavy menstrual bleeding.",
        "warnings": "Emergency contraception: not intended for routine use and not an abortifacient — will not end an established pregnancy. Less effective in women with body weight >165-175 lbs (may consider ulipristal acetate or copper IUD instead). IUD insertion: risk of PID, especially in first 20 days. Ectopic pregnancy must be excluded before IUD insertion if patient has risk factors.",
        "side_effects": "Emergency contraception: nausea, vomiting, headache, fatigue, abdominal pain, irregular bleeding. IUD: irregular spotting in first 3-6 months, then oligomenorrhea/amenorrhea; dysmenorrhea; cramping at insertion; expulsion (rare).",
        "dosage": "Emergency contraception (Plan B): 1.5 mg as a single dose (or 0.75 mg × 2 doses 12 hours apart). Take as soon as possible after unprotected sex; most effective within 24 hours, decreases after 72 hours. IUD: inserted by healthcare professional; duration 3-8 years depending on product.",
        "before_taking": "Emergency contraception: tell your doctor if you take medications that may reduce effectiveness (rifampin, carbamazepine, phenytoin). IUD: discuss with your provider about eligibility; return if severe pain, fever, or unusual discharge occurs after insertion.",
    },
    "norethindrone": {
        "description": "Norethindrone (Camila, Jolivette, Nora-BE, Heather) is a progestin-only oral contraceptive ('mini-pill'). It is also used in higher doses (norethindrone acetate, Aygestin) for endometriosis and abnormal uterine bleeding.",
        "uses": "Norethindrone 0.35 mg (mini-pill) is used for contraception, especially suitable for breastfeeding women (does not suppress lactation), women who cannot use estrogen (smokers >35, history of VTE, migraines with aura). Norethindrone acetate 5 mg (Aygestin) is used for endometriosis, abnormal uterine bleeding, and secondary amenorrhea.",
        "warnings": "Mini-pill requires strict adherence (same time within 3-hour window each day). If taken >3 hours late, use backup contraception for 48 hours. Less effective than combined OCs for preventing pregnancy. Small increased risk of ectopic pregnancy. Irregular bleeding patterns are common. Norethindrone acetate (Aygestin): thromboembolic risk; contraindicated with active VTE, thrombophlebitis, or cerebrovascular disease.",
        "side_effects": "Common: irregular periods, spotting, amenorrhea, breast tenderness, headache, nausea, acne, mood changes. Less common with norethindrone than with combined OCs: VTE risk not significantly elevated.",
        "dosage": "Mini-pill: 0.35 mg once daily every day (no hormone-free interval) — take at the same time each day within a 3-hour window. Norethindrone acetate (endometriosis): 5 mg/day for 6-9 months. Abnormal uterine bleeding: 2.5-10 mg/day for 5-10 days in the second half of the menstrual cycle.",
        "before_taking": "Mini-pill must be taken at the same time every day (within 3 hours). Tell your doctor about liver disease, breast cancer, or history of ectopic pregnancy. Use backup contraception if you are late taking a pill by more than 3 hours.",
    },
    "clomiphene": {
        "description": "Clomiphene citrate (Clomid, Serophene) is a selective estrogen receptor modulator (SERM) used to induce ovulation in women with anovulatory infertility, including polycystic ovary syndrome (PCOS).",
        "uses": "Clomiphene is used to induce ovulation in women with anovulatory infertility who want to become pregnant, particularly in PCOS and unexplained infertility. It works by blocking hypothalamic estrogen receptors, increasing FSH and LH secretion and stimulating ovarian follicle development. It may also be used off-label in men with idiopathic oligospermia.",
        "warnings": "Multiple gestation risk (twins 5-7%, triplets or more <1%) — patients should be aware of this risk. Ovarian hyperstimulation syndrome (OHSS): can range from mild ovarian enlargement to severe ascites, hypovolemia, and thromboembolism. Ovarian cysts may enlarge — monitor with ultrasound. Visual disturbances (blurring, spots) reported — discontinue if visual symptoms occur. No more than 3-6 cycles typically recommended.",
        "side_effects": "Common: hot flashes, abdominal discomfort, bloating, breast tenderness, nausea, headache, visual disturbances. Serious: OHSS, multiple gestations, ovarian cysts.",
        "dosage": "Initiate with 50 mg/day orally for 5 days starting on day 3, 4, or 5 of cycle. If no ovulation, increase to 100 mg/day for 5 days in the next cycle. Maximum 150 mg/day; do not exceed 6 cycles. Monitor with ultrasound and serum progesterone.",
        "before_taking": "Tell your doctor about liver disease, ovarian cysts, abnormal uterine bleeding, or thyroid/adrenal disease. Pregnancy must be excluded before each treatment cycle. Monitor for signs of OHSS (abdominal pain, bloating, weight gain).",
    },
    "misoprostol": {
        "description": "Misoprostol (Cytotec) is a synthetic prostaglandin E1 analog with uterotonic and gastric cytoprotective properties. It is used for gastric ulcer prevention and in obstetric/gynecologic applications.",
        "uses": "Misoprostol is FDA-approved for the prevention of NSAID-induced gastric ulcers in patients at high risk. Off-label/obstetric uses include cervical ripening before labor induction, treatment of postpartum hemorrhage, management of early pregnancy loss, and (in combination with mifepristone) medical termination of pregnancy up to 10 weeks.",
        "warnings": "CONTRAINDICATED in pregnant women for ulcer treatment (Cytotec label) due to risk of abortion, premature birth, or birth defects. Uterine rupture, particularly with previous uterine surgery — obstetric use requires close monitoring. NOT for use as an elective abortifacient outside medical supervision. Uterine hyperstimulation and fetal heart rate abnormalities can occur with obstetric use.",
        "side_effects": "Common: diarrhea, abdominal pain, nausea, cramping (including uterine), fever (with vaginal/sublingual dosing). Serious: uterine rupture, uterine hyperstimulation, severe diarrhea.",
        "dosage": "NSAID ulcer prevention: 200 mcg 4 times daily with food (take with meals and at bedtime); reduce to 100 mcg if not tolerated. Obstetric uses vary widely by indication and route (oral, vaginal, sublingual, buccal) — consult institutional protocols.",
        "before_taking": "Do not use for gastric ulcer prevention if pregnant. Tell your doctor about prior uterine surgery (including C-section) before any obstetric use. Significant diarrhea and cramping are expected with initial doses.",
    },
    "oxytocin": {
        "description": "Oxytocin (Pitocin) is a synthetic nonapeptide identical to the natural neurohypophyseal hormone. It is administered IV or IM in hospital settings to stimulate uterine contractions for labor induction or augmentation and to control postpartum bleeding.",
        "uses": "Oxytocin IV is indicated for the elective induction of labor in selected patients at term, for the stimulation or reinforcement of labor when clinically indicated, adjunctive therapy in abortion, and for the control of postpartum hemorrhage (postpartum and post-abortion uterine atony).",
        "warnings": "IV oxytocin must be administered only by trained healthcare professionals in a hospital setting with continuous fetal and uterine monitoring. Uterine hyperstimulation (tetanic contraction) and fetal distress can occur with excessive doses. Antidiuretic effect: water intoxication and severe hyponatremia reported with prolonged IV oxytocin infusion, particularly with excessive fluid intake. Oxytocin is not indicated for elective labor induction without medical necessity. Risk of neonatal hyperbilirubinemia.",
        "side_effects": "Maternal: nausea, vomiting, uterine hyperstimulation, cardiovascular effects (bradycardia, PVCs, hypotension), water intoxication. Fetal: bradycardia, fetal distress. Neonatal: hyperbilirubinemia.",
        "dosage": "Labor induction: 0.5-1 mU/min IV, increased by 1-2 mU/min every 30-60 minutes as needed. Maximum: 20-40 mU/min. Postpartum hemorrhage: 10-40 units in 1000 mL IV fluid; or 10 units IM after placenta delivery. Administered only in hospital by trained professionals.",
        "before_taking": "Hospital use only. Used under continuous medical supervision. Patient must inform provider of all previous uterine surgeries, abnormal fetal position, or complications.",
    },
    "desiccated-thyroid": {
        "description": "Desiccated thyroid (Armour Thyroid, Nature-Throid, WP Thyroid, NP Thyroid) is a thyroid hormone supplement derived from desiccated porcine thyroid glands, containing both thyroxine (T4) and triiodothyronine (T3).",
        "uses": "Desiccated thyroid is used for replacement or supplemental therapy in patients with primary hypothyroidism, secondary (pituitary) or tertiary (hypothalamic) hypothyroidism, and subclinical hypothyroidism. Some patients prefer it over synthetic levothyroxine for perceived symptomatic benefit from the T3 component.",
        "warnings": "Thyroid hormones can precipitate or aggravate cardiac arrhythmias — use with caution in patients with cardiovascular disease. Not for use as a weight loss treatment — can cause serious or life-threatening toxicity if used in euthyroid patients. Monitor TSH levels; maintain TSH in normal range. Contains porcine-derived material — inform patients with concerns about pork products.",
        "side_effects": "Symptoms of over-treatment: palpitations, angina, arrhythmias, tachycardia, hypertension, weight loss, tremor, nervousness, heat intolerance, sweating, diarrhea, menstrual irregularities. Under-treatment: fatigue, cold intolerance, constipation, weight gain.",
        "dosage": "Initial: 15-30 mg/day; increase by 15 mg every 2-4 weeks. Usual maintenance: 60-120 mg/day. Elderly or cardiac patients: lower starting doses (7.5-15 mg/day) with gradual titration. Doses are in mg (grains); 60 mg ≈ 1 grain = ~100 mcg levothyroxine equivalence.",
        "before_taking": "Tell your doctor about heart disease, adrenal or pituitary disorders, or diabetes. Take on an empty stomach, 30-60 minutes before breakfast. Separate from calcium, iron, and antacids by at least 4 hours. Do not switch between thyroid hormone formulations without re-checking TSH.",
    },
    "mupirocin": {
        "description": "Mupirocin (Bactroban) is a topical antibiotic with bactericidal activity against Staphylococcus aureus (including MRSA) and Streptococcus pyogenes. Available as cream and ointment.",
        "uses": "Mupirocin topical ointment (2%) is indicated for the treatment of impetigo caused by S. aureus and S. pyogenes. Mupirocin nasal ointment (2%) is used for eradicating MRSA nasal carriage in adults to reduce infection risk in institutional settings.",
        "warnings": "Do not use in the eyes. Not for systemic infections. May develop resistance with prolonged use. Topical absorption is minimal; systemic effects are rare. Mupirocin ointment contains polyethylene glycol — avoid in patients with renal impairment and damaged skin (potential for systemic absorption of PEG).",
        "side_effects": "Topical: burning, stinging, itching at application site, contact dermatitis (rare). Nasal: nasal burning, stinging, rhinitis, headache, altered taste.",
        "dosage": "Impetigo: apply small amount to affected area 3 times daily for 3-5 days; cover with gauze if desired. Nasal MRSA decolonization: apply ½ of single-use tube to each nostril twice daily for 5 days; close nostrils by pressing sides of nose for 1 minute.",
        "before_taking": "Avoid getting mupirocin in the eyes or on mucous membranes. Tell your doctor if you have renal impairment (avoid ointment on large open skin wounds due to PEG content). Complete the full course of treatment.",
    },
    "bacitracin": {
        "description": "Bacitracin is a topical antibiotic with activity primarily against gram-positive bacteria. Available as ointment and cream, often in combination with neomycin and polymyxin B (Neosporin, Triple Antibiotic).",
        "uses": "Bacitracin topical is used to prevent minor skin infections from cuts, scrapes, and burns. Combination products with neomycin and polymyxin B provide broader-spectrum coverage. Also available as ophthalmic ointment for superficial ocular infections. Injectable bacitracin (rarely used) is limited to certain serious gram-positive infections.",
        "warnings": "For external use only — do not use in the eyes (topical cream/ointment) or over large skin areas. Do not use longer than 1 week for self-care. Neomycin (in combination products) is a common cause of allergic contact dermatitis. Systemic bacitracin injection carries nephrotoxicity risk.",
        "side_effects": "Topical: mild irritation, stinging, contact dermatitis (especially neomycin component). Ophthalmic: mild irritation, burning.",
        "dosage": "Topical: apply thin layer to affected area 1-3 times daily. Clean and cover wound as needed. Ophthalmic: apply ½-inch ribbon to conjunctival sac every 3-4 hours.",
        "before_taking": "Do not apply to deep wounds, animal bites, or serious burns without consulting a doctor. If skin reaction occurs (rash, itching, redness), discontinue and consult a doctor.",
    },
    "adapalene": {
        "description": "Adapalene (Differin) is a third-generation topical retinoid used for acne vulgaris. The 0.1% gel/cream formulation is available OTC; the 0.3% gel is prescription-strength.",
        "uses": "Adapalene is indicated for the topical treatment of acne vulgaris in patients ≥12 years (0.1% OTC) and ≥9 years (0.3% Rx). It modulates cell differentiation and keratinization, preventing comedone formation and reducing microcomedone precursors.",
        "warnings": "Do not apply to eczematous, abraded, sunburned, or windburned skin. Avoid contact with eyes, lips, and nasal mucosa. Significant sun sensitivity — use sunscreen and avoid prolonged sun exposure. Initial worsening of acne ('purging') is normal and usually improves after 4-8 weeks. Retinoids are teratogenic — avoid during pregnancy. Not for use on skin with rosacea.",
        "side_effects": "Common: erythema, scaling, dryness, peeling, burning sensation (especially in first 2-4 weeks, then usually improves). Photosensitivity.",
        "dosage": "Apply a thin layer to the entire affected area (face, back) once daily at bedtime after washing and drying skin. Avoid the eye area, lips, and nostrils. Do not apply more than once per day — more frequent use increases irritation without added benefit. Effects typically seen in 8-12 weeks.",
        "before_taking": "Tell your doctor if you are pregnant or planning pregnancy — retinoids are teratogenic. Use sunscreen daily. Do not use with other drying agents or harsh cleansers during initial weeks of therapy.",
    },
    "benzoyl-peroxide": {
        "description": "Benzoyl peroxide (Clearasil, PanOxyl, Benzac) is an OTC and prescription topical antibacterial and keratolytic agent used for acne vulgaris. Available in concentrations from 2.5% to 10%.",
        "uses": "Benzoyl peroxide is used to treat mild to moderate acne vulgaris. It works by releasing free-radical oxygen to kill C. acnes (Propionibacterium acnes) bacteria and has keratolytic activity. It does not induce bacterial resistance. Often used in combination with topical retinoids or antibiotics.",
        "warnings": "Do not use on broken, irritated, or sunburned skin. May bleach hair, clothing, or bed linen — keep away from these materials. Skin drying and peeling are expected. May cause allergic contact dermatitis in susceptible individuals. Higher concentrations (10%) are more irritating with minimal additional efficacy over 2.5-5%.",
        "side_effects": "Common: dryness, peeling, redness, burning, and stinging (especially early in treatment). Rare: allergic contact dermatitis (true allergy), more severe irritation.",
        "dosage": "Apply to affected acne-prone areas (entire face, back, etc.) once or twice daily after washing with mild cleanser. Start with lower concentrations (2.5-5%) to minimize irritation. OTC concentrations up to 10%.",
        "before_taking": "Avoid contact with eyes, mouth, and nose. Use a gentle cleanser and moisturizer to help manage dryness. Do not combine with irritating products (other retinoids, alcohol-based toners) at the same time of day.",
    },
    "timolol": {
        "description": "Timolol ophthalmic (Timoptic, Betimol, Istalol) is a non-selective beta-adrenergic blocking agent used as eye drops for the treatment of ocular hypertension and open-angle glaucoma.",
        "uses": "Timolol ophthalmic is indicated for the treatment of elevated intraocular pressure (IOP) in patients with ocular hypertension or open-angle glaucoma. It reduces IOP by decreasing the production of aqueous humor. It may be used alone or in combination with other ophthalmic agents.",
        "warnings": "Systemic beta-blockade can occur with ophthalmic timolol — respiratory effects (bronchospasm in patients with asthma or COPD), cardiovascular effects (bradycardia, heart block, hypotension). Masked hypoglycemia symptoms in diabetics. Contraindicated in patients with sinus bradycardia, AV block greater than first degree, cardiogenic shock, overt heart failure, or bronchial asthma. Should not be abruptly discontinued in patients with coronary artery disease.",
        "side_effects": "Ocular: burning, stinging, redness, reduced tear secretion, superficial punctate keratitis. Systemic (from absorption): bradycardia, hypotension, bronchospasm, fatigue, depression, impotence.",
        "dosage": "Standard formulation: 1 drop (0.25% or 0.5% solution) in affected eye(s) twice daily. Timoptic-XE (gel-forming): 1 drop once daily. Istalol (gel): 1 drop once daily in the morning. Nasolacrimal occlusion (pressing the inner corner of eye for 1-2 minutes) reduces systemic absorption.",
        "before_taking": "Tell your doctor about asthma, COPD, heart problems, diabetes, or myasthenia gravis. Use nasolacrimal occlusion technique. Do not use soft contact lenses within 15 minutes of instillation.",
    },
    "latanoprost": {
        "description": "Latanoprost (Xalatan) is a prostaglandin F2α analog used as eye drops to lower intraocular pressure in open-angle glaucoma and ocular hypertension.",
        "uses": "Latanoprost is indicated for the reduction of elevated intraocular pressure in patients with open-angle glaucoma or ocular hypertension. It works by increasing the uveoscleral outflow of aqueous humor.",
        "warnings": "May cause permanent changes in iris color (increased brown pigmentation) and darkening of periocular skin — inform patients before initiating therapy. Eyelash changes (growth, thickening, darkening, lengthening) may occur. Use with caution in patients with aphakia, pseudophakia, or history of ocular herpes simplex. Macular edema (including CME) reported. If only one eye is being treated, apply only to that eye — systemic exposure is minimal but periorbital effects are localized.",
        "side_effects": "Ocular: iris pigmentation change (permanent), eyelash growth, blurring, burning/stinging, conjunctival hyperemia, punctate keratitis, blepharitis, macular edema. Systemic: upper respiratory tract infection, cold/flu, chest pain (rare).",
        "dosage": "1 drop in the affected eye(s) once daily in the evening. Store unopened bottles in refrigerator; once opened, may keep at room temperature for up to 6 weeks. Do not exceed once-daily dosing — more frequent dosing may reduce IOP-lowering effect.",
        "before_taking": "Inform patients about the possibility of permanent iris color change before initiating. Remove contact lenses before instillation; wait 15 minutes before reinserting. Apply in the evening for maximum IOP reduction.",
    },
    "bimatoprost": {
        "description": "Bimatoprost (Lumigan, Latisse) is a prostaglandin analog. Lumigan ophthalmic solution is used for open-angle glaucoma and ocular hypertension. Latisse is approved for hypotrichosis of the eyelashes.",
        "uses": "Bimatoprost 0.01-0.03% ophthalmic (Lumigan) is indicated for the reduction of elevated IOP in open-angle glaucoma and ocular hypertension. Latisse 0.03% is approved for the treatment of inadequate eyelashes (hypotrichosis).",
        "warnings": "May permanently darken the iris, periocular skin, and eyelashes. Macular edema has been reported. May cause or worsen pigmentation of the iris, periorbital tissue, and eyelashes with long-term use. For Latisse (eyelash application only to the upper eyelid margin with the applicator — not lower eyelid). Contamination of dropper tip should be avoided.",
        "side_effects": "Ocular: conjunctival hyperemia (redness), eyelash growth and darkening, iris and periorbital pigmentation, pruritus, sensation of foreign body. Systemic: rare.",
        "dosage": "Glaucoma (Lumigan 0.01%): 1 drop in affected eye(s) once daily in the evening. Eyelash hypotrichosis (Latisse): apply 1 drop to upper eyelid margin using sterile applicator daily in the evening.",
        "before_taking": "Inform patients about permanent pigmentation changes. Remove contacts before use; reinstate after 15 minutes. Latisse is not applied to the lower eyelid and should not enter the eye.",
    },
    "brimonidine": {
        "description": "Brimonidine (Alphagan P) is a selective alpha-2 adrenergic agonist used as ophthalmic drops to lower intraocular pressure in open-angle glaucoma and ocular hypertension.",
        "uses": "Brimonidine ophthalmic is indicated for the lowering of IOP in patients with open-angle glaucoma or ocular hypertension. It reduces aqueous humor production and increases uveoscleral outflow. It is often used as a second-line agent or in combination with other glaucoma medications.",
        "warnings": "Oral absorption can cause cardiovascular and CNS effects, including hypotension, bradycardia, sedation, and respiratory depression — avoid in infants and young children (risk of CNS depression and apnea). May cause fatigue and drowsiness. Vasovagal attacks reported. Rebound IOP elevation upon discontinuation.",
        "side_effects": "Ocular: conjunctival hyperemia, burning/stinging, corneal staining, foreign body sensation, eyelid erythema, increased pigmentation. Systemic: fatigue, drowsiness, dry mouth, headache, hypotension (from systemic absorption).",
        "dosage": "1 drop in affected eye(s) 3 times daily, approximately 8 hours apart. Preservative-free formulations also available.",
        "before_taking": "Avoid in infants and young children (systemic absorption can cause CNS depression). Use cautiously in patients with severe cardiovascular disease. Remove contacts before instillation; wait 15 minutes.",
    },
    "ofloxacin-ophthalmic": {
        "description": "Ofloxacin ophthalmic (Ocuflox) is a fluoroquinolone antibiotic eye drop used for bacterial conjunctivitis and corneal ulcers.",
        "uses": "Ofloxacin ophthalmic is indicated for the treatment of bacterial conjunctivitis caused by susceptible organisms including S. aureus, S. epidermidis, Streptococcus pneumoniae, Haemophilus influenzae, Serratia marcescens, and Pseudomonas aeruginosa. Also used for corneal ulcers.",
        "warnings": "Not for injection or systemic use. Do not wear contact lenses while using for bacterial conjunctivitis. Do not touch the dropper tip to any surface. Hypersensitivity reactions can occur — discontinue if severe.",
        "side_effects": "Common: transient ocular burning/discomfort, stinging, redness, photophobia, tearing. Rare: corneal precipitates, lid margin crusting.",
        "dosage": "Bacterial conjunctivitis: Days 1-2: 1-2 drops in affected eye(s) every 2-4 hours while awake. Days 3-7: 1-2 drops 4 times daily. Corneal ulcer: more intensive dosing — follow prescriber instructions.",
        "before_taking": "Do not wear contact lenses during treatment for conjunctivitis. Avoid contaminating the dropper. Wash hands before use.",
    },
    "tobramycin-ophthalmic": {
        "description": "Tobramycin ophthalmic (Tobrex) is an aminoglycoside antibiotic eye drop/ointment used for bacterial conjunctivitis and other external ocular infections.",
        "uses": "Tobramycin ophthalmic is indicated for the treatment of external infections of the eye and adnexa caused by susceptible bacteria including Staphylococcus, Streptococcus, Pseudomonas aeruginosa, Klebsiella, Haemophilus, and Acinetobacter species. Combined tobramycin/dexamethasone (TobraDex) is used for ocular infections with an inflammatory component.",
        "warnings": "Prolonged use may cause overgrowth of non-susceptible organisms including fungi. Do not use contact lenses during treatment. Not for systemic or injectable use. Cross-sensitivity with other aminoglycosides is possible.",
        "side_effects": "Common: transient burning, stinging, itching, lid swelling, conjunctival erythema. Rare: hypersensitivity reactions.",
        "dosage": "Mild-moderate infection: 1-2 drops every 4 hours. Severe infection: 2 drops every 30-60 minutes initially, reduce when improvement occurs. Ointment: ½-inch ribbon 2-3 times daily.",
        "before_taking": "Remove contact lenses before instillation; wait 15 minutes before reinserting. Do not wear contacts during treatment. Complete the full prescribed course.",
    },
    "multivitamin": {
        "description": "Multivitamins (Centrum, One A Day, Flintstones, MVI) are dietary supplement tablets or capsules containing a combination of vitamins and sometimes minerals, designed to provide nutritional support.",
        "uses": "Multivitamins supplement dietary intake to prevent nutritional deficiencies. They are used as a preventive supplement in healthy individuals with inadequate dietary intake, during pregnancy (prenatal vitamins), in patients with malabsorption syndromes, following bariatric surgery, and in specific populations with increased requirements (elderly, vegetarians/vegans).",
        "warnings": "Do not exceed the recommended dose. Vitamins A, D, E, and K are fat-soluble and can accumulate to toxic levels in excess. Iron-containing multivitamins can be fatal to small children in overdose — store away from children. Taking large amounts of niacin can cause skin flushing, liver toxicity. Do not take as a substitute for prescribed medications.",
        "side_effects": "Generally well tolerated at recommended doses. Common with iron-containing products: constipation, nausea, dark stools. Excessive dose of fat-soluble vitamins can cause toxicity (vitamin A: liver damage; vitamin D: hypercalcemia).",
        "dosage": "Standard adult multivitamin: take 1 tablet daily with food. Prenatal vitamins: 1 daily throughout pregnancy and breastfeeding. Pediatric chewable: per label for age-appropriate dose. Take with food to reduce nausea from iron.",
        "before_taking": "Separate from certain antibiotics (fluoroquinolones, tetracyclines) and thyroid medication by at least 2-4 hours (minerals may reduce absorption). Tell your doctor about all supplements you take.",
    },
    "leflunomide": {
        "description": "Leflunomide (Arava) is a disease-modifying antirheumatic drug (DMARD) that inhibits dihydroorotate dehydrogenase, reducing lymphocyte proliferation and inflammation in rheumatoid arthritis.",
        "uses": "Leflunomide is indicated for the treatment of active rheumatoid arthritis (RA) to reduce signs and symptoms and slow structural damage. It can be used as monotherapy or in combination with methotrexate (with close monitoring for additional hepatotoxicity).",
        "warnings": "FDA BOXED WARNINGS: Hepatotoxicity, including fatal liver failure, has occurred — monitor liver enzymes regularly and before initiating. Pregnancy: causes major birth defects — contraindicated in pregnancy. Leflunomide's active metabolite (A77 1726) has an extremely long half-life (1-4 weeks); drug elimination procedure (cholestyramine or activated charcoal) required when stopping therapy before pregnancy or before switching to another DMARD.",
        "side_effects": "Common: diarrhea, nausea, headache, rash, alopecia, elevated liver enzymes, hypertension. Serious: hepatotoxicity, serious infections, bone marrow toxicity, interstitial lung disease.",
        "dosage": "Loading dose (optional): 100 mg/day for 3 days; then 20 mg/day. Reduce to 10 mg/day if 20 mg not tolerated. Monitor LFTs every 1-2 months. If hepatotoxicity occurs, discontinue and initiate washout procedure.",
        "before_taking": "Exclude pregnancy before initiating (negative pregnancy test required). Tell your doctor about liver disease, immunodeficiency, or infections. Effective contraception required during treatment and until plasma levels are verified negligible after washout.",
    },
    "tofacitinib": {
        "description": "Tofacitinib (Xeljanz, Xeljanz XR) is a Janus kinase (JAK) inhibitor used for rheumatoid arthritis, psoriatic arthritis, ankylosing spondylitis, and ulcerative colitis.",
        "uses": "Tofacitinib is indicated for moderate-to-severe rheumatoid arthritis (inadequate response to methotrexate), psoriatic arthritis (inadequate response to DMARDs), active ankylosing spondylitis (inadequate response to biologics), and moderate-to-severe ulcerative colitis (inadequate response to TNF blockers).",
        "warnings": "FDA BOXED WARNINGS: Serious infections (bacterial, viral including herpes, fungal, opportunistic) resulting in hospitalization or death — evaluate for TB before initiating. Malignancy including lymphoma and solid tumors. Cardiovascular events (MACE: heart attack, stroke), thrombosis, and increased mortality observed in older patients ≥50 years with ≥1 cardiovascular risk factor in a clinical study with the 10 mg twice-daily dose. Avoid use with biologic DMARDs or potent immunosuppressants. Avoid live vaccines.",
        "side_effects": "Common: upper respiratory infection, nasopharyngitis, diarrhea, headache, hypertension, nausea. Serious: serious infections, malignancy, MACE, DVT/PE, cytopenias.",
        "dosage": "RA and PsA: 5 mg twice daily (or 11 mg XR once daily). UC: 10 mg twice daily for 8 weeks induction, then 5 mg (or 10 mg) twice daily maintenance. UC patients at risk for VTE or MACE: use lowest effective dose. Take without regard to food.",
        "before_taking": "Screen for TB and hepatitis B before initiating. Tell your doctor about history of infections, blood clots, cardiovascular disease, or cancer. Avoid live vaccines during treatment.",
    },
    "erythromycin": {
        "description": "Erythromycin (Erythrocin, E-Mycin, Ery-Tab, Erygel) is a macrolide antibiotic with activity against gram-positive bacteria and some gram-negative organisms. Available in oral (base, ethylsuccinate, stearate), topical, and ophthalmic formulations.",
        "uses": "Erythromycin is indicated for pharyngitis/tonsillitis, community-acquired pneumonia, whooping cough (pertussis), diphtheria, skin and soft tissue infections caused by susceptible organisms, Legionnaires' disease, Mycoplasma pneumonia, Chlamydia trachomatis infections (urethritis, cervicitis, conjunctivitis, pneumonia), nongonococcal urethritis, and syphilis in penicillin-allergic patients. Topical erythromycin is used for acne vulgaris.",
        "warnings": "Hepatotoxicity (cholestatic jaundice, hepatic dysfunction) reported with erythromycin estolate formulation. QT prolongation and cardiac arrhythmias including ventricular tachycardia and torsades de pointes. Significant drug interactions due to CYP3A4 inhibition — contraindicated with terfenadine, astemizole, cisapride, and pimozide. Ototoxicity with high doses. CDAD reported.",
        "side_effects": "Common: nausea, vomiting, abdominal pain, diarrhea (dose-dependent GI upset). Serious: hepatotoxicity (estolate), QT prolongation, torsades de pointes, CDAD, ototoxicity.",
        "dosage": "Adults: 250-500 mg every 6 hours or 500 mg-1 g every 12 hours (depending on formulation and indication). Typical range: 1-4 g/day. Take base and stearate 30 minutes before meals; ethylsuccinate without regard to food. Complete the full course.",
        "before_taking": "Tell your doctor about liver disease, heart rhythm problems, or QT prolongation. Do not take with cisapride, pimozide, or certain antihistamines. Avoid grapefruit juice (inhibits CYP3A4).",
    },
    "eletriptan": {
        "description": "Eletriptan (Relpax) is a selective 5-HT1B/1D serotonin receptor agonist (triptan) used for acute treatment of migraine attacks with or without aura in adults.",
        "uses": "Eletriptan is indicated for the acute treatment of migraine with or without aura in adults. It works by activating serotonin receptors to cause vasoconstriction of intracranial blood vessels and inhibition of neuropeptide release, thereby relieving migraine symptoms.",
        "warnings": "Contraindicated in ischemic coronary artery disease (angina, MI, silent ischemia), coronary artery vasospasm (Prinzmetal's angina), Wolff-Parkinson-White syndrome, other significant cardiovascular disease, peripheral vascular disease, cerebrovascular disease, and hypertension (uncontrolled). Should not be taken within 72 hours of potent CYP3A4 inhibitors (ketoconazole, itraconazole, ritonavir, clarithromycin). Serotonin syndrome risk with other serotonergic drugs. Do not use within 24 hours of another triptan or ergotamine.",
        "side_effects": "Common: nausea, dizziness, somnolence, dry mouth, weakness/fatigue, chest pressure or heaviness (usually non-cardiac). Rare serious: myocardial infarction, stroke, serotonin syndrome.",
        "dosage": "40 mg orally at onset of migraine; may repeat after 2 hours if partial response (max 80 mg/day). For severe migraines unresponsive to 20 mg, 40 mg may be more effective. Do not use for hemiplegic or basilar migraine.",
        "before_taking": "Do not take if you have cardiovascular disease, uncontrolled hypertension, or are taking ergotamine-containing medications. Tell your doctor about all medications including antidepressants. Avoid potent CYP3A4 inhibitors within 72 hours.",
    },
    "zolmitriptan": {
        "description": "Zolmitriptan (Zomig) is a selective 5-HT1B/1D serotonin receptor agonist (triptan) available as oral tablet, orally disintegrating tablet (ODT), and nasal spray for acute migraine treatment.",
        "uses": "Zolmitriptan is indicated for the acute treatment of migraine with or without aura in adults. It has the advantage of multiple formulations, including a nasal spray particularly useful for migraineurs with nausea/vomiting. The ODT formulation dissolves on the tongue without water.",
        "warnings": "Same cardiovascular contraindications as other triptans: avoid in coronary artery disease, cerebrovascular disease, uncontrolled hypertension, and other serious vascular conditions. Do not use within 24 hours of another triptan or ergotamine-containing medication. Serotonin syndrome risk. MAO-A inhibitors: contraindicated (zolmitriptan levels significantly increased by MAO inhibitors). Caution in mild-moderate hepatic impairment (do not exceed 5 mg/day).",
        "side_effects": "Common: tingling/paresthesia, warmth, heaviness, tightness, somnolence, dizziness, nausea. Nasal spray: unusual taste, nasal symptoms.",
        "dosage": "Tablet/ODT: 2.5 mg at onset; may repeat after 2 hours; max 10 mg/24 hours. Nasal spray: 2.5 or 5 mg in one nostril; may repeat after 2 hours; max 10 mg/24 hours. If no response to first dose, do not take second dose for same attack.",
        "before_taking": "Tell your doctor about cardiovascular disease, hypertension, liver disease, or if you use MAO inhibitors. Do not take with or within 2 weeks of MAO inhibitors. Inform your doctor about all serotonergic medications.",
    },
    "milnacipran": {
        "description": "Milnacipran (Savella) is a serotonin-norepinephrine reuptake inhibitor (SNRI) approved specifically for the management of fibromyalgia in adults.",
        "uses": "Milnacipran is indicated for the management of fibromyalgia in adults. It reduces pain and fatigue by inhibiting the reuptake of serotonin and norepinephrine in the central nervous system, improving descending pain modulation. Milnacipran is not approved for depression in the U.S. (despite being used as an antidepressant in other countries).",
        "warnings": "FDA BOXED WARNING: Antidepressants increase the risk of suicidal thoughts in children, adolescents, and young adults — milnacipran is not approved in pediatric patients. Serotonin syndrome risk with other serotonergic drugs. Increased blood pressure and heart rate — monitor cardiovascular status. Elevated liver enzymes and hepatitis reported — monitor liver function. Urinary retention, particularly in men. Seizure risk. Angle-closure glaucoma risk. Discontinuation syndrome: taper gradually.",
        "side_effects": "Common: nausea, headache, constipation, dizziness, insomnia, hot flashes, palpitations, hypertension, tachycardia, dry mouth, sweating. Serious: hypertension, tachycardia, serotonin syndrome, hepatotoxicity.",
        "dosage": "Day 1: 12.5 mg once; Days 2-3: 12.5 mg twice daily; Days 4-7: 25 mg twice daily; After day 7: 50 mg twice daily. Target dose: 50 mg twice daily. Renal impairment (CrCl 5-29 mL/min): 25 mg twice daily. Take with or without food.",
        "before_taking": "Tell your doctor about hypertension, heart disease, urinary problems (especially in men), liver disease, glaucoma, or depression with suicidal thoughts. Do not use with MAO inhibitors (dangerous interaction). Taper gradually when discontinuing.",
    },
    "liothyronine": {
        "description": "Liothyronine sodium (Cytomel, Triostat) is a synthetic form of triiodothyronine (T3), the active thyroid hormone. Oral tablets used for hypothyroidism; IV formulation for myxedema coma.",
        "uses": "Liothyronine is used for hypothyroidism when T3 supplementation is desired (some patients with persistent symptoms on levothyroxine), thyroid hormone suppression therapy in well-differentiated thyroid cancer, and as an adjunct with antithyroid drugs in thyrotoxicosis. IV liothyronine is used for myxedema coma (with IV T4 and stress doses of glucocorticoids).",
        "warnings": "Not for use in weight reduction in euthyroid patients (can cause serious or life-threatening toxicity). Because of its rapid onset and potent effect, liothyronine may be more difficult to titrate than levothyroxine. Use with caution in patients with cardiovascular disease — can precipitate cardiac arrhythmias, angina, or MI. Do not use in thyrotoxicosis or with artificial thyroid replacement when not needed.",
        "side_effects": "Signs of excess T3: palpitations, tachycardia, angina, arrhythmias, tremor, nervousness, heat intolerance, excessive sweating, weight loss, headache, insomnia, diarrhea.",
        "dosage": "Hypothyroidism: initial 25 mcg/day; increase by 12.5-25 mcg every 1-2 weeks; usual maintenance 25-75 mcg/day. Thyroid suppression: 75-100 mcg/day. TSH and free T3 monitoring guides dose adjustment. Take on empty stomach at consistent time daily.",
        "before_taking": "Tell your doctor about heart disease, adrenal gland disorders, or diabetes before starting. Take on empty stomach. Separate from calcium, iron, and antacids by at least 4 hours. Do not stop without medical supervision.",
    },
    "formoterol": {
        "description": "Formoterol (Foradil, Perforomist) is a long-acting beta-2 adrenergic agonist (LABA) inhaler used for maintenance treatment of asthma and COPD. It should always be used in combination with an inhaled corticosteroid (ICS) in asthma.",
        "uses": "Formoterol is indicated for maintenance treatment of bronchoconstriction in patients with COPD (including chronic bronchitis and emphysema) and for the prevention of exercise-induced bronchoconstriction (EIB). In asthma, it is always used in combination with an ICS (never as monotherapy).",
        "warnings": "FDA BOXED WARNING: Long-acting beta-agonists (LABAs) increase the risk of asthma-related death — do not use formoterol as monotherapy for asthma. Only prescribe as additional therapy in patients not adequately controlled on an ICS or whose disease severity requires initiation of an ICS and LABA. Formoterol is not for the rescue treatment of acute bronchospasm — use short-acting beta-agonist (SABA) for acute episodes. Paradoxical bronchospasm can occur.",
        "side_effects": "Common: tremor, tachycardia, palpitations, muscle cramps, headache, throat irritation, cough. Serious: paradoxical bronchospasm, angina, hypokalemia, hyperglycemia.",
        "dosage": "COPD (Perforomist nebulizer): 20 mcg/2 mL nebulized twice daily. Foradil (DPI capsule): 12 mcg inhaled via Aerolizer twice daily (12 hours apart). Dry powder capsules should be inhaled ONLY using the provided inhaler — do not swallow.",
        "before_taking": "Do not use as a rescue inhaler. Always use with an ICS in asthma. Tell your doctor about heart disease, hypertension, diabetes, thyroid disease, or seizures. Do not swallow formoterol capsules (DPI).",
    },
    "ramelteon": {
        "description": "Ramelteon (Rozerem) is a melatonin receptor agonist (MT1 and MT2 receptors) used for the treatment of insomnia characterized by difficulty falling asleep (sleep onset insomnia).",
        "uses": "Ramelteon is indicated for the treatment of insomnia characterized by difficulty with sleep onset. Unlike benzodiazepines and Z-drugs, it is not a controlled substance and does not carry dependence, abuse, or withdrawal risks. It works by mimicking melatonin to regulate the circadian clock.",
        "warnings": "Not for use in patients with severe hepatic impairment. Anaphylaxis and angioedema reported. Complex sleep behaviors reported (rare). Hormonal effects: decreased testosterone levels and increased prolactin levels reported with long-term use. Worsening depression and suicidal ideation: evaluate patients with co-existing depression. Avoid with fluvoxamine (major CYP1A2 inhibitor — 190-fold increase in ramelteon exposure).",
        "side_effects": "Common: somnolence, dizziness, fatigue, nausea, headache, exacerbated insomnia. Endocrine: decreased testosterone, elevated prolactin (long-term use). Rare: complex sleep behaviors, anaphylaxis.",
        "dosage": "8 mg orally 30 minutes before bedtime. Do not take with or immediately after a high-fat meal (delays onset). Not recommended in severe hepatic impairment. No dosage adjustment for age or gender.",
        "before_taking": "Tell your doctor about liver disease, depression, or sleep apnea. Do not take with fluvoxamine (serious interaction). Avoid alcohol and other CNS depressants. Take 30 minutes before bedtime.",
    },
    "suvorexant": {
        "description": "Suvorexant (Belsomra) is an orexin receptor antagonist used for the treatment of insomnia characterized by difficulty with sleep onset and/or sleep maintenance in adults. It is a Schedule IV controlled substance.",
        "uses": "Suvorexant is indicated for the treatment of insomnia characterized by difficulties with sleep onset and/or sleep maintenance in adults. It works by blocking orexin (hypocretin) receptors OX1R and OX2R, reducing wakefulness-promoting orexin signaling.",
        "warnings": "FDA BOXED WARNING: CNS depression — risk of impaired driving, coordination, and next-day somnolence, especially with 20 mg dose. Abnormal thinking and behavioral changes, including complex sleep behaviors (sleep-driving, sleep-walking, eating, phone calls) — discontinue if they occur. Worsening depression and suicidal ideation. Orexin neuropeptides are involved in wakefulness and cataplexy — monitor for hypnagogic hallucinations, cataplexy-like symptoms, and sleep paralysis. Drug interactions: avoid use with strong CYP3A4 inhibitors.",
        "side_effects": "Common: next-day somnolence (dose-related), headache, dizziness. Serious: complex sleep behaviors, CNS depression affecting driving, worsened depression, cataplexy-like symptoms.",
        "dosage": "Recommended dose: 10 mg within 30 minutes of bedtime (at least 7 hours before planned awakening). May increase to max 20 mg/day if 10 mg not effective. Start with 5 mg if taking moderate CYP3A4 inhibitors. Avoid strong CYP3A4 inhibitors (contraindicated).",
        "before_taking": "Tell your doctor about depression, narcolepsy, or drug or alcohol dependence. Do not take with strong CYP3A4 inhibitors. Allow 7 hours before activities requiring full alertness. Avoid alcohol.",
    },
    "diclofenac": {
        "description": "Diclofenac (Voltaren, Cataflam, Cambia) is an oral and topical NSAID (nonsteroidal anti-inflammatory drug) with analgesic and anti-inflammatory properties. Oral formulations are available by prescription; a topical gel (Voltaren) is available over the counter for joint and muscle pain.",
        "uses": "Diclofenac is used to treat pain, inflammation, and stiffness from osteoarthritis, rheumatoid arthritis, and ankylosing spondylitis. Oral diclofenac potassium (Cambia) is also used for acute migraine with or without aura. Topical diclofenac gel is used for osteoarthritis pain in joints of the hands, wrists, elbows, knees, ankles, and feet. Diclofenac epolamine patch is used to treat acute pain from minor strains, sprains, and contusions.",
        "warnings": "NSAIDs, including diclofenac, can increase the risk of serious cardiovascular thrombotic events including myocardial infarction and stroke, which can be fatal. Diclofenac can cause serious GI adverse events including bleeding, ulceration, and perforation of the stomach and intestines. Risk of hepatotoxicity: diclofenac is associated with a higher rate of liver enzyme elevations than other NSAIDs; liver tests should be monitored if used long-term. Avoid use in the third trimester of pregnancy and in patients with severe hepatic, renal, or cardiac impairment. Topical diclofenac can cause local skin reactions.",
        "side_effects": "Common (oral): abdominal pain, nausea, dyspepsia, diarrhea, constipation, headache, dizziness, rash, elevated liver enzymes. Serious: GI bleeding, peptic ulcer, hepatotoxicity (diclofenac has one of the highest rates among NSAIDs), cardiovascular events, renal insufficiency, severe skin reactions (SJS, TEN), anaphylaxis. Topical: local skin dryness, redness, and pruritus.",
        "dosage": "Osteoarthritis (oral): 100-150 mg/day in divided doses (e.g., 50 mg 2-3 times daily). Rheumatoid arthritis: 150-200 mg/day in divided doses. Migraine (Cambia): 50 mg powder packet dissolved in water at headache onset; do not repeat within 24 hours. Topical gel (Voltaren 1%): apply 4 g to the affected joint(s) 4 times daily; upper extremities max 16 g/day, lower extremities max 32 g/day.",
        "before_taking": "Tell your doctor if you have heart disease, high blood pressure, liver or kidney disease, asthma, stomach ulcers, or GI bleeding. Inform your doctor about all medications, especially blood thinners, other NSAIDs, SSRIs, ACE inhibitors, or diuretics. Use caution in patients with cardiovascular risk factors. Liver function should be monitored during chronic diclofenac therapy.",
    },
    "ursodiol": {
        "description": "Ursodiol (ursodeoxycholic acid; brand names Actigall, URSO 250, URSO Forte) is a bile acid used to dissolve gallstones, prevent gallstone formation, and treat primary biliary cholangitis (PBC). It is available by prescription.",
        "uses": "Ursodiol is indicated for: (1) dissolution of radiolucent, noncalcified gallbladder stones less than 20 mm in diameter in patients who are not surgical candidates; (2) prevention of gallstone formation in obese patients undergoing rapid weight loss; and (3) treatment of primary biliary cholangitis (PBC, also called primary biliary cirrhosis) to improve liver function tests and slow disease progression.",
        "warnings": "Gallstone dissolution therapy with ursodiol works for radiolucent, noncalcified gallstones only. Stones may recur after discontinuation. Liver tests should be monitored in patients with PBC. Use with caution in patients with hepatic impairment. Ursodiol is not recommended during pregnancy unless clearly needed; use effective contraception during therapy.",
        "side_effects": "Generally well tolerated. Common: diarrhea (dose-related), abdominal discomfort, nausea, vomiting, indigestion, constipation, hair thinning (rare). Serious: rare worsening of liver disease in patients with PBC who have advanced cirrhosis; monitor liver function tests.",
        "dosage": "Gallstone dissolution: 8-10 mg/kg/day in 2-3 divided doses. Prevention of gallstones during rapid weight loss: 300 mg twice daily during the weight-loss period. Primary biliary cholangitis: 13-15 mg/kg/day in 2-4 divided doses, administered with food. Duration of gallstone dissolution therapy: up to 24 months; obtain ultrasound at 6 and 12 months to assess response.",
        "before_taking": "Tell your doctor about liver disease, bile duct abnormalities, or recent bile duct surgery. Do not use for calcified or radiopaque gallstones, or for gallstone pancreatitis. Ursodiol may reduce the absorption of cyclosporine; dose adjustment may be needed.",
    },
}


REVIEWERS = [
    ("Lisa Huang", "MD, Endocrinology"),
    ("Robert Walsh", "PharmD, BCACP"),
]


def seed_drugs():
    existing = {d.generic_name for d in Drug.query.all()}
    cls_by_name = {c.name: c.id for c in DrugClass.query.all()}
    featured_targets = {"ibuprofen", "metformin", "lisinopril", "sertraline", "atorvastatin", "semaglutide", "amoxicillin", "levothyroxine"}
    for idx, entry in enumerate(DRUGS_DATA):
        gname, cname, avail, csa, pron, brands, conds = entry
        if gname in existing:
            continue
        # Try OpenFDA first, fall back to synthetic.
        openfda = fetch_openfda_label(gname)
        if openfda:
            uses = truncate(first(openfda.get("indications_and_usage")))
            warn = truncate(first(openfda.get("warnings") or openfda.get("warnings_and_cautions")))
            dose = truncate(first(openfda.get("dosage_and_administration")))
            adv = truncate(first(openfda.get("adverse_reactions")))
            inter = truncate(first(openfda.get("drug_interactions")))
            desc = truncate(first(openfda.get("description")) or first(openfda.get("clinical_pharmacology")))
        else:
            uses = warn = dose = adv = inter = desc = None
        if not any([uses, warn, dose, adv, inter, desc]):
            syn = synthetic_content(gname, cname, conds)
            uses = uses or syn["uses"]
            warn = warn or syn["warnings"]
            dose = dose or syn["dosage"]
            adv = adv or syn["side_effects"]
            inter = inter or syn["interactions_text"]
            desc = desc or syn["description"]

        # Manual overrides for drugs whose openFDA label resolved to a combination
        # product or otherwise mismatched content. Each override fully replaces the
        # uses/description/warnings/dosage/side_effects so the single-ingredient
        # drug page reads correctly.
        if gname in DRUG_CONTENT_OVERRIDES:
            ov = DRUG_CONTENT_OVERRIDES[gname]
            uses = ov.get("uses", uses)
            desc = ov.get("description", desc)
            warn = ov.get("warnings", warn)
            dose = ov.get("dosage", dose)
            adv = ov.get("side_effects", adv)

        faq = [
            {"q": f"What is {gname} used for?", "a": _trunc_at_sentence(uses) or f"{gname} is used to treat {', '.join(conds) if conds else 'various medical conditions'}."},
            {"q": f"How should I take {gname}?", "a": _trunc_at_sentence(dose) or f"Take {gname} exactly as prescribed by your doctor."},
            {"q": f"What are the most common side effects of {gname}?", "a": _trunc_at_sentence(adv) or "Common side effects vary; consult the side effects section above."},
            {"q": f"Can I drink alcohol while taking {gname}?", "a": "Talk with your doctor or pharmacist about whether alcohol is safe to consume while on this medication. Alcohol can worsen side effects of many drugs."},
            {"q": f"Is {gname} safe during pregnancy?", "a": "Discuss with your doctor before using this medication if you are pregnant, planning pregnancy, or breastfeeding."},
        ]

        d = Drug(
            generic_name=gname,
            slug=slugify(gname),
            brand_names_json=json.dumps(brands),
            drug_class_id=cls_by_name.get(cname),
            availability=avail,
            csa_schedule=csa,
            pregnancy_risk=_PREGNANCY_RISK.get(gname, "Discuss with your doctor"),
            pronunciation=pron,
            description=desc,
            uses=uses,
            warnings=warn,
            dosage=dose,
            side_effects=adv,
            interactions_text=inter,
            faq_json=json.dumps(faq),
            conditions_json=json.dumps(conds),
            related_drugs_json=json.dumps([]),
            is_featured=(gname in featured_targets),
            reviewer_name=REVIEWERS[idx % len(REVIEWERS)][0],
            reviewer_credential=REVIEWERS[idx % len(REVIEWERS)][1],
            last_updated=datetime.utcnow() - timedelta(days=hash(gname) % 365),
        )
        db.session.add(d)
    db.session.commit()

    # Populate related_drugs by class
    all_drugs = Drug.query.all()
    by_class = {}
    for d in all_drugs:
        by_class.setdefault(d.drug_class_id, []).append(d.generic_name)
    for d in all_drugs:
        peers = [n for n in by_class.get(d.drug_class_id, []) if n != d.generic_name][:6]
        d.related_drugs_json = json.dumps(peers)
    db.session.commit()


def seed_drug_conditions():
    cond_by_slug = {c.slug: c for c in Condition.query.all()}
    existing = {(dc.drug_id, dc.condition_id) for dc in DrugCondition.query.all()}
    for d in Drug.query.all():
        for c_slug in d.conditions_list:
            c = cond_by_slug.get(c_slug)
            if c and (d.id, c.id) not in existing:
                db.session.add(DrugCondition(drug_id=d.id, condition_id=c.id))
    db.session.commit()
    # Update denormalized drug_count
    for c in Condition.query.all():
        c.drug_count = DrugCondition.query.filter_by(condition_id=c.id).count()
    db.session.commit()


def seed_pill_images():
    drug_by_name = {d.generic_name: d for d in Drug.query.all()}
    existing = set()
    for pi in DrugImage.query.all():
        existing.add((pi.drug_id, pi.imprint))
    to_add = []
    for gname, imprint, shape, color, strength, mfg in PILL_IMAGES_DATA:
        d = drug_by_name.get(gname)
        if not d:
            continue
        if (d.id, imprint) in existing:
            continue
        to_add.append((d, imprint, shape, color, strength, mfg))
        existing.add((d.id, imprint))
    if not to_add:
        return
    for d, imprint, shape, color, strength, mfg in to_add:
        db.session.add(DrugImage(
            drug_id=d.id, imprint=imprint, shape=shape, color=color,
            strength=strength, manufacturer=mfg,
        ))
    db.session.commit()


def seed_interactions():
    """Add any interactions in INTERACTIONS_DATA that aren't already in the DB.

    Additive: matches on the unordered (drug_a_id, drug_b_id) pair so re-seeding
    won't duplicate rows. Gated as a whole — if every applicable pair is already
    present, returns without touching the session, preserving byte-identical
    reset semantics.
    """
    drug_by_name = {d.generic_name: d for d in Drug.query.all()}
    existing_pairs = set()
    for i in DrugInteraction.query.all():
        existing_pairs.add((i.drug_a_id, i.drug_b_id))
        existing_pairs.add((i.drug_b_id, i.drug_a_id))

    to_add = []
    for a, b, sev, desc in INTERACTIONS_DATA:
        da = drug_by_name.get(a)
        db_ = drug_by_name.get(b)
        if not da or not db_:
            continue
        if (da.id, db_.id) in existing_pairs:
            continue
        to_add.append((da, db_, sev, desc))
        existing_pairs.add((da.id, db_.id))
        existing_pairs.add((db_.id, da.id))

    if not to_add:
        return
    for da, db_, sev, desc in to_add:
        db.session.add(DrugInteraction(
            drug_a_id=da.id, drug_b_id=db_.id, severity=sev, description=desc,
        ))
    db.session.commit()


def seed_news():
    """Seed news articles.

    Each entry in NEWS_DATA is a tuple of (title, category, body) or
    (title, category, body, source, published_at_iso). When the 5-tuple form
    is used, the explicit source and publication date override the defaults.
    """
    existing = {n.title for n in NewsArticle.query.all()}
    now = datetime.utcnow()
    for i, entry in enumerate(NEWS_DATA):
        if len(entry) == 5:
            title, cat, body, source, pub_iso = entry
            published_at = datetime.fromisoformat(pub_iso)
        else:
            title, cat, body = entry
            source = "Drugs.com Medical News"
            published_at = now - timedelta(days=i * 2)
        if title in existing:
            continue
        db.session.add(NewsArticle(
            title=title, category=cat, body=body, source=source,
            published_at=published_at,
            is_featured=(i < 4),
        ))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    drugs = Drug.query.all()
    if not drugs:
        return
    # Per-user curated med lists. Alice gets a chronic-care mix (pain reliever
    # + diabetes + statin) so the med list page demos varied drug classes.
    curated_meds = {
        "alice.j@test.com": ["ibuprofen", "metformin", "atorvastatin"],
    }
    for idx, u in enumerate(BENCHMARK_USERS):
        user = User(
            username=u["username"], email=u["email"],
            first_name=u.get("first_name", ""), last_name=u.get("last_name", ""),
        )
        user.set_password(u["password"])
        db.session.add(user)
        db.session.flush()
        # Saved drugs (3+)
        curated = curated_meds.get(u["email"])
        if curated:
            saved_pool = [d for slug in curated
                          for d in [Drug.query.filter_by(slug=slug).first()] if d]
        else:
            saved_pool = drugs[(idx * 7) % len(drugs):(idx * 7) % len(drugs) + 5]
        if len(saved_pool) < 3:
            saved_pool = drugs[:5]
        for d in saved_pool[:4]:
            db.session.add(SavedDrug(user_id=user.id, drug_id=d.id, notes=f"Tracking for ongoing treatment."))
        # Reviews (2+)
        for j in range(3):
            target = drugs[(idx * 5 + j * 11) % len(drugs)]
            conds = target.conditions_list or ["general use"]
            tmpl = REVIEW_TEMPLATES[(idx + j) % len(REVIEW_TEMPLATES)]
            db.session.add(DrugReview(
                drug_id=target.id, user_id=user.id, rating=tmpl[1],
                title=tmpl[0], body=tmpl[2].format(cond=_humanize_cond(conds[0])),
                condition_treated=conds[0],
                helpful_count=(idx + j) * 3,
            ))
    db.session.commit()


def seed_extra_reviews():
    """Add reviews across all popular drugs from auto-generated reviewer users."""
    _REVIEWER_NAMES = [
        ("ChrisB79", "chrisb79@example.com"),
        ("MaryM_health", "marym.health@example.com"),
        ("JohnD_rx", "johnd.rx@example.com"),
        ("SarahK2024", "sarahk2024@example.com"),
        ("PatientAdvocate", "patient.advocate@example.com"),
        ("MigraineWarrior", "migraine.warrior@example.com"),
        ("DiabetesMgmt", "diabetes.mgmt@example.com"),
        ("HeartHealthPro", "hearthealthpro@example.com"),
    ]
    # Create reviewer users first (needed to check existing pairs)
    reviewers = []
    for i, (uname, email) in enumerate(_REVIEWER_NAMES):
        u = User.query.filter_by(email=email).first()
        if not u:
            # also try legacy email in case DB was seeded before rename
            legacy = f"reviewer{i}@example.com"
            u = User.query.filter_by(email=legacy).first()
        if not u:
            u = User(username=uname, email=email)
            u.set_password("review-seed-pw")
            db.session.add(u)
            db.session.flush()
        elif u.username != uname:
            u.username = uname
            u.email = email
        reviewers.append(u)
    db.session.commit()  # always persist username/email renames
    reviewer_ids = {u.id for u in reviewers}
    if DrugReview.query.filter(DrugReview.user_id.in_(reviewer_ids)).count() >= 700:
        return
    # Pre-load existing (drug_id, user_id) pairs to avoid duplicates
    existing_pairs = {
        (r.drug_id, r.user_id)
        for r in DrugReview.query.filter(DrugReview.user_id.in_(reviewer_ids)).all()
    }
    popular = ["ibuprofen", "metformin", "lisinopril", "sertraline", "atorvastatin",
               "amoxicillin", "levothyroxine", "alprazolam", "gabapentin", "omeprazole",
               "semaglutide", "fluoxetine", "amlodipine", "tramadol", "zolpidem",
               "warfarin", "clopidogrel", "furosemide", "prednisone", "rosuvastatin",
               "losartan", "metoprolol", "carvedilol", "hydrochlorothiazide",
               "pantoprazole", "famotidine", "ondansetron", "cetirizine", "loratadine",
               "montelukast", "ciprofloxacin", "doxycycline", "fluconazole", "acyclovir",
               "tamsulosin", "tadalafil", "sildenafil", "oxycodone", "hydrocodone",
               "methylphenidate", "lithium", "valproic acid", "lamotrigine",
               "levetiracetam", "duloxetine", "venlafaxine", "bupropion", "trazodone",
               "escitalopram", "quetiapine", "olanzapine", "aripiprazole", "clonazepam",
               "lorazepam", "diazepam", "buspirone", "pregabalin", "celecoxib",
               "naproxen", "cyclobenzaprine", "colchicine", "allopurinol", "alendronate",
               "estradiol", "methimazole", "finasteride", "spironolactone", "digoxin",
               "citalopram", "paroxetine", "mirtazapine", "risperidone", "topiramate",
               "verapamil", "diltiazem", "valsartan", "atenolol", "propranolol",
               "apixaban", "rivaroxaban", "esomeprazole", "lansoprazole", "azithromycin",
               "fexofenadine", "hydroxyzine", "fluticasone", "tiotropium",
               "valacyclovir", "morphine", "buprenorphine", "atomoxetine",
               "carbamazepine", "haloperidol", "methocarbamol", "baclofen",
               "tizanidine", "risedronate", "raloxifene", "testosterone",
               "isotretinoin", "tretinoin", "timolol", "latanoprost",
               "vitamin D3", "folic acid", "ferrous sulfate", "multivitamin",
               "aspirin", "meloxicam", "diclofenac", "indomethacin", "methotrexate",
               "acetaminophen", "codeine", "ketorolac", "piroxicam", "etodolac",
               "nifedipine", "amlodipine", "felodipine", "ramipril", "enalapril",
               "captopril", "benazepril", "irbesartan", "olmesartan", "telmisartan",
               "insulin glargine", "insulin lispro", "pioglitazone", "sitagliptin",
               "empagliflozin", "dapagliflozin", "liraglutide", "dulaglutide",
               "atorvastatin", "simvastatin", "pravastatin", "fluvastatin",
               "ezetimibe", "fenofibrate", "gemfibrozil", "niacin",
               "albuterol", "ipratropium", "budesonide", "salmeterol",
               "montelukast", "zafirlukast", "cromolyn", "theophylline",
               "alendronate", "ibandronate", "zoledronic acid", "denosumab",
               "levothyroxine", "liothyronine", "methimazole", "propylthiouracil",
               "hydrocortisone", "dexamethasone", "methylprednisolone", "triamcinolone",
               "amoxicillin", "clavulanate", "ampicillin", "cephalexin", "cefazolin",
               "clindamycin", "erythromycin", "tetracycline", "minocycline",
               "trimethoprim", "sulfamethoxazole", "nitrofurantoin", "fosfomycin",
               "fluconazole", "itraconazole", "voriconazole", "terbinafine",
               "acyclovir", "valacyclovir", "famciclovir", "oseltamivir",
               "hydroxychloroquine", "chloroquine", "doxycycline", "mefloquine",
               "donepezil", "memantine", "rivastigmine", "galantamine", "lecanemab",
               "tirzepatide", "sumatriptan", "diphenhydramine", "melatonin", "amitriptyline",
               "naloxone", "naltrexone", "doxazosin", "adalimumab", "dupilumab",
               "clonidine", "prazosin", "terazosin", "guanfacine",
               "zolpidem", "eszopiclone", "ramelteon", "doxylamine",
               "nortriptyline", "imipramine", "desipramine", "clomipramine",
               "sumatriptan", "rizatriptan", "zolmitriptan", "eletriptan",
               "morphine", "oxymorphone", "fentanyl", "tapentadol",
               "methadone", "naltrexone", "buprenorphine",
               "vitamin B12", "vitamin C", "zinc", "magnesium", "calcium carbonate",
               "docusate", "polyethylene glycol", "bisacodyl", "senna"]
    # The source list is organized by therapeutic area and intentionally
    # repeats some high-traffic drugs. A user may only review a given drug once,
    # so de-duplicate while preserving the first occurrence/order.
    popular = list(dict.fromkeys(popular))
    drug_by_name = {d.generic_name: d for d in Drug.query.all()}
    count = 0
    for i, name in enumerate(popular):
        d = drug_by_name.get(name)
        if not d:
            continue
        conds = d.conditions_list or ["general"]
        for j in range(4):
            # Offset by 5 so reviewer_N templates don't duplicate benchmark user reviews
            tmpl = REVIEW_TEMPLATES[(i + j + 5) % len(REVIEW_TEMPLATES)]
            u = reviewers[(i + j) % len(reviewers)]
            if (d.id, u.id) in existing_pairs:
                continue
            db.session.add(DrugReview(
                drug_id=d.id, user_id=u.id, rating=tmpl[1],
                title=tmpl[0], body=tmpl[2].format(cond=_humanize_cond(conds[j % len(conds)])),
                condition_treated=conds[j % len(conds)],
                helpful_count=(j + 1) * 4,
                created_at=datetime.utcnow() - timedelta(days=(i * 4 + j)),
            ))
            existing_pairs.add((d.id, u.id))
            count += 1
        if count >= 4000:
            break
    db.session.commit()
    if count > 0:
        recompute_drug_ratings()


def recompute_drug_ratings():
    for d in Drug.query.all():
        revs = DrugReview.query.filter_by(drug_id=d.id).all()
        if revs:
            d.avg_rating = round(sum(r.rating for r in revs) / len(revs), 1)
            d.review_count = len(revs)
        else:
            d.avg_rating = 0.0
            d.review_count = 0
    db.session.commit()


def seed_database():
    # Gate the entire seeding block: even a no-op commit bumps SQLite metadata
    # and breaks /reset byte-identity. All-or-nothing is the correct invariant.
    if Drug.query.count() > 0:
        return
    seed_drug_classes()
    seed_conditions()
    seed_drugs()
    seed_drug_conditions()
    seed_pill_images()
    seed_interactions()
    seed_news()
    seed_benchmark_users()
    seed_extra_reviews()
    recompute_drug_ratings()
    # Supplemental and backfill passes run once as part of initial seeding;
    # they are defined later in the file but called here so the all-or-nothing
    # gate above covers them too (avoids SQLite metadata bumps on every reset).
    seed_supplemental()
    seed_pregnancy_risks()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SEARCH_ALIASES: dict[str, list[str]] = {
    "antibiotics": ["antibiotic", "antibacterial", "antimicrobial", "fluoroquinolone", "macrolide", "penicillin", "cephalosporin"],
    "antibiotic":  ["antibiotics", "antibacterial", "antimicrobial", "fluoroquinolone"],
    "antifungals": ["antifungal"],
    "antifungal":  ["antifungals"],
    "antidepressants": ["antidepressant"],
    "antidepressant":  ["antidepressants"],
    "antipsychotics":  ["antipsychotic"],
    "antipsychotic":   ["antipsychotics"],
    "blood pressure":  ["antihypertensive", "hypertension"],
    "diabetes":        ["antidiabetic", "hypoglycemic"],
    "pain":            ["analgesic", "nsaid", "opioid"],
    "cholesterol":     ["statin", "lipid"],
    "anxiety":         ["anxiolytic", "benzodiazepine"],
    "seizures":        ["anticonvulsant", "antiepileptic"],
    "steroids":        ["corticosteroid", "glucocorticoid"],
}


def tokenize(q):
    if not q:
        return []
    return [t.lower() for t in re.split(r"\W+", q) if t]


def _expand_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for t in tokens:
        for alias in _SEARCH_ALIASES.get(t, []):
            if alias not in expanded:
                expanded.append(alias)
    return expanded


def score_drug(drug, tokens):
    class_name = drug.drug_class.name if drug.drug_class else ""
    class_desc = drug.drug_class.description if drug.drug_class else ""
    gname = drug.generic_name.lower()
    brands = " ".join(drug.brand_names).lower() if drug.brand_names else ""
    body = f"{class_name} {class_desc} {drug.uses or ''} {drug.description or ''}".lower()
    expanded = _expand_tokens(tokens)
    score = 0
    for t in expanded:
        if t == gname:
            score += 20  # exact generic name match
        elif gname.startswith(t) or t in gname:
            score += 10  # partial generic name match
        elif t in brands:
            score += 8   # brand name match
        elif t in body:
            score += 1   # description/class match
    return score


@app.template_filter('preg_category')
def preg_category_filter(risk: str) -> str:
    """Extract FDA pregnancy category letter (A/B/C/D/X) from a full risk string.

    Handles both bare letters ('C') and prefixed forms ('Category C - description...')
    Returns the uppercase letter, or '' if not found.
    """
    if not risk:
        return ''
    s = risk.strip()
    # Try "Category X" prefix form
    if s.upper().startswith('CATEGORY '):
        letter = s[9:10].upper()
        if letter in 'ABCDX':
            return letter
    # Try bare single letter
    if len(s) == 1 and s.upper() in 'ABCDX':
        return s.upper()
    return ''


@app.template_filter('pill_image_exists')
def pill_image_exists(slug):
    """Return True iff ``static/images/pills/<slug>.jpg`` is present on disk.

    Used by drug detail / pill identifier / drug images templates to decide
    whether to render the real downloaded photo (from NLM DailyMed, public
    domain) or fall back to the inline SVG pill illustration. The
    ``static/images/`` tree is HF-managed so its contents vary between
    fresh clones; templates can't filesystem-check, hence this filter.
    """
    if not slug:
        return False
    path = os.path.join(BASE_DIR, 'static', 'images', 'pills', f'{slug}.jpg')
    return os.path.exists(path)


@app.template_filter('clean_desc')
def clean_desc(text):
    """Strip FDA section-number prefix and return plain text suitable for a snippet."""
    if not text:
        return ''
    t = str(text).strip()
    # Strip "11 DESCRIPTION " or bare "DESCRIPTION " prefix
    t = re.sub(r'^\s*\d+\.?\s+[A-Z][A-Z &/()-]{3,}\s+', '', t)
    t = re.sub(r'^[A-Z]{4,}[A-Z /()-]*\s+', '', t)
    return t


@app.template_filter('format_drug_text')
def format_drug_text(text):
    """Format raw FDA-label drug text into readable HTML paragraphs.

    Collapses internal newlines, bolds ALL-CAPS section headings like
    'WARNINGS:', sets off numbered list items, and groups sentences into
    paragraphs of roughly three sentences each. Returns an HTML string
    consisting of one or more ``<p>...</p>`` blocks; intended to be
    piped through ``|safe`` in templates.
    """
    if not text:
        return ''
    # The source is normally the frozen seed DB, but some content originates
    # from a live external API at seed time. Escape it before inserting our own
    # small, known-safe formatting tags; callers render this filter with |safe.
    text = str(escape(str(text).strip()))
    # Strip section number prefixes from FDA labels (e.g. "11 DESCRIPTION ", "7 DRUG INTERACTIONS ")
    text = re.sub(r'^\s*\d+(?:\.\d+)?\s+[A-Z][A-Z ]{3,}\s+', '', text)
    text = re.sub(r'\.\s*\d+(?:\.\d+)?\s+[A-Z][A-Z ]{3,}\s+', '. ', text)
    # Strip FDA cross-reference bracketed refs like "[see Clinical Pharmacology (12.3)]"
    # or bare "[see Clinical Pharmacology  ]"
    text = re.sub(r'\[see [^\]]{1,80}\]', '', text)
    text = re.sub(r'\( ?\d+(?:\.\d+)? ?\)', '', text)
    # Strip raw FDA table headers like "Table 5." or "Table 5. Drugs That May..."
    text = re.sub(r'Table \d+\.?[^.]*?\.\s*', '', text)
    # Strip FDA subsection headings like "7.1 Drugs Known to Affect Thyroid Hormone Pharmacokinetics"
    # Match: digit.digit + space + Title Case words (up to 80 chars total) + lookahead for sentence start
    text = re.sub(r'\d+\.\d+(?:\.\d+)? [A-Z][A-Za-z ,/()-]{5,80}?(?=\n|  |\. [A-Z]| [A-Z][a-z]{2,}[^a-z])', ' ', text)
    # Strip parenthetical table ranges like "(Tables 5 to 8)" or "(Table 5)"
    text = re.sub(r'\(Tables? \d+(?: to \d+)?\)', '', text)
    # Strip flattened FDA table column headers like "Drug or Drug Class Effect " at start of paragraphs
    text = re.sub(r'(?:Drug (?:or Drug Class|Class|Name)\s+(?:Effect|Mechanism|Clinical Impact|Recommendation)\s*)', '', text)
    # Strip inline section refs like "(7)" or "( 7 )" after spaces
    text = re.sub(r'\s\(\s?\d+\s?\)\s', ' ', text)
    # Strip full sentences that are pure chemistry boilerplate
    boilerplate_patterns = [
        r'[Tt]he (empirical|chemical|molecular) formula',
        r'[Mm]olecular [Ww]eight',
        r'[Ii]nactive [Ii]ngredients',
        r'[Cc]hemical [Nn]ame',
        r'[Cc]rystalline powder',
        r'[Ss]oluble in (water|methanol|ethanol)',
        r'[Mm]elting [Pp]oint',
        r'[Pp]Ka value',
        r'[Ff]D&?C (Yellow|Blue|Red)',
        r'contains? (the following|gelatin|lactose|corn starch)',
        r'USP is \([βαδ]',     # IUPAC stereochem name "calcium USP is (βR, δR)-..."
        r'structural formula',
        r'molecular weight is \d',
        r'See full prescribing information',
        r'prescribing information for',
    ]
    sentences_raw = re.split(r'(?<=[.!?])\s+', text)
    filtered = []
    for s in sentences_raw:
        if not any(re.search(p, s) for p in boilerplate_patterns):
            filtered.append(s)
    text = ' '.join(filtered) if filtered else text
    # Collapse internal newlines into spaces.
    text = re.sub(r'\n+', ' ', text)
    # Bold ALL-CAPS section headings like 'WARNINGS:' or 'DOSAGE:'.
    text = re.sub(r'([A-Z]{3,}:)\s*', r'<strong>\1</strong> ', text)
    # Split into sentences at terminal punctuation followed by capital/digit.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text)
    paragraphs = []
    current = []
    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue
        current.append(sentence.strip())
        if len(current) >= 3 or i == len(sentences) - 1:
            paragraphs.append(' '.join(current))
            current = []
    if current:
        paragraphs.append(' '.join(current))
    return '<p>' + '</p><p>'.join(p for p in paragraphs if p.strip()) + '</p>'


@app.context_processor
def inject_globals():
    return {
        "site_name": "Drugs.com",
        "site_tagline": "Know More. Be Sure.",
        "current_year": datetime.utcnow().year,
        "all_letters": list(string.ascii_uppercase),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    featured = Drug.query.filter_by(is_featured=True).limit(8).all()
    _trending_names = ["semaglutide", "tirzepatide", "lisinopril", "metformin",
                        "atorvastatin", "gabapentin", "sertraline", "amoxicillin",
                        "ibuprofen", "levothyroxine", "omeprazole", "amlodipine"]
    trending = [Drug.query.filter_by(generic_name=n).first()
                for n in _trending_names]
    trending = [d for d in trending if d]
    # Exclude New Drug Approvals here -- that category gets its own dedicated
    # sidebar box below (title-free, links out to the category page), so
    # mixing it into this general feed would show its latest headline right
    # next to a category badge, leaking which article is most recent there.
    news = (NewsArticle.query
            .filter(~NewsArticle.category.in_(['New Drug Approvals', 'New Drugs']))
            .order_by(NewsArticle.published_at.desc()).limit(6).all())
    classes = DrugClass.query.order_by(DrugClass.name).limit(12).all()
    # Top 12 conditions by drug count (for homepage "Browse by" tabs)
    top_conditions = (Condition.query
                      .order_by(Condition.drug_count.desc(), Condition.name)
                      .limit(12).all())
    # Top 12 drug classes by number of drugs (denormalized count via subquery)
    class_drug_counts = dict(
        db.session.query(Drug.drug_class_id, db.func.count(Drug.id))
        .group_by(Drug.drug_class_id).all()
    )
    all_classes = DrugClass.query.all()
    for c in all_classes:
        c.drug_count_val = class_drug_counts.get(c.id, 0)
    top_drug_classes = sorted(
        all_classes, key=lambda c: (-c.drug_count_val, c.name)
    )[:12]
    # Common symptoms for the "Symptoms" tab (flat list of 12 from body systems)
    top_symptoms = [
        "Headache", "Cough", "Chest pain", "Nausea", "Joint pain", "Rash",
        "Anxiety", "Fatigue", "Shortness of breath", "Abdominal pain",
        "Back pain", "Insomnia",
    ]
    health_topics = Condition.query.filter(
        Condition.slug.in_(['hypertension', 'diabetes', 'depression', 'anxiety', 'pain',
                            'high-cholesterol', 'heart-disease', 'asthma', 'arthritis', 'insomnia'])
    ).all()
    fda_news = NewsArticle.query.filter_by(category="FDA Alerts").order_by(
        NewsArticle.published_at.desc()).limit(3).all()
    new_approvals = NewsArticle.query.filter(
        NewsArticle.category.in_(['New Drug Approvals', 'New Drugs'])
    ).order_by(NewsArticle.published_at.desc()).limit(4).all()
    image_drugs = (Drug.query.join(DrugImage, DrugImage.drug_id == Drug.id)
                   .order_by(Drug.review_count.desc(), Drug.id).limit(6).all())
    image_samples = [(d, d.images[0]) for d in image_drugs if d.images]
    return render_template("index.html", featured=featured, trending=trending,
                           news=news, classes=classes,
                           health_topics=health_topics, fda_news=fda_news,
                           new_approvals=new_approvals,
                           image_samples=image_samples,
                           top_conditions=top_conditions,
                           top_drug_classes=top_drug_classes,
                           top_symptoms=top_symptoms)


@app.route("/dosage-guide")
@app.route("/dosage-guide.html")
@app.route("/dosage")
def dosage_guide():
    drugs = Drug.query.order_by(Drug.generic_name).all()
    return render_template("dosage_guide.html", drugs=drugs)


@app.route("/pregnancy-safety")
@app.route("/pregnancy-safety.html")
def pregnancy_safety():
    drugs = Drug.query.filter(Drug.pregnancy_risk.isnot(None)).order_by(Drug.generic_name).all()
    return render_template("pregnancy_safety.html", drugs=drugs)


@app.route("/drugs-a-z")
@app.route("/drug-az")
@app.route("/drugs-a-to-z.html")
@app.route("/drug_information.html")
def drug_az():
    letter = _bounded_query_arg("letter", "A", 3).upper()
    if letter in ("0-9", "0"):
        letter = "0-9"
        drugs = Drug.query.filter(Drug.generic_name.op("GLOB")("[0-9]*")).order_by(Drug.generic_name).all()
    else:
        if letter not in string.ascii_uppercase:
            letter = "A"
        drugs = Drug.query.filter(Drug.generic_name.ilike(f"{letter}%")).order_by(Drug.generic_name).all()
    letter_counts = {
        L: Drug.query.filter(Drug.generic_name.ilike(f"{L}%")).count()
        for L in string.ascii_uppercase
    }
    letter_counts["0-9"] = Drug.query.filter(Drug.generic_name.op("GLOB")("[0-9]*")).count()
    popular_drugs = Drug.query.order_by(Drug.review_count.desc()).limit(10).all()

    # Top 8 drug classes by number of associated drugs.
    class_counts = (
        db.session.query(Drug.drug_class_id, db.func.count(Drug.id))
        .filter(Drug.drug_class_id.isnot(None))
        .group_by(Drug.drug_class_id)
        .all()
    )
    class_counts_sorted = sorted(class_counts, key=lambda r: -r[1])[:8]
    class_ids = [cid for cid, _ in class_counts_sorted]
    class_by_id = {c.id: c for c in DrugClass.query.filter(DrugClass.id.in_(class_ids)).all()} if class_ids else {}
    popular_classes = [class_by_id[cid] for cid, _ in class_counts_sorted if cid in class_by_id]

    # Top 6 conditions by drug count.
    cond_counts = dict(
        db.session.query(DrugCondition.condition_id, db.func.count(DrugCondition.drug_id))
        .group_by(DrugCondition.condition_id)
        .all()
    )
    all_conditions = Condition.query.all()
    for c in all_conditions:
        computed = cond_counts.get(c.id, 0)
        if c.drug_count is None or c.drug_count == 0:
            c.drug_count = computed
    popular_conditions = sorted(
        all_conditions, key=lambda c: (-(c.drug_count or 0), c.name)
    )
    popular_conditions = [c for c in popular_conditions if (c.drug_count or 0) > 0][:6]

    return render_template(
        "drug_az.html",
        active_letter=letter,
        all_letters=list(string.ascii_uppercase) + ["0-9"],
        drugs=drugs,
        letter_counts=letter_counts,
        popular_drugs=popular_drugs,
        popular_classes=popular_classes,
        popular_conditions=popular_conditions,
    )


def _first_sentences(text, n):
    """Return the first n sentences from text as a single string."""
    if not text:
        return ""
    # Strip simple HTML tags that may live in seed content
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    parts = re.split(r"(?<=[.!?])\s+", plain)
    parts = [p for p in parts if p]
    return " ".join(parts[:n]).strip()


def _build_default_faq(drug):
    """Generate a contextual FAQ from drug fields when faq_json is empty."""
    name = drug.generic_name
    name_cap = name.capitalize() if name else "this medicine"
    items = []

    uses_summary = _first_sentences(drug.uses, 2) or _first_sentences(drug.description, 2)
    if uses_summary:
        items.append({
            "q": f"What is {name} used for?",
            "a": uses_summary,
        })

    items.append({
        "q": f"How does {name} work?",
        "a": (
            f"{name_cap} belongs to the {drug.drug_class.name} class. "
            f"{drug.drug_class.description}"
        ) if drug.drug_class else (
            f"{name_cap} works through its active pharmacological mechanism in the body. "
            f"Talk to your doctor or pharmacist for a detailed explanation of how it works for your condition."
        ),
    })

    se_summary = _first_sentences(drug.side_effects, 3)
    if se_summary:
        items.append({
            "q": f"What are the most common side effects of {name}?",
            "a": se_summary,
        })

    avail = (drug.availability or "").lower()
    if "otc" in avail and "rx" in avail:
        otc_answer = (
            f"{name_cap} is available both over the counter and by prescription, "
            f"depending on the strength and formulation."
        )
    elif "otc" in avail:
        otc_answer = (
            f"Yes. {name_cap} is available over the counter without a prescription. "
            f"Always follow the directions on the label."
        )
    else:
        otc_answer = (
            f"No. {name_cap} is a prescription-only medicine and is not available over the counter. "
            f"You will need a prescription from a licensed healthcare provider."
        )
    items.append({
        "q": f"Is {name} available over the counter?",
        "a": otc_answer,
    })

    preg = (drug.pregnancy_risk or "").strip()
    if preg:
        items.append({
            "q": f"Is {name} safe to take during pregnancy?",
            "a": (
                f"Pregnancy risk for {name}: {preg}. "
                f"Always talk to your doctor before taking any medicine while pregnant or breastfeeding."
            ),
        })

    items.append({
        "q": f"Is there a generic version of {name}?",
        "a": (
            f"{name_cap} is itself a generic name. Generic versions are widely available "
            f"and may be sold under several brand names: "
            f"{', '.join(drug.brand_names) if drug.brand_names else 'see the brand names listed above'}."
        ),
    })

    return items


@app.route("/<slug>")
@app.route("/<slug>.html")
def drug_detail(slug):
    drug = Drug.query.filter_by(slug=slug).first()
    if not drug:
        # Try matching by brand name — agents often navigate to brand URLs like /advil, /ozempic.
        brand_q = slug.replace('-', ' ').replace('_', ' ')
        brand_hit = Drug.query.filter(Drug.brand_names_json.ilike(f'%"{brand_q}"%')).first()
        if not brand_hit:
            brand_hit = Drug.query.filter(Drug.brand_names_json.ilike(f'%{brand_q}%')).first()
        if brand_hit:
            return redirect(url_for('drug_detail', slug=brand_hit.slug), 301)
        abort(404)
    # Track recently viewed drugs in session
    viewed = session.get("recently_viewed", [])
    if drug.slug in viewed:
        viewed.remove(drug.slug)
    viewed.insert(0, drug.slug)
    viewed = viewed[:10]
    session["recently_viewed"] = viewed
    session.modified = True
    # Fetch recently viewed Drug rows (excluding current page's drug) in session order
    other_slugs = [s for s in viewed if s != drug.slug]
    recently_viewed = []
    if other_slugs:
        recently_viewed = Drug.query.filter(Drug.slug.in_(other_slugs)).all()
        rv_order = {s: i for i, s in enumerate(other_slugs)}
        recently_viewed.sort(key=lambda d: rv_order.get(d.slug, 99))
    reviews = (
        _public_reviews_query()
        .filter(DrugReview.drug_id == drug.id)
        .order_by(DrugReview.helpful_count.desc())
        .limit(20)
        .all()
    )
    related = Drug.query.filter(Drug.generic_name.in_(drug.related_drugs)).all()
    cond_by_slug = {c.slug: c for c in Condition.query.all()}
    drug_conditions = [cond_by_slug[s] for s in drug.conditions_list if s in cond_by_slug]
    saved = False
    if current_user.is_authenticated:
        saved = SavedDrug.query.filter_by(user_id=current_user.id, drug_id=drug.id).first() is not None
    # rating distribution: counts indexed 1..10
    rating_distribution = {i: 0 for i in range(1, 11)}
    for r in _public_reviews_query().filter(DrugReview.drug_id == drug.id).all():
        if 1 <= (r.rating or 0) <= 10:
            rating_distribution[r.rating] += 1
    user_review = None
    if current_user.is_authenticated:
        user_review = DrugReview.query.filter_by(drug_id=drug.id, user_id=current_user.id).first()
    related_news = NewsArticle.query.filter(
        db.or_(
            NewsArticle.title.ilike(f"%{drug.generic_name}%"),
            NewsArticle.body.ilike(f"%{drug.generic_name}%")
        )
    ).order_by(NewsArticle.published_at.desc()).limit(3).all()

    # Fallback: add brand name matches to fill up to 3
    if len(related_news) < 3 and drug.brand_names:
        seen_ids = {a.id for a in related_news}
        for brand in drug.brand_names[:2]:
            extras = NewsArticle.query.filter(
                db.or_(
                    NewsArticle.title.ilike(f"%{brand}%"),
                    NewsArticle.body.ilike(f"%{brand}%")
                )
            ).order_by(NewsArticle.published_at.desc()).limit(2).all()
            for a in extras:
                if a.id not in seen_ids:
                    related_news.append(a)
                    seen_ids.add(a.id)
                    if len(related_news) >= 3:
                        break

    # Final fallback: just recent news
    if not related_news:
        related_news = NewsArticle.query.order_by(NewsArticle.published_at.desc()).limit(3).all()
    related_drugs = []
    if drug.drug_class_id:
        related_drugs = Drug.query.filter(
            Drug.drug_class_id == drug.drug_class_id,
            Drug.id != drug.id
        ).order_by(Drug.generic_name, Drug.id).limit(6).all()
    drug_interactions = DrugInteraction.query.filter(
        (DrugInteraction.drug_a_id == drug.id) | (DrugInteraction.drug_b_id == drug.id)
    ).all()
    faq_items = list(drug.faq or _build_default_faq(drug))
    # Ensure NSAID drugs have an empty-stomach FAQ answer (common benchmark question)
    if drug.drug_class and ('nsaid' in (drug.drug_class.name or '').lower() or 'nonsteroidal' in (drug.drug_class.name or '').lower()):
        if not any('empty stomach' in (item.get('q') or '').lower() for item in faq_items):
            faq_items.append({
                "q": f"Can I take {drug.generic_name} on an empty stomach?",
                "a": (f"It is recommended to take {drug.generic_name} with food, milk, or antacids to help prevent "
                      f"stomach upset. Taking {drug.generic_name} on an empty stomach may increase the risk of "
                      f"nausea, stomach pain, heartburn, and gastrointestinal irritation. If stomach upset occurs, "
                      f"try taking it with a full glass of water and food."),
            })
    avoid_items = _build_avoid_items(drug)
    _ov = DRUG_CONTENT_OVERRIDES.get(drug.generic_name) or DRUG_CONTENT_OVERRIDES.get(drug.generic_name.replace(' ', '-'), {})
    before_taking = _ov.get("before_taking")
    # Apply runtime content overrides so drug pages reflect accurate info even if DB was seeded
    # with incorrect OpenFDA data (e.g. wrong formulation) or generic fallbacks.
    rt_uses = _ov.get("uses") or drug.uses
    rt_warnings = _ov.get("warnings") or drug.warnings
    rt_dosage = _ov.get("dosage") or drug.dosage
    rt_side_effects = _ov.get("side_effects") or drug.side_effects
    rt_description = _ov.get("description") or drug.description
    # Use override if present, otherwise use DB interactions_text but strip paragraphs
    # that reference combination-product brand names (e.g. ZITUVIMET for metformin).
    _COMBO_BRANDS = {'ZITUVIMET', 'JANUMET', 'INVOKAMET', 'XIGDUO', 'SYNJARDY',
                     'KOMBIGLYZE', 'JENTADUETO', 'KAZANO', 'OSENI', 'GLYXAMBI',
                     'STEGLUJAN', 'QTERNMET', 'TRIJARDY', 'SEGLUROMET', 'JARDIANCE',
                     'FARXIGA', 'INVOKANA', 'BYDUREON', 'BYETTA', 'TRULICITY',
                     'OZEMPIC', 'VICTOZA', 'RYBELSUS', 'MOUNJARO', 'WEGOVY'}
    _raw_interactions = _ov.get("interactions_text") or drug.interactions_text or ""
    # If no manual override and the DB field is raw FDA structured table text, suppress it
    # so only the clean inline DrugInteraction widget is shown.
    _RAW_FDA_PATTERNS = (
        re.compile(r'^\s*7\s+DRUG INTERACTIONS\s+See Table'),
        re.compile(r'^\s*7\s+DRUG INTERACTIONS\s+Table'),
        re.compile(r'^ADVERSE REACTIONS\b'),
        re.compile(r'^\s*7\.?\s+DRUG INTERACTIONS\s+[A-Z]'),
    )
    _is_raw_fda = (not _ov.get("interactions_text") and
                   any(p.match(_raw_interactions) for p in _RAW_FDA_PATTERNS))
    if _raw_interactions and not _is_raw_fda:
        _inter_paras = []
        for _p in _raw_interactions.split('\n\n'):
            _p_up = _p.upper()
            if any(b in _p_up for b in _COMBO_BRANDS) and drug.generic_name.upper() not in _p_up[:50]:
                continue
            _inter_paras.append(_p)
        rt_interactions = '\n\n'.join(_inter_paras) or None
    else:
        rt_interactions = None
    return render_template("drug_detail.html", drug=drug, reviews=reviews,
                           before_taking=before_taking,
                           rt_uses=rt_uses, rt_warnings=rt_warnings, rt_dosage=rt_dosage,
                           rt_side_effects=rt_side_effects, rt_description=rt_description,
                           rt_interactions=rt_interactions,
                           related=related, drug_conditions=drug_conditions, saved=saved,
                           rating_distribution=rating_distribution, user_review=user_review,
                           related_news=related_news, related_drugs=related_drugs,
                           drug_interactions=drug_interactions,
                           faq_items=faq_items,
                           avoid_items=avoid_items,
                           recently_viewed=recently_viewed)


def _build_avoid_items(drug):
    """Return a list of {title, reason} avoidance recommendations tailored to the drug's class.

    Class-specific guidance is matched by keyword against the drug's class name; falls
    back to a generic alcohol/driving warning when no class is matched. A generic
    "other medicines with similar ingredients" item is always appended.
    """
    cname = (drug.drug_class.name or "").lower() if drug.drug_class else ""
    items = []
    rules = [
        (("nsaid", "anti-inflammatory"), [
            ("Alcohol", "Drinking alcohol while taking NSAIDs increases the risk of stomach bleeding and ulcers."),
            ("Other NSAIDs", "Avoid combining with other NSAIDs (e.g., aspirin, naproxen) unless directed by your doctor."),
        ]),
        (("ssri", "snri", "antidepressant"), [
            ("Alcohol", "Alcohol can worsen drowsiness and may reduce the effectiveness of the medication."),
            ("MAO inhibitors", "Combining with MAOIs can cause a dangerous reaction known as serotonin syndrome."),
            ("St. John's Wort", "This herbal supplement can increase the risk of serotonin syndrome."),
        ]),
        (("opioid", "narcotic"), [
            ("Alcohol", "Mixing alcohol with opioids can cause severe drowsiness, slowed breathing, and overdose."),
            ("Driving or operating machinery", "Opioids can impair your reactions and judgment until you know how this medicine affects you."),
            ("Other CNS depressants", "Avoid benzodiazepines, sleep aids, and muscle relaxants unless directed."),
        ]),
        (("statin", "hmg-coa"), [
            ("Grapefruit juice", "Grapefruit can raise statin levels in the blood and increase the risk of muscle and liver problems."),
            ("Excessive alcohol", "Heavy alcohol use combined with statins increases the risk of liver damage."),
        ]),
        (("anticoagulant", "blood thinner"), [
            ("NSAIDs and aspirin", "These medications increase the risk of bleeding when combined with anticoagulants."),
            ("Vitamin K rich foods in large amounts", "Sudden changes in leafy green intake can affect how well warfarin-type drugs work."),
            ("Alcohol", "Alcohol can increase bleeding risk and affect anticoagulant levels."),
        ]),
        (("benzodiazepine", "sedative", "hypnotic"), [
            ("Alcohol", "Combining alcohol with sedatives can cause severe drowsiness and breathing problems."),
            ("Driving or operating machinery", "This medicine can impair your reactions until you know how it affects you."),
        ]),
        (("antibiotic",), [
            ("Alcohol", "Alcohol can worsen side effects and, with some antibiotics, cause severe reactions."),
            ("Dairy or antacids near doses", "Some antibiotics are poorly absorbed when taken with calcium, iron, or antacids."),
        ]),
        (("antihistamine",), [
            ("Alcohol", "Alcohol can intensify drowsiness caused by antihistamines."),
            ("Driving or operating machinery", "Until you know how this medicine affects you, avoid activities requiring alertness."),
        ]),
        (("ace inhibitor", "arb", "angiotensin"), [
            ("Potassium supplements and salt substitutes", "These can cause dangerously high potassium levels when combined with ACE inhibitors or ARBs."),
            ("NSAIDs", "NSAIDs may reduce the blood-pressure-lowering effect and increase the risk of kidney problems."),
        ]),
        (("diabetes", "insulin", "biguanide", "sulfonylurea"), [
            ("Alcohol", "Alcohol can cause unpredictable changes in blood sugar and increase the risk of low blood sugar."),
            ("Skipping meals", "Missing meals while taking diabetes medication raises the risk of hypoglycemia."),
        ]),
    ]
    for keywords, additions in rules:
        if any(k in cname for k in keywords):
            items.extend(additions)
            break
    if not items:
        items = [
            ("Alcohol", f"Drinking alcohol while taking {drug.generic_name} may worsen side effects."),
            ("Driving or operating machinery", f"Until you know how {drug.generic_name} affects you, avoid activities requiring full alertness."),
        ]
    items.append((
        "Other medicines with similar ingredients",
        f"Ask a doctor or pharmacist before using other medicines for pain, fever, swelling, or cold/flu symptoms, as they may contain ingredients similar to {drug.generic_name}.",
    ))
    return [{"title": t, "reason": r} for t, r in items]


@app.route("/comments/<slug>/")
@app.route("/comments/<slug>")
@app.route("/answers/support-group/<slug>/")
@app.route("/answers/support-group/<slug>")
@app.route("/<slug>/reviews")
@app.route("/<slug>/reviews.html")
def drug_reviews_page(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    page = _bounded_page_arg()
    condition_filter = _bounded_query_arg('condition', '', 100)
    sort = _bounded_query_arg('sort', 'recent', 20)

    query = _public_reviews_query().filter(DrugReview.drug_id == drug.id)
    if condition_filter:
        query = query.filter(DrugReview.condition_treated == condition_filter)
    if sort == 'helpful':
        query = query.order_by(DrugReview.helpful_count.desc())
    elif sort == 'highest':
        query = query.order_by(DrugReview.rating.desc())
    elif sort == 'lowest':
        query = query.order_by(DrugReview.rating.asc())
    else:
        query = query.order_by(DrugReview.created_at.desc())

    reviews = query.paginate(page=page, per_page=20, error_out=False)
    conditions = (
        _public_reviews_query()
        .filter(DrugReview.drug_id == drug.id)
        .with_entities(DrugReview.condition_treated)
        .distinct()
        .all()
    )
    conditions = [c[0] for c in conditions if c[0]]
    rating_dist = {
        i: _public_reviews_query().filter(
            DrugReview.drug_id == drug.id,
            DrugReview.rating == i,
        ).count()
        for i in range(1, 11)
    }
    related_drugs = []
    if drug.drug_class_id:
        related_drugs = Drug.query.filter(
            Drug.drug_class_id == drug.drug_class_id,
            Drug.id != drug.id
        ).order_by(Drug.avg_rating.desc().nullslast()).limit(6).all()
    faq_items = list(drug.faq or _build_default_faq(drug))
    return render_template("drug_reviews_page.html", drug=drug, reviews=reviews,
                          conditions=conditions, condition_filter=condition_filter,
                          sort=sort, rating_dist=rating_dist,
                          faq_items=faq_items, related_drugs=related_drugs)


@app.route("/<slug>/reviews/new", methods=["GET"])
@app.route("/<slug>/reviews/write", methods=["GET"])
@app.route("/<slug>/reviews/write.html", methods=["GET"])
@login_required
def drug_review_new(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    user_review = DrugReview.query.filter_by(drug_id=drug.id, user_id=current_user.id).first()
    conditions = (
        _public_reviews_query()
        .filter(DrugReview.drug_id == drug.id)
        .with_entities(DrugReview.condition_treated)
        .distinct()
        .all()
    )
    conditions = [c[0] for c in conditions if c[0]]
    return render_template("drug_review_new.html", drug=drug, user_review=user_review,
                           conditions=conditions)


@app.route("/<slug>/review", methods=["POST"])
@login_required
def submit_review(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    try:
        rating = int(request.form.get("rating", 5))
    except (TypeError, ValueError):
        rating = 5
    rating = max(1, min(10, rating))
    title = (request.form.get("title") or "").strip()[:200]
    body = (request.form.get("body") or "").strip()[:1000]
    condition = (request.form.get("condition_treated") or "").strip()[:100]
    if not title or not body or not condition:
        flash("Condition, title, and review text are required.", "danger")
        return redirect(url_for("drug_review_new", slug=slug))
    insert_review = sqlite_insert(DrugReview).values(
        drug_id=drug.id,
        user_id=current_user.id,
        rating=rating,
        title=title,
        body=body,
        condition_treated=condition,
        helpful_count=0,
        created_at=datetime.utcnow(),
    )
    upsert_review = insert_review.on_conflict_do_update(
        index_elements=["drug_id", "user_id"],
        set_={
            "rating": insert_review.excluded.rating,
            "title": insert_review.excluded.title,
            "body": insert_review.excluded.body,
            "condition_treated": insert_review.excluded.condition_treated,
        },
    )
    db.session.execute(upsert_review)
    _refresh_drug_review_stats(drug)
    db.session.commit()
    flash("Your review has been submitted.", "success")
    return redirect(url_for("drug_detail", slug=slug) + "#reviews")


@app.route("/<slug>/review/<int:review_id>/helpful", methods=["POST"])
def review_helpful_vote(slug, review_id):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    vote = (request.values.get("vote") or "yes").lower()
    if vote not in {"yes", "no"}:
        return jsonify({"error": "invalid_vote"}), 400

    # A helpful vote is a yes/no choice, not an unbounded counter button.
    # Authenticated votes are persisted in the existing user-preferences JSON;
    # anonymous votes live in the signed session, a process-local race cache,
    # and a request-time SQLite ledger that survives /restart atomically with
    # the helpful-count update (a full /reset still restores the seed DB).
    with _review_votes_lock:
        review = (
            _public_reviews_query()
            .filter(DrugReview.id == review_id, DrugReview.drug_id == drug.id)
            .first_or_404()
        )
        ledger_user = (
            current_user._get_current_object()
            if current_user.is_authenticated
            else None
        )
        if ledger_user is not None and review.user_id == ledger_user.id:
            return jsonify({"error": "self_vote_not_allowed"}), 403
        if (
            ledger_user is None
            and _previous_review_voter_id() == review.user_id
        ):
            return jsonify({"error": "self_vote_not_allowed"}), 403
        review_identity = _review_vote_identity(review)
        preferences = None
        user_votes = None
        session_votes = None
        vote_key = None
        settings_lock = None
        try:
            if ledger_user is not None:
                settings_lock = _user_settings_lock(ledger_user.id)
                settings_lock.acquire()
                db.session.refresh(ledger_user)
                preferences = ledger_user.preferences.copy()
                user_votes = _prune_review_votes(
                    preferences.get(_REVIEW_VOTES_PREFERENCE),
                    _MAX_REVIEW_VOTES,
                )
                previous_vote = user_votes.pop(str(review_id), None)
                previous_vote = user_votes.get(
                    review_identity, previous_vote
                )
            else:
                raw_session_votes = session.get(_REVIEW_VOTES_SESSION)
                session_votes = _valid_review_votes(
                    raw_session_votes
                )
                server_backed_votes = _server_backed_session_vote_ids(
                    raw_session_votes
                )
                review_session_key = _review_session_key(create=True)
                server_record = _server_review_vote_record(
                    review_session_key, review_identity
                )
                if server_record is not None and server_record[1] is not None:
                    return jsonify({"error": "vote_already_claimed"}), 409
                if server_record is not None:
                    server_backed_votes.add(review_identity)
                if review_session_key:
                    for key, stored_vote in _review_votes.items():
                        if key[:2] == ("session", review_session_key):
                            _remember_review_vote(
                                session_votes,
                                key[-1],
                                stored_vote,
                            )
                            server_backed_votes.add(key[-1])
                server_votes = _server_review_votes(
                    review_session_key
                )
                for stored_identity, stored_vote in server_votes.items():
                    _remember_review_vote(
                        session_votes, stored_identity, stored_vote
                    )
                    server_backed_votes.add(stored_identity)
                session_votes = _prune_review_votes(session_votes)
                if review_session_key:
                    for key in [
                        key
                        for key in _review_votes
                        if key[:2] == ("session", review_session_key)
                        and key[-1] not in session_votes
                    ]:
                        del _review_votes[key]
                vote_key = (
                    "session", review_session_key, review_identity
                )
                legacy_previous_vote = session_votes.pop(
                    str(review_id), None
                )
                legacy_previous_vote = session_votes.get(
                    review_identity, legacy_previous_vote
                )
                previous_vote = (
                    server_record[0]
                    if server_record is not None
                    else None
                    if review_identity in server_backed_votes
                    else legacy_previous_vote
                )
                if (
                    previous_vote is None
                    and review_identity not in session_votes
                    and len(session_votes) >= _MAX_REVIEW_VOTES_PER_SESSION
                ):
                    return jsonify({"error": "vote_limit_reached"}), 429
                if previous_vote is None:
                    candidate_votes = session_votes.copy()
                    _remember_review_vote(
                        candidate_votes,
                        review_identity,
                        vote,
                        _MAX_REVIEW_VOTES_PER_SESSION,
                    )
                    if not _review_votes_fit_session(
                        candidate_votes,
                        server_backed_votes | {review_identity},
                    ):
                        return jsonify({"error": "vote_limit_reached"}), 429
                    session_votes = candidate_votes
            if (
                ledger_user is not None
                and previous_vote is None
                and len(user_votes) >= _MAX_REVIEW_VOTES_PER_SESSION
            ):
                return jsonify({"error": "vote_limit_reached"}), 429
            delta = int(vote == "yes") - int(previous_vote == "yes")

            if delta:
                updated = DrugReview.query.filter(
                    DrugReview.id == review.id
                ).update(
                    {
                        DrugReview.helpful_count: db.func.max(
                            0,
                            db.func.coalesce(
                                DrugReview.helpful_count, 0
                            ) + delta,
                        )
                    },
                    synchronize_session=False,
                )
                if not updated:
                    db.session.rollback()
                    return jsonify({"error": "review_not_found"}), 404

            if ledger_user is not None:
                remembered = _remember_review_vote(
                    user_votes,
                    review_identity,
                    vote,
                    _MAX_REVIEW_VOTES_PER_SESSION,
                )
                if not remembered:
                    db.session.rollback()
                    return jsonify({"error": "vote_limit_reached"}), 429
                preferences[_REVIEW_VOTES_PREFERENCE] = user_votes
                ledger_user.set_preferences(preferences)
                db.session.commit()
            else:
                _remember_review_vote(
                    session_votes,
                    review_identity,
                    vote,
                    _MAX_REVIEW_VOTES_PER_SESSION,
                )
                if not _remember_server_review_vote(
                    review_session_key, review_identity, vote
                ):
                    db.session.rollback()
                    return jsonify({"error": "vote_limit_reached"}), 429
                db.session.commit()
                server_backed_votes.add(review_identity)
                session[_REVIEW_VOTES_SESSION] = _encode_session_review_votes(
                    session_votes, server_backed_votes
                )
                _review_votes[vote_key] = vote
                while len(_review_votes) > _MAX_REVIEW_VOTES:
                    del _review_votes[next(iter(_review_votes))]

            current_count = (
                db.session.query(DrugReview.helpful_count)
                .filter(DrugReview.id == review_id)
                .scalar()
            )
            if current_count is None:
                if vote_key is not None:
                    _review_votes.pop(vote_key, None)
                return jsonify({"error": "review_not_found"}), 404
        finally:
            if settings_lock is not None:
                settings_lock.release()
    return jsonify({"votes": current_count, "review_id": review_id})


@app.route("/advanced-search")
@app.route("/search")
def search():
    q = _bounded_query_arg("q").strip()
    class_slug = _bounded_query_arg(
        "class", max_length=_MAX_FILTER_TEXT_LENGTH
    )
    cond_slug = _bounded_query_arg(
        "condition", max_length=_MAX_FILTER_TEXT_LENGTH
    )
    avail = _bounded_query_arg("availability", max_length=20)
    page = _bounded_page_arg()
    per_page = 20

    drugs = Drug.query
    if class_slug:
        cls = DrugClass.query.filter_by(slug=class_slug).first()
        if cls:
            drugs = drugs.filter(Drug.drug_class_id == cls.id)
    if avail:
        drugs = drugs.filter(Drug.availability == avail)
    drugs = drugs.all()

    if cond_slug:
        drugs = [d for d in drugs if cond_slug in d.conditions_list]

    tokens = tokenize(q)
    matched_condition = None
    matched_class = None
    if tokens:
        # Check if query matches a condition or drug class name
        ql = q.lower()
        for c in Condition.query.all():
            if c.name.lower() == ql or c.slug == ql:
                matched_condition = c
                break
        if not matched_condition:
            for c in Condition.query.all():
                if ql in c.name.lower() or ql in (c.slug or ""):
                    matched_condition = c
                    break
        if not matched_condition:
            for cls in DrugClass.query.all():
                if cls.name.lower() == ql or cls.slug == ql:
                    matched_class = cls
                    break
            if not matched_class:
                for cls in DrugClass.query.all():
                    if ql in cls.name.lower() or ql in (cls.slug or ""):
                        matched_class = cls
                        break

        scored = [(score_drug(d, tokens), d) for d in drugs]
        scored = [(s, d) for s, d in scored if s > 0]
        existing_ids = {d.id for _, d in scored}

        # Explicit brand-name match: include drugs whose brand names contain
        # any query token (and bump the score of already-scored drugs).
        for d in drugs:
            brand_blob = " ".join(d.brand_names).lower() if d.brand_names else ""
            if any(t in brand_blob for t in tokens):
                if d.id in existing_ids:
                    scored = [(s + 2, dd) if dd.id == d.id else (s, dd) for s, dd in scored]
                else:
                    scored.append((2, d))
                    existing_ids.add(d.id)

        # Boost drugs matching the condition/class
        if matched_condition:
            extras = [d for d in drugs if matched_condition.slug in d.conditions_list]
            for d in extras:
                if d.id not in existing_ids:
                    scored.append((1, d))
                    existing_ids.add(d.id)
        if matched_class:
            extras = [d for d in drugs if d.drug_class_id == matched_class.id]
            for d in extras:
                if d.id not in existing_ids:
                    scored.append((1, d))
                    existing_ids.add(d.id)

        scored.sort(key=lambda x: (-x[0], x[1].generic_name))
        results = [d for _, d in scored]
    else:
        # Empty query: show popular drugs (most reviewed)
        if not (class_slug or cond_slug or avail):
            drugs = Drug.query.order_by(Drug.review_count.desc()).all()
        results = sorted(drugs, key=lambda d: -d.review_count) if not q else sorted(drugs, key=lambda d: d.generic_name)

    # Conditions and News result groups (only when there's a query and no
    # restrictive drug-only filters are applied).
    condition_results = []
    news_results = []
    if q:
        ql = q.lower()
        for c in Condition.query.all():
            if ql in c.name.lower() or ql in (c.slug or "").lower() \
               or ql in (c.description or "").lower():
                condition_results.append(c)
        condition_results.sort(key=lambda c: c.name)
        condition_results = condition_results[:10]

        for a in NewsArticle.query.all():
            if ql in a.title.lower() or ql in (a.body or "").lower() \
               or ql in (a.category or "").lower():
                news_results.append(a)
        news_results.sort(key=lambda a: a.published_at or datetime.min, reverse=True)
        news_results = news_results[:10]

    # "Did you mean?" suggestions: 3 closest drug names by edit-distance
    # ratio whenever the query produced zero drug hits.
    suggestions = []
    if q and not results:
        all_names = [d.generic_name for d in Drug.query.all()]
        suggestions = difflib.get_close_matches(q.lower(),
                                                [n.lower() for n in all_names],
                                                n=3, cutoff=0.5)
        # Map back to canonical capitalisation.
        lower_to_orig = {n.lower(): n for n in all_names}
        suggestions = [lower_to_orig.get(s, s) for s in suggestions]

    # "Related searches": fuzzy-near drug names, excluding any name already
    # present in the result set. Only computed when a query is present.
    related_searches = []
    if q:
        result_names_lower = {d.generic_name.lower() for d in results}
        all_names = [d.generic_name for d in Drug.query.all()]
        candidates = [n for n in all_names if n.lower() not in result_names_lower]
        matches = difflib.get_close_matches(q.lower(),
                                            [n.lower() for n in candidates],
                                            n=6, cutoff=0.4)
        lower_to_orig = {n.lower(): n for n in candidates}
        related_searches = [lower_to_orig.get(s, s) for s in matches]

    # Exact drug match: generic name or slug equals query
    exact_drug = None
    if q:
        ql = q.lower().strip()
        exact_drug = Drug.query.filter(
            db.or_(
                db.func.lower(Drug.generic_name) == ql,
                Drug.slug == ql.replace(" ", "-"),
            )
        ).first()
        if not exact_drug and results:
            top = results[0]
            if top.generic_name.lower() == ql or top.slug == ql.replace(" ", "-"):
                exact_drug = top

    total = len(results)
    total_all = total + len(condition_results) + len(news_results)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    page_results = results[(page - 1) * per_page: page * per_page]

    classes = DrugClass.query.order_by(DrugClass.name).all()
    conditions = Condition.query.order_by(Condition.name).all()
    return render_template("search.html", q=q, results=page_results, total=total,
                           total_all=total_all,
                           condition_results=condition_results,
                           news_results=news_results,
                           classes=classes, conditions=conditions,
                           class_slug=class_slug, cond_slug=cond_slug, avail=avail,
                           page=page, total_pages=total_pages,
                           suggestions=suggestions,
                           related_searches=related_searches,
                           matched_condition=matched_condition,
                           matched_class=matched_class,
                           exact_drug=exact_drug)


@app.route("/api/autocomplete")
def autocomplete():
    q = _bounded_query_arg(
        "q", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip().lower()
    if len(q) < 2:
        return jsonify([])
    # Search generic names
    drugs = Drug.query.filter(Drug.generic_name.ilike(f"{q}%")).limit(5).all()
    # Also search brand names within the list
    results = []
    for d in drugs:
        results.append({"type": "drug", "name": d.generic_name, "url": f"/{d.slug}.html", "label": d.generic_name.capitalize()})
        for brand in (d.brand_names or [])[:1]:  # only first brand
            if brand.lower().startswith(q):
                results.append({"type": "brand", "name": brand, "url": f"/{d.slug}.html", "label": f"{brand} ({d.generic_name})"})
    # Also search conditions
    conditions = Condition.query.filter(Condition.name.ilike(f"%{q}%")).limit(3).all()
    for c in conditions:
        results.append({"type": "condition", "name": c.name, "url": f"/condition/{c.slug}", "label": c.name})
    return jsonify(results[:8])


@app.route("/interaction-checker", methods=["GET", "POST"])
@app.route("/interaction-checker/", methods=["GET", "POST"])
@app.route("/drug_interactions.html", methods=["GET", "POST"])
@app.route("/drug-interactions/", methods=["GET", "POST"])
@app.route("/drug-interactions", methods=["GET", "POST"])
def interaction_checker():
    drugs = Drug.query.order_by(Drug.generic_name).all()
    drugs_input = None
    interactions = None
    unrecognized = []
    summary = None
    # Pre-populate from URL param (linked from drug detail pages, e.g. ?drug=ibuprofen)
    prefill_slug = _bounded_query_arg(
        "drug", max_length=_MAX_INTERACTION_NAME_LENGTH
    ).strip()
    prefill = ""
    if prefill_slug:
        d = Drug.query.filter_by(slug=prefill_slug).first()
        if not d:
            d = Drug.query.filter(db.func.lower(Drug.generic_name) == prefill_slug.lower()).first()
        prefill = d.generic_name if d else prefill_slug
    # Support GET with multiple drugs: ?drugs[]=warfarin&drugs[]=aspirin or ?drugs=warfarin,aspirin
    get_drugs = (
        request.args.getlist("drugs[]")
        + request.args.getlist("drugs")
    )
    if len(get_drugs) == 1 and "," in get_drugs[0]:
        get_drugs = [d.strip() for d in get_drugs[0].split(",")]
    add_drug = _bounded_query_arg(
        "add", max_length=_MAX_INTERACTION_NAME_LENGTH
    ).strip()
    if request.method == "GET" and prefill and add_drug:
        request_override = [prefill, add_drug]
    elif request.method == "GET" and len(get_drugs) >= 2:
        # Simulate a POST with these drugs
        request_override = get_drugs
    else:
        request_override = None
    if request.method == "POST" or request_override:
        raw = request_override if request_override else request.form.getlist("drugs")
        drugs_input = _normalize_interaction_names(raw)
        if drugs_input is None:
            abort(400)
        resolved = []
        seen_ids = set()
        for n in drugs_input:
            low = n.lower()
            d = Drug.query.filter(db.func.lower(Drug.generic_name) == low).first()
            if not d:
                for cand in drugs:
                    if low in [b.lower() for b in cand.brand_names]:
                        d = cand
                        break
            if d and d.id not in seen_ids:
                resolved.append(d)
                seen_ids.add(d.id)
            elif not d:
                unrecognized.append(n)

        interactions = []
        pair_keys = set()
        for a, b in combinations(resolved, 2):
            rec = DrugInteraction.query.filter(
                ((DrugInteraction.drug_a_id == a.id) & (DrugInteraction.drug_b_id == b.id)) |
                ((DrugInteraction.drug_a_id == b.id) & (DrugInteraction.drug_b_id == a.id))
            ).first()
            key = tuple(sorted([a.id, b.id]))
            if key in pair_keys:
                continue
            pair_keys.add(key)
            if rec:
                interactions.append({
                    "drug_a": a,
                    "drug_b": b,
                    "severity": rec.severity,
                    "description": rec.description,
                })
        # Sort major -> moderate -> minor
        order = {"major": 0, "moderate": 1, "minor": 2}
        interactions.sort(key=lambda it: order.get(it["severity"], 99))
        summary = {
            "total": len(interactions),
            "major": sum(1 for it in interactions if it["severity"] == "major"),
            "moderate": sum(1 for it in interactions if it["severity"] == "moderate"),
            "minor": sum(1 for it in interactions if it["severity"] == "minor"),
        }
        food_interactions, alcohol_interactions = _lifestyle_interactions(resolved)
        # If "alcohol" was explicitly entered, fold its interactions into main results
        if any(n.lower() == "alcohol" for n in drugs_input or []):
            for alc in alcohol_interactions:
                interactions.append({
                    "drug_a": alc["drug"],
                    "drug_b": None,
                    "drug_b_name": "Alcohol",
                    "severity": alc["severity"],
                    "description": alc["description"],
                })
            alcohol_interactions = []
            order = {"major": 0, "moderate": 1, "minor": 2}
            interactions.sort(key=lambda it: order.get(it["severity"], 99))
            summary = {
                "total": len(interactions),
                "major": sum(1 for it in interactions if it["severity"] == "major"),
                "moderate": sum(1 for it in interactions if it["severity"] == "moderate"),
                "minor": sum(1 for it in interactions if it["severity"] == "minor"),
            }
            unrecognized = [n for n in unrecognized if n.lower() != "alcohol"]
    else:
        food_interactions, alcohol_interactions = [], []
    return render_template(
        "interaction_checker.html",
        drugs=drugs,
        drugs_input=drugs_input,
        interactions=interactions,
        unrecognized=unrecognized,
        summary=summary,
        prefill=prefill,
        food_interactions=food_interactions,
        alcohol_interactions=alcohol_interactions,
    )


# Hardcoded clinical reference data for drug-food / drug-alcohol interactions.
# Keyed by (lowercased) generic name and by (lowercased) drug-class name.
_FOOD_BY_GENERIC = {
    "warfarin": [
        {"item": "Vitamin K-rich foods (kale, spinach, broccoli)", "severity": "moderate",
         "description": "Large or fluctuating intake of leafy greens high in vitamin K can antagonize warfarin's anticoagulant effect and destabilize INR. Keep vitamin K intake consistent rather than eliminating these foods."},
        {"item": "Cranberry juice", "severity": "moderate",
         "description": "Cranberry juice may potentiate warfarin and raise INR, increasing bleeding risk. Limit intake or avoid large quantities while on warfarin."},
    ],
    "ibuprofen": [
        {"item": "High-sodium foods", "severity": "minor",
         "description": "NSAIDs can cause fluid retention and elevate blood pressure; high-sodium meals compound this effect, particularly in patients with hypertension or heart failure."},
    ],
}

_FOOD_BY_CLASS = {
    "nsaids": [
        {"item": "High-sodium foods", "severity": "minor",
         "description": "NSAIDs promote sodium and water retention. Diets high in sodium can amplify blood-pressure increases and edema, especially in older adults or those with cardiac disease."},
    ],
    "statins": [
        {"item": "Grapefruit juice", "severity": "major",
         "description": "Grapefruit inhibits intestinal CYP3A4 and substantially raises serum levels of simvastatin, lovastatin, and atorvastatin. Elevated exposure increases the risk of myopathy and rhabdomyolysis."},
    ],
    "ssris": [
        {"item": "Tyramine-rich foods (aged cheese, cured meats)", "severity": "minor",
         "description": "While SSRIs are safer than MAOIs with tyramine, large tyramine loads can occasionally precipitate hypertensive or serotonergic symptoms in susceptible patients."},
    ],
    "anticoagulants": [
        {"item": "Vitamin K-rich foods (kale, spinach, broccoli)", "severity": "moderate",
         "description": "Vitamin K antagonizes warfarin-type anticoagulants. Keep daily vitamin K intake consistent to maintain stable INR; abrupt changes alter anticoagulant control."},
    ],
    "ace inhibitors": [
        {"item": "Potassium-rich foods (bananas, oranges, salt substitutes)", "severity": "moderate",
         "description": "ACE inhibitors reduce aldosterone-mediated potassium excretion. Excess dietary potassium, especially with salt substitutes, can produce clinically significant hyperkalemia."},
    ],
}

_ALCOHOL_BY_GENERIC = {
    "metronidazole": {"severity": "major",
        "description": "Metronidazole with alcohol can produce a disulfiram-like reaction with flushing, nausea, vomiting, tachycardia, and headache. Avoid alcohol during therapy and for at least 48 hours after the last dose."},
    "warfarin": {"severity": "major",
        "description": "Acute heavy alcohol intake inhibits warfarin metabolism and raises INR with bleeding risk; chronic use induces metabolism and reduces effect. Either pattern destabilizes anticoagulation."},
    "acetaminophen": {"severity": "moderate",
        "description": "Chronic alcohol use induces CYP2E1, increasing formation of acetaminophen's hepatotoxic metabolite (NAPQI). Combination significantly raises the risk of acute liver injury."},
    "metformin": {"severity": "moderate",
        "description": "Alcohol increases the risk of lactic acidosis in patients taking metformin, especially in those who drink heavily. Alcohol can also cause hypoglycemia or hyperglycemia and masks warning symptoms. Limit or avoid alcohol while taking metformin."},
}

_ALCOHOL_BY_CLASS = {
    "nsaids": {"severity": "major",
        "description": "Combining NSAIDs with alcohol substantially increases the risk of gastrointestinal bleeding, ulceration, and renal injury. Avoid or minimize alcohol while taking NSAIDs."},
    "ssris": {"severity": "moderate",
        "description": "SSRIs combined with alcohol increase central nervous system depression, sedation, and impaired judgment. Alcohol may also worsen depressive symptoms and reduce SSRI efficacy."},
    "benzodiazepines": {"severity": "major",
        "description": "Benzodiazepines plus alcohol cause additive CNS and respiratory depression. The combination can produce profound sedation, respiratory arrest, and death."},
    "opioids": {"severity": "major",
        "description": "Opioids and alcohol both depress the CNS and respiratory drive. Concurrent use markedly increases the risk of fatal respiratory depression and overdose."},
    "anticoagulants": {"severity": "major",
        "description": "Alcohol affects both anticoagulant metabolism and platelet function, increasing the risk of major bleeding. Patients should limit intake and discuss safe thresholds with their clinician."},
    "antihistamines": {"severity": "moderate",
        "description": "First-generation antihistamines combined with alcohol produce additive sedation and psychomotor impairment, raising the risk of falls and motor-vehicle accidents."},
    "antidiabetics": {"severity": "moderate",
        "description": "Alcohol can cause hypoglycemia (especially fasting) and impair recognition of warning symptoms. Sulfonylureas and insulin carry the greatest risk."},
}


def _lifestyle_interactions(resolved_drugs):
    """Return (food_interactions, alcohol_interactions) for the given Drug rows.

    Each food entry is {drug, item, severity, description}; each alcohol entry
    is {drug, severity, description}. Lookups are by lowercased generic name
    and drug-class name against hardcoded reference tables; drugs without
    matches contribute nothing. Lists are sorted major -> moderate -> minor,
    deduplicated per (drug, item) for food and one entry per drug for alcohol.
    """
    sev_order = {"major": 0, "moderate": 1, "minor": 2}
    food, alcohol = [], []
    seen_food = set()
    seen_alc = set()
    for d in resolved_drugs:
        gname = (d.generic_name or "").lower()
        cname = (d.drug_class.name or "").lower() if d.drug_class else ""
        candidates = list(_FOOD_BY_GENERIC.get(gname, []))
        candidates.extend(_FOOD_BY_CLASS.get(cname, []))
        for entry in candidates:
            key = (d.id, entry["item"])
            if key in seen_food:
                continue
            seen_food.add(key)
            food.append({"drug": d, **entry})
        alc = _ALCOHOL_BY_GENERIC.get(gname) or _ALCOHOL_BY_CLASS.get(cname)
        if alc and d.id not in seen_alc:
            seen_alc.add(d.id)
            alcohol.append({"drug": d, **alc})
    food.sort(key=lambda x: sev_order.get(x["severity"], 99))
    alcohol.sort(key=lambda x: sev_order.get(x["severity"], 99))
    return food, alcohol


@app.route("/api/interaction-check", methods=["POST"])
@csrf.exempt
def api_interaction_check():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400
    raw_names = _normalize_interaction_names(data.get("drugs", []))
    if raw_names is None:
        return jsonify({
            "error": "invalid_drugs",
            "max_drugs": _MAX_INTERACTION_DRUGS,
            "max_name_length": _MAX_INTERACTION_NAME_LENGTH,
        }), 400
    names = []
    seen_names = set()
    for raw_name in raw_names:
        name = raw_name.lower()
        if name not in seen_names:
            names.append(name)
            seen_names.add(name)
    has_alcohol = "alcohol" in names
    names = [n for n in names if n != "alcohol"]
    # normalize: try matching by generic name or brand
    matched = []
    matched_ids = set()
    name_to_drug = {}
    all_drugs = Drug.query.all()
    for n in names:
        d = Drug.query.filter(db.func.lower(Drug.generic_name) == n).first()
        if not d:
            # try brand match
            for cand in all_drugs:
                brands = [b.lower() for b in cand.brand_names]
                if n in brands:
                    d = cand
                    break
        if d:
            if d.id not in matched_ids:
                matched.append(d)
                matched_ids.add(d.id)
            name_to_drug[n] = d
    interactions = []
    pair_keys = set()
    no_interaction = []
    for a, b in combinations(matched, 2):
        # Try a-b and b-a
        rec = DrugInteraction.query.filter(
            ((DrugInteraction.drug_a_id == a.id) & (DrugInteraction.drug_b_id == b.id)) |
            ((DrugInteraction.drug_a_id == b.id) & (DrugInteraction.drug_b_id == a.id))
        ).first()
        key = tuple(sorted([a.generic_name, b.generic_name]))
        if key in pair_keys:
            continue
        pair_keys.add(key)
        if rec:
            interactions.append({
                "drug_a": a.generic_name,
                "drug_b": b.generic_name,
                "severity": rec.severity,
                "description": rec.description,
            })
        else:
            no_interaction.append([a.generic_name, b.generic_name])
    if has_alcohol:
        _, alcohol_hits = _lifestyle_interactions(matched)
        for hit in alcohol_hits:
            interactions.append({
                "drug_a": hit["drug"].generic_name,
                "drug_b": "alcohol",
                "severity": hit["severity"],
                "description": hit["description"],
            })
    return jsonify({
        "interactions": interactions,
        "drugs_checked": [d.generic_name for d in matched] + (["alcohol"] if has_alcohol else []),
        "unrecognized": [n for n in names if n not in name_to_drug],
        "no_interaction_pairs": no_interaction,
    })


@app.route("/drug-identifier.html")
@app.route("/drug-identifier")
@app.route("/pill_identification.html")
@app.route("/pill-identifier.html")
@app.route("/pill-identifier")
def pill_identifier():
    # When GET params are present, process as a search (same logic as pill_identifier_results)
    imprint = _bounded_query_arg(
        "imprint", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    shape = _bounded_query_arg(
        "shape", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    color = _bounded_query_arg(
        "color", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    shapes = sorted({i.shape for i in DrugImage.query.all() if i.shape})
    colors = sorted({i.color for i in DrugImage.query.all() if i.color})
    if not imprint and not shape and not color:
        return render_template("pill_identifier.html", shapes=shapes, colors=colors, results=None)
    q = DrugImage.query.order_by(DrugImage.id)
    if shape:
        q = q.filter(db.func.lower(DrugImage.shape) == shape.lower())
    if color:
        q = q.filter(db.func.lower(DrugImage.color) == color.lower())
    candidates = q.all()
    if imprint:
        def _norm(s):
            return re.sub(r"[\s\-]+", "", (s or "")).lower()
        needle = _norm(imprint)
        results = [r for r in candidates if needle in _norm(r.imprint)]
    else:
        results = candidates
    return render_template("pill_identifier.html", shapes=shapes, colors=colors,
                           results=results, imprint=imprint, shape=shape, color=color)


@app.route("/pill-identifier-results")
def pill_identifier_results():
    imprint = _bounded_query_arg(
        "imprint", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    shape = _bounded_query_arg(
        "shape", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    color = _bounded_query_arg(
        "color", max_length=_MAX_FILTER_TEXT_LENGTH
    ).strip()
    q = DrugImage.query.order_by(DrugImage.id)
    if shape:
        q = q.filter(db.func.lower(DrugImage.shape) == shape.lower())
    if color:
        q = q.filter(db.func.lower(DrugImage.color) == color.lower())
    candidates = q.all()
    if imprint:
        # Partial, case-insensitive match that ignores spaces and hyphens so
        # "I-2", "I 2", and "i2" all match a stored imprint of "I-2".
        def _norm(s):
            return re.sub(r"[\s\-]+", "", (s or "")).lower()
        needle = _norm(imprint)
        results = [r for r in candidates if needle in _norm(r.imprint)]
    else:
        results = candidates
    shapes = sorted({i.shape for i in DrugImage.query.all() if i.shape})
    colors = sorted({i.color for i in DrugImage.query.all() if i.color})
    return render_template("pill_identifier.html", shapes=shapes, colors=colors,
                           results=results, imprint=imprint, shape=shape, color=color)


@app.route("/condition/<slug>")
@app.route("/condition/<slug>.html")
@app.route("/conditions/<slug>.html")
@app.route("/conditions/<slug>")
def condition_page(slug):
    # Normalize slug: agents may use hyphens where DB stores underscores (or vice versa).
    cond = Condition.query.filter_by(slug=slug).first()
    if cond is None:
        alt = slug.replace('-', '_') if '-' in slug else slug.replace('_', '-')
        cond = Condition.query.filter_by(slug=alt).first()
    if cond is None:
        from flask import abort
        abort(404)
    links = DrugCondition.query.filter_by(condition_id=cond.id).all()
    drugs = [Drug.query.get(l.drug_id) for l in links]
    drugs = [d for d in drugs if d]
    sort = _bounded_query_arg("sort", "rating", 20).lower()
    if sort == "name":
        drugs.sort(key=lambda d: d.generic_name)
    else:
        sort = "rating"
        drugs.sort(key=lambda d: (-(d.avg_rating or 0), d.generic_name))
    # Group drugs by drug class for the "Standard treatments" view.
    by_class = {}
    for d in drugs:
        cls = d.drug_class.name if d.drug_class else 'Other'
        by_class.setdefault(cls, []).append(d)
    drugs_by_class = sorted(by_class.items(), key=lambda kv: (kv[0] == 'Other', kv[0].lower()))
    # Related conditions: other conditions that share at least one drug with this one.
    drug_ids = [d.id for d in drugs]
    related = []
    if drug_ids:
        shared_rows = (
            db.session.query(DrugCondition.condition_id, db.func.count(DrugCondition.drug_id).label('shared'))
            .filter(DrugCondition.drug_id.in_(drug_ids))
            .filter(DrugCondition.condition_id != cond.id)
            .group_by(DrugCondition.condition_id)
            .order_by(db.text('shared DESC'))
            .limit(8)
            .all()
        )
        for cid, _shared in shared_rows:
            other = Condition.query.get(cid)
            if other is not None:
                related.append(other)
    if not related:
        related = (
            Condition.query.filter(Condition.id != cond.id)
            .order_by(Condition.drug_count.desc())
            .limit(8)
            .all()
        )
    return render_template(
        "condition.html",
        condition=cond,
        drugs=drugs,
        drugs_by_class=drugs_by_class,
        sort=sort,
        related_conditions=related,
    )


CLASS_DESCRIPTIONS = {
    "NSAID": "Nonsteroidal anti-inflammatory drugs (NSAIDs) reduce pain, fever, and inflammation by blocking cyclooxygenase enzymes.",
    "NSAIDs": "Nonsteroidal anti-inflammatory drugs (NSAIDs) reduce pain, fever, and inflammation by blocking cyclooxygenase enzymes.",
    "SSRI": "Selective serotonin reuptake inhibitors (SSRIs) increase serotonin levels in the brain and are used to treat depression and anxiety disorders.",
    "SSRIs": "Selective serotonin reuptake inhibitors (SSRIs) increase serotonin levels in the brain and are used to treat depression and anxiety disorders.",
    "SNRI": "Serotonin-norepinephrine reuptake inhibitors (SNRIs) raise serotonin and norepinephrine levels, used for depression, anxiety, and chronic pain.",
    "ACE Inhibitor": "ACE inhibitors block the angiotensin-converting enzyme to lower blood pressure and treat heart failure.",
    "ACE Inhibitors": "ACE inhibitors block the angiotensin-converting enzyme to lower blood pressure and treat heart failure.",
    "ARB": "Angiotensin II receptor blockers (ARBs) relax blood vessels by blocking angiotensin II, used to treat hypertension and heart failure.",
    "Beta Blocker": "Beta blockers slow the heart rate and lower blood pressure by blocking adrenaline effects on beta receptors.",
    "Beta Blockers": "Beta blockers slow the heart rate and lower blood pressure by blocking adrenaline effects on beta receptors.",
    "Calcium Channel Blocker": "Calcium channel blockers relax blood vessels and reduce the heart's workload by blocking calcium entry into cardiac and smooth muscle cells.",
    "Statin": "Statins lower LDL cholesterol by inhibiting HMG-CoA reductase in the liver, reducing the risk of cardiovascular events.",
    "Statins": "Statins lower LDL cholesterol by inhibiting HMG-CoA reductase in the liver, reducing the risk of cardiovascular events.",
    "PPI": "Proton pump inhibitors (PPIs) suppress stomach acid production by blocking the H+/K+ ATPase pump, used for GERD and ulcers.",
    "Proton Pump Inhibitor": "Proton pump inhibitors (PPIs) suppress stomach acid production by blocking the H+/K+ ATPase pump, used for GERD and ulcers.",
    "Antibiotic": "Antibiotics kill or inhibit bacteria and are used to treat bacterial infections.",
    "Antibiotics": "Antibiotics kill or inhibit bacteria and are used to treat bacterial infections.",
    "Antihistamine": "Antihistamines block histamine receptors to relieve allergy symptoms such as sneezing, itching, and runny nose.",
    "Antihistamines": "Antihistamines block histamine receptors to relieve allergy symptoms such as sneezing, itching, and runny nose.",
    "Benzodiazepine": "Benzodiazepines enhance GABA activity in the brain to produce calming effects, used for anxiety, insomnia, and seizures.",
    "Opioid": "Opioids bind to opioid receptors to relieve moderate to severe pain; they carry risk of dependence and respiratory depression.",
    "Opioids": "Opioids bind to opioid receptors to relieve moderate to severe pain; they carry risk of dependence and respiratory depression.",
    "Corticosteroid": "Corticosteroids reduce inflammation and suppress the immune response, used for asthma, allergies, and autoimmune conditions.",
    "Diuretic": "Diuretics increase urine output to remove excess fluid, used for hypertension, heart failure, and edema.",
    "Biguanide": "Biguanides such as metformin lower blood glucose by reducing hepatic glucose production, used as first-line therapy for type 2 diabetes.",
}


# Extended, multi-paragraph profiles for major drug classes. Each entry has:
#   overview     - "What are X?" mechanism-of-action paragraph
#   uses         - "What are X used for?" paragraph
#   side_effects - list of common side effects shared across the class
# Lookup by class name OR singular form (stripping trailing 's').
DRUG_CLASS_DESCRIPTIONS_EXTENDED = {
    "Benzodiazepines": {
        "overview": (
            "Benzodiazepines are central nervous system depressants that enhance the activity of "
            "gamma-aminobutyric acid (GABA), the brain's main inhibitory neurotransmitter. By binding to "
            "a specific site on the GABA-A receptor, they increase the frequency with which chloride "
            "channels open in response to GABA, producing sedation, anxiolysis, muscle relaxation, and "
            "anticonvulsant effects. Individual benzodiazepines differ mainly in onset and duration of "
            "action, which determines whether a given drug is preferred for acute anxiety, panic attacks, "
            "alcohol withdrawal, status epilepticus, or short-term insomnia."
        ),
        "uses": (
            "Benzodiazepines are most often prescribed for the short-term management of generalized "
            "anxiety disorder, panic disorder, and acute situational anxiety. They are also used to "
            "control acute seizures and status epilepticus, manage alcohol and sedative withdrawal, "
            "produce sedation for medical procedures, treat severe insomnia for limited periods, and "
            "relieve muscle spasm. Because of the risk of tolerance, dependence, and withdrawal, "
            "guidelines generally recommend the lowest effective dose for the shortest duration."
        ),
        "side_effects": [
            "Drowsiness and sedation",
            "Dizziness and unsteadiness",
            "Impaired coordination and falls (especially in older adults)",
            "Memory problems and anterograde amnesia",
            "Slowed reaction time and impaired driving",
            "Confusion and cognitive slowing",
            "Tolerance, physical dependence, and withdrawal on abrupt discontinuation",
            "Respiratory depression when combined with opioids or alcohol",
        ],
    },
    "SSRIs": {
        "overview": (
            "Selective serotonin reuptake inhibitors (SSRIs) block the serotonin transporter on "
            "presynaptic neurons, increasing the amount of serotonin available in the synapse. Over "
            "several weeks, this leads to downstream adaptations in serotonin receptor signaling that "
            "are thought to underlie their antidepressant and anxiolytic effects. SSRIs are the most "
            "widely prescribed class of antidepressants because they are generally better tolerated and "
            "considerably safer in overdose than older tricyclic antidepressants and MAO inhibitors."
        ),
        "uses": (
            "SSRIs are first-line therapy for major depressive disorder and most anxiety disorders, "
            "including generalized anxiety disorder, panic disorder, social anxiety disorder, "
            "obsessive-compulsive disorder, and post-traumatic stress disorder. They are also used for "
            "premenstrual dysphoric disorder, bulimia nervosa, and certain forms of chronic pain. Full "
            "therapeutic effect typically takes four to six weeks, and treatment is usually continued "
            "for at least six months after symptom remission."
        ),
        "side_effects": [
            "Nausea and gastrointestinal upset",
            "Headache",
            "Insomnia or, conversely, drowsiness",
            "Sexual dysfunction (decreased libido, delayed orgasm)",
            "Weight changes",
            "Dry mouth",
            "Sweating",
            "Increased risk of bleeding, especially with NSAIDs",
            "Hyponatremia (low sodium), particularly in older adults",
            "Discontinuation syndrome if stopped abruptly",
        ],
    },
    "Statins": {
        "overview": (
            "Statins are HMG-CoA reductase inhibitors. By blocking the rate-limiting enzyme of "
            "cholesterol synthesis in the liver, they reduce hepatic cholesterol production, upregulate "
            "LDL receptors on liver cells, and increase clearance of LDL particles from the blood. The "
            "net effect is a substantial reduction in LDL cholesterol and a modest reduction in "
            "triglycerides, along with anti-inflammatory and plaque-stabilizing effects on the arterial "
            "wall. Decades of large randomized trials have established that statins reduce the risk of "
            "heart attack, stroke, and cardiovascular death."
        ),
        "uses": (
            "Statins are prescribed for primary and secondary prevention of cardiovascular disease in "
            "people with elevated LDL cholesterol, established coronary artery disease, prior stroke, "
            "diabetes, or a high calculated 10-year risk of atherosclerotic events. They are also used "
            "in familial hypercholesterolemia. Guidelines emphasize high-intensity statin therapy for "
            "those at highest risk and moderate-intensity therapy for intermediate-risk patients."
        ),
        "side_effects": [
            "Muscle aches and pains (myalgia)",
            "Muscle weakness",
            "Elevated liver enzymes",
            "Headache",
            "Digestive symptoms (nausea, constipation, diarrhea)",
            "Increased blood sugar and small increased risk of new-onset diabetes",
            "Rarely, rhabdomyolysis (severe muscle breakdown)",
            "Memory or concentration complaints (uncommon and usually reversible)",
        ],
    },
    "ACE inhibitors": {
        "overview": (
            "Angiotensin-converting enzyme (ACE) inhibitors block the enzyme that converts angiotensin "
            "I to angiotensin II, a potent vasoconstrictor that also stimulates aldosterone release. "
            "By lowering angiotensin II levels, ACE inhibitors relax blood vessels, reduce sodium and "
            "water retention, and decrease the workload on the heart. They also reduce bradykinin "
            "breakdown, which contributes to their vasodilatory effect and to their characteristic dry "
            "cough. Long-term use slows progression of kidney disease, particularly in diabetes."
        ),
        "uses": (
            "ACE inhibitors are a first-line treatment for hypertension and are central to the "
            "management of heart failure with reduced ejection fraction, where they improve survival "
            "and reduce hospitalization. They are also used after myocardial infarction to limit "
            "ventricular remodeling, and in patients with diabetic nephropathy or chronic kidney "
            "disease with proteinuria, where they slow progression of kidney damage."
        ),
        "side_effects": [
            "Dry, persistent cough",
            "Elevated blood potassium (hyperkalemia)",
            "Dizziness or lightheadedness, especially with the first dose",
            "Low blood pressure",
            "Worsening kidney function in susceptible patients",
            "Loss of taste",
            "Rash",
            "Angioedema (rare but serious swelling of the face, lips, or airway)",
            "Should not be used in pregnancy due to fetal harm",
        ],
    },
    "Nonsteroidal anti-inflammatory drugs": {
        "overview": (
            "Nonsteroidal anti-inflammatory drugs (NSAIDs) are among the most widely used medications "
            "in the world. They relieve pain, reduce fever, and decrease inflammation by inhibiting "
            "cyclooxygenase enzymes (COX-1 and COX-2), which are responsible for producing prostaglandins "
            "— lipid compounds that promote inflammation, sensitize pain receptors, and regulate several "
            "physiological processes. Traditional NSAIDs inhibit both COX-1 and COX-2, while selective "
            "COX-2 inhibitors (coxibs) preferentially target the inducible isoform to reduce gastrointestinal "
            "risk. NSAIDs are available both over-the-counter (e.g., ibuprofen, naproxen, aspirin) and "
            "by prescription (e.g., diclofenac, indomethacin, meloxicam, celecoxib)."
        ),
        "uses": (
            "NSAIDs are used for a wide range of conditions including headaches, dental pain, menstrual "
            "cramps, muscle aches, minor injuries, osteoarthritis, rheumatoid arthritis, ankylosing "
            "spondylitis, and gout. Low-dose aspirin has a separate role in cardiovascular prevention by "
            "irreversibly inhibiting platelet thromboxane A2 synthesis. Prescription NSAIDs are also used "
            "for acute gout flares, pericarditis, and perioperative pain management."
        ),
        "side_effects": [
            "Stomach upset, nausea, indigestion",
            "Gastric or duodenal ulcers and gastrointestinal bleeding",
            "Increased blood pressure",
            "Fluid retention and edema",
            "Reduced kidney function (especially with long-term or high-dose use)",
            "Cardiovascular events (heart attack, stroke) with chronic use",
            "Allergic reactions including rash, hives",
            "Liver enzyme elevations (rare)",
            "Increased bleeding time (especially aspirin)",
        ],
    },
    "Beta blockers": {
        "overview": (
            "Beta blockers (beta-adrenergic blocking agents) work by blocking the action of epinephrine "
            "(adrenaline) at beta-adrenergic receptors in the heart, kidneys, and other organs. This slows "
            "heart rate, reduces the force of cardiac contractions, and lowers blood pressure. Beta-1 "
            "selective agents (cardioselective) primarily affect the heart, while non-selective beta "
            "blockers also block beta-2 receptors in the lungs and peripheral vasculature. Some beta "
            "blockers also have intrinsic sympathomimetic activity or additional alpha-blocking properties."
        ),
        "uses": (
            "Beta blockers are prescribed for hypertension, angina pectoris, heart failure with reduced "
            "ejection fraction, rate control in atrial fibrillation and flutter, prevention of "
            "re-infarction after myocardial infarction, supraventricular tachycardias, essential tremor, "
            "migraine prophylaxis, and hyperthyroidism. They are also used to reduce anxiety symptoms in "
            "performance-related situational anxiety and are a component of post-MI secondary prevention."
        ),
        "side_effects": [
            "Fatigue and exercise intolerance",
            "Bradycardia (slow heart rate)",
            "Cold extremities",
            "Dizziness or lightheadedness",
            "Shortness of breath (especially non-selective agents in asthma/COPD patients)",
            "Sexual dysfunction",
            "Masking of hypoglycemia symptoms in diabetic patients",
            "Sleep disturbances and vivid dreams",
            "Weight gain",
        ],
    },
    "Proton pump inhibitors": {
        "overview": (
            "Proton pump inhibitors (PPIs) are a class of acid-suppressing medications that work by "
            "irreversibly (and with omeprazole/esomeprazole) or reversibly inhibiting the hydrogen-potassium "
            "ATPase enzyme (the 'proton pump') on the secretory surface of gastric parietal cells. This "
            "blocks the final step of gastric acid production regardless of the stimulus. PPIs are the "
            "most potent acid-suppressing agents available and produce sustained suppression of both basal "
            "and stimulated gastric acid secretion. They require conversion from an inactive prodrug form "
            "in the acidic environment of the parietal cell canaliculi."
        ),
        "uses": (
            "PPIs are used for gastroesophageal reflux disease (GERD), erosive esophagitis, peptic ulcer "
            "disease (both treatment and prevention of NSAID-induced ulcers), Helicobacter pylori "
            "eradication (in combination with antibiotics), Zollinger-Ellison syndrome and other "
            "hypersecretory conditions, and Barrett's esophagus. Short-course OTC formulations are "
            "approved for frequent heartburn occurring 2 or more days per week."
        ),
        "side_effects": [
            "Headache",
            "Nausea, diarrhea, or constipation",
            "Abdominal pain",
            "Hypomagnesemia with prolonged use",
            "Vitamin B12 deficiency with long-term use",
            "Increased risk of Clostridioides difficile infection",
            "Possible increased risk of bone fractures with long-term high-dose use",
            "Acute interstitial nephritis (rare)",
            "Drug interactions (especially with clopidogrel and methotrexate)",
        ],
    },
    "Fluoroquinolones": {
        "overview": (
            "Fluoroquinolones are broad-spectrum synthetic antibiotics that kill bacteria by inhibiting "
            "two essential bacterial enzymes: DNA gyrase (topoisomerase II) and topoisomerase IV. These "
            "enzymes are required for bacterial DNA replication, transcription, repair, and recombination. "
            "By trapping the enzyme-DNA complex in a broken state, fluoroquinolones cause rapid "
            "bactericidal activity. Their excellent oral bioavailability and penetration into tissues "
            "and cells make them useful for treating a wide range of infections. However, growing "
            "resistance and a distinctive serious adverse effect profile have led guidelines to "
            "recommend reserving them for infections with few alternatives."
        ),
        "uses": (
            "Fluoroquinolones are used for community-acquired pneumonia, complicated urinary tract "
            "infections and pyelonephritis, bacterial prostatitis, intra-abdominal infections, skin "
            "and soft tissue infections, sexually transmitted infections including gonorrhea and "
            "certain cases of chlamydia, traveler's diarrhea, anthrax and plague (as part of "
            "post-exposure prophylaxis), and Mycobacterium avium complex. They are also used in "
            "combination regimens for tuberculosis (levofloxacin, moxifloxacin)."
        ),
        "side_effects": [
            "Nausea, diarrhea, abdominal discomfort",
            "Headache and dizziness",
            "Tendinitis and tendon rupture (especially Achilles tendon)",
            "Peripheral neuropathy (may be permanent)",
            "CNS effects: insomnia, restlessness, confusion, seizures (rare)",
            "QT interval prolongation (especially moxifloxacin)",
            "Aortic aneurysm and aortic dissection (increased risk)",
            "Hypoglycemia (especially in elderly diabetic patients)",
            "Clostridioides difficile-associated diarrhea",
            "Photosensitivity reactions",
            "FDA Boxed Warning: disabling and potentially permanent side effects involving tendons, muscles, joints, nerves, and CNS",
        ],
    },
    "Opioids": {
        "overview": (
            "Opioids are a class of drugs that act primarily on opioid receptors (mu, kappa, and delta) "
            "in the brain, spinal cord, and peripheral tissues to produce analgesia, sedation, and "
            "euphoria. Natural opioids (morphine, codeine) are derived from the opium poppy; "
            "semi-synthetic opioids (oxycodone, hydrocodone, buprenorphine) are chemically modified "
            "natural opioids; and fully synthetic opioids (fentanyl, methadone, tramadol) are produced "
            "entirely in the laboratory. Opioid analgesics are among the most effective treatments for "
            "severe acute pain and cancer pain, but their use in chronic non-cancer pain is controversial "
            "due to risks of tolerance, physical dependence, addiction, and overdose. Most strong opioids "
            "are classified as Schedule II controlled substances in the United States."
        ),
        "uses": (
            "Opioids are indicated for severe acute pain (post-surgical, trauma, burn), cancer-related "
            "pain, and moderate-to-severe chronic pain in carefully selected patients when alternatives "
            "are inadequate. Methadone and buprenorphine are used in medication-assisted treatment of "
            "opioid use disorder. Codeine and hydrocodone are used in low doses for cough suppression. "
            "Loperamide (a peripheral opioid) is used for diarrhea. Palliative care relies heavily on "
            "opioids for end-of-life symptom management."
        ),
        "side_effects": [
            "Constipation (nearly universal; does not develop tolerance)",
            "Nausea and vomiting (especially initially)",
            "Sedation and drowsiness",
            "Respiratory depression (dose-dependent; most serious acute risk)",
            "Itching (pruritus)",
            "Urinary retention",
            "Tolerance and physical dependence with ongoing use",
            "Risk of addiction and opioid use disorder",
            "Overdose (miosis, stupor, respiratory depression; treat with naloxone)",
            "Hormonal effects: hypogonadism, decreased testosterone/estrogen with long-term use",
            "Opioid-induced hyperalgesia with prolonged high-dose use",
        ],
    },
    "SNRIs": {
        "overview": (
            "Serotonin-norepinephrine reuptake inhibitors (SNRIs) inhibit the reuptake of both serotonin "
            "and norepinephrine into presynaptic neurons, increasing availability of both neurotransmitters "
            "in the synapse. The dual mechanism distinguishes them from SSRIs and contributes to their "
            "effectiveness in both mood and pain conditions. Common SNRIs include venlafaxine (Effexor), "
            "duloxetine (Cymbalta), desvenlafaxine (Pristiq), and levomilnacipran (Fetzima)."
        ),
        "uses": (
            "SNRIs are approved for major depressive disorder, generalized anxiety disorder, social anxiety "
            "disorder, and panic disorder. Duloxetine has additional FDA approvals for diabetic peripheral "
            "neuropathic pain, fibromyalgia, and chronic musculoskeletal pain. Venlafaxine extended-release "
            "is used for hot flashes in menopausal women. They are also used off-label for migraine prevention "
            "and stress urinary incontinence."
        ),
        "side_effects": [
            "Nausea (often transient, especially at initiation)",
            "Headache, dizziness, somnolence or insomnia",
            "Dry mouth, constipation",
            "Increased sweating",
            "Sexual dysfunction (decreased libido, anorgasmia, delayed ejaculation)",
            "Dose-dependent hypertension (especially venlafaxine at higher doses)",
            "Tachycardia",
            "Discontinuation syndrome on abrupt cessation (dizziness, sensory disturbances, irritability)",
            "Suicidal ideation (boxed warning in children, adolescents, and young adults)",
            "Serotonin syndrome (especially with other serotonergic agents)",
            "Hyponatremia (SIADH, particularly in elderly patients)",
            "Increased bleeding risk (with anticoagulants or NSAIDs)",
        ],
    },
    "GLP-1 receptor agonists": {
        "overview": (
            "GLP-1 receptor agonists mimic the action of glucagon-like peptide-1, an incretin hormone "
            "released after meals. They stimulate insulin secretion in a glucose-dependent manner, suppress "
            "glucagon release, slow gastric emptying, and reduce appetite via central mechanisms. This class "
            "includes exenatide (Byetta, Bydureon), liraglutide (Victoza, Saxenda), semaglutide (Ozempic, "
            "Wegovy, Rybelsus), dulaglutide (Trulicity), and tirzepatide (Mounjaro, Zepbound), the last "
            "being a dual GIP/GLP-1 receptor agonist."
        ),
        "uses": (
            "GLP-1 receptor agonists are used as adjuncts to diet and exercise in adults with type 2 "
            "diabetes mellitus to improve glycemic control. Several agents in this class also carry "
            "cardiovascular risk reduction indications in patients with type 2 diabetes and established "
            "cardiovascular disease. Higher-dose formulations of semaglutide (Wegovy) and liraglutide "
            "(Saxenda) are approved for chronic weight management in adults and adolescents with obesity "
            "or overweight with comorbidities."
        ),
        "side_effects": [
            "Nausea, vomiting, diarrhea, constipation (most common, especially during dose escalation)",
            "Abdominal pain, dyspepsia",
            "Injection-site reactions (for subcutaneous formulations)",
            "Decreased appetite and weight loss",
            "Pancreatitis (rare but serious; discontinue if suspected)",
            "Cholelithiasis and cholecystitis (increased risk with weight loss)",
            "Hypoglycemia (mainly when combined with insulin or sulfonylureas)",
            "Diabetic retinopathy complications (with rapid glycemic improvement, particularly semaglutide)",
            "Acute kidney injury (often secondary to dehydration from GI side effects)",
            "Thyroid C-cell tumors (rodent carcinogenicity data; boxed warning; avoid in MEN 2 or MTC history)",
            "Tachycardia",
        ],
    },
    "SGLT2 inhibitors": {
        "overview": (
            "Sodium-glucose cotransporter 2 (SGLT2) inhibitors block SGLT2 in the proximal renal tubule, "
            "reducing glucose reabsorption and increasing urinary glucose excretion. This insulin-independent "
            "mechanism lowers blood glucose, body weight, and blood pressure. Members include canagliflozin "
            "(Invokana), dapagliflozin (Farxiga), empagliflozin (Jardiance), and ertugliflozin (Steglatro)."
        ),
        "uses": (
            "SGLT2 inhibitors are used to improve glycemic control in adults with type 2 diabetes mellitus. "
            "Several have additional cardiorenal indications: empagliflozin and dapagliflozin reduce the risk "
            "of cardiovascular death and hospitalization for heart failure in adults with established CVD or "
            "cardiovascular risk factors; dapagliflozin and canagliflozin slow progression of diabetic kidney "
            "disease. Dapagliflozin is also approved for heart failure with reduced ejection fraction "
            "regardless of diabetes status."
        ),
        "side_effects": [
            "Genital mycotic infections (vulvovaginal candidiasis, balanitis; most common class side effect)",
            "Urinary tract infections (increased due to glucosuria)",
            "Polyuria, pollakiuria",
            "Hypotension and dehydration (especially in elderly and with diuretics)",
            "Hypoglycemia (mainly when combined with insulin or sulfonylureas)",
            "Fournier's gangrene (necrotizing fasciitis of the perineum; rare but serious)",
            "Diabetic ketoacidosis, often euglycemic (especially with type 1 diabetes or peri-surgical use)",
            "Increased LDL cholesterol",
            "Lower limb amputations (canagliflozin; avoid in high-risk patients)",
            "Bone fractures (canagliflozin; mechanism unclear)",
            "Acute kidney injury on initiation (volume depletion–mediated)",
        ],
    },
    "ARBs": {
        "overview": (
            "Angiotensin receptor blockers (ARBs) selectively block the angiotensin II type 1 (AT1) receptor, "
            "preventing angiotensin II from causing vasoconstriction and aldosterone release. Unlike ACE "
            "inhibitors, ARBs do not inhibit bradykinin degradation and therefore rarely cause cough. "
            "Common ARBs include losartan (Cozaar), valsartan (Diovan), irbesartan (Avapro), olmesartan "
            "(Benicar), telmisartan (Micardis), and candesartan (Atacand)."
        ),
        "uses": (
            "ARBs are primarily used for hypertension and heart failure with reduced ejection fraction (as "
            "alternatives to ACE inhibitors). Losartan and irbesartan have specific approvals for nephropathy "
            "in type 2 diabetics. Valsartan reduces cardiovascular mortality and hospitalization after "
            "myocardial infarction. ARBs are first-line for patients who require renin-angiotensin system "
            "blockade but cannot tolerate ACE inhibitor–induced cough."
        ),
        "side_effects": [
            "Hyperkalemia (especially with potassium-sparing diuretics or renal impairment)",
            "Hypotension (particularly in volume-depleted patients)",
            "Acute kidney injury (with bilateral renal artery stenosis or severe volume depletion)",
            "Angioedema (rare, but cross-reactivity with ACE inhibitor history is possible)",
            "Dizziness, lightheadedness",
            "Elevated serum creatinine on initiation (usually mild and stabilizes)",
            "Fetal and neonatal toxicity (BOXED WARNING: contraindicated in pregnancy)",
            "Hepatotoxicity (olmesartan-associated sprue-like enteropathy, rare)",
        ],
    },
    "Anticonvulsants": {
        "overview": (
            "Anticonvulsants (antiepileptic drugs, AEDs) are a diverse group of medications that reduce "
            "seizure frequency and severity through multiple mechanisms including voltage-gated sodium channel "
            "blockade (phenytoin, carbamazepine, lamotrigine), enhancement of GABAergic inhibition "
            "(valproate, benzodiazepines, gabapentin analogs), calcium channel modulation (gabapentin, "
            "pregabalin), and glutamate receptor antagonism (perampanel). Many also have indications "
            "for mood stabilization, neuropathic pain, and migraine prevention."
        ),
        "uses": (
            "AEDs are used as monotherapy or adjunctive therapy for focal and generalized epileptic seizures. "
            "Selected agents are used for bipolar disorder mood stabilization (valproate, lamotrigine, "
            "carbamazepine), neuropathic pain (gabapentin, pregabalin), migraine prophylaxis (valproate, "
            "topiramate), and anxiety disorders (pregabalin). Phenytoin is used for acute seizure management "
            "and cardiac arrhythmias. Status epilepticus is managed with intravenous benzodiazepines and "
            "phenytoin or levetiracetam."
        ),
        "side_effects": [
            "Sedation, somnolence, cognitive slowing (dose-related, most common class effect)",
            "Dizziness, ataxia, diplopia (especially at initiation or with dose increases)",
            "Nausea, vomiting, weight changes (gain with valproate/gabapentin; loss with topiramate/zonisamide)",
            "Rash (ranging from mild maculopapular to severe Stevens-Johnson syndrome/TEN, especially lamotrigine, carbamazepine, phenytoin)",
            "Hyponatremia (carbamazepine, oxcarbazepine; via SIADH mechanism)",
            "Teratogenicity (valproate: highest risk—neural tube defects, cognitive impairment; carbamazepine, phenytoin also teratogenic)",
            "Osteoporosis with long-term use (enzyme-inducing AEDs accelerate vitamin D metabolism)",
            "Drug interactions (enzyme inducers carbamazepine, phenytoin, phenobarbital decrease many co-medications)",
            "Suicidal ideation and behavior (class warning for all AEDs)",
            "Valproate-specific: hepatotoxicity, pancreatitis, hyperammonemia, thrombocytopenia, PCOS",
            "Phenytoin-specific: gingival hyperplasia, peripheral neuropathy, folate deficiency, cerebellar atrophy with toxicity",
        ],
    },
}


def get_extended_class_profile(class_name):
    """Return the extended profile dict for a class name, or None if not present."""
    if not class_name:
        return None
    return (
        DRUG_CLASS_DESCRIPTIONS_EXTENDED.get(class_name)
        or DRUG_CLASS_DESCRIPTIONS_EXTENDED.get(class_name.rstrip("s"))
    )


_DRUG_CLASS_SLUG_ALIASES: dict[str, str] = {
    # Long-name aliases for DB slugs that use short names
    "nsaids": "nonsteroidal-anti-inflammatory-drugs",
    "nonsteroidal-anti-inflammatory": "nonsteroidal-anti-inflammatory-drugs",
    "benzos": "benzodiazepines",
    "ppi": "proton-pump-inhibitors",
    "ppis": "proton-pump-inhibitors",
    "hmg-coa-reductase-inhibitors": "statins",
    "selective-serotonin-reuptake-inhibitors": "ssris",
    "serotonin-norepinephrine-reuptake-inhibitors": "snris",
    "angiotensin-converting-enzyme-inhibitors": "ace-inhibitors",
    "angiotensin-receptor-blockers": "arbs",
    "beta-adrenergic-blockers": "beta-blockers",
    "glucocorticoids": "corticosteroids",
    "opioid-analgesics": "opioids",
}


@app.route("/drug-class/<slug>")
@app.route("/drug-class/<slug>.html")
@app.route("/drug-classes/<slug>.html")
@app.route("/drug-classes/<slug>")
def drug_class_page(slug):
    # Handle common abbreviations and aliases
    canonical = _DRUG_CLASS_SLUG_ALIASES.get(slug.lower())
    if canonical:
        return redirect(url_for("drug_class_page", slug=canonical), 301)
    cls = DrugClass.query.filter_by(slug=slug).first()
    if cls is None:
        alt = slug.replace('-', '_') if '-' in slug else slug.replace('_', '-')
        cls = DrugClass.query.filter_by(slug=alt).first()
    if cls is None:
        from flask import abort
        abort(404)
    sort = _bounded_query_arg("sort", "name", 20).lower()
    drugs_q = Drug.query.filter_by(drug_class_id=cls.id)
    if sort == "rating":
        drugs = drugs_q.order_by(Drug.avg_rating.desc(), Drug.generic_name).all()
    elif sort == "reviews":
        drugs = drugs_q.order_by(Drug.review_count.desc(), Drug.generic_name).all()
    else:
        sort = "name"
        drugs = drugs_q.order_by(Drug.generic_name).all()
    related = (
        DrugClass.query.filter(DrugClass.id != cls.id)
        .order_by(DrugClass.name)
        .limit(8)
        .all()
    )

    extended = get_extended_class_profile(cls.name) or {}
    class_overview = extended.get("overview")
    class_uses = extended.get("uses")
    class_side_effects = extended.get("side_effects") or []

    class_description = (
        class_overview
        or cls.description
        or CLASS_DESCRIPTIONS.get(cls.name)
        or CLASS_DESCRIPTIONS.get((cls.name or "").rstrip("s"))
    )

    drug_ids = [d.id for d in drugs]
    common_conditions = []
    if drug_ids:
        cond_counts = (
            db.session.query(
                DrugCondition.condition_id,
                db.func.count(DrugCondition.drug_id),
            )
            .filter(DrugCondition.drug_id.in_(drug_ids))
            .group_by(DrugCondition.condition_id)
            .order_by(db.func.count(DrugCondition.drug_id).desc())
            .limit(8)
            .all()
        )
        if cond_counts:
            ids = [cid for cid, _ in cond_counts]
            cond_map = {
                c.id: c
                for c in Condition.query.filter(Condition.id.in_(ids)).all()
            }
            for cid, n in cond_counts:
                c = cond_map.get(cid)
                if c:
                    common_conditions.append({"condition": c, "count": n})

    notable_drugs = sorted(
        drugs,
        key=lambda d: (-(d.avg_rating or 0), -(d.review_count or 0), d.generic_name),
    )[:5]

    return render_template(
        "drug_class.html",
        drug_class=cls,
        drugs=drugs,
        related_classes=related,
        sort=sort,
        drug_count=len(drugs),
        class_description=class_description,
        class_overview=class_overview,
        class_uses=class_uses,
        class_side_effects=class_side_effects,
        common_conditions=common_conditions,
        notable_drugs=notable_drugs,
    )


@app.route("/news.html")
@app.route("/mednews/")
@app.route("/mednews")
@app.route("/news/")
def news_index():
    cat = _bounded_query_arg(
        "cat", max_length=_MAX_FILTER_TEXT_LENGTH
    )
    q = _bounded_query_arg("q")
    page = _bounded_page_arg()
    per_page = 15
    cat_map = {
        "new-drug-approvals": "New Drug Approvals",
        "new drug approvals": "New Drug Approvals",
        "medical": "Medical",
        "fda-alerts": "FDA Alerts",
        "fda alerts": "FDA Alerts",
        "clinical-trials": "Clinical Trials",
        "clinical trials": "Clinical Trials",
        "health": "Health",
    }
    query = NewsArticle.query
    if cat:
        db_cat = cat_map.get(cat.lower(), cat)
        query = query.filter_by(category=db_cat)
    if q:
        query = query.filter(db.or_(
            NewsArticle.title.ilike(f"%{q}%"),
            NewsArticle.body.ilike(f"%{q}%")
        ))
    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    articles = query.order_by(NewsArticle.published_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    categories = ["New Drug Approvals", "Medical", "FDA Alerts", "Clinical Trials", "Health"]
    fda_alerts = NewsArticle.query.filter(
        NewsArticle.category.in_(["FDA Alerts", "Safety"])
    ).order_by(NewsArticle.published_at.desc()).limit(4).all()
    display_cat = cat_map.get(cat.lower(), cat) if cat else None
    return render_template("news.html", articles=articles, active_category=display_cat, active_cat=display_cat,
                           categories=categories, search_query=q, fda_alerts=fda_alerts,
                           page=page, total_pages=total_pages)


@app.route("/news/<slug>-<int:article_id>")
def news_article_slug(slug, article_id):
    return news_article(article_id)


@app.route("/news/article/<int:article_id>")
def news_article(article_id):
    article = NewsArticle.query.get_or_404(article_id)
    related = (
        NewsArticle.query.filter(
            NewsArticle.category == article.category,
            NewsArticle.id != article.id,
        )
        .order_by(NewsArticle.published_at.desc())
        .limit(5)
        .all()
    )
    return render_template("news_article.html", article=article, related=related)


@app.route("/news/category/<category>")
@app.route("/newdrugs.html", defaults={"category": "new-drug-approvals"})
@app.route("/fda_alerts.html", defaults={"category": "fda-alerts"})
@app.route("/clinical_trials.html", defaults={"category": "clinical-trials"})
@app.route("/news/<category>")
@app.route("/new-drug-approvals", defaults={"category": "new-drug-approvals"})
@app.route("/fda-alerts", defaults={"category": "fda-alerts"})
@app.route("/clinical-trials", defaults={"category": "clinical-trials"})
def news_category(category):
    cat_map = {
        "new-drug-approvals": "New Drug Approvals",
        "new drug approvals": "New Drug Approvals",
        "medical": "Medical",
        "fda-alerts": "FDA Alerts",
        "fda alerts": "FDA Alerts",
        "clinical-trials": "Clinical Trials",
        "clinical trials": "Clinical Trials",
        "health": "Health",
    }
    cat = cat_map.get(category.lower()) or (category if category in cat_map.values() else None)
    if not cat:
        abort(404)
    articles = NewsArticle.query.filter_by(category=cat).order_by(NewsArticle.published_at.desc()).all()
    categories = list(dict.fromkeys(cat_map.values()))
    fda_alerts = NewsArticle.query.filter(
        NewsArticle.category.in_(["FDA Alerts", "Safety"])
    ).order_by(NewsArticle.published_at.desc()).limit(4).all()
    return render_template("news.html", articles=articles, categories=categories, active_cat=cat, fda_alerts=fda_alerts)


@app.route("/drug-classes")
@app.route("/drug-classes.html")
def drug_classes_list():
    classes = DrugClass.query.order_by(DrugClass.name).all()
    class_data = []
    for dc in classes:
        count = Drug.query.filter_by(drug_class_id=dc.id).count()
        description = (
            CLASS_DESCRIPTIONS.get(dc.name)
            or CLASS_DESCRIPTIONS.get((dc.name or "").rstrip("s"))
            or (dc.description or "")
        )
        class_data.append({
            "obj": dc,
            "count": count,
            "description": description,
        })
    total = len(class_data)
    popular_classes = sorted(class_data, key=lambda x: (-(x["count"] or 0), x["obj"].name))[:10]
    popular_classes = [p for p in popular_classes if (p["count"] or 0) > 0]
    return render_template("drug_classes.html", class_data=class_data, total=total,
                           popular_classes=popular_classes)


@app.route("/conditions")
@app.route("/conditions.html")
def conditions_list():
    all_conditions = Condition.query.order_by(Condition.name).all()
    condition_drug_counts = dict(
        db.session.query(
            DrugCondition.condition_id, db.func.count(DrugCondition.drug_id)
        )
        .group_by(DrugCondition.condition_id)
        .all()
    )
    for c in all_conditions:
        computed = condition_drug_counts.get(c.id, 0)
        if c.drug_count is None or c.drug_count == 0:
            c.drug_count = computed
    all_letters = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['0-9']
    active_letter = _bounded_query_arg("letter", max_length=3).upper().strip() or None
    if active_letter == '0-9':
        conditions = [c for c in all_conditions if c.name and not c.name[0].isalpha()]
    elif active_letter:
        conditions = [c for c in all_conditions if c.name and c.name[0].upper() == active_letter]
    else:
        conditions = all_conditions
    top_slugs = ["hypertension", "diabetes", "depression", "asthma", "anxiety",
                 "high_cholesterol", "heart_disease", "migraine", "gerd", "arthritis"]
    by_slug = {c.slug: c for c in all_conditions}
    top_conditions = [by_slug[s] for s in top_slugs if s in by_slug]
    if len(top_conditions) < 6:
        extras = sorted(all_conditions, key=lambda c: -(c.drug_count or 0))
        for c in extras:
            if c not in top_conditions:
                top_conditions.append(c)
            if len(top_conditions) >= 8:
                break
    top_conditions = top_conditions[:8]

    # Featured conditions: those with the most drugs (independent of curated top list).
    featured_conditions = sorted(
        all_conditions, key=lambda c: (-(c.drug_count or 0), c.name)
    )[:8]
    featured_conditions = [c for c in featured_conditions if (c.drug_count or 0) > 0]

    # Group conditions alphabetically for letter section headers.
    grouped_conditions = {}
    for c in conditions:
        if not c.name:
            continue
        first = c.name[0].upper()
        if not first.isalpha():
            first = "0-9"
        grouped_conditions.setdefault(first, []).append(c)
    grouped_keys = sorted(
        grouped_conditions.keys(), key=lambda k: (k == "0-9", k)
    )

    return render_template("conditions.html",
                           conditions=conditions,
                           all_letters=all_letters,
                           active_letter=active_letter,
                           top_conditions=top_conditions,
                           condition_drug_counts=condition_drug_counts,
                           featured_conditions=featured_conditions,
                           grouped_conditions=grouped_conditions,
                           grouped_keys=grouped_keys)


SYMPTOM_BODY_SYSTEMS = [
    ("Head & Neurological", [
        "Headache", "Dizziness", "Fatigue", "Memory problems", "Confusion",
    ]),
    ("Respiratory", [
        "Cough", "Shortness of breath", "Wheezing", "Congestion", "Sore throat",
    ]),
    ("Cardiovascular", [
        "Chest pain", "Rapid heartbeat", "High blood pressure", "Swelling",
    ]),
    ("Digestive", [
        "Nausea", "Vomiting", "Diarrhea", "Constipation", "Abdominal pain", "Heartburn",
    ]),
    ("Musculoskeletal", [
        "Joint pain", "Muscle pain", "Back pain", "Weakness",
    ]),
    ("Skin", [
        "Rash", "Itching", "Hives", "Dry skin",
    ]),
    ("Mental Health", [
        "Anxiety", "Depression", "Insomnia", "Mood changes",
    ]),
    ("General", [
        "Fever", "Chills", "Night sweats", "Weight loss",
    ]),
]

# Map symptom name -> list of condition slugs that commonly present with it.
SYMPTOM_CONDITION_MAP = {
    "Headache": ["migraine", "hypertension", "anxiety"],
    "Dizziness": ["hypertension", "anemia", "anxiety"],
    "Fatigue": ["hypothyroidism", "anemia", "depression", "diabetes"],
    "Memory problems": ["depression", "anxiety"],
    "Confusion": ["depression", "anemia"],
    "Cough": ["asthma", "copd", "influenza", "bacterial_infections"],
    "Shortness of breath": ["asthma", "copd", "heart_disease", "anemia"],
    "Wheezing": ["asthma", "copd"],
    "Congestion": ["influenza", "viral_infections"],
    "Sore throat": ["influenza", "bacterial_infections", "viral_infections"],
    "Chest pain": ["heart_disease", "acid_reflux", "anxiety"],
    "Rapid heartbeat": ["hyperthyroidism", "anxiety", "heart_disease"],
    "High blood pressure": ["hypertension", "heart_disease"],
    "Swelling": ["heart_disease", "arthritis", "gout"],
    "Nausea": ["nausea", "migraine", "acid_reflux"],
    "Vomiting": ["nausea", "influenza"],
    "Diarrhea": ["diarrhea", "crohns_disease", "bacterial_infections"],
    "Constipation": ["constipation", "hypothyroidism"],
    "Abdominal pain": ["acid_reflux", "crohns_disease", "constipation"],
    "Heartburn": ["acid_reflux"],
    "Joint pain": ["arthritis", "gout", "lupus"],
    "Muscle pain": ["muscle_spasm", "influenza"],
    "Back pain": ["muscle_spasm", "osteoporosis"],
    "Weakness": ["anemia", "hypothyroidism", "vitamin_deficiency"],
    "Rash": ["eczema", "psoriasis", "lupus"],
    "Itching": ["eczema", "psoriasis", "acne"],
    "Hives": ["eczema"],
    "Dry skin": ["eczema", "psoriasis", "hypothyroidism"],
    "Anxiety": ["anxiety", "depression"],
    "Depression": ["depression", "anxiety", "hypothyroidism"],
    "Insomnia": ["anxiety", "depression", "menopause", "insomnia"],
    "Mood changes": ["depression", "anxiety", "menopause", "bipolar_disorder"],
    "Fever": ["influenza", "bacterial_infections", "viral_infections", "fever"],
    "Chills": ["influenza", "bacterial_infections", "viral_infections"],
    "Night sweats": ["menopause", "hyperthyroidism", "viral_infections"],
    "Weight loss": ["hyperthyroidism", "cancer", "diabetes", "depression"],
}


@app.route("/symptoms", methods=["GET", "POST"])
@app.route("/symptom_checker.html", methods=["GET", "POST"])
@app.route("/symptom-checker.html", methods=["GET", "POST"])
@app.route("/symptom-checker", methods=["GET", "POST"])
def symptom_checker():
    """Symptom checker: pick symptoms grouped by body system, see possible conditions.

    Selected symptoms come in via ``?symptom=X&symptom=Y`` (GET) or a form POST.
    Each symptom maps to a small static list of condition slugs; the union of
    those slugs is resolved against the ``Condition`` table and ranked by how
    many of the chosen symptoms point to each condition.
    """
    if request.method == "POST":
        selected = request.form.getlist("symptom")
    else:
        selected = request.args.getlist("symptom")
    selected_set = {s for s in selected if s in SYMPTOM_CONDITION_MAP}

    # Count how many selected symptoms point to each condition slug.
    slug_hits = {}
    for sym in selected_set:
        for slug in SYMPTOM_CONDITION_MAP.get(sym, []):
            slug_hits[slug] = slug_hits.get(slug, 0) + 1

    possible_conditions = []
    if slug_hits:
        conds = Condition.query.filter(Condition.slug.in_(list(slug_hits.keys()))).all()
        by_slug = {c.slug: c for c in conds}
        for slug, hits in sorted(slug_hits.items(), key=lambda kv: (-kv[1], kv[0])):
            c = by_slug.get(slug)
            if c is not None:
                possible_conditions.append((c, hits))

    return render_template(
        "symptom_checker.html",
        body_systems=SYMPTOM_BODY_SYSTEMS,
        selected=selected_set,
        possible_conditions=possible_conditions,
        total_selected=len(selected_set),
    )


# --- Auth ---
def _safe_next_url(next_url):
    # Only allow same-site relative redirects. Backslashes need an explicit
    # rejection: browsers normalize `/\evil.example` to `//evil.example`,
    # bypassing a simple single-leading-slash regex.
    if (
        not next_url
        or len(next_url) > 2_048
        or next_url.startswith("//")
        or "\\" in next_url
        or any(ord(ch) < 32 for ch in next_url)
    ):
        return None
    try:
        parts = urlsplit(next_url)
    except (ValueError, UnicodeError):
        return None
    if (
        not parts.scheme
        and not parts.netloc
        and parts.path.startswith("/")
        and not parts.path.startswith("//")
    ):
        return next_url
    return None


@app.route("/account/login/", methods=["GET", "POST"])
@app.route("/account/login", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    next_url = _safe_next_url(
        _bounded_query_arg("next", max_length=2_048)
    )
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            with _sqlite_write_lock:
                _claim_session_review_votes(user)
            login_user(user, remember=request.form.get("remember_me"))
            flash("Welcome back!", "success")
            return redirect(next_url or url_for("account"))
        flash("Invalid email or password.", "error")
    return render_template("login.html", next_url=next_url)


@app.route("/account/register/", methods=["GET", "POST"])
@app.route("/account/register", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            email = ""
        password_error = _password_validation_error(password) if password else None
        if not username or not email or not password:
            flash("Enter a username, valid email address, and password.", "danger")
        elif len(username) > 80:
            flash("Username must be 80 characters or fewer.", "danger")
        elif len(email) > 120:
            flash("Email address must be 120 characters or fewer.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif password_error:
            flash(password_error, "danger")
        elif not request.form.get("agree_terms"):
            flash("You must agree to the Terms of Use and Privacy Policy.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            with _sqlite_write_lock:
                db.session.add(user)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Email or username already registered.", "danger")
                    return render_template("register.html")
                _claim_session_review_votes(user)
            login_user(user)
            flash("Account created.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    prior_user_id = current_user.id
    review_session_key = _review_session_key()
    with _review_votes_lock:
        _clear_session_review_votes(review_session_key)
    session.pop("recently_viewed", None)
    session[_REVIEW_VOTER_SESSION] = prior_user_id
    logout_user()
    return redirect(url_for("index"))


@app.route("/my-account.html")
@app.route("/account")
@login_required
def account():
    reviews = DrugReview.query.filter_by(user_id=current_user.id).order_by(DrugReview.created_at.desc()).all()
    saved_count = SavedDrug.query.filter_by(user_id=current_user.id).count()
    recently_viewed_slugs = session.get("recently_viewed", [])
    recently_viewed = []
    if recently_viewed_slugs:
        recently_viewed = Drug.query.filter(Drug.slug.in_(recently_viewed_slugs)).all()
        slug_order = {s: i for i, s in enumerate(recently_viewed_slugs)}
        recently_viewed.sort(key=lambda d: slug_order.get(d.slug, 99))
    return render_template("account.html", reviews=reviews, saved_count=saved_count,
                           recently_viewed=recently_viewed,
                           recently_viewed_count=len(recently_viewed_slugs))


@app.route("/my-med-list.html")
@app.route("/my-med-list")
@login_required
def my_med_list():
    items = SavedDrug.query.filter_by(user_id=current_user.id).order_by(SavedDrug.created_at.desc()).all()
    return render_template("my_med_list.html", items=items)


@app.route("/my-med-list/toggle", methods=["POST"])
@login_required
def my_med_list_toggle():
    data = request.get_json(silent=True)
    if request.is_json and not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_request"}), 400
    if data is None:
        data = {}
    slug = data.get("slug") or request.form.get("slug")
    if not isinstance(slug, str) or len(slug) > 120:
        if request.is_json:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        return redirect(url_for("my_med_list"))
    if request.is_json and "saved" in data and not isinstance(data["saved"], bool):
        return jsonify({"ok": False, "error": "invalid_request"}), 400
    slug = slug.strip()
    drug = Drug.query.filter_by(slug=slug).first()
    if not drug:
        if request.is_json:
            return jsonify({"ok": False, "error": "drug_not_found"}), 404
        return redirect(url_for("my_med_list"))
    desired_value = data.get("saved") if "saved" in data else request.form.get("saved")
    desired_saved = None
    if desired_value is not None:
        desired_saved = (
            desired_value
            if isinstance(desired_value, bool)
            else str(desired_value).lower() in {"1", "true", "yes", "on"}
        )

    # Werkzeug serves this site with threads. Serialize the legacy toggle
    # fallback for parity semantics; current UI requests send an idempotent
    # desired state so retries and double submissions are also safe.
    with _saved_drug_lock(current_user.id, drug.id):
        existing = SavedDrug.query.filter_by(
            user_id=current_user.id,
            drug_id=drug.id,
        ).first()
        if desired_saved is None:
            desired_saved = existing is None
        if desired_saved and not existing:
            add_saved_drug = sqlite_insert(SavedDrug).values(
                user_id=current_user.id,
                drug_id=drug.id,
                notes="",
                created_at=datetime.utcnow(),
            ).on_conflict_do_nothing(index_elements=["user_id", "drug_id"])
            db.session.execute(add_saved_drug)
        elif not desired_saved and existing:
            db.session.delete(existing)
        db.session.commit()
    if request.is_json:
        return jsonify({"ok": True, "saved": desired_saved})
    return redirect(url_for("my_med_list"))


@app.route("/pro/")
@app.route("/pro")
@app.route("/professionals.html")
@app.route("/pro-edition")
@app.route("/pro-edition/")
def pro_edition():
    classes = DrugClass.query.order_by(DrugClass.name).all()
    return render_template("pro_edition.html", classes=classes)


@app.route("/compare/<path:vs_slug>")
def compare_drugs_slug(vs_slug):
    """Handle /compare/drugA-vs-drugB URL format."""
    if "-vs-" in vs_slug:
        parts = vs_slug.split("-vs-", 1)
        return redirect(url_for("compare_drugs", drug1=parts[0].removesuffix(".html"), drug2=parts[1].removesuffix(".html")))
    return redirect(url_for("compare_drugs", drug1=vs_slug))


@app.route("/compare/")
@app.route("/compare")
@app.route("/compare-drugs")
@app.route("/compare-drugs.html")
def compare_drugs():
    def _lookup(q):
        if not q:
            return None
        q = q.strip()
        if not q:
            return None
        d = Drug.query.filter(db.func.lower(Drug.slug) == q.lower()).first()
        if d:
            return d
        d = Drug.query.filter(db.func.lower(Drug.generic_name) == q.lower()).first()
        if d:
            return d
        # brand name fallback (substring match against brand_names_json)
        return Drug.query.filter(Drug.brand_names_json.ilike(f"%{q}%")).first()

    def _dosage_forms(drug):
        if not drug:
            return "—"
        shapes = {img.shape for img in drug.images if img.shape}
        if shapes:
            return ", ".join(sorted(shapes))
        dc = (drug.drug_class.name if drug.drug_class else "").lower()
        gn = drug.generic_name.lower()
        if "glp-1" in dc or "glucagon-like" in dc or gn in ("semaglutide", "liraglutide", "tirzepatide"):
            return "subcutaneous injection"
        if "insulin" in dc or "insulin" in gn:
            return "subcutaneous injection"
        if "monoclonal" in dc or "biologic" in dc or gn in ("adalimumab", "rituximab", "dupilumab", "enoxaparin"):
            return "injection"
        if "inhal" in dc or "bronchodilator" in dc or gn in ("fluticasone", "tiotropium", "salmeterol", "budesonide", "ipratropium"):
            return "inhalation aerosol/powder"
        if "ophthalm" in dc or gn in ("bimatoprost", "latanoprost", "timolol ophthalmic", "brimonidine"):
            return "ophthalmic solution"
        if "retinoid" in dc or gn in ("tretinoin", "isotretinoin", "adapalene"):
            return "cream, gel"
        return "Tablet"

    # Support ?drug1=X&drug2=Y, ?drugs=X&drugs=Y, and ?drugs=X,Y formats
    drugs_list = request.args.getlist("drugs")
    if len(drugs_list) > 3 or any(
        not isinstance(name, str)
        or len(name) > _MAX_FILTER_TEXT_LENGTH
        for name in drugs_list
    ):
        abort(400)
    if len(drugs_list) == 1 and "," in drugs_list[0]:
        drugs_list = [d.strip() for d in drugs_list[0].split(",")]
        if len(drugs_list) > 3:
            abort(400)
    raw_drugs = [
        _bounded_query_arg("drug1", max_length=_MAX_FILTER_TEXT_LENGTH)
        or (drugs_list[0] if len(drugs_list) > 0 else ""),
        _bounded_query_arg("drug2", max_length=_MAX_FILTER_TEXT_LENGTH)
        or (drugs_list[1] if len(drugs_list) > 1 else ""),
        _bounded_query_arg("drug3", max_length=_MAX_FILTER_TEXT_LENGTH)
        or (drugs_list[2] if len(drugs_list) > 2 else ""),
    ]
    if any(len(name) > _MAX_FILTER_TEXT_LENGTH for name in raw_drugs):
        abort(400)
    drug1, drug2, drug3 = (_lookup(name) for name in raw_drugs)
    if any(name and drug is None for name, drug in zip(
        raw_drugs, (drug1, drug2, drug3), strict=True
    )):
        abort(400)
    popular = Drug.query.order_by(Drug.review_count.desc()).limit(20).all()
    dosage_forms = {
        "drug1": _dosage_forms(drug1),
        "drug2": _dosage_forms(drug2),
        "drug3": _dosage_forms(drug3),
    }
    return render_template(
        "compare_drugs.html",
        drug1=drug1,
        drug2=drug2,
        drug3=drug3,
        popular=popular,
        dosage_forms=dosage_forms,
    )


@app.route("/account/reviews")
@login_required
def my_reviews():
    reviews = DrugReview.query.filter_by(user_id=current_user.id).order_by(DrugReview.created_at.desc()).all()
    return render_template("my_reviews.html", reviews=reviews)


@app.route("/account/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    with _review_votes_lock:
        review = DrugReview.query.filter_by(
            id=review_id,
            user_id=current_user.id,
        ).first_or_404()
        review_identity = _review_vote_identity(review)
        drug = review.drug
        db.session.delete(review)
        db.session.flush()
        _refresh_drug_review_stats(drug)
        if _anonymous_review_vote_table_exists():
            db.session.execute(
                text(
                    "DELETE FROM anonymous_review_vote "
                    "WHERE review_identity = :identity"
                ),
                {"identity": review_identity},
            )
        db.session.commit()
        for key in [
            key
            for key in _review_votes
            if key[-1] in {review_id, review_identity}
        ]:
            del _review_votes[key]
    return redirect(url_for("my_reviews"))


@app.route("/my-med-list/notes", methods=["POST"])
@login_required
def update_med_notes():
    slug = request.form.get("slug")
    notes = request.form.get("notes", "")
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    with _saved_drug_lock(current_user.id, drug.id):
        item = SavedDrug.query.filter_by(
            user_id=current_user.id,
            drug_id=drug.id,
        ).first()
        if item is None:
            flash("That medication is no longer in your Med List.", "danger")
            return redirect(url_for("my_med_list"))
        item.notes = notes[:500]
        db.session.commit()
    return redirect(url_for("my_med_list"))


@app.route("/account/settings")
@login_required
def account_settings():
    return render_template("account_settings.html")


@app.route("/account/settings/save", methods=["POST"])
@login_required
def save_settings():
    return_to = "account" if request.form.get("settings_form") == "dashboard" else "account_settings"
    password_changed = False
    email = (request.form.get("email") or current_user.email).strip().lower()
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError:
        flash("Enter a valid email address.", "danger")
        return redirect(url_for(return_to))
    if len(email) > 120:
        flash("Email address must be 120 characters or fewer.", "danger")
        return redirect(url_for(return_to))
    duplicate = User.query.filter(User.email == email, User.id != current_user.id).first()
    if duplicate:
        flash("Email already registered.", "danger")
        return redirect(url_for(return_to))

    with _user_settings_lock(current_user.id):
        # Flask-Login loaded this request's User before it acquired the lock.
        # Refresh so a concurrent subscriptions/settings request cannot make
        # this read-modify-write start from stale preferences_json.
        db.session.refresh(current_user)
        current_user.email = email
        if request.form.get("settings_form") == "settings":
            current_user.first_name = (request.form.get("first_name") or "").strip()[:80]
            current_user.last_name = (request.form.get("last_name") or "").strip()[:80]

            new_password = request.form.get("new_password") or ""
            if new_password:
                if not current_user.check_password(request.form.get("current_password") or ""):
                    flash("Current password is incorrect.", "danger")
                    return redirect(url_for("account_settings"))
                password_error = _password_validation_error(new_password)
                if password_error:
                    flash(password_error.replace("Password", "New password", 1), "danger")
                    return redirect(url_for("account_settings"))
                if new_password != (request.form.get("confirm_password") or ""):
                    flash("New passwords do not match.", "danger")
                    return redirect(url_for("account_settings"))
                current_user.set_password(new_password)
                password_changed = True

        preferences = current_user.preferences.copy()
        old_public_reviews = preferences.get("public_reviews", True)
        if request.form.get("settings_form") == "dashboard":
            preference_fields = {
                "newsletter": "newsletter",
                "fda_alerts": "fda_alerts",
                "new_approvals": "new_approvals",
                "interaction_warnings": "interaction_warnings",
                "refill_reminders": "refill_reminders",
            }
        else:
            preference_fields = {
                "notify_news": "newsletter",
                "notify_fda": "fda_alerts",
                "notify_interactions": "interaction_warnings",
                "notify_approvals": "new_approvals",
                "public_reviews": "public_reviews",
                "share_med_list": "share_med_list",
                "personalized": "personalized",
                "analytics": "analytics",
            }
        for form_name, preference_name in preference_fields.items():
            preferences[preference_name] = form_name in request.form
        current_user.set_preferences(preferences)
        if old_public_reviews != preferences.get("public_reviews", True):
            for review in current_user.reviews:
                _refresh_drug_review_stats(review.drug)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Email already registered.", "danger")
            return redirect(url_for(return_to))
    if password_changed:
        # Refresh this browser's session identifier while invalidating every
        # previously issued session/remember identifier tied to the old hash.
        login_user(current_user, fresh=True)
    flash("Settings saved.", "success")
    return redirect(url_for(return_to))


@app.route("/account/subscriptions")
@login_required
def account_subscriptions():
    return render_template("account_subscriptions.html")


@app.route("/account/subscriptions/save", methods=["POST"])
@login_required
def save_subscriptions():
    with _user_settings_lock(current_user.id):
        db.session.refresh(current_user)
        preferences = current_user.preferences.copy()
        for name in ["fda_alerts", "new_approvals", "newsletter", "med_list_reminders", "interaction_warnings"]:
            preferences[name] = name in request.form
        current_user.set_preferences(preferences)
        db.session.commit()
    flash("Email preferences saved.", "success")
    return redirect(url_for("account_subscriptions"))


@app.route("/sitemap.xml")
@app.route("/sitemap")
@app.route("/sitemap.html")
def sitemap():
    classes = DrugClass.query.order_by(DrugClass.name).all()
    conditions = Condition.query.order_by(Condition.name).all()
    all_letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["0-9"]
    return render_template(
        "sitemap.html",
        classes=classes,
        conditions=conditions,
        all_letters=all_letters,
    )


SIDE_EFFECTS_AZ = [
    "Abdominal pain", "Acne", "Agitation", "Allergic reaction", "Anemia",
    "Anxiety", "Appetite loss", "Arrhythmia", "Back pain", "Bleeding",
    "Bloating", "Blurred vision", "Bruising", "Chest pain", "Chills",
    "Confusion", "Constipation", "Cough", "Cramps", "Depression",
    "Diarrhea", "Dizziness", "Drowsiness", "Dry mouth", "Edema",
    "Fatigue", "Fever", "Flushing", "Gas", "Hair loss",
    "Headache", "Heartburn", "Hypertension", "Hypotension", "Indigestion",
    "Insomnia", "Itching", "Jaundice", "Joint pain", "Liver damage",
    "Muscle pain", "Nausea", "Nervousness", "Numbness", "Palpitations",
    "Rash", "Restlessness", "Ringing in ears", "Seizures", "Shortness of breath",
    "Skin reaction", "Sore throat", "Stomach upset", "Sweating", "Swelling",
    "Tachycardia", "Tremor", "Vomiting", "Weakness", "Weight gain",
    "Weight loss",
]

MOST_SEARCHED_SIDE_EFFECTS = [
    "Nausea", "Headache", "Dizziness", "Drowsiness", "Fatigue",
    "Diarrhea", "Constipation", "Insomnia", "Weight gain", "Rash",
]


@app.route("/side-effects/")
@app.route("/side-effects")
@app.route("/side-effects.html")
def side_effects_page():
    """Side Effects A-Z index page.

    Renders an alphabetical directory of common side effect names with an
    A-Z letter navigation, a search box, a "most commonly searched" list,
    and (when ``?q=`` is supplied) drugs whose ``side_effects`` text matches.
    """
    q = _bounded_query_arg("q").strip()
    drugs = []
    if q:
        drugs = Drug.query.filter(Drug.side_effects.ilike(f"%{q}%")).limit(30).all()

    # Group the curated A-Z list by first letter for the directory grid.
    by_letter = {}
    for name in SIDE_EFFECTS_AZ:
        letter = name[0].upper()
        by_letter.setdefault(letter, []).append(name)
    for letter in by_letter:
        by_letter[letter].sort()
    letters = sorted(by_letter.keys())
    all_letters = list(string.ascii_uppercase)

    popular = Drug.query.order_by(Drug.review_count.desc()).limit(10).all()
    # Attach override side_effects text so template can use cleaner content
    for d in popular:
        _ov = DRUG_CONTENT_OVERRIDES.get(d.generic_name) or DRUG_CONTENT_OVERRIDES.get(d.generic_name.replace(' ', '-'), {})
        d._se_text = _ov.get("side_effects") or d.side_effects or ""
    return render_template(
        "side_effects.html",
        drugs=drugs, query=q, popular=popular,
        by_letter=by_letter, letters=letters, all_letters=all_letters,
        most_searched=MOST_SEARCHED_SIDE_EFFECTS,
    )


@app.route("/drug-warnings")
@app.route("/boxed-warnings")
@app.route("/warnings/")
@app.route("/blackbox-warnings")
@app.route("/black-box-warnings")
def warnings_index():
    category = _bounded_query_arg(
        "category", "all", _MAX_FILTER_TEXT_LENGTH
    ).lower()
    if category not in {"all", "blackbox", "recalls", "safety"}:
        abort(400)
    warning_query = Drug.query.filter(Drug.warnings.isnot(None))
    if category == "blackbox":
        warning_query = warning_query.filter(
            db.or_(
                Drug.warnings.ilike("%boxed warning%"),
                Drug.warnings.ilike("%black box%"),
            )
        )
    drugs_with_warnings = warning_query.order_by(Drug.generic_name).limit(50).all()
    alerts_query = NewsArticle.query.filter(
        NewsArticle.category.in_(["FDA Alerts", "Recalls", "Safety", "Safety Alerts"])
    )
    if category == "recalls":
        alerts_query = alerts_query.filter(
            db.or_(
                NewsArticle.category == "Recalls",
                NewsArticle.title.ilike("%recall%"),
            )
        )
    elif category == "safety":
        alerts_query = alerts_query.filter(
            db.or_(
                NewsArticle.category.in_(["Safety", "Safety Alerts"]),
                db.and_(
                    NewsArticle.category == "FDA Alerts",
                    ~NewsArticle.title.ilike("%recall%"),
                ),
            )
        )
    fda_alerts = alerts_query.order_by(NewsArticle.published_at.desc()).limit(20).all()
    return render_template(
        "warnings_index.html",
        drugs=drugs_with_warnings,
        fda_alerts=fda_alerts,
        category=category,
    )


@app.route("/newsletter")
def newsletter():
    recent_articles = (
        NewsArticle.query.filter(
            ~NewsArticle.category.in_(["New Drug Approvals", "New Drugs"])
        ).order_by(NewsArticle.published_at.desc()).limit(6).all()
    )
    selected_lists = ["daily_mednews", "weekly_safety"]
    subscription_email = ""
    if current_user.is_authenticated:
        preferences = current_user.preferences
        selected_lists = preferences.get("newsletter_lists", selected_lists)
        subscription_email = preferences.get(
            "newsletter_email", current_user.email
        )
    else:
        saved_subscription = session.get("newsletter_subscription", {})
        if isinstance(saved_subscription, dict):
            selected_lists = saved_subscription.get("lists", selected_lists)
            subscription_email = saved_subscription.get("email", "")
    return render_template(
        "newsletter.html",
        recent_articles=recent_articles,
        selected_lists=set(selected_lists),
        subscription_email=subscription_email,
    )


@app.route("/newsletter/subscribe", methods=["POST"])
def newsletter_subscribe():
    email = (request.form.get("email") or "").strip().lower()
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError:
        flash("Enter a valid email address.", "danger")
        return redirect(url_for("newsletter"))
    if len(email) > 254:
        flash("Email address must be 254 characters or fewer.", "danger")
        return redirect(url_for("newsletter"))
    requested_lists = request.form.getlist("lists") + request.form.getlist("subs")
    list_aliases = {
        "general_updates": {
            "daily_mednews", "weekly_safety", "approvals_monthly", "clinical_trials",
        },
        "monthly": {"approvals_monthly"},
        "mednews": {"daily_mednews"},
        "fda": {"weekly_safety"},
    }
    canonical_lists = {
        "daily_mednews", "weekly_safety", "approvals_monthly", "clinical_trials",
    }
    selected_set = set()
    for item in requested_lists:
        if item in canonical_lists:
            selected_set.add(item)
        else:
            selected_set.update(list_aliases.get(item, set()))
    selected_lists = sorted(selected_set)
    if not selected_lists:
        flash("Choose at least one newsletter.", "danger")
        return redirect(url_for("newsletter"))
    selected_lists = sorted(set(selected_lists))
    if current_user.is_authenticated:
        with _user_settings_lock(current_user.id):
            db.session.refresh(current_user)
            preferences = current_user.preferences.copy()
            preferences["newsletter"] = True
            preferences["newsletter_lists"] = selected_lists
            preferences["newsletter_email"] = email
            current_user.set_preferences(preferences)
            db.session.commit()
        flash("Newsletter preferences saved to your account.", "success")
    else:
        session["newsletter_subscription"] = {
            "email": email,
            "lists": selected_lists,
        }
        flash(
            "Newsletter preferences saved for this demo browser session.",
            "success",
        )
    return redirect(url_for("newsletter"))


@app.route("/terms")
@app.route("/terms.html")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
@app.route("/privacy.html")
def privacy():
    return render_template("privacy.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    submitted = False
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        email = (request.form.get("email") or "").strip().lower()
        subject = (request.form.get("subject") or "").strip()
        message = (request.form.get("message") or "").strip()[:500]
        allowed_subjects = {"general", "error", "feedback", "drug_info"}
        if not name or subject not in allowed_subjects or not message:
            flash("Complete all contact form fields.", "danger")
        else:
            try:
                validate_email(email, check_deliverability=False)
            except EmailNotValidError:
                flash("Enter a valid email address.", "danger")
            else:
                receipt_source = "\0".join((name, email, subject, message))
                session["contact_submission"] = {
                    "subject": subject,
                    "receipt": hashlib.sha256(
                        receipt_source.encode("utf-8")
                    ).hexdigest()[:16],
                    "saved_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
                submitted = True
    return render_template("contact.html", submitted=submitted)


@app.route("/advertise")
@app.route("/about.html")
@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/apps")
def apps_page():
    return render_template("apps.html")


@app.route("/support")
@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/image/<slug>-images.html")
@app.route("/<slug>/images")
@app.route("/<slug>/images.html")
def drug_images(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    images = DrugImage.query.filter_by(drug_id=drug.id).all()
    return render_template("drug_images.html", drug=drug, images=images)


def _price_seed_unit(drug_id, pharmacy, qty):
    """Deterministic 0.0-1.0 jitter derived from (drug_id, pharmacy, qty).

    Stable across requests so a benchmark sees identical prices each load.
    """
    h = hashlib.md5(f"{drug_id}{pharmacy}{qty}".encode()).hexdigest()
    return int(h[:4], 16) / 65535.0


def generate_drug_prices(drug):
    """Build a deterministic per-pharmacy price table for a drug.

    Pricing tier is chosen from drug attributes:
      * Controlled substances (`csa_schedule` starts with "Schedule") use a
        mid-to-high band ($40-$220 / 30-day supply).
      * Brand-only drugs (Rx, has brand names, no generic equivalent flag)
        use the brand band ($80-$520 / 30-day supply).
      * OTC drugs use a low band ($4-$25 / 30-day supply).
      * Everything else (generic Rx) uses $6-$45 / 30-day supply.

    Prices are emitted for three quantity tiers (30, 60, 90) using a
    hash-based per-(drug, pharmacy, qty) seed so the same drug always
    quotes the same numbers. The 60- and 90-tablet tiers apply a bulk
    discount multiplier (1.85 and 2.6 respectively) versus 30.

    Returns:
        {tier, base_retail, quantities, prices_by_qty, rows, ...}
    where `prices_by_qty[qty]` is the list of pharmacy rows for that qty
    and `rows` is the 30-tablet row list (kept for backward compatibility).
    """
    seed = (drug.id * 31 + len(drug.generic_name or "") * 7) % 997
    csa = (drug.csa_schedule or "").lower()
    avail = (drug.availability or "Rx").lower()
    brands = drug.brand_names or []

    if csa.startswith("schedule"):
        base = 40 + (seed % 180)
        tier = "controlled"
    elif "otc" in avail:
        base = 4 + (seed % 22)
        tier = "otc"
    elif brands and "rx" in avail:
        # Brand-name Rx drugs skew expensive.
        base = 80 + (seed % 440)
        tier = "brand"
    else:
        base = 6 + (seed % 40)
        tier = "generic"

    pharmacies = [
        ("CVS Pharmacy",     1.12, True),
        ("Walgreens",        1.15, True),
        ("Walmart Pharmacy", 0.88, False),
        ("Rite Aid",         1.06, True),
        ("Costco Pharmacy",  0.82, False),
        ("GoodRx Price",     0.55, True),
    ]

    # Quantity tiers and bulk-discount multipliers vs base 30-tablet supply.
    qty_multipliers = {30: 1.0, 60: 1.85, 90: 2.6}
    quantities = [30, 60, 90]

    prices_by_qty = {}
    for qty in quantities:
        qmult = qty_multipliers[qty]
        rows_q = []
        for name, mult, coupon in pharmacies:
            r = _price_seed_unit(drug.id, name, qty)  # 0.0..1.0
            # 0.8 + r*0.4 → 0.8..1.2 deterministic jitter band
            supply = round(base * qmult * mult * (0.8 + r * 0.4), 2)
            unit = round(supply / qty, 2)
            retail_at_qty = base * qmult * 1.15
            savings = max(0, int(round((1 - supply / retail_at_qty) * 100)))
            rows_q.append({
                "pharmacy": name,
                "unit_price": unit,
                "supply_price": supply,
                "coupon": coupon,
                "savings_pct": savings,
            })
        prices_by_qty[qty] = rows_q

    # Deterministic coupon code for this drug.
    coupon_code = "DRUGS" + hashlib.md5(
        f"coupon-{drug.id}-{drug.generic_name or ''}".encode()
    ).hexdigest()[:4].upper()

    return {
        "tier": tier,
        "base_retail": round(base * 1.15, 2),
        "rows": prices_by_qty[30],  # backward-compatible default view
        "quantities": quantities,
        "prices_by_qty": prices_by_qty,
        "coupon_code": coupon_code,
        "has_generic": bool(brands),  # if it has brand names, a generic equivalent exists too
        "brand_price": round(base * 4.2, 2) if tier == "generic" and brands else None,
        "generic_price": round(base * 0.95, 2) if tier == "brand" else None,
    }


@app.route("/price-guide/<slug>")
@app.route("/price-guide/<slug>.html")
@app.route("/<slug>/price-guide")
@app.route("/<slug>/price-guide.html")
@app.route("/<slug>/prices")
@app.route("/<slug>/prices.html")
def drug_prices(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    price_data = generate_drug_prices(drug)
    return render_template("drug_prices.html", drug=drug, price_data=price_data)


@app.route("/monograph/<slug>.html")
@app.route("/monograph/<slug>")
@app.route("/drugs/pro/<slug>")
@app.route("/pro/<slug>.html")
@app.route("/pro/<slug>")
@app.route("/<slug>/monograph")
@app.route("/<slug>/monograph.html")
def drug_pro_monograph(slug):
    """Professional monograph stub page for a drug.

    Returns a 200 page summarizing prescriber-oriented info (mechanism, indications,
    dosing, contraindications, adverse reactions). Stub-quality content sourced from
    the existing drug record fields; mirrors the real drugs.com /pro/<slug>.html URL.
    """
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    return render_template("drug_pro_monograph.html", drug=drug)


def _parse_dosage_rows(text, drug_name):
    """Parse dosage text into list of {indication, form, adult, pediatric} rows."""
    if not text:
        return None
    rows = []
    sentences = re.split(r'(?<=[.;])\s+', text.strip())
    adult_dose = ""
    ped_dose = ""
    for s in sentences:
        sl = s.lower()
        if re.search(r'ped|child|infant|neonate', sl):
            ped_dose = s.strip()
        elif re.search(r'adult|initial|usual|max|dose', sl):
            if adult_dose:
                adult_dose += " " + s.strip()
            else:
                adult_dose = s.strip()
    if adult_dose:
        form = "Oral"
        if re.search(r'topical|cream|gel|patch', adult_dose.lower()):
            form = "Topical"
        elif re.search(r'inject|IV|subcutaneous', adult_dose):
            form = "Injection"
        rows.append({
            "indication": f"{drug_name.capitalize()} treatment",
            "form": form,
            "adult": adult_dose,
            "pediatric": ped_dose or "Consult prescribing information for weight-based dosing."
        })
    return rows if rows else None


@app.route("/dosage/<slug>.html")
@app.route("/dosage/<slug>")
@app.route("/<slug>/dosage")
@app.route("/<slug>/dosage.html")
def drug_dosage(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    _ov = DRUG_CONTENT_OVERRIDES.get(drug.generic_name) or DRUG_CONTENT_OVERRIDES.get(drug.generic_name.replace(' ', '-'), {})
    rt_dosage = _ov.get("dosage") or drug.dosage
    dosage_rows = _parse_dosage_rows(rt_dosage, drug.generic_name)
    related_drugs = []
    if drug.drug_class_id:
        related_drugs = Drug.query.filter(
            Drug.drug_class_id == drug.drug_class_id,
            Drug.id != drug.id
        ).order_by(Drug.avg_rating.desc().nullslast()).limit(6).all()
    faq_items = list(drug.faq or _build_default_faq(drug))
    return render_template("drug_dosage.html", drug=drug, rt_dosage=rt_dosage, dosage_rows=dosage_rows,
                           related_drugs=related_drugs, faq_items=faq_items)


def _parse_side_effects(text):
    """Parse side_effects text into {common: [...], serious: [...]} lists."""
    if not text:
        return None
    common, serious = [], []
    common_m = re.search(r'Common[^:]*:\s*(.+?)(?=\.\s*Serious|\Z)', text, re.IGNORECASE | re.DOTALL)
    serious_m = re.search(r'Serious[^:]*:\s*(.+?)(?=\.\s*Common|\Z)', text, re.IGNORECASE | re.DOTALL)
    if common_m:
        raw = common_m.group(1).strip().rstrip('.')
        common = [s.strip() for s in re.split(r',\s*(?:and\s+)?', raw) if s.strip()]
    if serious_m:
        raw = serious_m.group(1).strip().rstrip('.')
        serious = [s.strip() for s in re.split(r',\s*(?:and\s+)?', raw) if s.strip()]
    if not common and not serious:
        return None
    return {"common": common, "serious": serious}


@app.route("/sfx/<slug>-side-effects.html")
@app.route("/sfx/<slug>")
@app.route("/<slug>/side-effects")
@app.route("/<slug>/side-effects.html")
def drug_side_effects(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    _ov = DRUG_CONTENT_OVERRIDES.get(drug.generic_name) or DRUG_CONTENT_OVERRIDES.get(drug.generic_name.replace(' ', '-'), {})
    rt_side_effects = _ov.get("side_effects") or drug.side_effects
    se_parsed = _parse_side_effects(rt_side_effects)
    related_drugs = []
    if drug.drug_class_id:
        related_drugs = Drug.query.filter(
            Drug.drug_class_id == drug.drug_class_id,
            Drug.id != drug.id
        ).order_by(Drug.avg_rating.desc().nullslast()).limit(6).all()
    faq_items = list(drug.faq or _build_default_faq(drug))
    return render_template("drug_side_effects.html", drug=drug, rt_side_effects=rt_side_effects,
                           se_parsed=se_parsed, related_drugs=related_drugs, faq_items=faq_items)


# FDA pregnancy category mapping for common drugs. Drugs not listed fall through
# to a class-based heuristic, then to a neutral default. The historical
# A/B/C/D/X letter system is used because it remains the form most agents and
# benchmark tasks expect, even though FDA replaced it with PLLR labeling in 2015.
PREGNANCY_CATEGORIES = {
    "lisinopril": "D",
    "enalapril": "D",
    "losartan": "D",
    "valsartan": "D",
    "warfarin": "X",
    "isotretinoin": "X",
    "methotrexate": "X",
    "thalidomide": "X",
    "atorvastatin": "X",
    "simvastatin": "X",
    "rosuvastatin": "X",
    "ibuprofen": "C",
    "naproxen": "C",
    "aspirin": "D",
    "celecoxib": "C",
    "metformin": "B",
    "amoxicillin": "B",
    "azithromycin": "B",
    "cephalexin": "B",
    "acetaminophen": "B",
    "metoprolol": "C",
    "amlodipine": "C",
    "hydrochlorothiazide": "B",
    "furosemide": "C",
    "sertraline": "C",
    "fluoxetine": "C",
    "escitalopram": "C",
    "alprazolam": "D",
    "diazepam": "D",
    "lorazepam": "D",
    "clonazepam": "D",
    "oxycodone": "C",
    "hydrocodone": "C",
    "tramadol": "C",
    "morphine": "C",
    "codeine": "C",
    "prednisone": "C",
    "albuterol": "C",
    "omeprazole": "C",
    "atenolol": "D",
    "carbamazepine": "D",
    "phenytoin": "D",
    "valproic acid": "X",
    "topiramate": "D",
    "lithium": "D",
    "tetracycline": "D",
    "doxycycline": "D",
    "ciprofloxacin": "C",
    "levofloxacin": "C",
}

# Per-class fallback when a specific drug isn't mapped above.
PREGNANCY_CATEGORY_BY_CLASS = {
    "ACE inhibitors": "D",
    "Angiotensin II receptor blockers": "D",
    "Nonsteroidal anti-inflammatory drugs": "C",
    "HMG-CoA reductase inhibitors": "X",
    "Statins": "X",
    "Benzodiazepines": "D",
    "Tetracycline antibiotics": "D",
    "Penicillin antibiotics": "B",
    "Macrolide antibiotics": "B",
    "Cephalosporin antibiotics": "B",
    "Fluoroquinolone antibiotics": "C",
    "Opioid analgesics": "C",
    "Selective serotonin reuptake inhibitors": "C",
    "Beta blockers": "C",
    "Calcium channel blockers": "C",
    "Thiazide diuretics": "B",
    "Loop diuretics": "C",
    "Proton pump inhibitors": "C",
    "Corticosteroids": "C",
    "Antiepileptics": "D",
}


def _pregnancy_info(drug):
    """Derive an FDA pregnancy category and risk profile for `drug`.

    Resolution order: explicit `PREGNANCY_CATEGORIES` mapping, then
    `PREGNANCY_CATEGORY_BY_CLASS` heuristic, then a neutral "Not classified"
    fallback. Returns a dict consumed by `drug_pregnancy.html` containing:

      category       single-letter code A/B/C/D/X or "" if unclassified
      label          human label e.g. "Category D"
      cat_class      CSS class suffix for `.preg-badge--*`
      risk_summary   one-paragraph plain-language risk summary
      considerations list of clinical-consideration bullet strings
      fetal_data     list of fetal-risk evidence bullet strings
      breastfeeding  one-paragraph lactation summary
      severity_rank  0-4 used to drive emphasis / banner color
    """
    name = (drug.generic_name or "").lower()
    cls_name = drug.drug_class.name if getattr(drug, "drug_class", None) else ""

    cat = PREGNANCY_CATEGORIES.get(name)
    if not cat:
        cat = PREGNANCY_CATEGORY_BY_CLASS.get(cls_name, "")

    name_cap = (drug.generic_name or "this medication").title()

    if cat == "A":
        return {
            "category": "A",
            "label": "Category A",
            "cat_class": "a",
            "severity_rank": 0,
            "risk_summary": (
                f"Adequate and well-controlled studies in pregnant women have not "
                f"demonstrated a risk to the fetus with {name_cap} in any trimester. "
                f"This is the lowest pregnancy-risk classification."
            ),
            "considerations": [
                f"{name_cap} is generally considered safe across all trimesters when used at standard doses.",
                "Routine prenatal monitoring is sufficient; no additional fetal surveillance is required for this drug.",
                "Continue to discuss any new medication with your obstetrician.",
            ],
            "fetal_data": [
                "Human studies: no increased rate of congenital malformations in exposed pregnancies.",
                "Animal reproduction studies: no evidence of fetal harm at clinically relevant doses.",
                "Postmarketing surveillance: no signal for adverse fetal outcomes.",
            ],
            "breastfeeding": (
                f"{name_cap} is generally compatible with breastfeeding. Infant exposure through "
                f"breast milk is low and no adverse effects on the breastfed infant have been observed."
            ),
        }
    if cat == "B":
        return {
            "category": "B",
            "label": "Category B",
            "cat_class": "b",
            "severity_rank": 1,
            "risk_summary": (
                f"Animal reproduction studies have not demonstrated a fetal risk with {name_cap}, "
                f"but there are no adequate and well-controlled studies in pregnant women. "
                f"{name_cap} is generally considered acceptable when clinically indicated."
            ),
            "considerations": [
                f"{name_cap} may be used during pregnancy when the potential benefit justifies the potential risk.",
                "Use the lowest effective dose for the shortest required duration.",
                "Inform your obstetrician of all current medications, including over-the-counter products.",
            ],
            "fetal_data": [
                "Animal reproduction studies: no evidence of impaired fertility or fetal harm.",
                "Human pregnancy registries: limited data, no consistent signal for major congenital anomalies.",
                "Population studies have not shown an increased rate of birth defects above baseline (~3%).",
            ],
            "breastfeeding": (
                f"{name_cap} is typically compatible with breastfeeding. Small amounts may pass into breast "
                f"milk; monitor the infant for unusual symptoms and notify the pediatrician if any occur."
            ),
        }
    if cat == "C":
        return {
            "category": "C",
            "label": "Category C",
            "cat_class": "c",
            "severity_rank": 2,
            "risk_summary": (
                f"Animal reproduction studies have shown an adverse effect on the fetus with {name_cap}, "
                f"or no animal studies have been conducted, and there are no adequate well-controlled "
                f"studies in humans. The drug should be used in pregnancy only if the potential benefit "
                f"justifies the potential risk to the fetus."
            ),
            "considerations": [
                f"Reserve {name_cap} for situations where clearly indicated and alternatives with better safety data are not appropriate.",
                "Use the lowest effective dose for the shortest required duration, particularly during the first trimester.",
                "Discuss the risk-benefit balance with your obstetrician before continuing or starting therapy.",
                "Consider switching to a Category A or B alternative if one is available for your indication.",
            ],
            "fetal_data": [
                "Animal studies: evidence of teratogenicity or embryolethality at doses approaching the human exposure range.",
                "Human data: insufficient or conflicting; pregnancy registries are ongoing.",
                "Mechanism-based concerns may exist depending on the drug's pharmacology (e.g., late-trimester NSAID exposure can affect ductus arteriosus closure).",
            ],
            "breastfeeding": (
                f"Use {name_cap} during breastfeeding only with healthcare-provider guidance. The drug may be "
                f"excreted in human milk; the decision should weigh maternal benefit against potential infant exposure."
            ),
        }
    if cat == "D":
        return {
            "category": "D",
            "label": "Category D",
            "cat_class": "d",
            "severity_rank": 3,
            "risk_summary": (
                f"There is positive evidence of human fetal risk based on adverse-reaction data from "
                f"investigational or marketing experience or studies in humans. However, the potential "
                f"benefits from use of {name_cap} in pregnant women may be acceptable despite its risks "
                f"in serious or life-threatening situations when safer drugs cannot be used or are ineffective."
            ),
            "considerations": [
                f"Avoid {name_cap} during pregnancy whenever a safer alternative is available for your condition.",
                "If pregnancy is detected while on therapy, contact your obstetrician promptly so the regimen can be reassessed.",
                "Effective contraception is recommended for patients of reproductive potential.",
                "If continued use is clinically necessary, enhanced fetal surveillance (e.g., targeted ultrasound) may be warranted.",
                "Do not stop chronic therapy abruptly without medical advice; abrupt discontinuation may itself pose risks.",
            ],
            "fetal_data": [
                f"Human data: documented adverse fetal effects have been observed in pregnancies exposed to {name_cap}.",
                "Second- and third-trimester exposure is associated with the strongest signals for fetal harm in this category.",
                "Specific risks vary by drug class — ACE inhibitors and ARBs are linked to oligohydramnios, fetal renal dysfunction, skull hypoplasia, and neonatal death; benzodiazepines with neonatal withdrawal and floppy infant syndrome.",
                "First-trimester exposure may carry an elevated risk of structural malformations versus the baseline rate of ~3%.",
            ],
            "breastfeeding": (
                f"Use of {name_cap} during breastfeeding requires careful evaluation. Some Category D drugs "
                f"are still compatible with nursing at standard maternal doses; others are not. Confirm with "
                f"your healthcare provider before continuing therapy while breastfeeding."
            ),
        }
    if cat == "X":
        return {
            "category": "X",
            "label": "Category X",
            "cat_class": "x",
            "severity_rank": 4,
            "risk_summary": (
                f"Studies in animals or humans have demonstrated fetal abnormalities, or there is positive "
                f"evidence of fetal risk based on human experience, or both. The risk of use of {name_cap} "
                f"in a pregnant woman clearly outweighs any possible benefit. {name_cap} is CONTRAINDICATED "
                f"in women who are or may become pregnant."
            ),
            "considerations": [
                f"{name_cap} must NOT be used during pregnancy.",
                "Patients of reproductive potential must use effective contraception throughout therapy and for an appropriate washout period after discontinuation.",
                "If pregnancy occurs during therapy, discontinue the drug immediately and notify the obstetrician for counseling regarding fetal risk.",
                "A negative pregnancy test may be required prior to initiating therapy.",
                "Enrollment in a manufacturer pregnancy-prevention or REMS program may be required (e.g., iPLEDGE for isotretinoin).",
            ],
            "fetal_data": [
                f"Multiple human pregnancies exposed to {name_cap} have documented major congenital malformations, fetal demise, or both.",
                "Effects are typically dose-independent at therapeutic exposure and may occur with even brief first-trimester exposure.",
                "Pattern of teratogenicity is drug-specific and well characterized in postmarketing registries.",
            ],
            "breastfeeding": (
                f"{name_cap} is generally contraindicated during breastfeeding. Discuss safer alternatives "
                f"with your healthcare provider before initiating therapy if nursing is planned."
            ),
        }

    # Unclassified fallback.
    return {
        "category": "",
        "label": "Not classified",
        "cat_class": "none",
        "severity_rank": 2,
        "risk_summary": (
            f"{name_cap} has not been assigned a specific FDA pregnancy category in this reference, or its "
            f"PLLR-format labeling does not map cleanly to the legacy A/B/C/D/X system. Pregnancy safety "
            f"should be assessed by your healthcare provider based on the latest prescribing information."
        ),
        "considerations": [
            f"Discuss {name_cap} with your obstetrician before continuing or starting therapy in pregnancy.",
            "Bring the current prescribing information (package insert) to your prenatal visit.",
            "Use the lowest effective dose for the shortest required duration if therapy is continued.",
        ],
        "fetal_data": [
            "Human data: limited or not summarized in this reference.",
            "Animal data: refer to the manufacturer prescribing information.",
            "Consult the FDA Pregnancy and Lactation Labeling Rule (PLLR) section of the official label for the full risk summary.",
        ],
        "breastfeeding": (
            f"Lactation safety for {name_cap} should be evaluated individually. Consult your healthcare "
            f"provider or a lactation specialist before nursing while on this medication."
        ),
    }


@app.route("/pregnancy/<slug>.html")
@app.route("/pregnancy/<slug>")
@app.route("/breastfeeding/<slug>.html")
@app.route("/breastfeeding/<slug>")
@app.route("/<slug>/pregnancy")
@app.route("/<slug>/pregnancy.html")
def drug_pregnancy(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    preg = _pregnancy_info(drug)
    return render_template("drug_pregnancy.html", drug=drug, preg=preg)


@app.route("/<slug>/warnings")
@app.route("/<slug>/warnings.html")
def drug_warnings(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    _ov = DRUG_CONTENT_OVERRIDES.get(drug.generic_name) or DRUG_CONTENT_OVERRIDES.get(drug.generic_name.replace(' ', '-'), {})
    text = (_ov.get("warnings") or drug.warnings or "").strip()
    boxed_warning = None
    lowered = text.lower()
    if "boxed warning" in lowered or "black box" in lowered:
        for para in text.split("\n\n"):
            if "boxed warning" in para.lower() or "black box" in para.lower():
                boxed_warning = para.strip()
                break
        if not boxed_warning:
            boxed_warning = text[:400]
    categories = [
        ("Before taking this medicine",
         ["allerg", "pregnan", "breastfeed", "tell your doctor", "medical history",
          "kidney", "liver", "heart"]),
        ("Serious side effects to watch for",
         ["severe", "stop taking", "emergency", "call your doctor", "seek medical",
          "anaphyla", "bleeding", "skin reaction"]),
        ("Drug and food interactions",
         ["other medic", "interaction", "alcohol", "grapefruit", "food"]),
        ("Special populations",
         ["children", "elderly", "older adults", "pediatric", "geriatric"]),
    ]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1 and text:
        # Try sentence-split if no paragraph breaks.
        import re
        paragraphs = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    categorized = {name: [] for name, _ in categories}
    general = []
    for p in paragraphs:
        pl = p.lower()
        # Skip only the exact boxed-warning text; let categorized detail through.
        if boxed_warning and (p == boxed_warning or p == text.strip()):
            continue
        placed = False
        for name, kws in categories:
            if any(k in pl for k in kws):
                categorized[name].append(p)
                placed = True
                break
        if not placed:
            general.append(p)
    cards = [(name, items) for name, items in categorized.items() if items]
    if general:
        cards.append(("General warnings", general))
    return render_template("drug_warnings.html",
                           drug=drug,
                           boxed_warning=boxed_warning,
                           warning_cards=cards)


@app.route("/tips/<slug>-patient-tips")
@app.route("/tips/<slug>")
@app.route("/<slug>/faq")
@app.route("/<slug>/faq.html")
def drug_faq_page(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    faq_items = list(drug.faq or _build_default_faq(drug))
    return render_template("drug_faq_page.html", drug=drug, faq_items=faq_items)


@app.route("/<slug>/professional")
@app.route("/<slug>/professional.html")
def drug_professional_page(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    return redirect(url_for('drug_pro_monograph', slug=slug), 301)


@app.route("/drug-interactions/<slug>.html")
@app.route("/drug-interactions/<slug>")
@app.route("/<slug>/interactions")
@app.route("/<slug>/interactions.html")
@app.route("/<slug>/drug-interactions")
@app.route("/<slug>/drug-interactions.html")
def drug_interactions_page(slug):
    drug = Drug.query.filter_by(slug=slug).first_or_404()
    interactions = DrugInteraction.query.filter(
        db.or_(DrugInteraction.drug_a_id == drug.id, DrugInteraction.drug_b_id == drug.id)
    ).all()
    interaction_details = []
    for i in interactions:
        other_id = i.drug_b_id if i.drug_a_id == drug.id else i.drug_a_id
        other = Drug.query.get(other_id)
        if other is None:
            continue
        interaction_details.append({
            'other_drug': other,
            'severity': i.severity,
            'description': i.description,
        })
    sev_order = {'major': 0, 'moderate': 1, 'minor': 2, 'unknown': 3}
    interaction_details.sort(key=lambda x: sev_order.get(x['severity'], 3))
    # Group drug-drug interactions by severity for display.
    by_severity = {'major': [], 'moderate': [], 'minor': [], 'unknown': []}
    for it in interaction_details:
        by_severity.setdefault(it['severity'], by_severity['unknown']).append(it)
    summary = {
        'total': len(interaction_details),
        'major': sum(1 for x in interaction_details if x['severity'] == 'major'),
        'moderate': sum(1 for x in interaction_details if x['severity'] == 'moderate'),
        'minor': sum(1 for x in interaction_details if x['severity'] == 'minor'),
    }
    food_interactions, alcohol_interactions = _lifestyle_interactions([drug])
    related_drugs = []
    if drug.drug_class_id:
        related_drugs = Drug.query.filter(
            Drug.drug_class_id == drug.drug_class_id,
            Drug.id != drug.id
        ).order_by(Drug.avg_rating.desc().nullslast()).limit(6).all()
    return render_template(
        "drug_interactions_page.html",
        drug=drug,
        interactions=interaction_details,
        interactions_by_severity=by_severity,
        summary=summary,
        food_interactions=food_interactions,
        alcohol_interactions=alcohol_interactions,
        related_drugs=related_drugs,
    )


@app.route("/emergency")
@app.route("/emergency-info")
@app.route("/emergency-info.html")
def emergency_info():
    return render_template("emergency_info.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "drugs_com"}


@app.errorhandler(404)
def not_found(e):
    try:
        popular_drugs = (
            Drug.query.order_by(Drug.review_count.desc().nullslast())
            .limit(12)
            .all()
        )
    except Exception:
        popular_drugs = []
    return render_template("base.html", not_found=True, popular_drugs=popular_drugs), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_SUPPLEMENTAL_CONDITIONS = [
    ("ocd", "Obsessive-Compulsive Disorder (OCD)", "OCD is a mental health disorder characterized by recurring unwanted thoughts (obsessions) and repetitive behaviors (compulsions)."),
    ("ptsd", "Post-Traumatic Stress Disorder (PTSD)", "PTSD is a psychiatric disorder that may occur after experiencing or witnessing traumatic events."),
    ("panic_disorder", "Panic Disorder", "Panic disorder involves recurrent, unexpected panic attacks and persistent concern about future attacks."),
    ("social_anxiety", "Social Anxiety Disorder", "Social anxiety disorder is an intense, persistent fear of being watched and judged by others."),
    ("pmdd", "Premenstrual Dysphoric Disorder (PMDD)", "PMDD is a severe form of premenstrual syndrome causing significant emotional and physical symptoms."),
    ("neuropathic_pain", "Neuropathic Pain", "Neuropathic pain is chronic pain caused by damage or dysfunction of the nervous system."),
    ("restless_legs", "Restless Legs Syndrome", "Restless legs syndrome is a condition causing an uncontrollable urge to move the legs, usually due to uncomfortable sensations."),
    ("fibromyalgia", "Fibromyalgia", "Fibromyalgia is a chronic condition causing widespread pain, fatigue, and cognitive difficulties."),
    ("urinary_tract_infection", "Urinary Tract Infection (UTI)", "UTIs are bacterial infections of the urinary tract, including the bladder and kidneys."),
    ("pneumonia", "Pneumonia", "Pneumonia is an infection of the lungs caused by bacteria, viruses, or fungi."),
    ("edema", "Edema", "Edema is swelling caused by excess fluid trapped in the body's tissues."),
    ("atrial_fibrillation", "Atrial Fibrillation", "Atrial fibrillation is an irregular heart rhythm that can increase risk of stroke and heart failure."),
    ("deep_vein_thrombosis", "Deep Vein Thrombosis (DVT)", "DVT is a blood clot that forms in a deep vein, usually in the legs."),
    ("pulmonary_embolism", "Pulmonary Embolism", "Pulmonary embolism is a blockage in one of the pulmonary arteries, usually caused by blood clots."),
    ("type1_diabetes", "Diabetes (Type 1)", "Type 1 diabetes is an autoimmune condition where the pancreas produces little or no insulin."),
    ("weight_management", "Obesity / Weight Management", "Obesity management involves medical treatment to achieve and maintain a healthy body weight."),
]

_SUPPLEMENTAL_DRUG_CONDITIONS: list[tuple[str, str]] = [
    ("sertraline", "ocd"),
    ("sertraline", "ptsd"),
    ("sertraline", "panic_disorder"),
    ("sertraline", "social_anxiety"),
    ("sertraline", "pmdd"),
    ("fluoxetine", "ocd"),
    ("fluoxetine", "panic_disorder"),
    ("gabapentin", "neuropathic_pain"),
    ("gabapentin", "restless_legs"),
    ("gabapentin", "fibromyalgia"),
    ("ciprofloxacin", "urinary_tract_infection"),
    ("ciprofloxacin", "pneumonia"),
    ("levofloxacin", "urinary_tract_infection"),
    ("levofloxacin", "pneumonia"),
    ("amoxicillin", "urinary_tract_infection"),
    ("amoxicillin", "pneumonia"),
    ("furosemide", "edema"),
    ("digoxin", "atrial_fibrillation"),
    ("warfarin", "atrial_fibrillation"),
    ("warfarin", "deep_vein_thrombosis"),
    ("warfarin", "pulmonary_embolism"),
    ("semaglutide", "weight_management"),
    ("insulin aspart", "type1_diabetes"),
    ("insulin glargine", "type1_diabetes"),
    ("insulin lispro", "type1_diabetes"),
    ("metformin", "obesity"),
    ("alprazolam", "panic_disorder"),
    ("alprazolam", "social_anxiety"),
]


def seed_supplemental():
    """Add conditions and drug-condition links introduced after initial seeding.

    Called only from the top-level, all-or-nothing seed pipeline. Per-row
    existence checks also keep it safe to run manually during seed development.
    """
    changed = False
    existing_cond_slugs = {c.slug for c in Condition.query.all()}
    for slug, name, desc in _SUPPLEMENTAL_CONDITIONS:
        if slug not in existing_cond_slugs:
            db.session.add(Condition(name=name, slug=slug, description=desc))
            existing_cond_slugs.add(slug)
            changed = True
    if changed:
        db.session.commit()
        changed = False

    cond_by_slug = {c.slug: c.id for c in Condition.query.all()}
    drug_by_name = {d.generic_name: d for d in Drug.query.all()}
    existing_pairs = {
        (dc.drug_id, dc.condition_id)
        for dc in DrugCondition.query.all()
    }
    # Collect desired slugs per drug from supplemental list
    desired_slugs_per_drug: dict[str, list[str]] = {}
    for drug_name, cond_slug in _SUPPLEMENTAL_DRUG_CONDITIONS:
        desired_slugs_per_drug.setdefault(drug_name, []).append(cond_slug)

    for drug_name, extra_slugs in desired_slugs_per_drug.items():
        drug = drug_by_name.get(drug_name)
        if not drug:
            continue
        # Add missing DrugCondition rows
        for cond_slug in extra_slugs:
            cond_id = cond_by_slug.get(cond_slug)
            if cond_id and (drug.id, cond_id) not in existing_pairs:
                db.session.add(DrugCondition(drug_id=drug.id, condition_id=cond_id))
                existing_pairs.add((drug.id, cond_id))
                changed = True
        # Patch conditions_json so the drug detail page reflects all conditions
        current = drug.conditions_list
        merged = list(dict.fromkeys(current + extra_slugs))
        if merged != current:
            drug.conditions_json = json.dumps(merged)
            changed = True
    if changed:
        db.session.commit()

    # Keep the denormalized counts used by the conditions index in sync with
    # supplemental links. Previously every supplemental condition displayed
    # "0 drugs" even when its detail page had treatments.
    counts = dict(
        db.session.query(DrugCondition.condition_id, db.func.count(DrugCondition.id))
        .group_by(DrugCondition.condition_id)
        .all()
    )
    counts_changed = False
    for condition in Condition.query.all():
        actual = counts.get(condition.id, 0)
        if condition.drug_count != actual:
            condition.drug_count = actual
            counts_changed = True
    if counts_changed:
        db.session.commit()


def seed_pregnancy_risks():
    """Backfill pregnancy_risk for all drugs that have a known value.

    Called from the top-level seed pipeline; each update is a no-op when the
    value is already correct, and it commits only when a row changes.
    """
    changed = False
    for gname, risk in _PREGNANCY_RISK.items():
        d = Drug.query.filter(db.func.lower(Drug.generic_name) == gname.lower()).first()
        if d and d.pregnancy_risk != risk:
            d.pregnancy_risk = risk
            changed = True
    if changed:
        db.session.commit()


def init_app():
    with app.app_context():
        db.create_all()
        seed_database()


init_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
