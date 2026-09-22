import importlib.util
import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIRROR_REFERENCE_DATE = datetime(2024, 2, 15, 8, 0, 0)
MIRROR_REFERENCE_DATE_LABEL = MIRROR_REFERENCE_DATE.strftime('%B %-d, %Y')
EXPLORE_TOPICS = [
    {'key': 'top-stories', 'slug': 'top-stories', 'label': 'Top Stories'},
    {'key': 'el-nino', 'slug': 'el-nino', 'label': 'El Nino'},
    {'key': 'home-garden', 'slug': 'home-and-garden', 'label': 'Home & Garden'},
    {'key': 'allergies', 'slug': 'allergies', 'label': 'Allergies'},
    {'key': 'space', 'slug': 'space', 'label': 'Space'},
    {'key': 'product-guides', 'slug': 'product-guides', 'label': 'Product Guides'},
    {'key': 'animals', 'slug': 'animals', 'label': 'Animals'},
    {'key': 'travel', 'slug': 'travel', 'label': 'Travel'},
    {'key': 'bike', 'slug': 'bike', 'label': 'Bike'},
    {'key': 'seasonal', 'slug': 'seasonal', 'label': 'Seasonal'},
]
EXPLORE_TOPIC_CONTENT = {
    'top-stories': {
        'hero_title': 'A Super El Niño Is Increasingly Likely, And It Could Be Record Strong',
        'hero_description': "We’re trending toward El Niño, and by later this year, it could become one of the strongest on record.",
        'hero_image': '/static/images/weather/upstream/explore/el-nino__00.jpg',
        'items': [
            {'title': 'El Niño: What It Is And How It Can Affect Your Weather', 'description': 'You may have heard the term El Niño thrown around quite a bit, but what exactly does it mean?', 'duration': '0:50', 'image': '/static/images/weather/upstream/explore/el-nino__01.jpg'},
            {'title': 'Strong El Niño Years Can Bring May Hurricanes', 'description': 'In recent El Niño years, there has often been a named storm in May.', 'duration': '1:25', 'image': '/static/images/weather/upstream/explore/el-nino__02.png'},
            {'title': 'Why Does El Niño Affect Summer Weather Significantly Less Than Winter?', 'description': 'The summer before El Niño can feel like a regular summer.', 'duration': '', 'image': '/static/images/weather/upstream/explore/el-nino__03.jpg'},
        ],
    },
    'el-nino': {
        'hero_title': 'A Super El Niño Is Increasingly Likely, And It Could Be Record Strong',
        'hero_description': "We’re trending toward El Niño, and by later this year, it could become one of the strongest on record.",
        'hero_image': '/static/images/weather/upstream/explore/el-nino__00.jpg',
        'items': [
            {'title': 'El Niño: What It Is And How It Can Affect Your Weather', 'description': 'You may have heard the term El Niño thrown around quite a bit, but what exactly does it mean?', 'duration': '0:50', 'image': '/static/images/weather/upstream/explore/el-nino__01.jpg'},
            {'title': 'Strong El Niño Years Can Bring May Hurricanes', 'description': 'In recent El Niño years, there has often been a named storm in May.', 'duration': '1:25', 'image': '/static/images/weather/upstream/explore/el-nino__02.png'},
            {'title': 'Why Does El Niño Affect Summer Weather Significantly Less Than Winter?', 'description': 'The summer before El Niño can feel like a regular summer.', 'duration': '', 'image': '/static/images/weather/upstream/explore/el-nino__03.jpg'},
            {'title': "Eastern Pacific Hurricane Season Starts Friday. A Potential Super El Niño And A 'Wild Card' Could Boost It.", 'description': 'A strong El Niño could turbocharge the Eastern Pacific hurricane season.', 'duration': '', 'image': '/static/images/weather/upstream/explore/el-nino__04.png'},
        ],
    },
    'home-garden': {
        'hero_title': 'Farmer Shares the 5 Vegetables You Should Never Plant Together',
        'hero_description': "It's not about what you plant, but where you plant it.",
        'hero_image': '/static/images/weather/upstream/explore/home-and-garden__00.jpg',
        'items': [
            {'title': "Yelp's 2026 Home Trends: Smarter, stylish spaces for summer", 'description': 'Expect to see personality-driven homes with purpose.', 'duration': '', 'image': '/static/images/weather/upstream/explore/home-and-garden__01.jpg'},
            {'title': '10 Vegetables You Can Grow in Part Shade', 'description': "Here's how to maximize your harvest with limited sunlight.", 'duration': '', 'image': '/static/images/weather/upstream/explore/home-and-garden__02.jpg'},
            {'title': 'Aromatic Plants for a Home Garden Design', 'description': 'Easy-to-find scented plants for a romantic garden.', 'duration': '', 'image': '/static/images/weather/upstream/explore/home-and-garden__03.jpg'},
        ],
    },
    'allergies': {
        'hero_title': '5 Best Cities For Allergy Sufferers That Travelers Love',
        'hero_description': 'Top destination picks for travelers who want fewer allergy symptoms.',
        'hero_image': '/static/images/weather/upstream/explore/allergies__00.jpg',
        'items': [
            {'title': 'Allergy Season Grows Longer – Especially In These Places', 'description': 'Rising temperatures and shifting pollen windows are changing seasonal patterns.', 'duration': '', 'image': '/static/images/weather/upstream/explore/allergies__01.jpg'},
            {'title': 'Here’s How To Really Get Allergy Relief From Nasal Spray', 'description': 'Simple technique changes can make treatment far more effective.', 'duration': '', 'image': '/static/images/weather/upstream/explore/allergies__02.jpg'},
            {'title': 'The Worst European Summer Destinations For Allergy Sufferers', 'description': 'Some iconic summer routes can spike pollen and mold exposure.', 'duration': '', 'image': '/static/images/weather/upstream/explore/allergies__03.jpg'},
        ],
    },
    'space': {
        'hero_title': 'Lightning From Space? Storm Over Kansas Caught in Orbit',
        'hero_description': 'Orbital imagery captured dramatic lightning activity over the Plains.',
        'hero_image': '/static/images/weather/upstream/explore/space__00.jpg',
        'items': [
            {'title': "Here's The Best Way To Watch A Meteor Shower", 'description': 'Tips for timing, darkness, and viewing angles for meteor showers.', 'duration': '', 'image': '/static/images/weather/upstream/explore/space__01.jpg'},
            {'title': 'Full Flower Moon Welcomes May: Best Pics From Around The Globe', 'description': 'A visual roundup of moonrise photos from around the world.', 'duration': '', 'image': '/static/images/weather/upstream/explore/space__02.jpg'},
            {'title': 'Bright Fireball Streaks Over Washington, Oregon', 'description': 'Witness accounts describe a vivid streaking object lighting up the sky.', 'duration': '', 'image': '/static/images/weather/upstream/explore/space__03.jpg'},
        ],
    },
    'product-guides': {
        'hero_title': 'Product Reviews & Deals',
        'hero_description': 'Practical weather-focused buying guides and product picks.',
        'hero_image': '/static/images/weather/upstream/explore/seasonal__00.jpg',
        'items': [
            {'title': 'What You Need To Know To Be Prepared For Hurricane Season', 'description': 'Core preparation checklist before peak storm months.', 'duration': '0:48', 'image': '/static/images/weather/upstream/explore/seasonal__01.jpg'},
            {'title': 'Could You Travel To The Caribbean This Hurricane Season?', 'description': 'Travel planning tips and risk windows for tropical trips.', 'duration': '1:33', 'image': '/static/images/weather/upstream/explore/seasonal__04.png'},
            {'title': 'One Month Until Hurricane Season: What We Know', 'description': 'Latest outlook and key signals heading into the season.', 'duration': '1:22', 'image': '/static/images/weather/upstream/explore/seasonal__02.png'},
        ],
    },
    'animals': {
        'hero_title': '7 Rattlesnake Hotspots in Nevada Most People Don’t Know About',
        'hero_description': 'From Lake Tahoe to Great Basin National Park, see where these snakes are most common.',
        'hero_image': '/static/images/weather/upstream/explore/animals__00.jpg',
        'items': [
            {'title': 'The Best Cat Breeds for Young Kids', 'description': 'Find family-friendly cat breeds for households with children.', 'duration': '', 'image': '/static/images/weather/upstream/explore/animals__01.jpg'},
            {'title': 'Tiny Baby Geese Get Blown Over by the Wind in Adorable Video', 'description': 'Windy conditions turn into a surprisingly cute moment.', 'duration': '', 'image': '/static/images/weather/upstream/explore/animals__02.jpg'},
            {'title': 'What It Means When Crows Call Around Your Home', 'description': 'Why this behavior happens and what it may signal.', 'duration': '', 'image': '/static/images/weather/upstream/explore/animals__03.jpg'},
        ],
    },
    'travel': {
        'hero_title': 'Ask A Met: Why Is It Unsafe To Fly In A Winter Storm?',
        'hero_description': 'Each week, meteorologists answer weather questions from readers.',
        'hero_image': '/static/images/weather/upstream/explore/travel__00.jpg',
        'items': [
            {'title': 'Where In The World Is ... Fly Geyser?', 'description': 'Can you guess where in the world Fly Geyser is?', 'duration': '', 'image': '/static/images/weather/upstream/explore/travel__01.jpg'},
            {'title': 'Forget Summer, These National Parks Are Even Better In The Snow', 'description': 'These parks transform into snow-dusted destinations in winter.', 'duration': '', 'image': '/static/images/weather/upstream/explore/travel__02.jpg'},
            {'title': 'Where In The World Is ... Goblin Valley?', 'description': 'A landscape of unusual stone formations and surreal terrain.', 'duration': '', 'image': '/static/images/weather/upstream/explore/travel__03.jpg'},
        ],
    },
    'bike': {
        'hero_title': '5 Countries, 3 Continents, and One Tiny Bike: Our Long-Term Spawn Yoji Review',
        'hero_description': 'What really makes a good first pedal bike for kids?',
        'hero_image': '/static/images/weather/upstream/explore/bike__00.jpg',
        'items': [
            {'title': 'California Draws a Long-Overdue Line Between E-Bikes and E-Motos', 'description': 'A new bill aims to clearly separate classes of electric two-wheelers.', 'duration': '', 'image': '/static/images/weather/upstream/explore/bike__01.jpg'},
            {'title': "Utah’s 3,100-Mile Bike 'Interstate' Could Revolutionize Riding Across the State", 'description': 'A statewide paved network promises safer access and broader connectivity.', 'duration': '', 'image': '/static/images/weather/upstream/explore/bike__02.jpg'},
            {'title': 'Faster than Death – First Aid Meets Mountain Bikes', 'description': 'Why emergency readiness matters when riding remote trails.', 'duration': '', 'image': '/static/images/weather/upstream/explore/bike__03.jpg'},
        ],
    },
    'seasonal': {
        'hero_title': 'What You Need To Know To Be Prepared For Hurricane Season',
        'hero_description': 'Actionable preparation guidance before storms ramp up.',
        'hero_image': '/static/images/weather/upstream/explore/seasonal__00.jpg',
        'items': [
            {'title': 'The Anatomy of a Hurricane', 'description': 'A breakdown of storm structure and key parts of a hurricane.', 'duration': '2:35', 'image': '/static/images/weather/upstream/explore/seasonal__01.jpg'},
            {'title': 'One Month Until Hurricane Season: What We Know', 'description': 'Current outlook details one month out from the season start.', 'duration': '1:22', 'image': '/static/images/weather/upstream/explore/seasonal__02.png'},
            {'title': 'Why The Offseason Is Surprisingly Busy For Hurricane Experts', 'description': 'Forecast teams continue active preparation during the quieter months.', 'duration': '1:23', 'image': '/static/images/weather/upstream/explore/seasonal__03.jpg'},
        ],
    },
}
VIDEO_FEATURED = {
    'title': 'Storm-Weary Plains, Midwest To See More Severe Weather',
    'time_label': '1 day ago',
    'updated': 'Updated: May 13, 2026, 9:23 am EDT',
    'published': 'Published: May 13, 2026, 9:23 am EDT',
    'description': 'The storm-weary Plains and Midwest are looking at the potential for more severe weather this weekend into early next week. Damaging wind gusts, large hail, tornadoes and heavy rain will all be possible each day.',
    'duration': '0:37',
    'image': '/static/images/weather/upstream/video/severe__00.jpg',
    'upstream_url': 'https://weather.com/storms/severe/video/storm-weary-plains-midwest-more-severe-weather-weekend',
}
VIDEO_NEXT_UP = [
    {'title': 'PGA Championship Weather Forecast: Cool Start, Then A Warmup', 'duration': '0:48', 'image': '/static/images/weather/upstream/video/severe__01.jpg'},
    {'title': 'West Sizzles, But Heat Shifts East This Week-Weekend', 'duration': '0:50', 'image': '/static/images/weather/upstream/video/severe__02.jpg'},
    {'title': 'What You Need To Know To Be Prepared For Hurricane Season', 'duration': '0:48', 'image': '/static/images/weather/upstream/video/severe__03.jpg'},
    {'title': 'Could You Travel To The Caribbean This Hurricane Season?', 'duration': '1:33', 'image': '/static/images/weather/upstream/video/severe__04.jpg'},
    {'title': 'One Month Until Hurricane Season: What We Know', 'duration': '1:22', 'image': '/static/images/weather/upstream/video/severe__05.png'},
    {'title': 'Why The Major Shift In The May Temperature Outlook?', 'duration': '1:27', 'image': '/static/images/weather/upstream/video/severe__06.jpg'},
    {'title': 'Tornado Wrecks Homes In Germantown, Illinois', 'duration': '0:31', 'image': '/static/images/weather/upstream/video/severe__07.jpg'},
    {'title': 'Tornado Tosses Over Train Cars In Oswego, Kansas', 'duration': '0:27', 'image': '/static/images/weather/upstream/video/severe__08.jpg'},
    {'title': 'Inside The Aftermath Of Deadly Tornado In Runaway Bay, Texas', 'duration': '0:34', 'image': '/static/images/weather/upstream/video/severe__09.jpg'},
]

