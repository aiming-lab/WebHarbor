"""Ohio.gov mirror — official State of Ohio portal.

Offline mirror of https://ohio.gov/ for the WebHarbor benchmark. All runtime
content (resources, topic hubs, news, licenses, agencies, phone directory,
FAQs) is real ohio.gov data read from the bundled SQLite seed; templates
follow the upstream ODX Common Design layout (red theme). External "Launch"
buttons keep their real upstream URLs, exactly like the live site.
"""
import json
import os
import re
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash

from models import (MIRROR_REFERENCE_DATE, Agency, AlertItem, AlertSubscription,
                   AssistantQuery, ContactMessage, FAQ, FAQCategory, License,
                   NewsArticle, PhoneEntry, Resource, SavedResource, ScamReport,
                   TopicHub, TravelGuideRequest, User, db)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{INSTANCE_DIR}/ohio_gov.db"
app.config["SECRET_KEY"] = "webharbor-ohio-gov-dev-key"

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

AUDIENCES = ["residents", "tourism", "jobs", "business", "government"]
AUDIENCE_LABELS = {
    "residents": "Residents",
    "tourism": "Tourism",
    "jobs": "Jobs",
    "business": "Business",
    "government": "Government",
    "home": "Home",
    "help-center": "Help Center",
}


@app.context_processor
def inject_globals():
    return {"AUDIENCE_LABELS": AUDIENCE_LABELS}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
              "or", "is", "it", "by", "with", "how", "do", "i", "my", "can",
              "you", "your", "what", "where", "when", "who", "me", "get"}


def tokenize(query):
    return [t.lower() for t in re.split(r"\W+", query or "")
            if t.lower() not in STOP_WORDS and len(t) > 1]


def scored_search(query, items, fields, date_field=None):
    """Token-overlap scored search with field weighting (earlier fields weigh
    more — pass fields most important first, e.g. title before body)."""
    tokens = tokenize(query)
    if not tokens:
        return items, {}
    weights = [max(1, 4 - i) for i in range(len(fields))]  # 4,3,2,1...
    scored = []
    for it in items:
        score = 0
        for f, w in zip(fields, weights):
            text = (getattr(it, f, "") or "").lower()
            score += w * sum(1 for t in tokens if t in text)
        # phrase bonus: full query in the first (title) field
        if query and query.lower() in ((getattr(it, fields[0], "") or "").lower()):
            score += 6
        if score > 0:
            scored.append((it, score))
    scored.sort(key=lambda x: -x[1])
    return [s[0] for s in scored], {s[0].id: s[1] for s in scored}


def wildcard_match(pattern, value):
    """Shell-style wildcard match supporting * (any run) and ? (one char)."""
    pattern = (pattern or "").strip().lower()
    value = (value or "").strip().lower()
    if not pattern:
        return True
    rx = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$"
    return re.match(rx, value) is not None


def phone_digits(s):
    return re.sub(r"\D", "", s or "")


# ---------------------------------------------------------------------------
# Home + landing pages
# ---------------------------------------------------------------------------

def _load_json(name):
    path = os.path.join(BASE_DIR, "data", name)
    return json.loads(open(path).read())


@app.route("/")
def index():
    home = _load_json("home_sections.json")
    popular = home.get("popular", [])
    for card in popular:
        m = re.search(r"gov/site/(.+)$", card.get("href", ""))
        card["mirror_path"] = "/" + m.group(1) if m else None
    news_highlights = home.get("news_highlights", [])
    for n in news_highlights:
        n["slug"] = n.get("href", "").rstrip("/").split("/")[-1]
    divisions = home.get("divisions", [])
    return render_template("index.html", popular=popular,
                           news_highlights=news_highlights, divisions=divisions,
                           home=home)


def _landing_sections():
    return _load_json("landing_sections.json")


@app.route("/<audience>")
def landing(audience):
    if audience not in AUDIENCES:
        abort(404)
    sections = _landing_sections()
    page_sections = sections.get(audience, {})
    # resolve each category title to its topic hub so "See other resources"
    # links point at the real hub route
    hubs_by_title = {}
    for th in TopicHub.query.filter(TopicHub.slug.like(f"{audience}/topic-hubs%")):
        hubs_by_title.setdefault(th.title, th)
        if th.parent_title:
            hubs_by_title.setdefault(th.parent_title, th)
    resolved = []
    for cat, cards in page_sections.items():
        th = hubs_by_title.get(cat)
        hub_path = th.slug.split("/", 1)[1] if th else None  # drop audience prefix
        for card in cards:
            if "gov/site/" in card.get("href", ""):
                card["mirror_path"] = "/" + card["href"].split("gov/site/")[-1]
            else:
                card["mirror_path"] = None
        resolved.append({"title": cat, "cards": cards, "hub_path": hub_path})
    hero = LANDING_HEROES.get(audience)
    return render_template("landing.html", audience=audience,
                           label=AUDIENCE_LABELS[audience],
                           sections=resolved, hero=hero)


