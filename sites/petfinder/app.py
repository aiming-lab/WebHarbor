from __future__ import annotations

import hmac
import os
import re
import secrets
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = {
    "name": "Petfinder",
    "url": "https://www.petfinder.com/",
    "tagline": "Find your new best friend and adopt a pet.",
    "slug": "petfinder",
}

INFO_PAGES = {
    "petfinder": ("About Petfinder", "Petfinder connects adopters with shelters and rescues so more pets can find lasting homes."),
    "shelters-rescues": ("Animal Shelters & Rescues", "Learn how shelters and rescue groups care for pets and help adopters make a thoughtful match."),
    "foundation": ("Petfinder Foundation", "Supporting shelters and rescue organizations with resources that help pets in their care."),
    "faqs": ("Frequently Asked Questions", "Answers to common questions about searching for pets, adoption, accounts, and contacting shelters."),
    "mobile-app": ("Petfinder Mobile App", "Keep your pet search close at hand and revisit the pets that caught your eye."),
    "news": ("News Center", "Stories and updates from the pet adoption community."),
    "widgets": ("Put Petfinder on Your Site", "Help more people discover adoptable pets by sharing Petfinder resources."),
    "contact": ("Contact Us", "Find the right place to get help with Petfinder, a pet profile, or an adoption question."),
    "dog-breeds": ("Dog Breeds", "Explore dog breed traits while remembering that every individual pet has a unique history and personality."),
    "feeding-dogs": ("Feeding Your Dog", "Build a consistent feeding routine with guidance from your veterinarian."),
    "dog-behavior": ("Dog Behavior", "Understand everyday dog communication and support calm, positive habits."),
    "dog-health": ("Dog Health & Wellness", "Plan preventive care, exercise, grooming, and regular veterinary visits."),
    "dog-training": ("Dog Training", "Use patient, reward-based training to help your dog learn and feel secure."),
    "cat-breeds": ("Cat Breeds", "Learn about common cat traits while choosing a companion by individual fit."),
    "feeding-cats": ("Feeding Your Cat", "Choose an age-appropriate diet and discuss nutrition questions with your veterinarian."),
    "cat-behavior": ("Cat Behavior", "Read feline body language and create spaces where cats can play, rest, and retreat."),
    "cat-health": ("Cat Health & Wellness", "Support your cat with preventive care, enrichment, grooming, and regular checkups."),
    "cat-training": ("Cat Training", "Positive reinforcement can help cats learn routines and enjoy cooperative care."),
    "terms": ("Terms of Service", "Terms for using this local Petfinder experience."),
    "privacy": ("Privacy Policy", "How this local Petfinder experience handles account and session information."),
    "accessibility": ("Accessibility", "Petfinder is committed to an experience people can navigate with different devices and abilities."),
    "sitemap": ("Sitemap", "Browse the main areas of this Petfinder experience."),
}

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config.update(
    SECRET_KEY="webharbor-petfinder-dev-key",
    MAX_CONTENT_LENGTH=64 * 1024,
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "PETFINDER_DATABASE_URI",
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'petfinder.db')}",
    ),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    home_location = db.Column(db.String(100), default="New York, NY")
    sort_preference = db.Column(db.String(80), default="Nearest first")


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    species = db.Column(db.String(40), nullable=False)
    breed = db.Column(db.String(120), nullable=False)
    age = db.Column(db.String(40), nullable=False)
    size = db.Column(db.String(40), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    shelter = db.Column(db.String(180), nullable=False)
    days_on_petfinder = db.Column(db.Integer, nullable=False)
    adoption_fee = db.Column(db.Integer, nullable=False)
    coat = db.Column(db.String(40), nullable=False)
    color = db.Column(db.String(80), nullable=False)
    good_with_children = db.Column(db.Boolean, default=False, nullable=False)
    good_with_dogs = db.Column(db.Boolean, default=False, nullable=False)
    good_with_cats = db.Column(db.Boolean, default=False, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    story = db.Column(db.Text, nullable=False)
    image_index = db.Column(db.Integer, nullable=False)

    @property
    def search_blob(self) -> str:
        return " ".join(
            (
                self.name,
                self.species,
                self.breed,
                self.age,
                self.size,
                self.gender,
                self.location,
                self.shelter,
                self.coat,
                self.color,
                self.summary,
                self.story,
            )
        )


class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    read_minutes = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    section_heading = db.Column(db.String(180), nullable=False)
    checklist = db.Column(db.Text, nullable=False)

    @property
    def paragraphs(self) -> list[str]:
        return [part.strip() for part in self.body.split("\n\n") if part.strip()]

    @property
    def checklist_items(self) -> list[str]:
        return [item.strip() for item in self.checklist.split("|") if item.strip()]


class SavedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    listing = db.relationship("Listing")
    __table_args__ = (db.UniqueConstraint("user_id", "listing_id", name="uq_saved_user_listing"),)


class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="Submitted")
    listing = db.relationship("Listing")


def current_user() -> User | None:
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf_token"] = token
    return token


@app.before_request
def protect_post_requests():
    if request.method != "POST":
        return None
    expected = session.get("csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, submitted):
        abort(400)
    return None


@app.context_processor
def inject_common():
    return {
        "config": CONFIG,
        "csrf_token": csrf_token,
        "current_user": current_user(),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Sign in to save pets and contact shelters.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-") or "pet"


def safe_next_url(target: str | None) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return url_for("account")
    match = re.fullmatch(r"/(?:pets|listings)/([^/]+)/save", target)
    if match:
        return url_for("listing_detail", slug=match.group(1))
    match = re.fullmatch(r"/(?:pets|listings)/([^/]+)/inquire", target)
    if match:
        return url_for("listing_detail", slug=match.group(1))
    return target


def tokenize(query: str) -> list[str]:
    stop_words = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with"}
    return [part for part in re.split(r"\W+", query.casefold()) if len(part) > 1 and part not in stop_words]


def scored_search(query: str, rows, fields: list[str]):
    parts = tokenize(query)
    if not parts:
        return []
    scored = []
    for row in rows:
        haystack = " ".join(str(getattr(row, field, "") or "") for field in fields).casefold()
        score = sum(part in haystack for part in parts)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], getattr(item[1], "name", getattr(item[1], "title", ""))))
    return [row for _, row in scored]