MEDIA_IMAGE_PATH_ALIASES = {
    '/static/images/weather/upstream/media/06-where-has-it-spread-dozens-of-passengers-left-hantavirus-cruise-ship-after-first.jpg':
        '/static/images/weather/upstream/media/06-where-has-it-spread-dozens-of-passengers-left-hantavirus-cruise-ship-after-first-death.jpg',
}


def normalize_media_image_path(path: str) -> str:
    return MEDIA_IMAGE_PATH_ALIASES.get(path, path)


def mirror_now() -> datetime:
    return MIRROR_REFERENCE_DATE


def prefers_metric_units() -> bool:
    return bool(current_user.is_authenticated and current_user.preferred_units == 'metric')


def format_temp(temp_f: int | float) -> str:
    if prefers_metric_units():
        return f"{round((temp_f - 32) * 5 / 9)}°C"
    return f"{round(temp_f)}°F"


def format_wind(speed_mph: int | float, direction: str | None = None) -> str:
    if prefers_metric_units():
        speed = f"{round(speed_mph * 1.60934)} km/h"
    else:
        speed = f"{round(speed_mph)} mph"
    return f"{speed} {direction}".strip() if direction else speed


def format_distance(distance_mi: int | float) -> str:
    if prefers_metric_units():
        return f"{round(distance_mi * 1.60934)} km"
    return f"{round(distance_mi)} mi"


