"""IRS Refund Tracker mirror Flask app."""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, time
from typing import Any

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from seed_data import BENCHMARK_USERS, MIRROR_REFERENCE_DATE, build_seed_payload


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "irs_refund.db")
MIRROR_REFERENCE_DATETIME = datetime.combine(MIRROR_REFERENCE_DATE, time(10, 30))
PASSWORD = "TestPass123!"
STOP_WORDS = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "and",
    "or",
    "is",
    "it",
    "by",
    "with",
    "my",
    "your",
    "this",
    "that",
}

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-irs-refund-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sign in to open account tools and saved lookup history."

SEED_PAYLOAD = build_seed_payload()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(40), nullable=True)
    preferred_contact_method = db.Column(db.String(40), default="Email", nullable=False)
    default_tax_year = db.Column(db.Integer, default=2025, nullable=False)
    default_last_four = db.Column(db.String(4), nullable=True)
    default_zip_code = db.Column(db.String(5), nullable=True)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATETIME, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=MIRROR_REFERENCE_DATETIME,
        onupdate=MIRROR_REFERENCE_DATETIME,
        nullable=False,
    )

    profiles = db.relationship("TaxpayerProfile", back_populates="owner")
    lookup_histories = db.relationship(
        "LookupHistory",
        back_populates="user",
        order_by="desc(LookupHistory.searched_at), desc(LookupHistory.id)",
    )
    search_logs = db.relationship("SearchLog", back_populates="user")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class FilingStatus(db.Model):
    __tablename__ = "filing_statuses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)

    tax_returns = db.relationship("TaxReturn", back_populates="filing_status")


class TaxpayerProfile(db.Model):
    __tablename__ = "taxpayer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(40), nullable=False)
    zip_code = db.Column(db.String(5), nullable=False)
    last_four_id = db.Column(db.String(4), nullable=False)
    contact_preference = db.Column(db.String(40), default="Email", nullable=False)
    notes = db.Column(db.Text, nullable=False)

    owner = db.relationship("User", back_populates="profiles")
    tax_returns = db.relationship(
        "TaxReturn",
        back_populates="profile",
        order_by="desc(TaxReturn.tax_year), desc(TaxReturn.id)",
    )

    @property
    def city_state(self) -> str:
        return f"{self.city}, {self.state}"


class TaxReturn(db.Model):
    __tablename__ = "tax_returns"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("taxpayer_profiles.id"), nullable=False)
    filing_status_id = db.Column(db.Integer, db.ForeignKey("filing_statuses.id"), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    refund_amount = db.Column(db.Integer, nullable=False)
    delivery_method = db.Column(db.String(40), nullable=False)
    return_received_on = db.Column(db.Date, nullable=False)
    refund_approved_on = db.Column(db.Date, nullable=True)
    refund_sent_on = db.Column(db.Date, nullable=True)
    reference_code = db.Column(db.String(40), unique=True, nullable=False)
    is_public_demo = db.Column(db.Boolean, default=False, nullable=False)
    showcase_order = db.Column(db.Integer, nullable=True)
    showcase_label = db.Column(db.String(160), nullable=True)
    is_amended = db.Column(db.Boolean, default=False, nullable=False)

    profile = db.relationship("TaxpayerProfile", back_populates="tax_returns")
    filing_status = db.relationship("FilingStatus", back_populates="tax_returns")
    refund_status = db.relationship(
        "RefundStatus",
        back_populates="tax_return",
        uselist=False,
        cascade="all, delete-orphan",
    )
    timeline_events = db.relationship(
        "RefundTimelineEvent",
        back_populates="tax_return",
        order_by="RefundTimelineEvent.sequence",
        cascade="all, delete-orphan",
    )
    lookup_histories = db.relationship("LookupHistory", back_populates="tax_return")

    @property
    def public_case_name(self) -> str:
        return self.profile.full_name


class RefundStatus(db.Model):
    __tablename__ = "refund_statuses"

    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(db.Integer, db.ForeignKey("tax_returns.id"), unique=True, nullable=False)
    stage_key = db.Column(db.String(80), nullable=False)
    public_label = db.Column(db.String(160), nullable=False)
    headline = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    next_step = db.Column(db.Text, nullable=False)
    notice_code = db.Column(db.String(20), nullable=True)
    checklist_category = db.Column(db.String(40), nullable=False)
    progress_step = db.Column(db.Integer, default=1, nullable=False)

    tax_return = db.relationship("TaxReturn", back_populates="refund_status")


class RefundTimelineEvent(db.Model):
    __tablename__ = "refund_timeline_events"

    id = db.Column(db.Integer, primary_key=True)
    tax_return_id = db.Column(db.Integer, db.ForeignKey("tax_returns.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)

    tax_return = db.relationship("TaxReturn", back_populates="timeline_events")


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=False)
    related_stage = db.Column(db.String(160), nullable=False)


class HelpArticle(db.Model):
    __tablename__ = "help_articles"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    tax_topic = db.Column(db.String(80), nullable=False)
    related_stage = db.Column(db.String(160), nullable=False)


class FAQ(db.Model):
    __tablename__ = "faqs"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    question = db.Column(db.String(240), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)


class SearchLog(db.Model):
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    query = db.Column(db.String(240), nullable=False)
    result_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATETIME, nullable=False)

    user = db.relationship("User", back_populates="search_logs")


class LookupHistory(db.Model):
    __tablename__ = "lookup_histories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tax_return_id = db.Column(db.Integer, db.ForeignKey("tax_returns.id"), nullable=True)
    label = db.Column(db.String(160), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    filing_status_name = db.Column(db.String(120), nullable=False)
    refund_amount = db.Column(db.Integer, nullable=False)
    last_four_id = db.Column(db.String(4), nullable=False)
    zip_code = db.Column(db.String(5), nullable=False)
    result_stage = db.Column(db.String(160), nullable=False)
    was_match = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    searched_at = db.Column(db.DateTime, default=MIRROR_REFERENCE_DATETIME, nullable=False)

    user = db.relationship("User", back_populates="lookup_histories")
    tax_return = db.relationship("TaxReturn", back_populates="lookup_histories")


class DocumentChecklistItem(db.Model):
    __tablename__ = "document_checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(40), nullable=False)
    audience = db.Column(db.String(40), default="all", nullable=False)
    order_index = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.0f}"


def datefmt(value: date | datetime | None) -> str:
    if value is None:
        return "Not posted"
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.split(r"\W+", text)
        if token and token.lower() not in STOP_WORDS and len(token) > 1
    ]


