"""
GitHub Mirror - Flask Application
A faithful reproduction of GitHub's design and features.
"""
import os
import json
import re
import math
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, flash,
                   request, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from wtforms import StringField, PasswordField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, URL
from sqlalchemy import or_, func

# ───────────────────────── Mirror Clock ─────────────────────────
# The github mirror is a frozen snapshot. Every "now"-dependent value
# (relative-time strings like "2 days ago", "updated in last N days"
# search filters, seed timestamps, user-action timestamps) anchors to this
# constant so WebVoyager tasks like "find a repo updated in the last 2 days"
# produce the SAME answer regardless of when the user runs the mirror image.
# Flask-Login session expiry, CSRF tokens, and cookie lifetimes still use
# real wall-clock time (handled inside the framework, not via this clock).
MIRROR_REFERENCE_DATE = datetime(2024, 5, 15, 12, 0, 0)


def mirror_now():
    return MIRROR_REFERENCE_DATE


# ─────────────────────────── App Setup ───────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'github-mirror-secret-key-2024-xzy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///github_mirror.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ─────────────────────────── Models ───────────────────────────

# Association table: Repository <-> Topic
repo_topics = db.Table('repo_topics',
    db.Column('repo_id', db.Integer, db.ForeignKey('repository.id'), primary_key=True),
    db.Column('topic_id', db.Integer, db.ForeignKey('topic.id'), primary_key=True)
)

# Association table: User follows
follows = db.Table('follows',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(39), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), default='')
    bio = db.Column(db.String(255), default='')
    location = db.Column(db.String(100), default='')
    website = db.Column(db.String(200), default='')
    company = db.Column(db.String(100), default='')
    twitter = db.Column(db.String(100), default='')
    avatar = db.Column(db.String(200), default='')
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=mirror_now)
    # Plan
    plan = db.Column(db.String(20), default='free')  # free, team, enterprise

    # Relationships
    repositories = db.relationship('Repository', backref='owner', lazy='dynamic',
                                   foreign_keys='Repository.owner_id',
                                   cascade='all, delete-orphan')
    stars = db.relationship('Star', backref='user', lazy='dynamic',
                            cascade='all, delete-orphan')
    watches = db.relationship('Watch', backref='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    issues_filed = db.relationship('Issue', backref='author', lazy='dynamic',
                                   cascade='all, delete-orphan')
    comments = db.relationship('IssueComment', backref='author', lazy='dynamic',
                               cascade='all, delete-orphan')
    following = db.relationship('User', secondary=follows,
                                primaryjoin=(follows.c.follower_id == id),
                                secondaryjoin=(follows.c.followed_id == id),
                                lazy='dynamic', backref=db.backref('followers', lazy='dynamic'))

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar
        # Prefer a real-github scraped avatar if we have one on disk for this username
        if self.username:
            real_path = os.path.join(
                os.path.dirname(__file__), 'static', 'images', 'avatars',
                f'{self.username}.png')
            if os.path.exists(real_path):
                return f"/static/images/avatars/{self.username}.png"
        idx = (self.id or 0) % 15
        return f"/static/images/avatars/avatar_{idx:02d}.jpg"

    @property
    def followers_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()

    @property
    def public_repos_count(self):
        return self.repositories.filter_by(is_public=True).count()

    def is_following(self, user):
        return self.following.filter(follows.c.followed_id == user.id).count() > 0

    def has_starred(self, repo):
        return Star.query.filter_by(user_id=self.id, repo_id=repo.id).first() is not None

    def has_watched(self, repo):
        return Watch.query.filter_by(user_id=self.id, repo_id=repo.id).first() is not None


class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    language = db.Column(db.String(50), default='')
    license = db.Column(db.String(50), default='')
    stars_count = db.Column(db.Integer, default=0)
    forks_count = db.Column(db.Integer, default=0)
    watchers_count = db.Column(db.Integer, default=0)
    open_issues_count = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=True)
    is_fork = db.Column(db.Boolean, default=False)
    is_template = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    has_readme = db.Column(db.Boolean, default=True)
    has_wiki = db.Column(db.Boolean, default=False)
    has_issues = db.Column(db.Boolean, default=True)
    owner_type = db.Column(db.String(20), default='user')  # user, org
    homepage = db.Column(db.String(200), default='')
    default_branch = db.Column(db.String(50), default='main')
    size_kb = db.Column(db.Integer, default=0)
    readme = db.Column(db.Text, default='')
    topics_text = db.Column(db.Text, default='[]')  # JSON array of topic strings
    gallery_json = db.Column(db.Text, default='[]')  # JSON gallery sections
    created_at = db.Column(db.DateTime, default=mirror_now)
    updated_at = db.Column(db.DateTime, default=mirror_now, onupdate=mirror_now)
    pushed_at = db.Column(db.DateTime, default=mirror_now)
    # Task-driven extras: commits, releases, contributors, wiki — stored as JSON text
    latest_release_version = db.Column(db.String(50), default='')
    latest_release_date = db.Column(db.DateTime, nullable=True)
    latest_release_notes = db.Column(db.Text, default='')
    releases_json = db.Column(db.Text, default='[]')  # list of {version, date, notes}
    contributors_json = db.Column(db.Text, default='[]')  # list of {username, commits, avatar}
    latest_commit_sha = db.Column(db.String(40), default='')
    latest_commit_message = db.Column(db.Text, default='')
    latest_commit_date = db.Column(db.DateTime, nullable=True)
    latest_commit_files = db.Column(db.Text, default='[]')  # list of {name, additions, deletions}
    latest_commit_additions = db.Column(db.Integer, default=0)
    latest_commit_deletions = db.Column(db.Integer, default=0)
    # Recent commit history: list of {sha, message, author, date, files[], additions, deletions}.
    # Index 0 mirrors latest_commit_* for backward compatibility.
    commits_json = db.Column(db.Text, default='[]')
    wiki_pages_json = db.Column(db.Text, default='[]')  # list of {slug, title, body}

    # Relationships
    topics = db.relationship('Topic', secondary=repo_topics, backref='repositories', lazy='dynamic')
    stars = db.relationship('Star', backref='repo', lazy='dynamic', cascade='all, delete-orphan')
    watches = db.relationship('Watch', backref='repo', lazy='dynamic', cascade='all, delete-orphan')
    issues = db.relationship('Issue', backref='repo', lazy='dynamic', cascade='all, delete-orphan')

    def get_topics(self):
        try:
            return json.loads(self.topics_text or '[]')
        except Exception:
            return []

    def get_gallery(self):
        try:
            return json.loads(self.gallery_json or '[]')
        except Exception:
            return []

    def stars_display(self):
        n = self.stars_count
        if n >= 1000:
            return f"{n/1000:.1f}k"
        return str(n)

    def get_releases(self):
        try:
            return json.loads(self.releases_json or '[]')
        except Exception:
            return []

    def get_contributors(self):
        try:
            return json.loads(self.contributors_json or '[]')
        except Exception:
            return []

    def get_commit_files(self):
        try:
            return json.loads(self.latest_commit_files or '[]')
        except Exception:
            return []

    def get_commits(self):
        try:
            return json.loads(self.commits_json or '[]')
        except Exception:
            return []

    def get_wiki_pages(self):
        try:
            return json.loads(self.wiki_pages_json or '[]')
        except Exception:
            return []

    def updated_relative(self):
        # Match GitHub's <relative-time> default threshold P30D: relative
        # phrasing within 30 days, absolute "on Mon DD, YYYY" beyond.
        delta = mirror_now() - self.updated_at
        if delta.days >= 30:
            return f"Updated on {self.updated_at.strftime('%b %-d, %Y')}"
        if delta.days >= 1:
            return f"Updated {delta.days} day{'s' if delta.days > 1 else ''} ago"
        hours = delta.seconds // 3600
        if hours >= 1:
            return f"Updated {hours} hour{'s' if hours > 1 else ''} ago"
        return "Updated just now"


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    short_desc = db.Column(db.String(200), default='')
    image = db.Column(db.String(200), default='')
    repos_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=mirror_now)


class Star(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    repo_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=mirror_now)
    __table_args__ = (db.UniqueConstraint('user_id', 'repo_id'),)


class Watch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    repo_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=mirror_now)
    __table_args__ = (db.UniqueConstraint('user_id', 'repo_id'),)


class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='open')  # open, closed (PR: open, closed, merged)
    labels_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=mirror_now)
    closed_at = db.Column(db.DateTime, nullable=True)
    # PR support: 0 = regular issue, 1 = pull request
    is_pr = db.Column(db.Integer, default=0)
    # PR-only metadata; null for is_pr=0
    pr_head_branch = db.Column(db.String(120), default='')
    pr_base_branch = db.Column(db.String(120), default='main')
    pr_changed_files = db.Column(db.Integer, default=0)
    pr_additions = db.Column(db.Integer, default=0)
    pr_deletions = db.Column(db.Integer, default=0)
    pr_commits_count = db.Column(db.Integer, default=0)

    comments = db.relationship('IssueComment', backref='issue', lazy='dynamic',
                               cascade='all, delete-orphan')

    def get_labels(self):
        try:
            return json.loads(self.labels_json or '[]')
        except Exception:
            return []

    def comment_count(self):
        return self.comments.count()


class IssueComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=mirror_now)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ─────────────────────────── Forms ───────────────────────────

class LoginForm(FlaskForm):
    login = StringField('Username or email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1, 39)])
    email = StringField('Email address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(8, 128)])

class ProfileEditForm(FlaskForm):
    name = StringField('Name', validators=[Optional(), Length(max=100)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=255)])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    website = StringField('Website', validators=[Optional(), Length(max=200)])
    company = StringField('Company', validators=[Optional(), Length(max=100)])
    twitter = StringField('Twitter username', validators=[Optional(), Length(max=100)])

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old password', validators=[DataRequired()])
    new_password = PasswordField('New password', validators=[DataRequired(), Length(8, 128)])
    confirm_password = PasswordField('Confirm new password',
                                     validators=[DataRequired(), EqualTo('new_password')])

class NewRepoForm(FlaskForm):
    name = StringField('Repository name', validators=[DataRequired(), Length(1, 100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=255)])
    is_public = SelectField('Visibility', choices=[('true', 'Public'), ('false', 'Private')])
    init_readme = BooleanField('Add a README file')

class IssueForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(1, 255)])
    body = TextAreaField('Leave a comment', validators=[Optional()])

class CommentForm(FlaskForm):
    body = TextAreaField('Leave a comment', validators=[DataRequired()])

# ─────────────────────────── Helpers ───────────────────────────

_DEFAULT_LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584", "C++": "#f34b7d",
    "C": "#555555", "C#": "#178600", "Ruby": "#701516", "PHP": "#4F5D95",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Scala": "#c22d40",
    "Shell": "#89e051", "HTML": "#e34c26", "CSS": "#563d7c", "Vue": "#41b883",
    "Jupyter Notebook": "#DA5B0B", "R": "#198CE7", "Dart": "#00B4AB",
    "Elixir": "#6e4a7e", "Haskell": "#5e5086", "Lua": "#000080",
    "MATLAB": "#e16737", "OCaml": "#3be133", "PowerShell": "#012456",
    "Dockerfile": "#384d54", "Unknown": "#8f9ba8",
}

def _load_lang_colors():
    # Prefer the full 700-entry map scraped from github-colors; fall back to defaults.
    path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'lang_colors.json')
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            merged = dict(_DEFAULT_LANG_COLORS)
            merged.update({k: v for k, v in data.items() if isinstance(v, str)})
            return merged
        except Exception:
            pass
    return _DEFAULT_LANG_COLORS

LANG_COLORS = _load_lang_colors()


def avatar_for(username):
    """Resolve an avatar URL for any username (DB-linked or pure seed name).

    Checks static/images/avatars/<username>.png (scraped from real github),
    then the User table row (explicit override), otherwise rotates the 15
    generic pool images deterministically by hash."""
    if not username:
        return "/static/images/avatars/avatar_00.jpg"
    real = os.path.join(os.path.dirname(__file__), 'static', 'images', 'avatars',
                        f'{username}.png')
    if os.path.exists(real):
        return f"/static/images/avatars/{username}.png"
    u = User.query.filter_by(username=username).first()
    if u and u.avatar:
        return u.avatar
    # stable but varied fallback
    idx = abs(hash(username)) % 15
    return f"/static/images/avatars/avatar_{idx:02d}.jpg"

def load_gallery(full_name):
    path = os.path.join(os.path.dirname(__file__), 'repo_galleries.json')
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return data.get(full_name, [])
    return []

@app.context_processor
def inject_globals():
    return {
        'lang_colors': LANG_COLORS,
        'now': mirror_now(),
        'mirror_now': mirror_now(),
        'csrf_token': generate_csrf,
        'avatar_for': avatar_for,
    }


# ─── External github.com redirect middleware ───
# Some WebVoyager agents hallucinate real github.com URLs even though the task
# is hosted locally. If such a request ever reaches this Flask app (via
# /etc/hosts, proxy, or host header), rewrite it to the local equivalent so the
# agent lands on usable content instead of `about:blank`.
@app.before_request
def _redirect_external_github():
    host = (request.host or '').lower()
    # If the request arrives with a real github.com Host header, 307-redirect
    # to the local mirror path preserving the URL path & query string.
    if 'github.com' in host and 'localhost' not in host and '127.0.0.1' not in host:
        target = request.full_path.rstrip('?') or '/'
        # Strip leading /https:/github.com/ or similar, keep the path portion.
        return redirect(target, code=302)
    # Some agents also type URLs like /https://github.com/foo/bar into the bar.
    path = request.path or ''
    m = re.match(r'^/(https?:)?/*github\.com/(.*)$', path)
    if m:
        rest = m.group(2) or ''
        new_path = '/' + rest
        qs = request.query_string.decode('utf-8', errors='ignore')
        if qs:
            new_path += '?' + qs
        return redirect(new_path, code=302)

@app.template_filter('number_format')
def number_format(n):
    if n is None:
        return '0'
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)

@app.template_filter('time_ago')
def time_ago(dt):
    # Match GitHub's <relative-time> default threshold P30D: relative
    # phrasing within 30 days, absolute "on Mon DD, YYYY" beyond.
    if not dt:
        return ''
    delta = mirror_now() - dt
    if delta.days >= 30:
        return f"on {dt.strftime('%b %-d, %Y')}"
    if delta.days >= 1:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours}h ago"
    minutes = delta.seconds // 60
    if minutes >= 1:
        return f"{minutes}m ago"
    return "just now"

# ─────────────────────────── Seed Data ───────────────────────────

