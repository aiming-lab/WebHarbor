"""IMDb mirror — Flask app.

Phase 1 (clone-website) rewrite: real catalog data from Playwright scraping,
scored token-overlap search, four benchmark users with the canonical
WebHarbor email scheme (alice.j / bob.c / carol.d / david.k).

Mirrors the public, logged-out + logged-in browsing surface of imdb.com that
matters for web-agent benchmarks: title detail, name detail, search, charts
(Top 250 / Most Popular / Box Office), reviews, ratings, watchlist, news.
"""
import os
import json
import re
from datetime import datetime

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, desc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'imdb-mirror-dev-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'imdb.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to use this feature.'


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

title_genre = db.Table(
    'title_genre',
    db.Column('title_id', db.Integer, db.ForeignKey('titles.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True),
)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship('Review', backref='user', lazy=True,
                              cascade='all, delete-orphan')
    ratings = db.relationship('UserRating', backref='user', lazy=True,
                              cascade='all, delete-orphan')
    watchlist = db.relationship('WatchlistItem', backref='user', lazy=True,
                                cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Title(db.Model):
    __tablename__ = 'titles'
    id = db.Column(db.Integer, primary_key=True)
    tt_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title_type = db.Column(db.String(20), nullable=False, default='movie')
    primary_title = db.Column(db.String(255), nullable=False, index=True)
    original_title = db.Column(db.String(255), default='')
    year = db.Column(db.Integer, index=True)
    end_year = db.Column(db.Integer)
    runtime_min = db.Column(db.Integer)
    mpaa_rating = db.Column(db.String(10), default='')
    plot_short = db.Column(db.String(500), default='')
    plot = db.Column(db.Text, default='')
    rating_avg = db.Column(db.Float, default=0.0, index=True)
    num_votes = db.Column(db.Integer, default=0)
    metascore = db.Column(db.Integer)
    popularity_rank = db.Column(db.Integer, index=True)
    top_rank = db.Column(db.Integer, index=True)
    box_office_us = db.Column(db.BigInteger)
    box_office_world = db.Column(db.BigInteger)
    box_office_opening = db.Column(db.BigInteger)
    budget = db.Column(db.BigInteger)
    release_date = db.Column(db.String(20), default='')
    country = db.Column(db.String(80), default='')
    language = db.Column(db.String(80), default='')
    poster_path = db.Column(db.String(255), default='')
    taglines_json = db.Column(db.Text, default='[]')

    genres = db.relationship('Genre', secondary=title_genre, backref='titles',
                             lazy='joined')
    credits = db.relationship('Credit', backref='title', lazy=True,
                              cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='title', lazy=True,
                              cascade='all, delete-orphan')

    @property
    def directors(self):
        return [c for c in self.credits if c.role == 'director']

    @property
    def writers(self):
        return [c for c in self.credits if c.role == 'writer']

    @property
    def cast(self):
        return sorted([c for c in self.credits if c.role == 'actor'],
                      key=lambda c: c.billing_order or 999)

    def taglines(self):
        try:
            return json.loads(self.taglines_json or '[]')
        except Exception:
            return []

    @property
    def search_text(self):
        gnames = ' '.join(g.name for g in self.genres)
        people = ' '.join(c.person.name for c in self.credits[:8] if c.person)
        return ' '.join([
            self.primary_title, self.original_title or '',
            str(self.year or ''), gnames, people, self.plot_short or '',
        ]).lower()


class Person(db.Model):
    __tablename__ = 'persons'
    id = db.Column(db.Integer, primary_key=True)
    nm_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    birth_year = db.Column(db.Integer)
    death_year = db.Column(db.Integer)
    birth_place = db.Column(db.String(200), default='')
    bio = db.Column(db.Text, default='')
    primary_profession = db.Column(db.String(200), default='')
    photo_path = db.Column(db.String(255), default='')
    known_for_json = db.Column(db.Text, default='[]')

    credits = db.relationship('Credit', backref='person', lazy=True)

    def known_for(self):
        try:
            tt_ids = json.loads(self.known_for_json or '[]')
        except Exception:
            return []
        return Title.query.filter(Title.tt_id.in_(tt_ids)).all()


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)


class Credit(db.Model):
    __tablename__ = 'credits'
    id = db.Column(db.Integer, primary_key=True)
    title_id = db.Column(db.Integer, db.ForeignKey('titles.id'), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey('persons.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    character = db.Column(db.String(160), default='')
    billing_order = db.Column(db.Integer)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    title_id = db.Column(db.Integer, db.ForeignKey('titles.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer)
    headline = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    helpful_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_seed = db.Column(db.Boolean, default=False)


class UserRating(db.Model):
    __tablename__ = 'user_ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title_id = db.Column(db.Integer, db.ForeignKey('titles.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'title_id'),)


class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title_id = db.Column(db.Integer, db.ForeignKey('titles.id'), nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'title_id'),)


class NewsItem(db.Model):
    __tablename__ = 'news_items'
    id = db.Column(db.Integer, primary_key=True)
    headline = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, default='')
    source = db.Column(db.String(120), default='')
    published_at = db.Column(db.String(40), default='')
    category = db.Column(db.String(40), default='')
    related_tt = db.Column(db.String(20), default='')


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ---------------------------------------------------------------------------
# Scored token-overlap search (skill: NEVER strict AND)
# ---------------------------------------------------------------------------

STOP_WORDS = {
    'the','a','an','in','on','at','to','for','of','and','or','is','it','by',
    'with','this','that','from','about','into','as','be','are','was','were',
}


def _tokenize(q):
    return [t.lower() for t in re.split(r'\W+', q or '')
            if t and len(t) > 1 and t.lower() not in STOP_WORDS]


def scored_title_search(query, limit=50):
    toks = _tokenize(query)
    if not toks:
        return []
    rows = Title.query.all()
    hits = []
    for t in rows:
        text = t.search_text
        score = sum(1 for tk in toks if tk in text)
        if score:
            hits.append((score, -(t.num_votes or 0), t))
    hits.sort(key=lambda x: (-x[0], x[1]))
    return [h[2] for h in hits[:limit]]


def scored_person_search(query, limit=50):
    toks = _tokenize(query)
    if not toks:
        return []
    rows = Person.query.all()
    hits = []
    for p in rows:
        name_lc = p.name.lower()
        body = (' ' + (p.primary_profession or '') + ' ' +
                (p.birth_place or '') + ' ' + (p.bio or '')).lower()
        # Name matches weighted 10x; substring of full-name another +5.
        score = 0
        for tk in toks:
            if tk in name_lc:
                score += 10
            if tk in body:
                score += 1
        if all(tk in name_lc for tk in toks):
            score += 50  # exact full-name superiority
        if score:
            hits.append((score, name_lc, p))
    hits.sort(key=lambda x: (-x[0], x[1]))
    return [h[2] for h in hits[:limit]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_title_or_404(tt_id):
    t = Title.query.filter_by(tt_id=tt_id).first()
    if not t:
        abort(404)
    return t


def _get_person_or_404(nm_id):
    p = Person.query.filter_by(nm_id=nm_id).first()
    if not p:
        abort(404)
    return p


def _user_watchlist_ids():
    if not current_user.is_authenticated:
        return set()
    return {w.title_id for w in current_user.watchlist}


def _user_rating(title_id):
    if not current_user.is_authenticated:
        return None
    r = UserRating.query.filter_by(user_id=current_user.id, title_id=title_id).first()
    return r.rating if r else None


@app.context_processor
def inject_globals():
    return {
        'site_name': 'IMDb',
        'now_year': datetime.utcnow().year,
        'in_watchlist': _user_watchlist_ids(),
    }


@app.template_filter('money')
def fmt_money(v):
    if not v:
        return '—'
    if v >= 1_000_000_000:
        return f'${v/1_000_000_000:.1f}B'
    if v >= 1_000_000:
        return f'${v/1_000_000:.1f}M'
    if v >= 1_000:
        return f'${v/1_000:.1f}K'
    return f'${v}'


@app.template_filter('compact_votes')
def fmt_votes(v):
    if not v:
        return '0'
    if v >= 1_000_000:
        return f'{v/1_000_000:.1f}M'
    if v >= 1_000:
        return f'{v/1_000:.1f}K'
    return str(v)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    top_picks = (Title.query
                 .filter(Title.top_rank.isnot(None))
                 .order_by(Title.top_rank.asc())
                 .limit(10).all())
    trending = (Title.query
                .filter(Title.popularity_rank.isnot(None))
                .order_by(Title.popularity_rank.asc())
                .limit(8).all())
    in_theaters = (Title.query
                   .filter(Title.year.in_([2024, 2025, 2026]))
                   .order_by(desc(Title.year), desc(Title.rating_avg))
                   .limit(8).all())
    latest_news = NewsItem.query.order_by(desc(NewsItem.id)).limit(5).all()
    return render_template('index.html',
                           top_picks=top_picks,
                           trending=trending,
                           in_theaters=in_theaters,
                           latest_news=latest_news)


@app.route('/title/<tt_id>')
def title_detail(tt_id):
    t = _get_title_or_404(tt_id)
    cast = t.cast[:15]
    featured_reviews = (Review.query
                        .filter_by(title_id=t.id)
                        .order_by(desc(Review.is_seed), desc(Review.helpful_count))
                        .limit(3).all())
    similar = (Title.query
               .join(Title.genres)
               .filter(Genre.id.in_([g.id for g in t.genres]),
                       Title.id != t.id)
               .order_by(desc(Title.rating_avg))
               .limit(6).all())
    return render_template('title_detail.html', title=t, cast=cast,
                           featured_reviews=featured_reviews,
                           similar=similar,
                           user_rating=_user_rating(t.id))


@app.route('/title/<tt_id>/fullcredits')
def title_fullcredits(tt_id):
    t = _get_title_or_404(tt_id)
    return render_template('title_fullcredits.html', title=t)


@app.route('/title/<tt_id>/reviews')
def title_reviews(tt_id):
    t = _get_title_or_404(tt_id)
    sort = request.args.get('sort', 'helpful')
    q = Review.query.filter_by(title_id=t.id)
    if sort == 'recent':
        q = q.order_by(desc(Review.created_at))
    elif sort == 'rating':
        q = q.order_by(desc(Review.rating))
    else:
        q = q.order_by(desc(Review.helpful_count))
    return render_template('title_reviews.html', title=t,
                           reviews=q.all(), sort=sort)


@app.route('/title/<tt_id>/review', methods=['GET', 'POST'])
@login_required
def title_write_review(tt_id):
    t = _get_title_or_404(tt_id)
    if request.method == 'POST':
        headline = (request.form.get('headline') or '').strip()
        body = (request.form.get('body') or '').strip()
        rating = request.form.get('rating')
        if not headline or not body:
            flash('Headline and body are required.', 'error')
            return render_template('title_write_review.html', title=t)
        r = Review(title_id=t.id, user_id=current_user.id,
                   headline=headline[:160], body=body,
                   rating=int(rating) if rating else None)
        db.session.add(r)
        db.session.commit()
        flash('Review posted.', 'success')
        return redirect(url_for('title_reviews', tt_id=t.tt_id))
    return render_template('title_write_review.html', title=t)


@app.route('/title/<tt_id>/rate', methods=['POST'])
@login_required
def title_rate(tt_id):
    t = _get_title_or_404(tt_id)
    try:
        rating = int(request.form['rating'])
    except (KeyError, ValueError):
        flash('Invalid rating.', 'error')
        return redirect(url_for('title_detail', tt_id=t.tt_id))
    if not 1 <= rating <= 10:
        flash('Rating must be 1-10.', 'error')
        return redirect(url_for('title_detail', tt_id=t.tt_id))
    existing = UserRating.query.filter_by(user_id=current_user.id, title_id=t.id).first()
    if existing:
        existing.rating = rating
    else:
        db.session.add(UserRating(user_id=current_user.id, title_id=t.id, rating=rating))
    db.session.commit()
    flash(f'Rated {rating}/10.', 'success')
    return redirect(url_for('title_detail', tt_id=t.tt_id))


@app.route('/title/<tt_id>/watchlist', methods=['POST'])
@login_required
def title_watchlist_toggle(tt_id):
    t = _get_title_or_404(tt_id)
    existing = WatchlistItem.query.filter_by(user_id=current_user.id,
                                             title_id=t.id).first()
    if existing:
        db.session.delete(existing)
        flash('Removed from Watchlist.', 'info')
    else:
        db.session.add(WatchlistItem(user_id=current_user.id, title_id=t.id))
        flash('Added to Watchlist.', 'success')
    db.session.commit()
    return redirect(request.referrer or url_for('title_detail', tt_id=t.tt_id))


@app.route('/name/<nm_id>')
def name_detail(nm_id):
    p = _get_person_or_404(nm_id)
    grouped = {'director': [], 'writer': [], 'actor': [], 'producer': [], 'composer': []}
    for c in p.credits:
        grouped.setdefault(c.role, []).append(c)
    for k in grouped:
        grouped[k].sort(key=lambda c: -(c.title.year or 0))
    return render_template('name_detail.html', person=p, grouped=grouped,
                           known_for=p.known_for())


# Canonical IMDb search URL is /find?q= (URL realism, per WebHarbor doc).
# /search?q= remains as a WebHarbor convention alias.
@app.route('/find')
@app.route('/find/')
@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    kind = request.args.get('s', 'all')
    titles, people = [], []
    if q:
        if kind in ('all', 'tt'):
            titles = scored_title_search(q, limit=50)
        if kind in ('all', 'nm'):
            people = scored_person_search(q, limit=50)
    return render_template('search.html', q=q, kind=kind,
                           titles=titles, people=people)


@app.route('/search/title')
def advanced_title_search():
    q = request.args
    query = Title.query
    selected_genres = q.getlist('genre')
    title_type = q.get('title_type', '')
    year_from = q.get('year_from', type=int)
    year_to = q.get('year_to', type=int)
    rating_min = q.get('rating_min', type=float)
    sort = q.get('sort', 'popularity')
    if title_type:
        query = query.filter(Title.title_type == title_type)
    if year_from:
        query = query.filter(Title.year >= year_from)
    if year_to:
        query = query.filter(Title.year <= year_to)
    if rating_min:
        query = query.filter(Title.rating_avg >= rating_min)
    if selected_genres:
        query = (query.join(Title.genres)
                 .filter(Genre.slug.in_(selected_genres))
                 .group_by(Title.id)
                 .having(func.count(Genre.id) == len(selected_genres)))
    if sort == 'rating':
        query = query.order_by(desc(Title.rating_avg))
    elif sort == 'votes':
        query = query.order_by(desc(Title.num_votes))
    elif sort == 'year':
        query = query.order_by(desc(Title.year))
    elif sort == 'box_office':
        query = query.order_by(desc(Title.box_office_world))
    else:
        query = query.order_by(Title.popularity_rank.asc().nulls_last())
    results = query.limit(100).all()
    all_genres = Genre.query.order_by(Genre.name).all()
    return render_template('advanced_search.html',
                           results=results,
                           all_genres=all_genres,
                           selected_genres=selected_genres,
                           title_type=title_type,
                           year_from=year_from, year_to=year_to,
                           rating_min=rating_min, sort=sort)


@app.route('/chart/top')
def chart_top():
    titles = (Title.query
              .filter(Title.title_type == 'movie', Title.top_rank.isnot(None))
              .order_by(Title.top_rank.asc())
              .all())
    return render_template('chart.html', titles=titles,
                           chart_name='IMDb Top 250 Movies',
                           chart_slug='top',
                           description='As rated by regular IMDb voters.')


@app.route('/chart/toptv')
def chart_toptv():
    titles = (Title.query
              .filter(Title.title_type == 'tvSeries', Title.top_rank.isnot(None))
              .order_by(Title.top_rank.asc())
              .all())
    return render_template('chart.html', titles=titles,
                           chart_name='Top 250 TV Shows',
                           chart_slug='toptv',
                           description='Highest-rated TV series of all time.')


@app.route('/chart/moviemeter')
def chart_moviemeter():
    titles = (Title.query
              .filter(Title.popularity_rank.isnot(None))
              .order_by(Title.popularity_rank.asc())
              .limit(100).all())
    return render_template('chart.html', titles=titles,
                           chart_name='Most Popular Movies',
                           chart_slug='moviemeter',
                           description="IMDb users' most popular page views this week.")


@app.route('/chart/boxoffice')
def chart_boxoffice():
    titles = (Title.query
              .filter(Title.box_office_us.isnot(None))
              .order_by(desc(Title.box_office_us))
              .limit(50).all())
    return render_template('chart.html', titles=titles,
                           chart_name='Top Box Office (US)',
                           chart_slug='boxoffice',
                           description='Highest US domestic gross.')


@app.route('/genre/<slug>')
def genre_browse(slug):
    g = Genre.query.filter_by(slug=slug).first_or_404()
    titles = (Title.query.join(Title.genres)
              .filter(Genre.id == g.id)
              .order_by(desc(Title.rating_avg))
              .limit(60).all())
    return render_template('genre_browse.html', genre=g, titles=titles)


@app.route('/list/watchlist')
@login_required
def my_watchlist():
    items = (WatchlistItem.query
             .filter_by(user_id=current_user.id)
             .order_by(desc(WatchlistItem.added_at))
             .all())
    titles = [db.session.get(Title, w.title_id) for w in items]
    return render_template('watchlist.html', titles=titles)


@app.route('/list/ratings')
@login_required
def my_ratings():
    rs = (UserRating.query
          .filter_by(user_id=current_user.id)
          .order_by(desc(UserRating.created_at))
          .all())
    rows = [(r, db.session.get(Title, r.title_id)) for r in rs]
    return render_template('my_ratings.html', rows=rows)


@app.route('/news')
def news_list():
    items = NewsItem.query.order_by(desc(NewsItem.id)).all()
    return render_template('news.html', items=items)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        name = (request.form.get('name') or '').strip()
        pw = request.form.get('password') or ''
        if not email or not name or len(pw) < 6:
            flash('Email, name and a 6+ character password are required.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Account with that email already exists.', 'error')
            return render_template('register.html')
        u = User(email=email, name=name)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Welcome to IMDb.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        pw = request.form.get('password') or ''
        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(pw):
            flash('Invalid email or password.', 'error')
            return render_template('login.html')
        login_user(u)
        flash(f'Welcome back, {u.name}.', 'success')
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Signed out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    rating_count = UserRating.query.filter_by(user_id=current_user.id).count()
    watch_count = WatchlistItem.query.filter_by(user_id=current_user.id).count()
    return render_template('account.html',
                           review_count=review_count,
                           rating_count=rating_count,
                           watch_count=watch_count)


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.route('/_health')
def health():
    return jsonify({'ok': True, 'site': 'imdb',
                    'titles': Title.query.count(),
                    'persons': Person.query.count(),
                    'users': User.query.count()})


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap():
    with app.app_context():
        db.create_all()
        from seed_data import seed_all
        seed_all(db, Title, Person, Genre, Credit, Review, UserRating,
                 WatchlistItem, User, NewsItem)


_bootstrap()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