LANDING_HEROES = {
    # Verified against the live upstream landing pages: the hero images are
    # the "-lp-" files under static/images/resources (byte-identical for
    # business/tourism; same asset uuid for residents/government/jobs). The
    # original entries pointed at static/images/landing/... paths that never
    # existed, so all five audience pages rendered a broken hero (404).
    "residents": "/static/images/resources/residents-lp-GettyImages-2148892299.jpg",
    "business": "/static/images/resources/business-lp-GettyImages-1398498026.jpg",
    "government": "/static/images/resources/government-lp-GettyImages-1452692835.jpg",
    "jobs": "/static/images/resources/jobs-lp-GettyImages-1364394957.jpg",
    "tourism": "/static/images/resources/tourism-lp-GettyImages-1151481862.jpg",
}


# ---------------------------------------------------------------------------
# Upstream /wps/ URL rewriting (render time)
# ---------------------------------------------------------------------------
# Scraped body_html keeps the upstream absolute paths for embedded images
# (/wps/wcm/connect/gov/<uuid>/<n>/<file>) and internal links
# (/wps/portal/gov/site/<path>). Every embedded image is mirrored locally
# (tracked in asset_inventory.json; same upstream asset by exact /wps path)
# and the internal links follow the mirror's own route scheme -- the same
# /wps/portal/gov/site/ -> / mapping the home and landing cards already use
# -- so both are rewritten at render time. The seed DB keeps the upstream
# bytes untouched (byte-identical rebuild contract).
WPS_IMAGES = {
    "/wps/wcm/connect/gov/0d31082c-f8c6-417c-9d0f-6a54f291005b/1/starting-your-business-in-ohio-cover.jpg": "static/images/wps/starting-your-business-in-ohio-cover.jpg",
    "/wps/wcm/connect/gov/0d31082c-f8c6-417c-9d0f-6a54f291005b/2/hiring-your-first-or-next-employee-cover.jpg": "static/images/wps/hiring-your-first-or-next-employee-cover.jpg",
    "/wps/wcm/connect/gov/0d31082c-f8c6-417c-9d0f-6a54f291005b/3/sbalogo.png": "static/images/wps/sbalogo.png",
    "/wps/wcm/connect/gov/0d31082c-f8c6-417c-9d0f-6a54f291005b/4/Ohio-SBDC23.png": "static/images/wps/Ohio-SBDC23.png",
    "/wps/wcm/connect/gov/380372ca-d469-41ac-9319-b5263cca609f/1/ohgo-Screenshot-2025-06-30.jpg": "static/images/wps/ohgo-Screenshot-2025-06-30.jpg",
    "/wps/wcm/connect/gov/9d4c4925-fa70-41c7-9e80-f73e9ff6602b/1/offender-search-screenshot-2025-06-30.jpg": "static/images/wps/offender-search-screenshot-2025-06-30.jpg",
    "/wps/wcm/connect/gov/ab82c31b-68a5-48af-a88b-1f0942fec140/1/business-search-screenshot-2025-06-30.jpg": "static/images/wps/business-search-screenshot-2025-06-30.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/1/chatbot-flag-GettyImages-673012132.jpg": "static/images/topics/chatbot-flag-GettyImages-673012132.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/10/black-racer-snake-GettyImages-1021207332.jpg": "static/images/topics/black-racer-snake-GettyImages-1021207332.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/11/spotted-salamander-GettyImages-139904032.jpg": "static/images/topics/spotted-salamander-GettyImages-139904032.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/12/bullfrog-GettyImages-147308785.jpg": "static/images/topics/bullfrog-GettyImages-147308785.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/13/shelter-pet-GettyImages-1254477516.jpg": "static/images/topics/shelter-pet-GettyImages-1254477516.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/14/chatbot-carnation-GettyImages-1413320188.jpg": "static/images/topics/chatbot-carnation-GettyImages-1413320188.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/15/Chatbot-buckeye-tree-GettyImages-846642580.jpg": "static/images/topics/Chatbot-buckeye-tree-GettyImages-846642580.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/16/white-trillium-GettyImages-518651202.jpg": "static/images/topics/white-trillium-GettyImages-518651202.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/17/pargon-tomato-GettyImages-139867737.jpg": "static/images/topics/pargon-tomato-GettyImages-139867737.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/18/pawpaw-GettyImages-1280362006.jpg": "static/images/topics/pawpaw-GettyImages-1280362006.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/19/tomato-juice-GettyImages-516818208.jpg": "static/images/topics/tomato-juice-GettyImages-516818208.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/2/seal.jpg": "static/images/topics/seal.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/20/song-GettyImages-154927026.jpg": "static/images/topics/song-GettyImages-154927026.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/21/rock-song-GettyImages-1129643492.jpg": "static/images/topics/rock-song-GettyImages-1129643492.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/22/Blaine_Hill_S_Bridge_Ohio.jpg": "static/images/topics/Blaine_Hill_S_Bridge_Ohio.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/23/newark-earthworks-GettyImages-1473458053+%281%29.jpg": "static/images/topics/newark-earthworks-GettyImages-1473458053+(1).jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/24/adena-pipe.jpg": "static/images/topics/adena-pipe.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/25/barn-GettyImages-1416954056.jpg": "static/images/topics/barn-GettyImages-1416954056.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/26/state-airplane-wright-flyer-iii-GettyImages-1406119160.jpg": "static/images/topics/state-airplane-wright-flyer-iii-GettyImages-1406119160.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/27/flint-GettyImages-1368219385.jpg": "static/images/topics/flint-GettyImages-1368219385.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/28/isotelus-GettyImages-1248005755.jpg": "static/images/topics/isotelus-GettyImages-1248005755.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/3/GettyImages-1007304622.jpg": "static/images/topics/GettyImages-1007304622.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/4/Ohio-heart-for-symbols-page.jpg": "static/images/topics/Ohio-heart-for-symbols-page.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/5/statehouse-2-GettyImages-185243992.jpg": "static/images/topics/statehouse-2-GettyImages-185243992.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/6/chatbot-buckeye-GettyImages-1389150272.jpg": "static/images/topics/chatbot-buckeye-GettyImages-1389150272.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/7/chatbot-cardinal-GettyImages-1143963433.jpg": "static/images/topics/chatbot-cardinal-GettyImages-1143963433.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/8/ladybug-GettyImages-1273812417.jpg": "static/images/topics/ladybug-GettyImages-1273812417.jpg",
    "/wps/wcm/connect/gov/ad4fdb80-6e1c-4de1-a4db-c8186976c9d7/9/chatbot-white-tail-deer-GettyImages-1361084779.jpg": "static/images/topics/chatbot-white-tail-deer-GettyImages-1361084779.jpg",
    "/wps/wcm/connect/gov/bc7492d9-f788-4b74-9159-3c8a87148aea/1/StateMapCountiesAsset+1.png": "static/images/wps/StateMapCountiesAsset 1.png",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/1/facts-amusement-parks-GettyImages-183057020.jpg": "static/images/wps/facts-amusement-parks-GettyImages-183057020.jpg",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/2/facts-collegiate-sports-GettyImages-1009100668.jpg": "static/images/wps/facts-collegiate-sports-GettyImages-1009100668.jpg",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/3/facts-museums-GettyImages-2201083094.jpg": "static/images/wps/facts-museums-GettyImages-2201083094.jpg",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/4/Mohican+State+Park+in+Loudonville.jpg": "static/images/wps/Mohican State Park in Loudonville.jpg",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/5/facts-pro-sports-GettyImages-458417881.jpg": "static/images/wps/facts-pro-sports-GettyImages-458417881.jpg",
    "/wps/wcm/connect/gov/bf7c6576-2bc7-41ea-b04d-1f05a84b4372/6/Columbus+Zoo+and+Aquarium.jpg": "static/images/wps/Columbus Zoo and Aquarium.jpg",
    "/wps/wcm/connect/gov/f929abdc-5cf6-4897-ad76-e23c0a401dd8/1/sex-offender-search-ss-june26.jpg": "static/images/wps/sex-offender-search-ss-june26.jpg",
}


