"""Deterministic seed for the Walmart Careers mirror.

Run directly (`PYTHONHASHSEED=0 python seed_data.py`) to rebuild
`instance_seed/walmart_careers.db` from `catalog_source.py`. The build is
byte-reproducible: one RNG, no wall-clock reads, sorted iteration only, and
werkzeug password hashes hard-coded because werkzeug salts randomly.
"""
from __future__ import annotations

import importlib.util
import os
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import catalog_source as source
from _content import MIRROR_REFERENCE_DATE
from app import (
    Application,
    ApplicationDraft,
    Area,
    Category,
    Job,
    SavedJob,
    SeedMetadata,
    Store,
    User,
    SEED_VERSION,
    app,
    confirmation_for,
    db,
    dumps_json,
)

RNG = random.Random(20260905)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "walmart_careers.db"
INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"

# Hard-coded werkzeug hashes of DEMO_PASSWORD ("TestPass123!"). generate_password_hash
# salts randomly, so recomputing them here would break byte-identical rebuilds.
DEMO_PASSWORD_HASHES = {
    "alice.j@test.com": "scrypt:32768:8:1$x9JMG7iKsrRO1AGh$e8e195799326a6e1ff55d4d20dd2735d9d68c0ed4879bd6b263ac33fa9953b0f6c8505680f1a1d8a9fbe9b0d01ef5e88f99b77b89fc30299fda217185a3b7acf",
    "bob.c@test.com": "scrypt:32768:8:1$O14LIVdpqb3Q6D7E$4b9389cd00aad4417058fd629af5bf979b3f05bdf011791fbc65b7080fe898e50c7aedc2c22be92c71ae25a1df6922bb4ca44b386a7f17040b36888c0cdc8942",
    "carol.d@test.com": "scrypt:32768:8:1$9PGtFS6I89BOEugS$890b1c1935bb6c0c4a6f7f5ad689cc02415e4bd03b02e101f0c2095931d4f157a8504c0fa4f12c3073c94e1480fea3305ffbadc5e8540c5eaf1c16965cb47be7",
    "david.k@test.com": "scrypt:32768:8:1$luqs3gbiT1hPpw2c$09f31fef9514ae90d234cdd91a7f2c95d937e08a37fed60ce0b41755a097609040f7aa5083b94ecdd41804262dc778bd6f8d8e9f38f47f319fa8d6f3ed705d1b",
}

BENCHMARK_USERS = [
    ("alice.j@test.com", "alice.j", "Alice Johnson", "Alice", "Johnson", "479-555-0134", "Bentonville", "AR"),
    ("bob.c@test.com", "bob.c", "Bob Chen", "Bob", "Chen", "206-555-0178", "Seattle", "WA"),
    ("carol.d@test.com", "carol.d", "Carol Davis", "Carol", "Davis", "253-555-0119", "Tacoma", "WA"),
    ("david.k@test.com", "david.k", "David Kim", "David", "Kim", "214-555-0166", "Dallas", "TX"),
]
USER_CREATED_AT = datetime(2026, 6, 12, 9, 30, 0)
EXPECTED_COUNTS = {
    "areas": 7,
    "categories": 33,
    "stores": 51,
    "jobs": 246,
    "users": 4,
    "saved_jobs": 13,
    "applications": 4,
    "application_drafts": 0,
}

