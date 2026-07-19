"""Idempotent seed for the WebMD mirror.

Runs at every container boot and every /reset/webmd. Each seed function
early-returns on a populated DB so re-seeding is a no-op and the
byte-identical reset invariant holds (even a bare commit on a populated DB
bumps SQLite metadata).

Content sourcing: structured medical facts come from openFDA drug labeling
and MedlinePlus/NIH public-domain health topics (snapshots in scraped_data/);
all prose is original; authors are fictional personas.
"""
from datetime import date, datetime

from _seed_drugs_a import DRUGS_A
from _seed_drugs_b import DRUGS_B
from _seed_conditions_a import CONDITIONS_A, SYMPTOMS
from _seed_conditions_b import CONDITIONS_B
from _seed_authors import AUTHORS
from _seed_articles_a import ARTICLES_A
from _seed_articles_b import ARTICLES_B
from _seed_articles_c import ARTICLES_C

DRUGS = DRUGS_A + DRUGS_B
CONDITIONS = CONDITIONS_A + CONDITIONS_B
ARTICLES = ARTICLES_A + ARTICLES_B + ARTICLES_C

SECTIONS = [
    {"name": "Health A-Z", "slug": "conditions",
     "blurb": "Conditions, symptoms, and treatments explained."},
    {"name": "Drugs & Supplements", "slug": "drugs-supplements",
     "blurb": "How medicines work, safety, and smart use."},
    {"name": "Well-Being", "slug": "well-being",
     "blurb": "Sleep, fitness, stress, and healthy aging."},
    {"name": "Diet & Weight Management", "slug": "diet-weight",
     "blurb": "Nutrition science and sustainable weight strategies."},
    {"name": "Family & Pregnancy", "slug": "family-pregnancy",
     "blurb": "Pregnancy, parenting, and health across generations."},
    {"name": "Health News", "slug": "news",
     "blurb": "What's happening in health right now."},
]


def _d(iso):
    return date.fromisoformat(iso)


def seed_database(db, Section, Article, Drug, Condition, Symptom, Author,
                  condition_symptoms):
    if Section.query.count() > 0:
        return

    sections = {}
    for s in SECTIONS:
        row = Section(name=s["name"], slug=s["slug"], blurb=s["blurb"])
        db.session.add(row)
        sections[s["slug"]] = row

    authors = {}
    for a in AUTHORS:
        row = Author(
            name=a["name"], slug=a["slug"], role=a["role"],
            credentials=a["credentials"], bio=a["bio"],
            image=f"author_{a['slug']}.png",
        )
        db.session.add(row)
        authors[a["slug"]] = row

    db.session.flush()

    for art in ARTICLES:
        db.session.add(Article(
            title=art["title"], slug=art["slug"],
            section_id=sections[art["section"]].id,
            subcategory=art["subcategory"],
            summary=art["summary"], body_html=art["body_html"],
            author_id=authors[art["author"]].id,
            reviewer_id=authors[art["reviewer"]].id,
            published_date=_d(art["published"]),
            reviewed_date=_d(art["reviewed"]),
            image=f"article_{art['slug']}.png",
        ))

    for d in DRUGS:
        db.session.add(Drug(
            name=d["name"], slug=d["slug"],
            generic_name=d["generic_name"], brand_names=d["brand_names"],
            drug_class=d["drug_class"], category=d["category"],
            uses=d["uses"], dosage=d["dosage"],
            side_effects_common=d["side_effects_common"],
            side_effects_serious=d["side_effects_serious"],
            interactions=d["interactions"], warnings=d["warnings"],
            image=f"drug_{d['slug']}.png",
        ))

    symptoms = {}
    for name, slug in SYMPTOMS:
        row = Symptom(name=name, slug=slug)
        db.session.add(row)
        symptoms[slug] = row

    db.session.flush()

    for c in CONDITIONS:
        row = Condition(
            name=c["name"], slug=c["slug"], letter=c["letter"],
            overview=c["overview"], symptoms=c["symptoms"],
            causes=c["causes"], treatments=c["treatments"],
            related_drug_slugs=",".join(c["related_drug_slugs"]),
            image=f"condition_{c['slug']}.png",
        )
        db.session.add(row)
        db.session.flush()
        for ss in c["symptom_slugs"]:
            db.session.execute(condition_symptoms.insert().values(
                condition_id=row.id, symptom_id=symptoms[ss].id))

    db.session.commit()
    print(f"Seeded {len(SECTIONS)} sections, {len(ARTICLES)} articles, "
          f"{len(DRUGS)} drugs, {len(CONDITIONS)} conditions, "
          f"{len(SYMPTOMS)} symptoms, {len(AUTHORS)} authors.")


