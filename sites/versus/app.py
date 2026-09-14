"""Versus mirror — product comparison and ranking workflows."""
from __future__ import annotations

import json
import mimetypes
import os
import re
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
mimetypes.add_type("image/webp", ".webp")

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-versus-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'versus.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "vs", "versus"}

# Benchmark accounts all share the password "TestPass123!". The hash is frozen
# rather than recomputed at seed time because werkzeug draws a fresh scrypt salt
# on every call, which made instance_seed/versus.db differ byte-for-byte between
# two builds of the same commit and left its hash unpinnable.
BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_PASSWORD_HASH = (
    "scrypt:32768:8:1$L0zp47QSxuocH7od$a67d3cb38348337beea69448cc092b28dde062db907e"
    "f1b48ca024c4b3de11f31ae5ef044671d7d20de786d5be7ce8609b0481642c35d87fb696d6be9a2956dc"
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    tagline = db.Column(db.String(180), nullable=False)
    # What the brand/maker column means here. A sourced city or university is
    # identified by country, not by a manufacturer.
    brand_label = db.Column(db.String(30), nullable=False, default="Brand")
    spec_1 = db.Column(db.String(80), nullable=False)
    spec_2 = db.Column(db.String(80), nullable=False)
    spec_3 = db.Column(db.String(80), nullable=True)
    unit_1 = db.Column(db.String(24), default="")
    unit_2 = db.Column(db.String(24), default="")
    unit_3 = db.Column(db.String(24), default="")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    brand = db.Column(db.String(80), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=True)
    release_year = db.Column(db.Integer, nullable=True)
    spec_1_value = db.Column(db.Float, nullable=False)
    spec_2_value = db.Column(db.Float, nullable=False)
    spec_3_value = db.Column(db.Float, nullable=True)
    battery_hours = db.Column(db.Float, default=0)
    weight_grams = db.Column(db.Float, default=0)
    pros = db.Column(db.Text, nullable=False)
    cons = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    category = db.relationship("Category")

    @property
    def search_blob(self) -> str:
        return (
            f"{self.name} {self.brand} {self.category.name} {self.summary} "
            f"{self.pros} {self.cons} {self.category.spec_1} {self.spec_1_value} "
            f"{self.category.spec_2} {self.spec_2_value} {self.category.spec_3} {self.spec_3_value} "
            f"battery {self.battery_hours} hours weight {self.weight_grams} grams "
            f"price {self.price} score {self.score}"
        )


class SavedComparison(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    left_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    right_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    note = db.Column(db.String(240), default="")
    left = db.relationship("Product", foreign_keys=[left_id])
    right = db.relationship("Product", foreign_keys=[right_id])


def current_user() -> User | None:
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_common():
    return {"current_user": current_user(), "categories": Category.query.order_by(Category.name).all()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Sign in to save comparisons.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def tokenize(query: str) -> list[str]:
    return [
        token
        for token in re.split(r"\W+", query.lower())
        if len(token) > 1 and token not in STOP_WORDS
    ]


def scored_search(query: str, rows, fields: list[str]):
    parts = tokenize(query)
    if not parts:
        return list(rows)
    scored = []
    for row in rows:
        text = " ".join(str(getattr(row, field, "") or "") for field in fields).lower()
        score = sum(1 for part in parts if part in text)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], getattr(item[1], "score", 0) * -1, getattr(item[1], "name", "")))
    return [row for _, row in scored]


def product_by_slug(slug: str) -> Product:
    return Product.query.filter_by(slug=slug).first_or_404()


def winner(left: Product, right: Product) -> Product:
    return left if left.score >= right.score else right


# Signals where a smaller number is the better result.
LOWER_IS_BETTER = {"Price", "Weight", "Power"}