def score_text(query: str, parts: list[str]) -> int:
    tokens = tokenize(query)
    if not tokens:
        return 0
    haystack = " ".join(parts).lower()
    score = 0
    for token in tokens:
        if token in haystack:
            score += 2
        if haystack.startswith(token):
            score += 1
    return score


def current_alerts() -> list[Alert]:
    alerts = Alert.query.filter_by(is_active=True).order_by(Alert.order_index.asc()).all()
    if current_user.is_authenticated:
        return alerts
    return [alert for alert in alerts if alert.audience == "all"]


def get_public_cases(limit: int | None = None) -> list[TaxReturn]:
    query = (
        TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
            joinedload(TaxReturn.refund_status),
        )
        .filter_by(is_public_demo=True)
        .order_by(TaxReturn.showcase_order.asc(), TaxReturn.id.asc())
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def get_topics() -> dict[str, list[HelpArticle]]:
    articles = HelpArticle.query.order_by(HelpArticle.tax_topic.asc(), HelpArticle.title.asc()).all()
    grouped: dict[str, list[HelpArticle]] = defaultdict(list)
    for article in articles:
        grouped[article.tax_topic].append(article)
    return dict(grouped)


def progress_states(status: RefundStatus) -> list[dict[str, Any]]:
    steps = [
        {"label": "Return Received", "complete": status.progress_step >= 1, "active": status.progress_step == 1},
        {"label": "Refund Approved", "complete": status.progress_step >= 2, "active": status.progress_step == 2},
        {"label": "Refund Sent", "complete": status.progress_step >= 3, "active": status.progress_step == 3},
    ]
    if status.stage_key.startswith("delayed") or status.stage_key in {"processing", "offset_review", "amended_processing"}:
        steps[-1]["active"] = False
    return steps


def lookup_prefill_case(reference_code: str | None) -> TaxReturn | None:
    if not reference_code:
        return None
    return (
        TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
            joinedload(TaxReturn.refund_status),
        )
        .filter_by(reference_code=reference_code, is_public_demo=True)
        .first()
    )


def serialize_lookup_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "mode": result["mode"],
        "input": result["input"],
        "matched_return_id": result.get("matched_return_id"),
        "candidate_return_id": result.get("candidate_return_id"),
        "stage_label": result["stage_label"],
        "message": result["message"],
        "recommended_next_step": result["recommended_next_step"],
        "diff_fields": result.get("diff_fields", []),
    }
    return payload