@app.template_filter("mirror_wps")
def mirror_wps(html):
    """Rewrite upstream /wps/ media + internal links in scraped body_html to
    their mirror equivalents (images: local same-asset files; links: the
    site's own route scheme)."""
    if not html or "/wps/" not in html:
        return html

    def _img(match):
        local = WPS_IMAGES.get(match.group(2))
        if not local:
            return match.group(0)
        return match.group(1) + "/" + local + '"'

    # src="<path>" or src="<path>?MOD=AJPERES" -> the local asset (query dropped)
    html = re.sub(r'(src=")(/wps/wcm/connect/[^"?]+)(?:\?[^"]*)?(")', _img, html)
    # <a href="/wps/portal/gov/site/<path>"> -> <a href="/<path>"> (mirror routes)
    html = re.sub(r'(<a\s+href=")/wps/portal/gov/site/([^"]+)"',
                  lambda m: m.group(1) + "/" + m.group(2) + '"', html)
    return html


# ---------------------------------------------------------------------------
# Topic hubs (category pages)
# ---------------------------------------------------------------------------

@app.route("/<audience>/topic-hubs/<path:hub>")
@app.route("/<audience>/<path:hub>")
def topic_hub(audience, hub):
    if audience not in AUDIENCES:
        abort(404)
    for hub_path in (f"{audience}/topic-hubs/{hub}", f"{audience}/{hub}"):
        th = TopicHub.query.filter_by(slug=hub_path).first()
        if th:
            break
    if not th:
        abort(404)
    q = request.args.get("q", "").strip()
    # resources in this hub (direct members)
    members = [r for r in Resource.query.all() if th.title in r.categories]
    if q:
        members, _ = scored_search(q, members, ["title", "summary", "body_text"])
    else:
        members.sort(key=lambda r: r.title.lower())
    # sub-hubs (children)
    children = TopicHub.query.filter_by(parent_title=th.title).order_by(TopicHub.title).all()
    # sibling hubs of the same audience for the sidebar
    siblings = TopicHub.query.filter(
        TopicHub.slug.like(f"{audience}/topic-hubs/%"),
        TopicHub.parent_title.is_(None)).order_by(TopicHub.title).all()
    return render_template("topic_hub.html", hub=th, members=members,
                           children=children, siblings=siblings,
                           audience=audience, label=AUDIENCE_LABELS.get(audience, ""),
                           q=q)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@app.route("/<audience>/resources/<slug>")