# (user email, job title, store number) — resolved to job ids after the catalog is built.
SEED_SAVED_JOBS = [
    ("alice.j@test.com", "Freight Handler", "9046", datetime(2026, 8, 3, 14, 12, 0)),
    ("alice.j@test.com", "Cosmetics Cashier", "2503", datetime(2026, 8, 7, 19, 41, 0)),
    ("alice.j@test.com", "Optician", "5991", datetime(2026, 8, 9, 10, 5, 0)),
    ("alice.j@test.com", "Automation Technician", "6088", datetime(2026, 8, 13, 8, 16, 0)),
    ("alice.j@test.com", "Senior UX Designer", "11807", datetime(2026, 8, 17, 12, 27, 0)),
    ("alice.j@test.com", "Team Lead", "4137", datetime(2026, 8, 22, 17, 58, 0)),
    ("bob.c@test.com", "Asset Protection Associate", "5991", datetime(2026, 8, 4, 8, 22, 0)),
    ("bob.c@test.com", "Class A CDL Truck Driver", "6038", datetime(2026, 8, 11, 16, 48, 0)),
    ("bob.c@test.com", "Senior Data Scientist", "11500", datetime(2026, 8, 20, 12, 3, 0)),
    ("carol.d@test.com", "Pharmacy Technician", "4137", datetime(2026, 8, 6, 7, 55, 0)),
    ("carol.d@test.com", "Cafe Associate", "6318", datetime(2026, 8, 14, 21, 17, 0)),
    ("david.k@test.com", "Merchandising and Stocking Associate", "4750", datetime(2026, 8, 8, 11, 26, 0)),
    ("david.k@test.com", "IT Support Engineer", "10101", datetime(2026, 8, 19, 15, 34, 0)),
]

# (user email, job title, store number, submitted_at)
SEED_APPLICATIONS = [
    ("alice.j@test.com", "Team Lead", "144", datetime(2026, 8, 5, 13, 20, 0)),
    ("bob.c@test.com", "Order Filler", "6014", datetime(2026, 8, 12, 9, 2, 0)),
    ("carol.d@test.com", "Optician", "2073", datetime(2026, 8, 16, 17, 44, 0)),
    ("david.k@test.com", "Financial Analyst III", "11500", datetime(2026, 8, 21, 10, 11, 0)),
]

HERO_SETS = {
    "salaried": ["jobhero-corp-1.jpg", "jobhero-corp-2.jpg", "jobhero-corp-3.jpg"],
    "sams": ["jobhero-sams-1.png", "jobhero-sams-2.jpg", "jobhero-wm-2.jpg"],
    "walmart": ["jobhero-wm-1.png", "jobhero-wm-3.jpg", "jobhero-wm-4.jpg"],
    "walmart-alt": ["jobhero-wm-4.jpg", "jobhero-wm-2.jpg", "jobhero-wm-1.png"],
}

HOURLY_CLOSING = (
    "At Walmart, we offer competitive pay as well as performance-based incentive awards and other "
    "great benefits for a happier mind, body, and wallet. Health benefits include medical, vision and "
    "dental coverage. Financial benefits include 401(k), stock purchase and company-paid life "
    "insurance. Paid time off benefits include parental leave, family care leave, bereavement, jury "
    "duty, and voting."
)
LBU_CLOSING = (
    "Live Better U is a Walmart-paid education benefit program for full-time and part-time associates "
    "in Walmart and Sam's Club facilities. Programs range from high school completion to bachelor's "
    "degrees, including English Language Learning and short-form certificates. Tuition, books, and "
    "fees are completely paid for by Walmart."
)


# --------------------------------------------------------------------------- #
# Catalog construction
# --------------------------------------------------------------------------- #
def _shift_names(codes: str) -> list[str]:
    return [source.SHIFT_CODES[c] for c in codes.split(",")]


def _build_areas() -> dict[str, Area]:
    areas: dict[str, Area] = {}
    for slug, name, order, blurb, hero, has_index, filterable in source.AREAS:
        area = Area(
            slug=slug,
            name=name,
            display_order=order,
            blurb=blurb,
            hero_image=hero,
            has_index_page=has_index,
            is_filterable=filterable,
        )
        db.session.add(area)
        areas[slug] = area
    db.session.flush()
    return areas


def _build_categories(areas: dict[str, Area]) -> dict[tuple[str, str], Category]:
    categories: dict[tuple[str, str], Category] = {}
    for area_slug, name, slug, order in source.CATEGORIES:
        category = Category(
            area_id=areas[area_slug].id, name=name, slug=slug, display_order=order
        )
        db.session.add(category)
        categories[(area_slug, name)] = category
    db.session.flush()
    return categories