def get_lookup_result() -> dict[str, Any] | None:
    stored = session.get("lookup_result")
    if not stored:
        return None

    matched_return = None
    candidate_return = None
    if stored.get("matched_return_id"):
        matched_return = (
            TaxReturn.query.options(
                joinedload(TaxReturn.profile),
                joinedload(TaxReturn.filing_status),
                joinedload(TaxReturn.refund_status),
                joinedload(TaxReturn.timeline_events),
            )
            .filter_by(id=stored["matched_return_id"])
            .first()
        )
    if stored.get("candidate_return_id"):
        candidate_return = (
            TaxReturn.query.options(
                joinedload(TaxReturn.profile),
                joinedload(TaxReturn.filing_status),
                joinedload(TaxReturn.refund_status),
                joinedload(TaxReturn.timeline_events),
            )
            .filter_by(id=stored["candidate_return_id"])
            .first()
        )
    return {
        "mode": stored["mode"],
        "input": stored["input"],
        "matched_return": matched_return,
        "candidate_return": candidate_return,
        "stage_label": stored["stage_label"],
        "message": stored["message"],
        "recommended_next_step": stored["recommended_next_step"],
        "diff_fields": stored.get("diff_fields", []),
    }


def save_lookup_history(result: dict[str, Any]) -> None:
    if not current_user.is_authenticated:
        return

    matched_return = None
    if result.get("matched_return_id"):
        matched_return = TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
            joinedload(TaxReturn.refund_status),
        ).filter_by(id=result["matched_return_id"]).first()
    candidate_return = None
    if result.get("candidate_return_id"):
        candidate_return = TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
        ).filter_by(id=result["candidate_return_id"]).first()

    filing_status_name = "Unknown"
    label = "Synthetic refund lookup"
    notes = result["message"]
    tax_return_id = None
    if matched_return:
        filing_status_name = matched_return.filing_status.name
        label = f"{matched_return.profile.full_name} / {matched_return.tax_year}"
        tax_return_id = matched_return.id
        notes = matched_return.refund_status.headline
    elif candidate_return:
        filing_status_name = candidate_return.filing_status.name
        label = f"{candidate_return.profile.full_name} / {candidate_return.tax_year}"

    history = LookupHistory(
        user_id=current_user.id,
        tax_return_id=tax_return_id,
        label=label,
        tax_year=int(result["input"]["tax_year"]),
        filing_status_name=filing_status_name,
        refund_amount=int(result["input"]["refund_amount"]),
        last_four_id=result["input"]["last_four_id"],
        zip_code=result["input"]["zip_code"],
        result_stage=result["stage_label"],
        was_match=result["mode"] == "exact",
        notes=notes,
        searched_at=MIRROR_REFERENCE_DATETIME,
    )
    db.session.add(history)
    db.session.commit()


def evaluate_lookup(start_data: dict[str, Any], verify_data: dict[str, Any]) -> dict[str, Any]:
    year = int(start_data["tax_year"])
    filing_status_slug = start_data["filing_status_slug"]
    refund_amount = int(start_data["refund_amount"])
    last_four_id = verify_data["last_four_id"]
    zip_code = verify_data["zip_code"]

    base_query = (
        TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
            joinedload(TaxReturn.refund_status),
            joinedload(TaxReturn.timeline_events),
        )
        .join(TaxReturn.profile)
        .join(TaxReturn.filing_status)
    )
    exact_match = (
        base_query.filter(
            TaxReturn.tax_year == year,
            FilingStatus.slug == filing_status_slug,
            TaxReturn.refund_amount == refund_amount,
            TaxpayerProfile.last_four_id == last_four_id,
            TaxpayerProfile.zip_code == zip_code,
        )
        .first()
    )
    common_input = {
        "tax_year": year,
        "filing_status_slug": filing_status_slug,
        "refund_amount": refund_amount,
        "last_four_id": last_four_id,
        "zip_code": zip_code,
    }
    if exact_match:
        return {
            "mode": "exact",
            "input": common_input,
            "matched_return_id": exact_match.id,
            "stage_label": exact_match.refund_status.public_label,
            "message": exact_match.refund_status.headline,
            "recommended_next_step": exact_match.refund_status.next_step,
        }

    mismatch_queries = [
        base_query.filter(TaxReturn.tax_year == year, TaxpayerProfile.last_four_id == last_four_id).all(),
        base_query.filter(TaxReturn.tax_year == year, TaxpayerProfile.zip_code == zip_code).all(),
        base_query.filter(TaxReturn.tax_year == year, TaxReturn.refund_amount == refund_amount).all(),
    ]
    candidates: list[TaxReturn] = []
    for subset in mismatch_queries:
        for candidate in subset:
            if candidate not in candidates:
                candidates.append(candidate)
    best_candidate = None
    best_diff_fields: list[str] = []
    for candidate in candidates:
        diff_fields = []
        if candidate.filing_status.slug != filing_status_slug:
            diff_fields.append("filing status")
        if candidate.refund_amount != refund_amount:
            diff_fields.append("refund amount")
        if candidate.profile.last_four_id != last_four_id:
            diff_fields.append("last four digits")
        if candidate.profile.zip_code != zip_code:
            diff_fields.append("ZIP code")
        if best_candidate is None or len(diff_fields) < len(best_diff_fields):
            best_candidate = candidate
            best_diff_fields = diff_fields
    if best_candidate and best_diff_fields and len(best_diff_fields) <= 2:
        if len(best_diff_fields) == 1:
            mismatch_message = f"The {best_diff_fields[0]} does not match the synthetic demo record."
        else:
            mismatch_message = (
                "These lookup fields do not match the synthetic demo record: "
                + ", ".join(best_diff_fields[:-1])
                + f" and {best_diff_fields[-1]}."
            )
        return {
            "mode": "mismatch",
            "input": common_input,
            "candidate_return_id": best_candidate.id,
            "stage_label": "Information Mismatch",
            "message": mismatch_message,
            "recommended_next_step": (
                "Compare the public demo case or saved lookup history and correct the highlighted field(s)."
            ),
            "diff_fields": best_diff_fields,
        }

    return {
        "mode": "not_found",
        "input": common_input,
        "stage_label": "Not Found / Information Mismatch",
        "message": "No synthetic demo return matches the lookup values you entered.",
        "recommended_next_step": (
            "Use one of the public demo cases or a seeded benchmark account instead of real taxpayer data."
        ),
        "diff_fields": [],
    }


