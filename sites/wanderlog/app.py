#!/usr/bin/env python3
"""wanderlog — a WebHarbor mirror of https://wanderlog.com/

Flask + SQLite mirror of the Wanderlog travel planner: the marketing landing
page, destination explore pages (11 cities with their upstream descriptions,
category chips and top places), Wanderlog's ranked "best of" geo-category
lists (attractions / restaurants / hotels / cafes / free attractions, with the
web sources that ranked each place), place detail pages, the shared travel
guides directory (14 real user guides with sections, place details, views,
likes, collaborators and comments), user profiles, the traveler leaderboard,
and the hotel search surfaces.

The authenticated trip planner mirrors Wanderlog's core product: trips with
a day-by-day itinerary (add places from the real place catalog, reorder,
schedule times, notes), an interactive map of the trip with distances, packing
and to-do checklists, budget tracking with expenses, categories, per-traveler
balances and simplified debt settlement, sharing (private / link / public
with a view-only trip URL), and collaboration (invite by email, accept or
decline, members with roles). Four benchmark accounts (Alice, Bob, Carol,
Dana) come seeded with trips, checklists, budgets, collaborators, likes and
comments built on real captured places.

Content comes from the tracked source_data/*.json snapshots captured from
wanderlog.com on 2026-09-29; the SQLite seed is
materialized deterministically at image build time (PYTHONHASHSEED=0).
"""
import hashlib
import json
import secrets
from decimal import Decimal, InvalidOperation
import math
import os
import re
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, 'instance'))
app.config["SECRET_KEY"] = os.environ.get("WANDERLOG_SECRET_KEY") or "webharbor-wanderlog-dev-key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'WANDERLOG_DB_URI', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'wanderlog.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
csrf = CSRFProtect(app)

# The mirror is a frozen snapshot of the upstream site taken 2026-09-29.
MIRROR_TODAY = date(2026, 9, 29)
MIRROR_TS = "2026-09-29 12:00"
SITE_NAME = "wanderlog"
# bcrypt hash of 'TestPass123!' — frozen so the seed DB is byte-reproducible.
BENCHMARK_PASSWORD_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')
SOURCE = os.path.join(BASE_DIR, 'source_data')

BUDGET_CATEGORIES = ['Lodging', 'Food', 'Transport', 'Activities',
                     'Shopping', 'Other']


def _load(name):
    with open(os.path.join(SOURCE, name), encoding='utf-8') as f:
        return json.load(f)


# --------------------------------------------------------- asset resolution --

_INVENTORY = None


def _inventory():
    global _INVENTORY
    if _INVENTORY is None:
        _INVENTORY = {}
        path = os.path.join(BASE_DIR, 'asset_inventory.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for row in json.load(f).get('assets', []):
                    fname = os.path.basename(row['path'])
                    _INVENTORY[fname.rsplit('.', 1)[0]] = row['path']
    return _INVENTORY


def img(name):
    """URL for a managed upstream asset by logical name (None if absent)."""
    rel = _inventory().get(name)
    if not rel:
        return None
    return '/' + rel


def slugify(text):
    out = []
    for ch in (text or '').lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in ' -_':
            out.append('-')
    return ''.join(out).strip('-')[:60] or 'img'


def place_img(name):
    return img('place-' + slugify(name))


# ------------------------------------------------------------------ models --

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text)
    home_country = db.Column(db.String(80))
    avatar = db.Column(db.String(200))
    visit_geos_count = db.Column(db.Integer, default=0)
    countries_count = db.Column(db.Integer, default=0)
    is_pro = db.Column(db.Boolean, default=False)
    is_upstream = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(10), nullable=False)


class Geo(db.Model):
    __tablename__ = 'geos'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    state_name = db.Column(db.String(120))
    country_name = db.Column(db.String(120))
    depth = db.Column(db.Integer)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    popularity = db.Column(db.Integer)
    subcategory = db.Column(db.String(60))
    image = db.Column(db.String(200))
    description = db.Column(db.Text)
    bounds = db.Column(db.Text)          # JSON [w, s, e, n]
    ancestors = db.Column(db.Text)       # JSON [{id,name,countryName}]
    nearby = db.Column(db.Text)          # JSON [{id,name,countryName,subcategory}]
    geo_pairs = db.Column(db.Text)       # JSON [{fromGeo,toGeo}]
    categories = db.Column(db.Text)      # JSON [{id,name,shortName,emoji,geoCategoryName}]
    places_lists = db.Column(db.Text)    # JSON [{id,type,title,placeCount,topImageKey}]
    explore_sections = db.Column(db.Text)  # JSON [{type,heading,blocks:[{place_id,description,image}]}]


class CategoryList(db.Model):
    __tablename__ = 'category_lists'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    geo_id = db.Column(db.Integer, db.ForeignKey('geos.id'), nullable=False)
    header_image = db.Column(db.String(200))
    upstream_count = db.Column(db.Integer)
    distinction = db.Column(db.String(40))
    kind = db.Column(db.String(40))      # attractions | restaurants | hotels | cafes | free


class ListEntry(db.Model):
    __tablename__ = 'list_entries'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('category_lists.id'), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'), nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    sources = db.Column(db.Text)         # JSON [{siteName,shortName,indexInSource,snippet}]


class Place(db.Model):
    __tablename__ = 'places'
    id = db.Column(db.Integer, primary_key=True)
    wl_id = db.Column(db.Integer, index=True)
    gplace_id = db.Column(db.String(120))
    name = db.Column(db.String(200), nullable=False)
    kind_tags = db.Column(db.Text)       # JSON ["attractions", ...]
    description = db.Column(db.Text)
    generated_description = db.Column(db.Text)
    categories = db.Column(db.Text)      # JSON [..]
    tips = db.Column(db.Text)            # JSON [..]
    reasons = db.Column(db.Text)         # JSON [..]
    reviews_summary = db.Column(db.Text)
    admission = db.Column(db.Text)       # JSON [{source,title,...}]
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    image = db.Column(db.String(200))
    rating = db.Column(db.Float)
    phone = db.Column(db.String(60))
    website = db.Column(db.String(300))
    address = db.Column(db.String(300))
    price_level = db.Column(db.Integer)
    weekday_text = db.Column(db.Text)    # JSON [..]
    types = db.Column(db.Text)           # JSON [..]
    rank_info = db.Column(db.Text)       # JSON {rank,pageTitle,category}
    nearby_attractions = db.Column(db.Text)  # JSON [names]
    nearby_restaurants = db.Column(db.Text)   # JSON [names]
    geo_id = db.Column(db.Integer, db.ForeignKey('geos.id'))


class Guide(db.Model):
    __tablename__ = 'guides'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    slug = db.Column(db.String(200))
    title = db.Column(db.String(250), nullable=False)
    type = db.Column(db.String(40))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author_blurb = db.Column(db.Text)
    distinction = db.Column(db.String(40))
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    place_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(20))
    edited_at = db.Column(db.String(20))
    header_image = db.Column(db.String(200))


class GuideSection(db.Model):
    __tablename__ = 'guide_sections'
    id = db.Column(db.Integer, primary_key=True)
    guide_id = db.Column(db.Integer, db.ForeignKey('guides.id'), nullable=False)
    heading = db.Column(db.String(250))
    type = db.Column(db.String(40))
    notes = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False)


class GuideBlock(db.Model):
    __tablename__ = 'guide_blocks'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('guide_sections.id'), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'))
    text_note = db.Column(db.Text)
    note = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False)
    added_by = db.Column(db.Integer)
    place = db.relationship('Place')