def build_media_sections(cards: list[dict], offset: int = 0) -> dict:
    if not cards:
        return {
            'hero_card': None,
            'editor_card': None,
            'seasonal_card': None,
            'tile_cards': [],
            'headline_cards': [],
            'rail_cards': [],
            'video_cards': [],
        }
    count = len(cards)

    def at(idx: int):
        return cards[(offset + idx) % count]

    return {
        'hero_card': at(0),
        'editor_card': at(2),
        'seasonal_card': at(3),
        'tile_cards': [at(i) for i in range(1, min(5, count))],
        'headline_cards': [at(i) for i in range(5, min(10, count))],
        'rail_cards': [at(i) for i in range(6, min(10, count))],
        'video_cards': [at(i) for i in range(0, min(4, count))],
    }


def get_media_sections(offset: int = 0) -> dict:
    cards = [
        {'title': row.title, 'image': normalize_media_image_path(row.image_path), 'watch_url': row.watch_url}
        for row in WeatherMediaCard.query.order_by(WeatherMediaCard.position.asc()).limit(16).all()
    ]
    return build_media_sections(cards, offset=offset)


def get_topic_media_sections(topic_key: str, topic_map: dict[str, list[int]]) -> dict:
    rows = WeatherMediaCard.query.order_by(WeatherMediaCard.position.asc()).all()
    by_position = {row.position: row for row in rows}
    selected_positions = topic_map.get(topic_key, [])

    selected_cards = []
    for position in selected_positions:
        row = by_position.get(position)
        if row is None:
            continue
        selected_cards.append({'title': row.title, 'image': normalize_media_image_path(row.image_path), 'watch_url': row.watch_url})

    if len(selected_cards) < 6:
        existing_titles = {card['title'] for card in selected_cards}
        for row in rows:
            if row.title in existing_titles:
                continue
            selected_cards.append({'title': row.title, 'image': normalize_media_image_path(row.image_path), 'watch_url': row.watch_url})
            if len(selected_cards) >= 8:
                break

    return build_media_sections(selected_cards, offset=0)