def search_content(query: str) -> dict[str, list[dict[str, Any]]]:
    if not query.strip():
        return {"articles": [], "faqs": [], "notices": [], "topics": []}

    grouped = {"articles": [], "faqs": [], "notices": [], "topics": []}

    for article in HelpArticle.query.all():
        score = score_text(query, [article.title, article.summary, article.body, article.tax_topic])
        if score:
            grouped["articles"].append(
                {
                    "score": score,
                    "title": article.title,
                    "summary": article.summary,
                    "url": url_for("help_detail", slug=article.slug),
                    "meta": article.category,
                }
            )

    for faq in FAQ.query.all():
        score = score_text(query, [faq.question, faq.answer, faq.category])
        if score:
            grouped["faqs"].append(
                {
                    "score": score,
                    "title": faq.question,
                    "summary": faq.answer,
                    "url": url_for("faq"),
                    "meta": faq.category,
                }
            )

    for notice in Notice.query.all():
        score = score_text(query, [notice.code, notice.title, notice.summary, notice.details])
        if score:
            grouped["notices"].append(
                {
                    "score": score,
                    "title": f"{notice.code} - {notice.title}",
                    "summary": notice.summary,
                    "url": url_for("notice_detail", code=notice.code),
                    "meta": notice.related_stage,
                }
            )

    for topic, articles in get_topics().items():
        article_titles = " ".join(article.title for article in articles)
        score = score_text(query, [topic, article_titles])
        if score:
            grouped["topics"].append(
                {
                    "score": score,
                    "title": topic.replace("-", " ").title(),
                    "summary": f"{len(articles)} help article(s) in this topic.",
                    "url": url_for("tax_topics", topic=topic),
                    "meta": "Tax topic",
                }
            )

    for bucket in grouped.values():
        bucket.sort(key=lambda item: (-item["score"], item["title"]))
    return grouped


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    for user_data in BENCHMARK_USERS:
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            display_name=user_data["display_name"],
            city=user_data["city"],
            state=user_data["state"],
            preferred_contact_method=user_data["preferred_contact_method"],
            default_tax_year=user_data["default_tax_year"],
            default_last_four=user_data["default_last_four"],
            default_zip_code=user_data["default_zip_code"],
            created_at=MIRROR_REFERENCE_DATETIME,
            updated_at=MIRROR_REFERENCE_DATETIME,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
    db.session.commit()