@app.route("/resources/<slug>")
def resource_detail(audience, slug):
    res = Resource.query.filter_by(slug=slug).first_or_404()
    related = []
    if res.related_agencies:
        names = res.related_agencies
        related = Agency.query.filter(Agency.name.in_(names)).all()
    # same-category resources as "related resources"
    same_cat = []
    if res.categories:
        same_cat = [r for r in Resource.query.filter(Resource.id != res.id).all()
                    if set(res.categories) & set(r.categories)][:4]
    saved = False
    if current_user.is_authenticated:
        saved = SavedResource.query.filter_by(
            user_id=current_user.id, resource_id=res.id).first() is not None
    return render_template("resource_detail.html", res=res, related=related,
                           same_cat=same_cat, saved=saved)


@app.route("/resources")
def resources_all():
    page = request.args.get("page", 1, type=int)
    audience = request.args.get("audience", "")
    q = request.args.get("q", "")
    query = Resource.query
    if audience in AUDIENCES:
        query = query.filter_by(audience=audience)
    if q:
        items, scores = scored_search(q, list(query.all()),
                                       ["title", "summary", "body_text"])
    else:
        items = query.order_by(Resource.title).all()
    PER = 20
    total = len(items)
    page_items = items[(page - 1) * PER: page * PER]
    return render_template("resources_all.html", items=page_items, total=total,
                           page=page, per=PER, audience=audience, q=q)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@app.route("/search")
