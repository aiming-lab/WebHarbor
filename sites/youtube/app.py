import importlib.util
import json
import os
import re
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from sqlalchemy import or_
from wtforms import PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIRROR_REFERENCE_DATE = datetime(2024, 3, 1, 12, 0, 0)
MIRROR_REFERENCE_DATE_LABEL = MIRROR_REFERENCE_DATE.strftime('%B %-d, %Y')
BENCHMARK_USER_AVATAR_PATHS = {
    'alice.j@test.com': '/static/images/youtube/upstream/channels/c_067_avatar.jpg',
    'bob.c@test.com': '/static/images/youtube/upstream/channels/c_035_avatar.jpg',
    'carol.d@test.com': '/static/images/youtube/upstream/channels/c_010_avatar.jpg',
    'david.k@test.com': '/static/images/youtube/upstream/channels/c_007_avatar.jpg',
}


def mirror_now() -> datetime:
    return MIRROR_REFERENCE_DATE


def user_avatar_path(user: UserMixin | None) -> str:
    if not user or not getattr(user, 'email', None):
        return ''
    return BENCHMARK_USER_AVATAR_PATHS.get(user.email.lower(), '')


app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = 'webharbor-youtube-dev-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'youtube.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
csrf = CSRFProtect(app)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    handle = db.Column(db.String(80), unique=True, nullable=False, index=True)
    avatar_color = db.Column(db.String(20), default='#3ea6ff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship('Comment', backref='user', lazy=True, cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', backref='user', lazy=True, cascade='all, delete-orphan')
    watch_later_items = db.relationship('WatchLater', backref='user', lazy=True, cascade='all, delete-orphan')
    history_items = db.relationship('WatchHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    liked_videos = db.relationship('UserLike', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, raw: str):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def initials(self):
        parts = self.display_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.display_name[:2].upper()


class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), default='General')
    description = db.Column(db.Text, default='')
    subscriber_count = db.Column(db.Integer, default=0)
    avatar_path = db.Column(db.String(300), default='')
    banner_path = db.Column(db.String(300), default='')
    verified = db.Column(db.Boolean, default=False)
    accent_color = db.Column(db.String(20), default='#3ea6ff')

    videos = db.relationship('Video', backref='channel', lazy=True, cascade='all, delete-orphan')
    playlists = db.relationship('Playlist', backref='channel', lazy=True, cascade='all, delete-orphan')