def seed_database() -> None:
    if TaxpayerProfile.query.count() > 0:
        return

    status_map: dict[str, FilingStatus] = {}
    for entry in SEED_PAYLOAD["filing_statuses"]:
        row = FilingStatus(
            name=entry["name"],
            slug=entry["slug"],
            description=entry["description"],
        )
        db.session.add(row)
        status_map[row.slug] = row

    for entry in SEED_PAYLOAD["notices"]:
        db.session.add(
            Notice(
                code=entry["code"],
                title=entry["title"],
                summary=entry["summary"],
                details=entry["details"],
                related_stage=entry["related_stage"],
            )
        )

    for entry in SEED_PAYLOAD["help_articles"]:
        db.session.add(
            HelpArticle(
                slug=entry["slug"],
                title=entry["title"],
                category=entry["category"],
                summary=entry["summary"],
                body=entry["body"],
                tax_topic=entry["tax_topic"],
                related_stage=entry["related_stage"],
            )
        )

    for entry in SEED_PAYLOAD["faqs"]:
        db.session.add(
            FAQ(
                slug=entry["slug"],
                question=entry["question"],
                answer=entry["answer"],
                category=entry["category"],
            )
        )

    for entry in SEED_PAYLOAD["checklist_items"]:
        db.session.add(
            DocumentChecklistItem(
                slug=entry["slug"],
                title=entry["title"],
                description=entry["description"],
                category=entry["category"],
            )
        )

    for entry in SEED_PAYLOAD["alerts"]:
        db.session.add(
            Alert(
                title=entry["title"],
                body=entry["body"],
                level=entry["level"],
                audience=entry["audience"],
                order_index=entry["order_index"],
                is_active=True,
            )
        )

    user_map = {user.email: user for user in User.query.all()}
    profile_map: dict[str, TaxpayerProfile] = {}
    for entry in SEED_PAYLOAD["profiles"]:
        profile = TaxpayerProfile(
            owner_id=user_map.get(entry["owner_email"]).id if entry["owner_email"] else None,
            full_name=entry["full_name"],
            slug=entry["slug"],
            city=entry["city"],
            state=entry["state"],
            zip_code=entry["zip_code"],
            last_four_id=entry["last_four_id"],
            contact_preference=entry["contact_preference"],
            notes=entry["notes"],
        )
        db.session.add(profile)
        profile_map[profile.slug] = profile

    db.session.flush()

    scenario_map = SEED_PAYLOAD["status_scenarios"]
    for return_entry in SEED_PAYLOAD["returns"]:
        profile = profile_map[return_entry["profile_slug"]]
        tax_return = TaxReturn(
            profile_id=profile.id,
            filing_status_id=status_map[return_entry["filing_status_slug"]].id,
            tax_year=return_entry["tax_year"],
            refund_amount=return_entry["refund_amount"],
            delivery_method=return_entry["delivery_method"],
            return_received_on=return_entry["return_received_on"],
            refund_approved_on=return_entry["refund_approved_on"],
            refund_sent_on=return_entry["refund_sent_on"],
            reference_code=return_entry["reference_code"],
            is_public_demo=return_entry["is_public_demo"],
            showcase_order=return_entry["showcase_order"],
            showcase_label=return_entry["showcase_label"],
            is_amended=return_entry["is_amended"],
        )
        db.session.add(tax_return)
        db.session.flush()

        scenario = scenario_map[return_entry["scenario"]]
        db.session.add(
            RefundStatus(
                tax_return_id=tax_return.id,
                stage_key=return_entry["scenario"],
                public_label=scenario["public_label"],
                headline=scenario["headline"],
                explanation=scenario["explanation"],
                next_step=scenario["next_step"],
                notice_code=scenario["notice_code"],
                checklist_category=scenario["checklist_category"],
                progress_step=scenario["progress_step"],
            )
        )

        from seed_data import timeline_for_return

        for sequence, event in enumerate(timeline_for_return(return_entry), start=1):
            db.session.add(
                RefundTimelineEvent(
                    tax_return_id=tax_return.id,
                    sequence=sequence,
                    event_date=event["event_date"],
                    label=event["label"],
                    description=event["description"],
                )
            )

    db.session.commit()


def seed_lookup_history() -> None:
    if LookupHistory.query.count() > 0:
        return

    user_map = {user.email: user for user in User.query.all()}
    return_map = {
        (row.profile.slug, row.tax_year): row
        for row in TaxReturn.query.options(
            joinedload(TaxReturn.profile),
            joinedload(TaxReturn.filing_status),
            joinedload(TaxReturn.refund_status),
        ).all()
    }

    for email, items in SEED_PAYLOAD["benchmark_histories"].items():
        user = user_map[email]
        for offset, item in enumerate(items):
            row = return_map[(item["profile_slug"], item["tax_year"])]
            db.session.add(
                LookupHistory(
                    user_id=user.id,
                    tax_return_id=row.id,
                    label=item["label"],
                    tax_year=row.tax_year,
                    filing_status_name=row.filing_status.name,
                    refund_amount=row.refund_amount,
                    last_four_id=row.profile.last_four_id,
                    zip_code=row.profile.zip_code,
                    result_stage=row.refund_status.public_label,
                    was_match=True,
                    notes=row.refund_status.headline,
                    searched_at=MIRROR_REFERENCE_DATETIME,
                )
            )
            if offset == 0:
                db.session.add(
                    LookupHistory(
                        user_id=user.id,
                        tax_return_id=None,
                        label=f"{row.profile.full_name} / mismatch practice",
                        tax_year=row.tax_year,
                        filing_status_name=row.filing_status.name,
                        refund_amount=row.refund_amount,
                        last_four_id=row.profile.last_four_id,
                        zip_code="00000",
                        result_stage="Information Mismatch",
                        was_match=False,
                        notes="Synthetic mismatch example stored for benchmark review.",
                        searched_at=MIRROR_REFERENCE_DATETIME,
                    )
                )
    db.session.commit()