def compare_rows(left: Product, right: Product) -> list[dict]:
    """Signal-by-signal comparison with a leader and a margin per row.

    The source site presents a comparison as a set of areas with a winner and a
    margin each, rather than a single overall number, so the table carries that
    shape. The product the site *declares* the winner is still the higher Versus
    Score (see winner()); the area counts are additional information.
    """
    category = left.category
    specs = [
        (category.spec_1, left.spec_1_value, right.spec_1_value, category.unit_1),
        (category.spec_2, left.spec_2_value, right.spec_2_value, category.unit_2),
        (category.spec_3, left.spec_3_value, right.spec_3_value, category.unit_3),
    ]
    rows = [{"label": "Score", "left": left.score, "right": right.score, "unit": ""}]
    rows += [{"label": label, "left": lv, "right": rv, "unit": unit}
             for label, lv, rv, unit in specs
             if label and lv is not None and rv is not None]
    if left.price is not None and right.price is not None:
        rows.append({"label": "Price", "left": left.price, "right": right.price, "unit": ""})

    for row in rows:
        lv, rv = row["left"], row["right"]
        if lv is None or rv is None or lv == rv:
            row["leader"] = None
            row["margin"] = None
            continue
        lower_better = row["label"] in LOWER_IS_BETTER
        row["leader"] = "left" if ((lv < rv) if lower_better else (lv > rv)) else "right"
        row["margin"] = round(abs(lv - rv), 1)
    return rows


def lead_summary(rows: list[dict], side: str) -> tuple[int, int]:
    """(areas led by `side`, areas that have a leader at all)."""
    decided = [r for r in rows if r["leader"]]
    return sum(1 for r in decided if r["leader"] == side), len(decided)


@app.route("/")
def index():
    top = Product.query.order_by(Product.score.desc()).limit(8).all()
    popular_pairs = [
        ("iphone-15-pro", "samsung-galaxy-s24-ultra"),
        ("sony-wh-1000xm5", "bose-quietcomfort-ultra"),
        ("canon-eos-r6-mark-ii", "sony-a7-iv"),
        ("rtx-4080-super", "radeon-rx-7900-xtx"),
    ]
    pairs = [(product_by_slug(a), product_by_slug(b)) for a, b in popular_pairs]
    return render_template("index.html", top=top, pairs=pairs)


@app.route("/categories")
def category_index():
    counts = {
        cat.id: Product.query.filter_by(category_id=cat.id).count()
        for cat in Category.query.all()
    }
    return render_template("categories.html", counts=counts)


PAGE_SIZE = 8


def paginate(rows, page):
    """Slice a result set and describe the paging, the way a catalogue site does."""
    total = len(rows)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page or 1, 1), pages)
    start = (page - 1) * PAGE_SIZE
    return rows[start:start + PAGE_SIZE], {
        "page": page, "pages": pages, "total": total,
        "start": start + 1 if total else 0,
        "end": min(start + PAGE_SIZE, total),
        "has_prev": page > 1, "has_next": page < pages,
    }