def seed_database():
    if User.query.count() > 0:
        return

    # Demo users
    users_data = [
        ("octocat", "octocat@github.com", "Octocat", "GitHub's mascot", "San Francisco, CA",
         "https://github.com", "GitHub", "github", "free"),
        ("torvalds", "torvalds@linux.org", "Linus Torvalds",
         "Creator of Linux and Git. If there is one...", "Portland, OR",
         "", "Linux Foundation", "", "free"),
        ("gaearon", "gaearon@gmail.com", "Dan Abramov",
         "Working on @reactjs. Co-author of Redux and Create React App.", "London, UK",
         "https://overreacted.io", "", "dan_abramov", "free"),
        ("yyx990803", "yyx990803@gmail.com", "Evan You",
         "Creator of @vuejs and @vitejs. Independent open source developer.", "",
         "https://evanyou.me", "", "youyuxi", "free"),
        ("gvanrossum", "guido@python.org", "Guido van Rossum",
         "Python's creator. Retired BDFL.", "Belmont, CA", "", "", "", "free"),
        ("dhh", "dhh@hey.com", "David Heinemeier Hansson",
         "Creator of Ruby on Rails, co-owner of Basecamp, author of REWORK.", "",
         "https://dhh.dk", "37signals", "dhh", "free"),
        ("tj", "tj@apex.sh", "TJ Holowaychuk",
         "Prolific open source developer. Creator of Express, Koa, Mocha...", "",
         "", "", "", "free"),
        ("brendangregg", "brendan.d.gregg@gmail.com", "Brendan Gregg",
         "Systems performance and observability at Netflix.", "Santa Clara, CA",
         "https://www.brendangregg.com", "Netflix", "", "free"),
        ("sindresorhus", "sindresorhus@gmail.com", "Sindre Sorhus",
         "Full-Time Open-Sourcerer. Maker of stuff.", "Bangkok, Thailand",
         "https://sindresorhus.com", "", "sindresorhus", "free"),
        ("antirez", "antirez@gmail.com", "Salvatore Sanfilippo",
         "I'm the creator of Redis.", "Sicily, Italy",
         "http://invece.org", "", "antirez", "free"),
        ("mitchellh", "mitchell@hashicorp.com", "Mitchell Hashimoto",
         "Co-founder of HashiCorp. Building Ghostty.", "San Francisco, CA",
         "", "HashiCorp", "", "team"),
        ("defunkt", "chris@github.com", "Chris Wanstrath",
         "Co-founder of GitHub.", "San Francisco, CA",
         "", "GitHub", "defunkt", "free"),
        ("wycats", "wycats@gmail.com", "Yehuda Katz",
         "Co-creator of Ember.js, Rust core, Rails core, Bundler, Cargo.", "",
         "https://yehudakatz.com", "Tilde", "", "free"),
        ("fabpot", "fabien@symfony.com", "Fabien Potencier",
         "Creator of the Symfony PHP framework.", "Nantes, France",
         "https://fabien.potencier.org", "SensioLabs", "", "free"),
        ("mxcl", "mxcl@me.com", "Max Howell",
         "Creator of Homebrew. Software engineer.", "",
         "", "", "mxcl", "free"),
    ]

    users = []
    for i, (uname, email, name, bio, loc, web, company, twitter, plan) in enumerate(users_data):
        u = User(username=uname, email=email, name=name, bio=bio,
                 location=loc, website=web, company=company, twitter=twitter, plan=plan)
        u.set_password("password123")
        u.avatar = f"/static/images/avatars/avatar_{i:02d}.jpg"
        db.session.add(u)
        users.append(u)

    db.session.flush()

    # Demo topics
    topics_data = [
        ("python", "Python", "Python is a dynamically typed programming language designed to be quick to learn, understand, and use.", "Dynamically typed, garbage-collected language", True),
        ("javascript", "JavaScript", "JavaScript, often abbreviated as JS, is a high-level, dynamic programming language conforming to the ECMAScript specification.", "High-level, dynamic language for the web", True),
        ("typescript", "TypeScript", "TypeScript is a statically typed superset of JavaScript that adds optional static typing.", "Typed superset of JavaScript", True),
        ("machine-learning", "Machine learning", "A subset of artificial intelligence (AI) that provides systems the ability to automatically learn and improve from experience.", "AI that learns from data", True),
        ("deep-learning", "Deep learning", "Deep learning is a subfield of machine learning that uses neural networks with many layers.", "Neural networks with many layers", True),
        ("react", "React", "React is a JavaScript library for building user interfaces, maintained by Facebook.", "Facebook's UI library", True),
        ("vue", "Vue.js", "Vue.js is an open-source model-view-viewmodel front end JavaScript framework.", "Progressive JavaScript framework", True),
        ("rust", "Rust", "Rust is a multi-paradigm, general-purpose programming language emphasizing performance, type safety, and concurrency.", "Safe, fast systems language", True),
        ("go", "Go", "Go is an open source programming language that makes it easy to build simple, reliable, and efficient software.", "Google's systems programming language", True),
        ("kubernetes", "Kubernetes", "Kubernetes is an open-source system for automating deployment, scaling, and management of containerized applications.", "Container orchestration system", True),
        ("docker", "Docker", "Docker is a platform for developers and sysadmins to develop, deploy, and run applications with containers.", "Application containerization platform", False),
        ("api", "API", "An application programming interface (API) is a connection between computers or between computer programs.", "Interface between software components", False),
        ("web-development", "Web development", "Web development is the work involved in developing a website for the Internet.", "Building websites and web apps", False),
        ("security", "Security", "Security is freedom from, or resilience against, potential harm caused by others.", "Protecting systems and data", False),
        ("open-source", "Open source", "Open-source software is software with source code that anyone can inspect, modify, and enhance.", "Freely available source code", True),
        ("nlp", "Natural language processing", "Natural language processing (NLP) is a subfield of linguistics, computer science, and AI concerning interactions between computers and human language.", "Processing human language", False),
        ("devops", "DevOps", "DevOps is a set of practices that combines software development and IT operations.", "Development and operations collaboration", False),
        ("cloud", "Cloud computing", "Cloud computing is the on-demand availability of computer system resources.", "On-demand computing resources", False),
        ("hacktoberfest", "Hacktoberfest", "Hacktoberfest is a month-long celebration of open source software run by DigitalOcean.", "Annual open source event", True),
        ("ai", "Artificial intelligence", "Artificial intelligence (AI) is intelligence demonstrated by machines.", "Machine intelligence", True),
        ("frontend", "Front end", "Front-end web development is the practice of converting data to a graphical interface.", "UI-focused web development", False),
        ("backend", "Back end", "Back-end web development is the server side of web development.", "Server-side web development", False),
        ("java", "Java", "Java is a class-based, object-oriented programming language designed for portability.", "Object-oriented, portable language", False),
        ("swift", "Swift", "Swift is a powerful and intuitive programming language for Apple platforms.", "Apple's modern programming language", False),
        ("kotlin", "Kotlin", "Kotlin is a cross-platform, statically typed, general-purpose programming language.", "Modern JVM language by JetBrains", False),
    ]

    topic_objs = {}
    for slug, display, desc, short_desc, is_featured in topics_data:
        t = Topic(slug=slug, display_name=display, description=desc,
                  short_desc=short_desc, is_featured=is_featured)
        db.session.add(t)
        topic_objs[slug] = t

    db.session.flush()

    now = mirror_now()

    # Seed repositories
    repos_data = [
        {
            "owner": "microsoft", "name": "vscode",
            "desc": "Visual Studio Code - Open Source ('Code - OSS')",
            "lang": "TypeScript", "license": "MIT",
            "stars": 163000, "forks": 29000, "watchers": 3500, "issues": 7800,
            "topics": ["typescript", "open-source", "web-development", "api", "hacktoberfest"],
            "homepage": "https://code.visualstudio.com",
            "updated": now - timedelta(hours=2),
            "readme": """# Visual Studio Code - Open Source ("Code - OSS")

[![Feature Requests](https://img.shields.io/github/issues/microsoft/vscode/feature-request.svg)](https://github.com/microsoft/vscode/issues?q=is%3Aopen+is%3Aissue+label%3Afeature-request+sort%3Areactions-%2B1-desc)
[![Bugs](https://img.shields.io/github/issues/microsoft/vscode/bug.svg)](https://github.com/microsoft/vscode/issues?utf8=✓&q=is%3Aissue+is%3Aopen+label%3Abug)

The `microsoft/vscode` repository is where we do development and there are many ways you can participate in the project, for example:

* [Submit bugs and feature requests](https://github.com/microsoft/vscode/issues), and help us verify as they are checked in
* Review [source code changes](https://github.com/microsoft/vscode/pulls)
* Review the [documentation](https://github.com/microsoft/vscode-docs) and make pull requests for anything from typos to new content

## Contributing

There are many ways in which you can participate in this project, for example:

* Submit bugs and feature requests and help us verify as they are checked in
* Review source code changes

If you are interested in fixing issues and contributing directly to the code base, please see the document [How to Contribute](https://github.com/microsoft/vscode/wiki/How-to-Contribute).
"""
        },
        {
            "owner": "torvalds", "name": "linux",
            "desc": "Linux kernel source tree",
            "lang": "C", "license": "GPL-2.0",
            "stars": 180000, "forks": 54000, "watchers": 7800, "issues": 0,
            "topics": ["c", "open-source", "devops", "security"],
            "homepage": "https://www.kernel.org",
            "updated": now - timedelta(hours=1),
            "readme": """# Linux kernel

There are several guides for kernel developers and users. These guides can be rendered in a number of formats, like HTML and PDF. Please read Documentation/admin-guide/README.rst first.

In order to build the documentation, use ``make htmldocs`` or ``make pdfdocs``. The formatted documentation can also be read online at:

    https://www.kernel.org/doc/html/latest/

There are various text files in the Documentation/ subdirectory, several of them using the Restructured Text markup notation.

Please read the Documentation/process/changes.rst file, as it contains the requirements for building and running the kernel, and information about the problems which may result by upgrading your kernel.
"""
        },
        {
            "owner": "tensorflow", "name": "tensorflow",
            "desc": "An Open Source Machine Learning Framework for Everyone",
            "lang": "Python", "license": "Apache-2.0",
            "stars": 185000, "forks": 74000, "watchers": 8200, "issues": 3100,
            "topics": ["python", "machine-learning", "deep-learning", "ai", "nlp"],
            "homepage": "https://www.tensorflow.org",
            "updated": now - timedelta(hours=3),
            "readme": """# TensorFlow

TensorFlow is an end-to-end open source platform for machine learning. It has a comprehensive, flexible ecosystem of tools, libraries, and community resources that lets researchers push the state-of-the-art in ML and developers easily build and deploy ML-powered applications.

## Install

See the [TensorFlow install guide](https://www.tensorflow.org/install) for the [pip package](https://www.tensorflow.org/install/pip), to [enable GPU support](https://www.tensorflow.org/install/gpu), use a [Docker container](https://www.tensorflow.org/install/docker), and [build from source](https://www.tensorflow.org/install/source).

To install the current release, which includes support for CUDA-enabled GPU cards:

```
$ pip install tensorflow
```
"""
        },
        {
            "owner": "facebook", "name": "react",
            "desc": "The library for web and native user interfaces.",
            "lang": "JavaScript", "license": "MIT",
            "stars": 228000, "forks": 47000, "watchers": 9100, "issues": 900,
            "topics": ["javascript", "react", "frontend", "web-development", "open-source"],
            "homepage": "https://react.dev",
            "updated": now - timedelta(hours=5),
            "readme": """# React

React is a JavaScript library for building user interfaces.

* **Declarative:** React makes it painless to create interactive UIs. Design simple views for each state in your application, and React will efficiently update and render just the right components when your data changes.
* **Component-Based:** Build encapsulated components that manage their own state, then compose them to make complex UIs.
* **Learn Once, Write Anywhere:** We don't make assumptions about the rest of your technology stack, so you can develop new features in React without rewriting existing code.

[Learn how to use React in your project](https://react.dev/learn).

## Installation

React has been designed for gradual adoption from the start, and **you can use as little or as much React as you need**:

```
npm install react react-dom
```
"""
        },
        {
            "owner": "vuejs", "name": "vue",
            "desc": "This is the repo for Vue 2. For Vue 3, go to https://github.com/vuejs/core",
            "lang": "TypeScript", "license": "MIT",
            "stars": 208000, "forks": 33700, "watchers": 6400, "issues": 600,
            "topics": ["javascript", "vue", "frontend", "web-development", "typescript"],
            "homepage": "https://vuejs.org",
            "updated": now - timedelta(days=3),
            "readme": """# Vue.js

[![npm](https://img.shields.io/npm/v/vue.svg)](https://npmjs.com/package/vue)

Vue (pronounced /vjuː/, like view) is a **progressive framework** for building user interfaces. Unlike other monolithic frameworks, Vue is designed from the ground up to be incrementally adoptable. The core library is focused on the view layer only, and is easy to pick up and integrate with other libraries or existing projects.

## Ecosystem

| Project | Status | Description |
|---------|--------|-------------|
| [vue-router] | [![vue-router-status]][vue-router-package] | Single-page application routing |
| [vuex] | [![vuex-status]][vuex-package] | Large-scale state management |
| [vue-cli] | [![vue-cli-status]][vue-cli-package] | Project scaffolding |
| [vue-loader] | [![vue-loader-status]][vue-loader-package] | Single File Component (`*.vue` file) loader for webpack |
"""
        },
        {
            "owner": "golang", "name": "go",
            "desc": "The Go programming language",
            "lang": "Go", "license": "BSD-3-Clause",
            "stars": 124000, "forks": 17700, "watchers": 3200, "issues": 9200,
            "topics": ["go", "open-source", "backend", "api"],
            "homepage": "https://go.dev",
            "updated": now - timedelta(hours=3),
            "readme": """# The Go Programming Language

Go is an open source programming language that makes it easy to build simple, reliable, and efficient software.

![Gopher image](https://golang.org/doc/gopher/fiveyears.jpg)
*Gopher image by [Renee French][rf], licensed under [Creative Commons 4.0 Attributions license][cc4-by].*

Our canonical Git repository is located at https://go.googlesource.com/go. There is a mirror of the repository at https://github.com/golang/go.

Unless otherwise noted, the Go source files are distributed under the BSD-style license found in the LICENSE file.
"""
        },
        {
            "owner": "rust-lang", "name": "rust",
            "desc": "Empowering everyone to build reliable and efficient software.",
            "lang": "Rust", "license": "MIT",
            "stars": 97000, "forks": 12500, "watchers": 2400, "issues": 9800,
            "topics": ["rust", "open-source", "systems", "security"],
            "homepage": "https://www.rust-lang.org",
            "updated": now - timedelta(hours=4),
            "readme": """# The Rust Programming Language

This is the main source code repository for [Rust]. It contains the compiler, standard library, and documentation.

[Rust]: https://www.rust-lang.org

**Note: this README is for _users_ rather than _contributors_.**

## Quick Start

Read ["Installation"] from [The Book].

["Installation"]: https://doc.rust-lang.org/book/ch01-01-installation.html
[The Book]: https://doc.rust-lang.org/book/index.html
"""
        },
        {
            "owner": "kubernetes", "name": "kubernetes",
            "desc": "Production-Grade Container Scheduling and Management",
            "lang": "Go", "license": "Apache-2.0",
            "stars": 111000, "forks": 40000, "watchers": 3700, "issues": 2400,
            "topics": ["go", "kubernetes", "docker", "cloud", "devops"],
            "homepage": "https://kubernetes.io",
            "updated": now - timedelta(minutes=45),
            "readme": """# Kubernetes

Kubernetes, also known as K8s, is an open source system for managing [containerized applications] across multiple hosts. It provides basic mechanisms for the deployment, maintenance, and scaling of applications.

Kubernetes builds upon a decade and a half of experience at Google running production workloads at scale using a system called [Borg], combined with best-of-breed ideas and practices from the community.

Kubernetes is hosted by the Cloud Native Computing Foundation ([CNCF]).
If you want to know more about CNCF, check out their [website](https://www.cncf.io/).
"""
        },
        {
            "owner": "huggingface", "name": "transformers",
            "desc": "🤗 Transformers: State-of-the-art Machine Learning for Pytorch, TensorFlow, and JAX.",
            "lang": "Python", "license": "Apache-2.0",
            "stars": 136000, "forks": 27200, "watchers": 2800, "issues": 1500,
            "topics": ["python", "machine-learning", "deep-learning", "nlp", "ai"],
            "homepage": "https://huggingface.co/docs/transformers",
            "updated": now - timedelta(hours=2),
            "readme": """# Transformers

State-of-the-art Machine Learning for JAX, PyTorch and TensorFlow

Transformers provides thousands of pretrained models to perform tasks on different modalities such as text, vision, and audio.

These models can be applied on:

📝 Text, for tasks like text classification, information extraction, question answering, summarization, translation, and text generation, in over 100 languages.
🖼️ Images, for tasks like image classification, object detection, and segmentation.
🔊 Audio, for tasks like speech recognition and audio classification.

Transformers models can also perform tasks on **several modalities combined**, such as table question answering, optical character recognition, information extraction from scanned documents, video classification, and visual question answering.

## Installation

```bash
pip install transformers
```
"""
        },
        {
            "owner": "langchain-ai", "name": "langchain",
            "desc": "🦜🔗 Build context-aware reasoning applications",
            "lang": "Python", "license": "MIT",
            "stars": 95000, "forks": 15300, "watchers": 1900, "issues": 1200,
            "topics": ["python", "machine-learning", "ai", "nlp", "open-source"],
            "homepage": "https://python.langchain.com",
            "updated": now - timedelta(hours=4),
            "readme": """# 🦜🔗 LangChain

⚡ Build context-aware reasoning applications ⚡

Looking for the JS/TS version? Check out [LangChain.js](https://github.com/langchain-ai/langchainjs).

To help you ship LangChain apps to production faster, check out [LangSmith](https://smith.langchain.com).

[LangSmith](https://smith.langchain.com) is a unified developer platform for building, testing, and monitoring LLM applications. Fill out [this form](https://www.langchain.com/contact-sales) to speak with our sales team.

## Quick Install

```bash
pip install langchain
```
"""
        },
        {
            "owner": "tiangolo", "name": "fastapi",
            "desc": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
            "lang": "Python", "license": "MIT",
            "stars": 78000, "forks": 6700, "watchers": 1400, "issues": 700,
            "topics": ["python", "api", "backend", "web-development", "open-source"],
            "homepage": "https://fastapi.tiangolo.com",
            "updated": now - timedelta(hours=5),
            "readme": """# FastAPI

FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.

The key features are:

* **Fast**: Very high performance, on par with **NodeJS** and **Go** (thanks to Starlette and Pydantic). [One of the fastest Python frameworks available](#performance).
* **Fast to code**: Increase the speed to develop features by about 200% to 300%. *
* **Fewer bugs**: Reduce about 40% of human (developer) induced errors. *
* **Intuitive**: Great editor support. Completion everywhere. Less time debugging.
* **Easy**: Designed to be easy to use and learn. Less time reading docs.
* **Short**: Minimize code duplication. Multiple features from each parameter declaration.
* **Robust**: Get production-ready code. With automatic interactive documentation.

```
pip install fastapi
```
"""
        },
        {
            "owner": "django", "name": "django",
            "desc": "The Web framework for perfectionists with deadlines.",
            "lang": "Python", "license": "BSD-3-Clause",
            "stars": 81000, "forks": 31900, "watchers": 2400, "issues": 230,
            "topics": ["python", "web-development", "backend", "open-source", "security"],
            "homepage": "https://www.djangoproject.com/",
            "updated": now - timedelta(hours=8),
            "readme": """# Django

Django is a high-level Python web framework that encourages rapid development and clean, pragmatic design. Built by experienced developers, it takes care of much of the hassle of web development, so you can focus on writing your app without needing to reinvent the wheel. It's free and open source.

## Supported Versions

Refer to the Django documentation for the supported versions.

## Contributing to Django

As an open source project, we welcome contributions.

Component | Test Command
---------- | ------
All tests | `./runtests.py`
"""
        },
        {
            "owner": "rails", "name": "rails",
            "desc": "Ruby on Rails",
            "lang": "Ruby", "license": "MIT",
            "stars": 55800, "forks": 21700, "watchers": 1800, "issues": 810,
            "topics": ["ruby", "web-development", "backend", "open-source", "api"],
            "homepage": "https://rubyonrails.org",
            "updated": now - timedelta(hours=12),
            "readme": """# Ruby on Rails

[![Version](https://badge.fury.io/rb/railties.svg)](https://badge.fury.io/rb/railties)
[![Build Status](https://github.com/rails/rails/workflows/CI/badge.svg)](https://github.com/rails/rails/actions)

Rails is a web-application framework that includes everything needed to create database-backed web applications according to the Model-View-Controller (MVC) pattern.

Understanding the MVC pattern is key to understanding Rails. MVC divides your application into three layers: Model, View, and Controller, each with a specific responsibility.
"""
        },
        {
            "owner": "nodejs", "name": "node",
            "desc": "Node.js JavaScript runtime ✨🐢🚀✨",
            "lang": "JavaScript", "license": "MIT",
            "stars": 107000, "forks": 29400, "watchers": 3300, "issues": 1700,
            "topics": ["javascript", "backend", "api", "web-development", "open-source"],
            "homepage": "https://nodejs.org",
            "updated": now - timedelta(hours=2),
            "readme": """# Node.js

Node.js is an open-source, cross-platform, JavaScript runtime environment.

For information on using Node.js, see the [Node.js website](https://nodejs.org).

The Node.js project uses an [open governance model](./GOVERNANCE.md). The [OpenJS Foundation](https://openjsf.org/) provides support for the project.

**This project is bound by a [Code of Conduct](https://github.com/nodejs/.github/blob/main/CODE_OF_CONDUCT.md).**

## Table of Contents

* [Support](#support)
* [Release Types](#release-types)
  * [Download](#download)
    * [Current and LTS Releases](#current-and-lts-releases)
    * [Nightly Releases](#nightly-releases)
"""
        },
        {
            "owner": "vercel", "name": "next.js",
            "desc": "The React Framework – created and maintained by @vercel.",
            "lang": "JavaScript", "license": "MIT",
            "stars": 128000, "forks": 27200, "watchers": 3100, "issues": 2400,
            "topics": ["javascript", "react", "frontend", "web-development", "typescript"],
            "homepage": "https://nextjs.org",
            "updated": now - timedelta(hours=1),
            "readme": """# Next.js

The React Framework for the Web.

Used by some of the world's largest companies, Next.js enables you to create high-quality web applications with the power of React components.

## Features

- An intuitive [page-based](https://nextjs.org/docs/basic-features/pages) routing system (with support for [dynamic routes](https://nextjs.org/docs/routing/dynamic-routes))
- [Pre-rendering](https://nextjs.org/docs/basic-features/pages#pre-rendering), both [static generation](https://nextjs.org/docs/basic-features/pages#static-generation-recommended) (SSG) and [server-side rendering](https://nextjs.org/docs/basic-features/pages#server-side-rendering) (SSR) are supported on a per-page basis
- Automatic code splitting for faster page loads
- [Client-side navigation](https://nextjs.org/docs/routing/introduction#linking-between-pages) with optimized prefetching
"""
        },
        {
            "owner": "pallets", "name": "flask",
            "desc": "The Python micro framework for building web applications.",
            "lang": "Python", "license": "BSD-3-Clause",
            "stars": 67800, "forks": 16300, "watchers": 1700, "issues": 120,
            "topics": ["python", "web-development", "backend", "api", "open-source"],
            "homepage": "https://flask.palletsprojects.com",
            "updated": now - timedelta(days=4),
            "readme": """# Flask

Flask is a lightweight [WSGI](https://wsgi.readthedocs.io) web application framework. It is designed to make getting started quick and easy, with the ability to scale up to complex applications. It began as a simple wrapper around [Werkzeug](https://werkzeug.palletsprojects.com) and [Jinja](https://jinja.palletsprojects.com) and has become one of the most popular Python web application frameworks.

Flask offers suggestions, but doesn't enforce any dependencies or project layout. It is up to the developer to choose the tools and libraries they want to use. There are many extensions provided by the community that make adding new functionality easy.

```
pip install Flask
```
"""
        },
        {
            "owner": "expressjs", "name": "express",
            "desc": "Fast, unopinionated, minimalist web framework for node.",
            "lang": "JavaScript", "license": "MIT",
            "stars": 64900, "forks": 15200, "watchers": 2100, "issues": 230,
            "topics": ["javascript", "backend", "api", "web-development", "nodejs"],
            "homepage": "https://expressjs.com",
            "updated": now - timedelta(days=6),
            "readme": """# Express

Fast, unopinionated, minimalist web framework for [Node.js](http://nodejs.org).

```js
const express = require('express')
const app = express()

app.get('/', function (req, res) {
  res.send('Hello World')
})

app.listen(3000)
```
"""
        },
        {
            "owner": "sveltejs", "name": "svelte",
            "desc": "web development for the rest of us",
            "lang": "JavaScript", "license": "MIT",
            "stars": 80200, "forks": 4400, "watchers": 1400, "issues": 570,
            "topics": ["javascript", "frontend", "web-development", "open-source"],
            "homepage": "https://svelte.dev",
            "updated": now - timedelta(days=2),
            "readme": """# Svelte

Svelte is a new way to build web applications. It's a compiler that takes your declarative components and converts them into efficient JavaScript that surgically updates the DOM.

Learn more at the [Svelte website](https://svelte.dev), or stop by the [Discord chatroom](https://svelte.dev/chat).

## Getting started

You can play around with Svelte in the [tutorial](https://learn.svelte.dev/) or the [examples](https://svelte.dev/examples).

To create a new project:

```sh
npm create svelte@latest myapp
cd myapp
npm install
npm run dev
```
"""
        },
        {
            "owner": "redis", "name": "redis",
            "desc": "Redis is an in-memory database that persists on disk.",
            "lang": "C", "license": "BSD-3-Clause",
            "stars": 67000, "forks": 23800, "watchers": 2000, "issues": 1700,
            "topics": ["c", "backend", "open-source", "security", "cloud"],
            "homepage": "https://redis.io",
            "updated": now - timedelta(days=1),
            "readme": """# Redis

Redis is often referred to as a _data structures_ server. What this means is that Redis provides access to mutable data structures via a set of commands, which are sent using a _server-client_ model with TCP sockets and a simple protocol.

You can run atomic operations on these types, like appending to a string; incrementing the value in a hash; pushing an element to a list; computing set intersection, union and difference; or getting the member with highest ranking in a sorted set.

In order to achieve its outstanding performance, Redis works with an **in-memory dataset**. Depending on your use case, you can persist your data either by periodically **dumping the dataset to disk** or by **appending each command to a disk-based log**.

## Building Redis

Redis can be compiled and used on Linux, OSX, OpenBSD, NetBSD, FreeBSD.
"""
        },
        {
            "owner": "denoland", "name": "deno",
            "desc": "A modern runtime for JavaScript and TypeScript.",
            "lang": "Rust", "license": "MIT",
            "stars": 96000, "forks": 5300, "watchers": 1900, "issues": 1900,
            "topics": ["rust", "javascript", "typescript", "web-development", "open-source"],
            "homepage": "https://deno.com",
            "updated": now - timedelta(hours=10),
            "readme": """# Deno

[![Discord Chat](https://img.shields.io/discord/684898665143148621?logo=discord&style=social)](https://discord.gg/deno)

Deno is a *simple*, *modern* and *secure* runtime for **JavaScript** and **TypeScript** that uses V8 and is built in Rust.

### Features

- Secure by default. No file, network, or environment access, unless explicitly enabled.
- Supports TypeScript out of the box.
- Ships only a single executable file.
- Has built-in utilities like a dependency inspector (`deno info`) and a code formatter (`deno fmt`).
- Has [a set of reviewed standard modules](https://jsr.io/@std) that are guaranteed to work with Deno.
"""
        },
    ]

    # Map usernames to user objects
    user_map = {u.username: u for u in users}
    repo_map = {}

    for rd in repos_data:
        owner_name = rd["owner"]
        # Create owner user if not in seed list
        if owner_name not in user_map:
            u = User(username=owner_name, email=f"{owner_name}@example.com",
                     name=owner_name.title(), plan='free')
            u.set_password("password123")
            u.avatar = "/static/images/avatars/avatar_00.jpg"
            db.session.add(u)
            db.session.flush()
            user_map[owner_name] = u

        owner = user_map[owner_name]
        full_name = f"{owner_name}/{rd['name']}"

        gallery = load_gallery(full_name)

        repo = Repository(
            owner_id=owner.id,
            name=rd["name"],
            full_name=full_name,
            description=rd["desc"],
            language=rd["lang"],
            license=rd["license"],
            stars_count=rd["stars"],
            forks_count=rd["forks"],
            watchers_count=rd["watchers"],
            open_issues_count=rd["issues"],
            is_public=True,
            homepage=rd.get("homepage", ""),
            size_kb=rd.get("size_kb", 10000),
            readme=rd.get("readme", ""),
            topics_text=json.dumps(rd["topics"]),
            gallery_json=json.dumps(gallery),
            created_at=rd.get("created", now - timedelta(days=3000)),
            updated_at=rd["updated"],
            pushed_at=rd["updated"],
        )
        db.session.add(repo)
        db.session.flush()

        # Link topics
        for t_slug in rd["topics"]:
            if t_slug in topic_objs:
                repo.topics.append(topic_objs[t_slug])

        repo_map[full_name] = repo

    db.session.flush()

    # Seed demo user's repositories
    demo_user = user_map.get("octocat")
    if demo_user:
        demo_repos = [
            ("Hello-World", "My first repository on GitHub!", "Python", 4000, now - timedelta(days=10)),
            ("Spoon-Knife", "This repo is for demonstration purposes only.", "HTML", 12000, now - timedelta(days=30)),
            ("linguist", "Language Savant. If your repository's language is being reported incorrectly, send us a pull request!", "Ruby", 11600, now - timedelta(days=5)),
        ]
        for rname, rdesc, rlang, rstars, rupdated in demo_repos:
            fname = f"octocat/{rname}"
            if fname not in repo_map:
                r = Repository(
                    owner_id=demo_user.id,
                    name=rname, full_name=fname,
                    description=rdesc, language=rlang,
                    stars_count=rstars, forks_count=rstars // 10,
                    watchers_count=rstars // 50, open_issues_count=5,
                    is_public=True, topics_text='["open-source"]',
                    readme=f"# {rname}\n\n{rdesc}",
                    created_at=now - timedelta(days=2500),
                    updated_at=rupdated, pushed_at=rupdated,
                )
                db.session.add(r)
                repo_map[fname] = r

    db.session.flush()

    # Update topic repos_count
    for slug, topic in topic_objs.items():
        topic.repos_count = len(topic.repositories)

    # Seed some issues
    all_repos = list(repo_map.values())[:5]
    issue_labels = [
        ['bug', 'good first issue'],
        ['enhancement', 'help wanted'],
        ['documentation'],
        ['question', 'bug'],
        ['feature request'],
    ]
    issue_num = {}
    for i, repo in enumerate(all_repos):
        issue_num[repo.id] = 0
        for j in range(3):
            issue_num[repo.id] += 1
            author = users[j % len(users)]
            iss = Issue(
                repo_id=repo.id,
                author_id=author.id,
                number=issue_num[repo.id],
                title=f"Sample issue #{issue_num[repo.id]}: {'Bug in main module' if j == 0 else 'Feature request' if j == 1 else 'Documentation update needed'}",
                body=f"This is a sample issue description. It describes {'a bug that needs to be fixed' if j == 0 else 'a new feature to add' if j == 1 else 'documentation improvements needed'}.",
                status='open',
                labels_json=json.dumps(issue_labels[j % len(issue_labels)]),
                created_at=now - timedelta(days=j * 7),
            )
            db.session.add(iss)
            db.session.flush()

            # Add a comment
            commenter = users[(j + 1) % len(users)]
            comment = IssueComment(
                issue_id=iss.id,
                author_id=commenter.id,
                body="Thanks for reporting this! We'll look into it.",
                created_at=now - timedelta(days=j * 7 - 1),
            )
            db.session.add(comment)

    # Seed some follows
    for i in range(min(5, len(users))):
        for j in range(min(3, len(users))):
            if i != j:
                users[i].following.append(users[j])

    # Seed some stars for the demo user
    if demo_user and all_repos:
        for repo in all_repos[:3]:
            star = Star(user_id=demo_user.id, repo_id=repo.id)
            db.session.add(star)

    db.session.commit()
    print("Database seeded successfully.")