def resolve_topic(topics: list[dict], selected_key: str | None):
    topic_map = {topic['key']: topic for topic in topics}
    fallback = topics[0]
    selected = topic_map.get((selected_key or '').strip(), fallback)
    return selected


def resolve_topic_by_slug(topics: list[dict], topic_slug: str | None):
    topic_map = {topic['slug']: topic for topic in topics}
    fallback = topics[0]
    selected = topic_map.get((topic_slug or '').strip(), fallback)
    return selected


app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = 'webharbor-weather-dev-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'weather.db')}"
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
    full_name = db.Column(db.String(120), nullable=False)
    preferred_units = db.Column(db.String(20), default='imperial')
    home_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_locations = db.relationship('SavedLocation', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, raw: str):
        self.password_hash = bcrypt.generate_password_hash(raw).decode('utf-8')

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)


class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False)
    region = db.Column(db.String(120), default='')
    country = db.Column(db.String(120), default='United States')
    search_label = db.Column(db.String(180), default='')
    hero_image = db.Column(db.String(300), default='')
    radar_image = db.Column(db.String(300), default='')
    summary = db.Column(db.Text, default='')


class CurrentConditions(db.Model):
    __tablename__ = 'current_conditions'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    temperature_f = db.Column(db.Integer, default=70)
    feels_like_f = db.Column(db.Integer, default=70)
    humidity = db.Column(db.Integer, default=50)
    wind_mph = db.Column(db.Integer, default=5)
    wind_direction = db.Column(db.String(10), default='NW')
    uv_index = db.Column(db.Integer, default=3)
    visibility_mi = db.Column(db.Integer, default=10)
    air_quality = db.Column(db.String(40), default='Good')
    condition_label = db.Column(db.String(80), default='Clear')
    updated_at = db.Column(db.DateTime, default=mirror_now)
    location = db.relationship('Location')

    @property
    def temperature_c(self):
        return round((self.temperature_f - 32) * 5 / 9)

    @property
    def feels_like_c(self):
        return round((self.feels_like_f - 32) * 5 / 9)


