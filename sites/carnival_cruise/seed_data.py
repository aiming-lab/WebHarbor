"""Deterministic Carnival Cruise Line seed data.

Runs at every container boot and every /reset/carnival_cruise. Each seed
function early-returns on a populated DB so re-seeding is a no-op and the
byte-identical reset invariant holds (even a bare commit on a populated DB
bumps SQLite metadata).

Content sourcing: itineraries, sailing dates, per-stateroom prices, ports,
ships, shore excursions, destinations and info/FAQ copy come from the
committed scrape-derived literals (_seed_catalog.py, _seed_sailings.py,
_seed_ports.py, _seed_ships.py, _seed_destinations.py, _seed_excursions.py,
_seed_info.py) captured from the upstream site on 2026-09-22. Benchmark
users, their bookings, favorites and payment methods are original fixtures
for this mirror; their rewards points follow the real Carnival Rewards
earning rule (3 points per $1 of eligible spend).
"""
import json

from _seed_catalog import ITINERARIES, SCHEDULES
from _seed_destinations import DESTINATIONS
from _seed_excursions import EXCURSIONS
from _seed_ports import PORTS
from _seed_sailings import SAILINGS
from _seed_ships import SHIP_FEATURES, SHIPS

PASSWORD = "TestPass123!"
# Precomputed bcrypt hash of PASSWORD (cost 12). Kept as a literal so the
# seeded database is byte-identical on every reseed — bcrypt's random salt
# would otherwise change the file every boot.
PASSWORD_HASH = "$2b$12$z4B/zPQk3MG1hjlwK3qgWOHuI1ODF7l3H5ic2OyBcUxjsv9a6gOd6"

USERS = [
    {"email": "alice.j@test.com", "first_name": "Alice", "last_name": "Johnson",
     "phone": "305-555-0148", "address1": "485 Brickell Ave", "address2": "Apt 1204",
     "city": "Miami", "state": "FL", "zip_code": "33131",
     "vifp_number": "V38274910", "rewards_tier": "Gold"},
    {"email": "bob.c@test.com", "first_name": "Bob", "last_name": "Chen",
     "phone": "713-555-0172", "address1": "2216 Strand St", "address2": "",
     "city": "Galveston", "state": "TX", "zip_code": "77550",
     "vifp_number": "V51034772", "rewards_tier": "Blue"},
    {"email": "carol.d@test.com", "first_name": "Carol", "last_name": "Davis",
     "phone": "321-555-0139", "address1": "880 George King Blvd", "address2": "Unit 14",
     "city": "Cape Canaveral", "state": "FL", "zip_code": "32920",
     "vifp_number": "V73488265", "rewards_tier": "Red"},
    {"email": "david.k@test.com", "first_name": "David", "last_name": "Kim",
     "phone": "212-555-0117", "address1": "307 W 42nd St", "address2": "Apt 5F",
     "city": "New York", "state": "NY", "zip_code": "10036",
     "vifp_number": "V92816340", "rewards_tier": "Blue"},
]

# Per-user bookings: (itinerary code, departure port, ship code, dur,
#   room_type, room_category, guests, status, sailing_pick, add_excursions)
# sailing_pick selects the Nth sailing (by date) of that itinerary.
USER_BOOKINGS = {
    "alice.j@test.com": [
        ("BAW", "MIA", "CQ", 3, "balcony", "Premium Balcony", 2, "confirmed", 0, True),
        ("CBW", "MIA", "CB", 7, "interior", "Interior", 2, "confirmed", 1, False),
        ("WCD", "MIA", "CQ", 4, "oceanview", "Scenic Ocean View", 3, "cancelled", 0, False),
    ],
    "bob.c@test.com": [
        ("GLA", "GAL", "JB", 4, "interior", "Interior", 2, "confirmed", 0, True),
        ("LXQ", "LAX", "RD", 4, "balcony", "Balcony", 4, "cancelled", 2, False),
    ],
    "carol.d@test.com": [
        ("BH9", "MIA", "SN", 5, "suite", "Grand Suite", 2, "confirmed", 0, True),
        ("BMD", "PCV", "GL", 4, "interior", "Interior", 2, "confirmed", 1, False),
    ],
    "david.k@test.com": [
        ("BR6", "NYC", "FN", 5, "oceanview", "Scenic Ocean View", 2, "confirmed", 0, False),
        ("BMD", "PCV", "GL", 4, "interior", "Interior", 2, "cancelled", 3, False),
    ],
}