def _build_stores() -> dict[str, Store]:
    stores: dict[str, Store] = {}
    for row in source.STORES:
        (number, banner, location_name, street, city, state, zip_code,
         lat, lng, is_hub, is_office, _brand) = row
        hub_name, hub_blurb, hub_image = source.HUB_COPY.get(number, (None, None, None))
        store = Store(
            store_number=number,
            banner=banner,
            location_name=location_name,
            street=street,
            city=city,
            state=state,
            zip=zip_code,
            lat=lat,
            lng=lng,
            is_hub=is_hub,
            is_office=is_office,
            hub_name=hub_name,
            hub_blurb=hub_blurb,
            hub_image=hub_image,
        )
        db.session.add(store)
        stores[number] = store
    db.session.flush()
    return stores


def _store_brand() -> dict[str, str]:
    return {row[0]: row[11] for row in source.STORES}


def _hero_for(population: str, brand: str, index: int) -> list[str]:
    if population == "salaried":
        pool = HERO_SETS["salaried"]
    elif brand == "Sam's Club":
        pool = HERO_SETS["sams"]
    elif index % 2:
        pool = HERO_SETS["walmart-alt"]
    else:
        pool = HERO_SETS["walmart"]
    return list(pool)


def _build_jobs(areas, categories, stores) -> list[Job]:
    brands = _store_brand()
    trending = set(source.TRENDING_JOB_IDS)
    used_ids: set[str] = set()
    for family in source.HOURLY_FAMILIES:
        for placement in family["placements"]:
            extras = placement[6] or {}
            if "job_id" in extras:
                used_ids.add(extras["job_id"])
    for family in source.SALARIED_FAMILIES:
        for placement in family["placements"]:
            extras = placement[6] or {}
            if "job_id" in extras:
                used_ids.add(extras["job_id"])

    jobs: list[Job] = []
    store_cursor: dict[str, int] = {}
    index = 0

    for family in source.HOURLY_FAMILIES:
        area = areas[family["area"]]
        category = categories[(family["area"], family["category"])]
        for placement in family["placements"]:
            store_no, emp_type, codes, min_pay, max_pay, positions, extras = placement
            extras = extras or {}
            store = stores[store_no]
            brand = brands[store_no]
            cursor = store_cursor.get(store_no, 10200) + RNG.randint(120, 980)
            job_id = extras.get("job_id")
            if job_id is None:
                job_id = f"CP-{store_no}-{cursor}"
                while job_id in used_ids:
                    cursor += 37
                    job_id = f"CP-{store_no}-{cursor}"
            store_cursor[store_no] = cursor
            used_ids.add(job_id)

            fmt = {
                "banner": store.banner,
                "store": store.store_number,
                "city": store.city,
                "state": store.state,
                "location_name": store.location_name,
            }
            paragraphs = [p.format(**fmt) for p in family["do"]]
            paragraphs.append(HOURLY_CLOSING)
            paragraphs.append(LBU_CLOSING)
            primary_code = codes.split(",")[0]
            job = Job(
                job_id=job_id,
                population="hourly",
                title=family["title"],
                brand=brand,
                store_id=store.id,
                area_id=area.id,
                category_id=category.id,
                shifts_json=dumps_json(_shift_names(codes)),
                employment_type=emp_type,
                pay_frequency="Hourly",
                min_pay=min_pay,
                max_pay=max_pay,
                posted_date=MIRROR_REFERENCE_DATE - timedelta(days=RNG.randint(1, 120)),
                sort_rank=0,
                is_trending=job_id in trending,
                summary=family["summary"].format(**fmt),
                description="\n\n".join(paragraphs),
                additional_description_json=dumps_json(
                    [b.format(**fmt) for b in family["bring"]]
                ),
                hashtag=family.get("hashtag"),
                shift_time=extras.get("shift_time", source.SHIFT_WINDOWS[primary_code]),
                positions_available=positions,
                min_age_note=emp_type != "Intern",
                hero_images_json=dumps_json(_hero_for("hourly", brand, index)),
            )
            db.session.add(job)
            jobs.append(job)
            index += 1

    salaried_cursor = 2410000
    posting_seq = 5210000
    for family in source.SALARIED_FAMILIES:
        area = areas[family["area"]]
        category = categories[(family["area"], family["category"])]
        for placement in family["placements"]:
            store_no, emp_type, min_pay, max_pay, worker_type, slots, extras = placement
            extras = extras or {}
            store = stores[store_no]
            brand = brands[store_no]
            salaried_cursor += RNG.randint(150, 900)
            job_id = extras.get("job_id")
            if job_id is None:
                job_id = f"R-{salaried_cursor}"
                while job_id in used_ids:
                    salaried_cursor += 13
                    job_id = f"R-{salaried_cursor}"
            used_ids.add(job_id)
            posting_seq += RNG.randint(400, 4000)

            degree_field, y1, y2, yp = slots
            fmt = {
                "banner": store.banner,
                "store": store.store_number,
                "city": store.city,
                "state": store.state,
                "location_name": store.location_name,
                "degree_field": degree_field,
                "y1": y1,
                "y2": y2,
                "yp": yp,
            }
            paragraphs = [p.format(**fmt) for p in family["do"]]
            clause = extras.get("qual_clause")

            def qualification(template: str) -> str:
                text = template.format(**fmt)
                if clause:
                    text = text.rstrip(".") + ", " + clause + "."
                return text

            bring = [b.format(**fmt) for b in source.SALARIED_BRING[family["category"]]]
            job = Job(
                job_id=job_id,
                population="salaried",
                title=family["title"],
                brand=brand,
                store_id=store.id,
                area_id=area.id,
                category_id=category.id,
                shifts_json=dumps_json(_shift_names(family["shifts"])),
                employment_type=emp_type,
                pay_frequency="Annual",
                min_pay=min_pay,
                max_pay=max_pay,
                posted_date=MIRROR_REFERENCE_DATE - timedelta(days=RNG.randint(1, 120)),
                sort_rank=0,
                is_trending=job_id in trending,
                summary=family["summary"].format(**fmt),
                description="\n\n".join(paragraphs),
                about_team=family["about_team"].format(**fmt),
                additional_description_json=dumps_json(bring),
                hashtag=None,
                shift_time=None,
                positions_available=None,
                min_age_note=False,
                worker_type=worker_type,
                job_posting_id=f"JOB_POSTING-3-{posting_seq}",
                min_qualifications_json=dumps_json(
                    [
                        qualification(family["min_qual_option1"]),
                        qualification(family["min_qual_option2"]),
                    ]
                ),
                preferred_qualifications=family["preferred"].format(**fmt),
                hero_images_json=dumps_json(_hero_for("salaried", brand, index)),
            )
            db.session.add(job)
            jobs.append(job)
            index += 1

    ranks = list(range(len(jobs)))
    RNG.shuffle(ranks)
    for job, rank in zip(jobs, ranks):
        job.sort_rank = rank
    db.session.flush()
    return jobs