def search():
    q = request.args.get("search_query") or request.args.get("q") or ""
    tab = request.args.get("t", "Resources")
    page = request.args.get("page", 1, type=int)
    PER = 10

    resources = Resource.query.all()
    news = NewsArticle.query.order_by(NewsArticle.position).all()
    faqs = FAQ.query.all()
    agencies = Agency.query.all()
    licenses = License.query.all()

    res_hits, _ = scored_search(q, resources, ["title", "summary", "body_text", "search_summary"])
    news_hits, _ = scored_search(q, news, ["title", "summary", "body_html"])
    faq_hits, _ = scored_search(q, faqs, ["question", "answer_html"])
    ag_hits, _ = scored_search(q, agencies, ["name"])
    lic_hits, _ = scored_search(q, licenses, ["name", "agency"])

    if tab == "News":
        items, kind = news_hits, "news"
        total = len(news_hits)
    elif tab == "FAQs":
        items, kind = faq_hits, "faq"
        total = len(faq_hits)
    elif tab == "Agencies":
        items, kind = ag_hits, "agency"
        total = len(ag_hits)
    elif tab == "Licenses":
        items, kind = lic_hits, "license"
        total = len(lic_hits)
    else:
        items, kind = res_hits, "resource"
        total = len(res_hits)
        tab = "Resources"

    page_items = items[(page - 1) * PER: page * PER]
    pages = (total + PER - 1) // PER

    counts = {"Resources": len(res_hits), "News": len(news_hits),
              "FAQs": len(faq_hits), "Agencies": len(ag_hits),
              "Licenses": len(lic_hits)}
    return render_template("search.html", q=q, tab=tab, items=page_items,
                           kind=kind, total=total, page=page, pages=pages,
                           counts=counts)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

@app.route("/news-and-events/all-news")
@app.route("/media-center")
def all_news():
    page = request.args.get("page", 1, type=int)
    source = request.args.get("source", "")
    items = NewsArticle.query.order_by(NewsArticle.position)
    if source:
        items = items.filter(NewsArticle.source.ilike(f"%{source}%"))
    items = items.all()
    PER = 10
    total = len(items)
    page_items = items[(page - 1) * PER: page * PER]
    sources = sorted({a.source for a in NewsArticle.query.all() if a.source})
    return render_template("news_list.html", items=page_items, total=total,
                           page=page, per=PER, sources=sources,
                           active_source=source)


@app.route("/news-and-events/all-news/<slug>")
def news_detail(slug):
    art = NewsArticle.query.filter_by(slug=slug).first_or_404()
    others = NewsArticle.query.filter(NewsArticle.slug != slug).order_by(
        NewsArticle.position).limit(4).all()
    return render_template("news_detail.html", art=art, others=others)


# ---------------------------------------------------------------------------
# Licenses & permits (special resource page with the professional license table)
# ---------------------------------------------------------------------------

@app.route("/jobs/resources/licenses-and-permits")
def licenses_page():
    q = request.args.get("q", "").strip()
    agency = request.args.get("agency", "").strip()
    page = request.args.get("page", 1, type=int)
    items = License.query.order_by(License.name).all()
    if q:
        items, _ = scored_search(q, items, ["name", "agency"])
    if agency:
        items = [l for l in items if agency.lower() in (l.agency or "").lower()]
    agencies_sorted = sorted({l.agency for l in License.query.all() if l.agency})
    PER = 25
    total = len(items)
    page_items = items[(page - 1) * PER: page * PER]
    pages = (total + PER - 1) // PER
    return render_template("licenses.html", items=page_items, total=total,
                           page=page, pages=pages, q=q, agency=agency,
                           agencies=agencies_sorted)


# ---------------------------------------------------------------------------
# Help center: FAQs, phone search, state directory, Ohio Assistant
# ---------------------------------------------------------------------------

@app.route("/help-center")
def help_center():
    cats = FAQCategory.query.order_by(FAQCategory.title).all()
    return render_template("help_center.html", cats=cats)


@app.route("/help-center/faqs")
def faqs_all():
    cats = FAQCategory.query.order_by(FAQCategory.title).all()
    return render_template("faqs_all.html", cats=cats)


@app.route("/help-center/faqs/<cat>")
def faq_category(cat):
    c = FAQCategory.query.filter_by(slug=cat).first_or_404()
    items = FAQ.query.filter_by(category_slug=cat).order_by(FAQ.position).all()
    others = FAQCategory.query.filter(FAQCategory.slug != cat).order_by(FAQCategory.title).all()
    return render_template("faq_category.html", cat=c, items=items, others=others)