USER_FAVORITES = {
    "alice.j@test.com": [("BAW", "MIA"), ("CBW", "MIA"), ("WCD", "MIA"), ("JSL", "PCV")],
    "bob.c@test.com": [("GLA", "GAL"), ("LXQ", "LAX"), ("WCC", "GAL")],
    "carol.d@test.com": [("BH9", "MIA"), ("BAW", "MIA"), ("BMD", "PCV"), ("ECA", "BWI"),
                          ("WSK", "MIA")],
    "david.k@test.com": [("BR6", "NYC"), ("BMD", "PCV"), ("BH9", "MIA"), ("LX5", "LAX"),
                          ("GLA", "GAL"), ("WCP", "GAL")],
}

USER_PAYMENTS = {
    "alice.j@test.com": [
        ("Mastercard", "4242", 9, 2028, True),
        ("Visa", "1881", 4, 2027, False),
    ],
    "bob.c@test.com": [("Visa", "9903", 11, 2027, True)],
    "carol.d@test.com": [
        ("Visa", "5567", 2, 2029, True),
        ("Mastercard", "2208", 7, 2026, False),
    ],
    "david.k@test.com": [("Mastercard", "7701", 5, 2028, True)],
}


# upstream URLs whose extension does not match the real bytes; files are
# stored under the extension matching their content
ONBOARD_EXT_FIX = {
    "amari_bar_tile.png": "amari_bar_tile.jpg",
    "bonded-store-360.png": "bonded-store-360.jpg",
    "pizzeria-del-capitano-tile.png": "pizzeria-del-capitano-tile.jpg",
    "rococo-tile.png": "rococo-tile.jpg",
}
EXCURSION_EXT_FIX = {"305082": "png", "320076": "png"}


def _onboard_image(url):
    if not url:
        return ""
    base = url.split("?")[0].split("/")[-1]
    base = ONBOARD_EXT_FIX.get(base, base)
    return f"static/images/onboard/{base}" if "." in base else ""