# The primary benchmark account. Login-flow tasks reference this one; the
# others exist so account pages aren't trivially single-row.
BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "name": "Alice Johnson",
     "password": "TestPass123!"},
    {"email": "bob.m@test.com", "name": "Bob Martinez",
     "password": "TestPass123!"},
    {"email": "carol.w@test.com", "name": "Carol Williams",
     "password": "TestPass123!"},
    {"email": "david.k@test.com", "name": "David Kim",
     "password": "TestPass123!"},
]

# Pre-existing saved articles per user (article slugs). Fixed distribution so
# saved-list tasks have ambiguity and non-trivial state.
SAVED_ARTICLES = {
    "alice.j@test.com": [
        "high-blood-pressure-home-monitoring", "migraine-getting-real-treatment",
        "mediterranean-diet-week-one", "sleep-debt-week-short-nights",
        "ssri-first-six-weeks", "fiber-least-glamorous-nutrient",
    ],
    "bob.m@test.com": [
        "nsaids-compared", "knee-osteoarthritis-exercise",
        "strength-after-60", "weekend-warrior-study", "gout-attacks-prevention",
    ],
    "carol.w@test.com": [
        "first-trimester-checklist", "fevers-in-kids",
        "melatonin-evidence", "emotional-eating-circuit",
    ],
    "david.k@test.com": [
        "warfarin-vs-newer-anticoagulants", "atrial-fibrillation-basics",
        "prostate-psa-decision",
    ],
}

# Pre-existing reading history rows: (email, article slug, days before the
# benchmark date). Deterministic timestamps.
READING_HISTORY = [
    ("alice.j@test.com", "flu-season-hits-stride", 1),
    ("alice.j@test.com", "high-blood-pressure-home-monitoring", 2),
    ("alice.j@test.com", "type-2-diabetes-first-year", 4),
    ("alice.j@test.com", "hydration-how-much-water", 6),
    ("alice.j@test.com", "sodium-you-never-salted", 9),
    ("bob.m@test.com", "new-year-exercise-safely", 2),
    ("bob.m@test.com", "statins-muscle-aches", 3),
    ("bob.m@test.com", "walking-8000-steps", 7),
    ("bob.m@test.com", "protein-how-much", 11),
    ("carol.w@test.com", "norovirus-outbreaks-rise", 1),
    ("carol.w@test.com", "ear-infections-watchful-waiting", 5),
    ("carol.w@test.com", "kids-anxiety-talking", 8),
    ("david.k@test.com", "holiday-heart-syndrome", 3),
    ("david.k@test.com", "dry-january-physiology", 6),
    ("david.k@test.com", "blood-pressure-control-slipping", 10),
    ("david.k@test.com", "aging-parents-five-conversations", 14),
]


def seed_benchmark_users(db, User, bcrypt, Article, SavedArticle,
                         ReadingHistory, benchmark_today):
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = {}
    for u in BENCHMARK_USERS:
        user = User(email=u["email"], name=u["name"])
        user.password_hash = bcrypt.generate_password_hash(
            u["password"]).decode("utf-8")
        db.session.add(user)
        users[u["email"]] = user
    db.session.flush()

    anchor = datetime(benchmark_today.year, benchmark_today.month,
                      benchmark_today.day, 9, 0, 0)

    n_saved = 0
    for email, slugs in SAVED_ARTICLES.items():
        for i, slug in enumerate(slugs):
            art = Article.query.filter_by(slug=slug).first()
            if art:
                db.session.add(SavedArticle(
                    user_id=users[email].id, article_id=art.id,
                    created_at=anchor.replace(hour=8 + (i % 4)),
                ))
                n_saved += 1

    n_hist = 0
    for email, slug, days_ago in READING_HISTORY:
        art = Article.query.filter_by(slug=slug).first()
        if art:
            ts = datetime(benchmark_today.year, benchmark_today.month,
                          benchmark_today.day, 20, 0, 0)
            ts = datetime.fromordinal(ts.toordinal() - days_ago).replace(
                hour=20, minute=(days_ago * 7) % 60)
            db.session.add(ReadingHistory(
                user_id=users[email].id, article_id=art.id, created_at=ts))
            n_hist += 1

    db.session.commit()
    print(f"Seeded {len(BENCHMARK_USERS)} users, {n_saved} saved articles, "
          f"{n_hist} history rows.")