def benchmark_counts() -> dict[str, int]:
    return {
        "profiles": TaxpayerProfile.query.count(),
        "tax_returns": TaxReturn.query.count(),
        "refund_statuses": RefundStatus.query.count(),
        "timeline_events": RefundTimelineEvent.query.count(),
        "help_articles": HelpArticle.query.count(),
        "faqs": FAQ.query.count(),
        "notices": Notice.query.count(),
        "users": User.query.count(),
        "lookup_histories": LookupHistory.query.count(),
    }


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "reference_date": MIRROR_REFERENCE_DATE,
        "current_alerts": current_alerts(),
        "current_lookup_result": get_lookup_result(),
    }


@app.template_filter("money")
def money_filter(value: int | None) -> str:
    return money(value)


@app.template_filter("datefmt")
def date_filter(value: date | datetime | None) -> str:
    return datefmt(value)


@app.route("/")
def index():
    featured_articles = HelpArticle.query.order_by(HelpArticle.title.asc()).limit(6).all()
    faqs = FAQ.query.order_by(FAQ.category.asc(), FAQ.question.asc()).limit(6).all()
    counts = benchmark_counts()
    return render_template(
        "index.html",
        public_cases=get_public_cases(limit=6),
        featured_articles=featured_articles,
        faqs=faqs,
        counts=counts,
    )


@app.route("/refunds")
def refunds():
    notices = Notice.query.order_by(Notice.code.asc()).limit(8).all()
    status_cards = list(SEED_PAYLOAD["status_scenarios"].values())
    return render_template(
        "refunds.html",
        notices=notices,
        status_cards=status_cards,
        public_cases=get_public_cases(limit=4),
    )


@app.route("/where-is-my-refund")
def where_is_my_refund():
    return render_template(
        "where_is_my_refund.html",
        public_cases=get_public_cases(),
        counts=benchmark_counts(),
    )


@app.route("/refund-status")
def refund_status():
    return redirect(url_for("refund_status_start"))


@app.route("/refund-status/start", methods=["GET", "POST"])
def refund_status_start():
    selected_case = lookup_prefill_case(request.values.get("case"))
    filing_statuses = FilingStatus.query.order_by(FilingStatus.name.asc()).all()
    start_data = session.get("lookup_start", {})
    if selected_case:
        start_data = {
            "tax_year": selected_case.tax_year,
            "filing_status_slug": selected_case.filing_status.slug,
            "refund_amount": selected_case.refund_amount,
            "case_reference": selected_case.reference_code,
        }
        session["lookup_start"] = start_data

    if request.method == "POST":
        try:
            tax_year = int(request.form.get("tax_year", "0"))
            refund_amount = int(str(request.form.get("refund_amount", "")).replace(",", "").strip())
        except ValueError:
            flash("Enter a valid synthetic tax year and whole-dollar refund amount.", "error")
            return redirect(url_for("refund_status_start"))
        filing_status_slug = request.form.get("filing_status_slug", "").strip()
        if tax_year not in {2021, 2022, 2023, 2024, 2025} or not FilingStatus.query.filter_by(slug=filing_status_slug).first():
            flash("Select a valid synthetic tax year and filing status.", "error")
            return redirect(url_for("refund_status_start"))
        session["lookup_start"] = {
            "tax_year": tax_year,
            "filing_status_slug": filing_status_slug,
            "refund_amount": refund_amount,
            "case_reference": request.form.get("case_reference") or "",
        }
        return redirect(url_for("refund_status_verify"))

    return render_template(
        "refund_start.html",
        filing_statuses=filing_statuses,
        start_data=start_data,
        public_cases=get_public_cases(),
    )


