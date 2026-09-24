"""Deterministic seed builder for the marriott mirror.

Reads the tracked snapshots under source_data/ (captured from the live
marriott.com; see provenance.json) and materializes the full catalog:

  destinations.json  -> Destination + Hotel rows (with the live site's own
                        per-hotel nightly USD rate for its SSR snapshot dates)
  hotel_details.json -> hotel address, phone, check-in/out, amenities,
                        description, gallery imagery, room imagery
  hotel_reviews.json -> Review rows + the BazaarVoice rating snapshot
  site_content.json   -> Brand taxonomy + Offers (captured from offers.mi)

The whole build is deterministic (PYTHONHASHSEED=0, frozen digests, sorted
iteration) so the SQLite seed is byte-reproducible at image build time.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import date, datetime, timedelta

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"

# Frozen bcrypt digest for the benchmark password 'TestPass123!' (the digest
# is frozen rather than re-generated so the seed DB is byte-identical on every
# rebuild; the digest was produced with Flask-Bcrypt's standard cost factor).
BENCHMARK_PASSWORD_DIGEST = (
    "$2b$12$mTNQa9oqZyOoIJBpKN.0p.LVaApMSu9gZnYufEZrciM5QgBN7EM7u"
)

BENCHMARK_USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "first_name": "Alice",
        "last_name": "Johnson",
        "member_number": "918273645",
        "member_tier": "Gold Elite",
        "points": 148350,
        "joined_on": date(2021, 3, 14),
        "phone": "+1 202-555-0143",
        "street_address": "1245 K Street NW",
        "city": "Washington",
        "state": "District of Columbia",
        "country": "USA",
        "postal_code": "20005",
        "card": ("Visa", "4242", "Alice Johnson", 11, 2028, True),
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "first_name": "Bob",
        "last_name": "Chen",
        "member_number": "817263544",
        "member_tier": "Member",
        "points": 61250,
        "joined_on": date(2023, 7, 2),
        "phone": "+1 415-555-0198",
        "street_address": "88 King Street",
        "city": "San Francisco",
        "state": "California",
        "country": "USA",
        "postal_code": "94107",
        "card": ("Mastercard", "5309", "Bob Chen", 8, 2027, True),
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "first_name": "Carol",
        "last_name": "Davis",
        "member_number": "715243366",
        "member_tier": "Silver Elite",
        "points": 93700,
        "joined_on": date(2022, 1, 21),
        "phone": "+1 312-555-0177",
        "street_address": "330 North Wabash Avenue",
        "city": "Chicago",
        "state": "Illinois",
        "country": "USA",
        "postal_code": "60611",
        "card": ("Amex", "3007", "Carol Davis", 5, 2029, True),
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "first_name": "David",
        "last_name": "Kim",
        "member_number": "649271038",
        "member_tier": "Platinum Elite",
        "points": 274900,
        "joined_on": date(2019, 11, 8),
        "phone": "+1 212-555-0112",
        "street_address": "70 Pine Street",
        "city": "New York",
        "state": "New York",
        "country": "USA",
        "postal_code": "10005",
        "card": ("Visa", "1881", "David Kim", 2, 2028, True),
    },
]

BRAND_CODE_MAP = {
    # destination-payload brandId (the live properties list's own brand code)
    # -> mirror brand code from the captured brands taxonomy
    "RC": "RC", "SR": "SR", "JW": "JW", "LC": "LC", "WH": "WH", "EB": "EB",
    "MC": "MC", "SI": "SI", "WC": "WC", "DE": "DE", "LM": "LM", "RN": "RN",
    "GY": "GY", "CY": "CY", "FP": "FP", "SH": "SH", "FF": "FF", "AC": "AC",
    "CX": "CX", "OX": "OX", "AK": "AK", "GE": "GE", "TR": "TR", "RZ": "RC",
    "TZ": "TZ", "EL": "EL", "MV": "MV", "XR": "SR", "XC": "CY", "XP": "OX",
    "4P": "FP", "AL": "CX", "MO": "OX", "FA": "FF", "SP": "SH", "AU": "AK",
    "TB": "TR", "DS": "GE", "EX": "RZ2", "TP": "TZ", "EC": "EL", "ST": "CY",
    "RE": "RN", "EA": "CY", "SF": "SH", "RCF": "RC", "LG": "LC", "ED": "EB",
    # brandIds the live site's own properties lists use for the newer
    # brands (AC Hotels, Renaissance, Westin, Le Meridien, Fairfield,
    # Residence Inn, Tribute Portfolio, TownePlace Suites, St. Regis,
    # citizenM, Series by Marriott, Apartments by Marriott Bonvoy)
    "AR": "AC", "BR": "RN", "CM": "CM", "FI": "FF", "MD": "LM",
    "RI": "RZ2", "SE": "SE", "TS": "TZ", "TX": "TR", "WI": "WC",
    "BA": "BA",
}

ROOM_TIERS = [
    # (tier name, bed, occupancy, size_sqft, price multiplier, feature list)
    ("Guest Room, 1 King Bed", "1 king bed", 2, 320, 1.0,
     ["Flat-screen TV", "Coffee/tea maker", "Work desk", "In-room safe"]),
    ("Guest Room, 2 Double Beds", "2 double beds", 4, 350, 1.1,
     ["Flat-screen TV", "Coffee/tea maker", "Work desk", "In-room safe"]),
    ("Deluxe Guest Room, 1 King Bed, City View", "1 king bed", 2, 380, 1.35,
     ["City view", "Sitting area", "Mini-fridge", "Nespresso machine"]),
    ("Executive Suite, 1 King Bed", "1 king bed + sofa bed", 3, 560, 1.9,
     ["Separate living room", "Sofa bed", "Nespresso machine", "Bathrobe & slippers"]),
    ("Premium Suite, 1 King Bed, High Floor", "1 king bed + sofa bed", 4, 720, 2.6,
     ["High floor", "Separate dining area", "Upgraded bath amenities", "Club lounge access"]),
]


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return text[:150] or "hotel"


def _load(name: str):
    path = SOURCE / name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _room_features(hotel_index: int, brand: str) -> list:
    """Deterministic per-hotel variation so room inventories differ across
    properties while staying brand-consistent."""
    seeded = (hotel_index * 2654435761) % 2
    return ROOM_TIERS


def _points_rate(base_rate: int) -> int:
    # Marriott Bonvoy free-night redemptions track roughly 100 points per USD
    # of cash rate; round to a clean 500-point step.
    return max(3500, int(round(base_rate * 100 / 500.0)) * 500)


# Amenity labels derived from the hotels' own captured copy: the text the
# live site publishes for each property (the destination-page card blurb and
# the Marriott-authored product description on the reviews page). Only
# amenities evidenced in a hotel's own upstream text are derived; every
# property also carries the Complimentary Wi-Fi baseline the live amenity
# lists show for Marriott Bonvoy hotels.
_AMENITY_PATTERNS = [
    (r"rooftop (?:lounge|bar|terrace|pool)", "Rooftop Lounge"),
    (r"\bindoor pool\b", "Indoor Pool"),
    (r"(?<!indoor )\bpool\b|poolside", "Outdoor Pool"),
    (r"\bspa\b", "Spa"),
    (r"(?:fitness center|fitness room|24-hour fitness|\bgym\b)", "Fitness Center"),
    (r"restaurant", "Restaurant On-Site"),
    (r"\b(?:rooftop )?bar\b|\blounge\b|coffee shop|coffee bar", "Bar/Lounge"),
    (r"(?:free|complimentary) breakfast|breakfast included|breakfast buffet",
     "Breakfast Available"),
    (r"\b(?:full )?kitchen\b|kitchenette", "In-Room Kitchen"),
    (r"all[- ]suite", "All-Suites"),
    (r"grocery", "Grocery Delivery Service"),
    (r"pet[- ]friendly|pets? (?:are )?welcome", "Pet-Friendly"),
    (r"valet parking", "Valet Parking"),
    (r"\bparking\b", "Parking Available"),
    (r"meeting (?:space|room|facilit(?:y|ies))|event space|conference center",
     "Meeting Space"),
    (r"business center", "Business Center"),
    (r"room service", "Room Service"),
    (r"concierge", "Concierge Service"),
    (r"\blaundry\b", "On-Site Laundry"),
    (r"\bterrace\b|\bbalcon(?:y|ies)\b", "Outdoor Terrace"),
    (r"ev charging|electric vehicle charging", "EV Charging Station"),
]


def _derived_amenities(*texts) -> list:
    """Amenity labels evidenced in the hotel's own captured copy."""
    found = []
    blob = " ".join(t for t in texts if t)
    for pattern, label in _AMENITY_PATTERNS:
        if label in found:
            continue
        if re.search(pattern, blob, re.I):
            found.append(label)
    return found


