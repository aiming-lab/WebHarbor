"""A deterministic, task-complete local mirror of 9GAG."""

from __future__ import annotations

import os
import re

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config.update(
    SECRET_KEY="webharbor-9gag-deterministic-key",
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(INSTANCE_DIR, '9gag.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(500), default="")
    location = db.Column(db.String(120), default="")
    joined_at = db.Column(db.String(30), default="September 2026")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(20), unique=True, nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255), nullable=False)
    section = db.Column(db.String(80), nullable=False)
    post_type = db.Column(db.String(30), default="Photo")
    tags = db.Column(db.String(400), default="")
    author_name = db.Column(db.String(80), nullable=False)
    up_votes = db.Column(db.Integer, default=0)
    down_votes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    created_rank = db.Column(db.Integer, nullable=False)
    featured = db.Column(db.Boolean, default=False)

    @property
    def tag_list(self):
        return [tag.strip() for tag in self.tags.split("|") if tag.strip()]


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.String(40), nullable=False)
    post = db.relationship("Post", backref="comments")
    user = db.relationship("User")


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_vote_user_post"),)


class SavedPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    post = db.relationship("Post")
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_saved_user_post"),)


class HiddenPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_hidden_user_post"),)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    reason = db.Column(db.String(120), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:160] or "post"


def scored_posts(query, posts):
    stop = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is", "it", "by", "with"}
    tokens = [token for token in re.split(r"\W+", query.lower()) if len(token) > 1 and token not in stop]
    if not tokens:
        return list(posts)
    ranked = []
    for post in posts:
        haystack = f"{post.title} {post.description} {post.section} {post.tags} {post.author_name}".lower()
        score = sum(3 if token in post.title.lower() else 1 for token in tokens if token in haystack)
        if score:
            ranked.append((post, score))
    return [post for post, _ in sorted(ranked, key=lambda item: (-item[1], -item[0].up_votes, item[0].id))]


def visible_posts():
    query = Post.query
    if current_user.is_authenticated:
        hidden_ids = [row.post_id for row in HiddenPost.query.filter_by(user_id=current_user.id)]
        if hidden_ids:
            query = query.filter(~Post.id.in_(hidden_ids))
    return query


def render_feed(title="Hot", posts=None, active="home", query=""):
    posts = posts if posts is not None else visible_posts().order_by(Post.featured.desc(), Post.up_votes.desc()).all()
    page_number = max(request.args.get("page", 1, type=int), 1)
    total = len(posts)
    page_size = 10
    posts = posts[(page_number - 1) * page_size:page_number * page_size]
    saved_ids, votes = set(), {}
    if current_user.is_authenticated:
        saved_ids = {row.post_id for row in SavedPost.query.filter_by(user_id=current_user.id)}
        votes = {row.post_id: row.value for row in Vote.query.filter_by(user_id=current_user.id)}
    return render_template("feed.html", title=title, posts=posts, active=active, query=query,
                           saved_ids=saved_ids, votes=votes, page_number=page_number,
                           has_previous=page_number > 1, has_next=page_number * page_size < total)


@app.route("/")
@app.route("/home")
def index():
    return render_feed()


@app.route("/top")
def top():
    return render_feed("Top", visible_posts().order_by(Post.up_votes.desc()).all(), "top")


@app.route("/trending")
def trending():
    posts = sorted(visible_posts().all(), key=lambda post: post.up_votes + post.comment_count * 4, reverse=True)
    return render_feed("Trending", posts, "trending")


@app.route("/fresh")
def fresh():
    return render_feed("Fresh", visible_posts().order_by(Post.created_rank.desc()).all(), "fresh")


@app.route("/news")
def news():
    posts = visible_posts().filter(Post.section.in_(["news", "politics", "science"])).order_by(Post.created_rank.desc()).all()
    return render_feed("News", posts, "news")


@app.route("/interest/<section>")
def interest(section):
    posts = visible_posts().filter(db.func.lower(Post.section) == section.lower()).order_by(Post.up_votes.desc()).all()
    return render_feed(section.replace("-", " ").title(), posts, section)


@app.route("/tag/<tag>")
def tag(tag):
    needle = tag.replace("-", " ").lower()
    posts = visible_posts().filter(db.func.lower(Post.tags).contains(needle)).all()
    return render_feed(f"#{needle}", posts, "", needle)


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    return render_feed("Search", scored_posts(query, visible_posts().all()), "", query)


@app.route("/shuffle")
def shuffle():
    return redirect(url_for("post_detail", slug=Post.query.order_by(db.func.random()).first_or_404().slug))


