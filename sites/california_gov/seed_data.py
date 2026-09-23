"""Deterministic CA.gov seed data.

Runs at build time to materialize instance/california_gov.db and at every
container boot; each seed function early-returns on a populated DB so
re-seeding is a no-op and the byte-identical reset invariant holds.

Content sourcing: every department, service, FAQ, topic, popular ranking and
press-release headline mirrors the real https://www.ca.gov/ directory via the
committed scrape-derived literals in _seed_departments.py, _seed_services.py,
_seed_topics.py and _seed_content.py. Homepage "California by the numbers"
figures and the officials cards carry the upstream homepage copy.
"""
from _seed_content import NEWS
from _seed_departments import DEPARTMENTS
from _seed_services import SERVICES
from _seed_topics import HOMEPAGE_SERVICES, POPULAR_DEPARTMENTS, POPULAR_SERVICES, TOPICS

from app import (Department, DepartmentTopic, Faq, HomePageStat, NewsItem,
                 Official, Service, ServiceTopic, Topic, TopicCard, db)

# Real homepage copy (upstream "California by the numbers" cards).
HOMEPAGE_STATS = [
    {"value": "39", "value_suffix": "", "unit": "million",
     "description": "California is home to nearly 40 million residents. One in four Californians is born overseas."},
    {"value": "15", "value_suffix": "%", "unit": "of the US GDP",
     "description": "California contributes almost 15% to the US GDP. It is the world's fourth-largest economy."},
    {"value": "9", "value_suffix": "", "unit": "national parks",
     "description": "With the most national parks in the US, California also boasts 87 state parks and 63 state beaches."},
]

# Real homepage officials cards (upstream section "Government officials").
OFFICIALS = [
    {"role": "Governor", "name": "Gavin Newsom", "seal": "images/homepage/ca-for-all-logo.webp",
     "seal_alt": "California for All logo",
     "link_label": "Visit the Governor’s website", "link_url": "https://www.gov.ca.gov"},
    {"role": "Lieutenant Governor", "name": "Eleni Kounalakis",
     "seal": "images/homepage/ca-state-seal.webp",
     "seal_alt": "The great seal of the state of California",
     "link_label": "Visit the Lt. Governor’s website", "link_url": "https://ltg.ca.gov/"},
    {"role": "Governor’s cabinet", "name": None, "seal": "images/homepage/ca-gov-seal.webp",
     "seal_alt": "The Governor of Californiia seal",
     "link_label": "Visit the Governor’s cabinet website", "link_url": "https://www.gov.ca.gov/about/cabinet/"},
]

# Landing-page card copy (upstream services landing).
TOPIC_NAMES = {t["slug"]: t for t in TOPICS}


def _seed_topics() -> None:
    if Topic.query.count() > 0:
        return
    order = 0
    for row in TOPICS:
        order += 1
        db.session.add(Topic(slug=row["slug"], name=row["name"],
                            landing_description=row.get("landing_description"),
                            description=row.get("description"),
                            description_html=row.get("description_html"),
                            lineart=row.get("lineart"), position=order))


def _topic_id_by_name(name):
    return db.session.query(Topic.id).filter_by(name=name).first()


def _seed_departments() -> None:
    if Department.query.count() > 0:
        return
    popular_rank = {dept_id: i + 1 for i, dept_id in enumerate(POPULAR_DEPARTMENTS)}
    for row in DEPARTMENTS:
        db.session.add(Department(
            id=row["id"],
            name=row["name"],
            list_name=row.get("list_name") or row["name"],
            abbr=row.get("abbr"),
            description=row.get("description"),
            phone=row.get("phone"),
            phone_digits=row.get("phone_digits"),
            website=row.get("website"),
            more_contact=row.get("more_contact"),
            socials_json=_dumps(row.get("socials", [])),
            apps_json=_dumps(row.get("apps", [])),
            logo=row.get("logo"),
            last_updated=row.get("last_updated"),
            directory_rank=row.get("directory_rank"),
            popular_rank=popular_rank.get(row["id"]),
        ))
    db.session.flush()
    for row in DEPARTMENTS:
        position = 0
        for topic_name in row.get("topics", []):
            found = _topic_id_by_name(topic_name)
            if not found:
                continue
            position += 1
            db.session.add(DepartmentTopic(
                department_id=row["id"], topic_id=found[0], position=position))
        position = 0
        for faq in row.get("faqs", []):
            position += 1
            db.session.add(Faq(department_id=row["id"], question=faq["question"],
                               answer=faq.get("answer"), position=position))


