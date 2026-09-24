"""Build-time seed for the Kelley Blue Book mirror.

Reads scraped_data/vehicles_raw.jsonl (real model-year pricing/specs/FAQ
captured from kbb.com via Playwright — see scraped_data/scrape.py) and
materializes it into Make / Vehicle / VehicleTrim / VehicleFAQ rows.
Copies the real vehicle photos captured alongside it into static/images/.

Idempotency lives in app.py (seed_database / seed_benchmark_users each
early-return on a populated table) — this module just does the work.
"""
import json
import os
import random
import re
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED_JSONL = os.path.join(BASE_DIR, 'scraped_data', 'vehicles_raw.jsonl')
SCRAPED_IMG_DIR = os.path.join(BASE_DIR, 'scraped_data', 'images')
STATIC_IMG_DIR = os.path.join(BASE_DIR, 'static', 'images')

MAKE_NAMES = {
    'toyota': 'Toyota', 'honda': 'Honda', 'ford': 'Ford', 'chevrolet': 'Chevrolet',
    'jeep': 'Jeep', 'kia': 'Kia', 'hyundai': 'Hyundai', 'nissan': 'Nissan',
    'subaru': 'Subaru', 'mazda': 'Mazda', 'bmw': 'BMW', 'mercedes-benz': 'Mercedes-Benz',
    'audi': 'Audi', 'tesla': 'Tesla',
}


def _load_records():
    with open(SCRAPED_JSONL) as f:
        return [json.loads(line) for line in f if line.strip()]


def _copy_images(slug):
    src_dir = os.path.join(SCRAPED_IMG_DIR, slug)
    if not os.path.isdir(src_dir):
        return []
    dest_dir = os.path.join(STATIC_IMG_DIR, slug)
    os.makedirs(dest_dir, exist_ok=True)
    rel_paths = []
    for fname in sorted(os.listdir(src_dir)):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        src = os.path.join(src_dir, fname)
        dest = os.path.join(dest_dir, fname)
        if not os.path.exists(dest):
            shutil.copyfile(src, dest)
        rel_paths.append(f'images/{slug}/{fname}')
    return rel_paths


def _parse_price(text):
    m = re.search(r'[\d,]+', text or '')
    return float(m.group(0).replace(',', '')) if m else 0.0


def _model_name(title, year):
    # title looks like "2026 Toyota Camry Price, Reviews, Pictures & More | Kelley Blue Book"
    m = re.match(r'\d{4}\s+\S+\s+(.+?)\s+Price,', title or '')
    return m.group(1) if m else ''


def run_seed(db, Make, Vehicle, VehicleTrim, VehicleFAQ):
    records = _load_records()

    for slug, name in MAKE_NAMES.items():
        db.session.add(Make(slug=slug, name=name))
    db.session.flush()

    for r in records:
        images = _copy_images(r['slug'])
        trims_raw = r.get('trims') or []
        prices = [_parse_price(t['price']) for t in trims_raw if t.get('price')]
        min_price = min(prices) if prices else 0.0
        max_price = max(prices) if prices else 0.0
        model_name = _model_name(r.get('title', ''), r['year']) or r['model'].replace('-', ' ').title()
        spec_labels = list(trims_raw[0]['specs'].keys()) if trims_raw and trims_raw[0].get('specs') else []

        vehicle = Vehicle(
            slug=r['slug'],
            make_slug=r['make'],
            make_name=MAKE_NAMES.get(r['make'], r['make'].title()),
            model=r['model'],
            model_name=model_name,
            year=int(r['year']),
            title=f"{r['year']} {MAKE_NAMES.get(r['make'], r['make'].title())} {model_name}",
            pros=json.dumps(r.get('pros') or []),
            cons=json.dumps(r.get('cons') or []),
            rating=float(r.get('rating') or 0.0),
            review_count=int(r.get('review_count') or 0),
            min_price=min_price,
            max_price=max_price,
            spec_labels=json.dumps(spec_labels),
            image=images[0] if images else '',
            gallery_images=json.dumps(images),
            upstream_url=r.get('url') or '',
        )
        db.session.add(vehicle)
        db.session.flush()

        for t in trims_raw:
            specs = t.get('specs') or {}
            db.session.add(VehicleTrim(
                vehicle_id=vehicle.id,
                name=t.get('name', ''),
                price=_parse_price(t.get('price', '')),
                specs=json.dumps([specs.get(label, '') for label in spec_labels]),
            ))

        for qa in r.get('faq') or []:
            db.session.add(VehicleFAQ(
                vehicle_id=vehicle.id,
                question=qa.get('question', ''),
                answer=qa.get('answer', ''),
            ))

    db.session.commit()


BENCHMARK_USERS = [
    {'name': 'Alice Johnson', 'email': 'alice.j@test.com', 'password': 'TestPass123!',
     'phone': '415-555-0101', 'zip_code': '94102'},
    {'name': 'Bob Chen', 'email': 'bob.c@test.com', 'password': 'TestPass123!',
     'phone': '512-555-0202', 'zip_code': '78701'},
    {'name': 'Carol Davis', 'email': 'carol.d@test.com', 'password': 'TestPass123!',
     'phone': '212-555-0303', 'zip_code': '10001'},
    {'name': 'David Kim', 'email': 'david.k@test.com', 'password': 'TestPass123!',
     'phone': '312-555-0404', 'zip_code': '60601'},
]


def run_seed_users(db, User, SavedVehicle, QuoteRequest, Vehicle):
    created = []
    for u in BENCHMARK_USERS:
        user = User(name=u['name'], email=u['email'], phone=u['phone'], zip_code=u['zip_code'])
        user.set_password(u['password'])
        db.session.add(user)
        created.append(user)
    db.session.flush()
    alice, bob, carol, david = created

    vehicles = Vehicle.query.order_by(Vehicle.id).all()
    if not vehicles:
        db.session.commit()
        return

    rng = random.Random(11)
    v1, v2, v3, v4, v5, v6 = rng.sample(vehicles, 6)

    def _quote(user, vehicle, status, days_ago):
        db.session.add(QuoteRequest(
            user_id=user.id, vehicle_id=vehicle.id,
            trim_name=(vehicle.trims[0].name if vehicle.trims else ''),
            zip_code=user.zip_code, status=status,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))

    _quote(alice, v1, 'contacted', 10)
    _quote(alice, v2, 'pending', 1)
    _quote(bob, v3, 'contacted', 20)
    _quote(carol, v4, 'closed', 5)
    _quote(david, v5, 'pending', 2)

    for v in rng.sample(vehicles, 3):
        db.session.add(SavedVehicle(user_id=alice.id, vehicle_id=v.id))
    for v in rng.sample(vehicles, 2):
        db.session.add(SavedVehicle(user_id=bob.id, vehicle_id=v.id))

    db.session.commit()