class Trip(db.Model):
    __tablename__ = 'trips'
    id = db.Column(db.Integer, primary_key=True)
    edit_key = db.Column(db.String(40), unique=True, nullable=False)
    view_key = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    geo_id = db.Column(db.Integer, db.ForeignKey('geos.id'))
    start_date = db.Column(db.String(10))
    end_date = db.Column(db.String(10))
    travelers = db.Column(db.Integer, default=1)
    currency = db.Column(db.String(8), default='USD')
    privacy = db.Column(db.String(10), default='private')
    created_at = db.Column(db.String(10), nullable=False)
    updated_at = db.Column(db.String(10), nullable=False)
    geo = db.relationship('Geo')
    owner = db.relationship('User')


class TripCollaborator(db.Model):
    __tablename__ = 'trip_collaborators'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    invite_email = db.Column(db.String(160))
    role = db.Column(db.String(20), default='editor')
    status = db.Column(db.String(20), default='pending')
    invited_at = db.Column(db.String(10))


class TripSection(db.Model):
    __tablename__ = 'trip_sections'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    heading = db.Column(db.String(200))
    day_index = db.Column(db.Integer, default=1)
    position = db.Column(db.Integer, nullable=False)


class TripEntry(db.Model):
    __tablename__ = 'trip_entries'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('trip_sections.id'), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'), nullable=False)
    note = db.Column(db.Text)
    start_time = db.Column(db.String(5))
    duration_minutes = db.Column(db.Integer)
    position = db.Column(db.Integer, nullable=False)
    added_by = db.Column(db.Integer)
    place = db.relationship('Place')