@app.route("/")
def index():
    ordered = Listing.query.order_by(Listing.days_on_petfinder.asc(), Listing.id.asc()).all()
    guides = Guide.query.order_by(Guide.id.asc()).limit(3).all()
    return render_template(
        "index.html",
        nearby_primary=ordered[:4],
        nearby_secondary=ordered[4:8],
        total_listings=len(ordered),
        guides=guides,
    )


@app.route("/listings")
def legacy_listings():
    query = request.query_string.decode()
    return redirect(url_for("listings") + (f"?{query}" if query else ""), code=301)


@app.route("/pets")
def listings():
    filters = {
        "species": request.args.get("species", ""),
        "location": request.args.get("location", ""),
        "breed": request.args.get("breed", ""),
        "age": request.args.get("age", ""),
        "size": request.args.get("size", ""),
        "gender": request.args.get("gender", ""),
        "coat": request.args.get("coat", ""),
        "color": request.args.get("color", ""),
        "days": request.args.get("days", ""),
        "shelter": request.args.get("shelter", ""),
        "good_with_children": request.args.get("good_with_children", ""),
        "good_with_dogs": request.args.get("good_with_dogs", ""),
        "good_with_cats": request.args.get("good_with_cats", ""),
    }
    rows = Listing.query.all()
    for field in ("species", "location", "breed", "age", "size", "gender", "coat", "color", "shelter"):
        if filters[field]:
            rows = [row for row in rows if getattr(row, field) == filters[field]]
    for field in ("good_with_children", "good_with_dogs", "good_with_cats"):
        if filters[field] == "1":
            rows = [row for row in rows if getattr(row, field)]
    if filters["days"].isdigit():
        rows = [row for row in rows if row.days_on_petfinder <= int(filters["days"])]

    sort_key = request.args.get("sort", "newest")
    if sort_key == "longest":
        rows.sort(key=lambda row: (-row.days_on_petfinder, row.id))
    elif sort_key == "name":
        rows.sort(key=lambda row: (row.name.casefold(), row.id))
    else:
        sort_key = "newest"
        rows.sort(key=lambda row: (row.days_on_petfinder, row.id))

    total = len(rows)
    per_page = 12
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(request.args.get("page", default=1, type=int) or 1, 1), total_pages)
    start = (page - 1) * per_page
    page_rows = rows[start:start + per_page]

    distinct = lambda field: [
        value[0]
        for value in db.session.query(field).distinct().order_by(field).all()
    ]
    options = {
        "species": distinct(Listing.species),
        "locations": distinct(Listing.location),
        "breeds": distinct(Listing.breed),
        "ages": ["Baby", "Young", "Adult", "Senior"],
        "sizes": ["Small", "Medium", "Large"],
        "genders": ["Female", "Male"],
        "coats": distinct(Listing.coat),
        "colors": distinct(Listing.color),
        "shelters": distinct(Listing.shelter),
    }
    query_args = {key: value for key, value in filters.items() if value}
    query_args["sort"] = sort_key
    page_links = [
        (number, url_for("listings", **query_args, page=number))
        for number in range(1, total_pages + 1)
    ]
    return render_template(
        "listings.html",
        rows=page_rows,
        filters=filters,
        options=options,
        sort_key=sort_key,
        total=total,
        page=page,
        total_pages=total_pages,
        page_links=page_links,
        previous_url=url_for("listings", **query_args, page=page - 1) if page > 1 else None,
        next_url=url_for("listings", **query_args, page=page + 1) if page < total_pages else None,
    )


