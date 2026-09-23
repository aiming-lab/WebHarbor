"""Deterministic seed builder for the Y Combinator mirror.

Reads the tracked, upstream-sourced `source_data.json` plus `asset_inventory.json`
and materialises `instance_seed/y_combinator.db`. Run at image build time
(see the Dockerfile) so the seed is reproducible from tracked inputs and every
row is reviewable in the repository diff rather than shipped as an opaque blob.

    PYTHONHASHSEED=0 python3 seed_data.py
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import bcrypt as _bcrypt

from app import (BlogPost, Bookmark, Company, CompanyNews, FAQ, Founder, HomeBlock,
                 Launch, LaunchVote, LegalDocument, LibraryArticle, LibraryCarousel,
                 Staff, StaticPage, User, app, carousel_articles, db)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
INVENTORY = BASE_DIR / "asset_inventory.json"
INSTANCE_SEED = BASE_DIR / "instance_seed"
DB_FILE = BASE_DIR / "instance" / "y_combinator.db"

# The seed must be byte-reproducible from tracked inputs, so the bcrypt digest is
# fixed here rather than salted per build. A benchmark image ships deterministic
# demo credentials anyway (CONTRIBUTING.md, "Don't hard-code secrets").
BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_DIGEST = "$2b$12$kBUukusSVCcDD62RFBy6guhS0wqXeJLhVSuDNsS3SLhFos851kLHe"
BENCHMARK_USERS = [
    ("alice.j@test.com", "Alice Johnson"),
    ("bob.m@test.com", "Bob Martinez"),
    ("charlie.s@test.com", "Charlie Stone"),
    ("dana.w@test.com", "Dana Wu"),
]


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def available_images() -> set[str]:
    """Only reference media that the tracked inventory actually covers, so a
    field is either a real local file or empty — never a broken <img>."""
    if not INVENTORY.exists():
        return set()
    rows = json.loads(INVENTORY.read_text(encoding="utf-8")).get("assets", [])
    return {Path(row["path"]).name for row in rows}


def as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def seed(data: dict) -> None:
    images = available_images()

    def image(name):
        return name if name in images else None

    def dumps(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=False)

    companies: dict[str, Company] = {}
    for row in data["companies"]:
        company = Company(
            slug=row["slug"], name=row["name"], batch=row.get("batch"),
            batch_code=row.get("batch_code"), industry=row.get("industry"),
            subindustry=row.get("subindustry"), stage=row.get("stage"),
            status=row.get("status"), regions=dumps(row.get("regions") or []),
            tags=dumps(row.get("tags") or []), one_liner=row.get("one_liner"),
            long_description=row.get("long_description"), website=row.get("website"),
            year_founded=as_int(row.get("year_founded")),
            team_size=as_int(row.get("team_size")), location=row.get("location"),
            city=row.get("city"), country=row.get("country"),
            top_company=bool(row.get("top_company")),
            is_hiring=bool(row.get("is_hiring")),
            group_partner=row.get("group_partner"),
            linkedin_url=row.get("linkedin_url"), twitter_url=row.get("twitter_url"),
            github_url=row.get("github_url"), crunchbase_url=row.get("crunchbase_url"),
            logo=image(row.get("logo")),
        )
        db.session.add(company)
        companies[row["slug"]] = company
    db.session.flush()

    for row in data["companies"]:
        for position, item in enumerate(row.get("news") or []):
            db.session.add(CompanyNews(
                company_id=companies[row["slug"]].id, title=item["title"],
                url=item.get("url"), date=item.get("date"), position=position))

    for row in data["founders"]:
        company = companies.get(row.get("company_slug"))
        db.session.add(Founder(
            slug=row["slug"], name=row["name"], title=row.get("title"),
            bio=row.get("bio"), avatar=image(row.get("avatar")),
            company_id=company.id if company else None))

    for position, row in enumerate(data["staff"]):
        db.session.add(Staff(
            slug=row["slug"], name=row["name"], title=row.get("title"),
            bio=row.get("bio"), photo=image(row.get("photo")),
            group=row.get("group"), group_order=row.get("group_order") or 0,
            position=position))

    for row in data["blog_posts"]:
        db.session.add(BlogPost(
            slug=row["slug"], title=row["title"], published_at=row.get("published_at"),
            excerpt=row.get("excerpt"), body=row.get("html"),
            reading_time=as_int(row.get("reading_time")), author=row.get("author"),
            tag=row.get("tag"), feature_image=image(row.get("feature_image"))))

    articles: dict[str, LibraryArticle] = {}
    for row in data["library_articles"]:
        article = LibraryArticle(
            slug=row["slug"], title=row["title"], summary=row.get("content"),
            description=row.get("description"), author=row.get("author"),
            series=row.get("series"), created_at=row.get("created_at"),
            youtube_id=row.get("youtube_id"), view_count=as_int(row.get("view_count")),
            duration_seconds=as_int(row.get("duration_seconds")), link=row.get("link"),
            thumbnail=image(row.get("thumbnail")))
        db.session.add(article)
        articles[row["slug"]] = article
    db.session.flush()

    for row in data["library_carousels"]:
        carousel = LibraryCarousel(name=row["name"], description=row.get("description"),
                                   sort_order=row.get("sort_order") or 0)
        db.session.add(carousel)
        db.session.flush()
        for position, slug in enumerate(row.get("article_slugs") or []):
            article = articles.get(slug)
            if article:
                db.session.execute(carousel_articles.insert().values(
                    carousel_id=carousel.id, article_id=article.id, position=position))

    for row in data["launches"]:
        db.session.add(Launch(
            slug=row["slug"], title=row["title"], tagline=row.get("tagline"),
            created_at=row.get("created_at"), vote_count=as_int(row.get("vote_count")) or 0,
            company_name=row.get("company_name"), company_slug=row.get("company_slug"),
            company_batch=row.get("company_batch"),
            company_industry=row.get("company_industry"),
            company_url=row.get("company_url"),
            company_tags=dumps(row.get("company_tags") or []),
            logo=image(row.get("logo"))))

    for position, row in enumerate(data["faqs"]):
        db.session.add(FAQ(category=row.get("category"), question=row["question"],
                           answer=row["answer"], position=position))

    for position, row in enumerate(data["documents"]):
        db.session.add(LegalDocument(group=row.get("group"), title=row["title"],
                                     url=row.get("url"), filename=row.get("filename"),
                                     position=position))

    for row in data["static_pages"]:
        db.session.add(StaticPage(slug=row["slug"], title=row["title"],
                                  body=row.get("html")))

    home = data["home"]

    def block(kind, position, payload):
        db.session.add(HomeBlock(kind=kind, position=position, payload=dumps(payload)))

    block("hero", 0, {
        "line_one": home.get("hero_line_one"),
        "line_two_lead": home.get("hero_line_two_lead"),
        "headline_emphasis": home.get("hero_headline_emphasis"),
        "footnote": home.get("hero_footnote"),
        "footnote_attribution": home.get("hero_footnote_attribution"),
        "valuation_amount": home.get("valuation_amount"),
        "valuation_caption": home.get("valuation_caption"),
    })
    for i, paragraph in enumerate(home.get("narrative") or []):
        block("narrative", i, {"text": paragraph})
    for i, item in enumerate(home.get("in_the_room") or []):
        block("in_the_room", i, {**item, "poster": image(item.get("poster")),
                                 "video": image(item.get("video"))})
    for i, item in enumerate(home.get("before_now") or []):
        # Several band names (OpenAI, for one) are not in the public directory
        # upstream either, so only link the ones this mirror actually serves.
        listed = companies.get(item.get("key"))
        if not listed:
            listed = Company.query.filter(
                db.func.lower(Company.name) == (item.get("name") or "").lower()).first()
        block("before_now", i, {**item,
                                "company_slug": listed.slug if listed else None,
                                "images": [image(x) for x in (item.get("images") or [])]})
    for i, item in enumerate(home.get("logos") or []):
        block("logo", i, {**item, "logo": image(item.get("logo"))})
    for i, item in enumerate(home.get("about_quotes") or []):
        block("about_quote", i, {**item, "avatar": image(item.get("avatar"))})
    featured = home.get("featured_quote") or {}
    if featured.get("text"):
        block("featured_quote", 0, {**featured, "avatar": image(featured.get("avatar"))})
    for i, name in enumerate(home.get("about_strip") or []):
        if image(name):
            block("about_strip", i, {"image": name})
    for i, name in enumerate(home.get("cta_strip") or []):
        if image(name):
            block("cta_strip", i, {"image": name})
    for i, section in enumerate(home.get("partner_sections") or []):
        block("partner_section", i, {
            "title": section.get("title"),
            "partners": [{**p, "photo": image(p.get("photo")),
                          "batch_photo": image(p.get("batch_photo"))}
                         for p in section.get("partners") or []]})
    feature = home.get("knowledge_feature") or {}
    if feature.get("title"):
        block("knowledge_feature", 0, {**feature, "image": image(feature.get("image"))})
    for i, item in enumerate(home.get("knowledge_thumbnails") or []):
        block("knowledge_thumbnail", i, {**item, "image": image(item.get("image"))})
    for i, item in enumerate(home.get("startup_news") or []):
        block("startup_news", i, item)
    for i, item in enumerate(home.get("pg_essays") or []):
        block("pg_essay", i, item)

    if not _bcrypt.checkpw(BENCHMARK_PASSWORD.encode("utf-8"), BENCHMARK_DIGEST.encode("ascii")):
        raise SystemExit("benchmark digest does not match the documented password")
    for email, name in BENCHMARK_USERS:
        db.session.add(User(email=email, name=name, password=BENCHMARK_DIGEST,
                            newsletter=False))

    db.session.commit()


def build_seed_database() -> None:
    INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DB_FILE.exists():
        DB_FILE.unlink()
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed(load_source())
        counts = {
            "companies": Company.query.count(),
            "founders": Founder.query.count(),
            "staff": Staff.query.count(),
            "blog posts": BlogPost.query.count(),
            "library articles": LibraryArticle.query.count(),
            "launches": Launch.query.count(),
            "faqs": FAQ.query.count(),
            "documents": LegalDocument.query.count(),
            "static pages": StaticPage.query.count(),
            "home blocks": HomeBlock.query.count(),
            "users": User.query.count(),
        }
    shutil.copyfile(DB_FILE, INSTANCE_SEED / "y_combinator.db")
    for label, value in counts.items():
        print(f"  {label:<18} {value}")
    print(f"Seed database written to {INSTANCE_SEED / 'y_combinator.db'}")


if __name__ == "__main__":
    build_seed_database()