class DailyForecast(db.Model):
    __tablename__ = 'daily_forecasts'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    forecast_date = db.Column(db.Date, nullable=False)
    high_f = db.Column(db.Integer, default=70)
    low_f = db.Column(db.Integer, default=55)
    precip_pct = db.Column(db.Integer, default=10)
    humidity = db.Column(db.Integer, default=50)
    wind_mph = db.Column(db.Integer, default=8)
    uv_index = db.Column(db.Integer, default=4)
    sunrise = db.Column(db.String(20), default='6:48 AM')
    sunset = db.Column(db.String(20), default='5:39 PM')
    condition_label = db.Column(db.String(80), default='Partly Cloudy')
    location = db.relationship('Location')

    @property
    def label(self):
        delta = (self.forecast_date - MIRROR_REFERENCE_DATE.date()).days
        if delta == 0:
            return 'Today'
        if delta == 1:
            return 'Tomorrow'
        return self.forecast_date.strftime('%a')


class HourlyForecast(db.Model):
    __tablename__ = 'hourly_forecasts'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    forecast_time = db.Column(db.DateTime, nullable=False)
    temperature_f = db.Column(db.Integer, default=70)
    precip_pct = db.Column(db.Integer, default=10)
    wind_mph = db.Column(db.Integer, default=5)
    condition_label = db.Column(db.String(80), default='Clear')
    location = db.relationship('Location')


class SevereAlert(db.Model):
    __tablename__ = 'severe_alerts'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    alert_type = db.Column(db.String(120), nullable=False)
    severity = db.Column(db.String(20), default='Moderate')
    headline = db.Column(db.String(255), default='')
    details = db.Column(db.Text, default='')
    expires_at = db.Column(db.DateTime, nullable=False)
    location = db.relationship('Location')


class SavedLocation(db.Model):
    __tablename__ = 'saved_locations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.relationship('Location')


class SiteAsset(db.Model):
    __tablename__ = 'site_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    asset_path = db.Column(db.String(300), nullable=False)


class WeatherMediaCard(db.Model):
    __tablename__ = 'weather_media_cards'
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)
    watch_url = db.Column(db.String(500), default='')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    full_name = StringField('Full name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password')])


class SearchForm(FlaskForm):
    q = StringField('Search', validators=[Optional()])


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    primary_location = None
    slug = (request.view_args or {}).get('slug')
    if slug:
        primary_location = Location.query.filter_by(slug=slug).first()
    elif request.endpoint == 'search':
        query = (request.args.get('q') or '').strip()
        if query:
            matches = search_locations(query)
            if matches:
                primary_location = matches[0]
    if primary_location is None and current_user.is_authenticated and current_user.home_location_id:
        primary_location = db.session.get(Location, current_user.home_location_id)
    if primary_location is None:
        primary_location = Location.query.filter_by(slug='new-york-ny').first()
    primary_conditions = CurrentConditions.query.filter_by(location_id=primary_location.id).first() if primary_location else None
    logo_asset = SiteAsset.query.filter_by(asset_key='brand_logo').first()
    brand_logo_path = logo_asset.asset_path if logo_asset and logo_asset.asset_path else url_for('static', filename='icons/weather-logo-og.png')
    return {
        'mirror_reference_date_label': MIRROR_REFERENCE_DATE_LABEL,
        'generate_csrf': generate_csrf,
        'primary_location': primary_location,
        'primary_conditions': primary_conditions,
        'brand_logo_path': brand_logo_path,
        'unit_label': '°C' if prefers_metric_units() else '°F',
        'fmt_temp': format_temp,
        'fmt_wind': format_wind,
        'fmt_distance': format_distance,
    }


