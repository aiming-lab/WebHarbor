"""Idempotent seed routines for the IGN mirror."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from content_seed import CONTENT_ITEMS

MIRROR_REFERENCE_DATE = datetime(2026, 7, 2, 12, 0, 0)
PASSWORD = "TestPass123!"

SECTIONS = [
    {
        "slug": "games",
        "name": "Games",
        "description": "Console, PC, and mobile gaming news, previews, and analysis.",
        "color": "#bf1313",
        "sort_order": 1,
    },
    {
        "slug": "reviews",
        "name": "Reviews",
        "description": "IGN verdicts and score cards across games, tech, movies, and TV.",
        "color": "#ff4d4d",
        "sort_order": 2,
    },
    {
        "slug": "guides",
        "name": "Guides",
        "description": "Walkthroughs, wiki updates, map tasks, and checklist-style guides.",
        "color": "#2457ff",
        "sort_order": 3,
    },
    {
        "slug": "videos",
        "name": "Videos",
        "description": "Trailers, Daily Fix episodes, podcasts, and exclusive clips.",
        "color": "#7c3aed",
        "sort_order": 4,
    },
    {
        "slug": "movies",
        "name": "Movies",
        "description": "Film news, interviews, trailers, and theatrical reviews.",
        "color": "#dd6b20",
        "sort_order": 5,
    },
    {
        "slug": "tv",
        "name": "TV",
        "description": "Streaming, anime, episode recaps, and show reviews.",
        "color": "#991e8d",
        "sort_order": 6,
    },
    {
        "slug": "deals",
        "name": "Deals",
        "description": "Daily deal posts, gaming hardware, collectibles, and entertainment offers.",
        "color": "#087f5b",
        "sort_order": 7,
    },
]

AUTHORS = [
    "Luke Reilly",
    "Matt Purslow",
    "Sarah Thwaites",
    "Jesse Schedeen",
    "Tom Phillips",
    "Virginia Glaze",
    "Eric Song",
    "Daemon Hatfield",
    "Michael Higham",
    "Jada Griffin",
    "Nico Vergara",
    "Wesley Yin-Poole",
    "Carlos Morales",
    "Danielle Abraham",
    "Will Borger",
    "Scott White",
]

USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "display_name": "Alice Johnson",
        "region": "Seattle, WA",
        "favorite_platform": "PlayStation 5",
        "bio": "Tracks PlayStation, prestige TV, and guide checklists.",
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "display_name": "Bob Chen",
        "region": "Austin, TX",
        "favorite_platform": "PC",
        "bio": "Keeps a queue of strategy videos and RPG reviews.",
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "display_name": "Carol Davis",
        "region": "Brooklyn, NY",
        "favorite_platform": "Nintendo Switch",
        "bio": "Compares family games, streaming picks, and weekend deals.",
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "display_name": "David Kim",
        "region": "Los Angeles, CA",
        "favorite_platform": "Xbox Series X/S",
        "bio": "Follows trailers, sci-fi TV, and new hardware coverage.",
    },
]


def parse_datetime(value: str, offset: int) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return MIRROR_REFERENCE_DATE - timedelta(hours=offset * 6)


def clean_author(raw: str, title: str, index: int) -> str:
    author = re.sub(r"^by\s+", "", raw or "", flags=re.IGNORECASE).strip()
    bad_bits = ["guide", "tracking", "share", "rating", "start", "open", "contributors"]
    if (
        not author
        or len(author) > 32
        or any(bit in author.lower() for bit in bad_bits)
        or author.lower() in title.lower()
    ):
        return AUTHORS[index % len(AUTHORS)]
    return author


def score_label(score: int | None) -> str:
    if score is None:
        return ""
    if score >= 10:
        return "Masterpiece"
    if score >= 9:
        return "Amazing"
    if score >= 8:
        return "Great"
    if score >= 7:
        return "Good"
    if score >= 6:
        return "Okay"
    return "Mediocre"


def guide_checklist(item: dict) -> list[str]:
    title = item["title"].lower()
    if "gta online" in title:
        return [
            "Claim Independence Day freebies",
            "Review Fine Art Collector bonuses",
            "Check discounted vehicles",
            "Open the related GTA Online map",
        ]
    if "fortnite" in title:
        return [
            "Check weekly quests",
            "Review battle pass rewards",
            "Mark the map update section",
            "Save a rotation note",
        ]
    if "mass effect" in title or "citadel" in title or "illium" in title:
        return [
            "Read mission prerequisites",
            "Track squad conversation choices",
            "Mark collectible objective complete",
            "Check follow-up assignment",
        ]
    return [
        "Read overview",
        "Check latest updates",
        "Mark first objective complete",
        "Review related links",
    ]


def body_for(item: dict, section_name: str) -> list[str]:
    title = item["title"]
    description = item["description"].strip()
    tags = ", ".join(item.get("tags", [])[2:5]) or section_name.lower()
    content_type = item["content_type"]
    if content_type == "review":
        detail = (
            "The review page separates the verdict from the score card, platforms, "
            "reader discussion, and related coverage so agents must inspect the detail page."
        )
    elif content_type == "video":
        detail = (
            "The video page presents a duration, related clips, source game or show context, "
            "and a playlist action for account workflows."
        )
    elif content_type == "guide":
        detail = (
            "The guide page includes checklist progress and wiki-style update notes that can "
            "be changed only after signing in."
        )
    else:
        detail = (
            "The article page expands the summary with context, related coverage, and account "
            "actions for saving, commenting, and playlist planning."
        )
    return [
        description,
        f"This local IGN mirror files the story under {section_name} and tags it with {tags}.",
        detail,
        (
            "Cross-links and near-miss recommendations are intentionally included so browsing "
            "and search tasks require comparison instead of clicking the first result."
        ),
    ]


def seed_database(db, Section, ContentItem) -> None:
    if ContentItem.query.count() > 0:
        return

    for section in SECTIONS:
        db.session.add(Section(**section))
    db.session.flush()

    section_names = {section["slug"]: section["name"] for section in SECTIONS}
    for index, item in enumerate(CONTENT_ITEMS, start=1):
        section_slug = item["section_slug"]
        if section_slug not in section_names:
            section_slug = "games"
        body = body_for(item, section_names[section_slug])
        checklist = guide_checklist(item) if item["content_type"] == "guide" else []
        db.session.add(
            ContentItem(
                slug=item["slug"],
                source_path=item["source_path"],
                title=item["title"],
                description=item["description"],
                body_json=json.dumps(body),
                section_slug=section_slug,
                content_type=item["content_type"],
                author=clean_author(item.get("author", ""), item["title"], index),
                published_at=parse_datetime(item.get("published_at", ""), index),
                image_path=item.get("image_path", ""),
                score=item.get("score"),
                score_label=score_label(item.get("score")),
                comments_count=int(item.get("comments_count") or 0),
                duration=item.get("duration") or "",
                platforms_json=json.dumps(item.get("platforms") or []),
                tags_json=json.dumps(item.get("tags") or []),
                checklist_json=json.dumps(checklist),
                is_featured=index <= 4,
                is_top_story=index <= 20,
                is_editors_choice=(item.get("score") or 0) >= 9,
                sort_rank=item.get("home_rank") or index,
            )
        )
    db.session.commit()


def first_item(ContentItem, slug: str):
    return ContentItem.query.filter_by(slug=slug).first()


def find_item(ContentItem, title_part: str):
    return ContentItem.query.filter(ContentItem.title.ilike(f"%{title_part}%")).first()


def seed_benchmark_users(
    db,
    User,
    ContentItem,
    SavedItem,
    PlaylistEntry,
    Comment,
    AlertSubscription,
    Digest,
    GuideProgress,
) -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    all_items = ContentItem.query.order_by(ContentItem.id.asc()).all()
    guides = ContentItem.query.filter_by(content_type="guide").order_by(ContentItem.id.asc()).all()
    videos = ContentItem.query.filter_by(content_type="video").order_by(ContentItem.id.asc()).all()
    reviews = ContentItem.query.filter_by(content_type="review").order_by(ContentItem.id.asc()).all()

    selected = {
        "gta_history": find_item(ContentItem, "Complicated History of GTA"),
        "playstation": find_item(ContentItem, "Physical Media-Free Future"),
        "silo": find_item(ContentItem, "Silo Season 3 Review"),
        "pokemon_deal": find_item(ContentItem, "Amazon Restocks Rare Pokémon"),
        "cape_fear": find_item(ContentItem, "Cape Fear Episode 6"),
        "anne_hathaway": find_item(ContentItem, "Anne Hathaway Quit Knocked Up"),
        "college_football": find_item(ContentItem, "College Football 27 Review"),
        "walmart_rtx": find_item(ContentItem, "GeForce RTX 5070"),
        "nvc": find_item(ContentItem, "Will Nintendo Ever Stop Making Physical Games"),
        "hbo": find_item(ContentItem, "HBO Max"),
        "prime_video": find_item(ContentItem, "Amazon Prime Video"),
        "gta_weekly": first_item(ContentItem, "gta-online-weekly-updates"),
        "gta_cheats": first_item(ContentItem, "all-gta-5-cheat-codes-and-secrets-for-pc-and-console"),
        "fortnite": first_item(ContentItem, "fortnite"),
    }

    users = []
    for index, payload in enumerate(USERS):
        user = User(
            username=payload["username"],
            email=payload["email"],
            display_name=payload["display_name"],
            region=payload["region"],
            favorite_platform=payload["favorite_platform"],
            bio=payload["bio"],
            avatar_color=["#bf1313", "#2457ff", "#087f5b", "#7c3aed"][index],
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        users.append(user)
    db.session.flush()

    def add_saved(user, item, folder, note=""):
        if item:
            db.session.add(SavedItem(user_id=user.id, item_id=item.id, folder=folder, note=note))

    def add_playlist(user, item, position, status="queued", note=""):
        if item:
            db.session.add(
                PlaylistEntry(
                    user_id=user.id,
                    item_id=item.id,
                    position=position,
                    status=status,
                    note=note,
                )
            )

    for index, user in enumerate(users):
        pool = [item for item in selected.values() if item] + all_items[index * 6 : index * 6 + 8]
        unique = []
        for item in pool:
            if item and item.id not in {x.id for x in unique}:
                unique.append(item)

        for saved_index, item in enumerate(unique[:5], start=1):
            add_saved(
                user,
                item,
                ["Read Later", "Weekend", "Reviews", "Deals", "Guides"][saved_index - 1],
                f"Benchmark saved item {saved_index} for {user.username}.",
            )

        queue = (videos + reviews + guides + unique)[index : index + 5]
        for position, item in enumerate(queue[:4], start=1):
            add_playlist(
                user,
                item,
                position,
                status="watched" if position == 1 else "queued",
                note=f"{user.display_name.split()[0]}'s playlist note {position}.",
            )

        for alert in [
            ("games", user.favorite_platform),
            ("reviews", "review"),
            ("guides", "weekly update"),
        ]:
            db.session.add(
                AlertSubscription(
                    user_id=user.id,
                    section_slug=alert[0],
                    keyword=alert[1],
                    frequency="daily" if alert[0] != "guides" else "weekly",
                    active=True,
                )
            )

        digest_items = unique[:3]
        db.session.add(
            Digest(
                user_id=user.id,
                digest_number=f"IGN-{index + 1:04d}",
                title=f"{user.display_name.split()[0]}'s IGN Digest",
                delivery="email",
                status="delivered",
                item_slugs_json=json.dumps([item.slug for item in digest_items]),
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=index + 1),
            )
        )

        if unique:
            db.session.add(
                Comment(
                    user_id=user.id,
                    item_id=unique[0].id,
                    body="Saving this for a comparison task later.",
                    sentiment="positive",
                )
            )
        if len(unique) > 1:
            db.session.add(
                Comment(
                    user_id=user.id,
                    item_id=unique[1].id,
                    body="Useful context, but I need to inspect the related stories too.",
                    sentiment="neutral",
                )
            )

        for guide in guides[index : index + 2]:
            for checkpoint in guide.checklist[:2]:
                db.session.add(
                    GuideProgress(
                        user_id=user.id,
                        item_id=guide.id,
                        checkpoint=checkpoint,
                        completed=(checkpoint == "Read overview" and index % 2 == 0),
                    )
                )

    db.session.commit()
