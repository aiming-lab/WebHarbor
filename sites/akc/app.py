"""American Kennel Club mirror for WebHarbor."""
from __future__ import annotations

import os
import re
from datetime import date
from functools import wraps

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
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-akc-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'akc.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "dog", "dogs"}
REFERENCE_DATE = date(2026, 5, 28)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    household = db.Column(db.String(80), default="Apartment")
    activity_level = db.Column(db.String(80), default="Moderate")
    experience = db.Column(db.String(80), default="First-time owner")


class Breed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    group = db.Column(db.String(80), nullable=False)
    size = db.Column(db.String(40), nullable=False)
    energy = db.Column(db.Integer, nullable=False)
    grooming = db.Column(db.Integer, nullable=False)
    trainability = db.Column(db.Integer, nullable=False)
    good_with_children = db.Column(db.Integer, nullable=False)
    apartment_score = db.Column(db.Integer, nullable=False)
    life_expectancy = db.Column(db.String(40), nullable=False)
    height = db.Column(db.String(80), nullable=False)
    weight = db.Column(db.String(80), nullable=False)
    temperament = db.Column(db.String(160), nullable=False)
    overview = db.Column(db.Text, nullable=False)
    care = db.Column(db.Text, nullable=False)
    exercise = db.Column(db.Text, nullable=False)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    read_minutes = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    event_type = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(20), nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    venue = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)


class SavedBreed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    breed_id = db.Column(db.Integer, db.ForeignKey("breed.id"), nullable=False)
    note = db.Column(db.String(240), default="")
    breed = db.relationship("Breed")


class EventRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    dog_name = db.Column(db.String(80), nullable=False)
    class_name = db.Column(db.String(80), nullable=False)
    event = db.relationship("Event")


def current_user() -> User | None:
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "reference_date": REFERENCE_DATE}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def tokens(query: str) -> list[str]:
    return [
        token
        for token in re.split(r"\W+", query.lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def scored_search(query: str, rows, fields: list[str]):
    parts = tokens(query)
    if not parts:
        return list(rows)
    scored = []
    for row in rows:
        haystack = " ".join(str(getattr(row, field, "") or "") for field in fields).lower()
        score = sum(1 for part in parts if part in haystack)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], getattr(item[1], "name", getattr(item[1], "title", ""))))
    return [row for _, row in scored]


def breed_image_style(slug: str) -> str:
    palette = {
        "sporting": "#006778",
        "hound": "#9a3412",
        "working": "#1d4ed8",
        "terrier": "#7c2d12",
        "toy": "#be185d",
        "non-sporting": "#047857",
        "herding": "#4f46e5",
    }
    breed = Breed.query.filter_by(slug=slug).first()
    color = palette.get((breed.group if breed else "").lower(), "#6b7280")
    return f"background: linear-gradient(135deg, {color}, #f5f0e6);"


@app.route("/")
def index():
    featured = Breed.query.order_by(Breed.name).limit(6).all()
    events = Event.query.order_by(Event.starts_on).limit(3).all()
    articles = Article.query.order_by(Article.id.desc()).limit(3).all()
    return render_template("index.html", featured=featured, events=events, articles=articles)


@app.route("/breeds")
def breeds():
    query = request.args.get("q", "").strip()
    group = request.args.get("group", "").strip()
    size = request.args.get("size", "").strip()
    rows = Breed.query.order_by(Breed.name).all()
    if group:
        rows = [breed for breed in rows if breed.group == group]
    if size:
        rows = [breed for breed in rows if breed.size == size]
    if query:
        rows = scored_search(query, rows, ["name", "group", "temperament", "overview"])
    groups = [row[0] for row in db.session.query(Breed.group).distinct().order_by(Breed.group)]
    sizes = [row[0] for row in db.session.query(Breed.size).distinct().order_by(Breed.size)]
    return render_template("breeds.html", breeds=rows, groups=groups, sizes=sizes, query=query, group=group, size=size)


@app.route("/breeds/<slug>")
def breed_detail(slug):
    breed = Breed.query.filter_by(slug=slug).first_or_404()
    related = (
        Breed.query.filter(Breed.group == breed.group, Breed.slug != breed.slug)
        .order_by(Breed.name)
        .limit(4)
        .all()
    )
    saved = False
    user = current_user()
    if user:
        saved = SavedBreed.query.filter_by(user_id=user.id, breed_id=breed.id).first() is not None
    return render_template("breed_detail.html", breed=breed, related=related, saved=saved)