# --------------------------------------------------------------------------- #
# Seed entry points
# --------------------------------------------------------------------------- #
def seed_database(force: bool = False) -> None:
    if Job.query.count() > 0 and not force:
        return
    RNG.seed(20260905)
    areas = _build_areas()
    categories = _build_categories(areas)
    stores = _build_stores()
    _build_jobs(areas, categories, stores)


def seed_benchmark_users(force: bool = False) -> None:
    if User.query.count() > 0 and not force:
        return
    users: dict[str, User] = {}
    for email, username, display, first, last, phone, city, state in BENCHMARK_USERS:
        user = User(
            email=email,
            username=username,
            display_name=display,
            first_name=first,
            last_name=last,
            phone=phone,
            city=city,
            state=state,
            password_hash=DEMO_PASSWORD_HASHES[email],
            created_at=USER_CREATED_AT,
        )
        db.session.add(user)
        users[email] = user
    db.session.flush()

    for email, title, store_number, saved_at in SEED_SAVED_JOBS:
        job = _find_job(title, store_number)
        db.session.add(SavedJob(user_id=users[email].id, job_id=job.job_id, saved_at=saved_at))

    for email, title, store_number, submitted_at in SEED_APPLICATIONS:
        job = _find_job(title, store_number)
        user = users[email]
        application = Application(
            job_id=job.job_id,
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            status="Submitted",
            confirmation_no="pending",
            submitted_at=submitted_at,
        )
        db.session.add(application)
        db.session.flush()
        application.confirmation_no = confirmation_for(application.id)