@app.route("/listings/<slug>")
def legacy_listing_detail(slug):
    return redirect(url_for("listing_detail", slug=slug), code=301)


@app.route("/pets/<slug>")
def listing_detail(slug):
    listing = Listing.query.filter_by(slug=slug).first_or_404()
    related = (
        Listing.query.filter(Listing.species == listing.species, Listing.slug != listing.slug)
        .order_by(Listing.days_on_petfinder.asc())
        .limit(3)
        .all()
    )
    return render_template("listing_detail.html", listing=listing, related=related)


@app.route("/pets/<slug>/save", methods=["POST"])
@login_required
def save_listing(slug):
    listing = Listing.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    existing = SavedItem.query.filter_by(user_id=user.id, listing_id=listing.id).first()
    if not existing:
        db.session.add(SavedItem(user_id=user.id, listing_id=listing.id))
        db.session.commit()
        flash(f"Saved {listing.name}.", "success")
    else:
        flash(f"{listing.name} is already in your favorites.", "info")
    return redirect(url_for("account"))


@app.route("/pets/<slug>/inquire", methods=["POST"])
@login_required
def inquire(slug):
    listing = Listing.query.filter_by(slug=slug).first_or_404()
    message = request.form.get("message", "").strip()
    if len(message) < 10:
        flash("Add a short message for the shelter.", "error")
        return redirect(url_for("listing_detail", slug=slug))
    db.session.add(
        Inquiry(
            user_id=current_user().id,
            listing_id=listing.id,
            message=message,
            status="Submitted",
        )
    )
    db.session.commit()
    flash(f"Inquiry submitted for {listing.name}.", "success")
    return redirect(url_for("account"))


@app.route("/guides")
def guides():
    rows = Guide.query.order_by(Guide.id.asc()).all()
    category = request.args.get("category", "").strip()
    if category:
        rows = [row for row in rows if row.category.casefold() == category.casefold()]
    return render_template("guides.html", rows=rows, category=category)


@app.route("/guides/<slug>")
def guide_detail(slug):
    guide = Guide.query.filter_by(slug=slug).first_or_404()
    return render_template("guide_detail.html", guide=guide)