class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(60), default='General')
    tags_json = db.Column(db.Text, default='[]')
    duration = db.Column(db.String(20), default='10:00')
    duration_seconds = db.Column(db.Integer, default=600)
    thumbnail_path = db.Column(db.String(300), default='')
    poster_path = db.Column(db.String(300), default='')
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime, default=mirror_now)
    is_trending = db.Column(db.Boolean, default=False)
    comments_enabled = db.Column(db.Boolean, default=True)

    comments = db.relationship('Comment', backref='video', lazy=True, cascade='all, delete-orphan')

    def get_tags(self):
        try:
            return json.loads(self.tags_json or '[]')
        except Exception:
            return []

    @property
    def relative_date(self):
        delta = mirror_now() - self.published_at
        if delta.days <= 0:
            hours = max(1, delta.seconds // 3600)
            return f'{hours} hours ago'
        if delta.days < 7:
            return f'{delta.days} days ago'
        if delta.days < 30:
            weeks = max(1, delta.days // 7)
            return f'{weeks} weeks ago'
        months = max(1, delta.days // 30)
        return f'{months} months ago'

    @property
    def view_label(self):
        if self.views >= 1_000_000:
            return f'{self.views / 1_000_000:.1f}M views'
        if self.views >= 1_000:
            return f'{self.views / 1_000:.0f}K views'
        return f'{self.views} views'


class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    is_public = db.Column(db.Boolean, default=True)

    items = db.relationship('PlaylistVideo', backref='playlist', lazy=True, cascade='all, delete-orphan')


class PlaylistVideo(db.Model):
    __tablename__ = 'playlist_videos'
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    position = db.Column(db.Integer, default=1)
    video = db.relationship('Video')


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    like_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    channel = db.relationship('Channel')


class WatchLater(db.Model):
    __tablename__ = 'watch_later'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    video = db.relationship('Video')


class WatchHistory(db.Model):
    __tablename__ = 'watch_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    video = db.relationship('Video')


class UserLike(db.Model):
    __tablename__ = 'user_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    video = db.relationship('Video')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    display_name = StringField('Display name', validators=[DataRequired(), Length(min=2, max=120)])
    handle = StringField('Handle', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password')])


class CommentForm(FlaskForm):
    body = TextAreaField('Comment', validators=[DataRequired(), Length(min=2, max=800)])


class SearchForm(FlaskForm):
    search_query = StringField('Search', validators=[Optional()])
    category = SelectField('Category', choices=[], validators=[Optional()])


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def slugify(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9]+', '-', value.lower()).strip('-')
    return value or 'item'


def score_video(video: Video, query: str) -> int:
    terms = [term for term in re.findall(r'[a-z0-9]+', query.lower()) if term]
    haystacks = [
        video.title.lower(),
        video.description.lower(),
        video.channel.name.lower(),
        ' '.join(video.get_tags()).lower(),
        video.category.lower(),
    ]
    score = 0
    for term in terms:
        if term in haystacks[0]:
            score += 8
        if any(term in haystack for haystack in haystacks[1:]):
            score += 4
    if video.is_trending:
        score += 2
    return score


def nav_categories():
    return ['All', 'Music', 'Gaming', 'Science', 'Technology', 'Cooking', 'Travel', 'Live', 'Podcasts']


@app.context_processor
def inject_globals():
    return {
        'mirror_reference_date_label': MIRROR_REFERENCE_DATE_LABEL,
        'mirror_now': mirror_now,
        'nav_categories': nav_categories(),
        'generate_csrf': generate_csrf,
        'user_avatar_path': user_avatar_path,
    }


@app.route('/')
def index():
    selected = request.args.get('category', 'All')
    query = Video.query.order_by(Video.is_trending.desc(), Video.views.desc())
    if selected and selected != 'All':
        query = query.filter_by(category=selected)
    videos = query.limit(18).all()
    trending = Video.query.filter_by(is_trending=True).order_by(Video.views.desc()).limit(6).all()
    return render_template('index.html', videos=videos, trending=trending, selected_category=selected)


@app.route('/results')
def results():
    search_query = (request.args.get('search_query') or '').strip()
    category = (request.args.get('category') or 'All').strip() or 'All'
    active_filter = (request.args.get('filter') or 'All').strip() or 'All'
    filter_options = ['All', 'Watched', 'Unwatched', 'Recently uploaded', 'Live']
    if active_filter not in filter_options:
        active_filter = 'All'
    videos = Video.query.options(db.joinedload(Video.channel)).all()
    if category != 'All':
        videos = [video for video in videos if video.category == category]
    if search_query:
        ranked = [(score_video(video, search_query), video) for video in videos]
        ranked = [pair for pair in ranked if pair[0] > 0]
        ranked.sort(key=lambda item: (item[0], item[1].views), reverse=True)
        videos = [video for _, video in ranked]
    else:
        videos.sort(key=lambda video: (video.is_trending, video.views), reverse=True)
    watched_ids = set()
    if current_user.is_authenticated:
        watched_ids = {
            item.video_id
            for item in WatchHistory.query.filter_by(user_id=current_user.id).all()
        }
    if active_filter == 'Watched':
        videos = [video for video in videos if video.id in watched_ids]
    elif active_filter == 'Unwatched':
        videos = [video for video in videos if video.id not in watched_ids]
    elif active_filter == 'Recently uploaded':
        videos = sorted(videos, key=lambda video: video.published_at, reverse=True)
    elif active_filter == 'Live':
        videos = [video for video in videos if 'live' in video.category.lower() or 'live' in video.title.lower()]
    return render_template(
        'results.html',
        videos=videos,
        search_query=search_query,
        selected_category=category,
        active_filter=active_filter,
        filter_options=filter_options,
    )


@app.route('/watch/<slug>', methods=['GET', 'POST'])
def watch(slug: str):
    video = Video.query.filter_by(slug=slug).first_or_404()
    form = CommentForm()
    if form.validate_on_submit() and current_user.is_authenticated and video.comments_enabled:
        comment = Comment(video_id=video.id, user_id=current_user.id, body=form.body.data.strip(), like_count=1)
        db.session.add(comment)
        video.comment_count += 1
        db.session.commit()
        flash('Comment added.', 'success')
        return redirect(url_for('watch', slug=slug))
    related = (Video.query.filter(Video.category == video.category, Video.id != video.id)
               .order_by(Video.views.desc()).limit(8).all())
    comments = Comment.query.filter_by(video_id=video.id).order_by(Comment.like_count.desc()).limit(20).all()
    in_watch_later = False
    liked = False
    subscribed = False
    if current_user.is_authenticated:
        in_watch_later = WatchLater.query.filter_by(user_id=current_user.id, video_id=video.id).first() is not None
        liked = UserLike.query.filter_by(user_id=current_user.id, video_id=video.id).first() is not None
        subscribed = Subscription.query.filter_by(user_id=current_user.id, channel_id=video.channel_id).first() is not None
        if WatchHistory.query.filter_by(user_id=current_user.id, video_id=video.id).first() is None:
            db.session.add(WatchHistory(user_id=current_user.id, video_id=video.id, watched_at=mirror_now()))
            db.session.commit()
    return render_template('watch.html', video=video, related=related, comments=comments, form=form,
                           in_watch_later=in_watch_later, liked=liked, subscribed=subscribed)


@app.route('/channel/<slug>')
def channel(slug: str):
    channel_obj = Channel.query.filter_by(slug=slug).first_or_404()
    active_tab = (request.args.get('tab') or 'home').strip().lower()
    if active_tab not in {'home', 'videos', 'playlists', 'about'}:
        active_tab = 'home'
    videos = Video.query.filter_by(channel_id=channel_obj.id).order_by(Video.views.desc()).all()
    playlists = Playlist.query.filter_by(channel_id=channel_obj.id).all()
    return render_template('channel.html', channel=channel_obj, videos=videos, playlists=playlists, active_tab=active_tab)


@app.route('/playlist/<slug>')
def playlist(slug: str):
    playlist_obj = Playlist.query.filter_by(slug=slug).first_or_404()
    items = PlaylistVideo.query.filter_by(playlist_id=playlist_obj.id).order_by(PlaylistVideo.position.asc()).all()
    return render_template('playlist.html', playlist=playlist_obj, items=items)


@app.route('/feed/trending')
def trending():
    videos = Video.query.filter_by(is_trending=True).order_by(Video.views.desc()).all()
    return render_template('feed_listing.html', title='Trending', subtitle='Popular videos right now.', videos=videos)


@app.route('/feed/subscriptions')
@login_required
def subscriptions_feed():
    channel_ids = [sub.channel_id for sub in Subscription.query.filter_by(user_id=current_user.id).all()]
    videos = []
    if channel_ids:
        videos = Video.query.filter(Video.channel_id.in_(channel_ids)).order_by(Video.published_at.desc()).all()
    return render_template('feed_listing.html', title='Subscriptions', subtitle='Fresh uploads from channels you follow.', videos=videos)


@app.route('/feed/history')
@login_required
def history_feed():
    items = WatchHistory.query.filter_by(user_id=current_user.id).order_by(WatchHistory.watched_at.desc()).all()
    videos = [item.video for item in items]
    return render_template('feed_listing.html', title='History', subtitle='Videos you have watched recently.', videos=videos)


@app.route('/feed/watch-later')
@login_required
def watch_later_feed():
    items = WatchLater.query.filter_by(user_id=current_user.id).order_by(WatchLater.added_at.desc()).all()
    videos = [item.video for item in items]
    return render_template('feed_listing.html', title='Watch Later', subtitle='Saved videos to watch later.', videos=videos)


@app.route('/feed/liked')
@login_required
def liked_feed():
    items = UserLike.query.filter_by(user_id=current_user.id).order_by(UserLike.created_at.desc()).all()
    videos = [item.video for item in items]
    return render_template('feed_listing.html', title='Liked Videos', subtitle='Videos you have liked on this account.', videos=videos)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        current_user.display_name = (request.form.get('display_name') or current_user.display_name).strip()
        current_user.handle = slugify((request.form.get('handle') or current_user.handle).strip())
        db.session.commit()
        flash('Account updated.', 'success')
        return redirect(url_for('account'))
    subscriptions = (Subscription.query.filter_by(user_id=current_user.id)
                     .join(Channel, Subscription.channel_id == Channel.id)
                     .order_by(Channel.name.asc())
                     .all())
    subscribed_channels = [subscription.channel for subscription in subscriptions]
    stats = {
        'subscriptions': len(subscribed_channels),
        'watch_later': WatchLater.query.filter_by(user_id=current_user.id).count(),
        'likes': UserLike.query.filter_by(user_id=current_user.id).count(),
        'history': WatchHistory.query.filter_by(user_id=current_user.id).count(),
        'comments': Comment.query.filter_by(user_id=current_user.id).count(),
    }
    return render_template('account.html', subscribed_channels=subscribed_channels, stats=stats)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Welcome back.', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        handle = slugify(form.handle.data)
        if User.query.filter(or_(User.email == form.email.data.lower().strip(), User.handle == handle)).first():
            flash('An account with that email or handle already exists.', 'error')
        else:
            user = User(email=form.email.data.lower().strip(), display_name=form.display_name.data.strip(), handle=handle)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Your channel account is ready.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Signed out.', 'success')
    return redirect(url_for('index'))


@app.route('/api/toggle-watch-later/<slug>', methods=['POST'])
@login_required
def toggle_watch_later(slug: str):
    video = Video.query.filter_by(slug=slug).first_or_404()
    existing = WatchLater.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    if existing:
        db.session.delete(existing)
        state = 'removed'
    else:
        db.session.add(WatchLater(user_id=current_user.id, video_id=video.id, added_at=mirror_now()))
        state = 'saved'
    db.session.commit()
    flash(f'Video {state} from Watch Later.', 'success')
    return redirect(request.referrer or url_for('watch', slug=slug))


@app.route('/api/toggle-like/<slug>', methods=['POST'])
@login_required
def toggle_like(slug: str):
    video = Video.query.filter_by(slug=slug).first_or_404()
    existing = UserLike.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    if existing:
        db.session.delete(existing)
        video.likes = max(0, video.likes - 1)
    else:
        db.session.add(UserLike(user_id=current_user.id, video_id=video.id, created_at=mirror_now()))
        video.likes += 1
    db.session.commit()
    return redirect(request.referrer or url_for('watch', slug=slug))


@app.route('/api/toggle-subscription/<slug>', methods=['POST'])
@login_required
def toggle_subscription(slug: str):
    channel_obj = Channel.query.filter_by(slug=slug).first_or_404()
    existing = Subscription.query.filter_by(user_id=current_user.id, channel_id=channel_obj.id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Subscription(user_id=current_user.id, channel_id=channel_obj.id, subscribed_at=mirror_now()))
    db.session.commit()
    return redirect(request.referrer or url_for('channel', slug=slug))


def load_seed_module():
    seed_path = os.path.join(BASE_DIR, 'seed_data.py')
    spec = importlib.util.spec_from_file_location('youtube_seed_data', seed_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


seed_module = load_seed_module()

with app.app_context():
    db.create_all()
    seed_module.seed_database(db, Channel, Video, Playlist, PlaylistVideo)
    seed_module.seed_benchmark_users(db, User, Subscription, WatchLater, WatchHistory, UserLike, Comment, Video, Channel)

@app.route('/_health')
def health():
    return {'ok': True, 'site': 'youtube', 'videos': Video.query.count(), 'channels': Channel.query.count()}