def _dumps(value):
    import json

    return json.dumps(value, ensure_ascii=False)


def _seed_services() -> None:
    if Service.query.count() > 0:
        return
    popular_rank = {ref["service_id"]: i + 1 for i, ref in enumerate(POPULAR_SERVICES)}
    popular_label = {ref["service_id"]: ref["label"] for ref in POPULAR_SERVICES}
    homepage_rank = {ref["service_id"]: i + 1 for i, ref in enumerate(HOMEPAGE_SERVICES)}
    homepage_label = {ref["service_id"]: ref["label"] for ref in HOMEPAGE_SERVICES}
    for row in SERVICES:
        db.session.add(Service(
            id=row["id"],
            department_id=row["department_id"],
            name=row["name"],
            description=row.get("description"),
            phone=row.get("phone"),
            phone_digits=row.get("phone_digits"),
            launch_url=row.get("launch_url"),
            contact_url=row.get("contact_url"),
            dept_website=row.get("dept_website"),
            image=row.get("image"),
            last_updated=row.get("last_updated"),
            keywords_json=_dumps(row.get("keywords", [])),
            directory_rank=row.get("directory_rank"),
            dept_rank=row.get("dept_rank"),
            popular_rank=popular_rank.get(row["id"]),
            popular_label=popular_label.get(row["id"]),
            homepage_rank=homepage_rank.get(row["id"]),
            homepage_label=homepage_label.get(row["id"]),
        ))
    db.session.flush()
    for row in SERVICES:
        position = 0
        for faq in row.get("faqs", []):
            position += 1
            db.session.add(Faq(service_id=row["id"], question=faq["question"],
                               answer=faq.get("answer"), position=position))
        position = 0
        for topic_name in row.get("topics", []):
            found = _topic_id_by_name(topic_name)
            if not found:
                continue
            position += 1
            db.session.add(ServiceTopic(
                service_id=row["id"], topic_id=found[0], position=position))


def _seed_topic_cards() -> None:
    if TopicCard.query.count() > 0:
        return
    for row in TOPICS:
        topic = db.session.query(Topic).filter_by(slug=row["slug"]).first()
        if not topic:
            continue
        position = 0
        for card in row.get("cards", []):
            position += 1
            db.session.add(TopicCard(
                topic_id=topic.id,
                department_id=card.get("department_id"),
                service_id=card.get("service_id"),
                title=card["title"],
                blurb=card.get("blurb"),
                image=card.get("image"),
                image_alt=card.get("image_alt"),
                position=position,
            ))


def _seed_news() -> None:
    if NewsItem.query.count() > 0:
        return
    position = 0
    for row in NEWS:
        position += 1
        db.session.add(NewsItem(
            title=row["title"],
            display_date=row["display_date"],
            source_url=row["source_url"],
            excerpt=row.get("excerpt"),
            position=position,
        ))


def _seed_homepage_extras() -> None:
    if HomePageStat.query.count() == 0:
        position = 0
        for row in HOMEPAGE_STATS:
            position += 1
            db.session.add(HomePageStat(
                value=row["value"], value_suffix=row.get("value_suffix", ""),
                unit=row["unit"],
                description=row["description"], position=position))
    if Official.query.count() == 0:
        position = 0
        for row in OFFICIALS:
            position += 1
            db.session.add(Official(
                role=row["role"], name=row.get("name"), seal=row["seal"],
                seal_alt=row.get("seal_alt"),
                link_label=row["link_label"], link_url=row["link_url"],
                position=position))


def seed_database():
    """Idempotent: gates the whole directory seed on populated tables."""
    if Department.query.count() > 0:
        return
    _seed_topics()
    _seed_departments()
    _seed_services()
    _seed_topic_cards()
    _seed_news()
    _seed_homepage_extras()
    db.session.commit()


if __name__ == "__main__":
    # Build-time entry point (Dockerfile). Importing app materializes
    # instance/california_gov.db deterministically from the tracked
    # _seed_*.py literals; publish it as the instance_seed copy that the
    # container start script resets from on every boot.
    import shutil
    from pathlib import Path

    base = Path(__file__).resolve().parent
    seed_dir = base / "instance_seed"
    seed_dir.mkdir(exist_ok=True)
    shutil.copyfile(base / "instance" / "california_gov.db",
                    seed_dir / "california_gov.db")
    print(f"Seed database written to {seed_dir / 'california_gov.db'}")