@app.route("/gag/<slug>")
def post_detail(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    saved = current_user.is_authenticated and SavedPost.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
    vote = Vote.query.filter_by(user_id=current_user.id, post_id=post.id).first() if current_user.is_authenticated else None
    related = Post.query.filter(Post.section == post.section, Post.id != post.id).order_by(Post.up_votes.desc()).limit(5).all()
    return render_template("post_detail.html", post=post, saved=saved, vote=vote, related=related)


@app.post("/gag/<slug>/vote")
@login_required
def vote(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    value = 1 if request.form.get("value") == "1" else -1
    existing = Vote.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing and existing.value == value:
        db.session.delete(existing)
        post.up_votes -= int(value == 1)
        post.down_votes -= int(value == -1)
    elif existing:
        post.up_votes += 1 if value == 1 else -1
        post.down_votes += 1 if value == -1 else -1
        existing.value = value
    else:
        db.session.add(Vote(user_id=current_user.id, post_id=post.id, value=value))
        post.up_votes += int(value == 1)
        post.down_votes += int(value == -1)
    db.session.commit()
    return redirect(request.referrer or url_for("post_detail", slug=slug))


@app.post("/gag/<slug>/save")
@login_required
def save_post(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    row = SavedPost.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if row:
        db.session.delete(row)
        flash("Removed from saved posts.")
    else:
        db.session.add(SavedPost(user_id=current_user.id, post_id=post.id))
        flash("Saved to your collection.")
    db.session.commit()
    return redirect(request.referrer or url_for("post_detail", slug=slug))


@app.post("/gag/<slug>/comment")
@login_required
def add_comment(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    body = request.form.get("body", "").strip()
    if len(body) < 2:
        flash("Comment must contain at least 2 characters.", "error")
    else:
        db.session.add(Comment(post_id=post.id, user_id=current_user.id, body=body, created_at="just now"))
        post.comment_count += 1
        db.session.commit()
        flash("Comment posted.")
    return redirect(url_for("post_detail", slug=slug) + "#comments")


@app.post("/gag/<slug>/hide")
@login_required
def hide_post(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    if not HiddenPost.query.filter_by(user_id=current_user.id, post_id=post.id).first():
        db.session.add(HiddenPost(user_id=current_user.id, post_id=post.id))
        db.session.commit()
    flash("Post hidden from your feeds.")
    return redirect(url_for("index"))


@app.route("/gag/<slug>/report", methods=["GET", "POST"])
@login_required
def report_post(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if reason:
            db.session.add(Report(user_id=current_user.id, post_id=post.id, reason=reason))
            db.session.commit()
            flash("Thanks. Your report was submitted.")
            return redirect(url_for("post_detail", slug=slug))
        flash("Choose a reason.", "error")
    return render_template("report.html", post=post)


@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if len(title) < 4:
            flash("A title of at least 4 characters is required.", "error")
        else:
            base, slug, suffix = slugify(title), slugify(title), 2
            while Post.query.filter_by(slug=slug).first():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            post = Post(source_id=f"local-{Post.query.count() + 1}", slug=slug, title=title,
                        description=request.form.get("description", "").strip() or "Shared with the 9GAG community.",
                        image=request.form.get("image", "posts/aVvGONd-41d662a3.jpg"), section=request.form.get("section", "humor"),
                        post_type="Photo", tags=request.form.get("tags", ""), author_name=current_user.username,
                        up_votes=0, down_votes=0, comment_count=0, created_rank=Post.query.count() + 100)
            db.session.add(post)
            db.session.commit()
            flash("Your post is live.")
            return redirect(url_for("post_detail", slug=post.slug))
    return render_template("submit.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip()
        user = User.query.filter((User.email == identity) | (User.username == identity)).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            return redirect(request.args.get("next") or url_for("index"))
        flash("Incorrect email, username, or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email, username, password = request.form.get("email", "").strip().lower(), request.form.get("username", "").strip(), request.form.get("password", "")
        if "@" not in email or len(username) < 3 or len(password) < 8:
            flash("Enter a valid email, username, and password of at least 8 characters.", "error")
        elif User.query.filter((User.email == email) | (User.username == username)).first():
            flash("That email or username is already registered.", "error")
        else:
            user = User(email=email, username=username, display_name=username, password_hash="")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    posts = Post.query.filter_by(author_name=current_user.username).order_by(Post.created_rank.desc()).all()
    return render_template("account.html", profile=current_user, posts=posts)


@app.route("/u/<username>")
def profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author_name=username).order_by(Post.created_rank.desc()).all()
    return render_template("account.html", profile=profile_user, posts=posts)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        if not display_name:
            flash("Display name is required.", "error")
        else:
            current_user.display_name = display_name
            current_user.bio = request.form.get("bio", "").strip()[:500]
            current_user.location = request.form.get("location", "").strip()[:120]
            db.session.commit()
            flash("Profile updated.")
    return render_template("settings.html")


@app.route("/saved")
@login_required
def saved():
    rows = SavedPost.query.filter_by(user_id=current_user.id).order_by(SavedPost.id.desc()).all()
    return render_feed("Saved", [row.post for row in rows], "saved")


@app.route("/notifications")
@login_required
def notifications():
    return render_template("notifications.html")


@app.route("/about")
def about():
    return render_template("static_page.html", heading="About 9GAG", body="9GAG is a community-powered entertainment platform where people discover and discuss funny, surprising, and timely posts.")


@app.route("/rules")
def rules():
    return render_template("static_page.html", heading="Community rules", body="Be respectful, post original context, use accurate interests and tags, and report content that breaks community standards.")


@app.route("/apps")
def apps():
    return render_template("apps.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/_health")
def health():
    return {"ok": True, "site": "9gag", "posts": Post.query.count()}


with app.app_context():
    db.create_all()
    from seed_data import seed_benchmark_users, seed_database
    seed_database(db, User, Post, Comment, SavedPost, Vote)
    seed_benchmark_users(db, User, Post, Comment, SavedPost, Vote)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