# ─────────────────────────── Routes ───────────────────────────

@app.route('/')
def index():
    featured_repos = Repository.query.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(8).all()
    trending_repos = Repository.query.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(6).all()
    featured_topics = Topic.query.filter_by(is_featured=True).order_by(
        Topic.repos_count.desc()).limit(18).all()
    return render_template('index.html',
                           featured_repos=featured_repos,
                           trending_repos=trending_repos,
                           featured_topics=featured_topics)


@app.route('/search-syntax')
def search_syntax():
    return render_template('search_syntax.html')


@app.route('/explore')
def explore():
    trending = Repository.query.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(12).all()
    featured_topics = Topic.query.filter_by(is_featured=True).all()
    trending_devs = User.query.limit(8).all()
    collections = [
        {"title": "Machine Learning Models", "desc": "Cutting-edge ML frameworks and models", "count": 12},
        {"title": "Web Frameworks", "desc": "Modern frameworks for building web apps", "count": 18},
        {"title": "DevOps Tools", "desc": "Tools for CI/CD and infrastructure", "count": 9},
        {"title": "Security Tools", "desc": "Security scanning and vulnerability tools", "count": 7},
    ]
    return render_template('explore.html',
                           trending=trending,
                           featured_topics=featured_topics,
                           trending_devs=trending_devs,
                           collections=collections)