@app.route("/about/<slug>")
def info_page(slug):
    page = INFO_PAGES.get(slug)
    if not page:
        abort(404)
    return render_template("info.html", title=page[0], summary=page[1], slug=slug)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    listing_results = scored_search(query, Listing.query.all(), ["search_blob"])[:10]
    if location:
        listing_results = [item for item in listing_results if item.location == location]
    guide_results = scored_search(query, Guide.query.all(), ["title", "category", "summary", "body"])[:6]
    return render_template(
        "search.html",
        query=query,
        location=location,
        locations=[row[0] for row in db.session.query(Listing.location).distinct().order_by(Listing.location).all()],
        listing_results=listing_results,
        guide_results=guide_results,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").casefold().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.display_name}.", "success")
            return redirect(safe_next_url(request.args.get("next")))
        flash("Email or password did not match.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    saved = SavedItem.query.filter_by(user_id=user.id).order_by(SavedItem.id.asc()).all()
    inquiries = Inquiry.query.filter_by(user_id=user.id).order_by(Inquiry.id.desc()).all()
    return render_template("account.html", saved=saved, inquiries=inquiries)


@app.route("/account/preferences", methods=["POST"])
@login_required
def update_preferences():
    user = current_user()
    home_location = request.form.get("home_location", "").strip()
    sort_preference = request.form.get("sort_preference", "").strip()
    allowed_sorts = {"Nearest first", "Newest pets first", "Recently updated"}
    if home_location:
        user.home_location = home_location[:100]
    if sort_preference in allowed_sorts:
        user.sort_preference = sort_preference
    db.session.commit()
    flash("Preferences updated.", "success")
    return redirect(url_for("account"))


@app.route("/_health")
def health():
    return {"ok": True, "site": CONFIG["slug"]}


def seed_database():
    if Listing.query.count() > 0:
        return
    listings = [
        ("Milo Labrador Mix", "Dog", "Labrador Retriever Mix", "Adult", "Large", "Male", "New York, NY", "Hudson Valley Animal Rescue", 3, 325, "Short", "Yellow / Cream", True, True, False, "A friendly, house-trained companion who loves long walks and puzzle toys.", "Milo settles quickly after a walk and enjoys learning new cues. His foster family says he is happiest beside people and would do well with respectful children.", 0),
        ("Luna Domestic Shorthair", "Cat", "Domestic Shorthair", "Young", "Small", "Female", "Chicago, IL", "PAWS Chicago", 2, 150, "Short", "Orange / White", True, False, True, "A curious young cat who likes window seats, wand toys, and other cats.", "Luna is confident in a quiet home and warms up quickly with play. She has lived successfully with another calm cat.", 1),
        ("Nori Rabbit", "Rabbit", "Holland Lop Mix", "Adult", "Small", "Female", "Seattle, WA", "Seattle Animal Shelter", 6, 75, "Short", "White / Brown", True, False, False, "A gentle rabbit who enjoys leafy greens and supervised floor time.", "Nori is litter-box trained and likes cardboard tunnels. She needs an indoor home with space to stretch and explore.", 2),
        ("Sunny Guinea Pig", "Guinea Pig", "American", "Young", "Small", "Male", "Austin, TX", "Austin Humane Society", 4, 40, "Short", "Tricolor", True, False, False, "A social guinea pig who whistles for vegetables and enjoys hideouts.", "Sunny is used to gentle handling and would thrive with daily enrichment and plenty of hay.", 3),
        ("Maple Senior Beagle", "Dog", "Beagle", "Senior", "Medium", "Female", "Chicago, IL", "One Tail at a Time", 18, 250, "Short", "Tricolor", True, True, True, "A mellow senior who follows her nose and loves soft blankets.", "Maple prefers an easy pace and a predictable routine. She is comfortable with calm pets and older children.", 4),
        ("Atlas German Shepherd", "Dog", "German Shepherd Dog", "Adult", "Large", "Male", "New York, NY", "Big Apple Rescue", 7, 350, "Medium", "Black / Tan", False, True, False, "A focused, athletic dog looking for an experienced adopter.", "Atlas knows several cues and enjoys structured training. He needs an adult home that can continue his confidence work.", 5),
        ("Scout Border Collie", "Dog", "Border Collie", "Young", "Medium", "Male", "Boston, MA", "MSPCA-Angell", 4, 300, "Medium", "Black / White", True, True, False, "A bright young dog who enjoys agility games and learning tricks.", "Scout is energetic and affectionate. A family ready for daily exercise and positive training will see him thrive.", 6),
        ("Hazel Chihuahua", "Dog", "Chihuahua", "Adult", "Small", "Female", "New York, NY", "Second Chance Rescue", 2, 275, "Short", "Tan", True, False, True, "A small lap dog with a big personality and a love of sunny spots.", "Hazel bonds closely with her people. Slow introductions help her feel comfortable around new dogs.", 7),
        ("Ivy Calico", "Cat", "Calico", "Adult", "Small", "Female", "Austin, TX", "Austin Pets Alive!", 9, 125, "Short", "Calico", True, False, True, "A chatty calico who likes gentle brushing and quiet company.", "Ivy greets familiar people with a soft chirp and prefers a calm room with high perches.", 8),
        ("Cleo Tuxedo Cat", "Cat", "Domestic Shorthair", "Young", "Small", "Female", "Seattle, WA", "Seattle Humane", 6, 140, "Short", "Black / White", True, True, True, "A playful tuxedo cat who carries toy mice around the house.", "Cleo is outgoing, food motivated, and comfortable with friendly cats and dogs after gradual introductions.", 9),
        ("Poppy Tabby", "Cat", "Domestic Shorthair", "Adult", "Small", "Female", "New York, NY", "Bideawee", 12, 135, "Short", "Brown Tabby", False, False, True, "A thoughtful tabby who likes puzzle feeders and covered beds.", "Poppy takes time to trust, then becomes a loyal companion. She would prefer a home without young children.", 10),
        ("Willow Maine Coon", "Cat", "Maine Coon Mix", "Senior", "Large", "Female", "Boston, MA", "Animal Rescue League of Boston", 11, 100, "Long", "Gray", True, False, True, "A gentle long-haired cat who enjoys brushing and afternoon naps.", "Willow is easygoing and affectionate. Regular grooming keeps her coat comfortable and shiny.", 11),
        ("Ollie Poodle Mix", "Dog", "Poodle Mix", "Senior", "Medium", "Male", "Chicago, IL", "Wright-Way Rescue", 5, 225, "Curly", "Apricot", True, True, True, "A cheerful senior who still enjoys neighborhood walks and fetch.", "Ollie is adaptable, friendly with visitors, and happiest when included in everyday family life.", 7),
    ]
    additional_listings = [
        ("Nova Siberian Husky", "Dog", "Siberian Husky", "Young", "Large", "Female", "New York, NY", "ASPCA Adoption Center", 8, 350, "Medium", "Gray / White", True, True, False, 0),
        ("Bruno Mastiff Mix", "Dog", "Mastiff Mix", "Adult", "Large", "Male", "New York, NY", "Urban Resource Institute", 13, 300, "Short", "Fawn", False, True, False, 5),
        ("Daisy Cocker Spaniel", "Dog", "Cocker Spaniel", "Adult", "Medium", "Female", "New York, NY", "Bideawee", 16, 275, "Medium", "Golden", True, True, True, 7),
        ("Remy Terrier Mix", "Dog", "Terrier Mix", "Senior", "Small", "Male", "New York, NY", "Animal Haven", 21, 225, "Wire", "Black / Tan", True, False, True, 9),
        ("Pepper Great Dane", "Dog", "Great Dane", "Baby", "Large", "Female", "New York, NY", "Animal Care Centers of NYC", 1, 400, "Short", "Black", True, True, False, 2),
        ("Winnie Greyhound", "Dog", "Greyhound", "Adult", "Large", "Female", "Chicago, IL", "Chicago Canine Rescue", 9, 300, "Short", "Brindle", True, True, True, 6),
        ("Theo Boxer Mix", "Dog", "Boxer Mix", "Young", "Medium", "Male", "Chicago, IL", "PAWS Chicago", 11, 285, "Short", "Brown / White", True, True, False, 8),
        ("Archie Dachshund", "Dog", "Dachshund", "Adult", "Small", "Male", "Chicago, IL", "One Tail at a Time", 23, 250, "Short", "Red", True, False, True, 10),
        ("Sage Shepherd Mix", "Dog", "Shepherd Mix", "Adult", "Large", "Female", "Chicago, IL", "Chicago Animal Care and Control", 45, 200, "Medium", "Sable", False, True, False, 11),
        ("Koda Shiba Inu", "Dog", "Shiba Inu", "Young", "Medium", "Male", "Seattle, WA", "Seattle Humane", 10, 325, "Short", "Red / Cream", False, True, True, 3),
        ("Freya Golden Retriever", "Dog", "Golden Retriever", "Adult", "Large", "Female", "Seattle, WA", "Homeward Pet Adoption Center", 14, 375, "Long", "Golden", True, True, True, 4),
        ("Ziggy Cattle Dog", "Dog", "Australian Cattle Dog", "Adult", "Medium", "Male", "Seattle, WA", "Seattle Animal Shelter", 27, 280, "Short", "Blue Merle", False, True, False, 5),
        ("Pearl Great Pyrenees", "Dog", "Great Pyrenees", "Senior", "Large", "Female", "Seattle, WA", "Pasado's Safe Haven", 19, 240, "Long", "White", True, True, True, 6),
        ("Benny Boston Terrier", "Dog", "Boston Terrier", "Baby", "Small", "Male", "Seattle, WA", "Emerald City Pet Rescue", 3, 390, "Short", "Black / White", True, True, True, 7),
        ("Rudy Pit Bull Mix", "Dog", "Pit Bull Terrier Mix", "Adult", "Large", "Male", "Austin, TX", "Austin Pets Alive!", 12, 225, "Short", "Blue / White", True, True, False, 8),
        ("Maisie Corgi Mix", "Dog", "Pembroke Welsh Corgi Mix", "Young", "Medium", "Female", "Austin, TX", "Austin Humane Society", 6, 310, "Medium", "Tan / White", True, True, True, 9),
        ("Hank Hound Mix", "Dog", "Hound Mix", "Senior", "Large", "Male", "Austin, TX", "Texas Humane Heroes", 31, 190, "Short", "Tricolor", True, True, True, 10),
        ("Tilly Papillon", "Dog", "Papillon", "Adult", "Small", "Female", "Austin, TX", "Central Texas SPCA", 17, 260, "Long", "White / Brown", False, False, True, 11),
        ("Leo Vizsla Mix", "Dog", "Vizsla Mix", "Baby", "Medium", "Male", "Austin, TX", "Love-A-Bull", 2, 360, "Short", "Rust", True, True, False, 0),
        ("Gus English Bulldog", "Dog", "English Bulldog", "Adult", "Medium", "Male", "Boston, MA", "Animal Rescue League of Boston", 20, 350, "Short", "White / Fawn", True, False, True, 1),
        ("Phoebe Samoyed", "Dog", "Samoyed", "Young", "Large", "Female", "Boston, MA", "MSPCA-Angell", 7, 410, "Long", "White", True, True, True, 2),
        ("Finn Schnauzer", "Dog", "Miniature Schnauzer", "Senior", "Small", "Male", "Boston, MA", "Last Hope K9 Rescue", 25, 230, "Wire", "Salt / Pepper", False, True, True, 3),
        ("Rosie English Setter", "Dog", "English Setter", "Adult", "Large", "Female", "Boston, MA", "Great Dog Rescue New England", 15, 320, "Long", "White / Orange", True, True, False, 4),
        ("Ace Whippet", "Dog", "Whippet", "Young", "Medium", "Male", "Boston, MA", "Northeast Animal Shelter", 4, 335, "Short", "Brindle / White", True, True, True, 5),
        ("Mabel Persian", "Cat", "Persian", "Adult", "Small", "Female", "Chicago, IL", "Tree House Humane Society", 8, 175, "Long", "Cream", True, False, True, 6),
        ("Theo Siamese", "Cat", "Siamese", "Young", "Medium", "Male", "Chicago, IL", "Felines & Canines", 12, 160, "Short", "Seal Point", False, False, True, 7),
        ("Saffron Abyssinian", "Cat", "Abyssinian", "Young", "Small", "Female", "Chicago, IL", "Harmony House for Cats", 5, 170, "Short", "Ruddy", True, False, False, 8),
        ("Jasper Russian Blue", "Cat", "Russian Blue", "Young", "Medium", "Male", "New York, NY", "ASPCA Adoption Center", 7, 155, "Short", "Gray", True, False, True, 9),
        ("Olive Ragdoll Mix", "Cat", "Ragdoll Mix", "Adult", "Large", "Female", "New York, NY", "Animal Haven", 18, 145, "Long", "Cream / Brown", True, True, True, 10),
        ("Wren Bombay", "Cat", "Bombay", "Senior", "Small", "Female", "New York, NY", "Bideawee", 28, 95, "Short", "Black", False, False, True, 11),
        ("Mochi Siamese Mix", "Cat", "Siamese Mix", "Baby", "Small", "Female", "Seattle, WA", "Seattle Humane", 3, 185, "Short", "Lynx Point", True, True, True, 0),
        ("Felix American Shorthair", "Cat", "American Shorthair", "Senior", "Medium", "Male", "Seattle, WA", "Seattle Animal Shelter", 24, 90, "Short", "Silver Tabby", True, False, True, 1),
        ("Zola Bengal Mix", "Cat", "Bengal Mix", "Young", "Medium", "Female", "Austin, TX", "Austin Pets Alive!", 6, 180, "Short", "Brown Spotted", False, True, False, 2),
        ("Otis American Shorthair", "Cat", "American Shorthair", "Senior", "Medium", "Male", "Austin, TX", "Austin Humane Society", 22, 100, "Short", "Orange Tabby", True, False, True, 3),
        ("Pearl Snowshoe", "Cat", "Snowshoe", "Adult", "Small", "Female", "Austin, TX", "Texas Humane Heroes", 10, 135, "Short", "Seal Point / White", True, True, True, 4),
        ("Beans Norwegian Forest Cat", "Cat", "Norwegian Forest Cat", "Young", "Large", "Male", "Boston, MA", "Animal Rescue League of Boston", 9, 165, "Long", "Brown Tabby / White", True, False, True, 5),
        ("Nora Turkish Angora", "Cat", "Turkish Angora", "Adult", "Medium", "Female", "Boston, MA", "Northeast Animal Shelter", 14, 150, "Long", "White", False, False, True, 6),
        ("Fern Mini Rex", "Rabbit", "Mini Rex", "Young", "Small", "Female", "Seattle, WA", "Seattle Animal Shelter", 4, 70, "Short", "Chocolate", True, False, False, 7),
        ("Juniper Flemish Giant", "Rabbit", "Flemish Giant", "Adult", "Medium", "Female", "Seattle, WA", "Seattle Humane", 15, 85, "Short", "Sandy", True, False, False, 8),
        ("Pepper Lionhead", "Rabbit", "Lionhead", "Adult", "Small", "Male", "Seattle, WA", "Emerald City Pet Rescue", 20, 65, "Long", "Black", False, False, False, 9),
        ("Clover Dutch Rabbit", "Rabbit", "Dutch", "Young", "Small", "Female", "New York, NY", "Animal Care Centers of NYC", 8, 80, "Short", "Black / White", True, False, False, 10),
        ("Biscuit English Spot", "Rabbit", "English Spot", "Adult", "Medium", "Male", "Chicago, IL", "Red Door Animal Shelter", 17, 75, "Short", "White / Brown", True, False, False, 11),
        ("Thumper Rex Rabbit", "Rabbit", "Rex", "Senior", "Medium", "Male", "Austin, TX", "House Rabbit Resource Network", 26, 60, "Short", "Castor", False, False, False, 0),
        ("Pippa Angora Rabbit", "Rabbit", "English Angora", "Baby", "Small", "Female", "Boston, MA", "House Rabbit Network", 5, 90, "Long", "White", True, False, False, 1),
        ("Pecan Abyssinian Guinea Pig", "Guinea Pig", "Abyssinian", "Adult", "Small", "Female", "Chicago, IL", "Red Door Animal Shelter", 13, 45, "Rough", "Brown / White", True, False, False, 2),
        ("Marbles Teddy Guinea Pig", "Guinea Pig", "Teddy", "Young", "Small", "Male", "Seattle, WA", "Seattle Animal Shelter", 7, 50, "Plush", "Tricolor", True, False, False, 3),
        ("Tofu Peruvian Guinea Pig", "Guinea Pig", "Peruvian", "Adult", "Small", "Male", "Boston, MA", "MSPCA-Angell", 16, 55, "Long", "White / Tan", False, False, False, 4),
    ]
    species_image_indices = {
        "Dog": (0, 4, 5, 6, 7),
        "Cat": (1, 8, 9, 10, 11),
        "Rabbit": (2,),
        "Guinea Pig": (3,),
    }
    image_index_overrides = {
        "Pepper Great Dane": 0, "Leo Vizsla Mix": 6, "Benny Boston Terrier": 7,
        "Ace Whippet": 0, "Maisie Corgi Mix": 6, "Phoebe Samoyed": 0,
        "Nova Siberian Husky": 5, "Winnie Greyhound": 0, "Koda Shiba Inu": 7,
        "Theo Boxer Mix": 4, "Rudy Pit Bull Mix": 0, "Bruno Mastiff Mix": 5,
        "Freya Golden Retriever": 0, "Rosie English Setter": 6, "Daisy Cocker Spaniel": 4,
        "Tilly Papillon": 7, "Pearl Great Pyrenees": 5, "Gus English Bulldog": 4,
        "Remy Terrier Mix": 7, "Archie Dachshund": 4, "Finn Schnauzer": 7,
        "Ziggy Cattle Dog": 6, "Hank Hound Mix": 4, "Sage Shepherd Mix": 5,
        "Mochi Siamese Mix": 8, "Saffron Abyssinian": 1, "Zola Bengal Mix": 10,
        "Jasper Russian Blue": 9, "Mabel Persian": 11, "Beans Norwegian Forest Cat": 11,
        "Pearl Snowshoe": 9, "Theo Siamese": 9, "Nora Turkish Angora": 11,
        "Olive Ragdoll Mix": 8, "Otis American Shorthair": 10,
        "Felix American Shorthair": 9, "Wren Bombay": 10,
    }
    for values in additional_listings:
        name, species, breed, age, size, gender, location, shelter = values[:8]
        first_name = name.split()[0]
        summary = f"{first_name} is a {age.lower()} {breed.lower()} ready for a patient, caring home."
        story = (
            f"The team at {shelter} describes {first_name} as an engaging companion. "
            f"Ask the adoption team about routines, introductions, and the best fit for this {size.lower()} {species.lower()}."
        )
        image_choices = species_image_indices[species]
        image_index = image_index_overrides.get(
            name,
            image_choices[sum(ord(character) for character in name) % len(image_choices)],
        )
        listings.append(values[:-1] + (summary, story, image_index))
    columns = (
        "name", "species", "breed", "age", "size", "gender", "location", "shelter",
        "days_on_petfinder", "adoption_fee", "coat", "color", "good_with_children",
        "good_with_dogs", "good_with_cats", "summary", "story", "image_index",
    )
    for values in listings:
        data = dict(zip(columns, values))
        data["slug"] = slugify(data["name"])
        db.session.add(Listing(**data))

    guides = [
        ("Pet adoption checklist", "Adopting pets", 7, "A practical checklist for preparing your family, home, and schedule for a new pet.", "Adoption day is exciting, but a little planning makes the transition easier for everyone. Talk with the shelter about routines, medical history, and the first few quiet days at home.\n\nGive your new pet time to decompress. Keep introductions calm and let trust build at the pet's pace.", "Before you bring your pet home", "Choose a veterinarian and save the clinic number|Set up a quiet room with food, water, and a comfortable bed|Check fences, windows, plants, and household hazards"),
        ("Preparing your home for adoption", "Adopting pets", 6, "Create a calm, pet-safe space before your new companion arrives.", "Decide where your pet will sleep, eat, and take breaks. Put supplies in place before adoption day so the first evening can stay quiet.\n\nPlan gradual introductions to children and resident pets, and keep the new pet's world small at first.", "A comfortable first week", "Keep meals and walks on a predictable schedule|Offer a private retreat that visitors leave undisturbed|Use gates or closed doors for slow pet introductions"),
        ("Questions to ask an animal shelter", "Finding a pet", 5, "Learn about a pet's routine, health, and behavior before making a match.", "Shelter staff and foster families can share details that are not obvious from a profile. Ask how the pet behaves at home, around visitors, and during handling.\n\nConfirm which medical records, supplies, and follow-up support come with the adoption.", "Questions worth bringing", "What does a typical day look like for this pet?|Has the pet lived with children, dogs, or cats?|What medical care or training should continue after adoption?"),
        ("Introducing a rescue pet", "Pet care", 6, "Help a new pet meet people and resident animals at a comfortable pace.", "Start with scent and distance rather than face-to-face contact. Short, successful sessions are better than a long introduction.\n\nWatch body language and separate the animals before either becomes overwhelmed.", "Keep introductions low pressure", "Exchange bedding before the first meeting|Reward calm behavior on both sides of a gate|Give every pet separate food, water, and resting areas"),
        ("Understanding adoption fees", "Adopting pets", 4, "See what an adoption fee may cover and what to budget for after adoption.", "Adoption fees often help shelters provide vaccinations, microchips, spay or neuter surgery, and daily care. Included services vary by organization.\n\nAsk for an itemized explanation and plan separately for food, licensing, grooming, and future veterinary care.", "Budget beyond adoption day", "Confirm which vaccinations are current|Ask whether a microchip transfer is included|Plan an emergency veterinary fund"),
        ("Choosing the right dog for your routine", "Finding a pet", 7, "Match a dog's energy, size, and support needs to everyday life.", "Think about your weekday schedule, activity level, visitors, and the space available at home. Breed labels are only one clue; ask about the individual dog's behavior and recovery needs.\n\nA realistic match gives both adopter and dog room to settle in successfully.", "Look beyond first impressions", "Ask about daily exercise needs|Discuss behavior in a foster home|Plan care for workdays and travel"),
        ("Helping a shy cat feel safe", "Pet care", 6, "Use choice, routine, and quiet spaces to help a reserved cat decompress.", "Start with one calm room and let the cat decide when to approach. Predictable meals and gentle play can make a new environment feel safer.\n\nAvoid pulling a hiding cat into the open; small signs of curiosity are meaningful progress.", "Build trust at the cat's pace", "Provide covered hiding places|Sit nearby without reaching|Reward voluntary approaches"),
        ("Rabbit housing essentials", "Pet care", 5, "Create an indoor rabbit space with room to move, hide, and forage.", "Rabbits need more than a small cage. Use an exercise pen or rabbit-proofed room with traction, litter, hay, water, and safe chew materials.\n\nDaily movement and social time support physical and emotional health.", "Set up a rabbit-friendly space", "Offer unlimited grass hay|Cover cords and unsafe baseboards|Include a hide box and non-slip flooring"),
        ("Meeting a pet in foster care", "Finding a pet", 4, "Prepare useful questions before meeting a foster-based pet.", "Foster caregivers can often describe how a pet behaves during ordinary household routines. Share an honest picture of your home so the rescue can help assess fit.\n\nPay attention to recovery after excitement as well as the initial greeting.", "Make the meeting informative", "Describe your household schedule|Ask about triggers and comforts|Discuss a gradual transition plan"),
        ("Your new pet's first veterinary visit", "Pet health", 6, "Organize records and questions for an early wellness appointment.", "Bring the shelter's medical paperwork, current medications, and feeding details. Your veterinarian can review preventive care and help set priorities for the first months.\n\nCall ahead if your pet is fearful or needs a quieter arrival plan.", "Prepare for the appointment", "Bring adoption medical records|List food and medications|Write down behavior or health questions"),
        ("Safe travel home after adoption", "Adopting pets", 4, "Plan a secure, low-stress trip from the shelter to your home.", "Use an appropriate carrier or vehicle restraint before leaving the adoption center. Keep the trip direct and calm, with doors and windows secured.\n\nHave the pet's quiet settling area ready before arrival.", "Before leaving the shelter", "Fit a secure collar or carrier|Confirm your direct route home|Keep a towel and cleanup supplies nearby"),
        ("Building a predictable feeding routine", "Pet care", 5, "Use consistent meals and measured portions while your pet settles in.", "Ask what and when the pet has been eating, then make dietary changes gradually. Regular meal times also help with training and observation.\n\nContact a veterinarian if appetite changes suddenly or digestive signs persist.", "Support healthy eating habits", "Measure each meal|Change foods gradually|Track appetite during the first week"),
    ]
    for title, category, read_minutes, summary, body, section_heading, checklist in guides:
        db.session.add(Guide(slug=slugify(title), title=title, category=category, read_minutes=read_minutes, summary=summary, body=body, section_heading=section_heading, checklist=checklist))
    db.session.commit()


def seed_users():
    if User.query.count() > 0:
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "New York, NY", "Nearest first"),
        ("bob_c", "bob.c@test.com", "Bob Chen", "Chicago, IL", "Newest pets first"),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Seattle, WA", "Recently updated"),
        ("david_k", "david.k@test.com", "David Kim", "Austin, TX", "Nearest first"),
    ]
    for username, email, display_name, home_location, sort_preference in users:
        db.session.add(User(username=username, email=email, display_name=display_name, home_location=home_location, sort_preference=sort_preference, password_hash=generate_password_hash("TestPass123!")))
    db.session.commit()


def seed_saved_items():
    if SavedItem.query.count() > 0:
        return
    alice = User.query.filter_by(email="alice.j@test.com").one()
    for slug in ("milo-labrador-mix", "nori-rabbit"):
        listing = Listing.query.filter_by(slug=slug).one()
        db.session.add(SavedItem(user_id=alice.id, listing_id=listing.id))
    db.session.commit()


with app.app_context():
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()
    seed_database()
    seed_users()
    seed_saved_items()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