@app.route("/help-center/phone-search")
def phone_search():
    first = request.args.get("firstName", "").strip()
    last = request.args.get("lastName", "").strip()
    agency = request.args.get("agency", "").strip()
    phone = request.args.get("phone", "").strip()
    searched = bool(first or last or agency or phone)
    items = []
    if searched:
        for e in PhoneEntry.query.all():
            if first and not wildcard_match(first, e.name.split()[0] if e.name.split() else ""):
                continue
            if last and not wildcard_match(last, e.name.split()[-1] if e.name.split() else ""):
                continue
            if agency and agency.lower() not in (e.agency or "").lower():
                continue
            if phone:
                pat_digits = phone_digits(phone)
                val_digits = phone_digits(e.phone)
                if pat_digits and val_digits != pat_digits and not wildcard_match(phone, e.phone):
                    continue
            items.append(e)
        items.sort(key=lambda e: e.name.lower())
    return render_template("phone_search.html", items=items, searched=searched,
                           first=first, last=last, agency=agency, phone=phone)


@app.route("/help-center/state-directory")
def state_directory():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per = request.args.get("per", 25, type=int)
    items = Agency.query.order_by(Agency.name).all()
    if q:
        items, _ = scored_search(q, items, ["name"])
    total = len(items)
    per = per if per in (25, 50, 75, 100) else 25
    pages = (total + per - 1) // per
    page_items = items[(page - 1) * per: page * per]
    return render_template("state_directory.html", items=page_items, total=total,
                           q=q, page=page, per=per, pages=pages)


@app.route("/help-center/ohio-assistant")
def ohio_assistant():
    answer = None
    q = request.args.get("q", "").strip()
    if q:
        answer = assistant_answer(q)
    return render_template("ohio_assistant.html", q=q, answer=answer)


def assistant_answer(q):
    resources = Resource.query.all()
    hits, _ = scored_search(q, resources, ["title", "summary", "body_text"])
    top = hits[:3]
    if not top:
        return {"text": ("I could not find Ohio.gov resources for that. Try "
                         "different keywords, or browse the Services for "
                         "Residents, Jobs, Business, or Government sections."),
                "results": []}
    return {"text": "Here are the most relevant Ohio.gov resources I found:",
            "results": top}