@app.route("/breeds/<slug>/save", methods=["POST"])
@login_required
def save_breed(slug):
    breed = Breed.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    existing = SavedBreed.query.filter_by(user_id=user.id, breed_id=breed.id).first()
    if not existing:
        db.session.add(SavedBreed(user_id=user.id, breed_id=breed.id, note=request.form.get("note", "")))
        db.session.commit()
        flash(f"{breed.name} was saved to your profile.", "success")
    return redirect(url_for("breed_detail", slug=slug))


@app.route("/breed-selector", methods=["GET", "POST"])
def breed_selector():
    matches = []
    answers = {}
    if request.method == "POST":
        answers = {
            "home": request.form.get("home", "apartment"),
            "energy": int(request.form.get("energy", "3")),
            "grooming": int(request.form.get("grooming", "3")),
            "children": int(request.form.get("children", "3")),
        }
        for breed in Breed.query.all():
            score = 0
            score += 6 - abs(breed.energy - answers["energy"])
            score += 6 - abs(breed.grooming - answers["grooming"])
            score += 6 - abs(breed.good_with_children - answers["children"])
            score += breed.apartment_score if answers["home"] == "apartment" else min(5, breed.energy + 1)
            matches.append((score, breed))
        matches.sort(key=lambda item: (-item[0], item[1].name))
        matches = matches[:8]
    return render_template("selector.html", matches=matches, answers=answers)


@app.route("/compare")
def compare():
    selected = [slug for slug in request.args.getlist("breed") if slug]
    breeds_for_picker = Breed.query.order_by(Breed.name).all()
    compared = Breed.query.filter(Breed.slug.in_(selected)).order_by(Breed.name).all() if selected else []
    return render_template("compare.html", breeds=breeds_for_picker, compared=compared, selected=selected)


@app.route("/articles")
def articles():
    category = request.args.get("category", "")
    rows = Article.query.order_by(Article.title).all()
    if category:
        rows = [article for article in rows if article.category == category]
    categories = [row[0] for row in db.session.query(Article.category).distinct().order_by(Article.category)]
    return render_template("articles.html", articles=rows, categories=categories, category=category)