def seed_database(db, Ship, ShipHero, ShipFeature, Destination, Port, Itinerary,
                  ItineraryDay, Sailing, Excursion):
    """Populate the catalog. Idempotent: early-returns when populated."""
    if Itinerary.query.count() > 0:
        return

    # ---- ships
    def _intro_text(rec):
        intro = rec.get("intro") or ""
        if isinstance(intro, list):
            return "\n".join(str(x) for x in intro)[:4000]
        return str(intro)[:4000]

    ships_by_code = {}
    for rec in SHIPS:
        ship = Ship(code=rec["code"], name=rec["name"], slug=rec["slug"],
                    hero_image=f"static/images/ships/{rec['slug']}-hero.jpg",
                    intro=_intro_text(rec),
                    long_desc_html=rec.get("long_desc_html") or "",
                    sail_to="|".join((rec.get("compare") or {}).get("sail_to", [])),
                    sail_from="|".join((rec.get("compare") or {}).get("sail_from", [])),
                    durations="|".join((rec.get("compare") or {}).get("durations", [])))
        db.session.add(ship)
        ships_by_code[rec["code"]] = ship
    db.session.flush()
    for rec in SHIPS:
        ship = ships_by_code[rec["code"]]
        for i, h in enumerate(rec.get("hero_images") or []):
            db.session.add(ShipHero(ship_id=ship.id,
                                    url=f"static/images/ships/{rec['slug']}-hero{i + 2}.jpg",
                                    sort=i))
    db.session.flush()
    code_by_slug = {rec["slug"]: rec["code"] for rec in SHIPS}
    for feat in SHIP_FEATURES:
        ship = ships_by_code.get(code_by_slug.get(feat["ship_slug"]))
        if not ship:
            continue
        db.session.add(ShipFeature(
            ship_id=ship.id, kind=feat["kind"], title=feat["title"],
            cost=feat.get("cost"), desc_html=feat.get("desc_html") or "",
            text=feat.get("text") or "",
            image=_onboard_image(feat.get("image_url")),
            sort=feat.get("order", 0)))
    db.session.flush()

    # ---- ports
    ports_by_code = {}
    for rec in PORTS:
        port = Port(code=rec["code"], name=rec["name"],
                    slug=rec.get("slug") or rec["name"].lower().replace(" ", "-"),
                    is_homeport=bool(rec.get("is_homeport")),
                    desc_html=rec.get("desc_html") or "",
                    image=f"static/images/ports/{rec.get('slug') or rec['name'].lower().replace(' ', '-')}.jpg")
        db.session.add(port)
        ports_by_code[rec["code"]] = port
    db.session.flush()

    # ---- destinations
    for rec in DESTINATIONS:
        db.session.add(Destination(
            slug=rec["slug"], name=rec["name"],
            overview="\n\n".join(rec.get("overview") or []),
            things_to_do=json.dumps(rec.get("things_to_do") or []),
            hero_image=f"static/images/destinations/{rec['slug']}.jpg",
            ships_csv="|".join(rec.get("ships") or [])))
    db.session.flush()

    # ---- itineraries + day schedules
    itins_by_key = {}
    for rec in ITINERARIES:
        ship = ships_by_code[rec["ship_code"]]
        port = ports_by_code.get(rec["departure_port_code"])
        if not ship or not port:
            continue
        itin = Itinerary(code=rec["code"], ship_id=ship.id, departure_port_id=port.id,
                         title=rec["title"], url_path=rec["url_path"],
                         region_code=rec["region_code"], region_name=rec["region_name"],
                         dur=rec["dur"], ports_csv="|".join(rec["ports"]),
                         roundtrip=bool(rec["roundtrip"]), from_price=rec["from_price"],
                         image=rec["image"],
                         has_extra_value=bool(rec.get("has_extra_value")))
        db.session.add(itin)
        itins_by_key[(rec["code"], rec["departure_port_code"], rec["ship_code"], rec["dur"])] = itin
    db.session.flush()
    for rec in ITINERARIES:
        itin = itins_by_key.get((rec["code"], rec["departure_port_code"], rec["ship_code"], rec["dur"]))
        if not itin:
            continue
        sched = SCHEDULES.get(f"{rec['code']}|{rec['departure_port_code']}|{rec['ship_code']}|{rec['dur']}", [])
        for day in sched:
            db.session.add(ItineraryDay(itinerary_id=itin.id, day=day["day"],
                                        port_code=day["port_code"], port_name=day["port"],
                                        arrive=day["arrive"] or "", depart=day["depart"] or ""))
    db.session.flush()

    # ---- sailings
    for rec in SAILINGS:
        itin = itins_by_key.get((rec["itinerary_code"], rec["departure_port_code"],
                                 rec["ship_code"], rec["dur"]))
        if not itin:
            continue
        db.session.add(Sailing(sailing_id=rec["sailing_id"], itinerary_id=itin.id,
                               departure_date=rec["departure_date"],
                               arrival_date=rec["arrival_date"],
                               dep_arr=rec["dep_arr"], dep_arr_days=rec["dep_arr_days"],
                               year=rec["year"], interior=rec["interior"],
                               oceanview=rec["oceanview"], balcony=rec["balcony"],
                               suite=rec["suite"], lowest=rec["lowest"]))
    db.session.flush()

    # ---- excursions
    for rec in EXCURSIONS:
        db.session.add(Excursion(
            code=rec["code"], port_slug=rec["port_slug"], title=rec["title"],
            slug=rec.get("slug") or rec["code"], price=rec.get("price"),
            price_unit=rec.get("price_unit") or "", rating=rec.get("rating"),
            review_count=rec.get("review_count") or 0,
            desc_html=rec.get("desc_html") or "",
            image=f"static/images/excursions/{rec['code']}.{EXCURSION_EXT_FIX.get(rec['code'], 'jpg')}",
            duration=rec.get("duration") or "", activity_level=rec.get("activity_level") or "",
            min_age=rec.get("min_age") or ""))
    db.session.flush()
    db.session.commit()


