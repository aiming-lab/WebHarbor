"""Build-time seed for the Healthgrades mirror.

Reads scraped_data/doctors_raw.jsonl (real doctor profiles captured from
healthgrades.com via Playwright — see scraped_data/scrape.py) and
materializes it into Specialty / Doctor / Review rows. Copies the real
doctor photos captured alongside it into static/images/.

Idempotency lives in app.py (seed_database / seed_benchmark_users each
early-return on a populated table) — this module just does the work.
"""
import json
import os
import random
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED_JSONL = os.path.join(BASE_DIR, 'scraped_data', 'doctors_raw.jsonl')
SCRAPED_IMG_DIR = os.path.join(BASE_DIR, 'scraped_data', 'images')
STATIC_IMG_DIR = os.path.join(BASE_DIR, 'static', 'images')


def _load_records():
    with open(SCRAPED_JSONL) as f:
        return [json.loads(line) for line in f if line.strip()]


def _copy_image(slug):
    src = os.path.join(SCRAPED_IMG_DIR, slug, '0.jpg')
    if not os.path.isfile(src):
        return ''
    dest_dir = os.path.join(STATIC_IMG_DIR, slug)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, '0.jpg')
    if not os.path.exists(dest):
        shutil.copyfile(src, dest)
    return f'images/{slug}/0.jpg'


def _as_list(v):
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def run_seed(db, Specialty, Doctor, Review):
    records = _load_records()

    # ---- specialties ----
    seen_specs = {}
    for r in records:
        if r['specialty_slug'] not in seen_specs:
            seen_specs[r['specialty_slug']] = r['specialty_name']
    for slug, name in seen_specs.items():
        db.session.add(Specialty(slug=slug, name=name))
    db.session.flush()

    # ---- doctors / reviews ----
    for r in records:
        image = _copy_image(r['slug'])
        rating_info = r.get('rating') or {}
        location = r.get('location') or {}
        address = location.get('address') or {}
        geo = location.get('geo') or {}

        hospitals = [h.get('name') for h in _as_list(r.get('hospitalAffiliation')) if h.get('name')]
        hospitals = sorted(set(hospitals))

        education = []
        for a in _as_list(r.get('alumni')):
            school = (a.get('alumniOf') or {}).get('name')
            if school and school not in education:
                education.append(school)

        doctor = Doctor(
            slug=r['slug'],
            name=r['name'],
            specialty_slug=r['specialty_slug'],
            specialty_name=r['specialty_name'],
            description=r.get('description') or '',
            image=image,
            npi=r.get('usNPI') or '',
            street_address=address.get('streetAddress') or '',
            city=address.get('addressLocality') or '',
            state=address.get('addressRegion') or '',
            zip_code=address.get('postalCode') or '',
            latitude=float(geo.get('latitude') or 0.0),
            longitude=float(geo.get('longitude') or 0.0),
            hospital_names=json.dumps(hospitals),
            education=json.dumps(education),
            service_name=(r.get('availableService') or {}).get('name', ''),
            rating=float(rating_info.get('ratingValue') or 0.0),
            review_count=int(rating_info.get('reviewCount') or 0),
            upstream_url=r.get('url') or '',
        )
        db.session.add(doctor)
        db.session.flush()

        for rv in r.get('reviews') or []:
            author = (rv.get('author') or {}).get('name') or 'Patient'
            rating_val = (rv.get('reviewRating') or {}).get('ratingValue') or 5
            try:
                created = datetime.strptime(rv.get('datePublished', ''), '%Y-%m-%d')
            except ValueError:
                created = datetime.utcnow() - timedelta(days=random.randint(1, 400))
            db.session.add(Review(
                doctor_id=doctor.id,
                author_name=author.strip() or 'Patient',
                rating=int(round(rating_val)),
                body=rv.get('reviewBody') or '',
                created_at=created,
            ))

    db.session.commit()


BENCHMARK_USERS = [
    {'name': 'Alice Johnson', 'email': 'alice.j@test.com', 'password': 'TestPass123!',
     'phone': '415-555-0101', 'city': 'San Francisco', 'state': 'CA', 'zip_code': '94102'},
    {'name': 'Bob Chen', 'email': 'bob.c@test.com', 'password': 'TestPass123!',
     'phone': '512-555-0202', 'city': 'Austin', 'state': 'TX', 'zip_code': '78701'},
    {'name': 'Carol Davis', 'email': 'carol.d@test.com', 'password': 'TestPass123!',
     'phone': '212-555-0303', 'city': 'New York', 'state': 'NY', 'zip_code': '10001'},
    {'name': 'David Kim', 'email': 'david.k@test.com', 'password': 'TestPass123!',
     'phone': '312-555-0404', 'city': 'Chicago', 'state': 'IL', 'zip_code': '60601'},
]


def run_seed_users(db, User, SavedDoctor, Appointment, Doctor):
    created = []
    for u in BENCHMARK_USERS:
        user = User(
            name=u['name'], email=u['email'], phone=u['phone'],
            city=u['city'], state=u['state'], zip_code=u['zip_code'],
        )
        user.set_password(u['password'])
        db.session.add(user)
        created.append(user)
    db.session.flush()
    alice, bob, carol, david = created

    doctors = Doctor.query.order_by(Doctor.id).all()
    if not doctors:
        db.session.commit()
        return

    rng = random.Random(7)
    d1, d2, d3, d4, d5, d6 = rng.sample(doctors, 6)

    def _appt(user, doctor, status, days_ago, reason):
        db.session.add(Appointment(
            user_id=user.id, doctor_id=doctor.id, patient_name=user.name,
            reason=reason, preferred_date=(datetime.utcnow() - timedelta(days=days_ago)).strftime('%Y-%m-%d'),
            status=status, created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))

    _appt(alice, d1, 'confirmed', 10, 'Annual checkup')
    _appt(alice, d2, 'requested', 1, 'Follow-up consultation')
    _appt(bob, d3, 'confirmed', 20, 'New patient visit')
    _appt(carol, d4, 'cancelled', 5, 'Second opinion')
    _appt(david, d5, 'requested', 2, 'Persistent symptoms')

    for d in rng.sample(doctors, 3):
        db.session.add(SavedDoctor(user_id=alice.id, doctor_id=d.id))
    for d in rng.sample(doctors, 2):
        db.session.add(SavedDoctor(user_id=bob.id, doctor_id=d.id))

    db.session.commit()