@app.route("/articles/<slug>")
def article_detail(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    return render_template("article_detail.html", article=article)


@app.route("/events")
def events():
    event_type = request.args.get("type", "")
    state = request.args.get("state", "")
    rows = Event.query.order_by(Event.starts_on).all()
    if event_type:
        rows = [event for event in rows if event.event_type == event_type]
    if state:
        rows = [event for event in rows if event.state == state]
    types = [row[0] for row in db.session.query(Event.event_type).distinct().order_by(Event.event_type)]
    states = [row[0] for row in db.session.query(Event.state).distinct().order_by(Event.state)]
    return render_template("events.html", events=rows, types=types, states=states, event_type=event_type, state=state)


@app.route("/events/<slug>", methods=["GET", "POST"])
def event_detail(slug):
    event = Event.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        if not current_user():
            flash("Sign in before registering for an event.", "info")
            return redirect(url_for("login", next=request.path))
        reg = EventRegistration(
            user_id=current_user().id,
            event_id=event.id,
            dog_name=request.form.get("dog_name", "").strip() or "TBD",
            class_name=request.form.get("class_name", "Beginner Novice"),
        )
        db.session.add(reg)
        db.session.commit()
        flash("Registration saved in your AKC profile.", "success")
        return redirect(url_for("account"))
    return render_template("event_detail.html", event=event)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    breed_results = scored_search(query, Breed.query.all(), ["name", "group", "temperament", "overview"])[:8] if query else []
    article_results = scored_search(query, Article.query.all(), ["title", "category", "summary", "body"])[:8] if query else []
    event_results = scored_search(query, Event.query.all(), ["title", "event_type", "city", "description"])[:8] if query else []
    return render_template(
        "search.html",
        query=query,
        breed_results=breed_results,
        article_results=article_results,
        event_results=event_results,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        username = request.form.get("username", "").strip()
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("That email or username is already registered.", "error")
        else:
            user = User(
                email=email,
                username=username,
                display_name=request.form.get("display_name", username),
                password_hash=generate_password_hash(request.form.get("password", "TestPass123!")),
                household=request.form.get("household", "Apartment"),
                activity_level=request.form.get("activity_level", "Moderate"),
                experience=request.form.get("experience", "First-time owner"),
            )
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("Your AKC profile is ready.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    saved = SavedBreed.query.filter_by(user_id=user.id).all()
    registrations = EventRegistration.query.filter_by(user_id=user.id).all()
    return render_template("account.html", user=user, saved=saved, registrations=registrations)


@app.route("/account/profile", methods=["POST"])
@login_required
def update_profile():
    user = current_user()
    user.household = request.form.get("household", user.household)
    user.activity_level = request.form.get("activity_level", user.activity_level)
    user.experience = request.form.get("experience", user.experience)
    db.session.commit()
    flash("Profile preferences updated.", "success")
    return redirect(url_for("account"))


@app.route("/_health")
def health():
    return {"ok": True, "site": "akc"}


@app.route("/breed-art/<slug>.svg")
def breed_art(slug):
    breed = Breed.query.filter_by(slug=slug).first()
    if not breed:
        abort(404)
    initials = "".join(part[0] for part in breed.name.split()[:2]).upper()
    color = {
        "Sporting": "#006778",
        "Hound": "#9a3412",
        "Working": "#1d4ed8",
        "Terrier": "#7c2d12",
        "Toy": "#be185d",
        "Non-Sporting": "#047857",
        "Herding": "#4f46e5",
    }.get(breed.group, "#4b5563")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" role="img" aria-label="{breed.name}">
<rect width="720" height="480" fill="#f5f0e6"/>
<circle cx="140" cy="90" r="180" fill="{color}" opacity=".14"/>
<circle cx="590" cy="405" r="210" fill="{color}" opacity=".18"/>
<path d="M221 334c-24-51 6-118 64-147 41-21 90-22 132-2 27 13 48 35 61 62 43 9 72 42 72 81 0 47-42 85-94 85H300c-37 0-69-20-79-79z" fill="{color}" opacity=".88"/>
<path d="M302 182l-52-68c-9-12-2-29 13-30l89-7c18-1 31 17 23 33l-35 72z" fill="{color}"/>
<path d="M456 184l49-67c9-12 28-9 32 5l26 88c5 17-12 31-27 23l-80-42z" fill="{color}"/>
<circle cx="344" cy="263" r="12" fill="#111827"/>
<circle cx="461" cy="263" r="12" fill="#111827"/>
<path d="M382 306c21 16 43 16 65 0" fill="none" stroke="#111827" stroke-width="14" stroke-linecap="round"/>
<text x="38" y="70" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#111827">{initials}</text>
<text x="38" y="112" font-family="Arial, sans-serif" font-size="22" fill="#4b5563">{breed.group} Group</text>
</svg>"""
    return app.response_class(svg, mimetype="image/svg+xml")


def seed_database():
    if Breed.query.count() > 0:
        return
    breeds = [
        ("labrador-retriever", "Labrador Retriever", "Sporting", "Large", 5, 2, 5, 5, 3, "11-13 years", "21.5-24.5 in", "55-80 lb", "Friendly, active, outgoing"),
        ("golden-retriever", "Golden Retriever", "Sporting", "Large", 4, 4, 5, 5, 3, "10-12 years", "21.5-24 in", "55-75 lb", "Intelligent, friendly, devoted"),
        ("french-bulldog", "French Bulldog", "Non-Sporting", "Small", 2, 2, 3, 4, 5, "10-12 years", "11-13 in", "under 28 lb", "Adaptable, playful, smart"),
        ("german-shepherd-dog", "German Shepherd Dog", "Herding", "Large", 5, 3, 5, 4, 2, "7-10 years", "22-26 in", "50-90 lb", "Confident, courageous, smart"),
        ("poodle-standard", "Poodle Standard", "Non-Sporting", "Large", 4, 5, 5, 5, 3, "10-18 years", "over 15 in", "40-70 lb", "Active, proud, very smart"),
        ("beagle", "Beagle", "Hound", "Medium", 4, 2, 3, 5, 4, "10-15 years", "13-15 in", "20-30 lb", "Merry, curious, friendly"),
        ("dachshund", "Dachshund", "Hound", "Small", 3, 2, 3, 3, 5, "12-16 years", "8-9 in", "16-32 lb", "Friendly, curious, spunky"),
        ("rottweiler", "Rottweiler", "Working", "Large", 4, 2, 4, 4, 2, "9-10 years", "22-27 in", "80-135 lb", "Loyal, loving, confident guardian"),
        ("cavalier-king-charles-spaniel", "Cavalier King Charles Spaniel", "Toy", "Small", 3, 3, 4, 5, 5, "12-15 years", "12-13 in", "13-18 lb", "Affectionate, gentle, graceful"),
        ("australian-shepherd", "Australian Shepherd", "Herding", "Medium", 5, 3, 5, 4, 2, "12-15 years", "18-23 in", "40-65 lb", "Smart, work-oriented, exuberant"),
        ("boxer", "Boxer", "Working", "Large", 4, 2, 4, 5, 3, "10-12 years", "21.5-25 in", "50-80 lb", "Bright, fun-loving, active"),
        ("border-collie", "Border Collie", "Herding", "Medium", 5, 3, 5, 4, 1, "12-15 years", "18-22 in", "30-55 lb", "Affectionate, smart, energetic"),
        ("shih-tzu", "Shih Tzu", "Toy", "Small", 2, 5, 3, 4, 5, "10-18 years", "9-10.5 in", "9-16 lb", "Affectionate, playful, outgoing"),
        ("bernese-mountain-dog", "Bernese Mountain Dog", "Working", "Large", 3, 4, 4, 5, 2, "7-10 years", "23-27.5 in", "70-115 lb", "Good-natured, calm, strong"),
        ("doberman-pinscher", "Doberman Pinscher", "Working", "Large", 5, 2, 5, 4, 2, "10-12 years", "24-28 in", "60-100 lb", "Loyal, fearless, alert"),
        ("cocker-spaniel", "Cocker Spaniel", "Sporting", "Medium", 3, 4, 4, 5, 4, "10-14 years", "13.5-15.5 in", "20-30 lb", "Gentle, smart, happy"),
        ("great-dane", "Great Dane", "Working", "Large", 3, 2, 3, 4, 2, "7-10 years", "28-32 in", "110-175 lb", "Friendly, patient, dependable"),
        ("papillon", "Papillon", "Toy", "Small", 4, 3, 5, 4, 5, "14-16 years", "8-11 in", "5-10 lb", "Alert, friendly, happy"),
        ("whippet", "Whippet", "Hound", "Medium", 4, 1, 3, 4, 4, "12-15 years", "18-22 in", "25-40 lb", "Affectionate, playful, calm"),
        ("west-highland-white-terrier", "West Highland White Terrier", "Terrier", "Small", 4, 3, 3, 4, 4, "13-15 years", "10-11 in", "15-20 lb", "Loyal, happy, entertaining"),
        ("siberian-husky", "Siberian Husky", "Working", "Medium", 5, 3, 3, 4, 2, "12-14 years", "20-23.5 in", "35-60 lb", "Loyal, mischievous, outgoing"),
        ("boston-terrier", "Boston Terrier", "Non-Sporting", "Small", 3, 1, 4, 5, 5, "11-13 years", "15-17 in", "12-25 lb", "Friendly, bright, amusing"),
        ("newfoundland", "Newfoundland", "Working", "Large", 3, 5, 4, 5, 2, "9-10 years", "26-28 in", "100-150 lb", "Sweet, patient, devoted"),
        ("chihuahua", "Chihuahua", "Toy", "Small", 3, 1, 3, 3, 5, "14-16 years", "5-8 in", "under 6 lb", "Graceful, charming, sassy"),
    ]
    for slug, name, group, size, energy, grooming, trainability, children, apartment, life, height, weight, temperament in breeds:
        db.session.add(Breed(
            slug=slug,
            name=name,
            group=group,
            size=size,
            energy=energy,
            grooming=grooming,
            trainability=trainability,
            good_with_children=children,
            apartment_score=apartment,
            life_expectancy=life,
            height=height,
            weight=weight,
            temperament=temperament,
            overview=f"The {name} profile summarizes AKC-style breed history, temperament, size, and owner fit for benchmark browsing tasks.",
            care=f"{name} owners should plan routine veterinary care, structured socialization, nail trims, dental care, and age-appropriate nutrition.",
            exercise=f"Exercise needs are rated {energy}/5. Use the rating with household size and training goals when comparing breeds.",
        ))
    articles = [
        ("how-to-choose-the-right-dog-breed", "How to Choose the Right Dog Breed", "Getting Started", "AKC Staff", 7, "Match lifestyle, home, grooming tolerance, and training expectations before choosing a puppy."),
        ("puppy-socialization-checklist", "Puppy Socialization Checklist", "Puppies", "Dr. Mara Chen", 6, "A week-by-week checklist for confident, polite puppies."),
        ("canine-good-citizen-overview", "Canine Good Citizen Overview", "Training", "Evan Porter", 5, "Understand the ten skills in AKC's CGC program and how to prepare."),
        ("dog-grooming-basics", "Dog Grooming Basics by Coat Type", "Health", "Priya Shah", 8, "Compare grooming routines for smooth, double, curly, and drop coats."),
        ("first-dog-show-guide", "Your First AKC Dog Show", "Sports", "Lena Morris", 6, "What to bring, where to check in, and how conformation rings are organized."),
        ("responsible-breeder-questions", "Questions to Ask a Responsible Breeder", "Puppies", "Noah Rivera", 7, "Health testing, contracts, pedigrees, and early socialization questions."),
        ("summer-safety-for-dogs", "Summer Safety for Dogs", "Health", "AKC Staff", 4, "Heat, hydration, pavement checks, and safe travel reminders."),
        ("agility-training-introduction", "Introduction to Agility Training", "Sports", "Mina Brooks", 5, "A beginner path from foundation skills to local trials."),
        ("therapy-dog-title-basics", "Therapy Dog Title Basics", "Training", "Owen Kim", 5, "Visits, documentation, and temperament expectations for therapy dog teams."),
        ("apartment-dog-owner-tips", "Apartment Dog Owner Tips", "Lifestyle", "AKC Staff", 6, "Noise, elevators, exercise routines, and neighbor-friendly planning."),
    ]
    for slug, title, category, author, minutes, summary in articles:
        db.session.add(Article(slug=slug, title=title, category=category, author=author, read_minutes=minutes, summary=summary, body=summary + " The mirror includes practical steps, comparison cues, and realistic navigation text so agents can ground answers in visible content."))
    events = [
        ("national-obedience-classic", "National Obedience Classic", "Obedience", "Orlando", "FL", date(2026, 6, 14), "Orange County Convention Center"),
        ("midwest-agility-trial", "Midwest Agility Trial", "Agility", "Madison", "WI", date(2026, 7, 9), "Dane County Expo Center"),
        ("puppy-training-webinar", "Puppy Training Webinar", "Education", "Online", "US", date(2026, 6, 3), "AKC Virtual Classroom"),
        ("terrier-club-specialty", "Terrier Club Specialty", "Conformation", "Columbus", "OH", date(2026, 8, 21), "Ohio Expo Center"),
        ("canine-good-citizen-test-ny", "Canine Good Citizen Test", "Training", "New York", "NY", date(2026, 6, 27), "Riverside Training Hall"),
        ("herding-instinct-clinic", "Herding Instinct Clinic", "Herding", "Fort Worth", "TX", date(2026, 9, 5), "Lone Star Stockdog Arena"),
        ("junior-handler-workshop", "Junior Handler Workshop", "Education", "Seattle", "WA", date(2026, 7, 18), "Evergreen Kennel Club"),
        ("sporting-dog-field-day", "Sporting Dog Field Day", "Field Trial", "Lancaster", "PA", date(2026, 10, 2), "Brandywine Preserve"),
    ]
    for slug, title, event_type, city, state, starts_on, venue in events:
        db.session.add(Event(slug=slug, title=title, event_type=event_type, city=city, state=state, starts_on=starts_on, venue=venue, description=f"{title} offers AKC-style schedules, entry information, class selection, and local venue details."))
    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "Apartment", "Moderate", "First-time owner", ["french-bulldog", "cavalier-king-charles-spaniel", "boston-terrier"]),
        ("bob_c", "bob.c@test.com", "Bob Chen", "House with yard", "High", "Sports competitor", ["border-collie", "australian-shepherd", "labrador-retriever"]),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Suburban home", "Low", "Family owner", ["golden-retriever", "newfoundland", "beagle"]),
        ("david_k", "david.k@test.com", "David Kim", "Condo", "Moderate", "Experienced owner", ["poodle-standard", "whippet", "papillon"]),
    ]
    for username, email, display_name, household, activity, experience, saved_slugs in users:
        user = User(username=username, email=email, display_name=display_name, household=household, activity_level=activity, experience=experience, password_hash=generate_password_hash("TestPass123!"))
        db.session.add(user)
        db.session.flush()
        for slug in saved_slugs:
            breed = Breed.query.filter_by(slug=slug).first()
            db.session.add(SavedBreed(user_id=user.id, breed_id=breed.id, note="Saved benchmark profile breed."))
    db.session.commit()


with app.app_context():
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