TRENDING_DEVELOPERS = [
    # (rank, username, name, trending_repo_full_name, since)
    (1, "yyx990803", "Evan You", "vuejs/vue", "monthly"),
    (2, "gaearon", "Dan Abramov", "facebook/react", "monthly"),
    (3, "torvalds", "Linus Torvalds", "torvalds/linux", "monthly"),
    (4, "tj", "TJ Holowaychuk", "expressjs/express", "monthly"),
    (5, "antirez", "Salvatore Sanfilippo", "redis/redis", "monthly"),
    (1, "gaearon", "Dan Abramov", "facebook/react", "weekly"),
    (2, "yyx990803", "Evan You", "vuejs/vue", "weekly"),
    (1, "torvalds", "Linus Torvalds", "torvalds/linux", "daily"),
    (2, "gaearon", "Dan Abramov", "facebook/react", "daily"),
]


@app.route('/trending')
def trending():
    lang_filter = request.args.get('l', '') or request.args.get('language', '')
    since = request.args.get('since', 'daily')
    tab = request.args.get('tab', 'repositories')
    page = request.args.get('page', 1, type=int)
    per_page = 25

    query = Repository.query.filter_by(is_public=True)
    if lang_filter:
        query = query.filter(Repository.language.ilike(lang_filter))
    repos = query.order_by(Repository.stars_count.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    languages = db.session.query(Repository.language, func.count(Repository.id)).filter(
        Repository.language != '').group_by(Repository.language).order_by(
        func.count(Repository.id).desc()).all()

    devs = [d for d in TRENDING_DEVELOPERS if d[4] == since]
    devs_info = []
    for rank, uname, name, repo_full, _s in devs:
        u = User.query.filter_by(username=uname).first()
        r = Repository.query.filter_by(full_name=repo_full).first()
        if u and r:
            devs_info.append({
                "rank": rank, "user": u, "repo": r,
                "repo_full_name": r.full_name,
            })

    return render_template('trending.html',
                           repos=repos, lang_filter=lang_filter,
                           since=since, tab=tab, languages=languages,
                           developers=devs_info)


@app.route('/trending/developers')
def trending_developers():
    """Dedicated Developers tab for GitHub Trending.
    Matches real URL https://github.com/trending/developers?since=monthly."""
    since = request.args.get('since', 'daily')
    lang_filter = request.args.get('l', '') or request.args.get('language', '')

    devs = [d for d in TRENDING_DEVELOPERS if d[4] == since]
    devs_info = []
    for rank, uname, name, repo_full, _s in devs:
        u = User.query.filter_by(username=uname).first()
        r = Repository.query.filter_by(full_name=repo_full).first()
        if u and r:
            devs_info.append({
                "rank": rank, "user": u, "repo": r,
                "repo_full_name": r.full_name,
            })

    # Empty repositories pagination for shared template
    repos = Repository.query.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).paginate(page=1, per_page=0, error_out=False)
    languages = db.session.query(Repository.language, func.count(Repository.id)).filter(
        Repository.language != '').group_by(Repository.language).order_by(
        func.count(Repository.id).desc()).all()

    return render_template('trending.html',
                           repos=repos, lang_filter=lang_filter,
                           since=since, tab='developers', languages=languages,
                           developers=devs_info)


@app.route('/topics')
def topics():
    featured = Topic.query.filter_by(is_featured=True).all()
    all_topics = Topic.query.order_by(Topic.repos_count.desc()).all()
    return render_template('topics.html', featured=featured, all_topics=all_topics)