# ---------------------------------------------------------------------------
# Auth + account
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ident = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        user = User.query.filter((User.email == ident) |
                                 (User.username == ident)).first()
        if user and user.check_password(pw):
            login_user(user)
            flash("You are now signed in with your OHID.", "success")
            nxt = request.args.get("next")
            return redirect(nxt or url_for("account"))
        flash("Invalid OHID or password. Please try again.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")
        display = request.form.get("display_name", "").strip()
        if not username or not email or not pw:
            flash("All fields are required.", "danger")
        elif pw != pw2:
            flash("The two passwords do not match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "danger")
        else:
            u = User(username=username, email=email, display_name=display or username)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash("Your OHID account was created.", "success")
            return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have signed out of your OHID.", "success")
    return redirect(url_for("index"))


@app.route("/account")
@login_required
def account():
    saved = (db.session.query(SavedResource, Resource)
             .join(Resource, Resource.id == SavedResource.resource_id)
             .filter(SavedResource.user_id == current_user.id)
             .order_by(SavedResource.created_at).all())
    subs = AlertSubscription.query.filter_by(user_id=current_user.id).all()
    subs_types = [s.alert_type for s in subs]
    guides = TravelGuideRequest.query.filter_by(user_id=current_user.id).all()
    reports = ScamReport.query.filter_by(user_id=current_user.id).all()
    return render_template("account.html", saved=saved, subs=subs,
                           subs_types=subs_types, guides=guides, reports=reports)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    if request.method == "POST":
        u = current_user
        u.display_name = request.form.get("display_name", u.display_name)
        u.first_name = request.form.get("first_name", u.first_name)
        u.last_name = request.form.get("last_name", u.last_name)
        u.phone = request.form.get("phone", u.phone)
        u.address_line1 = request.form.get("address_line1", u.address_line1)
        u.city = request.form.get("city", u.city)
        u.state = request.form.get("state", u.state)
        u.zip = request.form.get("zip", u.zip)
        db.session.commit()
        flash("Your OHID profile has been updated.", "success")
        return redirect(url_for("account"))
    return render_template("account_edit.html")


@app.route("/account/saved/<int:resource_id>", methods=["POST"])
@login_required
def toggle_saved(resource_id):
    res = Resource.query.get_or_404(resource_id)
    existing = SavedResource.query.filter_by(
        user_id=current_user.id, resource_id=resource_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed {res.title} from your saved resources.", "success")
    else:
        db.session.add(SavedResource(user_id=current_user.id, resource_id=resource_id))
        db.session.commit()
        flash(f"Saved {res.title} to your OHID account.", "success")
    return redirect(request.referrer or url_for("account"))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.route("/alerts")
def alerts():
    items = AlertItem.query.order_by(AlertItem.position, AlertItem.id).all()
    subscribed = []
    if current_user.is_authenticated:
        subscribed = [s.alert_type for s in
                      AlertSubscription.query.filter_by(user_id=current_user.id)]
    return render_template("alerts.html", items=items, subscribed=subscribed)


@app.route("/alerts/subscribe", methods=["POST"])
def alerts_subscribe():
    email = request.form.get("email", "").strip()
    alert_type = request.form.get("alert_type", "All alerts").strip()
    if not email or "@" not in email:
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for("alerts"))
    uid = current_user.id if current_user.is_authenticated else None
    db.session.add(AlertSubscription(user_id=uid, email=email, alert_type=alert_type))
    db.session.commit()
    flash(f"You are now subscribed to {alert_type} at {email}.", "success")
    return redirect(url_for("alerts"))


# ---------------------------------------------------------------------------
# Forms: travel guide + scam report
# ---------------------------------------------------------------------------

@app.route("/travel-guide", methods=["GET", "POST"])
def travel_guide():
    if request.method == "POST":
        required = ["full_name", "email", "address_line1", "city", "state", "zip", "format"]
        if all(request.form.get(f, "").strip() for f in required):
            req = TravelGuideRequest(
                user_id=current_user.id if current_user.is_authenticated else None,
                full_name=request.form["full_name"].strip(),
                email=request.form["email"].strip(),
                address_line1=request.form["address_line1"].strip(),
                city=request.form["city"].strip(),
                state=request.form["state"].strip(),
                zip=request.form["zip"].strip(),
                format=request.form["format"].strip())
            db.session.add(req)
            db.session.commit()
            flash(f"Your 2026 Ohio Travel Guide will be mailed to {req.address_line1}, "
                  f"{req.city}, {req.state} {req.zip}.", "success")
            return redirect(url_for("travel_guide"))
        flash("Please fill in every field so we can mail your guide.", "danger")
    return render_template("travel_guide.html")


@app.route("/report-scam", methods=["GET", "POST"])
def report_scam():
    if request.method == "POST":
        if not request.form.get("full_name", "").strip() or \
           not request.form.get("description", "").strip() or \
           not request.form.get("scam_type", "").strip():
            flash("Name, scam type, and description are required.", "danger")
        else:
            rep = ScamReport(
                user_id=current_user.id if current_user.is_authenticated else None,
                full_name=request.form["full_name"].strip(),
                email=request.form.get("email", "").strip(),
                phone=request.form.get("phone", "").strip(),
                scam_type=request.form["scam_type"].strip(),
                description=request.form["description"].strip(),
                amount=request.form.get("amount", "").strip(),
                occurred_on=request.form.get("occurred_on", "").strip())
            db.session.add(rep)
            db.session.commit()
            flash("Your consumer complaint has been submitted to the Ohio Attorney "
                  "General's office. Keep your confirmation number.", "success")
            return redirect(url_for("report_scam"))
    return render_template("report_scam.html")


# ---------------------------------------------------------------------------
# Static info pages
# ---------------------------------------------------------------------------

@app.route("/privacy-notice-and-policies")
def privacy():
    return render_template("privacy.html")


@app.route("/accessibility")
def accessibility():
    return render_template("accessibility.html")


@app.route("/responsible-gambling")
def responsible_gambling():
    return render_template("responsible_gambling.html")


@app.route("/outage-notification")
def outage_notification():
    items = AlertItem.query.order_by(AlertItem.position, AlertItem.id).all()
    return render_template("outage_notification.html", items=items)


@app.route("/_health")
def health():
    counts = {
        "resources": Resource.query.count(),
        "news": NewsArticle.query.count(),
        "licenses": License.query.count(),
        "agencies": Agency.query.count(),
        "phones": PhoneEntry.query.count(),
        "faqs": FAQ.query.count(),
        "users": User.query.count(),
    }
    return {"ok": all(v > 0 for v in counts.values()), "site": "ohio_gov", **counts}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def seed_database():
    if Resource.query.count() > 0:
        return
    from seed_data import seed_content
    seed_content(db)


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    from seed_data import seed_users
    seed_users(db)


with app.app_context():
    db.create_all()
    seed_database()
    seed_benchmark_users()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