class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    text = db.Column(db.String(200), nullable=False)
    list_type = db.Column(db.String(20), default='packing')
    checked = db.Column(db.Boolean, default=False)
    added_by = db.Column(db.Integer)
    position = db.Column(db.Integer, nullable=False)


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.String(10))
    split_among = db.Column(db.Text)    # JSON [user ids]


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    guide_id = db.Column(db.Integer, db.ForeignKey('guides.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(20), nullable=False)


class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    guide_id = db.Column(db.Integer, db.ForeignKey('guides.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


# ------------------------------------------------------------------ seeding --

def _seed_gate(model, count_needed=1):
    return model.query.count() < count_needed


def seed_geos():
    if not _seed_gate(Geo):
        return
    data = _load('geos.json')['destinations']
    sections = _load('explore_sections.json')['sections']
    for gid, g in data.items():
        db.session.add(Geo(
            id=int(gid), name=g['name'], state_name=g.get('stateName'),
            country_name=g.get('countryName'), depth=g.get('depth'),
            latitude=g.get('latitude'), longitude=g.get('longitude'),
            popularity=g.get('popularity'), subcategory=g.get('subcategory'),
            image=img('geo-' + slugify(g['name'])),
            description=g.get('placeDescription') or g.get('manualDescription'),
            bounds=json.dumps(g.get('bounds') or []),
            ancestors=json.dumps(g.get('ancestors') or []),
            nearby=json.dumps(g.get('nearby') or []),
            geo_pairs=json.dumps(g.get('geoPairs') or []),
            categories=json.dumps(g.get('categories') or []),
            places_lists=json.dumps(g.get('placesLists') or []),
            explore_sections=json.dumps(sections.get(gid, [])),
        ))
    # lite geos referenced by the benchmark fixtures (autocomplete capture)
    for qname, gid in (('iceland', 88419), ('kyoto', 2)):
        rows = _load('autocomplete.json')['queries'].get(qname) or []
        row = next((r for r in rows if r['id'] == gid), None)
        if row and not Geo.query.get(gid):
            db.session.add(Geo(id=gid, name=row['name'],
                               country_name=row.get('countryName'),
                               depth=row.get('depth'),
                               latitude=row.get('latitude'),
                               longitude=row.get('longitude'),
                               popularity=row.get('popularity') or 0,
                               subcategory=row.get('subcategory'),
                               description=None,
                               bounds=json.dumps([]), ancestors=json.dumps([]),
                               nearby=json.dumps([]), geo_pairs=json.dumps([]),
                               categories=json.dumps([]),
                               places_lists=json.dumps([]),
                               explore_sections=json.dumps([])))
    db.session.flush()
    # lite geos for every destination's nearby list (explore-page cards)
    for gid, g in sorted(data.items(), key=lambda kv: int(kv[0])):
        for n in g.get('nearby', []):
            if Geo.query.get(n['id']) is None:
                db.session.add(Geo(
                    id=n['id'], name=n['name'],
                    country_name=n.get('countryName'),
                    subcategory=n.get('subcategory'),
                    popularity=0,
                    image=img('geo-' + slugify(n['name'])),
                    description=None,
                    bounds=json.dumps([]), ancestors=json.dumps([]),
                    nearby=json.dumps([]), geo_pairs=json.dumps([]),
                    categories=json.dumps([]), places_lists=json.dumps([]),
                    explore_sections=json.dumps([])))
                db.session.flush()
    db.session.commit()


_KIND_BY_SLUG = [('restaurants', 'restaurants'), ('attractions', 'attractions'),
                 ('hotels', 'hotels'), ('cafes', 'cafes'),
                 ('free-attractions', 'free')]


def _list_kind(slug):
    for needle, kind in _KIND_BY_SLUG:
        if needle in slug:
            return kind
    return 'other'


def seed_places():
    if not _seed_gate(Place):
        return
    lists = _load('geo_categories.json')['lists']
    guides = _load('guides.json')['guides']
    places_pages = _load('places.json')['places']

    index = {}          # name.casefold() -> Place (global fallback)
    scoped = {}         # (name.casefold(), geo name) -> Place
    by_wl = {}          # wl_id -> Place

    def get_or_create(name, wl_id=None, gplace_id=None, geo_id=None,
                      geo_name=None):
        key = (name or '').casefold()
        place = None
        if wl_id:
            place = by_wl.get(wl_id)
        if place is None and key and geo_name:
            place = scoped.get((key, geo_name))
        if place is None and key and wl_id is None and geo_name is None:
            # guide blocks carry no geo context — global name fallback
            place = index.get(key)
        if place is None:
            place = Place(name=name or 'Unnamed place', wl_id=wl_id,
                          gplace_id=gplace_id, geo_id=geo_id)
            db.session.add(place)
            db.session.flush()
        if wl_id and place.wl_id is None:
            place.wl_id = wl_id
        if gplace_id and not place.gplace_id:
            place.gplace_id = gplace_id
        if geo_id and place.geo_id is None:
            place.geo_id = geo_id
        if key:
            index[key] = place
            if geo_name:
                scoped[(key, geo_name)] = place
        if place.wl_id:
            by_wl[place.wl_id] = place
        return place

    # geo-category lists first (they carry wl ids + images + categories)
    for cid, lst in sorted(lists.items(), key=lambda kv: int(kv[0])):
        for p in lst['places']:
            place = get_or_create(p['name'], p.get('wanderlogPlaceId'),
                                  p.get('placeId'), lst.get('geoId'),
                                  geo_name=lst.get('geoName'))
            if p.get('latitude') is not None and place.latitude is None:
                place.latitude, place.longitude = p['latitude'], p['longitude']
            if not place.description and p.get('description'):
                place.description = p['description']
            cats = json.loads(place.categories or '[]')
            for c in (p.get('placeCategories') or []):
                if c not in cats:
                    cats.append(c)
            place.categories = json.dumps(cats[:8])
            if not place.image:
                place.image = place_img(p['name'])
            tags = json.loads(place.kind_tags or '[]')
            kind = _list_kind(lst['slug'])
            if kind not in tags:
                tags.append(kind)
            place.kind_tags = json.dumps(tags)

    # guide place blocks (rich Google data)
    for key, g in sorted(guides.items()):
        for s in g['sections']:
            for b in s['blocks']:
                if b.get('kind') != 'place':
                    continue
                place = get_or_create(b['name'], None, b.get('placeId'))
                if b.get('latitude') is not None and place.latitude is None:
                    place.latitude, place.longitude = b['latitude'], b['longitude']
                if b.get('formatted_address') and not place.address:
                    place.address = b['formatted_address']
                if b.get('rating') is not None and place.rating is None:
                    place.rating = b['rating']
                if b.get('phone') and not place.phone:
                    place.phone = b['phone']
                if b.get('website') and not place.website:
                    place.website = b['website']
                if b.get('price_level') is not None and place.price_level is None:
                    place.price_level = b['price_level']
                if b.get('weekday_text') and not place.weekday_text:
                    place.weekday_text = json.dumps(b['weekday_text'])
                if b.get('types') and not place.types:
                    place.types = json.dumps(b['types'])
                if not place.image:
                    place.image = place_img(b['name'])
    db.session.flush()

    # place detail pages (richest records; match by wl id or name)
    for pid, page in sorted(places_pages.items(), key=lambda kv: int(kv[0])):
        place = by_wl.get(page['id']) or index.get((page['name'] or '').casefold())
        if place is None:
            place = get_or_create(page['name'], page['id'], page.get('googlePlaceId'))
        place.wl_id = page['id']
        by_wl[page['id']] = place
        if page.get('description') and not place.description:
            place.description = page['description']
        if page.get('generatedDescription'):
            place.generated_description = page['generatedDescription']
        if page.get('categories'):
            place.categories = json.dumps(page['categories'][:10])
        if page.get('tips'):
            place.tips = json.dumps(page['tips'])
        if page.get('reasonsToVisit'):
            place.reasons = json.dumps(page['reasonsToVisit'])
        if page.get('reviewsSummary'):
            place.reviews_summary = page['reviewsSummary']
        if page.get('admissionDetails'):
            place.admission = json.dumps(page['admissionDetails'])
        if page.get('latitude') is not None and place.latitude is None:
            place.latitude, place.longitude = page['latitude'], page['longitude']
        if page.get('rank'):
            place.rank_info = json.dumps({
                'rank': page.get('rank'),
                'pageTitle': page.get('rankPageTitle'),
                'category': page.get('rankCategory')})
        if page.get('relatedNearbyAttractions'):
            place.nearby_attractions = json.dumps(page['relatedNearbyAttractions'])
        if page.get('relatedNearbyRestaurants'):
            place.nearby_restaurants = json.dumps(page['relatedNearbyRestaurants'])
        if not place.image:
            place.image = place_img(page['name'])
    db.session.flush()

    # explore section blocks: geo + description fallback
    for gid, g in _load('geos.json')['destinations'].items():
        for sec in _load('explore_sections.json')['sections'].get(gid, []):
            for b in sec['blocks']:
                place = scoped.get(((b['name'] or '').casefold(), g['name']))
                if place is not None:
                    if place.geo_id is None:
                        place.geo_id = int(gid)
                    if not place.image:
                        place.image = place_img(b['name'])
                    if b.get('latitude') is not None and place.latitude is None:
                        place.latitude, place.longitude = b['latitude'], b['longitude']
    db.session.commit()


def seed_lists():
    if not _seed_gate(CategoryList):
        return
    lists = _load('geo_categories.json')['lists']
    for cid, lst in sorted(lists.items(), key=lambda kv: int(kv[0])):
        cl = CategoryList(id=int(cid), slug=lst['slug'], title=lst['title'],
                          geo_id=lst['geoId'],
                          header_image=img('cat-' + str(cid)),
                          upstream_count=lst.get('upstreamCount'),
                          distinction=lst.get('distinction'),
                          kind=_list_kind(lst['slug']))
        db.session.add(cl)
        db.session.flush()
        for p in lst['places']:
            place = Place.query.filter_by(wl_id=p.get('wanderlogPlaceId')).first()
            if place is None:
                place = Place.query.filter(
                    Place.name == p['name'],
                    Place.geo_id == lst['geoId']).first()
            db.session.add(ListEntry(
                list_id=int(cid), place_id=place.id, rank=p['rank'],
                sources=json.dumps(p.get('sources') or [])))
    db.session.commit()


def seed_users_guides():
    if not _seed_guide_gate():
        return
    profiles = _load('profiles.json')
    # upstream users referenced by guides + profiles
    by_username = {}

    def upsert_user(u, bio=None, followers=None, following=None):
        uname = u.get('username')
        if not uname:
            return None
        if uname in by_username:
            return by_username[uname]
        user = User(email=f"{secure_filename(uname).lower() or 'u'}@wanderlog.upstream",
                    username=uname, display_name=u.get('name') or uname,
                    password_hash=BENCHMARK_PASSWORD_HASH,
                    bio=bio, home_country=None,
                    avatar=img('user-' + slugify(uname)),
                    visit_geos_count=u.get('visitGeosCount') or 0,
                    countries_count=u.get('countriesCount') or 0,
                    is_pro=bool(u.get('isProUser')),
                    is_upstream=True,
                    created_at='2019-01-01')
        db.session.add(user)
        db.session.flush()
        by_username[uname] = user
        return user

    for prof in profiles['users']:
        u = prof['user']
        user = upsert_user(u)
        if user is None:
            continue
        user.visit_geos_count = u.get('visitGeosCount') or 0
        user.countries_count = u.get('countriesCount') or 0
        user.is_pro = bool(u.get('isProUser'))
    db.session.flush()

    guides = _load('guides.json')['guides']
    for key in sorted(guides):
        g = guides[key]
        author = upsert_user(g.get('author') or {})
        if author is None:
            author = upsert_user({'username': 'wanderlog', 'name': 'Wanderlog'})
        guide = Guide(id=g['id'], key=key, slug=g.get('slug'), title=g['title'],
                      type=g.get('type'), author_id=author.id,
                      author_blurb=g.get('authorBlurb'),
                      distinction=g.get('distinction'),
                      view_count=g.get('viewCount') or 0,
                      like_count=g.get('likeCount') or 0,
                      place_count=g.get('placeCount') or 0,
                      created_at=(g.get('createdAt') or '')[:19],
                      edited_at=(g.get('editedAt') or '')[:19],
                      header_image=img('guide-' + key))
        db.session.add(guide)
        db.session.flush()
        for pos, s in enumerate(g['sections'], start=1):
            sec = GuideSection(guide_id=guide.id, heading=s.get('heading'),
                               type=s.get('type'), notes=s.get('notes'),
                               position=pos)
            db.session.add(sec)
            db.session.flush()
            for bpos, b in enumerate(s['blocks'], start=1):
                place = None
                if b.get('kind') == 'place':
                    place = Place.query.filter_by(name=b['name']).first()
                db.session.add(GuideBlock(
                    section_id=sec.id,
                    place_id=place.id if place else None,
                    text_note=None if b.get('kind') == 'place' else b.get('note'),
                    note=b.get('note') if b.get('kind') == 'place' else None,
                    position=bpos,
                    added_by=b.get('addedBy')))
    db.session.commit()


def _seed_guide_gate():
    return Guide.query.count() < 1


def seed_benchmark():
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    data = _load('benchmark_users.json')

    users = {}
    for spec in data['users']:
        user = User(email=spec['email'], username=spec['username'],
                    display_name=spec['display_name'],
                    password_hash=BENCHMARK_PASSWORD_HASH,
                    bio=spec.get('bio'), home_country=spec.get('home_country'),
                    avatar=img('user-' + slugify(spec['username'])),
                    visit_geos_count=spec.get('visit_geos_count', 0),
                    countries_count=spec.get('countries_count', 0),
                    is_pro=spec.get('is_pro', False), is_upstream=False,
                    created_at=spec.get('created_at', '2025-01-01'))
        db.session.add(user)
        users[spec['username']] = user
    db.session.flush()

    def place_by_name(name):
        return Place.query.filter(Place.name == name).first()

    def place_id(name):
        p = place_by_name(name)
        assert p is not None, f"benchmark fixture references unknown place {name!r}"
        return p.id

    for spec in data['trips']:
        trip = Trip(edit_key=spec['edit_key'], view_key=spec['view_key'],
                    title=spec['title'], owner_id=users[spec['owner']].id,
                    geo_id=spec.get('geo_id'),
                    start_date=spec.get('start_date'),
                    end_date=spec.get('end_date'),
                    travelers=spec.get('travelers', 2),
                    currency=spec.get('currency', 'USD'),
                    privacy=spec.get('privacy', 'private'),
                    created_at=spec.get('created_at', '2026-09-01'),
                    updated_at=spec.get('created_at', '2026-09-20'))
        db.session.add(trip)
        db.session.flush()
        for pos, day in enumerate(spec.get('days', []), start=1):
            sec = TripSection(trip_id=trip.id, heading=day['heading'],
                              day_index=pos, position=pos)
            db.session.add(sec)
            db.session.flush()
            for epos, entry in enumerate(day.get('entries', []), start=1):
                db.session.add(TripEntry(
                    section_id=sec.id, place_id=place_id(entry['place']),
                    note=entry.get('note'), start_time=entry.get('start_time'),
                    duration_minutes=entry.get('duration_minutes'),
                    position=epos, added_by=users[spec['owner']].id))
        for cpos, item in enumerate(spec.get('checklist', []), start=1):
            db.session.add(ChecklistItem(
                trip_id=trip.id, text=item['text'],
                list_type=item.get('list_type', 'packing'),
                checked=item.get('checked', False),
                added_by=users[spec['owner']].id, position=cpos))
        for expense in spec.get('expenses', []):
            db.session.add(Expense(
                trip_id=trip.id, description=expense['description'],
                amount_cents=expense['amount_cents'],
                category=expense['category'],
                paid_by=users[expense['paid_by']].id,
                date=expense.get('date'),
                split_among=json.dumps(
                    [users[u].id for u in expense.get('split_among', [spec['owner']])])))
        for collab in spec.get('collaborators', []):
            db.session.add(TripCollaborator(
                trip_id=trip.id, user_id=users[collab['user']].id,
                invite_email=users[collab['user']].email,
                role=collab.get('role', 'editor'),
                status=collab.get('status', 'accepted'),
                invited_at=collab.get('invited_at', '2026-09-10')))
    db.session.flush()

    for like in data.get('likes', []):
        guide = Guide.query.filter_by(key=like['guide']).first()
        db.session.add(Like(guide_id=guide.id,
                            user_id=users[like['user']].id))
        guide.like_count += 1
    for comment in data.get('comments', []):
        guide = Guide.query.filter_by(key=comment['guide']).first()
        db.session.add(Comment(guide_id=guide.id,
                              user_id=users[comment['user']].id,
                              body=comment['body'],
                              created_at=comment['created_at']))
    db.session.commit()


# ------------------------------------------------------------------ helpers --

def _j(model_field, default=None):
    return json.loads(model_field) if model_field else (default if default is not None else [])


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def fmt_money(cents, currency='USD'):
    return f"${cents / 100:,.2f}"


def day_count(trip):
    start, end = parse_date(trip.start_date), parse_date(trip.end_date)
    if start and end and end >= start:
        return (end - start).days + 1
    return 1


def trip_members(trip):
    """Owner + accepted collaborators, deterministic order."""
    collabs = (TripCollaborator.query.filter_by(trip_id=trip.id, status='accepted')
               .order_by(TripCollaborator.id).all())
    members = [User.query.get(trip.owner_id)]
    for c in collabs:
        if c.user_id and c.user_id != trip.owner_id:
            u = User.query.get(c.user_id)
            if u:
                members.append(u)
    return members


def can_edit(trip, user):
    if user is None or not user.is_authenticated:
        return False
    if trip.owner_id == user.id:
        return True
    c = TripCollaborator.query.filter_by(trip_id=trip.id, user_id=user.id,
                                         status='accepted').first()
    return c is not None and c.role == 'editor'


def can_view(trip, user):
    if trip.privacy in ('link', 'public'):
        return True
    if user is None or not user.is_authenticated:
        return False
    if trip.owner_id == user.id:
        return True
    c = TripCollaborator.query.filter_by(trip_id=trip.id, user_id=user.id).first()
    return c is not None and c.status in ('accepted', 'pending')


def balances(trip):
    """Return per-member money state and simplified settlements."""
    members = trip_members(trip)
    by_id = {u.id: u for u in members}
    paid = {u.id: 0 for u in members}
    owed = {u.id: 0 for u in members}
    total = 0
    for e in (Expense.query.filter_by(trip_id=trip.id)
              .order_by(Expense.id).all()):
        total += e.amount_cents
        if e.paid_by in paid:
            paid[e.paid_by] += e.amount_cents
        split_ids = json.loads(e.split_among or '[]')
        split_ids = [i for i in split_ids if i in owed]
        if not split_ids:
            split_ids = list(owed.keys())
        share = e.amount_cents / len(split_ids)
        for uid in split_ids:
            owed[uid] += share
    net = {uid: round(paid[uid] - owed[uid], 2) for uid in paid}
    net_display = {}
    for uid, v in net.items():
        cents = int(round(abs(v)))
        net_display[uid] = ('+' if v >= 0 else '-') + fmt_money(cents)
    creditors = sorted([(uid, v) for uid, v in net.items() if v > 0.005],
                       key=lambda kv: -kv[1])
    debtors = sorted([(uid, -v) for uid, v in net.items() if v < -0.005],
                      key=lambda kv: kv[1])
    settlements = []
    ci = di = 0
    while ci < len(creditors) and di < len(debtors):
        cuid, cv = creditors[ci]
        duid, dv = debtors[di]
        amount = round(min(cv, dv), 2)
        if amount > 0:
            settlements.append((by_id[duid], by_id[cuid],
                                fmt_money(int(round(amount)))))
        creditors[ci] = (cuid, cv - amount)
        debtors[di] = (duid, dv - amount)
        if creditors[ci][1] <= 0.005:
            ci += 1
        if debtors[di][1] <= 0.005:
            di += 1
    return {
        'members': members, 'total': total,
        'paid': {uid: int(round(v)) for uid, v in paid.items()},
        'owed': {k: round(v, 2) for k, v in owed.items()},
        'net': net, 'net_display': net_display,
        'settlements': settlements,
    }


def _base_ctx():
    return {
        'site_name': 'Wanderlog',
        'img': img, 'place_img': place_img, 'slugify': slugify,
        'fmt_money': fmt_money,
    }


app.jinja_env.filters['from_json'] = lambda value: json.loads(value) if value else []


def _landing_avatar(path):
    """Map an upstream landing avatar path to its downloaded mirror file."""
    avatars = _load('landing.json')['assets'].get('avatars', [])
    if path in avatars:
        return f'/static/images/upstream/landing-avatars-{avatars.index(path)}.jpg'
    return ''


app.jinja_env.filters['landing_avatar'] = _landing_avatar


def _collab_user(c):
    return User.query.get(c.user_id) if c.user_id else None


def _select_list(items, list_type):
    return [i for i in items if i.list_type == list_type]


def _done_count(items):
    return sum(1 for i in items if i.checked)


app.jinja_env.filters['collab_user'] = _collab_user
app.jinja_env.filters['select_list'] = _select_list
app.jinja_env.filters['done_count'] = _done_count
app.jinja_env.filters['expense_payer'] = lambda e: db.session.get(User, e.paid_by)
app.jinja_env.filters['dict_sorted'] = lambda d: sorted(d.items())


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


# -------------------------------------------------------------- auth routes --

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        display = request.form.get('display_name', '').strip() or username
        password = request.form.get('password', '')
        if not re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email):
            flash('Please enter a valid email address.', 'error')
        elif not re.match(r'^[A-Za-z0-9_]{3,30}$', username):
            flash('Usernames are 3-30 letters, numbers or underscores.', 'error')
        elif len(password) < 8:
            flash('Passwords need at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('That username is taken.', 'error')
        else:
            user = User(email=email, username=username, display_name=display,
                        password_hash=bcrypt.generate_password_hash(password).decode(),
                        avatar=img('user-wanderlog'),
                        created_at=MIRROR_TODAY.isoformat())
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Welcome to Wanderlog! Create your first trip to get started.')
            return redirect(url_for('plans'))
    return render_template('register.html', **_base_ctx())


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and not user.is_upstream and bcrypt.check_password_hash(
                user.password_hash, password):
            login_user(user)
            flash('Welcome back!')
            next_url = request.args.get('next') or url_for('plans')
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = url_for('plans')
            return redirect(next_url)
        flash('Incorrect email or password.', 'error')
    return render_template('login.html', **_base_ctx())


@app.route('/logout', methods=['POST'])
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('home'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.display_name = request.form.get(
            'display_name', '').strip() or current_user.display_name
        current_user.bio = request.form.get('bio', '').strip()
        current_user.home_country = request.form.get('home_country', '').strip()
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('profile'))
    my_trips = Trip.query.filter_by(owner_id=current_user.id).order_by(Trip.id).all()
    collab_ids = [c.trip_id for c in TripCollaborator.query.filter_by(
        user_id=current_user.id, status='accepted').all()]
    shared = Trip.query.filter(Trip.id.in_(collab_ids)).all() if collab_ids else []
    likes = Like.query.filter_by(user_id=current_user.id).all()
    liked_guides = [Guide.query.get(l.guide_id) for l in likes]
    return render_template('account.html', my_trips=my_trips, shared=shared,
                           liked_guides=[g for g in liked_guides if g],
                           **_base_ctx())


# ---------------------------------------------------------- public content --

@app.route('/')
def home():
    landing = _load('landing.json')
    geos = Geo.query.order_by(Geo.popularity.desc()).all()
    guides = Guide.query.order_by(Guide.view_count.desc()).limit(6).all()
    return render_template('home.html', landing=landing, geos=geos,
                           guides=guides, **_base_ctx())


@app.route('/guides')
def guides():
    q = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'views')
    query = Guide.query
    if q:
        query = query.filter(Guide.title.ilike(f'%{q}%'))
    order = {'views': Guide.view_count.desc(),
             'likes': Guide.like_count.desc(),
             'places': Guide.place_count.desc(),
             'recent': Guide.edited_at.desc()}.get(sort, Guide.view_count.desc())
    rows = query.order_by(order).all()
    return render_template('guides.html', guides=rows, q=q, sort=sort,
                           **_base_ctx())


def _guide_or_404(key):
    guide = Guide.query.filter_by(key=key).first_or_404()
    return guide


@app.route('/view/<key>')
@app.route('/view/<key>/<slug>')
def guide_view(key, slug=None):
    guide = _guide_or_404(key)
    # view counts stay frozen at the captured upstream values so every
    # walkthrough observes the same numbers (verifier determinism)
    sections = (GuideSection.query.filter_by(guide_id=guide.id)
                .order_by(GuideSection.position).all())
    blocks_by_section = {}
    for s in sections:
        blocks_by_section[s.id] = (GuideBlock.query.filter_by(section_id=s.id)
                                   .order_by(GuideBlock.position).all())
    author = User.query.get(guide.author_id)
    comments = (Comment.query.filter_by(guide_id=guide.id)
                .order_by(Comment.created_at, Comment.id).all())
    liked = (current_user.is_authenticated and
             Like.query.filter_by(guide_id=guide.id, user_id=current_user.id).first()
             is not None)
    return render_template('guide.html', guide=guide, sections=sections,
                           blocks_by_section=blocks_by_section, author=author,
                           comments=comments, comment_users={
                               c.id: User.query.get(c.user_id) for c in comments},
                           liked=liked, **_base_ctx())


@app.route('/guides/like/<key>', methods=['POST'])
@login_required
def guide_like(key):
    guide = _guide_or_404(key)
    existing = Like.query.filter_by(guide_id=guide.id,
                                    user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        guide.like_count = max(0, guide.like_count - 1)
        db.session.commit()
        flash('Removed your like.')
    else:
        db.session.add(Like(guide_id=guide.id, user_id=current_user.id))
        guide.like_count += 1
        db.session.commit()
        flash('Thanks for the like!')
    return redirect(url_for('guide_view', key=key))


@app.route('/guides/comment/<key>', methods=['POST'])
@login_required
def guide_comment(key):
    guide = _guide_or_404(key)
    body = request.form.get('body', '').strip()
    if body:
        db.session.add(Comment(guide_id=guide.id, user_id=current_user.id,
                               body=body,
                               created_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
        flash('Comment posted.')
    return redirect(url_for('guide_view', key=key))


@app.route('/explore/<int:gid>')
@app.route('/explore/<int:gid>/<slug>')
def explore(gid, slug=None):
    geo = Geo.query.get_or_404(gid)
    lists = (CategoryList.query.filter_by(geo_id=gid)
             .order_by(CategoryList.id).all())
    linked = {cl.id: cl for cl in lists}
    sections = []
    for sec in _j(geo.explore_sections):
        blocks = []
        for b in sec.get('blocks', []):
            place = Place.query.filter(Place.name == b['name']).first()
            blocks.append({
                'name': b['name'],
                'description': b.get('description'),
                'place': place,
                'image': (place.image if place and place.image else None),
            })
        sections.append({'type': sec.get('type'), 'heading': sec.get('heading'),
                         'blocks': blocks})
    categories = []
    for c in _j(geo.categories):
        categories.append({
            'name': c.get('shortName') or c['name'],
            'emoji': c.get('emoji'),
            'list': linked.get(c['id']),
        })
    nearby = []
    for n in _j(geo.nearby):
        g2 = Geo.query.get(n['id'])
        if g2:
            nearby.append(g2)
    return render_template('explore.html', geo=geo, lists=lists,
                           sections=sections, categories=categories,
                           nearby=nearby, **_base_ctx())


@app.route('/list/geoCategory/<int:cid>/<slug>')
def category_list(cid, slug):
    cl = CategoryList.query.get_or_404(cid)
    geo = Geo.query.get(cl.geo_id)
    rows = (db.session.query(ListEntry, Place)
            .filter(ListEntry.list_id == cid, ListEntry.place_id == Place.id)
            .order_by(ListEntry.rank).all())
    return render_template('list.html', cl=cl, geo=geo, rows=rows,
                           **_base_ctx())


@app.route('/place/details/<int:pid>')
def place_details(pid):
    place = Place.query.filter_by(wl_id=pid).first_or_404()
    lists = (db.session.query(CategoryList, ListEntry)
             .filter(ListEntry.place_id == place.id,
                     ListEntry.list_id == CategoryList.id)
             .order_by(CategoryList.id).all())
    return render_template('place.html', place=place, lists=lists, **_base_ctx())


@app.route('/u/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    guides = (Guide.query.filter_by(author_id=user.id)
              .order_by(Guide.view_count.desc()).all())
    public_trips = []
    if not user.is_upstream:
        public_trips = (Trip.query.filter_by(owner_id=user.id, privacy='public')
                        .order_by(Trip.id).all())
    profiles = _load('profiles.json')
    extra = next((u for u in profiles['users']
                  if u['user']['username'] == username), None)
    return render_template('profile.html', user=user, guides=guides,
                           public_trips=public_trips, extra=extra,
                           is_me=(current_user.is_authenticated and
                                  current_user.id == user.id),
                           **_base_ctx())


@app.route('/hotels')
def hotels():
    geo_arg = request.args.get('geo', type=int)
    if geo_arg:
        return redirect(url_for('hotels_geo', gid=geo_arg))
    geos = Geo.query.order_by(Geo.popularity.desc()).all()
    return render_template('hotels.html', geos=geos,
                           landing=_load('landing.json'), **_base_ctx())


@app.route('/hotels/<int:gid>')
def hotels_geo(gid):
    geo = Geo.query.get_or_404(gid)
    cl = (CategoryList.query.filter_by(geo_id=gid, kind='hotels').first())
    rows = []
    if cl:
        rows = (db.session.query(ListEntry, Place)
                .filter(ListEntry.list_id == cl.id, ListEntry.place_id == Place.id)
                .order_by(ListEntry.rank).all())
    return render_template('hotels_geo.html', geo=geo, cl=cl, rows=rows,
                           **_base_ctx())


@app.route('/leaderboard')
def leaderboard():
    profiles = _load('profiles.json')['leaderboard']
    return render_template('leaderboard.html', lb=profiles,
                           User_by_username={
                               u['username']: User.query.filter_by(
                                   username=u['username']).first()
                               for u in profiles['visitGeosLeaders']},
                           **_base_ctx())


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    geos, places, guide_rows, users = [], [], [], []
    if q:
        like = f'%{q}%'
        geos = Geo.query.filter(Geo.name.ilike(like)).order_by(
            Geo.popularity.desc()).limit(12).all()
        places = Place.query.filter(Place.name.ilike(like)).limit(20).all()
        guide_rows = Guide.query.filter(Guide.title.ilike(like)).limit(12).all()
        users = User.query.filter(db.or_(User.username.ilike(like),
                                         User.display_name.ilike(like))).limit(10).all()
    return render_template('search.html', q=q, geos=geos, places=places,
                           guides=guide_rows, users=users, **_base_ctx())


# ------------------------------------------------------------- trip planner --

def _trip_or_404(edit_key):
    return Trip.query.filter_by(edit_key=edit_key).first_or_404()


@app.route('/plans')
@login_required
def plans():
    my_trips = Trip.query.filter_by(owner_id=current_user.id).order_by(Trip.id).all()
    collabs = TripCollaborator.query.filter_by(user_id=current_user.id).all()
    shared, pending = [], []
    for c in collabs:
        t = Trip.query.get(c.trip_id)
        if t:
            if c.status == 'accepted':
                shared.append((t, c))
            elif c.status == 'pending':
                pending.append((t, c))
    return render_template('plans.html', my_trips=my_trips, shared=shared,
                           pending=pending, **_base_ctx())


@app.route('/plan/new', methods=['GET', 'POST'])
@login_required
def plan_new():
    chosen = None
    geo_id_arg = request.args.get('geo_id', type=int)
    if geo_id_arg:
        chosen = Geo.query.get(geo_id_arg)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        geo_id = request.form.get('geo_id', type=int)
        start = request.form.get('start_date', '').strip() or None
        end = request.form.get('end_date', '').strip() or None
        geo = Geo.query.get(geo_id) if geo_id else None
        if not title:
            flash('Give your trip a name.', 'error')
        elif not geo:
            flash('Pick a destination.', 'error')
        else:
            s, e = parse_date(start), parse_date(end)
            if (s is None) != (e is None) or (start and not s) or (end and not e):
                flash('Enter both a start and an end date, or leave both blank.', 'error')
            elif s and e and e < s:
                flash('The end date cannot be before the start date.', 'error')
            else:
                edit_key = secrets.token_hex(8)
                view_key = secrets.token_hex(8)
                trip = Trip(edit_key=edit_key, view_key=view_key,
                            title=title, owner_id=current_user.id,
                            geo_id=geo.id, start_date=start, end_date=end,
                            travelers=max(1, request.form.get('travelers', 2, type=int)),
                            privacy='private',
                            created_at=MIRROR_TODAY.isoformat(),
                            updated_at=MIRROR_TODAY.isoformat())
                db.session.add(trip)
                db.session.flush()
                n = day_count(trip)
                for i in range(1, n + 1):
                    heading = f'Day {i}'
                    if s:
                        heading = f'Day {i} · {(s + timedelta(days=i - 1)).strftime("%b %-d")}'
                    db.session.add(TripSection(trip_id=trip.id, heading=heading,
                                               day_index=i, position=i))
                db.session.commit()
                flash('Trip created. Add places to each day!')
                return redirect(url_for('plan', edit_key=trip.edit_key))
    q = request.args.get('q', '').strip()
    matches = []
    if q:
        matches = Geo.query.filter(Geo.name.ilike(f'%{q}%')).order_by(
            Geo.popularity.desc()).limit(8).all()
    return render_template('plan_new.html', q=q, matches=matches, chosen=chosen,
                           **_base_ctx())


@app.route('/plan/<edit_key>')
@login_required
def plan(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    sections = (TripSection.query.filter_by(trip_id=trip.id)
                .order_by(TripSection.position).all())
    entries_by_section = {}
    for s in sections:
        entries_by_section[s.id] = (db.session.query(TripEntry, Place)
                                    .filter(TripEntry.section_id == s.id,
                                            TripEntry.place_id == Place.id)
                                    .order_by(TripEntry.position).all())
    collaborators = (TripCollaborator.query.filter_by(trip_id=trip.id)
                     .order_by(TripCollaborator.id).all())
    checklist = (ChecklistItem.query.filter_by(trip_id=trip.id)
                 .order_by(ChecklistItem.position).all())
    expenses = (Expense.query.filter_by(trip_id=trip.id)
                .order_by(Expense.date, Expense.id).all())
    bal = balances(trip)
    geo = Geo.query.get(trip.geo_id) if trip.geo_id else None
    return render_template('plan.html', trip=trip, sections=sections,
                           entries_by_section=entries_by_section,
                           collaborators=collaborators, checklist=checklist,
                           expenses=expenses, bal=bal, geo=geo,
                           members=bal['members'], **_base_ctx())


@app.route('/plan/<edit_key>/add', methods=['GET'])
@login_required
def plan_add_place(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    q = request.args.get('q', '').strip()
    sections = (TripSection.query.filter_by(trip_id=trip.id)
                .order_by(TripSection.position).all())
    results = []
    if q:
        results = (Place.query.filter(Place.name.ilike(f'%{q}%'))
                   .order_by((Place.geo_id == (trip.geo_id or -1)).desc(), Place.id)
                   .limit(24).all())
    return render_template('add_place.html', trip=trip, q=q, sections=sections,
                           results=results, **_base_ctx())


def valid_stop_time():
    time = request.form.get('start_time', '').strip()
    raw_duration = request.form.get('duration', '').strip()
    duration = request.form.get('duration', type=int)
    return ((not time or re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', time))
            and (not raw_duration or (duration is not None and 0 < duration <= 1440)))


@app.route('/plan/<edit_key>/entry', methods=['POST'])
@login_required
def plan_entry_add(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    section = TripSection.query.get(request.form.get('section_id', type=int) or 0)
    place = Place.query.get(request.form.get('place_id', type=int) or 0)
    if not section or section.trip_id != trip.id or not place:
        abort(400)
    if not valid_stop_time():
        abort(400, 'Enter a valid start time and a positive duration up to one day.')
    pos = (TripEntry.query.filter_by(section_id=section.id).count() + 1)
    db.session.add(TripEntry(section_id=section.id, place_id=place.id,
                             note=request.form.get('note', '').strip() or None,
                             start_time=request.form.get('start_time', '').strip() or None,
                             duration_minutes=request.form.get('duration', type=int),
                             position=pos, added_by=current_user.id))
    trip.updated_at = MIRROR_TODAY.isoformat()
    db.session.commit()
    flash(f'Added {place.name}.')
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/entry/<int:eid>/move', methods=['POST'])
@login_required
def plan_entry_move(eid):
    entry = TripEntry.query.get_or_404(eid)
    section = TripSection.query.get_or_404(entry.section_id)
    trip = Trip.query.get_or_404(section.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    delta = request.form.get('delta', type=int) or 0
    siblings = (TripEntry.query.filter_by(section_id=section.id)
                .order_by(TripEntry.position).all())
    idx = next((i for i, e in enumerate(siblings) if e.id == entry.id), None)
    if idx is not None and 0 <= idx + delta < len(siblings):
        siblings.insert(idx + delta, siblings.pop(idx))
        for i, e in enumerate(siblings, start=1):
            e.position = i
    db.session.commit()
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/entry/<int:eid>/remove', methods=['POST'])
@login_required
def plan_entry_remove(eid):
    entry = TripEntry.query.get_or_404(eid)
    section = TripSection.query.get_or_404(entry.section_id)
    trip = Trip.query.get_or_404(section.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    db.session.delete(entry)
    siblings = (TripEntry.query.filter_by(section_id=section.id)
                .order_by(TripEntry.position).all())
    for i, e in enumerate(siblings, start=1):
        e.position = i
    db.session.commit()
    flash('Place removed from the itinerary.')
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/entry/<int:eid>/update', methods=['POST'])
@login_required
def plan_entry_update(eid):
    entry = TripEntry.query.get_or_404(eid)
    section = TripSection.query.get_or_404(entry.section_id)
    trip = Trip.query.get_or_404(section.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    if not valid_stop_time():
        abort(400, 'Enter a valid start time and a positive duration up to one day.')
    entry.note = request.form.get('note', '').strip() or None
    entry.start_time = request.form.get('start_time', '').strip() or None
    entry.duration_minutes = request.form.get('duration', type=int)
    db.session.commit()
    flash('Stop updated.')
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/<edit_key>/section', methods=['POST'])
@login_required
def plan_section_add(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    heading = request.form.get('heading', '').strip() or f'Day {day_count(trip)}'
    pos = TripSection.query.filter_by(trip_id=trip.id).count() + 1
    db.session.add(TripSection(trip_id=trip.id, heading=heading,
                               day_index=pos, position=pos))
    db.session.commit()
    flash('Section added.')
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/section/<int:sid>/rename', methods=['POST'])
@login_required
def plan_section_rename(sid):
    section = TripSection.query.get_or_404(sid)
    trip = Trip.query.get_or_404(section.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    section.heading = request.form.get('heading', '').strip() or section.heading
    db.session.commit()
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/<edit_key>/checklist', methods=['GET', 'POST'])
@login_required
def plan_checklist(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        if text:
            pos = ChecklistItem.query.filter_by(trip_id=trip.id).count() + 1
            db.session.add(ChecklistItem(
                trip_id=trip.id, text=text,
                list_type=request.form.get('list_type', 'packing'),
                added_by=current_user.id, position=pos))
            db.session.commit()
            flash('Item added to the checklist.')
        return redirect(url_for('plan_checklist', edit_key=edit_key))
    items = (ChecklistItem.query.filter_by(trip_id=trip.id)
             .order_by(ChecklistItem.list_type, ChecklistItem.position).all())
    return render_template('plan_checklist.html', trip=trip, items=items,
                           **_base_ctx())


@app.route('/plan/checklist/<int:iid>/toggle', methods=['POST'])
@login_required
def checklist_toggle(iid):
    item = ChecklistItem.query.get_or_404(iid)
    trip = Trip.query.get_or_404(item.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    item.checked = not item.checked
    db.session.commit()
    return redirect(url_for('plan_checklist', edit_key=trip.edit_key))


@app.route('/plan/checklist/<int:iid>/delete', methods=['POST'])
@login_required
def checklist_delete(iid):
    item = ChecklistItem.query.get_or_404(iid)
    trip = Trip.query.get_or_404(item.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    db.session.delete(item)
    db.session.commit()
    flash('Checklist item removed.')
    return redirect(url_for('plan_checklist', edit_key=trip.edit_key))


@app.route('/plan/<edit_key>/budget', methods=['GET', 'POST'])
@login_required
def plan_budget(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    members = trip_members(trip)
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        amount = request.form.get('amount', '').strip()
        paid_by = request.form.get('paid_by', type=int)
        category = request.form.get('category', 'Other')
        split = request.form.getlist('split_among', type=int) or [m.id for m in members]
        try:
            value = Decimal(amount)
            cents = int(value * 100) if value.is_finite() and value == value.quantize(Decimal('0.01')) else -1
        except (InvalidOperation, ValueError, OverflowError):
            cents = -1
        expense_date = request.form.get('date', '').strip()
        if (not description or cents < 0 or cents > 10**12 or paid_by not in [m.id for m in members]
                or category not in BUDGET_CATEGORIES or len(split) != len(set(split))
                or not set(split).issubset({m.id for m in members})
                or (expense_date and parse_date(expense_date) is None)):
            flash('Enter a valid amount with at most two decimal places, date, category and trip members.', 'error')
        else:
            db.session.add(Expense(trip_id=trip.id, description=description,
                                  amount_cents=cents, category=category,
                                  paid_by=paid_by,
                                  date=request.form.get('date', '').strip() or None,
                                  split_among=json.dumps(split)))
            trip.updated_at = MIRROR_TODAY.isoformat()
            db.session.commit()
            flash('Expense recorded.')
        return redirect(url_for('plan_budget', edit_key=edit_key))
    expenses = (Expense.query.filter_by(trip_id=trip.id)
               .order_by(Expense.date, Expense.id).all())
    bal = balances(trip)
    by_cat = {}
    for e in expenses:
        by_cat[e.category] = by_cat.get(e.category, 0) + e.amount_cents
    return render_template('plan_budget.html', trip=trip, expenses=expenses,
                           bal=bal, members=members, by_cat=by_cat,
                           categories=BUDGET_CATEGORIES, **_base_ctx())


@app.route('/plan/expense/<int:eid>/delete', methods=['POST'])
@login_required
def expense_delete(eid):
    expense = Expense.query.get_or_404(eid)
    trip = Trip.query.get_or_404(expense.trip_id)
    if not can_edit(trip, current_user):
        abort(403)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.')
    return redirect(url_for('plan_budget', edit_key=trip.edit_key))


@app.route('/plan/<edit_key>/collaborators', methods=['POST'])
@login_required
def plan_collaborators(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    email = request.form.get('email', '').strip().lower()
    invitee = User.query.filter_by(email=email).first()
    if not email:
        flash('Enter the email of the person to invite.', 'error')
    elif invitee and invitee.id == trip.owner_id:
        flash('That person already owns this trip.', 'error')
    elif invitee is None:
        flash('No Wanderlog account found for that email.', 'error')
    elif TripCollaborator.query.filter_by(trip_id=trip.id,
                                          user_id=invitee.id).first():
        flash('That person is already invited or a collaborator.', 'error')
    else:
        db.session.add(TripCollaborator(
            trip_id=trip.id, user_id=invitee.id, invite_email=email,
            role='editor', status='pending',
            invited_at=MIRROR_TODAY.isoformat()))
        db.session.commit()
        flash(f'Invitation sent to {invitee.display_name}.')
    return redirect(url_for('plan', edit_key=edit_key))


@app.route('/plan/collaborator/<int:cid>/remove', methods=['POST'])
@login_required
def collaborator_remove(cid):
    collab = TripCollaborator.query.get_or_404(cid)
    trip = Trip.query.get_or_404(collab.trip_id)
    if trip.owner_id != current_user.id:
        abort(403)
    db.session.delete(collab)
    db.session.commit()
    flash('Collaborator removed.')
    return redirect(url_for('plan', edit_key=trip.edit_key))


@app.route('/plan/invite/<int:cid>', methods=['POST'])
@login_required
def invite_respond(cid):
    collab = TripCollaborator.query.get_or_404(cid)
    if collab.user_id != current_user.id:
        abort(403)
    action = request.form.get('action')
    if action == 'accept':
        collab.status = 'accepted'
        flash('You joined the trip as a collaborator.')
    elif action == 'decline':
        collab.status = 'declined'
        flash('Invitation declined.')
    db.session.commit()
    return redirect(url_for('plans'))


@app.route('/plan/<edit_key>/settings', methods=['GET', 'POST'])
@login_required
def plan_settings(edit_key):
    trip = _trip_or_404(edit_key)
    if trip.owner_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete':
            section_ids = [s.id for s in TripSection.query.filter_by(
                trip_id=trip.id).all()]
            if section_ids:
                for e in TripEntry.query.filter(
                        TripEntry.section_id.in_(section_ids)).all():
                    db.session.delete(e)
            for model in (TripSection, ChecklistItem, Expense,
                          TripCollaborator):
                col = model.trip_id
                for row in db.session.query(model).filter(col == trip.id).all():
                    db.session.delete(row)
            db.session.delete(trip)
            db.session.commit()
            flash('Trip deleted.')
            return redirect(url_for('plans'))
        title = request.form.get('title', '').strip()
        start = request.form.get('start_date', '').strip() or None
        end = request.form.get('end_date', '').strip() or None
        privacy = request.form.get('privacy', trip.privacy)
        travelers = max(1, request.form.get('travelers', trip.travelers, type=int))
        s, e = parse_date(start), parse_date(end)
        if ((s is None) != (e is None) or (start and not s) or (end and not e)
                or (s and e and e < s)):
            flash('Enter valid dates with the end on or after the start.', 'error')
            return redirect(url_for('plan_settings', edit_key=edit_key))

        if title:
            trip.title = title
        trip.privacy = privacy if privacy in ('private', 'link', 'public') else trip.privacy
        trip.travelers = travelers
        s, e = parse_date(start), parse_date(end)
        if (s is None) != (e is None) or (start and not s) or (end and not e):
            flash('Enter both dates or neither.', 'error')
        elif s and e and e < s:
            flash('The end date cannot be before the start date.', 'error')
        else:
            trip.start_date, trip.end_date = start, end
            n = day_count(trip)
            existing = (TripSection.query.filter_by(trip_id=trip.id)
                        .order_by(TripSection.position).count())
            if existing and existing != n and s and e:
                for i in range(existing + 1, n + 1):
                    db.session.add(TripSection(
                        trip_id=trip.id, heading=f'Day {i} · {(s + timedelta(days=i - 1)).strftime("%b %-d")}',
                        day_index=i, position=i))
                db.session.commit()
        trip.updated_at = MIRROR_TODAY.isoformat()
        db.session.commit()
        flash('Trip settings saved.')
        return redirect(url_for('plan_settings', edit_key=edit_key))
    return render_template('plan_settings.html', trip=trip,
                           day_count=day_count(trip), **_base_ctx())


def _map_context(trip):
    stops = []
    sections = (TripSection.query.filter_by(trip_id=trip.id)
                .order_by(TripSection.position).all())
    for s in sections:
        rows = (db.session.query(TripEntry, Place)
                .filter(TripEntry.section_id == s.id,
                        TripEntry.place_id == Place.id)
                .order_by(TripEntry.position).all())
        for entry, place in rows:
            stops.append({'section': s, 'entry': entry, 'place': place})
    points = [s for s in stops
              if s['place'].latitude is not None and s['place'].longitude is not None]
    bounds = {'w': -10.0, 's': 35.0, 'e': 30.0, 'n': 60.0}
    if points:
        lats = [p['place'].latitude for p in points]
        lngs = [p['place'].longitude for p in points]
        pad_lat = max((max(lats) - min(lats)) * 0.15, 0.02)
        pad_lng = max((max(lngs) - min(lngs)) * 0.15, 0.02)
        bounds = {'w': min(lngs) - pad_lng, 'e': max(lngs) + pad_lng,
                  's': min(lats) - pad_lat, 'n': max(lats) + pad_lat}
    width, height = 800.0, 460.0

    def project(lat, lng):
        x = (lng - bounds['w']) / (bounds['e'] - bounds['w']) * (width - 60) + 30
        y = (bounds['n'] - lat) / (bounds['n'] - bounds['s']) * (height - 70) + 35
        return round(x, 1), round(y, 1)

    for i, p in enumerate(points, start=1):
        p['pin'] = i
        p['x'], p['y'] = project(p['place'].latitude, p['place'].longitude)
    legs = []
    for a, b in zip(points, points[1:]):
        km = haversine_km(a['place'].latitude, a['place'].longitude,
                          b['place'].latitude, b['place'].longitude)
        legs.append({'a': a, 'b': b, 'km': round(km, 1), 'mi': round(km * 0.621371, 1)})
    return {'stops': stops, 'points': points, 'legs': legs, 'bounds': bounds,
            'width': width, 'height': height}


@app.route('/plan/<edit_key>/map')
@login_required
def plan_map(edit_key):
    trip = _trip_or_404(edit_key)
    if not can_edit(trip, current_user):
        abort(403)
    ctx = _map_context(trip)
    return render_template('plan_map.html', trip=trip, **ctx, **_base_ctx())


@app.route('/trip/<view_key>')
def trip_view(view_key):
    trip = Trip.query.filter_by(view_key=view_key).first_or_404()
    if not can_view(trip, current_user):
        flash('This trip is private. Log in as a member to view it.', 'error')
        return redirect(url_for('login'))
    sections = (TripSection.query.filter_by(trip_id=trip.id)
                .order_by(TripSection.position).all())
    entries_by_section = {}
    for s in sections:
        entries_by_section[s.id] = (db.session.query(TripEntry, Place)
                                    .filter(TripEntry.section_id == s.id,
                                            TripEntry.place_id == Place.id)
                                    .order_by(TripEntry.position).all())
    collaborators = [User.query.get(c.user_id) for c in
                     TripCollaborator.query.filter_by(trip_id=trip.id,
                                                       status='accepted').all()]
    owner = User.query.get(trip.owner_id)
    geo = Geo.query.get(trip.geo_id) if trip.geo_id else None
    bal = balances(trip)
    ctx = _map_context(trip)
    return render_template('trip_view.html', trip=trip, sections=sections,
                           entries_by_section=entries_by_section,
                           collaborators=[c for c in collaborators if c],
                           owner=owner, geo=geo, bal=bal, **ctx, **_base_ctx())


# ------------------------------------------------------------------- health --

@app.route('/_health')
def health():
    return jsonify({
        'ok': (User.query.count() > 0 and Geo.query.count() >= 11
               and Place.query.count() > 400 and Guide.query.count() >= 14
               and Trip.query.count() >= 4),
        'site': SITE_NAME,
        'geos': Geo.query.count(),
        'places': Place.query.count(),
        'guides': Guide.query.count(),
        'users': User.query.count(),
        'trips': Trip.query.count(),
        'lists': CategoryList.query.count(),
    })


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html', **_base_ctx()), 404


# -------------------------------------------------------------------- main --

def seed_all():
    db.create_all()
    seed_geos()
    seed_places()
    seed_lists()
    seed_users_guides()
    seed_benchmark()


def main():
    with app.app_context():
        seed_all()


with app.app_context():
    if not os.environ.get('WANDERLOG_NO_AUTOSEED'):
        seed_all()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 40130))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
