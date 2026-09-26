#!/usr/bin/env python3
"""Deterministic build-time/boot-time seeder for the qatar_airways mirror.

All content rows come from the tracked snapshots under source_data/:
  * cityList_en.json            — the live site's airport/city picker feed
  * destination_cards.json      — 253 destination cards from the destinations page
  * destination_repositories.json — 172 full destination guide payloads
  * flight_catalog_2026-09-24.json — 500 real QR flights (schedule snapshot)
  * flight_status_raw_2026-09-24.json — the flight-status API payload behind them
Editorial copy for offers / FAQs / fleet mirrors the captured pages under
scraped_data/ (see provenance.json).

Every seed function is gated as a whole (early-return on a populated
DB) so /reset restores the instance byte-identically.
"""
import json
import math
import re
from datetime import date
from pathlib import Path

# NOTE: app.py imports this module at the bottom of its bootstrap, and the
# test suite reloads app.py — so everything from the app package (models,
# the fare/Avios helpers) is imported lazily INSIDE the seed functions.
# Importing at module level would pin stale model classes across a reload.
BASE = Path(__file__).resolve().parent
SOURCE = BASE / "source_data"

# One frozen PBKDF2 digest for every benchmark user so the seed DB is
# byte-reproducible on every build (password: TestPass123!).
BENCHMARK_PASSWORD_HASH = ("pbkdf2:sha256:1000000$IP8McigEVWQctiaE"
                           "$016208e8c88849aff56dd1bd5e85f8aac40821cd15a86a2ca9bbfdeabfec67c4")

# Real coordinates for the five network airports whose guide payload has no
# usable coordinates (public airport facts; used only to drive fare zones).
EXTRA_COORDS = {
    "AHB": (18.2395, 42.6575),   # Abha International
    "ALY": (31.1805, 29.9260),   # Alexandria Borg El Arab
    "MUX": (30.2030, 71.4190),   # Multan International
    "PZU": (19.7760, 37.2320),   # Port Sudan
    "TAS": (41.2580, 69.2810),   # Tashkent
}
DOH_COORDS = (25.2678, 51.5310)  # Hamad International Airport

REGION_FALLBACK_COORDS = {
    "africa": (0.0, 20.0),
    "asia": (25.0, 110.0),
    "europe": (50.0, 10.0),
    "themiddleeast": (27.0, 45.0),
    "theamericas": (10.0, -80.0),
    "pacific": (-25.0, 140.0),
}


def _load(name):
    return json.loads((SOURCE / name).read_text())


def _parse_coord(value):
    """'51.5074° N' -> 51.5074 ; '0.1278° W' -> -0.1278 ; else None."""
    if not value:
        return None
    m = re.match(r"^\s*([0-9.]+)°?\s*([NSEW])", str(value))
    if not m:
        return None
    num = float(m.group(1))
    return -num if m.group(2) in ("S", "W") else num


def _coords_for(repo_payload, iata):
    """Lat/lon for a destination, tolerating the site's swapped fields."""
    if iata in EXTRA_COORDS:
        return EXTRA_COORDS[iata]
    if not repo_payload:
        return None
    candidates = [repo_payload.get("latitude"), repo_payload.get("longitude")]
    lat = lon = None
    for c in candidates:
        m = re.match(r"^\s*([0-9.]+)°?\s*([NSEW])", str(c or ""))
        if not m:
            continue
        if m.group(2) in ("N", "S") and lat is None:
            lat = _parse_coord(c)
        elif m.group(2) in ("E", "W") and lon is None:
            lon = _parse_coord(c)
    if lat is None or lon is None:
        return None
    return (lat, lon)