def build_seed(db):
    """Populate the catalog (hotels, destinations, brands, rooms, reviews)."""
    from app import (Brand, Destination, Hotel, HotelImage, RoomType,
                     Review, Offer)

    content = _load("site_content.json") or {"brands": [], "offers": []}

    # ---- brands -------------------------------------------------------
    brand_rows = {}
    for order, b in enumerate(content["brands"], start=1):
        row = Brand(code=b["code"], name=b["name"], category=b["category"],
                    blurb=b["blurb"], site_order=order)
        db.session.add(row)
        brand_rows[b["code"]] = row
    db.session.flush()

    # ---- destinations + hotels ----------------------------------------
    destinations = _load("destinations.json") or []
    details = _load("hotel_details.json") or {}
    # fold in the incremental harvester state (partial captures) so seeded
    # detail fields advance with the resumable harvest
    state_details = json.loads(
        (BASE_DIR / "scraped_data" / "hotel_pages" / "hotel_details_state.json")
        .read_text()) if (BASE_DIR / "scraped_data" / "hotel_pages"
                              / "hotel_details_state.json").exists() else {}
    for marsha, row in state_details.items():
        if row and not row.get("missing") and marsha not in details:
            details[marsha] = row
    reviews_data = _load("hotel_reviews.json") or {}
    products = _load("hotel_products.json") or {}

    dest_rows = {}
    hotel_rows = {}
    hotels_by_dest = {}

    for dest in sorted(destinations, key=lambda d: d["slug"]):
        row = Destination(
            slug=dest["slug"],
            city=dest.get("city") or dest["slug"].replace("-", " ").title(),
            state=dest.get("state"),
            country=dest.get("country") or "USA",
            country_code=dest.get("countryCode") or "US",
            region_path=_region_path(dest),
            destination_name=dest.get("destinationName"),
            latitude=dest.get("latitude"),
            longitude=dest.get("longitude"),
            hero_image=(_mirror_image_path(dest.get("slug") or "x",
                                          (dest.get("hero") or {}).get("url"),
                                          kind="destinations")
                       if (dest.get("hero") or {}).get("url") else None),
            hotel_count=0,
            intro=dest.get("intro"),
            explore=json.dumps(dest.get("explore") or [],
                               ensure_ascii=False),
        )
        db.session.add(row)
        dest_rows[dest["slug"]] = row
        hotels_by_dest[dest["slug"]] = dest.get("hotels") or []

    db.session.flush()

    idx = 0
    for slug in sorted(hotels_by_dest.keys()):
        dest_row = dest_rows[slug]
        dest_hotels = hotels_by_dest[slug]
        count = 0
        for h in sorted(dest_hotels, key=lambda x: (x.get("marsha") or "")):
            marsha = (h.get("marsha") or "").upper()
            if not marsha or marsha in hotel_rows:
                continue
            detail = details.get(marsha) or {}
            product = products.get(marsha) or {}
            brand_code = BRAND_CODE_MAP.get((h.get("brandId") or "").upper()) or "MC"
            brand = brand_rows.get(brand_code) or brand_rows.get("MC")
            slug_field = (h.get("slug") or detail.get("slug") or _slugify(
                detail.get("name") or h.get("title") or marsha))
            name = detail.get("name") or h.get("title") or marsha
            addr = detail.get("address") or {}
            summary = (reviews_data.get(marsha) or {}).get("summary") or {}
            price = h.get("priceValue") or detail.get("base_rate") or 189
            # description chain: live overview copy (captured hotels) ->
            # the Marriott-authored product description the live reviews page
            # uses (BazaarVoice) -> the destination page's own card blurb.
            description = (detail.get("description")
                           or product.get("description")
                           or h.get("description")
                           or f"{name} welcomes Marriott Bonvoy members with member rates and free Wi-Fi.")
            # amenities: the live JSON-LD list when the detail page was
            # captured; otherwise the labels evidenced in the hotel's own
            # captured copy, plus the universal Wi-Fi baseline.
            if detail.get("amenities"):
                amenities = list(detail["amenities"])
            else:
                amenities = _derived_amenities(
                    product.get("description"), h.get("description"))
                if "Complimentary Wi-Fi" not in amenities:
                    amenities.append("Complimentary Wi-Fi")
                amenities.sort()
            hotel = Hotel(
                marsha=marsha,
                slug=slug_field,
                name=name,
                brand_id=brand.id,
                destination_id=dest_row.id,
                address_line=addr.get("street") or "",
                city=addr.get("city") or dest_row.city,
                state=addr.get("region") or dest_row.state,
                country=addr.get("country") or dest_row.country,
                country_code=dest_row.country_code,
                postal_code=addr.get("postalCode"),
                phone=(detail.get("phone") or ""),
                latitude=None,
                longitude=None,
                description=description,
                short_description=h.get("description"),
                checkin_time=detail.get("checkin") or "16:00",
                checkout_time=detail.get("checkout") or "11:00",
                amenities=json.dumps(amenities, sort_keys=True),
                base_rate=int(price),
                points_rate=_points_rate(int(price)),
                rating_avg=summary.get("average"),
                review_count=summary.get("count") or 0,
                rating_distribution=json.dumps(
                    {k: v for k, v in (summary.get("distribution") or {}).items()},
                    sort_keys=True),
                sub_ratings=json.dumps(
                    {k: {"avg": v} for k, v in sorted(
                        (reviews_data.get(marsha) or {}).get(
                            "captured_subrating_averages", {}).items())},
                    sort_keys=True),
                hero_image=None,
                distance_text=h.get("milesText"),
                is_bookable=h.get("bookable") is not False,
            )
            db.session.add(hotel)
            hotel_rows[marsha] = hotel
            count += 1
            idx += 1
        dest_row.hotel_count = count
    db.session.flush()

    # ---- images --------------------------------------------------------
    # card images come from the destination page's own properties list (every
    # hotel has them); the detail harvest adds the fuller gallery + room
    # imagery on top when captured.
    card_images = {}
    for dest in destinations:
        for h in dest.get("hotels") or []:
            marsha = (h.get("marsha") or "").upper()
            if marsha and h.get("images"):
                card_images.setdefault(marsha, []).extend(h["images"])
    for marsha in sorted(hotel_rows.keys()):
        hotel = hotel_rows[marsha]
        detail = details.get(marsha) or {}
        order = 0
        seen_paths = set()

        def add_image(url, alt, category):
            nonlocal order
            if not url:
                return
            path = _mirror_image_path(marsha, url)
            # only reference imagery the asset harvester actually laid down
            # (dead upstream renditions in a wayback capture must not leave
            # the DB pointing at a missing file)
            if not (BASE_DIR / path.lstrip("/")).exists():
                return
            if path in seen_paths:
                return
            seen_paths.add(path)
            db.session.add(HotelImage(
                hotel_id=hotel.id, path=path,
                alt=alt or hotel.name,
                category=category or _image_category(url, alt),
                sort_order=order))
            order += 1
            if order == 1:
                hotel.hero_image = path

        for img in detail.get("gallery", [])[:12]:
            add_image(img.get("url"), img.get("alt"),
                      _image_category(img.get("url") or "", img.get("alt")))
        for img in card_images.get(marsha, []):
            add_image(img.get("url"), img.get("alt"),
                      _image_category(img.get("url") or "", img.get("alt")))
        for img in detail.get("rooms_imagery", [])[:6]:
            add_image(img.get("url"), img.get("alt") or "Guest room", "room")

    db.session.flush()

    # ---- room types -----------------------------------------------------
    for i, marsha in enumerate(sorted(hotel_rows.keys())):
        hotel = hotel_rows[marsha]
        detail = details.get(marsha) or {}
        imagery = detail.get("rooms_imagery") or []
        # every hotel carries real photos from the destination capture; rooms
        # without dedicated rooms-page imagery reuse the property's own real
        # gallery (never a placeholder box)
        hotel_images = [im for im in db.session.query(HotelImage).filter_by(
            hotel_id=hotel.id).order_by(HotelImage.sort_order).all()]
        roomy = [im for im in hotel_images
                 if im.category == "room" or "room" in (im.alt or "").lower()]
        fallback = roomy or hotel_images
        rates_seen = set()
        for tier_i, (name, bed, occupancy, size, mult, features) in enumerate(ROOM_TIERS):
            rate = int(round(hotel.base_rate * mult / 5.0) * 5)
            while rate in rates_seen:
                rate += 5
            rates_seen.add(rate)
            img_path = None
            if imagery and tier_i < len(imagery) and imagery[tier_i].get("url"):
                cand = _mirror_image_path(marsha, imagery[tier_i]["url"])
                if (BASE_DIR / cand.lstrip("/")).exists():
                    img_path = cand
            if img_path is None and fallback:
                img_path = fallback[tier_i % len(fallback)].path
            desc = (f"{name} at {hotel.name}. Sleeps {occupancy} with {bed}. "
                    f"Complimentary Wi-Fi and a work desk come standard.")
            db.session.add(RoomType(
                hotel_id=hotel.id,
                code=f"{'abcdefghijklmnopqrstuvwxyz'[tier_i % 26].upper()}{i}",
                name=name,
                bed_description=bed,
                max_occupancy=occupancy,
                size_sqft=size,
                view=(name.split(", ")[-1] if ", " in name and name.split(", ")[-1].endswith("View") else None),
                features=json.dumps(features),
                description=desc,
                base_rate=rate,
                points_rate=_points_rate(rate),
                image_path=img_path,
                sort_order=tier_i,
            ))

    db.session.flush()

    # ---- reviews ---------------------------------------------------------
    for marsha in sorted(hotel_rows.keys()):
        hotel = hotel_rows[marsha]
        data = reviews_data.get(marsha) or {}
        for rv in data.get("reviews", []):
            if not rv.get("rating") or not rv.get("body"):
                continue
            reviewed = rv.get("date")
            try:
                reviewed_on = datetime.strptime(reviewed, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                reviewed_on = date(2026, 8, 30)
            db.session.add(Review(
                hotel_id=hotel.id,
                author=rv.get("author") or "Marriott Bonvoy member",
                author_location=rv.get("location"),
                rating=int(rv["rating"]),
                title=rv.get("title") or "",
                body=rv["body"],
                trip_type=rv.get("trip_type"),
                reviewed_on=reviewed_on,
                management_response=rv.get("mgmt_response") or None,
            ))

    # ---- offers -----------------------------------------------------------
    for order, o in enumerate(content.get("offers", []), start=1):
        brand = brand_rows.get(o.get("brand")) if o.get("brand") else None
        offer_img = o.get("image")
        db.session.add(Offer(
            title=o["title"],
            blurb=o["blurb"],
            brand_id=brand.id if brand else None,
            cta_label=o.get("cta_label", "View Details"),
            cta_href=o.get("cta_href"),
            image_path=_mirror_image_path(f"{o.get('order', order)}", offer_img,
                                         kind="offers")
                       if offer_img else None,
            book_by=o.get("book_by"),
            stay_dates=o.get("stay_dates"),
            site_order=o.get("order", order),
        ))

    db.session.commit()


def _region_path(dest: dict) -> str:
    """The live /en-us/destinations/<region>.mi path the page was captured
    from (stored by harvest_destinations.py alongside the slug)."""
    path = dest.get("region_path")
    if path:
        return path
    return dest["slug"]


def _mirror_image_path(owner: str, url: str, kind: str = "hotels") -> str:
    """Map an upstream cache.marriott.com rendition URL to the mirrored
    static path the asset harvester downloads it to. The asset harvester
    calls this same function, so DB rows and files stay in sync."""
    ext = ".jpg"
    m = re.search(r"\.(jpe?g|png|tif|tiff|webp)(?:[?#]|$)", url or "", re.I)
    if m:
        if m.group(1).lower() in ("tif", "tiff", "webp"):
            ext = ".jpg"
        else:
            ext = "." + m.group(1).lower()
    filename = re.sub(r"[^a-zA-Z0-9-]+", "-", url.rsplit("/", 1)[-1]).strip("-")
    return f"/static/images/{kind}/{owner.lower()}/{filename}{ext}"


def _image_category(url: str, alt) -> str:
    text = f"{url} {alt or ''}".lower()
    if "guestroom" in text or "bedroom" in text or "suite" in text or "loft" in text:
        return "room"
    if "pool" in text or "fitness" in text or "spa" in text:
        return "amenity"
    if "restaurant" in text or "bar" in text or "dining" in text or "lobby" in text:
        return "dining"
    if "exterior" in text:
        return "exterior"
    return "gallery"


def build_benchmark_users(db, bcrypt=None):
    """Seed the four benchmark accounts with trips, saved hotels and cards."""
    from app import (User, PaymentMethod, Favorite, Reservation, Hotel, RoomType)

    hotel_q = Hotel.query.order_by(Hotel.marsha)
    hotels = hotel_q.all()
    if not hotels:
        return
    first_hotel = hotels[0]
    first_room = RoomType.query.filter_by(hotel_id=first_hotel.id).order_by(RoomType.sort_order).first()

    def room_for(hotel_row):
        return RoomType.query.filter_by(hotel_id=hotel_row.id) \
            .order_by(RoomType.sort_order).first() or first_room

    plan = {
        "alice.j@test.com": [
            # (marsha, checkin offset, nights, status)
            (None, 40, 2, "confirmed"),
            (None, -60, 3, "confirmed"),
            (None, -140, 1, "canceled"),
        ],
        "bob.c@test.com": [
            (None, 25, 1, "confirmed"),
            (None, -30, 4, "confirmed"),
        ],
        "carol.d@test.com": [
            (None, 55, 2, "confirmed"),
            (None, -95, 2, "confirmed"),
        ],
        "david.k@test.com": [
            (None, 18, 3, "confirmed"),
            (None, 32, 2, "confirmed"),
            (None, -75, 5, "confirmed"),
            (None, -200, 2, "confirmed"),
        ],
    }
    # deterministic hotel picks per user
    picks = {
        "alice.j@test.com": [3, 11, 5],
        "bob.c@test.com": [1, 7],
        "carol.d@test.com": [9, 2],
        "david.k@test.com": [4, 13, 6, 9],
    }

    for user_cfg in BENCHMARK_USERS:
        user = User(
            email=user_cfg["email"],
            password_hash=BENCHMARK_PASSWORD_DIGEST,
            first_name=user_cfg["first_name"],
            last_name=user_cfg["last_name"],
            phone=user_cfg["phone"],
            member_number=user_cfg["member_number"],
            member_tier=user_cfg["member_tier"],
            points=user_cfg["points"],
            joined_on=user_cfg["joined_on"],
            street_address=user_cfg["street_address"],
            city=user_cfg["city"],
            state=user_cfg["state"],
            country=user_cfg["country"],
            postal_code=user_cfg["postal_code"],
            created_at=datetime(2026, 9, 1, 0, 0, 0),
        )
        db.session.add(user)
        db.session.flush()

        card_type, last_four, holder, m, y, default = user_cfg["card"]
        db.session.add(PaymentMethod(
            user_id=user.id, card_type=card_type, last_four=last_four,
            holder_name=holder, exp_month=m, exp_year=y,
            is_default=default, added_on=date(2025, 6, 15)))

        entries = plan[user.email]
        chosen = picks[user.email]
        for i, (marsha_unused, offset, nights, status) in enumerate(entries):
            hotel = hotels[chosen[i] % len(hotels)]
            room = room_for(hotel)
            checkin = date(2026, 9, 23) + timedelta(days=offset)
            checkout = checkin + timedelta(days=nights)
            total = room.base_rate * nights
            db.session.add(Reservation(
                confirmation_number=bench_confirmation(user.email, i),
                user_id=user.id,
                hotel_id=hotel.id,
                room_type_id=room.id,
                guest_first_name=user.first_name,
                guest_last_name=user.last_name,
                guest_email=user.email,
                checkin=checkin,
                checkout=checkout,
                adults=2,
                children=1 if i % 2 else 0,
                rooms=1,
                nightly_rate=room.base_rate,
                total_rate=total,
                status=status,
                created_at=datetime(2026, 9, 1, 8, 0, 0),
            ))

        # saved hotels: 3 per user, deterministic picks
        for j in range(3):
            hotel = hotels[(chosen[0] + j * 5 + 2) % len(hotels)]
            exists = Favorite.query.filter_by(user_id=user.id, hotel_id=hotel.id).first()
            if not exists:
                db.session.add(Favorite(user_id=user.id, hotel_id=hotel.id,
                                       saved_on=date(2026, 9, 15)))

    db.session.commit()


def bench_confirmation(email: str, index: int) -> str:
    """Deterministic confirmation numbers for the seeded trips."""
    digest = hashlib.sha256(f"{email}:{index}".encode()).hexdigest()
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(alphabet[int(c, 16) % 32] for c in digest[:10])


if __name__ == "__main__":
    import os
    import shutil

    from app import app, db

    # importing app above already ran the gated bootstrap seeds; calling the
    # gated seed functions again is a no-op (and proves idempotency).
    with app.app_context():
        db.create_all()
        from app import seed_database, seed_benchmark_users
        seed_database()
        seed_benchmark_users()
        from app import Hotel, User
        print("seeded", Hotel.query.count(), "hotels,",
              User.query.count(), "users")

    os.makedirs(os.path.join(BASE_DIR, "instance_seed"), exist_ok=True)
    shutil.copyfile(os.path.join(BASE_DIR, "instance", "marriott.db"),
                    os.path.join(BASE_DIR, "instance_seed", "marriott.db"))
    print("copied seed to instance_seed/marriott.db")
