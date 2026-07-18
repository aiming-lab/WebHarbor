"""Recreation.gov mirror - Flask app."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
app.config["SECRET_KEY"] = "webharbor-recreation-gov-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'recreation_gov.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

STOP_WORDS = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "near", "with", "from", "on", "at", "by", "is", "are", "me", "my"}

INVENTORY_LABELS = {
    "camping": "Camping & Lodging",
    "tickets": "Tickets & Tours",
    "permits": "Permits",
    "passes": "Activity & Site Passes",
    "day_use": "Day Use / Venues",
    "lottery": "Lotteries",
}

HOME_EXPERIENCE_PANELS = [
    {
        "key": "all",
        "label": "All Experiences",
        "inventory_types": ("camping", "tickets", "permits", "passes", "day_use"),
        "description": "Popular outdoor stays, timed entry, tours, and permit windows within driving distance.",
    },
    {
        "key": "camping",
        "label": "Camping & Lodging",
        "inventory_types": ("camping",),
        "description": "Campgrounds, cabins, and overnight options with upcoming availability.",
    },
    {
        "key": "tickets",
        "label": "Tickets & Tours",
        "inventory_types": ("tickets",),
        "description": "Guided tours, monument access, and scheduled visitor experiences.",
    },
    {
        "key": "permits",
        "label": "Permits",
        "inventory_types": ("permits",),
        "description": "Lottery windows, wilderness permits, and backcountry entry rules.",
    },
    {
        "key": "passes",
        "label": "Activity Passes",
        "inventory_types": ("passes",),
        "description": "Timed-entry and standard amenity passes for high-demand destinations.",
    },
    {
        "key": "day_use",
        "label": "Day Use & Venues",
        "inventory_types": ("day_use",),
        "description": "Picnic areas, launch points, and reservable day-use venues.",
    },
]

CATEGORY_TILES = [
    ("camping", "Camping & Lodging", "real-nav-camping.webp", "Book campsites, cabins, RV sites, and overnight stays.", None),
    ("tickets", "Tickets & Tours", "real-nav-tickets.webp", "Reserve tours, tickets, ranger programs, and visitor experiences.", None),
    ("permits", "Permits", "real-nav-permits.webp", "Find wilderness, day-use, and special access permits.", None),
    ("passes", "Activity Passes", "real-nav-passes.webp", "Buy activity and site passes before you arrive.", None),
    ("lottery", "Lotteries", "real-nav-lotteries.webp", "Enter high-demand lotteries and timed entry drawings.", None),
    ("fishing", "Hunting & Fishing", "real-nav-fishing.webp", "Discover fishing access, permit windows, and outdoor sport experiences.", "fishing"),
    ("day_use", "Day Use & Venues", "real-nav-venues.webp", "Reserve picnic areas, venues, parking, and day-use sites.", None),
]

HOME_NEARBY_SLUGS = [
    "aquatic-park-cove-overnight-anchoring",
    "point-reyes-national-seashore-campground",
    "pinnacles-campground",
    "oak-knoll-campground",
    "glory-hole-recreation-area",
    "lake-sonoma-boat-in-sites",
]

HOME_AI_EXAMPLES = [
    "RV camping near Zion with electric hookups for 4 people next month",
    "Tent sites near Yosemite with hiking trails this weekend",
    "Day use permits for Yellowstone",
    "Accessible cabins in Alaska with fishing available in July",
    "Waterfront camping at Grand Canyon with full hookups for a 35 foot RV",
    "Timed entry passes for Rocky Mountain with easy morning access",
    "Guided historic tours near San Francisco this weekend",
    "Family-friendly picnic areas near Sedona with parking",
    "Backcountry permits near Lake Tahoe for two nights",
    "Cabins with fishing access in Alaska during July",
]

HOME_ARTICLE_SLUGS = [
    "campfire-safety-tips",
    "play-it-safe-trip-planning",
    "beautiful-beach-destinations",
]

ARTICLE_LIBRARY = {
    "campfire-safety-tips": {
        "slug": "campfire-safety-tips",
        "title": "Campfire Safety Tips",
        "kicker": "Location Spotlight",
        "summary": "Review current fire rules, wood collection limits, and quiet-hour expectations before you head out.",
        "image": "real-aquatic-park-cove.webp",
        "paragraphs": [
            "Campfire rules vary by agency, season, and current fire conditions. Visitors should confirm whether fires are allowed, whether only provided rings may be used, and whether local bans override normal campground rules.",
            "Pack a shovel, keep water close by, and never leave a fire unattended. Even established campgrounds may require fires to be fully extinguished before you depart for a trail, shower, or picnic area.",
            "If your trip includes high-demand sites such as Point Reyes or Pinnacles, review facility alerts before arrival because weather and fuel conditions can change operating rules quickly.",
        ],
    },
    "play-it-safe-trip-planning": {
        "slug": "play-it-safe-trip-planning",
        "title": "Plan Ahead and Play It Safe for Your Next Outdoor Adventure",
        "kicker": "Trip Planning",
        "summary": "Compare permits, timed entry windows, and campsite rules before committing to a long drive.",
        "image": "real-point-reyes-seashore.webp",
        "paragraphs": [
            "Popular public lands destinations often combine several reservation systems: overnight stays, timed entry, transit shuttles, or wilderness permits. Checking those constraints together prevents avoidable no-entry situations.",
            "A strong plan starts with three checks: the inventory type you need, the allowed date window, and the agency rules attached to that reservation. Recreation.gov mirrors make those details visible side by side so agents can compare options quickly.",
            "For higher-risk itineraries, save alternatives nearby before checkout. That gives you a practical fallback if a site closes, a permit window changes, or access conditions tighten.",
        ],
    },
    "beautiful-beach-destinations": {
        "slug": "beautiful-beach-destinations",
        "title": "10 Beautiful Beach Destinations",
        "kicker": "Inspiration",
        "summary": "From sheltered coves to long Pacific overlooks, coastal inventory mixes day-use, tours, and overnight stays.",
        "image": "real-aquatic-park-cove.webp",
        "paragraphs": [
            "Beach and waterfront inventory spans more than campgrounds. Visitors often need to compare parking passes, harbor tours, overnight anchoring, and reservable launch or picnic access in the same trip plan.",
            "San Francisco Maritime, Aquatic Park Cove, Point Reyes, and Fort Point demonstrate how different reservation types cluster around the same coastal region.",
            "When recreating real trip-planning behavior, treat nearby day-use and tour inventory as complements to camping rather than separate flows.",
        ],
    },
    "celebrate-america-250": {
        "slug": "celebrate-america-250",
        "title": "Celebrate 250 Years of American Discovery",
        "kicker": "America250",
        "summary": "Historic parks, cultural sites, public lands, and commemorative itineraries tied to the America250 campaign.",
        "image": "real-america-250-background.webp",
        "paragraphs": [
            "Explore historic parks, cultural sites, scenic landscapes, and public lands connected to America's 250th anniversary. The mirror highlights places like San Francisco Maritime National Historical Park, Fort Point, Golden Gate, Yosemite, Yellowstone, Denali, and Cumberland Island.",
            "Trip ideas include pairing a historic tour with a nearby campground, reserving a timed-entry pass for a national park, or comparing wilderness permits before a backpacking route.",
            "The real site uses these editorial pages to connect inspiration with bookable inventory. Keeping those links inside the same mirror makes the homepage feel closer to the original product.",
        ],
    },
    "accessible-camping-trip-ideas": {
        "slug": "accessible-camping-trip-ideas",
        "title": "Accessible Camping Trip Ideas for National Parks and Forests",
        "kicker": "Accessibility",
        "summary": "Compare accessible campsites, paved access routes, parking notes, and nearby visitor services before departure.",
        "image": "real-point-reyes-campground.webp",
        "paragraphs": [
            "Accessible camping planning works best when travelers compare more than a single campsite photo. Arrival surfaces, restroom access, parking distance, and whether trailheads or viewpoints are reachable from camp all affect whether a listing fits the trip.",
            "Listings such as Point Reyes, Pinnacles, Glory Hole, and Sherando Lake show how accessibility details can appear across different agencies and reservation types. Some highlight accessible sites, while others emphasize parking, visitor-center routes, or day-use support.",
            "A practical workflow is to save two or three near-miss alternatives before checkout. That gives travelers backup options if an accessible site is no longer available or if the closest campground does not match the rest of the itinerary.",
        ],
    },
    "compare-pass-types-before-you-go": {
        "slug": "compare-pass-types-before-you-go",
        "title": "Compare Pass Types Before You Go",
        "kicker": "Passes & Entry",
        "summary": "Timed entry, site passes, and activity permits often look similar until you read the validity window and on-arrival rules.",
        "image": "real-passes-featured.webp",
        "paragraphs": [
            "Public-land passes can represent different products: timed vehicle entry, amenity access, activity permits, or all-day site admission. Looking only at the title can lead to booking the wrong product for the trip you have planned.",
            "A better comparison starts with three checks: how long the pass remains valid, whether it applies to one person or one vehicle, and whether the park also honors annual interagency passes or in-person payment.",
            "Yellowstone fishing permits, Rocky Mountain timed-entry products, and park site passes at Yosemite or Grand Teton all illustrate how similar booking cards can hide very different access rules.",
        ],
    },
    "fishing-permits-and-season-windows": {
        "slug": "fishing-permits-and-season-windows",
        "title": "Fishing Permits and Season Windows to Check Before You Travel",
        "kicker": "Activity Planning",
        "summary": "Fishing access often depends on permit duration, seasonal rules, and how the activity overlaps with campsite or backcountry reservations.",
        "image": "real-nav-fishing.webp",
        "paragraphs": [
            "Fishing-related products on Recreation.gov can behave differently from standard camping reservations. Some are valid for a short multi-day window, while others cover a broader season or are paired with separate access reservations.",
            "Travelers heading to Yellowstone, Lake Sonoma, Hemlock Cabin, or Oak Knoll usually need to compare fishing opportunities against surrounding facilities, launch access, and whether a separate camping or parking reservation is also required.",
            "When planning a mixed itinerary, keep the permit duration visible alongside campsite dates so that the activity window does not silently expire before the rest of the reservation does.",
        ],
    },
    "scenic-drives-and-timed-entry": {
        "slug": "scenic-drives-and-timed-entry",
        "title": "Scenic Drives, Timed Entry, and Arrival Planning",
        "kicker": "Trip Logistics",
        "summary": "Some of the highest-demand destinations require travelers to coordinate park-entry products with tours, parking, or overnight stays.",
        "image": "real-yosemite-site-pass-hero.jpeg",
        "paragraphs": [
            "Timed-entry products change how visitors should plan a trip. Arriving too early, too late, or at the wrong entrance can turn a fully reserved day into a partial itinerary with limited access.",
            "Yosemite, Rocky Mountain, Mariposa Grove, and other high-demand destinations often work best when visitors compare park-entry timing with shuttle inventory, parking reservations, and nearby overnight options.",
            "A strong plan starts by confirming the exact validity window on the booking card and then checking whether the destination also requires a separate parking, campsite, or activity reservation after entry.",
        ],
    },
    "cabin-packing-for-remote-stays": {
        "slug": "cabin-packing-for-remote-stays",
        "title": "Packing for Remote Cabin Stays",
        "kicker": "Cabins",
        "summary": "Remote cabins look simple on search cards, but the detail pages often contain the practical information that determines whether a stay is feasible.",
        "image": "066-preview-photo-of-hemlock-cabin.webp",
        "paragraphs": [
            "Cabin listings frequently compress important constraints into a few amenity tags. Travelers still need to read whether access is by trail, boat, or winter road, and whether heat, cookware, or potable water are actually provided.",
            "Hemlock Cabin, Samsing Cove Cabin, Tilly Jane A-Frame, and other remote stays show why 'cabin' alone is not enough. A wood stove, bunk configuration, or required boat access can completely change the trip plan.",
            "Before booking, compare the access method, the shelter type, and the weather-sensitive equipment requirements together. That prevents cabin trips from becoming last-minute logistics problems.",
        ],
    },
    "family-friendly-lake-camping": {
        "slug": "family-friendly-lake-camping",
        "title": "Family-Friendly Lake Camping to Save for Summer",
        "kicker": "Camping Inspiration",
        "summary": "Lake destinations often mix standard campsites, primitive areas, marinas, and reservable day-use options in the same region.",
        "image": "real-lake-sonoma-boat-in.webp",
        "paragraphs": [
            "Lake-focused itineraries reward comparison. One shoreline listing may be best for fishing, another for swimming, and another for larger family groups that need parking, showers, or a nearby marina.",
            "Berlin Lake, Lake Sonoma, Center Hill Lake, New Hogan Lake, and New Melones Lake all demonstrate how similarly named facilities can still vary sharply in access, available amenities, and reservation style.",
            "Families planning around weather changes should save both an overnight option and a nearby day-use fallback so the trip still works if the preferred campsite is no longer available.",
        ],
    },
    "ranger-programs-and-historic-tours": {
        "slug": "ranger-programs-and-historic-tours",
        "title": "Ranger Programs and Historic Tours Worth Pairing With a Weekend Trip",
        "kicker": "Tours & Programs",
        "summary": "Tour inventory can add structure to a trip, especially when it is paired with nearby camping, parking, or ferry-based access.",
        "image": "real-sf-maritime-tours.webp",
        "paragraphs": [
            "Historic tours and ranger-led programs often serve as the anchor activity for an otherwise flexible itinerary. They provide a fixed time around which parking, lodging, or campground plans can be organized.",
            "San Francisco Maritime, Fort Point, Voyageurs, and Campbell Creek show how tour pages can differ in accessibility, seating, route style, and whether the experience is outdoors, indoors, or on the water.",
            "When demand is high, save a nearby campground or day-use option before purchasing tickets. That makes it easier to keep the weekend intact if travel timing changes after the core reservation is made.",
        ],
    },
    "wilderness-permit-checklist": {
        "slug": "wilderness-permit-checklist",
        "title": "A Wilderness Permit Checklist Before Checkout",
        "kicker": "Backcountry",
        "summary": "Permit detail pages hide high-value clues in the trailhead, quota, and season sections that should be reviewed before booking.",
        "image": "real-desolation-hero.webp",
        "paragraphs": [
            "Backcountry permits should be read as operational documents, not just product pages. Trailhead constraints, zone rules, quota windows, and printing requirements often determine whether a permit actually matches the route in mind.",
            "Desolation Wilderness, Inyo, Aravaipa Canyon, Canyonlands, and Yosemite wilderness products illustrate how different agencies expose similar information with different terminology.",
            "Before checkout, compare the entry point, the permit duration, whether day-use and overnight products are separated, and what document or digital confirmation must be carried in the field.",
        ],
    },
    "coastal-trip-combos": {
        "slug": "coastal-trip-combos",
        "title": "Build a Better Coastal Trip by Combining Camping, Tours, and Day Use",
        "kicker": "Coastal Planning",
        "summary": "Coastal inventory tends to be strongest when travelers mix overnight access with a second reservation type nearby.",
        "image": "real-aquatic-park-cove.webp",
        "paragraphs": [
            "Many coastal trips work better when visitors book more than one inventory type. A waterfront campground, nearby shuttle or parking reservation, and a historic or ranger-led tour can create a more complete itinerary than any single listing alone.",
            "Point Reyes, Aquatic Park Cove, Fort Point, San Francisco Maritime, and Cumberland Island all show how beaches and waterfront access can spread across camping, tours, anchoring, and permit workflows.",
            "The best comparison questions are often logistical: which listing controls overnight access, which one controls arrival timing, and which one adds the experience you want once you are already in the area.",
        ],
    },
}

DETAIL_GALLERIES = {
    "point-reyes-national-seashore-campground": [
        ("real-point-reyes-gallery-oak.webp", "Large oak tree at a Point Reyes campsite"),
        ("real-point-reyes-gallery-drakes.webp", "Campsite with distant views of Drakes Bay"),
        ("real-point-reyes-gallery-campsite.webp", "Campsite with picnic table and bear box"),
    ],
    "desolation-wilderness-permit": [
        ("real-desolation-hero.webp", "High alpine panorama in Desolation Wilderness"),
        ("real-desolation-granite.webp", "Granite peaks and alpine lakes in Desolation Wilderness"),
        ("real-desolation-lake.webp", "Lake view inside Desolation Wilderness"),
    ],
}

INSPIRATION_CARDS = [
    {
        "title": "Campfire Safety Tips",
        "kicker": "Location Spotlight",
        "image": "real-a250-fireworks.webp",
        "href": "help_center",
    },
    {
        "title": "Plan Ahead and Play It Safe",
        "kicker": "Trip Planning",
        "image": "real-point-reyes-seashore.webp",
        "href": "help_center",
    },
    {
        "title": "10 Beautiful Beach Destinations",
        "kicker": "Inspiration",
        "image": "real-aquatic-park-cove.webp",
        "href": "search",
    },
]

STATE_CENTERS = {
    "AK": (63.7, -149.5), "AZ": (34.2, -111.7), "CA": (36.7, -119.4),
    "CO": (39.0, -105.5), "GA": (32.6, -83.4), "KS": (38.5, -98.2),
    "KY": (37.6, -85.2), "MI": (44.3, -85.5), "MN": (46.1, -94.3),
    "MS": (32.7, -89.7), "NC": (35.5, -79.4), "NM": (34.5, -106.1),
    "NY": (42.9, -75.5), "OH": (40.3, -82.7), "OK": (35.6, -97.5),
    "OR": (43.9, -120.5), "TN": (35.8, -86.4), "TX": (31.1, -99.3),
    "UT": (39.3, -111.6), "VA": (37.7, -78.2), "WA": (47.4, -120.7),
    "WI": (44.6, -89.7), "WY": (43.0, -107.6), "FL": (27.8, -81.7),
    "ME": (45.2, -69.0),
}

DEFAULT_MAP_CENTER = (39.6, -98.5)

US_STATES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"),
    ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"),
    ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
    ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
    ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
    ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"),
    ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"),
    ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
    ("WI", "Wisconsin"), ("WY", "Wyoming"),
]
STATE_NAMES = dict(US_STATES)

DETAIL_ALERTS = {
    "desolation-wilderness-permit": "Tahoe Rim Trail thru-hike permits and quota-zone availability can change during the 2026 season. Review trailhead restrictions and plan backup zones before reserving.",
}

DETAIL_OPTION_OVERRIDES = {
    "desolation-wilderness-permit": ["Zone 06 Rubicon", "Zone 18 Eagle", "Zone 33 Aloha", "Zone 45 Twin Lakes"],
    "yellowstone-national-park-fishing-permit": ["3-Day Individual Permit", "7-Day Individual Permit", "Season Permit"],
}

BOOKING_OPTION_SPAN_OVERRIDES = {
    "yellowstone-national-park-fishing-permit": {
        "3-Day Individual Permit": 2,
        "7-Day Individual Permit": 6,
    },
}

BOOKING_OPTION_END_DATE_OVERRIDES = {
    "yellowstone-national-park-fishing-permit": {
        "Season Permit": "2026-12-31",
    },
}

SITEPASS_ID_TO_SLUG = {
    74296: "yosemite-national-park-site-pass",
}

SITE_PASS_CONTENT = {
    "default": {
        "page_title": "Site Pass Selection",
        "alert": "Since January 1, 2026, changes to National Park Entrance Fees and Passes for non-residents have taken effect.",
        "notice": "",
        "about": "This site pass can be used digitally on a phone or tablet and may also be honored alongside other valid interagency pass products. Review park-specific operating rules before arrival.",
        "about_link_label": "Fees & Passes web page.",
        "hero_image": "",
    },
    "yosemite-national-park-site-pass": {
        "page_title": "Site Pass Selection",
        "alert": "Since January 1, 2026, changes to National Park Entrance Fees and Passes for non-residents have taken effect.",
        "notice": "Non-U.S. Residents must pay an additional fee for each person 16 years or older in the party.",
        "about": "Yosemite National Park also accepts payment in person during Operating Hours and honors valid America the Beautiful Passes (Annual, Senior, Access, Military, etc.). For more information, visit the park's Fees & Passes web page.",
        "about_link_label": "Fees & Passes web page.",
        "hero_image": "real-yosemite-site-pass-hero.jpeg",
    },
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), default="")
    home_city = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    name = db.Column(db.String(220), nullable=False)
    inventory_type = db.Column(db.String(40), nullable=False, index=True)
    agency = db.Column(db.String(80), nullable=False)
    parent_area = db.Column(db.String(180), default="")
    location = db.Column(db.String(180), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    distance_miles = db.Column(db.Float, default=0)
    price = db.Column(db.Numeric(8, 2), default=0)
    price_unit = db.Column(db.String(40), default="night")
    rating = db.Column(db.Float, default=4.0)
    review_count = db.Column(db.Integer, default=0)
    available = db.Column(db.Boolean, default=True)
    accessible = db.Column(db.Boolean, default=False)
    reservable = db.Column(db.Boolean, default=True)
    image = db.Column(db.String(220), default="")
    short_description = db.Column(db.Text, default="")
    long_description = db.Column(db.Text, default="")
    amenities_json = db.Column(db.Text, default="[]")
    activities_json = db.Column(db.Text, default="[]")
    rules_json = db.Column(db.Text, default="[]")
    checkin_date = db.Column(db.String(20), default="2026-05-15")
    checkout_date = db.Column(db.String(20), default="2026-05-17")
    capacity = db.Column(db.Integer, default=4)
    tags = db.Column(db.String(500), default="")

    campsites = db.relationship("Campsite", backref="facility", cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="facility", cascade="all, delete-orphan")

    @property
    def label(self) -> str:
        return INVENTORY_LABELS.get(self.inventory_type, self.inventory_type.title())

    @property
    def amenities(self) -> list[str]:
        return json.loads(self.amenities_json or "[]")

    @property
    def activities(self) -> list[str]:
        return json.loads(self.activities_json or "[]")

    @property
    def rules(self) -> list[str]:
        return json.loads(self.rules_json or "[]")

    @property
    def price_display(self) -> str:
        amount = float(self.price or 0)
        if amount <= 0:
            return "Free"
        if self.price_unit == "pass":
            return f"${amount:,.0f} / pass"
        if self.price_unit == "permit":
            return f"${amount:,.0f} / permit"
        if self.price_unit == "ticket":
            return f"${amount:,.0f} / ticket"
        return f"${amount:,.0f} / {self.price_unit}"

    @property
    def trip_window(self) -> str:
        return _date_window_label(self.checkin_date, self.checkout_date)

    @property
    def image_url(self) -> str:
        fallback = "008-a-common-yellowthroat-warbler-perched-among-lush-green-vegetation-at-p.webp"
        return url_for("static", filename=f"images/{self.image or fallback}")


class Campsite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    name = db.Column(db.String(140), nullable=False)
    site_type = db.Column(db.String(80), default="Standard")
    nightly_rate = db.Column(db.Numeric(8, 2), default=0)
    capacity = db.Column(db.Integer, default=4)
    accessible = db.Column(db.Boolean, default=False)
    available_dates = db.Column(db.String(250), default="")

    @property
    def dates(self) -> list[str]:
        return [d.strip() for d in (self.available_dates or "").split(",") if d.strip()]


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, default=5)
    body = db.Column(db.Text, nullable=False)
    visit_date = db.Column(db.String(40), default="April 2026")


class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    label = db.Column(db.String(80), default="Home")
    street = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=True)


class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    card_type = db.Column(db.String(40), default="Visa")
    last4 = db.Column(db.String(4), nullable=False)
    expiry = db.Column(db.String(7), default="12/28")
    is_default = db.Column(db.Boolean, default=True)


class SavedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    facility = db.relationship("Facility")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    campsite_id = db.Column(db.Integer, db.ForeignKey("campsite.id"), nullable=True)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    guests = db.Column(db.Integer, default=2)
    quantity = db.Column(db.Integer, default=1)
    facility = db.relationship("Facility")
    campsite = db.relationship("Campsite")

    @property
    def total(self) -> Decimal:
        nights = _nights(self.start_date, self.end_date)
        base = self.campsite.nightly_rate if self.campsite else self.facility.price
        multiplier = max(nights, 1) if self.facility.inventory_type == "camping" else self.quantity
        return Decimal(base or 0) * multiplier


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    campsite_name = db.Column(db.String(160), default="")
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    guests = db.Column(db.Integer, default=2)
    total_cost = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(40), default="Upcoming")
    confirmation_code = db.Column(db.String(40), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    facility = db.relationship("Facility")


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    cart_count = 0
    saved_ids: set[int] = set()
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        saved_ids = {item.facility_id for item in SavedItem.query.filter_by(user_id=current_user.id).all()}
    return {"inventory_labels": INVENTORY_LABELS, "cart_count": cart_count, "saved_ids": saved_ids, "today": date(2026, 5, 12)}


def _tokens(query: str) -> list[str]:
    return [t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 1 and t not in STOP_WORDS]


def _facility_haystack(facility: Facility) -> str:
    state_full_name = STATE_NAMES.get(facility.state, facility.state)
    parts = [
        facility.name, facility.label, facility.agency, facility.parent_area,
        facility.location, facility.state, facility.short_description,
        state_full_name, facility.long_description, facility.tags, " ".join(facility.amenities),
        " ".join(facility.activities),
        "accessible" if facility.accessible else "",
        "available" if facility.available else "",
        "reservable" if facility.reservable else "",
    ]
    return " ".join(parts).lower()


def _scored_search(query: str, items: list[Facility]) -> list[Facility]:
    tokens = _tokens(query)
    if not tokens:
        return items
    scored: list[tuple[Facility, int]] = []
    for item in items:
        haystack = _facility_haystack(item)
        score = sum(1 for token in tokens if token in haystack)
        if score > 0:
            scored.append((item, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].distance_miles, -pair[0].rating, pair[0].name))
    return [item for item, _ in scored]


def _filtered_facilities(args) -> list[Facility]:
    query = Facility.query
    inventory_type = args.get("inventory_type") or args.get("type")
    if inventory_type:
        query = query.filter(Facility.inventory_type == inventory_type)
    agency = args.get("agency")
    if agency:
        query = query.filter(Facility.agency == agency)
    activity = args.get("activity")
    if activity:
        query = query.filter(or_(Facility.activities_json.ilike(f"%{activity}%"), Facility.tags.ilike(f"%{activity}%")))
    if args.get("accessible") == "1":
        query = query.filter(Facility.accessible.is_(True))
    if args.get("available") == "1":
        query = query.filter(Facility.available.is_(True))
    max_price = args.get("max_price")
    if max_price:
        try:
            query = query.filter(Facility.price <= float(max_price))
        except ValueError:
            pass
    results = _scored_search(args.get("q", "").strip(), query.all())
    sort = args.get("sort", "best")
    if sort == "price":
        results.sort(key=lambda f: (float(f.price or 0), f.name))
    elif sort == "rating":
        results.sort(key=lambda f: (-f.rating, -f.review_count, f.name))
    elif sort == "distance":
        results.sort(key=lambda f: (f.distance_miles, f.name))
    elif sort == "available":
        results.sort(key=lambda f: (not f.available, f.distance_miles, f.name))
    return results


def _nights(start_date: str, end_date: str) -> int:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        return max((end - start).days, 1)
    except ValueError:
        return 1


def _date_window_label(start_date: str, end_date: str) -> str:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return "PLAN AHEAD"
    if start.month == end.month:
        return f"{start.strftime('%b').upper()} {start.day} - {end.day}"
    return f"{start.strftime('%b').upper()} {start.day} - {end.strftime('%b').upper()} {end.day}"


def _pretty_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return value


def _display_trip_window(start_date: str, end_date: str) -> str:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        if start_date and end_date:
            return f"{start_date} to {end_date}"
        return start_date or end_date or ""
    if start == end:
        return start.strftime("%b %d, %Y")
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%b %d')} - {end.day}, {end.year}"
    if start.year == end.year:
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
    return f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"


def _booking_end_date(
    start_date: str,
    option: str,
    option_spans: dict[str, int],
    option_end_dates: dict[str, str],
    fallback_end_date: str,
) -> str:
    if option in option_end_dates:
        return option_end_dates[option]
    if option in option_spans:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            return (start + timedelta(days=option_spans[option])).isoformat()
        except ValueError:
            return fallback_end_date
    return fallback_end_date


@app.template_filter("trip_window")
def trip_window_filter(value: object) -> str:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return _display_trip_window(str(value[0]), str(value[1]))
    return str(value or "")


def _stable_offset(seed: str, scale: float) -> float:
    total = sum((idx + 11) * ord(char) for idx, char in enumerate(seed))
    return (((total % 2000) / 1000) - 1) * scale


def _relative_map_position(lat: float, lng: float) -> tuple[float, float]:
    clamped_lng = min(max(lng, -124.5), -66.5)
    clamped_lat = min(max(lat, 24.0), 49.5)
    x = ((clamped_lng + 124.5) / 58.0) * 100
    y = ((49.5 - clamped_lat) / 25.5) * 100
    return round(min(max(x, 6), 94), 2), round(min(max(y, 8), 92), 2)


def _facility_map_point(facility: Facility, rank: int = 1) -> dict[str, object]:
    base_lat, base_lng = STATE_CENTERS.get(facility.state, DEFAULT_MAP_CENTER)
    lat = round(base_lat + _stable_offset(f"{facility.slug}-lat", 1.45), 4)
    lng = round(base_lng + _stable_offset(f"{facility.slug}-lng", 1.95), 4)
    x, y = _relative_map_position(lat, lng)
    return {
        "id": facility.id,
        "slug": facility.slug,
        "name": facility.name,
        "label": facility.label,
        "location": f"{facility.location}, {facility.state}",
        "distance": f"{facility.distance_miles:.0f} miles away",
        "rating": f"{facility.rating:.1f} rating",
        "reviews": f"{facility.review_count:,} reviews",
        "price_display": facility.price_display,
        "href": url_for("facility_detail", slug=facility.slug),
        "lat": lat,
        "lng": lng,
        "x": x,
        "y": y,
        "rank": rank,
        "available": facility.available,
        "accessible": facility.accessible,
    }


def _map_entry(facility: Facility, rank: int = 1) -> dict[str, object]:
    return {"facility": facility, "point": _facility_map_point(facility, rank)}


def _build_experience_panel(panel_spec: dict[str, object], limit: int = 5) -> dict[str, object]:
    inventory_types = panel_spec["inventory_types"]
    available_results = (
        Facility.query.filter(Facility.inventory_type.in_(inventory_types), Facility.available.is_(True))
        .order_by(Facility.distance_miles, Facility.rating.desc(), Facility.review_count.desc())
        .all()
    )
    ranked_results = list(available_results)
    seen_ids = {facility.id for facility in ranked_results}
    if len(ranked_results) < limit:
        fallback_results = (
            Facility.query.filter(Facility.inventory_type.in_(inventory_types))
            .order_by(Facility.rating.desc(), Facility.review_count.desc(), Facility.distance_miles)
            .all()
        )
        for facility in fallback_results:
            if facility.id in seen_ids:
                continue
            ranked_results.append(facility)
            seen_ids.add(facility.id)
            if len(ranked_results) >= limit:
                break
    selected = ranked_results[:limit]
    entries = [_map_entry(facility, rank=index + 1) for index, facility in enumerate(selected)]
    return {
        "key": panel_spec["key"],
        "label": panel_spec["label"],
        "description": panel_spec["description"],
        "entries": entries,
        "count": len(entries),
    }


def _cart_total(items: list[CartItem]) -> Decimal:
    return sum((item.total for item in items), Decimal("0"))


def _next_confirmation() -> str:
    return f"RG-2026-{Reservation.query.count() + 1:05d}"


def _facilities_by_slug(slugs: list[str]) -> list[Facility]:
    rows = Facility.query.filter(Facility.slug.in_(slugs)).all()
    by_slug = {facility.slug: facility for facility in rows}
    return [by_slug[slug] for slug in slugs if slug in by_slug]


def _detail_gallery(facility: Facility) -> list[dict[str, str]]:
    gallery = DETAIL_GALLERIES.get(facility.slug)
    if not gallery:
        gallery = [
            (facility.image or "real-point-reyes-campground.webp", f"Photo of {facility.name}"),
            ("real-point-reyes-seashore.webp", f"Landscape near {facility.name}"),
            ("real-pinnacles-national-park.webp", "Nearby public lands destination"),
        ]
    return [
        {"src": url_for("static", filename=f"images/{filename}"), "alt": alt}
        for filename, alt in gallery
    ]


def _home_tab_results(inventory_type: str, limit: int = 10) -> list[Facility]:
    results = (
        Facility.query.filter_by(inventory_type=inventory_type, available=True)
        .order_by(Facility.distance_miles, Facility.rating.desc(), Facility.review_count.desc())
        .limit(limit)
        .all()
    )
    if len(results) < limit:
        seen = {facility.id for facility in results}
        fallback = Facility.query.filter_by(inventory_type=inventory_type)
        if seen:
            fallback = fallback.filter(~Facility.id.in_(seen))
        results.extend(
            fallback.order_by(Facility.rating.desc(), Facility.review_count.desc(), Facility.distance_miles)
            .limit(limit - len(results))
            .all()
        )
    if len(results) < limit and inventory_type == "day_use":
        seen = {facility.id for facility in results}
        related = Facility.query.filter(Facility.inventory_type.in_(["passes", "tickets"]))
        if seen:
            related = related.filter(~Facility.id.in_(seen))
        results.extend(
            related.order_by(Facility.distance_miles, Facility.rating.desc(), Facility.review_count.desc())
            .limit(limit - len(results))
            .all()
        )
    return results


def _booking_config(facility: Facility) -> dict[str, object]:
    titles = {
        "camping": "Available Campsites",
        "tickets": "Available Tickets",
        "permits": "Available Permits",
        "passes": "Available Passes",
        "day_use": "Available Day Use",
        "lottery": "Available Lotteries",
    }
    intros = {
        "camping": "Select travel dates and add an available site to your cart.",
        "tickets": "Select an available day and reserve timed entry or tour inventory.",
        "permits": "Select an available day to reserve a permit.",
        "passes": "Choose the pass type and entry date before checkout.",
        "day_use": "Reserve parking, picnic, or day-use access before arrival.",
        "lottery": "Choose a season window and enter the latest lottery cycle.",
    }
    option_label = {
        "camping": "Select Campsite",
        "tickets": "Select Experience",
        "permits": "Select Destination Zone",
        "passes": "Select Pass Type",
        "day_use": "Select Access Type",
        "lottery": "Select Lottery Window",
    }.get(facility.inventory_type, "Select Option")
    options: list[str]
    if facility.inventory_type == "camping" and facility.campsites:
        options = [f"{site.name} · {site.site_type}" for site in facility.campsites[:5]]
    else:
        options = DETAIL_OPTION_OVERRIDES.get(facility.slug, facility.activities[:4] or [facility.label])
    option_spans = BOOKING_OPTION_SPAN_OVERRIDES.get(facility.slug, {})
    option_end_dates = BOOKING_OPTION_END_DATE_OVERRIDES.get(facility.slug, {})
    default_option = options[0] if options else ""
    quantity_label = "Guests" if facility.inventory_type == "camping" else "Group Members"
    date_selection_mode = "window"
    calendar_span_days = 2
    primary_date_label = "Entry Date"
    secondary_date_label = "Reservation Window"
    end_date_value = facility.checkout_date
    selected_status_label = _display_trip_window(facility.checkin_date, facility.checkout_date)
    if facility.inventory_type == "camping":
        date_selection_mode = "range"
        calendar_span_days = max(_nights(facility.checkin_date, facility.checkout_date), 1)
        secondary_date_label = "Departure Date"
    elif facility.inventory_type in {"passes", "tickets", "day_use"}:
        date_selection_mode = "single_day"
        calendar_span_days = 0
        primary_date_label = "Visit Date"
        secondary_date_label = ""
        end_date_value = facility.checkin_date
        selected_status_label = _pretty_date(facility.checkin_date)
    if default_option and (default_option in option_spans or default_option in option_end_dates):
        date_selection_mode = "window"
        primary_date_label = "Visit Date"
        secondary_date_label = "Valid For"
        end_date_value = _booking_end_date(
            facility.checkin_date,
            default_option,
            option_spans,
            option_end_dates,
            facility.checkout_date,
        )
        calendar_span_days = max(_nights(facility.checkin_date, end_date_value), 0)
        selected_status_label = _display_trip_window(facility.checkin_date, end_date_value)
    return {
        "title": titles.get(facility.inventory_type, "Availability"),
        "intro": intros.get(facility.inventory_type, "Review current availability before booking."),
        "option_label": option_label,
        "options": options,
        "option_span_days": option_spans,
        "option_end_dates": option_end_dates,
        "quantity_label": quantity_label,
        "primary_cta": "Book Now" if facility.reservable else "Details Only",
        "date_selection_mode": date_selection_mode,
        "calendar_span_days": calendar_span_days,
        "primary_date_label": primary_date_label,
        "secondary_date_label": secondary_date_label,
        "entry_date_label": _pretty_date(facility.checkin_date),
        "window_label": _display_trip_window(facility.checkin_date, facility.checkout_date),
        "end_date_value": end_date_value,
        "selected_status_label": selected_status_label,
    }


def _important_dates(facility: Facility) -> list[dict[str, str]]:
    if facility.inventory_type == "permits":
        try:
            checkin = datetime.strptime(facility.checkin_date, "%Y-%m-%d").date()
        except ValueError:
            checkin = date(2026, 5, 15)
        return [
            {"date": _pretty_date(facility.checkin_date), "info": "Mirror entry window opens for the first available permit date."},
            {"date": _pretty_date((checkin - timedelta(days=7)).isoformat()), "info": "Printable permit window typically opens seven days before entry."},
            {"date": "Sep 30, 2026", "info": "Quota-season demand usually relaxes after this period for wilderness inventory."},
        ]
    return [
        {"date": _pretty_date(facility.checkin_date), "info": f"Primary arrival date in this mirror for {facility.name}."},
        {"date": _pretty_date(facility.checkout_date), "info": "Sample departure date used for current availability and trip pricing."},
        {"date": facility.trip_window.title(), "info": "Current featured weekend window displayed across the site."},
    ]


def _review_breakdown(facility: Facility) -> list[dict[str, object]]:
    total = max(int(facility.review_count or 0), len(facility.reviews), 1)
    avg = max(1.0, min(5.0, float(facility.rating or 4.0)))
    if avg >= 4.6:
        weights = {5: 0.72, 4: 0.18, 3: 0.06, 2: 0.02, 1: 0.02}
    elif avg >= 4.2:
        weights = {5: 0.58, 4: 0.24, 3: 0.10, 2: 0.04, 1: 0.04}
    elif avg >= 3.8:
        weights = {5: 0.42, 4: 0.28, 3: 0.16, 2: 0.08, 1: 0.06}
    else:
        weights = {5: 0.30, 4: 0.24, 3: 0.20, 2: 0.14, 1: 0.12}
    counts = {stars: int(round(total * ratio)) for stars, ratio in weights.items()}
    delta = total - sum(counts.values())
    counts[5] += delta
    return [
        {
            "stars": stars,
            "count": counts[stars],
            "percent": max((counts[stars] / total) * 100, 0),
        }
        for stars in range(5, 0, -1)
    ]


def _detail_resources(facility: Facility) -> list[dict[str, str]]:
    resources = [
        {
            "label": f"{facility.parent_area or facility.agency} overview",
            "href": url_for("search", q=facility.parent_area or facility.agency),
        },
        {
            "label": f"More {facility.label.lower()} near {facility.location}",
            "href": url_for("search", q=facility.location, inventory_type=facility.inventory_type),
        },
        {
            "label": "Rules & Reservation Policies",
            "href": f"{url_for('help_center')}#passes-permits",
        },
        {
            "label": "Contact & Support Paths",
            "href": f"{url_for('help_center')}#contact",
        },
    ]
    return resources


def _site_pass_context(facility: Facility) -> dict[str, str]:
    content = {**SITE_PASS_CONTENT["default"], **SITE_PASS_CONTENT.get(facility.slug, {})}
    hero_image = content.get("hero_image") or facility.image_url
    if hero_image and not str(hero_image).startswith("http"):
        hero_image = url_for("static", filename=f"images/{hero_image}")
    return {
        "page_title": content["page_title"],
        "alert": content["alert"],
        "notice": content["notice"],
        "about": content["about"],
        "about_link_label": content["about_link_label"],
        "hero_image": hero_image,
        "interagency_image": url_for("static", filename="images/real-interagency-passes.webp"),
    }


@app.route("/")
def index():
    featured = Facility.query.filter_by(available=True).order_by(Facility.rating.desc()).limit(8).all()
    nearby = _facilities_by_slug(HOME_NEARBY_SLUGS)
    seen = {facility.id for facility in nearby}
    fallback_query = Facility.query.filter_by(inventory_type="camping", available=True)
    if seen:
        fallback_query = fallback_query.filter(~Facility.id.in_(seen))
    nearby.extend(
        fallback_query.order_by(Facility.distance_miles, Facility.rating.desc())
        .limit(max(12 - len(nearby), 0))
        .all()
    )
    passes = Facility.query.filter(Facility.inventory_type.in_(["passes", "permits"])).order_by(Facility.review_count.desc()).limit(6).all()
    experience_panels = [_build_experience_panel(spec) for spec in HOME_EXPERIENCE_PANELS]
    home_map_markers = [
        {**entry["point"], "panel_key": panel["key"]}
        for panel in experience_panels
        for entry in panel["entries"]
    ]
    home_map_center = home_map_markers[0] if home_map_markers else {"lat": DEFAULT_MAP_CENTER[0], "lng": DEFAULT_MAP_CENTER[1]}
    popular_location_names = sorted(
        {
            facility.parent_area.strip()
            for facility in Facility.query.filter(Facility.parent_area != "").all()
            if facility.parent_area.strip()
        },
        key=str.lower,
    )
    state_links = [{"code": code, "name": name, "href": url_for("search", q=name)} for code, name in US_STATES]
    home_tab_panels = [
        {
            "key": "all",
            "type": "explore_all",
        },
        {
            "key": "camping",
            "type": "inventory",
            "title": "Available This Weekend",
            "description": "Campgrounds with upcoming availability.",
            "inventory_type": "camping",
            "placeholder": "Search by location or campground name",
            "secondary": "Ways to Stay",
            "tertiary": "When",
            "entries": _home_tab_results("camping", limit=10),
        },
        {
            "key": "tickets",
            "type": "inventory",
            "title": "Available This Weekend",
            "description": "Tickets and tours with upcoming availability.",
            "inventory_type": "tickets",
            "placeholder": "Search by location or facility name",
            "secondary": "Time",
            "tertiary": "mm/dd/yyyy",
            "entries": _home_tab_results("tickets", limit=10),
        },
        {
            "key": "permits",
            "type": "inventory",
            "title": "Permits Near You",
            "description": "Closest entrance, activity, and vehicle permits.",
            "inventory_type": "permits",
            "placeholder": "Search by location or facility name",
            "secondary": "",
            "tertiary": "",
            "entries": _home_tab_results("permits", limit=10),
        },
        {
            "key": "day_use",
            "type": "inventory",
            "title": "Available This Weekend",
            "description": "Venues and day-use facilities with upcoming availability.",
            "inventory_type": "day_use",
            "placeholder": "Search by location or facility name",
            "secondary": "",
            "tertiary": "mm/dd/yyyy",
            "entries": _home_tab_results("day_use", limit=10),
        },
        {
            "key": "ai",
            "type": "ai",
            "placeholder": "Tell us what kind of outdoor recreation you want to reserve. Be as descriptive as possible.",
            "examples": HOME_AI_EXAMPLES,
        },
    ]
    promo_features = [
        {
            "eyebrow": "Mobile App",
            "title": "Adventure is at Your Fingertips",
            "body": "Find campgrounds, timed entry, and permits on the go with trip details saved in one place.",
            "image": url_for("static", filename="images/real-mobile-app-featured-background.webp"),
            "href": url_for("search", inventory_type="camping"),
        },
        {
            "eyebrow": "Passes",
            "title": "Plan Day Use Ahead of Time",
            "body": "Reserve high-demand entry and amenity passes before your trip window opens up.",
            "image": url_for("static", filename="images/real-passes-featured.webp"),
            "href": url_for("passes"),
        },
    ]
    category_tiles = [
        {
            "key": key,
            "label": label,
            "image": url_for("static", filename=f"images/{image}"),
            "description": description,
            "href": url_for("category", inventory_type=key) if key in INVENTORY_LABELS else url_for("search", q=search_query or label),
        }
        for key, label, image, description, search_query in CATEGORY_TILES
    ]
    article_cards = [
        {
            **ARTICLE_LIBRARY[slug],
            "href": url_for("article_detail", slug=slug),
            "image_url": url_for("static", filename=f"images/{ARTICLE_LIBRARY[slug]['image']}"),
        }
        for slug in HOME_ARTICLE_SLUGS
    ]
    return render_template(
        "index.html",
        featured=featured,
        nearby=nearby,
        passes=passes,
        popular_location_names=popular_location_names,
        state_links=state_links,
        home_tab_panels=home_tab_panels,
        experience_panels=experience_panels,
        home_map_markers=home_map_markers,
        home_map_center=home_map_center,
        promo_features=promo_features,
        category_tiles=category_tiles,
        article_cards=article_cards,
        anchor_city="Santa Clara, CA",
    )


@app.route("/search")
def search():
    results = _filtered_facilities(request.args)
    agencies = [row[0] for row in db.session.query(Facility.agency).distinct().order_by(Facility.agency).all()]
    search_entries = [_map_entry(facility, rank=index + 1) for index, facility in enumerate(results[:24])]
    return render_template("search.html", results=results, agencies=agencies, args=request.args, search_entries=search_entries)


@app.route("/category/<inventory_type>")
def category(inventory_type: str):
    if inventory_type not in INVENTORY_LABELS:
        abort(404)
    args = request.args.to_dict(flat=True)
    args["inventory_type"] = inventory_type
    results = _filtered_facilities(args)
    return render_template("category.html", inventory_type=inventory_type, results=results)


@app.route("/camping")
def camping():
    return redirect(url_for("category", inventory_type="camping"))


@app.route("/tickets")
def tickets():
    return redirect(url_for("category", inventory_type="tickets"))


@app.route("/permits")
def permits():
    return redirect(url_for("category", inventory_type="permits"))


@app.route("/permits/<int:permit_id>")
def permit_detail_alias(permit_id: int):
    if permit_id == 233261:
        return redirect(url_for("facility_detail", slug="desolation-wilderness-permit"))
    abort(404)


@app.route("/sitepass/<int:sitepass_id>")
def sitepass_detail_alias(sitepass_id: int):
    slug = SITEPASS_ID_TO_SLUG.get(sitepass_id)
    if slug:
        return redirect(url_for("facility_detail", slug=slug))
    abort(404)


@app.route("/passes")
def passes():
    return redirect(url_for("category", inventory_type="passes"))


@app.route("/day-use")
def day_use():
    return redirect(url_for("category", inventory_type="day_use"))


@app.route("/lottery")
def lottery():
    return redirect(url_for("category", inventory_type="lottery"))


@app.route("/facility/<slug>")
def facility_detail(slug: str):
    facility = Facility.query.filter_by(slug=slug).first_or_404()
    related = Facility.query.filter(Facility.inventory_type == facility.inventory_type, Facility.id != facility.id).order_by(Facility.rating.desc()).limit(4).all()
    detail_map_entries = [_map_entry(item, rank=index + 1) for index, item in enumerate([facility] + related[:3])]
    recent_reviews = Review.query.filter_by(facility_id=facility.id).order_by(Review.id.desc()).limit(48).all()
    current_author = ""
    if current_user.is_authenticated:
        current_author = current_user.display_name or current_user.username
    is_site_pass = facility.inventory_type == "passes" and "site pass" in facility.name.lower()
    template_name = "site_pass_detail.html" if is_site_pass else "facility_detail.html"
    return render_template(
        template_name,
        facility=facility,
        related=related,
        detail_map_entries=detail_map_entries,
        gallery_images=_detail_gallery(facility),
        detail_alert=DETAIL_ALERTS.get(facility.slug),
        booking_config=_booking_config(facility),
        important_dates=_important_dates(facility),
        review_breakdown=_review_breakdown(facility),
        recent_reviews=recent_reviews,
        current_review_author=current_author,
        detail_resources=_detail_resources(facility),
        detail_map_markers=[entry["point"] for entry in detail_map_entries],
        state_name=STATE_NAMES.get(facility.state, facility.state),
        site_pass_context=_site_pass_context(facility),
    )


@app.route("/facility/<slug>/reviews", methods=["POST"])
@login_required
def add_review(slug: str):
    facility = Facility.query.filter_by(slug=slug).first_or_404()
    body = request.form.get("body", "").strip()
    visit_date = request.form.get("visit_date", "").strip() or datetime.utcnow().strftime("%B %Y")
    try:
        rating = max(1, min(5, int(request.form.get("rating", "5"))))
    except ValueError:
        rating = 5
    if len(body) < 12:
        flash("Write at least a short trip note before submitting a review.", "danger")
        return redirect(url_for("facility_detail", slug=slug, _anchor="reviews"))
    review = Review(
        facility_id=facility.id,
        author=current_user.display_name or current_user.username,
        rating=rating,
        body=body,
        visit_date=visit_date,
    )
    aggregate_count = int(facility.review_count or 0)
    aggregate_rating = float(facility.rating or 0)
    facility.rating = round((((aggregate_rating * aggregate_count) + rating) / (aggregate_count + 1)) if aggregate_count else rating, 1)
    facility.review_count = aggregate_count + 1
    db.session.add(review)
    db.session.commit()
    flash("Review submitted.", "success")
    return redirect(url_for("facility_detail", slug=slug, _anchor="reviews"))


@app.route("/facility/<slug>/save", methods=["POST"])
@login_required
def save_facility(slug: str):
    facility = Facility.query.filter_by(slug=slug).first_or_404()
    existing = SavedItem.query.filter_by(user_id=current_user.id, facility_id=facility.id).first()
    if existing:
        db.session.delete(existing)
        flash("Removed from your saved list.", "info")
    else:
        db.session.add(SavedItem(user_id=current_user.id, facility_id=facility.id))
        flash("Saved to your trip list.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("facility_detail", slug=slug))


@app.route("/cart")
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    return render_template("cart.html", items=items, total=_cart_total(items))


@app.route("/cart/add/<int:facility_id>", methods=["POST"])
@login_required
def add_to_cart(facility_id: int):
    facility = Facility.query.get_or_404(facility_id)
    if not facility.reservable:
        flash("This location is informational only and cannot be reserved.", "warning")
        return redirect(url_for("facility_detail", slug=facility.slug))
    start_date = request.form.get("start_date") or facility.checkin_date
    end_date = request.form.get("end_date") or facility.checkout_date
    guests = max(int(request.form.get("guests") or 2), 1)
    campsite_id = request.form.get("campsite_id")
    campsite = Campsite.query.get(int(campsite_id)) if campsite_id else None
    db.session.add(CartItem(user_id=current_user.id, facility_id=facility.id, campsite_id=campsite.id if campsite else None, start_date=start_date, end_date=end_date, guests=guests, quantity=max(int(request.form.get("quantity") or 1), 1)))
    db.session.commit()
    flash(f"Added {facility.name} to your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_cart_item(item_id: int):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Cart item removed.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("search"))
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).order_by(PaymentMethod.is_default.desc()).all()
    total = _cart_total(items)
    if request.method == "POST":
        if not addresses or not payments:
            flash("Add a saved address and payment method before checkout.", "danger")
            return redirect(url_for("account"))
        base_count = Reservation.query.count()
        for offset, item in enumerate(items, start=1):
            reservation = Reservation(user_id=current_user.id, facility_id=item.facility_id, campsite_name=item.campsite.name if item.campsite else item.facility.label, start_date=item.start_date, end_date=item.end_date, guests=item.guests, total_cost=item.total, status="Upcoming", confirmation_code=_next_confirmation())
            reservation.confirmation_code = f"RG-2026-{base_count + offset:05d}"
            db.session.add(reservation)
            db.session.delete(item)
        db.session.commit()
        flash("Your reservation is confirmed.", "success")
        return redirect(url_for("reservations"))
    return render_template("checkout.html", items=items, total=total, addresses=addresses, payments=payments)


@app.route("/saved")
@login_required
def saved():
    items = SavedItem.query.filter_by(user_id=current_user.id).order_by(SavedItem.created_at.desc()).all()
    return render_template("saved.html", items=items)


@app.route("/reservations")
@login_required
def reservations():
    upcoming = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.start_date.desc()).all()
    return render_template("reservations.html", reservations=upcoming)


@app.route("/reservations/<int:reservation_id>/cancel", methods=["POST"])
@login_required
def cancel_reservation(reservation_id: int):
    reservation = Reservation.query.filter_by(id=reservation_id, user_id=current_user.id).first_or_404()
    reservation.status = "Cancelled"
    db.session.commit()
    flash(f"Cancelled reservation {reservation.confirmation_code}.", "info")
    return redirect(url_for("reservations"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        current_user.display_name = request.form.get("display_name", current_user.display_name).strip() or current_user.display_name
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        current_user.home_city = request.form.get("home_city", current_user.home_city).strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    payments = PaymentMethod.query.filter_by(user_id=current_user.id).all()
    return render_template("account.html", addresses=addresses, payments=payments)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Signed in.", "success")
            return redirect(request.args.get("next") or url_for("account"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        username = request.form.get("username", "").strip() or email.split("@")[0]
        display_name = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        if not email or "@" not in email or len(password) < 8:
            flash("Use a valid email and an 8+ character password.", "danger")
            return render_template("register.html")
        if User.query.filter(or_(User.email == email, User.username == username)).first():
            flash("That email or username already exists.", "danger")
            return render_template("register.html")
        user = User(username=username, email=email, display_name=display_name)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(Address(user_id=user.id, label="Home", street="100 Trailhead Dr", city="Denver", state="CO", zip_code="80202"))
        db.session.add(PaymentMethod(user_id=user.id, card_type="Visa", last4="4242", expiry="12/28"))
        db.session.commit()
        login_user(user)
        flash("Account created.", "success")
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/signup")
@app.route("/create-account")
def signup_alias():
    return redirect(url_for("register"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("index"))


@app.route("/help")
def help_center():
    topic_cards = [
        {
            "title": "Manage Reservations",
            "body": "Review cancellations, booking windows, early departures, and how existing reservations can be changed.",
            "href": "#reservations",
        },
        {
            "title": "Account & Sign-In",
            "body": "Create an account, sign in, and keep saved trips, cart items, and reservation updates in one place.",
            "href": "#account-help",
        },
        {
            "title": "Passes, Permits & Timed Entry",
            "body": "Compare permit windows, timed entry availability, and fee rules before you commit to a trip.",
            "href": "#passes-permits",
        },
        {
            "title": "Accessibility Support",
            "body": "Find accessibility assistance, alternate-format support, and TDD contact information.",
            "href": "#accessibility",
        },
    ]
    faq_entries = [
        {
            "question": "Why do I need an account to make most reservations?",
            "answer": "Accounts act as the unique identifier for reservation limits, updates, closure notices, and saved-trip workflows. They also keep reservation communications tied to one profile.",
        },
        {
            "question": "What is a booking window?",
            "answer": "A booking window determines how far in advance an arrival date becomes reservable. Windows vary by facility and inventory type, so visitors should confirm details on the specific listing.",
        },
        {
            "question": "How are fees set on Recreation.gov?",
            "answer": "Participating agencies set recreation fees, while reservation and service fees follow Recreation.gov policy. Those fees vary by inventory type and whether a reservation is made online, by call center, or in person.",
        },
        {
            "question": "How should I prepare for high-demand on-sales?",
            "answer": "Use one signed-in account, verify your dates ahead of time, keep backup inventory nearby, and expect heavy traffic around release windows for popular campgrounds and permits.",
        },
    ]
    policy_points = [
        "Camping, day-use, and cabin reservations typically include an $8 online reservation fee. Ticket reservations typically include a $1 online reservation fee.",
        "A $10 service fee is usually withheld from cancellations, and late cancellations may also forfeit the first night's use fee or the applicable day-use fee.",
        "Reservation changes outside the cut-off window may incur a fee depending on the type of change, while same-site or same-date adjustments may not.",
        "Refund requests can be submitted through the customer profile after a reservation ends, and emergency closures may qualify for full fee refunds.",
    ]
    return render_template(
        "help.html",
        topic_cards=topic_cards,
        faq_entries=faq_entries,
        policy_points=policy_points,
    )


@app.route("/articles")
def articles_index():
    articles = [
        {
            **article,
            "href": url_for("article_detail", slug=slug),
            "image_url": url_for("static", filename=f"images/{article['image']}"),
        }
        for slug, article in ARTICLE_LIBRARY.items()
    ]
    return render_template("articles.html", articles=articles)


@app.route("/articles/<slug>")
def article_detail(slug: str):
    article = ARTICLE_LIBRARY.get(slug)
    if not article:
        abort(404)
    return render_template(
        "article.html",
        title=article["title"],
        kind="editorial",
        article={
            **article,
            "image_url": url_for("static", filename=f"images/{article['image']}"),
        },
    )


@app.route("/about-us")
def about():
    return render_template("article.html", title="About Recreation.gov", kind="about")


@app.route("/articles/location-spotlight/Celebrating-America's-250th-Anniversary/1367")
def america250_article():
    return redirect(url_for("article_detail", slug="celebrate-america-250"))


@app.route("/api/facilities")
def api_facilities():
    results = _filtered_facilities(request.args)
    response = []
    for facility in results:
        point = _facility_map_point(facility)
        response.append(
            {
                "name": facility.name,
                "slug": facility.slug,
                "inventory_type": facility.inventory_type,
                "agency": facility.agency,
                "location": facility.location,
                "price": float(facility.price or 0),
                "rating": facility.rating,
                "available": facility.available,
                "lat": point["lat"],
                "lng": point["lng"],
            }
        )
    return jsonify(response)


@app.route("/_health")
def health():
    return {"ok": True, "site": "recreation_gov", "facilities": Facility.query.count()}


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


from seed_data import seed_benchmark_users, seed_database  # noqa: E402

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
with app.app_context():
    db.create_all()
    seed_database(db, Facility, Campsite, Review)
    seed_benchmark_users(db, User, Address, PaymentMethod, SavedItem, CartItem, Reservation, Facility, Campsite)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