def _find_job(title: str, store_number: str) -> Job:
    store = Store.query.filter_by(store_number=store_number).one()
    job = (
        Job.query.filter_by(title=title, store_id=store.id)
        .order_by(Job.job_id)
        .first()
    )
    if job is None:
        raise RuntimeError(f"no seeded job {title!r} at store {store_number}")
    return job


# --------------------------------------------------------------------------- #
# Build-time invariant checks.
#
# The benchmark task locators and their expected answers live in
# scripts_dev/assert_distractors.py, which is git-ignored and docker-ignored and
# therefore absent from the shipped tree. The freezer loads it by path when it is
# there, so a developer rebuild still fails on a catalog edit that breaks a task;
# a tree without it builds the same database and skips the checks.
# --------------------------------------------------------------------------- #
def _load_distractor_checks():
    path = BASE_DIR / "scripts_dev" / "assert_distractors.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("walmart_careers_assert_distractors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assert_distractors


def _current_counts() -> dict[str, int]:
    return {
        "areas": Area.query.count(),
        "categories": Category.query.count(),
        "stores": Store.query.count(),
        "jobs": Job.query.count(),
        "users": User.query.count(),
        "saved_jobs": SavedJob.query.count(),
        "applications": Application.query.count(),
        "application_drafts": ApplicationDraft.query.count(),
    }


def _seed_is_complete() -> bool:
    marker = db.session.get(SeedMetadata, "version")
    counts = _current_counts()
    core_counts_match = all(counts[key] == EXPECTED_COUNTS[key] for key in ("areas", "categories", "stores", "jobs"))
    benchmark_emails = {email for (email, *_rest) in BENCHMARK_USERS}
    present_emails = {row.email for row in User.query.filter(User.email.in_(benchmark_emails)).all()}
    return marker is not None and marker.value == SEED_VERSION and core_counts_match and present_emails == benchmark_emails


def _database_has_seed_rows() -> bool:
    return any(_current_counts().values()) or SeedMetadata.query.count() > 0


def _validate_seed() -> None:
    counts = _current_counts()
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"seed row counts differ: expected={EXPECTED_COUNTS}, actual={counts}")
    violations = db.session.execute(text("PRAGMA foreign_key_check")).all()
    if violations:
        raise RuntimeError(f"seed foreign-key violations: {violations[:5]}")


def ensure_seed_database() -> None:
    if _seed_is_complete():
        return
    if _database_has_seed_rows():
        raise RuntimeError("walmart_careers database is partial, unversioned, or from another seed version")
    try:
        seed_database(force=True)
        seed_benchmark_users(force=True)
        _validate_seed()
        db.session.add(SeedMetadata(key="version", value=SEED_VERSION))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def build_seed_database() -> None:
    INSTANCE_SEED_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    destination = INSTANCE_SEED_DIR / "walmart_careers.db"
    checks = _load_distractor_checks()
    try:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if DB_PATH.exists():
            DB_PATH.unlink()
        with app.app_context():
            db.create_all()
            ensure_seed_database()
            if checks is not None:
                checks()
            db.session.remove()
            db.engine.dispose()
        temporary = destination.with_suffix(".db.tmp")
        shutil.copyfile(DB_PATH, temporary)
        os.replace(temporary, destination)
    except Exception:
        destination.with_suffix(".db.tmp").unlink(missing_ok=True)
        DB_PATH.unlink(missing_ok=True)
        raise
    if checks is None:
        print("scripts_dev/assert_distractors.py not present - tracked tests provide the release invariants.")


if __name__ == "__main__":
    build_seed_database()
    print("Seed database generated from the deterministic Walmart Careers source catalog.")