@app.route("/refund-status/verify", methods=["GET", "POST"])
def refund_status_verify():
    start_data = session.get("lookup_start")
    if not start_data:
        flash("Start the synthetic lookup flow from the first step.", "error")
        return redirect(url_for("refund_status_start"))

    case = lookup_prefill_case(start_data.get("case_reference"))
    verify_data = session.get("lookup_verify", {})
    if case:
        verify_data.setdefault("last_four_id", case.profile.last_four_id)
        verify_data.setdefault("zip_code", case.profile.zip_code)

    if request.method == "POST":
        last_four_id = request.form.get("last_four_id", "").strip()
        zip_code = request.form.get("zip_code", "").strip()
        if not re.fullmatch(r"\d{4}", last_four_id):
            flash("Use a four-digit synthetic last-four identifier.", "error")
            return redirect(url_for("refund_status_verify"))
        if not re.fullmatch(r"\d{5}", zip_code):
            flash("Use a five-digit synthetic ZIP code.", "error")
            return redirect(url_for("refund_status_verify"))
        verify_data = {"last_four_id": last_four_id, "zip_code": zip_code}
        session["lookup_verify"] = verify_data
        result = evaluate_lookup(start_data, verify_data)
        serialized = serialize_lookup_result(result)
        session["lookup_result"] = serialized
        save_lookup_history(serialized)
        return redirect(url_for("refund_status_result"))

    return render_template(
        "refund_verify.html",
        start_data=start_data,
        verify_data=verify_data,
        public_cases=get_public_cases(limit=4),
    )


@app.route("/refund-status/result")
def refund_status_result():
    result = get_lookup_result()
    if not result:
        flash("Run the synthetic refund lookup flow first.", "error")
        return redirect(url_for("refund_status_start"))

    matched_return = result["matched_return"]
    candidate_return = result["candidate_return"]
    checklist_items: list[DocumentChecklistItem] = []
    notice = None
    progress = []
    if matched_return:
        status = matched_return.refund_status
        progress = progress_states(status)
        checklist_items = (
            DocumentChecklistItem.query.filter_by(category=status.checklist_category)
            .order_by(DocumentChecklistItem.title.asc())
            .all()
        )
        if status.notice_code:
            notice = Notice.query.filter_by(code=status.notice_code).first()
    elif candidate_return:
        checklist_items = (
            DocumentChecklistItem.query.filter_by(category="mismatch")
            .order_by(DocumentChecklistItem.title.asc())
            .all()
        )

    return render_template(
        "refund_result.html",
        result=result,
        matched_return=matched_return,
        candidate_return=candidate_return,
        checklist_items=checklist_items,
        notice=notice,
        progress=progress,
    )


@app.route("/refund-status/summary")
def refund_status_summary():
    result = get_lookup_result()
    if not result:
        flash("Open a synthetic refund result before printing the summary.", "error")
        return redirect(url_for("refund_status_start"))
    return render_template(
        "refund_summary.html",
        result=result,
        matched_return=result["matched_return"],
        candidate_return=result["candidate_return"],
    )


@app.route("/refund-status/history")
def refund_status_history():
    if current_user.is_authenticated:
        return redirect(url_for("lookup_history"))
    return render_template(
        "lookup_history.html",
        guest_mode=True,
        histories=[],
        public_cases=get_public_cases(limit=6),
    )


@app.route("/help")
def help_index():
    articles = HelpArticle.query.order_by(HelpArticle.category.asc(), HelpArticle.title.asc()).all()
    return render_template("help_index.html", articles=articles, topics=get_topics())


@app.route("/help/<slug>")
def help_detail(slug: str):
    article = HelpArticle.query.filter_by(slug=slug).first_or_404()
    related_articles = (
        HelpArticle.query.filter(
            HelpArticle.tax_topic == article.tax_topic,
            HelpArticle.id != article.id,
        )
        .order_by(HelpArticle.title.asc())
        .limit(4)
        .all()
    )
    return render_template("help_detail.html", article=article, related_articles=related_articles)


@app.route("/faq")
def faq():
    faqs = FAQ.query.order_by(FAQ.category.asc(), FAQ.question.asc()).all()
    grouped: dict[str, list[FAQ]] = defaultdict(list)
    for item in faqs:
        grouped[item.category].append(item)
    return render_template("faq.html", grouped=grouped)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = search_content(query)
    total_results = sum(len(items) for items in results.values())
    if query:
        db.session.add(
            SearchLog(
                user_id=current_user.id if current_user.is_authenticated else None,
                query=query,
                result_count=total_results,
                created_at=MIRROR_REFERENCE_DATETIME,
            )
        )
        db.session.commit()
    return render_template("search.html", query=query, results=results, total_results=total_results)


@app.route("/notices")
def notices():
    selected_stage = request.args.get("stage", "").strip()
    query = Notice.query.order_by(Notice.code.asc())
    if selected_stage:
        query = query.filter(Notice.related_stage.ilike(f"%{selected_stage}%"))
    return render_template(
        "notices.html",
        notices=query.all(),
        selected_stage=selected_stage,
        stages=sorted({notice.related_stage for notice in Notice.query.all()}),
    )