@app.route('/topics/<slug>')
def topic_detail(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    sort_key = (request.args.get('o') or request.args.get('sort') or 'stars').lower()
    language = request.args.get('l', '').strip()

    q = Repository.query.filter(
        Repository.is_public == True,
        Repository.topics.any(Topic.slug == slug)
    )
    if language:
        q = q.filter(Repository.language == language)

    if sort_key in ('fewest_stars', 'stars_asc', 'stars-asc'):
        q = q.order_by(Repository.stars_count.asc())
    elif sort_key in ('most_forks', 'forks_desc', 'forks'):
        q = q.order_by(Repository.forks_count.desc())
    elif sort_key in ('fewest_forks', 'forks_asc'):
        q = q.order_by(Repository.forks_count.asc())
    elif sort_key in ('updated', 'most_updated', 'recently_updated', 'pushed'):
        q = q.order_by(Repository.pushed_at.desc())
    elif sort_key in ('least_updated', 'oldest_updated'):
        q = q.order_by(Repository.pushed_at.asc())
    elif sort_key in ('trending',):
        q = q.order_by(Repository.updated_at.desc(), Repository.stars_count.desc())
    else:  # default: most_stars
        sort_key = 'stars'
        q = q.order_by(Repository.stars_count.desc())

    repos = q.paginate(page=page, per_page=20, error_out=False)

    # Language facet for the filter chips
    lang_rows = (db.session.query(Repository.language, func.count(Repository.id))
                 .filter(Repository.is_public == True,
                         Repository.language != '',
                         Repository.topics.any(Topic.slug == slug))
                 .group_by(Repository.language)
                 .order_by(func.count(Repository.id).desc())
                 .limit(10).all())
    topic_languages = [(l, n) for l, n in lang_rows]

    return render_template('topic_detail.html', topic=topic, repos=repos,
                           current_sort=sort_key, current_lang=language,
                           topic_languages=topic_languages)


@app.route('/marketplace')
def marketplace():
    categories = [
        {"name": "Code quality", "icon": "check-circle", "count": 127},
        {"name": "Continuous integration", "icon": "zap", "count": 89},
        {"name": "Dependency management", "icon": "package", "count": 44},
        {"name": "Deployment", "icon": "cloud", "count": 73},
        {"name": "IDEs", "icon": "code", "count": 21},
        {"name": "Monitoring", "icon": "activity", "count": 56},
        {"name": "Project management", "icon": "trello", "count": 38},
        {"name": "Security", "icon": "shield", "count": 62},
        {"name": "Testing", "icon": "check-square", "count": 49},
        {"name": "Utilities", "icon": "tool", "count": 85},
    ]
    featured_apps = [
        {"name": "Snyk", "desc": "Find and fix vulnerabilities in your code", "icon": "🛡️", "stars": 4.8, "free": True},
        {"name": "Codecov", "desc": "Leading code coverage solution", "icon": "📊", "stars": 4.6, "free": True},
        {"name": "CircleCI", "desc": "Automate your development process", "icon": "⚡", "stars": 4.5, "free": True},
        {"name": "SonarCloud", "desc": "Code quality and security for your projects", "icon": "🔍", "stars": 4.7, "free": True},
        {"name": "Dependabot", "desc": "Automated dependency updates built into GitHub", "icon": "🤖", "stars": 4.9, "free": True},
        {"name": "DeepSource", "desc": "Detect 800+ types of issues in your code", "icon": "🔬", "stars": 4.4, "free": True},
    ]
    return render_template('marketplace.html', categories=categories, featured_apps=featured_apps)


@app.route('/pricing')
def pricing():
    plans = [
        {
            "name": "Free",
            "price": 0,
            "price_display": "$0",
            "period": "per month",
            "desc": "The basics for individuals and organizations",
            "cta": "Join for free",
            "cta_url": "/register",
            "private_repos": "Unlimited",
            "package_storage_gb": 0.5,
            "features": [
                "Unlimited public repositories",
                "Unlimited private repositories",
                "2,000 GitHub Actions minutes/month",
                "500MB GitHub Packages storage",
                "120 GitHub Codespaces core hours/month",
                "15GB GitHub Codespaces storage/month",
                "Community support",
            ],
            "is_popular": False,
        },
        {
            "name": "Pro",
            "price": 4,
            "price_display": "$4",
            "period": "per user/month",
            "desc": "For individuals looking for more collaboration and "
                    "advanced tooling",
            "cta": "Upgrade to Pro",
            "cta_url": "/register",
            "private_repos": "Unlimited",
            "package_storage_gb": 2,
            "features": [
                "Everything included in Free",
                "Unlimited private repositories",
                "3,000 GitHub Actions minutes/month",
                "2GB GitHub Packages storage",
                "Advanced tools for private repositories",
                "Required reviewers",
                "Multiple reviewers in pull requests",
                "Wiki for private repositories",
                "Protected branches",
                "Pages and wikis for private repos",
                "Email support",
            ],
            "is_popular": False,
        },
        {
            "name": "Team",
            "price": 4,
            "price_display": "$4",
            "period": "per user/month",
            "desc": "Advanced collaboration for individuals and organizations",
            "cta": "Continue with Team",
            "cta_url": "/register",
            "private_repos": "Unlimited",
            "package_storage_gb": 2,
            "features": [
                "Everything included in Free",
                "Access to GitHub Codespaces",
                "3,000 GitHub Actions minutes/month",
                "2GB GitHub Packages storage",
                "Web-based support",
                "Required reviewers",
                "Multiple reviewers in pull requests",
                "Draft pull requests",
                "Code owners",
                "Protected branches",
                "Repository insights graphs",
            ],
            "is_popular": True,
        },
        {
            "name": "Enterprise",
            "price": 21,
            "price_display": "$21",
            "period": "per user/month",
            "desc": "Security, compliance, and flexible deployment",
            "cta": "Start a free trial",
            "cta_url": "/register",
            "private_repos": "Unlimited",
            "package_storage_gb": 50,
            "features": [
                "Everything included in Team",
                "50,000 GitHub Actions minutes/month",
                "50GB GitHub Packages storage",
                "Enterprise Managed Users",
                "GitHub Connect",
                "SAML single sign-on",
                "Enterprise Account to centrally manage multiple organizations",
                "Advanced auditing",
                "GitHub Advanced Security (add-on)",
                "SOC 1 and SOC 2 type 2 compliance",
                "FedRAMP ATO",
                "24/7 premium support",
            ],
            "is_popular": False,
        },
    ]
    # Storage comparison: Enterprise 50GB - Team 2GB = 48GB more
    storage_comparison = {
        "team_gb": 2,
        "enterprise_gb": 50,
        "difference_gb": 48,
        "summary": "Enterprise includes 48 GB more GitHub Packages storage "
                   "than Team (50 GB vs 2 GB).",
    }
    return render_template('pricing.html', plans=plans,
                           storage_comparison=storage_comparison)


COPILOT_FEATURES = [
    {
        "name": "Code completion",
        "desc": "Get AI-powered code suggestions as you type in your editor. "
                "Copilot learns from your coding style and project context."
    },
    {
        "name": "Copilot Chat",
        "desc": "Ask Copilot questions in natural language right inside your IDE. "
                "Explain code, generate tests, fix bugs, and more."
    },
    {
        "name": "Pull request summaries",
        "desc": "Automatically generate pull request descriptions, review comments, "
                "and summaries so teams ship code faster."
    },
]

COPILOT_INDIVIDUAL_PLAN = {
    "name": "Copilot Individual",
    "price_monthly": 10,
    "price_yearly": 100,
    "price_display_monthly": "$10 USD/month",
    "price_display_yearly": "$100 USD/year",
    "features": [
        "Code completion in your IDE",
        "Copilot Chat in IDE and on GitHub.com",
        "Chat on GitHub Mobile",
        "Access to GPT-4o and Claude models",
        "Code review and explanation",
        "Pull request summaries",
        "Third-party model extensions",
    ],
}

COPILOT_FAQS = [
    {"q": "When can I use Copilot Chat on mobile?",
     "a": "GitHub Copilot Chat is available in GitHub Mobile on iOS and Android for "
          "all paid Copilot subscribers. You can start a chat from any repository on "
          "GitHub Mobile and get answers to coding questions on the go."},
    {"q": "Does Copilot Individual include access to Chat?",
     "a": "Yes. Copilot Individual includes Copilot Chat in supported IDEs, on "
          "GitHub.com, and in GitHub Mobile."},
    {"q": "How much does Copilot Individual cost?",
     "a": "Copilot Individual is $10 USD per month or $100 USD per year for "
          "verified individual developers."},
    {"q": "Which editors does Copilot support?",
     "a": "Copilot works with Visual Studio Code, Visual Studio, JetBrains IDEs, "
          "Neovim, and Xcode."},
    {"q": "Is Copilot available for students?",
     "a": "Yes, Copilot is free for verified students, teachers, and maintainers "
          "of popular open source projects through GitHub Education."},
]


@app.route('/features/copilot')
def feature_copilot():
    tiers = [
        {"name": "Copilot Free", "price": "$0", "desc": "For individuals just getting started",
         "completions": "2,000/month", "chat": "50/month", "features": ["Code completion", "Chat in IDE"]},
        {"name": "Copilot Individual", "price": "$10 USD/month",
         "desc": "For individual developers",
         "completions": "Unlimited", "chat": "Unlimited",
         "features": COPILOT_INDIVIDUAL_PLAN["features"]},
        {"name": "Copilot Pro+", "price": "$39 USD/month", "desc": "For power users",
         "completions": "Unlimited", "chat": "Unlimited",
         "features": ["Everything in Individual", "GitHub Spark access",
                      "Early access to new features"]},
        {"name": "Copilot Business", "price": "$19 USD/user/month", "desc": "For teams",
         "completions": "Unlimited", "chat": "Unlimited",
         "features": ["Everything in Individual", "Policy management", "Audit logs",
                      "IP indemnity"]},
    ]
    return render_template('feature_copilot.html', tiers=tiers,
                           features=COPILOT_FEATURES,
                           individual=COPILOT_INDIVIDUAL_PLAN)


@app.route('/features/copilot/faq')
def feature_copilot_faq():
    return render_template('feature_copilot_faq.html', faqs=COPILOT_FAQS)


@app.route('/skills')
def skills():
    first_day_courses = [
        {"slug": "introduction-to-github",
         "title": "Introduction to GitHub",
         "desc": "Get started using GitHub in less than an hour.",
         "duration": "1 hour"},
        {"slug": "communicate-using-markdown",
         "title": "Communicate using Markdown",
         "desc": "Learn Markdown to create rich content on GitHub.",
         "duration": "45 minutes"},
        {"slug": "github-pages",
         "title": "GitHub Pages",
         "desc": "Publish a website directly from your GitHub repository.",
         "duration": "1 hour"},
        {"slug": "hello-github-actions",
         "title": "Hello GitHub Actions",
         "desc": "Create your first GitHub Actions workflow.",
         "duration": "1 hour"},
    ]
    code_with_github = [
        {"slug": "review-pull-requests",
         "title": "Review pull requests",
         "desc": "Practice reviewing pull requests like a pro.",
         "duration": "1 hour"},
        {"slug": "resolve-merge-conflicts",
         "title": "Resolve merge conflicts",
         "desc": "Learn what causes merge conflicts and how to resolve them "
                 "using the GitHub web editor.",
         "duration": "1 hour",
         "actions": [
             "Identify when and why merge conflicts happen",
             "Resolve simple merge conflicts with the GitHub web editor",
             "Mark conflicts as resolved and complete a pull request merge",
         ]},
        {"slug": "release-based-workflow",
         "title": "Release-based workflow",
         "desc": "Practice a release-based workflow.",
         "duration": "2 hours"},
    ]
    automate_workflows = [
        {"slug": "continuous-integration",
         "title": "Continuous integration with GitHub Actions",
         "desc": "Learn how to create workflows that enable you to use CI.",
         "duration": "1 hour"},
        {"slug": "continuous-delivery",
         "title": "Continuous delivery with GitHub Actions",
         "desc": "Create two deployment workflows with GitHub Actions.",
         "duration": "1 hour"},
    ]
    sections = [
        {"heading": "First day on GitHub", "courses": first_day_courses},
        {"heading": "Code with GitHub", "courses": code_with_github},
        {"heading": "Automate workflows", "courses": automate_workflows},
    ]
    return render_template('skills.html', sections=sections)


@app.route('/skills/<slug>')
def skill_course(slug):
    all_courses = []
    for sec in [
        ("First day on GitHub", [
            ("introduction-to-github", "Introduction to GitHub"),
            ("communicate-using-markdown", "Communicate using Markdown"),
            ("github-pages", "GitHub Pages"),
            ("hello-github-actions", "Hello GitHub Actions"),
        ]),
    ]:
        all_courses.extend(sec[1])
    # Special: resolve merge conflicts detail page
    course_data = {
        "resolve-merge-conflicts": {
            "title": "Resolve merge conflicts",
            "desc": "Learn what causes merge conflicts and how to resolve them "
                    "using the GitHub web editor.",
            "duration": "1 hour",
            "actions": [
                "Identify when and why merge conflicts happen",
                "Resolve simple merge conflicts with the GitHub web editor",
                "Edit files and commit changes to finish a pull request",
                "Mark conflicts as resolved and complete a pull request merge",
            ],
        },
    }
    course = course_data.get(slug, {
        "title": slug.replace('-', ' ').title(),
        "desc": "GitHub Skills course.",
        "duration": "1 hour",
        "actions": ["Learn the fundamentals", "Practice with a hands-on repo",
                    "Complete the course"],
    })
    return render_template('skill_course.html', course=course, slug=slug)


CUSTOMER_STORIES = [
    {"slug": "mercedes-benz",
     "company": "Mercedes-Benz",
     "headline": "Mercedes-Benz accelerates software delivery with GitHub",
     "summary": "How the automaker uses GitHub Enterprise to build "
                "in-vehicle software faster across 800+ developers.",
     "industry": "Automotive"},
    {"slug": "shopify",
     "company": "Shopify",
     "headline": "Shopify scales developer productivity with GitHub Copilot",
     "summary": "Shopify's engineering team uses Copilot to ship code 55% "
                "faster while maintaining quality.",
     "industry": "E-commerce"},
]


@app.route('/customer-stories')
def customer_stories():
    return render_template('customer_stories.html', stories=CUSTOMER_STORIES)


@app.route('/customer-stories/<slug>')
def customer_story_detail(slug):
    story = next((s for s in CUSTOMER_STORIES if s['slug'] == slug), None)
    if not story:
        abort(404)
    return render_template('customer_story_detail.html', story=story)


RESOURCE_TOPICS = [
    {"slug": "security",
     "title": "Security",
     "headline": "Build secure software with GitHub",
     "intro": "Understand how GitHub helps you secure the software supply chain.",
     "sections": [
         {"heading": "What is GitHub Advanced Security?",
          "body": "GitHub Advanced Security is a suite of tools built into "
                  "the developer workflow. It runs on every pull request, "
                  "every push, and every default-branch update, so security "
                  "feedback arrives at the same time as code review feedback. "
                  "Code scanning analyzes your source for over 200 classes "
                  "of vulnerability using CodeQL. Secret scanning detects "
                  "leaked tokens across every commit and every fork. "
                  "Dependency review flags vulnerable open-source packages "
                  "before they merge. Together, these checks make security "
                  "part of how developers ship — not a separate gate."},
         {"heading": "Code scanning",
          "body": "Automatically analyze your code for vulnerabilities and "
                  "errors with CodeQL."},
         {"heading": "Secret scanning",
          "body": "Detect leaked credentials across your repositories and "
                  "automatically alert partners."},
     ]},
    {"slug": "devops",
     "title": "DevOps",
     "headline": "Learn how GitHub enables DevOps",
     "intro": "DevOps is the collaboration between development and operations.",
     "sections": [
         {"heading": "What is DevOps?",
          "body": "DevOps brings together people, processes, and technology "
                  "to deliver value to customers."},
     ]},
    {"slug": "ai",
     "title": "AI",
     "headline": "Build with AI on GitHub",
     "intro": "Explore how GitHub helps you build AI-powered applications.",
     "sections": [
         {"heading": "What is GitHub Copilot?",
          "body": "Copilot is your AI pair programmer."},
     ]},
]


@app.route('/resources')
def resources():
    return render_template('resources.html', topics=RESOURCE_TOPICS)


@app.route('/resources/security')
def resources_security():
    """Rich Security marketing page. Preserves the original Q&A so the
    WebVoyager GitHub--21 'role of Advanced Security' answer is still
    extractable from the page."""
    topic = next((t for t in RESOURCE_TOPICS if t['slug'] == 'security'), None)
    return render_template('resources_security.html', topic=topic)


@app.route('/resources/<slug>')
def resources_topic(slug):
    topic = next((t for t in RESOURCE_TOPICS if t['slug'] == slug), None)
    if not topic:
        abort(404)
    return render_template('resources_topic.html', topic=topic)


@app.route('/signup/check')
@csrf.exempt
def signup_check():
    email = request.args.get('email', '').strip().lower()
    exists = bool(email and User.query.filter_by(email=email).first())
    return jsonify({"email": email, "exists": exists,
                    "message": ("Email already registered." if exists
                                else "Email is available.")})


@app.route('/features/actions')
def feature_actions():
    return render_template('feature_actions.html')


@app.route('/features/codespaces')
def feature_codespaces():
    return render_template('feature_codespaces.html')


@app.route('/about')
def about():
    return render_template('about.html')


# ─── Auth ───

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        login_id = form.login.data.strip()
        user = User.query.filter(
            or_(User.email == login_id, User.username == login_id)
        ).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        uname = form.username.data.strip().lower()
        if User.query.filter_by(username=uname).first():
            flash('Username already taken.', 'danger')
        elif User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash('Email already registered.', 'danger')
        else:
            u = User(username=uname, email=form.email.data.strip().lower(),
                     name=uname)
            u.set_password(form.password.data)
            u.avatar = f"/static/images/avatars/avatar_{(hash(uname) % 15):02d}.jpg"
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash('Account created! Welcome to GitHub Mirror.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))


# ─── User Profile ───

@app.route('/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    tab = request.args.get('tab', 'repositories')
    repos = user.repositories.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(20).all()
    starred = Star.query.filter_by(user_id=user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(20).all()
    return render_template('user_profile.html', profile_user=user, repos=repos,
                           starred=starred, tab=tab)


@app.route('/<username>/followers')
def user_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers_list = user.followers.all()
    repos = user.repositories.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(20).all()
    starred = Star.query.filter_by(user_id=user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(20).all()
    return render_template('user_profile.html', profile_user=user, repos=repos,
                           starred=starred, tab='followers', follow_users=followers_list)


@app.route('/<username>/following')
def user_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following_list = user.following.all()
    repos = user.repositories.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(20).all()
    starred = Star.query.filter_by(user_id=user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(20).all()
    return render_template('user_profile.html', profile_user=user, repos=repos,
                           starred=starred, tab='following', follow_users=following_list)


# ─── Repository ───

@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_repo():
    form = NewRepoForm()
    if form.validate_on_submit():
        rname = form.name.data.strip()
        rname = re.sub(r'[^a-zA-Z0-9_\-.]', '-', rname)
        full_name = f"{current_user.username}/{rname}"
        if Repository.query.filter_by(full_name=full_name).first():
            flash('A repository with this name already exists.', 'danger')
        else:
            is_pub = form.is_public.data == 'true'
            readme_content = ""
            if form.init_readme.data:
                readme_content = f"# {rname}\n\n{form.description.data or ''}"
            repo = Repository(
                owner_id=current_user.id,
                name=rname,
                full_name=full_name,
                description=form.description.data or '',
                is_public=is_pub,
                readme=readme_content,
                topics_text='[]',
                gallery_json='[]',
            )
            db.session.add(repo)
            db.session.commit()
            flash(f'Repository {full_name} created!', 'success')
            return redirect(url_for('repo_detail', username=current_user.username, reponame=rname))
    return render_template('new_repo.html', form=form)


@app.route('/<username>/<reponame>')
def repo_detail(username, reponame):
    user = User.query.filter_by(username=username).first_or_404()
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    if not repo.is_public and (not current_user.is_authenticated or current_user.id != repo.owner_id):
        abort(404)
    gallery = repo.get_gallery()
    topics = repo.get_topics()
    recent_issues = repo.issues.filter_by(status='open').order_by(
        Issue.created_at.desc()).limit(5).all()
    is_starred = current_user.is_authenticated and current_user.has_starred(repo)
    is_watching = current_user.is_authenticated and current_user.has_watched(repo)
    related = Repository.query.filter(
        Repository.language == repo.language,
        Repository.id != repo.id,
        Repository.is_public == True
    ).order_by(Repository.stars_count.desc()).limit(4).all()
    # Live open-issue count so the Issues tab badge matches the
    # /issues page (which filters the issue table directly).
    open_count = repo.issues.filter_by(status='open', is_pr=0).count()
    open_pr_count = repo.issues.filter_by(status='open', is_pr=1).count()
    all_commits = repo.get_commits()
    commit_count = len(all_commits) if all_commits else (1 if repo.latest_commit_sha else 0)
    latest_author = (all_commits[0].get('author') if all_commits else user.username)
    return render_template('repo_detail.html', repo=repo, owner=user,
                           gallery=gallery, topics=topics,
                           recent_issues=recent_issues,
                           is_starred=is_starred, is_watching=is_watching,
                           related=related, open_count=open_count,
                           open_pr_count=open_pr_count,
                           commit_count=commit_count,
                           latest_author=latest_author)


def _first_commit(repo, owner_username):
    """Synthesize a representative 'first commit' row from repo.created_at.
    Lets the /commits page surface the repo's creation date even though we
    only persist the 10 most recent commits in commits_json."""
    import hashlib
    sha = hashlib.sha1(f'{repo.full_name}::initial'.encode()).hexdigest()
    created = repo.created_at
    return {
        'sha': sha,
        'message': 'Initial commit',
        'date': created.strftime('%Y-%m-%dT%H:%M:%S') if created else '',
        'author': owner_username,
        'files': [
            {'name': 'README.md', 'additions': 24, 'deletions': 0},
            {'name': '.gitignore', 'additions': 8, 'deletions': 0},
            {'name': 'LICENSE', 'additions': 21, 'deletions': 0},
        ],
        'additions': 53,
        'deletions': 0,
        'is_first': True,
    }


@app.route('/<username>/<reponame>/commits')
def repo_commits(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    commits = repo.get_commits()
    # Backwards-compatibility: if commits_json hasn't been seeded yet, fall back
    # to a single-commit list synthesized from latest_commit_* columns.
    if not commits and repo.latest_commit_sha:
        commits = [{
            'sha': repo.latest_commit_sha,
            'message': repo.latest_commit_message or '',
            'date': repo.latest_commit_date.isoformat() if repo.latest_commit_date else '',
            'author': (User.query.get(repo.owner_id).username if repo.owner_id else username),
            'files': repo.get_commit_files(),
            'additions': repo.latest_commit_additions or 0,
            'deletions': repo.latest_commit_deletions or 0,
        }]
    owner_username = (User.query.get(repo.owner_id).username if repo.owner_id else username)
    first_commit = _first_commit(repo, owner_username)
    return render_template('repo_commits.html', repo=repo, commits=commits,
                           first_commit=first_commit)


@app.route('/<username>/<reponame>/commit/<sha>')
def repo_commit_detail(username, reponame, sha):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    commits = repo.get_commits()
    commit = next((c for c in commits if c.get('sha', '').startswith(sha) or sha.startswith(c.get('sha', ''))), None)
    if not commit:
        # Maybe it's the latest commit (which may not yet be in commits_json)
        if repo.latest_commit_sha and (repo.latest_commit_sha.startswith(sha) or sha.startswith(repo.latest_commit_sha)):
            commit = {
                'sha': repo.latest_commit_sha,
                'message': repo.latest_commit_message or '',
                'date': repo.latest_commit_date.isoformat() if repo.latest_commit_date else '',
                'author': (User.query.get(repo.owner_id).username if repo.owner_id else username),
                'files': repo.get_commit_files(),
                'additions': repo.latest_commit_additions or 0,
                'deletions': repo.latest_commit_deletions or 0,
            }
    if not commit:
        # Maybe it's the synthesized "first commit" sha (= sha1(full_name + '::initial'))
        owner_username = (User.query.get(repo.owner_id).username if repo.owner_id else username)
        fc = _first_commit(repo, owner_username)
        if fc['sha'].startswith(sha) or sha.startswith(fc['sha']):
            commit = fc
    if not commit:
        abort(404)
    return render_template('repo_commit_detail.html', repo=repo, commit=commit)


@app.route('/<username>/<reponame>/releases')
def repo_releases(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    releases = repo.get_releases() or []
    # Enrich each release record with author/avatar/is_prerelease/assets/body_html
    # derived from whatever the seed script supplied, with sensible defaults so the
    # card template can always render a full layout.
    owner = User.query.get(repo.owner_id)
    default_author = owner.username if owner else username
    enriched = []
    for idx, r in enumerate(releases):
        author = r.get('author') or default_author
        body = r.get('notes') or r.get('body') or ''
        version = r.get('version') or 'untagged'
        is_pre = bool(r.get('is_prerelease') or
                      any(tag in version.lower()
                          for tag in ('rc', 'beta', 'alpha', 'pre', 'canary')))
        assets = r.get('assets') or [
            {'name': f"Source code (zip)", 'size': '—'},
            {'name': f"Source code (tar.gz)", 'size': '—'},
        ]
        enriched.append({
            'version': version,
            'date': r.get('date') or '',
            'notes': body,
            'author': author,
            'author_avatar': avatar_for(author),
            'is_prerelease': is_pre,
            'is_latest': (idx == 0),
            'assets': assets,
            'commit_sha': r.get('commit_sha') or (f"{abs(hash(version)):x}"[:7]),
        })
    open_count = repo.issues.filter_by(status='open').count()
    return render_template('repo_releases.html', repo=repo, releases=enriched,
                           open_count=open_count)


@app.route('/<username>/<reponame>/contributors')
def repo_contributors(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    raw = repo.get_contributors() or []
    # Build enriched contributor cards: avatar + commit count + tiny sparkline data
    enriched = []
    max_commits = max((c.get('commits', 0) for c in raw), default=1) or 1
    for c in raw:
        uname = c.get('username') or 'contributor'
        commits = int(c.get('commits') or 0)
        additions = int(c.get('additions') or commits * 47)
        deletions = int(c.get('deletions') or commits * 12)
        # deterministic mini bar chart (30 bars, heights 2-20)
        import hashlib
        seed = int(hashlib.md5(uname.encode()).hexdigest()[:8], 16)
        bars = []
        for i in range(30):
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            bars.append(3 + (seed % 17))
        u = User.query.filter_by(username=uname).first()
        enriched.append({
            'username': uname,
            'display_name': (u.name if u and u.name else uname),
            'commits': commits,
            'commit_share': round(commits * 100.0 / max_commits, 1),
            'additions': additions,
            'deletions': deletions,
            'avatar': avatar_for(uname),
            'bio': (u.bio if u else ''),
            'bars': bars,
        })
    # Honor ?sort=<key>. Previously the template shipped a bare <select>
    # with no onchange handler, so agents clicking it saw zero effect even
    # though the label claimed the list was resorted. Now: route parses
    # `sort`, resorts the list, and the template binds the <select> to
    # navigate on change so the rendered order matches the label.
    sort_key = (request.args.get('sort') or '').lower().strip()
    if sort_key in ('commits_asc', 'fewest_commits', 'commits-asc'):
        enriched.sort(key=lambda c: c['commits'])
        sort_key = 'commits_asc'
    elif sort_key in ('additions', 'most_additions', 'additions_desc'):
        enriched.sort(key=lambda c: -c['additions'])
        sort_key = 'additions'
    elif sort_key in ('deletions', 'most_deletions', 'deletions_desc'):
        enriched.sort(key=lambda c: -c['deletions'])
        sort_key = 'deletions'
    else:  # default: commits desc
        enriched.sort(key=lambda c: -c['commits'])
        sort_key = 'commits'
    # Recompute rank after sorting so the "#1" label on each card matches
    # the rendered position, not the pre-sort order.
    for i, c in enumerate(enriched, 1):
        c['rank'] = i
    # Live open-issue count so the Issues tab badge matches /issues.
    open_count = repo.issues.filter_by(status='open').count()
    return render_template('repo_contributors.html', repo=repo,
                           contributors=enriched,
                           total_commits=sum(c['commits'] for c in enriched),
                           current_sort=sort_key,
                           open_count=open_count)


@app.route('/<username>/<reponame>/graphs/contributors')
def repo_contributors_graphs(username, reponame):
    """Real github URL is /<user>/<repo>/graphs/contributors — keep the short
    /contributors path too for backwards compat with existing task-solver
    trajectories."""
    return repo_contributors(username, reponame)


@app.route('/<username>/<reponame>/stargazers')
def repo_stargazers(username, reponame):
    """Previously 404. List users who starred this repo."""
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    rows = (db.session.query(User)
            .join(Star, Star.user_id == User.id)
            .filter(Star.repo_id == repo.id)
            .order_by(Star.created_at.desc())
            .all())
    return render_template('repo_stargazers.html', repo=repo, stargazers=rows)


@app.route('/<username>/<reponame>/wiki')
def repo_wiki(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    pages = repo.get_wiki_pages()
    return render_template('repo_wiki.html', repo=repo, pages=pages)


@app.route('/<username>/<reponame>/wiki/<page_slug>')
def repo_wiki_page(username, reponame, page_slug):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    pages = repo.get_wiki_pages()
    page = next((p for p in pages if p.get('slug') == page_slug), None)
    if not page:
        abort(404)
    return render_template('repo_wiki_page.html', repo=repo, page=page, pages=pages)


@app.route('/<username>/<reponame>/issues')
def repo_issues(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    status = request.args.get('q', 'is:open')
    is_open = 'closed' not in status
    # Match real github default: open issues sorted by created_at desc;
    # closed issues sorted by closed_at desc (so "last N closed" is unambiguous).
    if is_open:
        issues = repo.issues.filter_by(status='open', is_pr=0).order_by(
            Issue.created_at.desc()).all()
    else:
        issues = repo.issues.filter_by(status='closed', is_pr=0).order_by(
            Issue.closed_at.desc().nulls_last(), Issue.created_at.desc()).all()
    open_count = repo.issues.filter_by(status='open', is_pr=0).count()
    closed_count = repo.issues.filter_by(status='closed', is_pr=0).count()
    form = IssueForm()
    return render_template('repo_issues.html', repo=repo, issues=issues,
                           is_open=is_open, open_count=open_count,
                           closed_count=closed_count, form=form)


@app.route('/<username>/<reponame>/pulls')
def repo_pulls(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    status = request.args.get('q', 'is:open')
    is_open = 'closed' not in status and 'merged' not in status
    show_merged = 'merged' in status
    if show_merged:
        pulls = repo.issues.filter_by(status='merged', is_pr=1).order_by(Issue.created_at.desc()).all()
    elif is_open:
        pulls = repo.issues.filter_by(status='open', is_pr=1).order_by(Issue.created_at.desc()).all()
    else:
        pulls = repo.issues.filter(Issue.is_pr == 1, Issue.status.in_(('closed', 'merged'))).order_by(Issue.created_at.desc()).all()
    open_count = repo.issues.filter_by(status='open', is_pr=1).count()
    closed_count = repo.issues.filter(Issue.is_pr == 1, Issue.status.in_(('closed', 'merged'))).count()
    return render_template('repo_pulls.html', repo=repo, pulls=pulls,
                           is_open=is_open, show_merged=show_merged,
                           open_count=open_count, closed_count=closed_count)


@app.route('/<username>/<reponame>/issues/new', methods=['GET', 'POST'])
@login_required
def new_issue(username, reponame):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    form = IssueForm()
    if form.validate_on_submit():
        next_num = (repo.issues.count() or 0) + 1
        issue = Issue(
            repo_id=repo.id,
            author_id=current_user.id,
            number=next_num,
            title=form.title.data,
            body=form.body.data or '',
            status='open',
            labels_json='[]',
        )
        db.session.add(issue)
        repo.open_issues_count = repo.issues.filter_by(status='open').count() + 1
        db.session.commit()
        flash('Issue created!', 'success')
        return redirect(url_for('issue_detail', username=username, reponame=reponame,
                                number=issue.number))
    return render_template('new_issue.html', repo=repo, form=form)


@app.route('/<username>/<reponame>/issues/<int:number>')
def issue_detail(username, reponame, number):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    issue = Issue.query.filter_by(repo_id=repo.id, number=number).first_or_404()
    comments = issue.comments.order_by(IssueComment.created_at.asc()).all()
    form = CommentForm()
    return render_template('issue_detail.html', repo=repo, issue=issue,
                           comments=comments, form=form)


@app.route('/<username>/<reponame>/issues/<int:number>/comment', methods=['POST'])
@login_required
def add_issue_comment(username, reponame, number):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    issue = Issue.query.filter_by(repo_id=repo.id, number=number).first_or_404()
    form = CommentForm()
    if form.validate_on_submit():
        comment = IssueComment(
            issue_id=issue.id,
            author_id=current_user.id,
            body=form.body.data,
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comment added.', 'success')
    return redirect(url_for('issue_detail', username=username, reponame=reponame, number=number))


@app.route('/<username>/<reponame>/issues/<int:number>/close', methods=['POST'])
@login_required
def close_issue(username, reponame, number):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    issue = Issue.query.filter_by(repo_id=repo.id, number=number).first_or_404()
    if current_user.id == issue.author_id or current_user.id == repo.owner_id:
        issue.status = 'closed'
        issue.closed_at = mirror_now()
        repo.open_issues_count = max(0, (repo.open_issues_count or 1) - 1)
        db.session.commit()
        flash('Issue closed.', 'success')
    return redirect(url_for('issue_detail', username=username, reponame=reponame, number=number))


@app.route('/<username>/<reponame>/issues/<int:number>/reopen', methods=['POST'])
@login_required
def reopen_issue(username, reponame, number):
    repo = Repository.query.filter_by(full_name=f"{username}/{reponame}").first_or_404()
    issue = Issue.query.filter_by(repo_id=repo.id, number=number).first_or_404()
    if current_user.id == issue.author_id or current_user.id == repo.owner_id:
        issue.status = 'open'
        issue.closed_at = None
        repo.open_issues_count = (repo.open_issues_count or 0) + 1
        db.session.commit()
        flash('Issue reopened.', 'success')
    return redirect(url_for('issue_detail', username=username, reponame=reponame, number=number))


# ─── Account ───

@app.route('/account')
@login_required
def account():
    repos = current_user.repositories.order_by(Repository.updated_at.desc()).limit(10).all()
    stars = Star.query.filter_by(user_id=current_user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(10).all()
    following = current_user.following.limit(8).all()
    followers = current_user.followers.limit(8).all()
    return render_template('account.html', repos=repos, stars=stars,
                           following=following, followers=followers)


@app.route('/settings/profile', methods=['GET', 'POST'])
@login_required
def settings_profile():
    form = ProfileEditForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data or ''
        current_user.bio = form.bio.data or ''
        current_user.location = form.location.data or ''
        current_user.website = form.website.data or ''
        current_user.company = form.company.data or ''
        current_user.twitter = form.twitter.data or ''
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('settings_profile'))
    return render_template('settings_profile.html', form=form)


@app.route('/settings/password', methods=['GET', 'POST'])
@login_required
def settings_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password updated!', 'success')
            return redirect(url_for('settings_password'))
    return render_template('settings_password.html', form=form)


@app.route('/settings/delete', methods=['POST'])
@login_required
def settings_delete():
    user = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('index'))


@app.route('/settings')
@login_required
def settings():
    return redirect(url_for('settings_profile'))


# ─── Stars ───

@app.route('/stars')
@login_required
def my_stars():
    stars = Star.query.filter_by(user_id=current_user.id).join(Repository).order_by(
        Star.created_at.desc()).all()
    return render_template('stars.html', stars=stars)


# ─── Watching ───

@app.route('/watching')
@login_required
def my_watching():
    watches = Watch.query.filter_by(user_id=current_user.id).join(Repository).order_by(
        Watch.created_at.desc()).all()
    return render_template('watching.html', watches=watches)


@app.route('/<username>/watching')
def user_watching(username):
    user = User.query.filter_by(username=username).first_or_404()
    watches = Watch.query.filter_by(user_id=user.id).join(Repository).order_by(
        Watch.created_at.desc()).all()
    repos = user.repositories.filter_by(is_public=True).order_by(
        Repository.stars_count.desc()).limit(20).all()
    starred = Star.query.filter_by(user_id=user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(20).all()
    return render_template('user_profile.html', profile_user=user, repos=repos,
                           starred=starred, tab='watching', watches=watches)


# ─── Form-based POST routes (replaces AJAX for agent compatibility) ───

@app.route('/star/toggle/<int:repo_id>', methods=['POST'])
@login_required
def star_toggle_form(repo_id):
    """Form-POST version of star toggle — works in CDP-controlled browsers."""
    repo = db.session.get(Repository, repo_id)
    if not repo:
        abort(404)
    existing = Star.query.filter_by(user_id=current_user.id, repo_id=repo_id).first()
    if existing:
        db.session.delete(existing)
        repo.stars_count = max(0, repo.stars_count - 1)
    else:
        star = Star(user_id=current_user.id, repo_id=repo_id)
        db.session.add(star)
        repo.stars_count += 1
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or url_for('repo_detail',
               username=repo.full_name.split('/')[0], reponame=repo.name)
    return redirect(next_url)


@app.route('/watch/toggle/<int:repo_id>', methods=['POST'])
@login_required
def watch_toggle_form(repo_id):
    """Form-POST version of watch toggle."""
    repo = db.session.get(Repository, repo_id)
    if not repo:
        abort(404)
    existing = Watch.query.filter_by(user_id=current_user.id, repo_id=repo_id).first()
    if existing:
        db.session.delete(existing)
        repo.watchers_count = max(0, repo.watchers_count - 1)
    else:
        watch = Watch(user_id=current_user.id, repo_id=repo_id)
        db.session.add(watch)
        repo.watchers_count += 1
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or url_for('repo_detail',
               username=repo.full_name.split('/')[0], reponame=repo.name)
    return redirect(next_url)


@app.route('/follow/toggle/<int:user_id>', methods=['POST'])
@login_required
def follow_toggle_form(user_id):
    """Form-POST version of follow toggle."""
    target = db.session.get(User, user_id)
    if not target or target.id == current_user.id:
        abort(400)
    if current_user.is_following(target):
        current_user.following.remove(target)
    else:
        current_user.following.append(target)
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or url_for('user_profile',
               username=target.username)
    return redirect(next_url)


@app.route('/fork/<int:repo_id>', methods=['POST'])
@login_required
def fork_form(repo_id):
    """Form-POST version of fork."""
    repo = db.session.get(Repository, repo_id)
    if not repo or not repo.is_public:
        abort(404)
    fork_name = f"{current_user.username}/{repo.name}"
    existing = Repository.query.filter_by(full_name=fork_name).first()
    if existing:
        flash('You already have a fork of this repository.', 'info')
        return redirect(url_for('repo_detail', username=current_user.username,
                                reponame=repo.name))
    fork = Repository(
        owner_id=current_user.id,
        name=repo.name,
        full_name=fork_name,
        description=repo.description,
        language=repo.language,
        license=repo.license,
        is_public=True,
        is_fork=True,
        readme=repo.readme,
        topics_text=repo.topics_text,
        gallery_json=repo.gallery_json,
    )
    db.session.add(fork)
    repo.forks_count += 1
    db.session.commit()
    flash(f'Forked to {fork_name}!', 'success')
    return redirect(url_for('repo_detail', username=current_user.username,
                            reponame=repo.name))


# ─── Search (scored relevance, filters, sort) ───

STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
             'and', 'or', 'is', 'are', 'be', 'by', 'from', 'as', 'that', 'this',
             'about', 'repository', 'repo', 'project', 'projects', 'open',
             'source', 'opensource', 'on', 'github', 'related', 'find',
             'search', 'look', 'up', 'report', 'provide', 'tell'}


def _repo_haystack(r):
    return ' '.join([
        (r.full_name or '').lower(),
        (r.name or '').lower(),
        (r.description or '').lower(),
        (r.language or '').lower(),
        (r.topics_text or '').lower(),
        (r.readme or '').lower(),
    ])


def _score_repo(r, tokens):
    h = _repo_haystack(r)
    return sum(1 for t in tokens if t in h)


def _parse_github_qualifiers(q):
    """Parse GitHub-style search qualifiers out of a query string.

    Recognized qualifiers (stripped from the returned ``cleaned_q``):
      language:X | lang:X | l:X
      stars:>=N | stars:>N | stars:<=N | stars:<N | stars:N..M | stars:N
      forks:>=N (same forms as stars)
      created:>YYYY-MM-DD | created:<YYYY-MM-DD | created:YYYY-MM-DD..YYYY-MM-DD
      pushed:>YYYY-MM-DD | pushed:<YYYY-MM-DD   (maps to updated_at)
      updated:>YYYY-MM-DD | updated:<YYYY-MM-DD (alias of pushed)
      sort:stars[-desc|-asc] | sort:updated | sort:forks | sort:created
      topic:X
      license:X
      type:repositories|users|topics    (stripped, handled elsewhere)
      is:public|archived|not-archived

    Returns: (cleaned_q, filters_dict)
      filters_dict may contain any of:
        language, min_stars, max_stars, min_forks,
        created_after, created_before, updated_after, updated_before,
        topic, license, sort, type, archived
    """
    filters = {}
    if not q:
        return '', filters

    def _apply_numeric(prefix, raw, filters, min_key, max_key):
        val = raw.strip()
        m = re.match(r'^>=?(-?\d+)$', val)
        if m:
            filters[min_key] = int(m.group(1)) + (0 if val.startswith('>=') else 1)
            return
        m = re.match(r'^<=?(-?\d+)$', val)
        if m:
            filters[max_key] = int(m.group(1)) - (0 if val.startswith('<=') else 1)
            return
        m = re.match(r'^(-?\d+)\.\.(-?\d+)$', val)
        if m:
            filters[min_key] = int(m.group(1))
            filters[max_key] = int(m.group(2))
            return
        m = re.match(r'^(-?\d+)$', val)
        if m:
            filters[min_key] = int(m.group(1))
            filters[max_key] = int(m.group(1))
            return

    def _apply_date(raw, filters, after_key, before_key):
        val = raw.strip()
        m = re.match(r'^>=?(\d{4}-\d{2}-\d{2})$', val)
        if m:
            filters[after_key] = m.group(1)
            return
        m = re.match(r'^<=?(\d{4}-\d{2}-\d{2})$', val)
        if m:
            filters[before_key] = m.group(1)
            return
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$', val)
        if m:
            filters[after_key] = m.group(1)
            filters[before_key] = m.group(2)
            return
        m = re.match(r'^(\d{4}-\d{2}-\d{2})$', val)
        if m:
            filters[after_key] = m.group(1)
            filters[before_key] = m.group(1)
            return

    tokens = q.split()
    kept = []
    for tok in tokens:
        low = tok.lower()
        if ':' not in low:
            kept.append(tok)
            continue
        key, _, val = tok.partition(':')
        key = key.lower()
        if not val:
            kept.append(tok)
            continue
        if key in ('language', 'lang', 'l'):
            filters['language'] = val.strip('"').strip("'")
        elif key == 'stars':
            _apply_numeric('stars', val, filters, 'min_stars', 'max_stars')
        elif key == 'forks':
            _apply_numeric('forks', val, filters, 'min_forks', 'max_forks')
        elif key == 'created':
            _apply_date(val, filters, 'created_after', 'created_before')
        elif key in ('pushed', 'updated'):
            _apply_date(val, filters, 'updated_after', 'updated_before')
        elif key == 'topic':
            filters['topic'] = val.strip('"').strip("'")
        elif key == 'license':
            filters['license'] = val.strip('"').strip("'")
        elif key == 'sort':
            filters['sort'] = val.strip('"').strip("'").lower()
        elif key == 'type':
            filters['type'] = val.strip('"').strip("'").lower()
        elif key == 'is':
            v = val.strip('"').strip("'").lower()
            if v == 'archived':
                filters['archived'] = '1'
            elif v in ('not-archived', 'notarchived'):
                filters['archived'] = '0'
            elif v == 'public':
                pass  # default
        else:
            # Unrecognized qualifier: drop the key but keep the value as a
            # search term so we don't miss it entirely.
            kept.append(val)
    cleaned_q = ' '.join(kept).strip()
    return cleaned_q, filters


def _apply_repo_filters(query_obj, extra=None):
    """Apply request.args filters (plus optional extra filters parsed from
    GitHub-style qualifiers in the q string) to a Repository query."""
    extra = extra or {}

    def _arg(name, default=''):
        if name in extra:
            return extra[name]
        return request.args.get(name, default)

    def _arg_int(name):
        if name in extra:
            try:
                return int(extra[name])
            except (TypeError, ValueError):
                return None
        return request.args.get(name, type=int)

    lang = (extra.get('language') or request.args.get('language', '').strip()
            or request.args.get('l', '').strip())
    if lang:
        query_obj = query_obj.filter(Repository.language.ilike(lang))

    min_stars = _arg_int('min_stars')
    if min_stars is not None:
        query_obj = query_obj.filter(Repository.stars_count >= min_stars)

    max_stars = _arg_int('max_stars')
    if max_stars is not None:
        query_obj = query_obj.filter(Repository.stars_count <= max_stars)

    min_forks = _arg_int('min_forks')
    if min_forks is not None:
        query_obj = query_obj.filter(Repository.forks_count >= min_forks)

    max_forks = _arg_int('max_forks')
    if max_forks is not None:
        query_obj = query_obj.filter(Repository.forks_count <= max_forks)

    license_f = (extra.get('license') or request.args.get('license', '').strip())
    if license_f:
        query_obj = query_obj.filter(Repository.license.ilike(f'%{license_f}%'))

    topic_f = (extra.get('topic') or request.args.get('topic', '').strip())
    if topic_f:
        query_obj = query_obj.filter(Repository.topics_text.ilike(f'%"{topic_f}"%'))

    # Updated within N days
    updated_days = request.args.get('updated_days', type=int)
    if updated_days is not None:
        cutoff = mirror_now() - timedelta(days=updated_days)
        query_obj = query_obj.filter(Repository.updated_at >= cutoff)

    # Created in last N days
    created_days = request.args.get('created_days', type=int)
    if created_days is not None:
        cutoff = mirror_now() - timedelta(days=created_days)
        query_obj = query_obj.filter(Repository.created_at >= cutoff)

    # Created after date (YYYY-MM-DD)
    created_after = (extra.get('created_after') or
                     request.args.get('created_after', '').strip())
    if created_after:
        try:
            dt = datetime.strptime(created_after, '%Y-%m-%d')
            query_obj = query_obj.filter(Repository.created_at >= dt)
        except ValueError:
            pass
    created_before = (extra.get('created_before') or
                      request.args.get('created_before', '').strip())
    if created_before:
        try:
            dt = datetime.strptime(created_before, '%Y-%m-%d')
            query_obj = query_obj.filter(Repository.created_at <= dt)
        except ValueError:
            pass

    # updated_after / updated_before (from pushed: or updated: qualifier)
    updated_after = (extra.get('updated_after') or
                     request.args.get('updated_after', '').strip())
    if updated_after:
        try:
            dt = datetime.strptime(updated_after, '%Y-%m-%d')
            query_obj = query_obj.filter(Repository.updated_at >= dt)
        except ValueError:
            pass
    updated_before = (extra.get('updated_before') or
                      request.args.get('updated_before', '').strip())
    if updated_before:
        try:
            dt = datetime.strptime(updated_before, '%Y-%m-%d')
            query_obj = query_obj.filter(Repository.updated_at <= dt)
        except ValueError:
            pass

    if request.args.get('has_readme') == '1':
        query_obj = query_obj.filter(Repository.has_readme == True)
    if request.args.get('has_wiki') == '1':
        query_obj = query_obj.filter(Repository.has_wiki == True)
    archived_flag = extra.get('archived', request.args.get('archived'))
    if archived_flag == '1':
        query_obj = query_obj.filter(Repository.is_archived == True)
    if archived_flag == '0':
        query_obj = query_obj.filter(Repository.is_archived == False)

    owner_type = request.args.get('owner_type', '').strip()
    if owner_type:
        query_obj = query_obj.filter(Repository.owner_type == owner_type)

    return query_obj


def _apply_repo_sort(results, sort_key):
    if sort_key in ('best-match', 'best_match'):
        return results
    if sort_key in ('stars', 'stars_desc'):
        return sorted(results, key=lambda r: r.stars_count, reverse=True)
    if sort_key == 'stars_asc':
        return sorted(results, key=lambda r: r.stars_count)
    if sort_key in ('forks', 'forks_desc'):
        return sorted(results, key=lambda r: r.forks_count, reverse=True)
    if sort_key == 'forks_asc':
        return sorted(results, key=lambda r: r.forks_count)
    if sort_key in ('updated', 'updated_desc', 'recent', 'newest'):
        return sorted(results, key=lambda r: r.updated_at or datetime.min, reverse=True)
    if sort_key == 'updated_asc':
        return sorted(results, key=lambda r: r.updated_at or datetime.max)
    if sort_key in ('created', 'created_desc'):
        return sorted(results, key=lambda r: r.created_at or datetime.min, reverse=True)
    if sort_key == 'created_asc':
        return sorted(results, key=lambda r: r.created_at or datetime.max)
    return sorted(results, key=lambda r: r.stars_count, reverse=True)


@app.route('/search')
def search():
    raw_q = request.args.get('q', '').strip()
    # Parse GitHub-style qualifiers (language:python, stars:>=100,
    # created:>2024-01-01, pushed:>2024-01-01, sort:stars-desc, type:...)
    # from the raw q string before scoring.
    q, parsed = _parse_github_qualifiers(raw_q)
    # type: qualifier overrides URL param if present
    search_type = parsed.get('type') or request.args.get('type', 'repositories')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    repos = None
    users = None
    topic_results = None
    total = 0

    if search_type in ('repositories', ''):
        base = Repository.query.filter_by(is_public=True)
        base = _apply_repo_filters(base, extra=parsed)
        candidates = base.all()
        if q:
            tokens = [t.lower() for t in re.findall(r'[a-z0-9][\w-]*', q.lower())
                      if t and t not in STOPWORDS and len(t) >= 2]
            if tokens:
                # Require at least half of the meaningful tokens match so
                # that multi-word searches like "climate change data visualization"
                # don't return every repo that happens to contain a common word.
                if len(tokens) >= 4:
                    min_required = max(2, (len(tokens) + 1) // 2)
                elif len(tokens) >= 2:
                    min_required = 2
                else:
                    min_required = 1
                scored = []
                for r in candidates:
                    s = _score_repo(r, tokens)
                    if s >= min_required:
                        scored.append((s, r))
                scored.sort(key=lambda x: (-x[0], -x[1].stars_count))
                results = [r for _, r in scored]
            else:
                results = candidates
        else:
            results = candidates
        # sort: qualifier from q takes precedence; normalize
        # "stars-desc" / "stars_desc" / "stars" to the keys _apply_repo_sort
        # understands. Also accept GitHub's native `s=` / `o=` parameters
        # (stars+desc, updated, forks, etc.) that agents type directly.
        sort_key = parsed.get('sort') or request.args.get('sort', '') or \
                   request.args.get('s', 'best-match')
        order = (request.args.get('o', '') or '').lower()
        sort_key = sort_key.replace('-', '_').lower()
        if order == 'asc' and sort_key in ('stars', 'forks', 'updated', 'created'):
            sort_key = f'{sort_key}_asc'
        results = _apply_repo_sort(results, sort_key)
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        page_items = results[start:end]
        repos = _PaginatedList(page_items, page=page, per_page=per_page, total=total)
    elif search_type == 'users' and q:
        users = User.query.filter(
            or_(User.username.ilike(f'%{q}%'), User.name.ilike(f'%{q}%'))
        ).paginate(page=page, per_page=per_page, error_out=False)
        total = users.total if users else 0
    elif search_type == 'topics' and q:
        topic_results = Topic.query.filter(
            or_(Topic.slug.ilike(f'%{q}%'), Topic.display_name.ilike(f'%{q}%'))
        ).paginate(page=page, per_page=per_page, error_out=False)
        total = topic_results.total if topic_results else 0

    # Build facets from the SAME filtered + text-scored set as `results`, but
    # drop the filter being faceted (so users can still switch values).
    # Previously this used Repository.query.filter_by(is_public=True) which
    # returned global counts — agents saw "Rust (21)" next to a decision-tree
    # search that only had 1 real Rust hit.
    from collections import Counter as _Counter

    if search_type in ('repositories', ''):
        # Pull URL-level params we need to optionally skip, so we can match
        # the text query + all OTHER filters without re-invoking the request-
        # coupled _apply_repo_filters helper.
        _url_lang = (request.args.get('language', '').strip()
                     or request.args.get('l', '').strip())
        _url_license = request.args.get('license', '').strip()
        _url_min_stars = request.args.get('min_stars', type=int)
        _url_max_stars = request.args.get('max_stars', type=int)
        _url_min_forks = request.args.get('min_forks', type=int)
        _url_max_forks = request.args.get('max_forks', type=int)
        _url_topic = request.args.get('topic', '').strip()
        _parsed_lang = parsed.get('language', '')
        _parsed_license = parsed.get('license', '')
        _parsed_topic = parsed.get('topic', '')

        def _facet_pool(skip_key):
            # Fetch all public repos, then apply filters in Python — skipping
            # the key we want to enumerate over.
            pool = Repository.query.filter_by(is_public=True).all()
            eff_lang = '' if skip_key == 'language' else (_parsed_lang or _url_lang)
            eff_license = '' if skip_key == 'license' else (_parsed_license or _url_license)
            eff_topic = _parsed_topic or _url_topic

            def _keep(r):
                if eff_lang and (r.language or '').lower() != eff_lang.lower():
                    return False
                if eff_license and eff_license.lower() not in (r.license or '').lower():
                    return False
                if _url_min_stars is not None and r.stars_count < _url_min_stars:
                    return False
                if _url_max_stars is not None and r.stars_count > _url_max_stars:
                    return False
                if _url_min_forks is not None and r.forks_count < _url_min_forks:
                    return False
                if _url_max_forks is not None and r.forks_count > _url_max_forks:
                    return False
                if eff_topic and f'"{eff_topic}"' not in (r.topics_text or ''):
                    return False
                return True

            cands = [r for r in pool if _keep(r)]
            # Apply the same text-query scoring as the results set.
            if q:
                tokens_f = [t.lower() for t in re.findall(r'[a-z0-9][\w-]*', q.lower())
                            if t and t not in STOPWORDS and len(t) >= 2]
                if tokens_f:
                    if len(tokens_f) >= 4:
                        min_req = max(2, (len(tokens_f) + 1) // 2)
                    elif len(tokens_f) >= 2:
                        min_req = 2
                    else:
                        min_req = 1
                    cands = [r for r in cands if _score_repo(r, tokens_f) >= min_req]
            return cands

        lang_pool = _facet_pool('language')
        lang_counter = _Counter(r.language for r in lang_pool if r.language)
        language_facets = lang_counter.most_common(12)

        lic_pool = _facet_pool('license')
        lic_counter = _Counter(r.license for r in lic_pool if r.license)
        license_facets = lic_counter.most_common(8)
    else:
        language_facets = []
        license_facets = []

    sort_key_out = (parsed.get('sort') or request.args.get('sort', '')
                    or request.args.get('s', 'best-match'))
    current_lang = parsed.get('language') or request.args.get('l', '')

    return render_template('search.html', q=raw_q or q, search_type=search_type,
                           repos=repos, users=users, topics=topic_results,
                           total=total, page=page,
                           language_facets=language_facets,
                           license_facets=license_facets,
                           current_sort=sort_key_out,
                           current_lang=current_lang)


class _PaginatedList:
    """Lightweight pagination shim for in-memory result lists."""

    def __init__(self, items, page=1, per_page=20, total=0):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, (total + per_page - 1) // per_page)
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1


# ─── Notifications ───

@app.route('/notifications')
@login_required
def notifications():
    # Demo notifications based on user's starred repos
    stars = Star.query.filter_by(user_id=current_user.id).join(Repository).order_by(
        Star.created_at.desc()).limit(5).all()
    return render_template('notifications.html', stars=stars)


# ─── API Routes ───

@csrf.exempt
@app.route('/api/star/toggle', methods=['POST'])
@login_required
def api_star_toggle():
    data = request.get_json()
    repo_id = data.get('repo_id')
    repo = db.session.get(Repository, repo_id)
    if not repo:
        return jsonify({'error': 'Repo not found'}), 404
    existing = Star.query.filter_by(user_id=current_user.id, repo_id=repo_id).first()
    if existing:
        db.session.delete(existing)
        repo.stars_count = max(0, repo.stars_count - 1)
        starred = False
    else:
        star = Star(user_id=current_user.id, repo_id=repo_id)
        db.session.add(star)
        repo.stars_count += 1
        starred = True
    db.session.commit()
    return jsonify({'success': True, 'starred': starred, 'stars_count': repo.stars_count})


@csrf.exempt
@app.route('/api/watch/toggle', methods=['POST'])
@login_required
def api_watch_toggle():
    data = request.get_json()
    repo_id = data.get('repo_id')
    repo = db.session.get(Repository, repo_id)
    if not repo:
        return jsonify({'error': 'Repo not found'}), 404
    existing = Watch.query.filter_by(user_id=current_user.id, repo_id=repo_id).first()
    if existing:
        db.session.delete(existing)
        repo.watchers_count = max(0, repo.watchers_count - 1)
        watching = False
    else:
        watch = Watch(user_id=current_user.id, repo_id=repo_id)
        db.session.add(watch)
        repo.watchers_count += 1
        watching = True
    db.session.commit()
    return jsonify({'success': True, 'watching': watching, 'watchers_count': repo.watchers_count})


@csrf.exempt
@app.route('/api/follow/toggle', methods=['POST'])
@login_required
def api_follow_toggle():
    data = request.get_json()
    user_id = data.get('user_id')
    target = db.session.get(User, user_id)
    if not target or target.id == current_user.id:
        return jsonify({'error': 'Invalid user'}), 400
    if current_user.is_following(target):
        current_user.following.remove(target)
        following = False
    else:
        current_user.following.append(target)
        following = True
    db.session.commit()
    return jsonify({'success': True, 'following': following,
                    'followers_count': target.followers_count})


@csrf.exempt
@app.route('/api/fork/<int:repo_id>', methods=['POST'])
@login_required
def api_fork(repo_id):
    repo = db.session.get(Repository, repo_id)
    if not repo or not repo.is_public:
        return jsonify({'error': 'Repo not found'}), 404
    fork_name = f"{current_user.username}/{repo.name}"
    existing = Repository.query.filter_by(full_name=fork_name).first()
    if existing:
        return jsonify({'success': False, 'message': 'You already have a fork of this repo',
                        'redirect': url_for('repo_detail', username=current_user.username,
                                            reponame=repo.name)})
    fork = Repository(
        owner_id=current_user.id,
        name=repo.name,
        full_name=fork_name,
        description=repo.description,
        language=repo.language,
        license=repo.license,
        is_public=True,
        is_fork=True,
        readme=repo.readme,
        topics_text=repo.topics_text,
        gallery_json=repo.gallery_json,
    )
    db.session.add(fork)
    repo.forks_count += 1
    db.session.commit()
    return jsonify({'success': True, 'message': f'Forked to {fork_name}',
                    'redirect': url_for('repo_detail', username=current_user.username,
                                        reponame=repo.name)})


@app.route('/api/repos')
def api_repos():
    lang = request.args.get('language', '')
    query = Repository.query.filter_by(is_public=True)
    if lang:
        query = query.filter_by(language=lang)
    repos = query.order_by(Repository.stars_count.desc()).limit(20).all()
    return jsonify([{
        'id': r.id, 'full_name': r.full_name, 'description': r.description,
        'language': r.language, 'stars': r.stars_count, 'forks': r.forks_count,
    } for r in repos])


# ─── Error Handlers ───

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ─────────────────────────── Main ───────────────────────────

def seed_benchmark_users():
    """Idempotent: add 4 benchmark users with stars, watches, issues, follows.
    Call after seed_database() — requires repos to already exist.
    """
    if User.query.filter_by(email='alice.j@test.com').first():
        return  # already seeded

    benchmark_users_data = [
        ("alice_j", "alice.j@test.com", "Alice Johnson",
         "Full-stack developer and open source enthusiast.", "Austin, TX",
         "https://alicejohnson.dev", "OpenDev Inc", "alice_codes", "free"),
        ("bob_c", "bob.c@test.com", "Bob Chen",
         "Machine learning engineer. Python lover.", "Seattle, WA",
         "", "DataSci Co", "bob_ml", "free"),
        ("carol_d", "carol.d@test.com", "Carol Diaz",
         "Frontend developer. React & Vue enthusiast.", "New York, NY",
         "https://caroldiaz.io", "PixelCraft", "carol_dev", "free"),
        ("david_k", "david.k@test.com", "David Kim",
         "Rust and systems programming. Performance obsessed.", "San Francisco, CA",
         "", "RustSystems LLC", "david_rust", "team"),
    ]

    new_users = []
    for i, (uname, email, name, bio, loc, web, company, twitter, plan) in enumerate(benchmark_users_data):
        u = User(username=uname, email=email, name=name, bio=bio,
                 location=loc, website=web, company=company, twitter=twitter, plan=plan)
        u.set_password("TestPass123!")
        u.avatar = f"/static/images/avatars/avatar_{(i % 15):02d}.jpg"
        db.session.add(u)
        new_users.append(u)

    db.session.flush()

    # Helper to get repo by full_name
    def _get_repo(full_name):
        return Repository.query.filter_by(full_name=full_name).first()

    # Helper to add a star (idempotent)
    def _star(user, repo):
        if repo and not Star.query.filter_by(user_id=user.id, repo_id=repo.id).first():
            db.session.add(Star(user_id=user.id, repo_id=repo.id))
            repo.stars_count += 1

    # Helper to add a watch (idempotent)
    def _watch(user, repo):
        if repo and not Watch.query.filter_by(user_id=user.id, repo_id=repo.id).first():
            db.session.add(Watch(user_id=user.id, repo_id=repo.id))
            repo.watchers_count += 1

    alice, bob, carol, david = new_users

    # ── Alice: full-stack dev, stars JS/Python repos ──
    for fn in ['facebook/react', 'vuejs/vue', 'vercel/next.js',
               'tensorflow/tensorflow', 'django/django', 'pallets/flask',
               'tiangolo/fastapi']:
        _star(alice, _get_repo(fn))
    for fn in ['facebook/react', 'vuejs/vue', 'django/django']:
        _watch(alice, _get_repo(fn))

    # ── Bob: ML engineer, stars ML/AI repos ──
    for fn in ['tensorflow/tensorflow', 'huggingface/transformers',
               'langchain-ai/langchain', 'microsoft/vscode', 'facebook/react']:
        _star(bob, _get_repo(fn))
    for fn in ['tensorflow/tensorflow', 'huggingface/transformers', 'langchain-ai/langchain']:
        _watch(bob, _get_repo(fn))

    # ── Carol: frontend dev, stars JS frameworks ──
    for fn in ['facebook/react', 'vuejs/vue', 'vercel/next.js',
               'sveltejs/svelte', 'angular/angular', 'expressjs/express', 'nodejs/node']:
        _star(carol, _get_repo(fn))
    for fn in ['facebook/react', 'sveltejs/svelte', 'angular/angular']:
        _watch(carol, _get_repo(fn))

    # ── David: systems/Rust dev, stars Rust/Go/C++ repos ──
    for fn in ['rust-lang/rust', 'golang/go', 'torvalds/linux',
               'kubernetes/kubernetes', 'microsoft/vscode', 'tiangolo/fastapi']:
        _star(david, _get_repo(fn))
    for fn in ['rust-lang/rust', 'golang/go', 'kubernetes/kubernetes']:
        _watch(david, _get_repo(fn))

    db.session.flush()

    # ── Follows ──
    def _get_user(username):
        return User.query.filter_by(username=username).first()

    # Alice follows: gaearon, yyx990803, torvalds, bob, carol
    for uname in ['gaearon', 'yyx990803', 'torvalds']:
        t = _get_user(uname)
        if t and not alice.is_following(t):
            alice.following.append(t)
    for t in [bob, carol]:
        if not alice.is_following(t):
            alice.following.append(t)

    # Bob follows: gvanrossum, torvalds, alice, david
    for uname in ['gvanrossum', 'torvalds']:
        t = _get_user(uname)
        if t and not bob.is_following(t):
            bob.following.append(t)
    for t in [alice, david]:
        if not bob.is_following(t):
            bob.following.append(t)

    # Carol follows: gaearon, yyx990803, alice, bob
    for uname in ['gaearon', 'yyx990803']:
        t = _get_user(uname)
        if t and not carol.is_following(t):
            carol.following.append(t)
    for t in [alice, bob]:
        if not carol.is_following(t):
            carol.following.append(t)

    # David follows: torvalds, mitchellh, antirez, alice
    for uname in ['torvalds', 'mitchellh', 'antirez']:
        t = _get_user(uname)
        if t and not david.is_following(t):
            david.following.append(t)
    if not david.is_following(alice):
        david.following.append(alice)

    db.session.flush()

    # ── Seed Issues filed by benchmark users ──
    def _add_issue(repo_fn, author, title, body, status='open', labels=None):
        repo = _get_repo(repo_fn)
        if not repo:
            return
        next_num = (repo.issues.count() or 0) + 1
        issue = Issue(
            repo_id=repo.id,
            author_id=author.id,
            number=next_num,
            title=title,
            body=body or '',
            status=status,
            labels_json=json.dumps(labels or []),
        )
        db.session.add(issue)
        if status == 'open':
            repo.open_issues_count = (repo.open_issues_count or 0) + 1

    # Alice
    _add_issue('facebook/react', alice,
               'useState hook causes unexpected re-render on complex state updates',
               'When using useState with nested objects, the component re-renders even when '
               'values are deeply equal. Causes performance degradation in large lists.',
               labels=['bug', 'hooks'])
    _add_issue('django/django', alice,
               'ORM query optimization for many-to-many with prefetch_related',
               'Using prefetch_related with annotated querysets generates N+1 queries '
               'in some edge cases. Please add documentation or optimize.',
               labels=['performance', 'documentation'])

    # Bob
    _add_issue('tensorflow/tensorflow', bob,
               'GPU memory leak when using tf.data with large datasets',
               'Observed increasing GPU memory usage over epochs when using tf.data pipeline '
               'with map() and batch() on datasets > 100GB.',
               labels=['bug', 'gpu', 'memory'])
    _add_issue('huggingface/transformers', bob,
               'Add support for streaming inference in pipeline API',
               'The pipeline API buffers the entire output before returning. '
               'It would be useful to support streaming token generation for LLMs.',
               labels=['enhancement', 'feature-request'])

    # Carol
    _add_issue('vuejs/vue', carol,
               'v-model on custom components breaks with TypeScript strict mode',
               'When using v-model with TypeScript strict mode enabled, type inference '
               'fails for custom component props.',
               labels=['bug', 'typescript'])
    _add_issue('angular/angular', carol,
               'Router outlet flickers on route change with animations',
               'When using RouterOutlet with Angular animations, a brief flicker is visible '
               'during route transitions.',
               status='closed',
               labels=['bug', 'router', 'animations'])

    # David
    _add_issue('rust-lang/rust', david,
               'Lifetime elision rules unclear for async fn return types',
               'The compiler error messages for lifetime issues in async functions are not '
               'always clear about which lifetime rule is being violated.',
               labels=['documentation', 'async', 'lifetimes'])
    _add_issue('golang/go', david,
               'sync.Map performance regression in Go 1.22 under high contention',
               'Benchmarks show sync.Map read performance dropped ~15% in Go 1.22 vs 1.21 '
               'under high read contention.',
               labels=['bug', 'performance', 'sync'])

    db.session.commit()


def post_seed_tweaks():
    """Idempotent updates that run on every startup to keep WebVoyager-task
    coverage current even if seed_database() short-circuits because users
    already exist."""
    # Promote topics that frequently appear in WebVoyager tasks so they're
    # discoverable from the homepage / topics index.
    promote_slugs = ('image-processing', 'cybersecurity', 'web-scraping',
                     'security', 'nlp')
    changed = False
    for slug in promote_slugs:
        t = Topic.query.filter_by(slug=slug).first()
        if t and not t.is_featured:
            t.is_featured = True
            changed = True
    # Refresh repos_count so topic cards show real numbers.
    for t in Topic.query.all():
        c = len(t.repositories) if isinstance(t.repositories, list) else t.repositories.count()
        if t.repos_count != c:
            t.repos_count = c
            changed = True
    if changed:
        db.session.commit()


def create_app():
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
        post_seed_tweaks()
    return app


# Ensure DB schema + tweaks apply regardless of how app is launched (direct
# `app.run` vs `create_app()` entrypoint).
with app.app_context():
    try:
        db.create_all()
        seed_database()
        seed_benchmark_users()
        post_seed_tweaks()
    except Exception:
        # In case of stale schema, skip silently; routes remain available.
        db.session.rollback()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 28848))
    app.run(host='0.0.0.0', port=port, debug=False)
