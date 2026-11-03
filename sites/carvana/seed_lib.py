#!/usr/bin/env python3
"""Deterministic seed builder for the carvana mirror.

Everything materialized here comes from the tracked source_data/*.json
snapshots (captured 2026-09-29) in a fixed order; the four benchmark
accounts and their favorites, orders with delivery schedules and trade-in
offers are authored fixtures following the u_s_customs/zara/ziprecruiter
precedent: every vehicle they reference is a real captured upstream row
(real vehicleId, stock number, VIN, price, photos), and every timestamp is
a frozen constant so the SQLite output is byte-reproducible
(PYTHONHASHSEED=0).
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

BENCHMARK_HASH = (
    '$2b$12$qSds4Mr9Wo7VwPWLhompEer88SuxxXFDp31P9etY6v7nfRctNO7B.')

MIRROR_DATE = "2026-09-29"

CONDITION_MULTIPLIERS = {
    'excellent': 1.00,
    'good': 0.92,
    'fair': 0.78,
    'rough': 0.60,
}


def condition_multiplier(condition):
    return CONDITION_MULTIPLIERS.get(condition, 0.92)


# Upstream bodyStyle keys normalized to the display names the SRP filter
# panel and browse links use.
BODY_STYLE_MAP = {
    'Suv': 'SUV', 'SUV': 'SUV', 'Sedan': 'Sedan', 'Pickup': 'Truck',
    'Truck': 'Truck', 'Hatchback': 'Hatchback', 'Coupe': 'Coupe',
    'Convertible': 'Convertible', 'Wagon': 'Wagon', 'MiniVan': 'Minivan',
    'Minivan': 'Minivan',
}


def vehicle_baseline(vin):
    """Deterministic valuation baseline for the sell-your-car flow.

    Anchored on the captured corpus: the baseline is the median captured
    KBB value ($21,790 across the snapshot) adjusted by a stable hash of
    the VIN, so the same VIN always produces the same offer.
    """
    base = 21790
    h = int(hashlib.sha256(vin.encode()).hexdigest()[:8], 16)
    swing = (h % 9000) - 3000          # -3000 .. +5999
    return max(1500, base + swing)


def _load(source, name):
    with open(os.path.join(source, name), encoding="utf-8") as f:
        return json.load(f)


def _badge_names(v):
    """Vehicle-card badges exactly as the upstream SERP renders them."""
    badges = []
    for tag in v.get("vehicleTags") or []:
        name = tag.get("tagName") if isinstance(tag, dict) else None
        if name:
            badges.append(name)
    if v.get("previousPrice") and v["previousPrice"] > (v.get("price") or {}).get("total", 0):
        if "New Price" not in badges:
            badges.append("New Price")
    return badges


def _vehicle_row(card, details, pricing):
    price = card.get("price") or {}
    det = details or {}
    d = det.get("details") or {}
    photos = det.get("photos") or {}
    terms = pricing or {}
    fuel = card.get("fuelType") or d.get("fuelDescription")
    if fuel and fuel.lower() == "electric":
        engine = d.get("engineDescription") or "Electric Motor"
    else:
        engine = d.get("engineDescription")
    gallery = []
    if photos.get("spin_frames"):
        # the three lightest frames of the upstream 64-frame 360 spin,
        # kept in spin order
        gallery = [u for u in photos["spin_frames"][::5]][:3]
    highlights = []
    for h in d.get("highlights") or []:
        if isinstance(h, dict):
            name = h.get("tagName")
            desc = h.get("tagDescription")
            if name and desc and h.get("isVdpDisplayable", True):
                highlights.append(f"{name} — {desc}")
            elif name:
                highlights.append(name)
    features = []
    for cat in d.get("standardEquipment") or []:
        if isinstance(cat, dict):
            for item in cat.get("items", cat.get("features", [])) or []:
                if isinstance(item, dict):
                    nm = item.get("name")
                    if nm:
                        features.append(nm)
                elif isinstance(item, str):
                    features.append(item)
    options = []
    for o in (d.get("catalogFeatures") or {}).get("options", []):
        nm = o.get("name")
        if nm:
            options.append(nm)
    for p in (d.get("catalogFeatures") or {}).get("packages", []):
        nm = p.get("name")
        if nm:
            options.append(nm)
    for o in d.get("installedOptions") or []:
        if isinstance(o, dict) and o.get("name"):
            options.append(o["name"])
        elif isinstance(o, str):
            options.append(o)
    narratives = []
    for n in d.get("narratives") or []:
        nc = n.get("narrativeContent") or {}
        for b in nc.get("bulletPoints") or []:
            if b.get("title") and b.get("content"):
                narratives.append({"title": b["title"],
                                   "content": b["content"]})
    inspection = []
    rep = d.get("inspectionReport") or {}
    for grp in rep.get("categories", []) or []:
        if isinstance(grp, dict):
            for item in grp.get("features", []) or []:
                if isinstance(item, dict) and item.get("name"):
                    verdict = item.get("verdict") or item.get("status") or ""
                    inspection.append(f"{item['name']}: {verdict}" if verdict
                                      else item["name"])
    for note in rep.get("notes", []) or []:
        if isinstance(note, str):
            inspection.append(note)
    warranty_bits = []
    if d.get("remainingWarrantyMonths"):
        warranty_bits.append(
            f"Basic warranty: {d['remainingWarrantyMonths']} months / "
            f"{d.get('remainingWarrantyMiles', '—')} miles remaining")
    if d.get("remainingDriveTrainWarrantyMonths"):
        warranty_bits.append(
            f"Powertrain warranty: {d['remainingDriveTrainWarrantyMonths']} "
            f"months / {d.get('remainingDriveTrainWarrantyMiles', '—')} miles "
            "remaining")
    prior_uses = card.get("priorUseTypes") or d.get("priorUseTypes") or []
    detail_tags = [str(t.get("tagName") or "")
                   for t in (d.get("highlights") or [])]
    single_owner = any("single owner" in n.lower() for n in detail_tags)
    accident_free = d.get("isAutocheckReportAccidentVehicle") is False
    loc = d.get("location") or {}
    apr = None
    term = None
    taxes = None
    if terms:
        apr = f"{terms.get('apr', 0.0699) * 100:.2f}"
        term = int(terms.get("termInMonths") or 72)
        taxes = int(terms.get("estimatedTaxesAndFees") or 0)
    return {
        "vehicle_id": card["vehicleId"],
        "stock_number": card.get("stockNumber"),
        "year": card.get("year"),
        "make": card.get("make"),
        "model": card.get("model"),
        "trim": card.get("trim") or d.get("trim"),
        "body_style": BODY_STYLE_MAP.get(
            (card.get("bodyStyle") or d.get("bodyType") or "Sedan"),
            card.get("bodyStyle") or d.get("bodyType") or "Sedan"),
        "mileage": card.get("mileage"),
        "price": (price or {}).get("total") or d.get("price"),
        "previous_price": card.get("previousPrice"),
        "kbb_value": (price or {}).get("kbbValue") or d.get("kbbValue"),
        "msrp": (price or {}).get("msrp") or d.get("msrp"),
        "exterior_color": card.get("color") or d.get("exteriorColor"),
        "interior_color": card.get("interiorColor") or d.get("interiorColor"),
        "fuel_type": fuel,
        # The card's milesPerGallon is not a combined rating (and can be
        # mislabeled EV data). Only expose the explicit source field.
        "mpg_combined": d.get("mpgCombined"),
        "transmission": d.get("transmission") or (
            "Automatic" if d.get("automaticTransmission") else None),
        "drivetrain": d.get("drivetrainDescription"),
        "engine": engine,
        "seating": card.get("seatingCapacity") or d.get("seating"),
        "doors": d.get("doors"),
        "vin": card.get("vin") or d.get("vin"),
        "city": loc.get("city"),
        "state": loc.get("stateAbbreviation"),
        "offering": card.get("offering") or d.get("offering"),
        "single_owner": single_owner,
        "accident_free": accident_free,
        "prior_uses": ",".join(prior_uses) if prior_uses else None,
        "card_image": f"card-{card['vehicleId']}",
        "hero_image": f"hero-{card['vehicleId']}" if photos.get("hero") else None,
        "gallery": json.dumps([f"v{card['vehicleId']}-frame-{i}"
                               for i in range(len(gallery))]),
        "interior_image": (f"int-{card['vehicleId']}"
                           if photos.get("interior") else None),
        "badges": json.dumps(_badge_names(card)),
        "highlights": json.dumps(highlights),
        "features": json.dumps(sorted(set(features))),
        "installed_options": json.dumps(sorted(set(options))),
        "narratives": json.dumps(narratives),
        "inspection": json.dumps(sorted(set(inspection))),
        "warranty_text": "; ".join(warranty_bits) or None,
        "in_service_date": (d.get("inServiceDate") or "")[:10] or None,
        "price_dropped_at": (card.get("priceUpdateDate") or "")[:10] or None,
        "apr": apr,
        "default_term": term,
        "estimated_taxes_fees": taxes,
        "has_detail": bool(details),
    }


def seed_all(db, app):
    """Seed vehicles, snapshots and reviews from the tracked snapshots."""
    from app import (Favorite, Order, OrderEvent, Profile, SearchSnapshot,
                     TradeInOffer, User, Vehicle, VehicleReview,
                     HelpArticle)

    source = os.path.join(HERE, "source_data")
    cards = _load(source, "vehicles.json")
    details = _load(source, "vdp_details.json")
    pricing = _load(source, "pricing.json") if os.path.exists(
        os.path.join(source, "pricing.json")) else {}
    snapshots = _load(source, "srp_snapshots.json")
    reviews = _load(source, "reviews.json")

    rows = []
    for card in sorted(cards, key=lambda c: c["vehicleId"]):
        vid = str(card["vehicleId"])
        rows.append(_vehicle_row(card, details.get(vid),
                                 pricing.get(vid)))
    for row in rows:
        db.session.add(Vehicle(**row))
    for snap in snapshots:
        db.session.add(SearchSnapshot(
            key=snap["key"], url=snap["url"],
            upstream_total=snap["upstream_total"],
            page1_order=json.dumps(snap["page1_order"])))
    help_path = os.path.join(source, "help_articles.json")
    if os.path.exists(help_path):
        for a in _load(source, "help_articles.json"):
            db.session.add(HelpArticle(
                section=a["section"], category=a["category"],
                slug=a["slug"], question=a["question"],
                answer=a["answer"]))
    for r in reviews:
        db.session.add(VehicleReview(**r))
    db.session.commit()
    print(f"[seed] vehicles={len(rows)} snapshots={len(snapshots)} "
          f"reviews={len(reviews)}")


def seed_benchmark(db, bcrypt, app):
    """The four benchmark users and their fixtures (Alice/Bob/Carol/Dana)."""
    from app import (Favorite, Order, OrderEvent, Profile, TradeInOffer,
                     User, Vehicle)

    def vid_of(vehicle_id):
        return Vehicle.query.filter_by(vehicle_id=vehicle_id).first()

    users = [
        dict(email='alice.j@test.com', display_name='Alice Johnson'),
        dict(email='bob.c@test.com', display_name='Bob Chen'),
        dict(email='carol.d@test.com', display_name='Carol Davis'),
        dict(email='dana.k@test.com', display_name='Dana Kim'),
    ]
    created = {}
    for u in users:
        row = User(email=u['email'], display_name=u['display_name'],
                   password_hash=BENCHMARK_HASH, is_benchmark=True,
                   created_at='2026-09-01')
        db.session.add(row)
        created[u['email']] = row
    db.session.flush()

    profiles = [
        ('alice.j@test.com', '(206) 555-0142', '2811 Maple Ave', 'Seattle',
         'WA', '98103',
         'Shopping for a reliable commuter to replace my aging sedan.'),
        ('bob.c@test.com', '(480) 555-0187', '5220 E Desert Cove Dr',
         'Scottsdale', 'AZ', '85254',
         'Truck guy. Towing capacity and 4WD matter more to me than MPG.'),
        ('carol.d@test.com', '(312) 555-0119', '1040 N State St', 'Chicago',
         'IL', '60610',
         'Want something fun but practical for city parking.'),
        ('dana.k@test.com', '(617) 555-0163', '77 Beacon St', 'Boston',
         'MA', '02108',
         'EV-curious. Charging at home, so range is my only worry.'),
    ]
    for email, phone, street, city, state, zip5, about in profiles:
        db.session.add(Profile(user_id=created[email].id, phone=phone,
                               street=street, city=city, state=state,
                               zip5=zip5, about=about))
    db.session.flush()

    def fav(email, vehicle_id):
        v = vid_of(vehicle_id)
        if v:
            db.session.add(Favorite(user_id=created[email].id,
                                    vehicle_id=v.id, saved_at=MIRROR_DATE))

    # Alice: three saved cars around her Seattle commute
    for v in _pick_vehicles(db, [('Honda', 'Civic'), ('Toyota', 'RAV4'),
                                ('Tesla', 'Model 3')]):
        fav('alice.j@test.com', v.vehicle_id)
    # Bob: trucks and a Wrangler
    for v in _pick_vehicles(db, [('Ford', 'F150 SuperCrew Cab'),
                                 ('Jeep', 'Wrangler')]):
        fav('bob.c@test.com', v.vehicle_id)
    # Carol: one sporty sedan
    for v in _pick_vehicles(db, [('BMW', '3 Series')]):
        fav('carol.d@test.com', v.vehicle_id)
    # Dana: an EV plus a hybrid
    for v in _pick_vehicles(db, [('Tesla', 'Model Y'), ('Toyota', 'Camry Hybrid')]):
        fav('dana.k@test.com', v.vehicle_id)
    db.session.flush()

    # Orders: one delivered (Bob), one scheduled (Alice), one in financing
    # review (Dana).
    alice_car = _pick_vehicles(db, [('Honda', 'Civic')])[0]
    bob_car = _pick_vehicles(db, [('Ford', 'F150 SuperCrew Cab')])[0]
    dana_car = _pick_vehicles(db, [('Tesla', 'Model Y')])[0]

    bob_order = Order(
        order_number='CV-100019', user_id=created['bob.c@test.com'].id,
        vehicle_id=bob_car.id, payment_type='finance', down_payment=4000,
        trade_credit=0, term_months=72, apr='6.99', monthly_payment=int(
            bob_car.monthly_payment(down_payment=4000, term=72,
                                     apr_percent=6.99)),
        delivery_date='2026-09-12', delivery_slot='10:00 AM - 12:00 PM',
        delivery_street='5220 E Desert Cove Dr', delivery_city='Scottsdale',
        delivery_state='AZ', delivery_zip='85254',
        status='Delivered', created_at='2026-09-02')
    db.session.add(bob_order)
    db.session.flush()
    for status, note, when in [
            ('Order placed', 'Order placed online', '2026-09-02'),
            ('Financing approved', 'Financing approved at 6.99% APR for 72 months', '2026-09-03'),
            ('Delivery scheduled', 'Delivery scheduled for 2026-09-12 (10:00 AM - 12:00 PM) to Scottsdale, AZ', '2026-09-03'),
            ('Out for delivery', 'Vehicle loaded on the delivery truck', '2026-09-12'),
            ('Delivered', 'Vehicle delivered — 7-Day Money-Back Guarantee started', '2026-09-12')]:
        db.session.add(OrderEvent(order_id=bob_order.id, status=status,
                                  note=note, occurred_at=when))

    alice_order = Order(
        order_number='CV-100026', user_id=created['alice.j@test.com'].id,
        vehicle_id=alice_car.id, payment_type='finance', down_payment=2500,
        trade_credit=0, term_months=60, apr='6.24', monthly_payment=int(
            alice_car.monthly_payment(down_payment=2500, term=60,
                                      apr_percent=6.24)),
        delivery_date='2026-10-02', delivery_slot='12:00 PM - 2:00 PM',
        delivery_street='2811 Maple Ave', delivery_city='Seattle',
        delivery_state='WA', delivery_zip='98103',
        status='Delivery scheduled', created_at=MIRROR_DATE)
    db.session.add(alice_order)
    db.session.flush()
    for status, note, when in [
            ('Order placed', 'Order placed online', MIRROR_DATE),
            ('Financing approved', 'Financing approved at 6.24% APR for 60 months', MIRROR_DATE),
            ('Delivery scheduled', 'Delivery scheduled for 2026-10-02 (12:00 PM - 2:00 PM) to Seattle, WA', MIRROR_DATE)]:
        db.session.add(OrderEvent(order_id=alice_order.id, status=status,
                                  note=note, occurred_at=when))

    dana_order = Order(
        order_number='CV-100033', user_id=created['dana.k@test.com'].id,
        vehicle_id=dana_car.id, payment_type='cash', down_payment=0,
        trade_credit=0, term_months=None, apr=None, monthly_payment=None,
        delivery_date='2026-10-05', delivery_slot='8:00 AM - 10:00 AM',
        delivery_street='77 Beacon St', delivery_city='Boston',
        delivery_state='MA', delivery_zip='02108',
        status='Financing review', created_at=MIRROR_DATE)
    db.session.add(dana_order)
    db.session.flush()
    for status, note, when in [
            ('Order placed', 'Order placed online', MIRROR_DATE),
            ('Financing review', 'Cash purchase verification in progress', MIRROR_DATE)]:
        db.session.add(OrderEvent(order_id=dana_order.id, status=status,
                                  note=note, occurred_at=when))

    # A claimed trade-in offer for Bob (his old truck).
    db.session.add(TradeInOffer(
        user_id=created['bob.c@test.com'].id,
        vin='1FTFW1ET5DFC12345', year=2014, make='Ford', model='F-150',
        trim='XLT SuperCrew', mileage=96500, condition='good',
        offer_amount=vehicle_baseline('1FTFW1ET5DFC12345'),
        offer_code='TI-90013', created_at='2026-09-20'))
    db.session.commit()
    print("[seed] benchmark users: 4 (alice/bob/carol/dana)")


def _pick_vehicles(db, specs):
    """First captured vehicle for each (make, model) spec, in spec order."""
    from app import Vehicle
    out = []
    for make, model in specs:
        v = (Vehicle.query.filter(Vehicle.make == make,
                                  Vehicle.model == model)
             .order_by(Vehicle.vehicle_id).first())
        if v:
            out.append(v)
    return out