def homepage_story_data():
    scraped_cards = [
        {'title': row.title, 'image': normalize_media_image_path(row.image_path), 'watch_url': row.watch_url}
        for row in WeatherMediaCard.query.order_by(WeatherMediaCard.position.asc()).limit(16).all()
    ]
    media_sections = build_media_sections(scraped_cards, offset=0)
    hero_image = '/static/images/weather/hero/feature-story.jpg'
    editor_image = '/static/images/weather/hero/editor-pick.jpg'
    seasonal_image = '/static/images/weather/hero/seasonal-tip.png'
    top_story_tiles = []
    top_story_headlines = []
    right_rail_cards = []
    if scraped_cards:
        top_story_tiles = [
            {
                'title': card['title'],
                'image': card['image'],
            }
            for card in scraped_cards[1:5]
        ]
        top_story_headlines = [card['title'] for card in scraped_cards[5:10]]
        right_rail_cards = [
            {
                'title': card['title'],
                'image': card['image'],
            }
            for card in scraped_cards[6:10]
        ]
    if not top_story_tiles:
        top_story_tiles = [
            {
                'title': 'Traveling Soon? Here Are The Maps You Need',
                'image': hero_image,
            },
            {
                'title': "The Arctic Is On Fire - And No, It's Not Normal",
                'image': hero_image,
            },
            {
                'title': "Home Insurance Disasters You're Not Prepared For",
                'image': seasonal_image,
            },
            {
                'title': 'See Tiny Kittens Rescued From Mississippi Tornado Wreckage',
                'image': editor_image,
            },
        ]
    if not top_story_headlines:
        top_story_headlines = [
            'How To Stay Bear-Aware While Hiking National Parks',
            'Scientists Warn New Orleans Residents May Need To Begin Relocation Planning Now, Study Finds',
            'This Major World Capital Is Sinking 10 Inches A Year',
            'Lightning From Space? Storm Over Kansas Caught in Orbit',
            'New Tick-Borne Illness Concern Is Growing',
        ]
    if not right_rail_cards:
        right_rail_cards = [
            {
                'title': '17 Popular Sun Shirts For Men And Women',
                'image': seasonal_image,
            },
            {
                'title': 'Why You Need A Silk Pillowcase (And Our Top Picks)',
                'image': hero_image,
            },
            {
                'title': '12 Travel Essentials To Stash In Your Carry-On',
                'image': editor_image,
            },
            {
                'title': "Last Minute Mother's Day Gifts That Can Still Arrive On Time",
                'image': hero_image,
            },
        ]
    hero_story_card = media_sections['hero_card']
    editor_card = media_sections['editor_card']
    seasonal_card = media_sections['seasonal_card']
    video_cards = media_sections['video_cards']
    return {
        'hero_story': {
            'title': hero_story_card['title'] if hero_story_card else 'Deadly Fungal Storms Sweeping The US',
            'summary': '',
            'image': hero_story_card['image'] if hero_story_card else hero_image,
        },
        'editor_pick': {
            'title': editor_card['title'] if editor_card else 'See Tiny Kittens Rescued From Mississippi Tornado Wreckage',
            'image': editor_card['image'] if editor_card else editor_image,
        },
        'seasonal_tip': {
            'title': seasonal_card['title'] if seasonal_card else 'Seasonal Tips for Late-Winter Temperature Swings',
            'image': seasonal_card['image'] if seasonal_card else seasonal_image,
        },
        'top_story_tiles': top_story_tiles,
        'top_story_headlines': top_story_headlines,
        'right_rail_cards': right_rail_cards,
        'video_cards': video_cards,
    }