def haversine(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(round(2 * r * math.asin(math.sqrt(x))))


def _region_for_country(country, card_regions):
    country_l = (country or "").strip().lower()
    for ctry, region in card_regions:
        if ctry.lower() == country_l:
            return region
    return None


def _app():
    """Lazy access to the (possibly reloaded) app module's names."""
    import app as _m
    return _m


def seed_database():
    """Whole-function gate: everything below runs only on an empty DB."""
    app = _app()
    Airport = app.Airport
    Destination = app.Destination
    Flight = app.Flight
    FlightStatus = app.FlightStatus
    Aircraft = app.Aircraft
    Offer = app.Offer
    FAQ = app.FAQ
    db = app.db
    if Airport.query.count() > 0:
        return

    cards = _load("destination_cards.json")
    repos = _load("destination_repositories.json")
    city_list = _load("cityList_en.json")
    catalog = _load("flight_catalog_2026-09-24.json")
    status_raw = _load("flight_status_raw_2026-09-24.json")

    # ---- airports (the live site's picker feed) --------------------------
    card_regions = [(c["country"], c["region"]) for c in cards]
    for entry in city_list:
        code = entry.get("shorthand")
        if not code:
            continue
        region = _region_for_country(entry.get("country"), card_regions) or "europe"
        db.session.add(Airport(code=code, city=entry.get("city", ""),
                               airport_name=entry.get("airport", ""),
                               country=entry.get("country", ""),
                               country_code=entry.get("countryCode"),
                               region=region))

    # ---- destinations -----------------------------------------------------
    # card -> IATA resolution is frozen in source_data/card_iata_map.json by
    # the harvest script so the seeder and the image tree always agree
    card_map_path = SOURCE / "card_iata_map.json"
    card_map = json.loads(card_map_path.read_text()) if card_map_path.exists() else {}
    repo_by_iata = {}
    for key, payload in repos.items():
        repo_by_iata[payload["iataCode"]] = payload
    for card in cards:
        iata = None
        payload = None
        # 1. frozen card -> IATA resolution (agrees with the image tree)
        iata = card_map.get(card["slug"])
        if iata:
            payload = repo_by_iata.get(iata)
        # 2. fall back to matching the card to its guide payload via the
        #    card image path, but only when the city names agree (several
        #    sparse destinations share a placeholder aircraft image)
        if iata is None:
            for iata_c, p in repo_by_iata.items():
                if (p.get("horizontalImage3") == card.get("image")
                        and str(p.get("destinationTitle", "")).strip().lower()
                        == card["city"].strip().lower()):
                    iata, payload = iata_c, p
                    break
        if iata is None:
            for iata_c, p in repo_by_iata.items():
                if card.get("slug", "").endswith(p.get("iataCode", "").lower()):
                    iata, payload = iata_c, p
                    break
        has_guide = payload is not None
        if iata is None:
            # non-guide card: derive the IATA from the city picker feed
            city_tokens = [t.strip().lower() for t in re.split(r"\*", card["city"])]
            candidates = [e for e in city_list
                          if any(t and t in e.get("city", "").lower() for t in city_tokens)
                          and e.get("country", "") == card.get("country")]
            iata = candidates[0]["shorthand"] if candidates else None
        if not iata:
            continue
        dest = Destination(
            iata=iata, city=card["city"], country=card["country"],
            region=card["region"], slug=card["slug"],
            card_image=f"/static/images/destinations/{iata}/h3.jpg",
            has_guide=has_guide)
        if payload:
            dest.title_h1 = payload.get("destinationHighlightsH1") or f"Flights to {card['city']}"
            dest.intro = payload.get("destinationPageIntro") or ""
            dest.overview_heading = payload.get("overviewTabHeading") or f"Book your visit to {card['city']}"
            dest.overview_text = payload.get("overviewText") or ""
            dest.attractions_heading = payload.get("touristAttractionsTabHeading") or "Things to do"
            dest.attractions_text = payload.get("touristAttractionsText") or ""
            dest.activities_heading = payload.get("leisureactivitiesTabHeading") or "Activities"
            dest.activities_text = payload.get("leisureActivitiesText") or ""
            dest.dining_heading = payload.get("eatingTabHeading") or "Food"
            dest.dining_text = payload.get("eatingImageText") or ""
            dest.shopping_heading = payload.get("shoppingTabHeading") or "Shopping"
            dest.shopping_text = payload.get("shoppingText") or ""
            for attr, field in (("hero_image", "heroImageDesktop"),
                                ("overview_image", "overviewImage"),
                                ("attractions_image", "touristAttractionsImage1"),
                                ("activities_image", "leisureActivitiesImage1"),
                                ("dining_image", "eatingImage1"),
                                ("shopping_image", "shoppingImage1"),
                                ("h1_image", "mainHorizontalImage"),
                                ("h2_image", "horizontalImage2"),
                                ("square_image", "mainSquareImage")):
                # sparse guides ship empty section payloads, and a handful of
                # renditions are not preserved in the Wayback snapshot; only
                # reference images that actually exist so templates never
                # render a broken file (they fall back to the card image)
                if (payload.get(field) or "").strip():
                    rel = f"/static/images/destinations/{iata}/{slot_of(field)}.jpg"
                    if (BASE / rel.lstrip("/")).is_file():
                        setattr(dest, attr, rel)
        db.session.add(dest)
    db.session.flush()

    # ---- distances --------------------------------------------------------
    coords = {}
    for dest in Destination.query.all():
        payload = repo_by_iata.get(dest.iata)
        c = _coords_for(payload, dest.iata)
        if c:
            coords[dest.iata] = c
        else:
            coords[dest.iata] = REGION_FALLBACK_COORDS.get(dest.region, (20.0, 20.0))

    def distance_between(a, b):
        ca = DOH_COORDS if a == "DOH" else coords.get(a)
        cb = DOH_COORDS if b == "DOH" else coords.get(b)
        if not ca or not cb:
            return 4000
        return max(300, haversine(ca, cb))

    # ---- flights + statuses ----------------------------------------------
    flight_rows = {}
    for f in catalog:
        dep = re.sub(r"^\w{3} \w{3} \d{2} \d{4} ", "", f["dep_sched"])
        arr = re.sub(r"^\w{3} \w{3} \d{2} \d{4} ", "", f["arr_sched"])
        row = Flight(number=f["number"], origin_code=f["from"], dest_code=f["to"],
                     equipment=f["equipment"], dep_time=dep, arr_time=arr,
                     distance_km=distance_between(f["from"], f["to"]))
        db.session.add(row)
        flight_rows[f["number"]] = row
    db.session.flush()
    for key, payload in sorted(status_raw.items()):
        for fl in payload.get("flights", []):
            number = int(fl["carrier"]["flightNumber"])
            fs = fl.get("fsInfo", {}) or {}
            row = FlightStatus(flight_id=flight_rows[number].id,
                               status_code=fs.get("opsStatusCode", "SCHD"),
                               dep_est=_hm(fl.get("departureDateEstimated")),
                               arr_est=_hm(fl.get("arrivalDateEstimated")),
                               dep_act=_hm(fl.get("departureDateActual")),
                               arr_act=_hm(fl.get("arrivalDateActual")))
            db.session.add(row)

    # ---- aircraft + seat maps ---------------------------------------------
    for spec in FLEET:
        db.session.add(Aircraft(code=spec["code"], family=spec["family"],
                                description=spec["description"],
                                seat_capacity=spec["seat_capacity"],
                                qsuite=spec.get("qsuite", False),
                                first_class=spec.get("first_class", False),
                                image=spec["image"],
                                seatmap=json.dumps(spec["seatmap"])))

    # ---- offers -----------------------------------------------------------
    for off in OFFERS:
        db.session.add(Offer(**off))

    # ---- FAQs -------------------------------------------------------------
    for category, question, answer in FAQS:
        db.session.add(FAQ(category=category, question=question, answer=answer))

    db.session.commit()


def _hm(value):
    """'Thu Sep 24 2026 13:00' -> '13:00'."""
    if not value:
        return None
    m = re.search(r"(\d{1,2}:\d{2})", str(value))
    return m.group(1) if m else None


def slot_of(field):
    return {"heroImageDesktop": "hero", "overviewImage": "overview",
            "touristAttractionsImage1": "attractions",
            "leisureActivitiesImage1": "activities", "eatingImage1": "dining",
            "shoppingImage1": "shopping", "mainHorizontalImage": "h1",
            "horizontalImage2": "h2", "mainSquareImage": "square"}[field]


FLEET = [
    {
        "code": "Airbus A320", "family": "Airbus",
        "description": ("Fly in a spacious single-aisle cabin, along with Qatar Airways' "
                        "curated product and renowned service, delivering exceptional "
                        "passenger comfort on routes across the network."),
        "seat_capacity": "132–144 seats", "image": "/static/images/brand/a320-aircraft-h2.jpg",
        "seatmap": {"business": {"rows": [1, 3], "cols": "CDF"},
                     "economy": {"rows": [4, 29], "cols": "ABCDEF", "preferred_rows": [4, 5, 12]}},
    },
    {
        "code": "Airbus A330-200", "family": "Airbus",
        "description": ("A workhorse of the regional network offering fully flat Business "
                        "Class seats and a quiet, comfortable Economy cabin."),
        "seat_capacity": "226 seats", "image": "/static/images/brand/h3-b777.jpg",
        "seatmap": {"business": {"rows": [1, 5], "cols": "ACFG"},
                     "economy": {"rows": [16, 39], "cols": "ABCDEFGH", "preferred_rows": [16, 17, 28]}},
    },
    {
        "code": "Airbus A330-300", "family": "Airbus",
        "description": ("The larger A330 variant flies regional trunk routes with a fully "
                        "flat Business Class and a roomy Economy cabin."),
        "seat_capacity": "289–305 seats", "image": "/static/images/brand/h3-b777.jpg",
        "seatmap": {"business": {"rows": [1, 7], "cols": "ACFG"},
                     "economy": {"rows": [18, 45], "cols": "ABCDEFGH", "preferred_rows": [18, 19, 30]}},
    },
    {
        "code": "Airbus A350-900", "family": "Airbus", "qsuite": True,
        "description": ("Qatar Airways is the global launch customer and operator of the "
                        "world's most advanced passenger aircraft. Bringing major advantages "
                        "in fuel efficiency along with unmatched passenger comfort, the A350 "
                        "is notable for the quietest cabin of any twin-aisle aircraft."),
        "seat_capacity": "283 seats (features Qsuite)",
        "image": "/static/images/brand/h1-a350-wing.jpg",
        "seatmap": {"business": {"rows": [1, 8], "cols": "ADEG"},
                     "economy": {"rows": [30, 51], "cols": "ABCDEFGHJK", "preferred_rows": [30, 31, 32]}},
    },
    {
        "code": "Airbus A350-1000", "family": "Airbus", "qsuite": True,
        "description": ("The stretched A350-1000 carries the award-winning Qsuite Business "
                        "Class across the long-haul network with the quietest cabin of any "
                        "twin-aisle aircraft."),
        "seat_capacity": "327–395 seats (features Qsuite)",
        "image": "/static/images/brand/h2-a350-aircraft-flight2-ar.jpg",
        "seatmap": {"business": {"rows": [1, 11], "cols": "ADEG"},
                     "economy": {"rows": [30, 53], "cols": "ABCDEFGHJK", "preferred_rows": [30, 31, 32]}},
    },
    {
        "code": "Airbus A380-800", "family": "Airbus", "first_class": True,
        "description": ("Qatar Airways A380, the largest aircraft in our fleet, is a passenger "
                        "favourite providing an exceptional travel experience. It features a "
                        "tri-class configuration with First, Business and Economy Class over "
                        "two decks, with one of the world's largest on-board lounges."),
        "seat_capacity": "517 seats",
        "image": "/static/images/brand/h3-custom-a380-fleetpage.jpg",
        "seatmap": {"first": {"rows": [1, 3], "cols": "ADFG"},
                     "business": {"rows": [4, 11], "cols": "ADEFG"},
                     "economy": {"rows": [30, 57], "cols": "ABCDEFGHJK", "preferred_rows": [30, 31, 32]}},
    },
    {
        "code": "Boeing 777-200LR", "family": "Boeing",
        "description": ("The long-range 777-200LR connects Doha with ultra-long-haul "
                        "destinations, featuring a spacious Business Class cabin."),
        "seat_capacity": "272–276 seats",
        "image": "/static/images/brand/h3-b777.jpg",
        "seatmap": {"business": {"rows": [1, 7], "cols": "ACEF"},
                     "economy": {"rows": [30, 49], "cols": "ABCDEFGHJ", "preferred_rows": [30, 31]}},
    },
    {
        "code": "Boeing 777-300ER", "family": "Boeing", "first_class": True,
        "description": ("Our Boeing 777 boasts comfortable seats and promises an exceptional "
                        "travel experience. Savour delectable cuisine on board while our "
                        "award-winning cabin crew takes care of your every need."),
        "seat_capacity": "294–412 seats (features First Class)",
        "image": "/static/images/brand/h3-b777.jpg",
        "seatmap": {"first": {"rows": [1, 2], "cols": "AFG"},
                     "business": {"rows": [3, 10], "cols": "ACEF"},
                     "economy": {"rows": [30, 53], "cols": "ABCDEFGHJ", "preferred_rows": [30, 31, 32]}},
    },
    {
        "code": "Boeing 787-8", "family": "Boeing",
        "description": ("Our Boeing 787 Dreamliner is a masterpiece of aeronautical "
                        "engineering. Enjoy refined hospitality on board as you embark on a "
                        "journey like none other to any of our destinations worldwide."),
        "seat_capacity": "254–267 seats",
        "image": "/static/images/brand/h3-787-inflight.jpg",
        "seatmap": {"business": {"rows": [1, 7], "cols": "ADEG"},
                     "economy": {"rows": [30, 45], "cols": "ABCDEGH", "preferred_rows": [30, 31]}},
    },
    {
        "code": "Boeing 787-9", "family": "Boeing",
        "description": ("The stretched Dreamliner features Business Class seats with a "
                        "privacy door and the lowest cabin altitude in the fleet for a "
                        "smoother long-haul experience."),
        "seat_capacity": "311 seats (Business Class with privacy door)",
        "image": "/static/images/brand/h3-787-inflight.jpg",
        "seatmap": {"business": {"rows": [1, 8], "cols": "ADEG"},
                     "economy": {"rows": [30, 50], "cols": "ABCDEGH", "preferred_rows": [30, 31, 32]}},
    },
]

OFFERS = [
    {
        "slug": "motogp-adventures", "title": "Rev up your engines: MotoGP™ adventures",
        "category": "Sports travel",
        "summary": ("Never miss out on the big events with our exclusive offers and promo "
                    "codes. Feel the thrill of MotoGP™ race weekends and fly there with "
                    "promo code MOTOGP26."),
        "description": ("Get closer to the action at MotoGP™ races around the world. Book your "
                        "flights with promo code MOTOGP26 to save 10% on Economy and Business "
                        "Class fares to selected race cities. Offer applies to return trips "
                        "booked on qatarairways.com."),
        "image": "/static/images/brand/h2-father-son-middle-east-vfr.jpg",
        "promo_code": "MOTOGP26", "discount_line": "Save 10% on race-weekend flights",
        "terms": ("Discount applies to the base fare of return trips booked on "
                  "qatarairways.com with promo code MOTOGP26. Not combinable with other "
                  "promotions. Offer valid on new bookings only."),
        "valid_until": "31 Dec 2026", "featured": True,
    },
    {
        "slug": "formula-1-races", "title": "Feel the thrill: Formula 1® races",
        "category": "Sports travel",
        "summary": ("Be part of the action at Formula 1® Grand Prix weekends. Book a flight "
                    "with promo code F1QATAR26 and save on your race travel."),
        "description": ("From the Lusail Grand Prix to street circuits around the world, fly "
                        "to every Formula 1® race weekend in comfort. Use promo code F1QATAR26 "
                        "when booking to take 10% off your return fare."),
        "image": "/static/images/brand/h2-qsuite-quad-seat.jpg",
        "promo_code": "F1QATAR26", "discount_line": "10% off Grand Prix weekend fares",
        "terms": ("Promo code F1QATAR26 applies to return trips booked on qatarairways.com. "
                  "Seats are limited and the offer may be withdrawn without notice."),
        "valid_until": "30 Nov 2026", "featured": True,
    },
    {
        "slug": "qatar-summer", "title": "Qatar Summer: endless sun",
        "category": "Holidays",
        "summary": ("Make the most of the summer with our special fares to Doha and beyond. "
                    "Use promo code QSUMMER26 for 10% off summer getaways."),
        "description": ("Doha's museums, souqs and desert escapes are waiting. Book a summer "
                        "trip with promo code QSUMMER26 and save 10% on fares to, from and "
                        "via Qatar."),
        "image": "/static/images/brand/v-doha-culture.jpg",
        "promo_code": "QSUMMER26", "discount_line": "10% off summer fares via Doha",
        "terms": ("Travel must be completed by 30 September 2026. Promo code QSUMMER26 is "
                  "valid on qatarairways.com bookings only."),
        "valid_until": "30 Sep 2026", "featured": True,
    },
    {
        "slug": "african-safari-journeys", "title": "Journey into the wild: African safaris",
        "category": "Holidays",
        "summary": ("Discover African safari destinations with our curated journey ideas and "
                    "special fares to the continent's top wildlife parks."),
        "description": ("From the Serengeti to Kruger, explore our top African safari "
                        "destinations. Book with promo code SAFARI26 to save 10% on flights "
                        "to selected African cities."),
        "image": "/static/images/brand/v-maldives-beach.jpg",
        "promo_code": "SAFARI26", "discount_line": "Save 10% on safari-bound flights",
        "terms": ("Valid on return trips to selected African destinations booked on "
                  "qatarairways.com with promo code SAFARI26."),
        "valid_until": "31 Dec 2026", "featured": False,
    },
    {
        "slug": "the-signature-collection", "title": "The Signature Collection: up to 40% off Doha holidays",
        "category": "Holidays",
        "summary": ("Save more and earn greater rewards when you book your flight plus hotel "
                    "package with Qatar Airways Holidays — up to 40% off Doha holidays."),
        "description": ("Stay at hand-picked Doha hotels with breakfast and transfers included. "
                        "The Signature Collection packages combine flights and nights at the "
                        "city's landmark hotels with savings of up to 40%."),
        "image": "/static/images/brand/h2-hia-self-service-stations.jpg",
        "promo_code": None, "discount_line": "Up to 40% off flight + hotel packages",
        "terms": ("Package prices include flights, hotel, breakfast and airport transfers. "
                  "Prices are per person based on two adults sharing."),
        "valid_until": "31 Dec 2026", "featured": False,
    },
    {
        "slug": "qatar-stopover", "title": "The world's best value stopover in Qatar",
        "category": "Stopover",
        "summary": ("Turn one holiday into two with incredible stopover packages to Qatar — "
                    "from desert dunes to Museum of Islamic Art."),
        "description": ("Add a free stopover in Doha on your connecting journey. Choose from "
                        "our stopover packages and discover Qatar's desert, souqs and skyline "
                        "without extra airfare."),
        "image": "/static/images/destinations/DOH/hero.jpg",
        "promo_code": None, "discount_line": "Free stopover packages via Doha",
        "terms": ("Stopover packages are available to passengers connecting through Hamad "
                  "International Airport with a transit time over 5 hours."),
        "valid_until": "Ongoing", "featured": False,
    },
    {
        "slug": "addon-services", "title": "Elevate your experience with add-on services",
        "category": "Add-ons",
        "summary": ("Save on extra baggage allowance, Al Maha meet and assist services or "
                    "lounge access when purchased on qatarairways.com or our mobile app. "
                    "Use promo code BAG15 for 15% off extra baggage."),
        "description": ("Carry more with you: purchase extra baggage allowance in advance and "
                        "save. Promo code BAG15 takes 15% off extra baggage fees added via "
                        "Manage booking. Al Maha meet and assist and lounge access are also "
                        "available at member rates."),
        "image": "/static/images/brand/h2-paid-baggage.jpg",
        "promo_code": "BAG15", "discount_line": "15% off extra baggage in Manage booking",
        "terms": ("Promo code BAG15 is applied automatically when extra baggage is added to a "
                  "booking that was made with the code. Fees are per additional 23kg piece."),
        "valid_until": "31 Dec 2026", "featured": False,
    },
    {
        "slug": "student-club", "title": "Student Club: extra baggage and fare discounts",
        "category": "Students",
        "summary": ("Students save with the Student Club: exclusive fares, extra baggage and "
                    "a free date change on your first booking."),
        "description": ("Join the Privilege Club Student Club with your student ID to unlock "
                        "exclusive fares, an extra 10kg baggage allowance and one free flight "
                        "date change."),
        "image": "/static/images/brand/m-SC-Extra-Baggage.jpg",
        "promo_code": None, "discount_line": "Extra 10kg baggage for students",
        "terms": ("A valid student ID must be presented at check-in. Student Club benefits "
                  "apply to Qatar Airways marketed and operated flights."),
        "valid_until": "Ongoing", "featured": False,
    },
    {
        "slug": "qsuite-experience", "title": "Private. Luxurious. Qsuite.",
        "category": "On board",
        "summary": ("Begin an unforgettable journey where luxury is reimagined. Relax, dine, "
                    "and unwind with generous space and the privacy you deserve."),
        "description": ("Experience Qsuite on select A350 and B777 aircraft: the world's first "
                        "double bed in Business Class, adjustable panels and do-not-disturb "
                        "signs in your own private suite."),
        "image": "/static/images/brand/v-qsuite-businessman.jpg",
        "promo_code": None, "discount_line": "Available on select long-haul flights",
        "terms": ("Qsuite availability varies by aircraft. Check the fleet page for aircraft "
                  "featuring Qsuite."),
        "valid_until": "Ongoing", "featured": False,
    },
    {
        "slug": "starlink-wifi", "title": "Starlink Wi-Fi. Fast and free for members.",
        "category": "On board",
        "summary": ("Chat with family and friends or stream your favourite shows. Log in or "
                    "join Privilege Club for uninterrupted access throughout your flight."),
        "description": ("Starlink Wi-Fi is now available on board. Privilege Club members "
                        "enjoy free unlimited Wi-Fi on every flight; non-members can purchase "
                        "access during the journey."),
        "image": "/static/images/brand/h3-LNB-ife-wifi.jpg",
        "promo_code": None, "discount_line": "Free unlimited Wi-Fi for Privilege Club members",
        "terms": ("Wi-Fi availability may vary by aircraft and route. Membership number must "
                  "be added to the booking before boarding."),
        "valid_until": "Ongoing", "featured": False,
    },
]

FAQS = [
    ("Baggage", "How much checked baggage can I take on my trip?",
     "Checked baggage is included on all Qatar Airways flights. For flights to or from "
     "Africa or the Americas your allowance is based on pieces: Economy Lite includes 1 "
     "piece up to 23kg, while Economy Classic, Convenience and Comfort include 2 pieces "
     "up to 23kg each. For all other routes the allowance is weight-based: 20kg on Economy "
     "Lite, 25kg on Economy Classic, 30kg on Economy Convenience and 35kg on Economy "
     "Comfort. Business Class includes 2 pieces up to 32kg each on piece routes, or 40kg "
     "on weight routes; First Elite includes 50kg."),
    ("Baggage", "What are the size limits for carry-on baggage?",
     "Carry-on baggage dimensions must not exceed 50cm (length) x 37cm (width) x 25cm "
     "(depth) — 20in x 15in x 10in. Economy customers may carry 1 piece up to 7kg; "
     "Business and First customers may carry 2 pieces up to 15kg total. For flights to or "
     "from Brazil, Economy customers can carry one piece up to 10kg."),
    ("Baggage", "How much can a single checked bag weigh?",
     "A single piece of checked baggage cannot exceed 32kg (70lb). For flights to or from "
     "Africa or the Americas, dimensions per bag must not exceed 158cm total "
     "(length + width + height); for other routes the total must not exceed 300cm."),
    ("Baggage", "How do I purchase extra baggage allowance?",
     "Save when you purchase extra baggage allowance on qatarairways.com or our mobile "
     "app before your trip. Open Manage booking, choose Add extra baggage, and pay per "
     "additional 23kg piece. Each extra piece costs USD 60 on routes up to 3,000km, "
     "USD 100 up to 8,000km and USD 140 beyond. Bookings made with promo code BAG15 "
     "receive 15% off these fees in Manage booking."),
    ("Baggage", "Do infants have their own baggage allowance?",
     "Infants have their own checked baggage allowance, plus one baby stroller or "
     "collapsible carrycot at no additional cost. Infants travelling on a separate seat "
     "are also entitled to one car seat at no additional cost."),
    ("Booking", "How do I book a flight on qatarairways.com?",
     "Use the booking widget on the homepage: enter your origin and destination, "
     "departure and return dates, the number of passengers and your preferred cabin, "
     "then choose a fare on the search results page. After passenger details and "
     "payment you will receive a 6-character booking reference (PNR)."),
    ("Booking", "What fare types are available in Economy Class?",
     "Economy Class fares come in four types: Lite (the lowest fare, 20kg checked baggage "
     "on weight routes), Classic (25kg), Convenience (30kg, more flexibility) and Comfort "
     "(35kg, the most flexible Economy fare). On piece-based routes to or from Africa and "
     "the Americas, Classic, Convenience and Comfort all include 2 pieces up to 23kg each."),
    ("Booking", "What fare types are available in Business Class?",
     "Business Class fares come in four types: Business Lite, Business Classic, Business "
     "Comfort and Business Elite. All include 2 checked pieces up to 32kg each on piece "
     "routes or 40kg on weight routes, lounge access and priority services."),
    ("Booking", "How do promo codes work?",
     "Enter a promo code in the booking widget before you search. Eligible codes, such "
     "as MOTOGP26, F1QATAR26, QSUMMER26 or SAFARI26, take 10% off the base fare of your "
     "trip; the discount appears on the payment page. One promo code can be used per "
     "booking and codes cannot be combined."),
    ("Booking", "Which payment methods do you accept?",
     "We accept major credit and debit cards including Visa, Mastercard and American "
     "Express. Card details are only required at the payment step; your booking is "
     "confirmed instantly with a PNR you can use in Manage booking."),
    ("Check-in", "When can I check in online?",
     "Online check-in opens on qatarairways.com and our mobile app and stays available "
     "until a short window before departure. Retrieve your booking with your 6-character "
     "booking reference and last name, select seats from the aircraft seat map, and "
     "receive your boarding pass."),
    ("Check-in", "What do I need for online check-in?",
     "You need your 6-character booking reference (PNR) and the last name on the "
     "booking. After selecting a seat for every passenger the boarding pass shows your "
     "gate, boarding time and seat for each leg."),
    ("Check-in", "Are there self-service check-in kiosks at the airport?",
     "Yes. At certain airports you can use self-service check-in kiosks and automated "
     "baggage drop: select your seats, add your Privilege Club number, drop your baggage, "
     "collect your boarding pass and head to the gate."),
    ("Check-in", "What is Fast Pass?",
     "Fast Pass is a facial recognition service at Hamad International Airport that lets "
     "you move through the airport using your face as your boarding pass."),
    ("Check-in", "What is BAGTAG?",
     "BAGTAG is a digitised baggage label. Check in using the Qatar Airways mobile app "
     "and select 'Create baggage label' to label your bags from anywhere, depending on "
     "your route."),
    ("Flight status", "How do I track my flight status?",
     "Open Flight status from the homepage and search by flight number (for example "
     "QR001) or by route and date. The result shows the scheduled, estimated and actual "
     "departure and arrival times together with the current status such as Arrived, "
     "En route, Boarding or Delayed."),
    ("Flight status", "What do the flight status codes mean?",
     "Arrived means the flight has reached its gate; En route means it is in the air; "
     "Boarding means passengers are boarding; Departed means the aircraft has pushed "
     "back; Delayed and Rescheduled explain schedule changes; Cancelled means the flight "
     "was cancelled."),
    ("Special assistance", "How do I arrange travel with my pet?",
     "Enter your booking reference and last name to submit a request for travelling with "
     "your pet. There may be restrictions on carrying pets abroad; check the Visa and "
     "other requirements section for your destination, then the Customs section, to "
     "learn more about cats, dogs and birds."),
    ("Special assistance", "How do I request medical assistance?",
     "Fill in the medical assistance form in English to make special requests based on "
     "your medical needs. Be sure to submit the form between 7 days and 48 hours before "
     "departure."),
    ("Special assistance", "What are the rules for carrying firearms?",
     "Firearms requests must be submitted more than 24 hours before departure. Specific "
     "destination deadlines apply: for Oman more than 19 days prior to departure, and "
     "for Bahrain more than 9 days prior to departure. Tickets must be issued only on "
     "Qatar Airways marketed and operated flights; carriage of these items is not "
     "permitted on interline and/or codeshare journeys."),
    ("Special assistance", "Is there support for hard-of-hearing passengers?",
     "Hard-of-hearing passengers can use our dedicated 24-hour support number: "
     "+1 833 607 2675."),
    ("Special assistance", "How are unaccompanied children looked after?",
     "For your peace of mind, children flying alone are taken care of by our crew and "
     "ground staff throughout the journey via the Young solo traveller service."),
    ("Certificates", "How do I get a proof of travel certificate?",
     "Generate a certificate for your completed flight as proof of travel. Certificates "
     "can be requested for up to 12 months from the date of travel via the Get travel "
     "certificate service on the Help page."),
    ("Certificates", "Can I get a certificate for a delayed or cancelled flight?",
     "Yes. A separate certificate is available for delayed or cancelled flights. A "
     "separate certificate is also available for each flight in your journey — for "
     "example, if your trip includes a connecting flight (DXB → DOH → LHR), you can "
     "download one certificate for DXB → DOH and another for DOH → LHR."),
    ("Certificates", "How do I request a tax invoice?",
     "Enter your booking reference (PNR) and last name on the Help page to process a tax "
     "invoice request. For tickets purchased through a travel agency, please liaise with "
     "them directly."),
    ("Privilege Club", "What is Privilege Club?",
     "Privilege Club is Qatar Airways' loyalty programme. Members earn Avios and "
     "Qpoints on every eligible flight, unlock member-only offers, and can pay with "
     "Cash + Avios. Membership starts at Burgundy tier."),
    ("Privilege Club", "How do I move up a membership tier?",
     "Earn 150 Qpoints within any 12-month period to upgrade to Silver, 300 Qpoints to "
     "upgrade to Gold, and 600 Qpoints to upgrade to Platinum. In addition, at least 20% "
     "of your Qpoints must come from flights marketed and operated by Qatar Airways, or "
     "you must have flown 4 sectors within 12 months (or 8 sectors within 24 months) on "
     "such flights."),
    ("Privilege Club", "How many Qpoints do I need to retain my tier?",
     "To retain Silver, earn 135 Qpoints within the last 12 months or 270 Qpoints "
     "within the last 24 months prior to your renewal date. To retain Gold, earn 270 or "
     "540 Qpoints; to retain Platinum, earn 540 or 1080 Qpoints respectively."),
    ("Privilege Club", "What tier bonus do higher tiers earn on flights?",
     "Silver members earn a 25% tier bonus on eligible flights with Qatar Airways, Gold "
     "members earn a 75% tier bonus and Platinum members earn a 100% tier bonus on top "
     "of base Avios."),
    ("Privilege Club", "How much extra baggage do Privilege Club tiers get?",
     "Silver members get 15kg extra baggage allowance (or one piece, depending on the "
     "route), Gold members get 20kg (or one piece) and Platinum members get 25kg (or "
     "two pieces, depending on the route)."),
    ("Privilege Club", "What are Qcredits?",
     "Qcredits are redeemable per tier cycle: Gold members receive 40 Qcredits to redeem "
     "for upgrades, excess baggage and much more. Qcredits are separate from Avios and "
     "Qpoints."),
    ("Privilege Club", "How do I secure my account with an OTP?",
     "Add an extra layer of security to your account with a one-time pin (OTP). Choose "
     "to require the OTP always at login or only during your transactions, and receive "
     "it via email, SMS or both."),
    ("Privilege Club", "Can I upgrade with Avios?",
     "Yes. Open Manage booking for an Economy booking that carries your Privilege Club "
     "number and choose Upgrade with Avios. The upgrade moves the booking to Business "
     "Class on the same flight and debits the required Avios from your balance."),
    ("On board", "Is Wi-Fi available on board?",
     "Starlink Wi-Fi is fast and free for Privilege Club members: log in or join "
     "Privilege Club for uninterrupted access throughout your flight. Non-members can "
     "purchase access on board."),
    ("On board", "Which aircraft feature Qsuite?",
     "Qsuite features on select A350-900, A350-1000 and Boeing 777 aircraft. The A350 "
     "fleet pages on this site note Qsuite in the seating capacity table."),
    ("At the airport", "Where can I relax before my flight?",
     "Offering surroundings that rival those of a five-star hotel, our lounges — "
     "including Al Mourjan — will redefine your lounge experience. Privilege Club "
     "members save 10% on Al Maha Meet and Assist services and lounges."),
    ("At the airport", "How do I book Al Maha meet and assist services?",
     "Al Maha Services can be booked on qatarairways.com or our mobile app. Privilege "
     "Club members save 10% on Al Maha Meet and Assist services and lounges; Gold and "
     "Platinum members enjoy the Al Maha 'meet and assist' service as a tier benefit "
     "(conditions apply)."),
    ("Travel requirements", "What are the power bank rules for travel?",
     "Per the travel alert of 18 June 2026, there are updated requirements for "
     "travelling with power banks. Check the Travel alerts banner on the homepage "
     "before you fly."),
    ("Travel requirements", "How do I check visa and passport requirements?",
     "Every destination guide on this site has a Check your travel requirements panel: "
     "enter your destination, citizenship, departure country and residence to learn the "
     "latest passport, visa, health and customs requirements."),
    ("Stopover", "Can I turn one holiday into two with a stopover?",
     "Yes. The world's best value stopover: turn one holiday into two with incredible "
     "stopover packages to Qatar, from desert dunes to the Museum of Islamic Art, when "
     "connecting through Doha."),
    ("Feedback", "How do I share feedback or a concern?",
     "At Qatar Airways, every journey matters. Share feedback or concerns via the "
     "Feedback & Concerns service on the Help page: send a compliment, tell us how we "
     "can improve, or comment on your online experience. Providing your booking details "
     "helps us support you better, but you can continue without them."),
]


def seed_benchmark_users():
    """Whole-function gate; seeds the four benchmark members + their trips."""
    app = _app()
    User = app.User
    Booking = app.Booking
    BookingLeg = app.BookingLeg
    Passenger = app.Passenger
    Activity = app.Activity
    Flight = app.Flight
    db = app.db
    MIRROR_REFERENCE_DATE = app.MIRROR_REFERENCE_DATE
    FARE_TYPES = app.FARE_TYPES
    fare_amount = app.fare_amount
    avios_for_distance = app.avios_for_distance
    qpoints_for_distance = app.qpoints_for_distance
    gate_for = app.gate_for
    taxes_for = app.taxes_for
    db.create_all()
    # create_all() emits implicit column indexes from a set, whose order depends
    # on object addresses; create them in a fixed order instead so every build
    # produces a byte-identical database
    db.session.execute(db.text(
        "CREATE INDEX IF NOT EXISTS ix_flights_dest_code ON flights (dest_code)"))
    db.session.execute(db.text(
        "CREATE INDEX IF NOT EXISTS ix_flights_origin_code ON flights (origin_code)"))
    db.session.commit()

    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = [
        dict(email="alice.j@test.com", first_name="Alice", last_name="Johnson",
             tier="Gold", avios=48250, qpoints=415, qcredits=40,
             membership_no="QRPC0004217", country="United Kingdom",
             mobile="+44 7700 900123", title="Ms"),
        dict(email="bob.c@test.com", first_name="Bob", last_name="Chen",
             tier="Silver", avios=15300, qpoints=210, qcredits=0,
             membership_no="QRPC0007752", country="Singapore",
             mobile="+65 6789 2345", title="Mr"),
        dict(email="carol.d@test.com", first_name="Carol", last_name="Davis",
             tier="Burgundy", avios=4200, qpoints=60, qcredits=0,
             membership_no="QRPC0009134", country="United States",
             mobile="+1 202-555-0134", title="Mrs"),
        dict(email="david.k@test.com", first_name="David", last_name="Kim",
             tier="Platinum", avios=96700, qpoints=720, qcredits=100,
             membership_no="QRPC0001588", country="Australia",
             mobile="+61 2 9876 5432", title="Mr"),
    ]
    members = {}
    for u in users:
        row = User(password_hash=BENCHMARK_PASSWORD_HASH,
                   joined="2024-03-15", **u)
        db.session.add(row)
        members[u["email"]] = row
    db.session.flush()

    def add_booking(member, pnr, cabin, fare, adults, children, legs_spec,
                    pax_spec, status="confirmed", checked_in=False,
                    extra_bags=0, avios_redeemed=0, promo_code=None):
        booking = Booking(pnr=pnr, user_id=member.id, pc_number=member.membership_no,
                          contact_email=member.email, contact_last_name=member.last_name,
                          cabin=cabin, fare_type=fare, adults=adults, children=children,
                          extra_bags=extra_bags, status=status, checked_in=checked_in,
                          avios_redeemed=avios_redeemed, promo_code=promo_code,
                          created_at=MIRROR_REFERENCE_DATE.isoformat())
        total = 0
        for (origin, dest, day, number) in legs_spec:
            fl = Flight.query.filter_by(number=number).first()
            fare_price = fare_amount(fl, fare) * (adults + children)
            total += fare_price
            booking.legs.append(BookingLeg(
                flight_number=number, origin_code=origin, dest_code=dest,
                leg_date=day, dep_time=fl.dep_time, arr_time=fl.arr_time,
                equipment=fl.equipment, distance_km=fl.distance_km,
                fare_price=fare_price, gate=gate_for(number)))
        for (title, first, last, ptype) in pax_spec:
            ticket = (int.from_bytes(pnr.encode(), "little")
                      + sum(ord(c) for c in first)) % 10**10
            booking.passengers.append(Passenger(title=title, first_name=first,
                                                last_name=last, pax_type=ptype,
                                                ticket_number=f"157-{ticket:010d}"))
        taxes = taxes_for(total)
        booking.total_paid = total + taxes
        db.session.add(booking)
        avios = sum(avios_for_distance(l.distance_km, cabin, member.tier) for l in booking.legs)
        qpoints = sum(qpoints_for_distance(l.distance_km, cabin) for l in booking.legs)
        db.session.add(Activity(user_id=member.id, kind="earn",
                                avios=avios, qpoints=qpoints,
                                description=(f"Flight QR{legs_spec[0][3]:03d} "
                                              f"{legs_spec[0][0]}→{legs_spec[0][1]} "
                                              f"({FARE_TYPES[fare][1]})"),
                                occurred_at="2026-09-20"))
        db.session.add(Activity(user_id=member.id, kind="bonus", avios=2500, qpoints=0,
                                description="Privilege Club partner bonus — Qatar Duty Free",
                                occurred_at="2026-08-30"))
        return booking

    # Alice: London return (Economy Classic, 2 pax) + Paris one-way (Business)
    add_booking(members["alice.j@test.com"], "QK17TP", "Economy", "ECO_CLASSIC",
                2, 0,
                [("DOH", "LHR", "2026-10-08", 1), ("LHR", "DOH", "2026-10-15", 12)],
                [("Ms", "Alice", "Johnson", "adult"), ("Mr", "Mark", "Johnson", "adult")])
    add_booking(members["alice.j@test.com"], "QR92XN", "Business", "BUS_CLASSIC",
                1, 0,
                [("DOH", "CDG", "2026-11-02", 41)],
                [("Ms", "Alice", "Johnson", "adult")])
    # Bob: Bangkok one-way (Economy Lite — upgrade candidate) + Dubai (earliest trip)
    add_booking(members["bob.c@test.com"], "QB55MD", "Economy", "ECO_LITE",
                1, 0,
                [("DOH", "BKK", "2026-10-12", 826)],
                [("Mr", "Bob", "Chen", "adult")])
    add_booking(members["bob.c@test.com"], "QB31ZA", "Economy", "ECO_COMFORT",
                1, 0,
                [("DOH", "DXB", "2026-10-05", 1002)],
                [("Mr", "Bob", "Chen", "adult")])
    # Carol: New York return (Economy Classic, couple) — check-in candidate
    add_booking(members["carol.d@test.com"], "QC08BV", "Economy", "ECO_CLASSIC",
                2, 0,
                [("DOH", "JFK", "2026-10-20", 701), ("JFK", "DOH", "2026-10-27", 702)],
                [("Mrs", "Carol", "Davis", "adult"), ("Mr", "James", "Davis", "adult")])
    # David: LHR→DOH Business Elite + DOH→SYD First Elite
    add_booking(members["david.k@test.com"], "QD44RS", "Business", "BUS_ELITE",
                1, 0,
                [("LHR", "DOH", "2026-10-03", 4)],
                [("Mr", "David", "Kim", "adult")])
    add_booking(members["david.k@test.com"], "QD77LW", "First", "FIR_ELITE",
                1, 0,
                [("DOH", "SYD", "2026-11-18", 908)],
                [("Mr", "David", "Kim", "adult")])
    db.session.commit()


# Sanity check used by the test suite: the frozen digest must verify.
def _selfcheck():
    from werkzeug.security import check_password_hash
    assert check_password_hash(BENCHMARK_PASSWORD_HASH, "TestPass123!")


def main() -> None:
    """Standalone entry: build instance/qatar_airways.db from scratch (idempotent).

    Importing the app module runs the full bootstrap (create_all + the two
    gated seed functions), so generating the shipped seed is just an import.
    """
    import app  # noqa: F401  (bootstrap runs; seeds are gated)
    print("seeded")


if __name__ == "__main__":
    main()