def seed_benchmark_users(db, User, Booking, BookingExcursion, SavedCruise,
                         PaymentMethod, Itinerary, Sailing, Port, Excursion,
                         bcrypt):
    """Create the 4 benchmark users with bookings/favorites/payments.
    Idempotent: early-returns when the first user exists."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    itin_lookup = {}
    for it in Itinerary.query.all():
        itin_lookup[(it.code, it.departure_port.code)] = it

    for spec in USERS:
        user = User(email=spec["email"], first_name=spec["first_name"],
                    last_name=spec["last_name"], phone=spec["phone"],
                    address1=spec["address1"], address2=spec["address2"],
                    city=spec["city"], state=spec["state"], zip_code=spec["zip_code"],
                    vifp_number=spec["vifp_number"], rewards_tier=spec["rewards_tier"])
        user.set_password_hash(PASSWORD_HASH)
        db.session.add(user)
    db.session.flush()

    points = {u["email"]: 0 for u in USERS}
    seq = 0
    cabin_seq = 0
    for spec in USERS:
        user = User.query.filter_by(email=spec["email"]).first()
        for (code, port, ship, dur, room_type, room_cat, guests, status,
             pick, add_excs) in USER_BOOKINGS[spec["email"]]:
            itin = itin_lookup.get((code, port))
            if not itin:
                continue
            sailings = Sailing.query.filter_by(itinerary_id=itin.id).order_by(
                Sailing.departure_date).all()
            if not sailings:
                continue
            sailing = sailings[min(pick, len(sailings) - 1)]
            price = sailing.room_price(room_type) or sailing.lowest
            total = float(price) * guests
            seq += 1
            cabin_seq += 1
            booking = Booking(
                booking_number=f"9N{spec['vifp_number'][1:5]}{seq:02d}",
                user_id=user.id, sailing_id=sailing.id, room_type=room_type,
                room_category=room_cat, guests=guests,
                lead_guest=f"{spec['first_name']} {spec['last_name']}",
                cabin_number=f"{4 + (cabin_seq % 6)}{'BCDEFGHJ'[cabin_seq % 8]}{101 + cabin_seq}",
                total_price=total, status=status)
            db.session.add(booking)
            if status == "confirmed":
                points[spec["email"]] += int(total * 3)
        for (code, port) in USER_FAVORITES[spec["email"]]:
            itin = itin_lookup.get((code, port))
            if itin:
                db.session.add(SavedCruise(user_id=user.id, itinerary_id=itin.id))
        for (ctype, last4, em, ey, is_default) in USER_PAYMENTS[spec["email"]]:
            db.session.add(PaymentMethod(
                user_id=user.id, card_type=ctype, last4=last4,
                holder_name=f"{spec['first_name']} {spec['last_name']}",
                exp_month=em, exp_year=ey, is_default=is_default))
    db.session.flush()

    # booked excursions for flagged bookings: the top-reviewed excursion of
    # the first excursion-capable port on that itinerary.
    for spec in USERS:
        user = User.query.filter_by(email=spec["email"]).first()
        for (code, port, ship, dur, room_type, room_cat, guests, status,
             pick, add_excs) in USER_BOOKINGS[spec["email"]]:
            if not add_excs or status != "confirmed":
                continue
            itin = itin_lookup.get((code, port))
            if not itin:
                continue
            booking = Booking.query.filter(
                Booking.user_id == user.id,
                Booking.sailing_id.in_([s.id for s in
                                       Sailing.query.filter_by(itinerary_id=itin.id).all()]),
                Booking.status == "confirmed").first()
            if not booking:
                continue
            for day in itin.days:
                port_row = Port.query.filter_by(code=day.port_code).first()
                if not port_row or not port_row.slug:
                    continue
                exc = Excursion.query.filter_by(port_slug=port_row.slug).order_by(
                    Excursion.review_count.desc()).first()
                if exc:
                    db.session.add(BookingExcursion(
                        booking_id=booking.id, excursion_id=exc.id,
                        guests=booking.guests,
                        price=(exc.price or 0) * booking.guests))
                    break

    for spec in USERS:
        user = User.query.filter_by(email=spec["email"]).first()
        user.rewards_points = points[spec["email"]]
        user.rewards_stars = points[spec["email"]]

    db.session.commit()