@app.route("/notices/<code>")
def notice_detail(code: str):
    notice = Notice.query.filter(func.lower(Notice.code) == code.lower()).first_or_404()
    related_articles = (
        HelpArticle.query.filter(
            (HelpArticle.related_stage == notice.related_stage)
            | (HelpArticle.category.ilike(f"%{notice.related_stage.split(':')[0]}%"))
        )
        .order_by(HelpArticle.title.asc())
        .limit(4)
        .all()
    )
    return render_template("notice_detail.html", notice=notice, related_articles=related_articles)


@app.route("/tax-topics")
def tax_topics():
    selected_topic = request.args.get("topic")
    topics = get_topics()
    return render_template("tax_topics.html", topics=topics, selected_topic=selected_topic)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    submitted = False
    form_data = {
        "name": "",
        "email": current_user.email if current_user.is_authenticated else "",
        "topic": "",
        "message": "",
    }
    if request.method == "POST":
        form_data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "topic": request.form.get("topic", "").strip(),
            "message": request.form.get("message", "").strip(),
        }
        if not form_data["name"] or not form_data["email"] or not form_data["message"]:
            flash("Complete the demo contact form before sending it.", "error")
        else:
            submitted = True
            flash("Demo contact request recorded locally. No live IRS systems were contacted.", "success")
    return render_template("contact.html", submitted=submitted, form_data=form_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(
            (func.lower(User.email) == login_value) | (func.lower(User.username) == login_value)
        ).first()
        if not user or not user.check_password(password):
            flash("The local demo credentials did not match a registered account.", "error")
            return redirect(url_for("login"))
        login_user(user)
        flash("Signed in to the local benchmark mirror.", "success")
        return redirect(request.args.get("next") or url_for("account"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not username or not display_name or not email or not password:
            flash("Complete every field to create a local demo account.", "error")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("The password confirmation did not match.", "error")
            return redirect(url_for("register"))
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("That email or username already exists in the local mirror.", "error")
            return redirect(url_for("register"))
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            city=request.form.get("city", "").strip() or "Demo City",
            state=request.form.get("state", "").strip() or "DC",
            preferred_contact_method=request.form.get("preferred_contact_method", "Email") or "Email",
            default_tax_year=int(request.form.get("default_tax_year", "2025")),
            default_last_four=request.form.get("default_last_four", "").strip() or None,
            default_zip_code=request.form.get("default_zip_code", "").strip() or None,
            created_at=MIRROR_REFERENCE_DATETIME,
            updated_at=MIRROR_REFERENCE_DATETIME,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Demo account created locally. Use only synthetic practice data here.", "success")
        return redirect(url_for("account"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Signed out of the local benchmark mirror.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    profiles = (
        TaxpayerProfile.query.filter_by(owner_id=current_user.id)
        .options(joinedload(TaxpayerProfile.tax_returns).joinedload(TaxReturn.refund_status))
        .all()
    )
    histories = current_user.lookup_histories[:6]
    return render_template("account.html", profiles=profiles, histories=histories)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        default_last_four = request.form.get("default_last_four", "").strip() or None
        default_zip_code = request.form.get("default_zip_code", "").strip() or None
        if default_last_four and not re.fullmatch(r"\d{4}", default_last_four):
            flash("Use a four-digit synthetic last-four value in account settings.", "error")
            return redirect(url_for("account_edit"))
        if default_zip_code and not re.fullmatch(r"\d{5}", default_zip_code):
            flash("Use a five-digit synthetic ZIP code in account settings.", "error")
            return redirect(url_for("account_edit"))
        current_user.display_name = request.form.get("display_name", "").strip() or current_user.display_name
        current_user.city = request.form.get("city", "").strip() or current_user.city
        current_user.state = request.form.get("state", "").strip() or current_user.state
        current_user.preferred_contact_method = (
            request.form.get("preferred_contact_method", "").strip() or current_user.preferred_contact_method
        )
        try:
            current_user.default_tax_year = int(request.form.get("default_tax_year", current_user.default_tax_year))
        except ValueError:
            flash("Choose a valid synthetic default tax year.", "error")
            return redirect(url_for("account_edit"))
        current_user.default_last_four = default_last_four
        current_user.default_zip_code = default_zip_code
        current_user.updated_at = MIRROR_REFERENCE_DATETIME
        db.session.commit()
        flash("Demo account preferences updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/lookup-history")
@login_required
def lookup_history():
    return render_template(
        "lookup_history.html",
        guest_mode=False,
        histories=current_user.lookup_histories,
        public_cases=[],
    )


@app.route("/healthcheck/seed-counts")
def seed_counts():
    return benchmark_counts()


with app.app_context():
    db.create_all()
    seed_benchmark_users()
    seed_database()
    seed_lookup_history()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
