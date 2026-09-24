"""Deterministic seed builder for the League of Legends mirror.

Reads the tracked, upstream-sourced source_data.json (champions, abilities,
skins, news categories, articles, external news cards) and materialises the
runtime DB. Called at image build time (see the Dockerfile) and defensively at
boot; every seed function early-returns when its data already exists so
/reset/<league_of_legends> stays byte-identical.

    LOL_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, favorite champions, saved articles) are synthetic
and reference real seeded champions/articles; every date written into the
seed is the pinned snapshot date so the seed is byte-stable across builds.

Content provenance: champions/abilities/skins data and imagery come from the
live leagueoflegends.com champion pages (harvested 2026-09-22; splash and
ability art via Riot's ddragon CDN, portraits via cmsassets.rgpub.io). News
articles come from the live news hub and category pages. See provenance.json.
"""
from __future__ import annotations

import os

os.environ.setdefault("LOL_SKIP_BOOTSTRAP", "1")

import json  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

from app import (  # noqa: E402
    Ability,
    Article,
    ArticleCategory,
    BookmarkArticle,
    Champion,
    FavoriteChampion,
    Skin,
    User,
    app,
    db,
    dump_json,
    stable_password_hash,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_SEED = BASE_DIR / "instance_seed"

MIRROR_DATE_STR = "2026-09-22"
BENCHMARK_PASSWORD = "TestPass123!"
RNG_SEED = 42

BENCHMARK_USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "display_name": "Alice Johnson",
        "summoner_name": "StarlitFox",
        "region": "NA",
        "joined_date": "2026-01-12",
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "display_name": "Bob Chen",
        "summoner_name": "MidlaneMancer",
        "region": "EUW",
        "joined_date": "2026-02-03",
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "display_name": "Carol Davis",
        "summoner_name": "SupportMain99",
        "region": "NA",
        "joined_date": "2026-03-21",
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "display_name": "David Kim",
        "summoner_name": "TopLanerKor",
        "region": "KR",
        "joined_date": "2026-04-17",
    },
]


def load_source() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def seed_database() -> None:
    """Idempotent: skip entirely when the roster already exists."""
    if Champion.query.count() > 0:
        return
    source = load_source()

    categories = {}
    for row in source.get("categories", []):
        category = ArticleCategory(
            machine_name=row["machine_name"],
            title=row["title"],
            description=row.get("description") or "",
        )
        db.session.add(category)
        categories[row["machine_name"]] = category
    db.session.flush()

    for row in source.get("champions", []):
        champion = Champion(
            slug=row["slug"],
            name=row["name"],
            epithet=row.get("epithet") or "",
            roles=dump_json(row.get("roles") or []),
            difficulty_name=row.get("difficulty_name") or "Low",
            difficulty_value=row.get("difficulty_value") or 1,
            lore=row.get("lore") or "",
            release_key=row.get("release_key") or 0,
            portrait=row.get("portrait") or "",
            splash=row.get("splash") or "",
        )
        db.session.add(champion)
        db.session.flush()
        for ability_row in row.get("abilities", []):
            db.session.add(Ability(
                champion_id=champion.id,
                slot=ability_row["slot"],
                slot_label=ability_row.get("slot_label") or ability_row["slot"],
                name=ability_row.get("name") or "",
                description=ability_row.get("description") or "",
                icon=ability_row.get("icon") or "",
                poster=ability_row.get("poster") or "",
                sort=ability_row.get("sort") or 0,
            ))
        for skin_row in row.get("skins", []):
            db.session.add(Skin(
                champion_id=champion.id,
                num=skin_row["num"],
                name=skin_row.get("name") or row["name"],
                splash=skin_row.get("splash") or "",
            ))

    for row in source.get("articles", []):
        category = categories.get(row.get("category") or "")
        if category is None:
            continue
        db.session.add(Article(
            slug=row["slug"],
            category_id=category.id,
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            banner=row.get("banner") or "",
            publish_date=row.get("publish_date") or MIRROR_DATE_STR,
            authors=dump_json(row.get("authors") or []),
            tags=dump_json(row.get("tags") or []),
            body_html=row.get("body_html") or "",
            related=dump_json(row.get("related") or []),
            external_url=row.get("external_url") or "",
            is_patch_note=1 if row.get("is_patch_note") else 0,
        ))

    for row in source.get("external_links", []):
        category = categories.get(row.get("category") or "")
        if category is None:
            continue
        db.session.add(Article(
            slug=row["slug"],
            category_id=category.id,
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            banner=f"news/{row['slug']}_card.jpg",
            publish_date=row.get("publish_date") or MIRROR_DATE_STR,
            authors=dump_json([]),
            tags=dump_json([]),
            body_html="",
            related=dump_json([]),
            external_url=row.get("external_url") or "",
            is_patch_note=0,
        ))

    db.session.commit()


def seed_benchmark_users() -> None:
    """Idempotent: skip entirely when the first benchmark user exists."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    rng = random.Random(RNG_SEED)
    champion_ids = [
        row[0] for row in db.session.query(Champion.id).order_by(Champion.name).all()]
    article_ids = [
        row[0] for row in db.session.query(Article.id)
        .filter(Article.external_url == "").order_by(Article.publish_date.desc()).all()]
    for user_row in BENCHMARK_USERS:
        user = User(
            username=user_row["username"],
            email=user_row["email"],
            display_name=user_row["display_name"],
            summoner_name=user_row["summoner_name"],
            region=user_row["region"],
            password_hash=stable_password_hash(BENCHMARK_PASSWORD),
            joined_date=user_row["joined_date"],
        )
        db.session.add(user)
        db.session.flush()
        for champion_id in rng.sample(champion_ids, 5):
            db.session.add(FavoriteChampion(
                user_id=user.id, champion_id=champion_id,
                added_date=MIRROR_DATE_STR))
        for article_id in rng.sample(article_ids, 4):
            db.session.add(BookmarkArticle(
                user_id=user.id, article_id=article_id,
                added_date=MIRROR_DATE_STR))
    db.session.commit()


def build_seed_file() -> Path:
    """Materialise instance_seed/league_of_legends.db from a fresh build."""
    import app as app_module  # noqa: F401  (bootstrap is skipped via env)

    db_path = INSTANCE_DIR / "league_of_legends.db"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
    INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
    seed_path = INSTANCE_SEED / "league_of_legends.db"
    for stale in INSTANCE_SEED.glob("*.db"):
        stale.unlink()
    shutil.copy2(db_path, seed_path)
    return seed_path


if __name__ == "__main__":
    written = build_seed_file()
    print(f"[seed] instance_seed/league_of_legends.db written ({written.stat().st_size} bytes)")