def build_homepage_view_model(featured_locations: list[Location], conditions_by_slug: dict, forecast_hint):
    lead_location = next((location for location in featured_locations if location.slug == 'new-york-ny'), featured_locations[0] if featured_locations else None)
    lead_condition = conditions_by_slug.get(lead_location.slug) if lead_location else None
    stories = homepage_story_data()
    spotlight_modules = None
    if lead_location and lead_condition:
        lead_forecast = DailyForecast.query.filter_by(location_id=lead_location.id).order_by(DailyForecast.forecast_date.asc()).limit(2).all()
        spotlight_modules = health_activity_modules(lead_location, lead_condition, lead_forecast)
    return {
        'lead_location': lead_location,
        'lead_condition': lead_condition,
        'featured_locations': featured_locations,
        'conditions_by_slug': conditions_by_slug,
        'forecast_hint': forecast_hint,
        'spotlight_modules': spotlight_modules,
        **stories,
    }


def health_activity_modules(location, conditions, forecast):
    today = forecast[0] if forecast else None
    tomorrow = forecast[1] if len(forecast) > 1 else today
    pollen_level = 'Moderate'
    flu_risk = 'Low'
    running_score = 'Good'
    if conditions.humidity >= 70:
        pollen_level = 'High'
    if conditions.temperature_f <= 35:
        flu_risk = 'Moderate'
    if today and today.precip_pct >= 50:
        running_score = 'Fair'
    return {
        'air_quality_module': {
            'label': conditions.air_quality,
            'value': conditions.uv_index,
            'description': f"Air quality is {conditions.air_quality.lower()} with visibility around {conditions.visibility_mi} miles.",
        },
        'allergy_module': {
            'label': pollen_level,
            'value': today.precip_pct if today else conditions.humidity,
            'description': 'Pollen and mold levels may fluctuate through the day as temperatures rise.',
        },
        'flu_module': {
            'label': flu_risk,
            'value': tomorrow.low_f if tomorrow else conditions.temperature_f,
            'description': 'Cool mornings and indoor crowding can raise cold and flu discomfort risk.',
        },
        'outdoor_module': {
            'label': running_score,
            'value': today.high_f if today else conditions.temperature_f,
            'description': f"Outdoor conditions look {running_score.lower()} for walks, errands, and quick workouts.",
        },
    }


def search_locations(query: str):
    if not query:
        return []
    lowered = query.lower().strip()
    locations = Location.query.all()
    results = []
    for location in locations:
        haystack = ' '.join([location.city, location.region, location.country, location.search_label]).lower()
        score = 0
        for term in lowered.split():
            if term in haystack:
                score += 4
        if lowered in haystack:
            score += 6
        if score:
            results.append((score, location))
    results.sort(key=lambda item: (item[0], item[1].city), reverse=True)
    return [location for _, location in results]


@app.route('/')
def index():
    featured = Location.query.filter(Location.slug.in_(['new-york-ny', 'miami-fl', 'tokyo-jp', 'reykjavik-is'])).all()
    conditions = {condition.location.slug: condition for condition in CurrentConditions.query.all()}
    lead_location = next((location for location in featured if location.slug == 'new-york-ny'), featured[0] if featured else None)
    forecast_hint = None
    if lead_location:
        forecast_hint = DailyForecast.query.filter_by(location_id=lead_location.id).order_by(DailyForecast.forecast_date.asc()).first()
    model = build_homepage_view_model(featured, conditions, forecast_hint)
    return render_template('index.html', **model)


@app.route('/search')
def search():
    query = (request.args.get('q') or '').strip()
    locations = search_locations(query)
    result_conditions = {}
    if locations:
        ids = [location.id for location in locations]
        result_conditions = {
            condition.location_id: condition
            for condition in CurrentConditions.query.filter(CurrentConditions.location_id.in_(ids)).all()
        }
    return render_template('search.html', query=query, locations=locations, result_conditions=result_conditions)


