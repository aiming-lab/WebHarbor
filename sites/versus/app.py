"""Versus mirror — product comparison and ranking workflows."""
from __future__ import annotations

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
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-versus-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'versus.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "vs", "versus"}


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
    spec_1 = db.Column(db.String(80), nullable=False)
    spec_2 = db.Column(db.String(80), nullable=False)
    spec_3 = db.Column(db.String(80), nullable=False)
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
    price = db.Column(db.Integer, nullable=False)
    release_year = db.Column(db.Integer, nullable=False)
    spec_1_value = db.Column(db.Float, nullable=False)
    spec_2_value = db.Column(db.Float, nullable=False)
    spec_3_value = db.Column(db.Float, nullable=False)
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
    return render_template("category.html", category=category, products=rows, brands=brands, brand=brand, max_price=max_price, min_score=min_score)


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
    return render_template("compare.html", left=left_product, right=right_product, winner=winner(left_product, right_product))


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
    return render_template("rankings.html", products=rows, category_slug=category_slug)


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


@app.route("/product-art/<slug>.svg")
def product_art(slug):
    product = product_by_slug(slug)
    hue = abs(hash(product.slug)) % 360
    initials = "".join(part[0] for part in product.brand.split()[:2]).upper()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" role="img" aria-label="{product.name}">
<rect width="720" height="480" fill="hsl({hue}, 64%, 94%)"/>
<circle cx="610" cy="100" r="150" fill="hsl({hue}, 70%, 62%)" opacity=".22"/>
<circle cx="120" cy="390" r="190" fill="hsl({(hue + 46) % 360}, 70%, 48%)" opacity=".16"/>
<rect x="190" y="120" width="340" height="230" rx="34" fill="hsl({hue}, 58%, 42%)"/>
<rect x="228" y="154" width="264" height="150" rx="18" fill="white" opacity=".82"/>
<text x="360" y="247" text-anchor="middle" font-family="Arial, sans-serif" font-size="58" font-weight="800" fill="#101828">{initials}</text>
<text x="360" y="396" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#101828">{product.score} Versus Score</text>
</svg>"""
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/_health")
def health():
    return {"ok": True, "site": "versus"}


def seed_database():
    if Category.query.count() > 0:
        return
    categories = [
        ("smartphones", "Smartphones", "Compare cameras, screens, battery life, and performance.", "Camera score", "Battery", "Display", "pt", "h", "in"),
        ("headphones", "Headphones", "Compare noise cancelling, battery, weight, and travel features.", "ANC score", "Battery", "Weight", "pt", "h", "g"),
        ("cameras", "Cameras", "Compare sensor resolution, stabilization, burst speed, and video features.", "Megapixels", "Burst", "Weight", "MP", "fps", "g"),
        ("graphics-cards", "Graphics Cards", "Compare gaming performance, VRAM, power draw, and value.", "VRAM", "Power", "Benchmark", "GB", "W", "pt"),
        ("smartwatches", "Smartwatches", "Compare fitness sensors, battery, display, and ecosystem support.", "Fitness score", "Battery", "Weight", "pt", "h", "g"),
    ]
    category_map = {}
    for slug, name, tagline, spec_1, spec_2, spec_3, unit_1, unit_2, unit_3 in categories:
        cat = Category(slug=slug, name=name, tagline=tagline, spec_1=spec_1, spec_2=spec_2, spec_3=spec_3, unit_1=unit_1, unit_2=unit_2, unit_3=unit_3)
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
    db.session.commit()


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
        db.session.add(User(username=username, email=email, display_name=display_name, password_hash=generate_password_hash("TestPass123!")))
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