@app.route("/category/<slug>")
def category_detail(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()
    brand = request.args.get("brand", "")
    max_price = request.args.get("max_price", type=int)
    min_score = request.args.get("min_score", type=int)
    rows = Product.query.filter_by(category_id=category.id).order_by(Product.score.desc()).all()
    if brand:
        rows = [item for item in rows if item.brand == brand]
    if max_price:
        rows = [item for item in rows if item.price <= max_price]
    if min_score:
        rows = [item for item in rows if item.score >= min_score]
    brands = [row[0] for row in db.session.query(Product.brand).filter_by(category_id=category.id).distinct().order_by(Product.brand)]
    has_prices = db.session.query(Product.price).filter(
        Product.category_id == category.id, Product.price.isnot(None)).first() is not None
    rows, paging = paginate(rows, request.args.get("page", type=int))
    return render_template("category.html", category=category, products=rows, brands=brands,
                           brand=brand, max_price=max_price, min_score=min_score,
                           paging=paging, has_prices=has_prices)


@app.route("/item/<slug>")
def product_detail(slug):
    product = product_by_slug(slug)
    related = (
        Product.query.filter(Product.category_id == product.category_id, Product.slug != product.slug)
        .order_by(Product.score.desc())
        .limit(5)
        .all()
    )
    return render_template("product.html", product=product, related=related)


@app.route("/compare")
def compare_picker():
    left_slug = request.args.get("left", "")
    right_slug = request.args.get("right", "")
    if left_slug and right_slug:
        return redirect(url_for("compare_detail", left=left_slug, right=right_slug))
    products = Product.query.order_by(Product.category_id, Product.score.desc()).all()
    return render_template("compare_picker.html", products=products, left_slug=left_slug, right_slug=right_slug)


@app.route("/compare/<left>-vs-<right>")
def compare_detail(left, right):
    left_product = product_by_slug(left)
    right_product = product_by_slug(right)
    if left_product.category_id != right_product.category_id:
        flash("Those products are in different categories; compare signals are still shown side by side.", "info")
    rows = compare_rows(left_product, right_product)
    champion = winner(left_product, right_product)
    side = "left" if champion is left_product else "right"
    led, decided = lead_summary(rows, side)
    return render_template("compare.html", left=left_product, right=right_product,
                           winner=champion, rows=rows, areas_led=led,
                           areas_total=decided)


@app.route("/compare/<left>-vs-<right>/save", methods=["POST"])
@login_required
def save_comparison(left, right):
    left_product = product_by_slug(left)
    right_product = product_by_slug(right)
    user = current_user()
    existing = SavedComparison.query.filter_by(user_id=user.id, left_id=left_product.id, right_id=right_product.id).first()
    if not existing:
        db.session.add(SavedComparison(user_id=user.id, left_id=left_product.id, right_id=right_product.id, note=request.form.get("note", "")))
        db.session.commit()
        flash("Comparison saved.", "success")
    return redirect(url_for("account"))


@app.route("/rankings")
def rankings():
    category_slug = request.args.get("category", "")
    rows = Product.query.order_by(Product.score.desc()).all()
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        rows = [row for row in rows if row.category_id == category.id]
    ranked = list(enumerate(rows, start=1))
    ranked, paging = paginate(ranked, request.args.get("page", type=int))
    return render_template("rankings.html", ranked=ranked, category_slug=category_slug,
                           paging=paging)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    products = scored_search(query, Product.query.all(), ["search_blob"])[:12] if query else []
    cats = scored_search(query, Category.query.all(), ["name", "tagline"]) if query else []
    return render_template("search.html", query=query, products=products, cats=cats)


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


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved = SavedComparison.query.filter_by(user_id=current_user().id).all()
    return render_template("account.html", saved=saved)


@app.route("/about")
def about():
    """What this mirror is, and which parts of it are synthetic.

    The source site is mirrored for an offline agent benchmark, so the page
    states plainly which values are sourced and which are generated rather than
    leaving a visitor to assume everything is real.
    """
    return render_template("about.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "versus"}


SOURCED = os.path.join(BASE_DIR, "data", "catalogue_wikidata.json")

# Wikidata is user-edited, and some rows pair claims that do not belong
# together -- a state's population against a city's area, for instance. Rather
# than maintain a hand-written list of bad ids (the first attempt named an id
# that was not the offending item's, so the bad row shipped anyway), the claims
# are cross-checked against each other and anything implausible is dropped.
# Known limitation, not a solved problem: population and area are independent
# claims and are not guaranteed to describe the same administrative boundary. A
# metro-area population paired with a city-proper area inflates the derived
# density. The bound below removes the gross cases (one row paired a state
# population with a city area, giving 102,298 people per km2) but cannot
# separate, say, an inflated Kuala Lumpur from a genuinely dense Mumbai. No task
# is written against the density figure for that reason, and data/README.md
# records the caveat.
MAX_PLAUSIBLE_DENSITY = 40000      # people per km2; the densest real cities sit near 46k
MIN_PLAUSIBLE_DENSITY = 50


def _sourced_rows():
    """Cities and universities, as fetched from Wikidata with provenance.

    Consumer-electronics categories are not sourced this way: no free citable
    source carries their specs at scale (a SPARQL count of digital cameras
    holding both mass and release date returns zero). See data/README.md.
    """
    if not os.path.exists(SOURCED):
        return {"cities": [], "universities": []}
    with open(SOURCED, encoding="utf-8") as fh:
        data = json.load(fh)
    out, seen = {}, {}
    for key in ("cities", "universities"):
        rows = [r for r in data.get(key, []) if _claims_are_consistent(key, r)]
        rows = sorted(rows, key=lambda r: r["qid"])   # deterministic order
        for r in rows:
            seen.setdefault(_slugify(r["name"]), []).append(r["qid"])
        out[key] = rows
    # Two entities sharing an English label are indistinguishable on the page, so
    # a task naming one would be ambiguous. Drop every side of the collision
    # rather than silently keeping whichever sorted first. Wikidata has two
    # items labelled "University of Lille": the merged 2018 institution and the
    # historic one.
    ambiguous = {q for qids in seen.values() if len(qids) > 1 for q in qids}
    if ambiguous:
        for key in out:
            out[key] = [r for r in out[key] if r["qid"] not in ambiguous]
    return out


def _claims_are_consistent(kind, rec):
    """Cross-check a row's own claims; drop it when they contradict each other."""
    f = rec["fields"]
    try:
        if kind == "cities":
            density = float(f["pop"]["value"]) / float(f["area"]["value"])
            return MIN_PLAUSIBLE_DENSITY < density < MAX_PLAUSIBLE_DENSITY
        if kind == "universities":
            founded = int(f["inception"]["value"][:4])
            return 1000 < founded <= 2026 and float(f["students"]["value"]) > 0
    except (KeyError, ValueError, ZeroDivisionError):
        return False
    return True


def seed_database():
    if Category.query.count() > 0:
        return
    categories = [
        ("smartphones", "Smartphones", "Compare cameras, screens, battery life, and performance.", "Camera score", "Battery", "Display", "pt", "h", "in", "Brand"),
        ("headphones", "Headphones", "Compare noise cancelling, battery, weight, and travel features.", "ANC score", "Battery", "Weight", "pt", "h", "g", "Brand"),
        ("cameras", "Cameras", "Compare sensor resolution, stabilization, burst speed, and video features.", "Megapixels", "Burst", "Weight", "MP", "fps", "g", "Brand"),
        ("graphics-cards", "Graphics Cards", "Compare gaming performance, VRAM, power draw, and value.", "VRAM", "Power", "Benchmark", "GB", "W", "pt", "Brand"),
        ("smartwatches", "Smartwatches", "Compare fitness sensors, battery, display, and ecosystem support.", "Fitness score", "Battery", "Weight", "pt", "h", "g", "Brand"),
        ("cities", "Cities", "Compare population, footprint, and how densely people live.", "Population", "Area", "Density", "", "km2", "/km2", "Country"),
        ("universities", "Universities", "Compare enrolment and how long the institution has been teaching.", "Students", "Founded", None, "", "", None, "Country"),
    ]

    category_map = {}
    for slug, name, tagline, spec_1, spec_2, spec_3, unit_1, unit_2, unit_3, brand_label in categories:
        cat = Category(slug=slug, name=name, tagline=tagline, brand_label=brand_label,
                       spec_1=spec_1, spec_2=spec_2, spec_3=spec_3,
                       unit_1=unit_1, unit_2=unit_2, unit_3=unit_3)
        db.session.add(cat)
        db.session.flush()
        category_map[slug] = cat

    products = [
        ("iphone-15-pro", "iPhone 15 Pro", "Apple", "smartphones", 93, 999, 2023, 92, 23, 6.1, 23, 187, "Excellent video, fast chip, titanium frame", "Expensive, slower wired charging"),
        ("samsung-galaxy-s24-ultra", "Samsung Galaxy S24 Ultra", "Samsung", "smartphones", 95, 1299, 2024, 96, 28, 6.8, 28, 232, "Long zoom, bright display, S Pen", "Large and heavy"),
        ("google-pixel-8-pro", "Google Pixel 8 Pro", "Google", "smartphones", 91, 999, 2023, 94, 26, 6.7, 26, 213, "Computational camera, clean Android", "Charging speed trails rivals"),
        ("oneplus-12", "OnePlus 12", "OnePlus", "smartphones", 89, 799, 2024, 88, 31, 6.8, 31, 220, "Fast charging, strong value", "Camera tuning less consistent"),
        ("sony-wh-1000xm5", "Sony WH-1000XM5", "Sony", "headphones", 94, 399, 2022, 96, 30, 250, 30, 250, "Top-tier ANC, light design, app EQ", "Does not fold compactly"),
        ("bose-quietcomfort-ultra", "Bose QuietComfort Ultra", "Bose", "headphones", 93, 429, 2023, 95, 24, 253, 24, 253, "Excellent comfort, immersive audio", "Premium price"),
        ("apple-airpods-max", "AirPods Max", "Apple", "headphones", 88, 549, 2020, 90, 20, 385, 20, 385, "Spatial audio, premium build", "Heavy, case is awkward"),
        ("sennheiser-momentum-4", "Sennheiser Momentum 4", "Sennheiser", "headphones", 90, 349, 2022, 86, 60, 293, 60, 293, "Huge battery life, balanced sound", "ANC trails Sony and Bose"),
        ("canon-eos-r6-mark-ii", "Canon EOS R6 Mark II", "Canon", "cameras", 92, 2499, 2022, 24, 40, 670, 0, 670, "Fast autofocus, strong video tools", "Resolution lower than rivals"),
        ("sony-a7-iv", "Sony A7 IV", "Sony", "cameras", 91, 2498, 2021, 33, 10, 658, 0, 658, "Great hybrid camera, lens ecosystem", "Rolling shutter in some modes"),
        ("nikon-z8", "Nikon Z8", "Nikon", "cameras", 96, 3999, 2023, 45.7, 20, 910, 0, 910, "Pro body performance, excellent stills", "Large and expensive"),
        ("fujifilm-x-t5", "Fujifilm X-T5", "Fujifilm", "cameras", 88, 1699, 2022, 40, 15, 557, 0, 557, "Compact body, high resolution APS-C", "Video AF behind full-frame leaders"),
        ("rtx-4080-super", "GeForce RTX 4080 Super", "NVIDIA", "graphics-cards", 94, 999, 2024, 16, 320, 18400, 0, 0, "Excellent 4K ray tracing, DLSS 3", "Still expensive"),
        ("radeon-rx-7900-xtx", "Radeon RX 7900 XTX", "AMD", "graphics-cards", 91, 949, 2022, 24, 355, 16800, 0, 0, "Large VRAM, strong raster performance", "Ray tracing behind NVIDIA"),
        ("rtx-4070-super", "GeForce RTX 4070 Super", "NVIDIA", "graphics-cards", 88, 599, 2024, 12, 220, 12300, 0, 0, "Efficient, strong 1440p card", "12GB VRAM limit for some workloads"),
        ("radeon-rx-7800-xt", "Radeon RX 7800 XT", "AMD", "graphics-cards", 86, 499, 2023, 16, 263, 10800, 0, 0, "Good value and VRAM", "Upscaling ecosystem weaker"),
        ("apple-watch-series-9", "Apple Watch Series 9", "Apple", "smartwatches", 92, 399, 2023, 94, 18, 42, 18, 42, "Best iPhone integration, bright display", "Battery lasts about a day"),
        ("garmin-venu-3", "Garmin Venu 3", "Garmin", "smartwatches", 90, 449, 2023, 92, 336, 47, 336, 47, "Long battery, health metrics", "Smaller app ecosystem"),
        ("samsung-galaxy-watch-6", "Samsung Galaxy Watch 6", "Samsung", "smartwatches", 87, 299, 2023, 88, 40, 33, 40, 33, "Good Android integration, slim design", "Battery is moderate"),
        ("fitbit-sense-2", "Fitbit Sense 2", "Fitbit", "smartwatches", 82, 249, 2022, 84, 144, 37, 144, 37, "Simple health tracking, light body", "Limited third-party apps"),
    ]
    for slug, name, brand, category_slug, score, price, year, spec1, spec2, spec3, battery, weight, pros, cons in products:
        db.session.add(Product(
            slug=slug,
            name=name,
            brand=brand,
            category_id=category_map[category_slug].id,
            score=score,
            price=price,
            release_year=year,
            spec_1_value=spec1,
            spec_2_value=spec2,
            spec_3_value=spec3,
            battery_hours=battery,
            weight_grams=weight,
            pros=pros,
            cons=cons,
            summary=f"{name} is a {category_map[category_slug].name.lower()} contender with a Versus score of {score}, released in {year}, and priced around ${price}.",
        ))
    seed_sourced_entries(category_map)
    db.session.commit()


def _slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seed_sourced_entries(category_map):
    """Add the Wikidata-sourced Cities and Universities entries.

    Every figure here is a Wikidata claim recorded in data/catalogue_wikidata.json
    with its Q-id, property id and unit. The Versus Score is synthetic, as it is
    for every other category, and is derived deterministically from the sourced
    figures so it stays stable across builds rather than being hand-assigned.
    """
    rows = _sourced_rows()

    for rec in rows["cities"]:
        pop = float(rec["fields"]["pop"]["value"])
        area = float(rec["fields"]["area"]["value"])
        density = round(pop / area, 1)
        db.session.add(Product(
            slug=_slugify(rec["name"]), name=rec["name"], brand=rec.get("country", "—"),
            category_id=category_map["cities"].id,
            score=_synthetic_score(density, 200, 12000),
            price=None, release_year=None,
            spec_1_value=pop, spec_2_value=area, spec_3_value=density,
            battery_hours=0, weight_grams=0,
            pros=f"{pop:,.0f} residents across {area:,.0f} km2",
            cons=f"Density {density:,.0f} people per km2",
            summary=(f"{rec['name']} covers {area:,.0f} km2 and is home to "
                     f"{pop:,.0f} people, a density of {density:,.0f} per km2.")))

    for rec in rows["universities"]:
        students = float(rec["fields"]["students"]["value"])
        founded = int(rec["fields"]["inception"]["value"][:4])
        db.session.add(Product(
            slug=_slugify(rec["name"]), name=rec["name"], brand=rec.get("country", "—"),
            category_id=category_map["universities"].id,
            score=_synthetic_score(students, 70000, 200000),
            price=None, release_year=founded,
            spec_1_value=students, spec_2_value=float(founded), spec_3_value=None,
            battery_hours=0, weight_grams=0,
            pros=f"{students:,.0f} enrolled students",
            cons=f"Teaching since {founded}",
            summary=(f"{rec['name']} has enrolled {students:,.0f} students and has "
                     f"been teaching since {founded}.")))


def _synthetic_score(value, low, high):
    """A benchmark score, not a real-world rating. Deterministic from the input."""
    span = max(high - low, 1)
    return max(60, min(99, round(60 + 39 * (value - low) / span)))


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson"),
        ("bob_c", "bob.c@test.com", "Bob Chen"),
        ("carol_d", "carol.d@test.com", "Carol Davis"),
        ("david_k", "david.k@test.com", "David Kim"),
    ]
    for username, email, display_name in users:
        db.session.add(User(username=username, email=email, display_name=display_name, password_hash=BENCHMARK_PASSWORD_HASH))
    db.session.commit()
    alice = User.query.filter_by(email="alice.j@test.com").first()
    for left_slug, right_slug, note in [
        ("iphone-15-pro", "samsung-galaxy-s24-ultra", "Phone upgrade shortlist"),
        ("sony-wh-1000xm5", "bose-quietcomfort-ultra", "Travel headphones"),
        ("rtx-4080-super", "radeon-rx-7900-xtx", "4K build"),
    ]:
        db.session.add(SavedComparison(user_id=alice.id, left_id=product_by_slug(left_slug).id, right_id=product_by_slug(right_slug).id, note=note))
    db.session.commit()


with app.app_context():
    os.makedirs(app.instance_path, exist_ok=True)
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