@app.route('/weather/<slug>')
def location_detail(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    conditions = CurrentConditions.query.filter_by(location_id=location.id).first_or_404()
    forecast = DailyForecast.query.filter_by(location_id=location.id).order_by(DailyForecast.forecast_date.asc()).limit(10).all()
    hourly = HourlyForecast.query.filter_by(location_id=location.id).order_by(HourlyForecast.forecast_time.asc()).limit(12).all()
    alerts = SevereAlert.query.filter_by(location_id=location.id).order_by(SevereAlert.expires_at.asc()).all()
    health_modules = health_activity_modules(location, conditions, forecast[:2])
    media_sections = get_media_sections(offset=1)
    return render_template(
        'location.html',
        location=location,
        conditions=conditions,
        forecast=forecast,
        hourly=hourly,
        alerts=alerts,
        health_modules=health_modules,
        media_sections=media_sections,
    )


@app.route('/weather/<slug>/hourly')
def hourly(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    hours = HourlyForecast.query.filter_by(location_id=location.id).order_by(HourlyForecast.forecast_time.asc()).all()
    media_sections = get_media_sections(offset=3)
    return render_template('hourly.html', location=location, hours=hours, media_sections=media_sections)


@app.route('/weather/<slug>/forecast')
def forecast(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    days = DailyForecast.query.filter_by(location_id=location.id).order_by(DailyForecast.forecast_date.asc()).all()
    media_sections = get_media_sections(offset=5)
    return render_template('forecast_10day.html', location=location, days=days, media_sections=media_sections)


@app.route('/weather/<slug>/alerts')
def alerts(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    alerts = SevereAlert.query.filter_by(location_id=location.id).order_by(SevereAlert.expires_at.asc()).all()
    media_sections = get_media_sections(offset=7)
    return render_template('alerts.html', location=location, alerts=alerts, media_sections=media_sections)


@app.route('/radar/<slug>')
def radar(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    media_sections = get_media_sections(offset=9)
    return render_template('radar.html', location=location, media_sections=media_sections)


@app.route('/video')
def video():
    return render_template(
        'video.html',
        featured_video=VIDEO_FEATURED,
        next_up_videos=VIDEO_NEXT_UP,
    )


def _render_explore(selected_topic: dict):
    topic_content = EXPLORE_TOPIC_CONTENT.get(selected_topic['key'], EXPLORE_TOPIC_CONTENT['top-stories'])
    explore_items = topic_content['items']
    explore_hero = {
        'title': topic_content['hero_title'],
        'description': topic_content['hero_description'],
        'cta': 'Read more',
        'image': topic_content['hero_image'],
        'watch_url': f"https://weather.com/explore/{selected_topic['slug']}",
    }
    locations = Location.query.order_by(Location.city.asc()).all()
    result_conditions = {
        condition.location_id: condition
        for condition in CurrentConditions.query.all()
    }
    return render_template(
        'explore.html',
        locations=locations,
        result_conditions=result_conditions,
        explore_topics=EXPLORE_TOPICS,
        selected_explore_topic=selected_topic['key'],
        explore_hero=explore_hero,
        explore_items=explore_items,
    )


@app.route('/explore')
def explore():
    selected_topic = resolve_topic(EXPLORE_TOPICS, request.args.get('topic'))
    return _render_explore(selected_topic)


@app.route('/explore/<topic_slug>')
def explore_topic(topic_slug: str):
    selected_topic = resolve_topic_by_slug(EXPLORE_TOPICS, topic_slug)
    return _render_explore(selected_topic)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        current_user.full_name = (request.form.get('full_name') or current_user.full_name).strip()
        current_user.preferred_units = (request.form.get('preferred_units') or current_user.preferred_units).strip()
        db.session.commit()
        flash('Preferences updated.', 'success')
        return redirect(url_for('account'))
    saved = SavedLocation.query.filter_by(user_id=current_user.id).all()
    home_location = db.session.get(Location, current_user.home_location_id) if current_user.home_location_id else None
    return render_template('account.html', saved=saved, home_location=home_location)


@app.route('/account/save-location/<slug>', methods=['POST'])
@login_required
def save_location(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    if SavedLocation.query.filter_by(user_id=current_user.id, location_id=location.id).first() is None:
        db.session.add(SavedLocation(user_id=current_user.id, location_id=location.id))
        db.session.commit()
        flash(f'{location.city} saved to your locations.', 'success')
    return redirect(request.referrer or url_for('location_detail', slug=slug))


@app.route('/account/remove-location/<slug>', methods=['POST'])
@login_required
def remove_location(slug: str):
    location = Location.query.filter_by(slug=slug).first_or_404()
    item = SavedLocation.query.filter_by(user_id=current_user.id, location_id=location.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f'{location.city} removed from your saved locations.', 'success')
    return redirect(request.referrer or url_for('account'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Signed in.', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(email=email, full_name=form.full_name.data.strip())
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Signed out.', 'success')
    return redirect(url_for('index'))


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'weather', 'locations': Location.query.count()}


def load_seed_module():
    seed_path = os.path.join(BASE_DIR, 'seed_data.py')
    spec = importlib.util.spec_from_file_location('weather_seed_data', seed_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


seed_module = load_seed_module()

with app.app_context():
    db.create_all()
    seed_module.seed_database(
        db,
        Location,
        CurrentConditions,
        DailyForecast,
        HourlyForecast,
        SevereAlert,
        SiteAsset,
        WeatherMediaCard,
    )
    seed_module.seed_benchmark_users(db, User, SavedLocation, Location)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
