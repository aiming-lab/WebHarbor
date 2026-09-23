"""Deterministic build-time/boot-time seeder for the imgur mirror.

Reads the tracked source snapshot (source_data.json) and materializes it
into the site's SQLite database. The snapshot arrays are pre-sorted by the
build script, so repeated builds on the same source produce byte-identical
databases (the Dockerfile seeds with PYTHONHASHSEED=0).

Every seed function early-returns on a populated database, which keeps
`/reset/imgur` byte-identical.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(BASE_DIR, "source_data.json")

# Benchmark users share one deterministic digest for TestPass123! so the seed
# database is byte-reproducible on every rebuild.
BENCHMARK_PASSWORD_HASH = (
    "scrypt:32768:8:1$webharbor-imgur-fixed-salt-v1$"
    "091bce136687417e57683a12cc594febaa7cdb9eaaf945af2f2f4a8bd2e392ad"
    "7a96b79c57629aea23d97a51f3fef20ee01ecec28178e6e6809321c459112888"
)

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display": "David Kim"},
]


def _load_source() -> dict:
    with open(SOURCE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime(2026, 9, 22, 22, 0, 0)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def seed_database():
    from app import (Accolade, Comment, Favorite, FollowTag, FollowUser, Media,
                     Post, Tag, Trophy, User, Vote, CommentVote, MemeTemplate, db,
                     reputation_name)

    if Post.query.count() > 0:
        return

    source = _load_source()

    # ---------------------------------------------------------------- tags
    for row in source["tags"]:
        db.session.add(Tag(
            name=row["name"], display_name=row["display_name"],
            followers=row["followers"], total_items=row["total_items"],
            accent=row["accent"], background_path=row["background_path"],
            description=row["description"], is_featured=row["is_featured"],
            position=row["position"]))

    # ---------------------------------------------------------------- users
    for row in source["users"]:
        db.session.add(User(
            id=row["id"], username=row["username"], email=None, password_hash=None,
            avatar=row["avatar"], bio=row["bio"], reputation=row["reputation"],
            reputation_name=row["reputation_name"],
            created_at=_parse_date(row["created_at"]), is_benchmark=False))

    for row in source["benchmark_users"]:
        db.session.add(User(
            id=row["id"], username=row["username"], email=row["email"],
            password_hash=BENCHMARK_PASSWORD_HASH, avatar=row["avatar"],
            bio=row["bio"], reputation=row["reputation"],
            reputation_name=reputation_name(row["reputation"]),
            created_at=_parse_date(row["created_at"]), is_benchmark=True))

    db.session.flush()

    # ---------------------------------------------------------------- posts
    for row in source["posts"]:
        db.session.add(Post(
            id=row["id"], author_id=row["author_id"], title=row["title"],
            seo_title=row["seo_title"], description=row["description"],
            view_count=row["view_count"], upvote_count=row["upvote_count"],
            downvote_count=row["downvote_count"], point_count=row["point_count"],
            image_count=row["image_count"], comment_count=row["comment_count"],
            favorite_count=row["favorite_count"], virality=row["virality"],
            score=row["score"], is_album=row["is_album"],
            in_most_viral=row["in_most_viral"], in_top_week=row["in_top_week"],
            in_user_sub=row["in_user_sub"], platform=row["platform"],
            created_at=_parse_date(row["created_at"])))
    db.session.flush()

    for row in source["posts"]:
        for media in row["media"]:
            db.session.add(Media(
                id=media["id"], post_id=row["id"], position=media["position"],
                mime_type=media["mime_type"], type=media["type"], ext=media["ext"],
                feed_path=media["feed_path"], detail_path=media["detail_path"],
                poster_path=media.get("poster_path", ""),
                width=media["width"], height=media["height"], size=media["size"],
                is_animated=media["is_animated"], has_sound=media["has_sound"],
                duration=media["duration"]))
        for tag_name in row["tags"]:
            db.session.execute(db.insert(db.metadata.tables["post_tags"]).values(
                post_id=row["id"], tag_name=tag_name))
        for accolade in row["accolades"]:
            db.session.add(Accolade(post_id=row["id"], name=accolade["name"],
                                    image_path=accolade["image_path"],
                                    count=accolade.get("count", 1)))
    db.session.flush()

    # ---------------------------------------------------------------- comments
    for row in source["comments"]:
        db.session.add(Comment(
            id=row["id"], post_id=row["post_id"], parent_id=row["parent_id"] or None,
            author_id=row["author_id"], text=row["text"],
            image_path=row.get("image_path", ""),
            upvote_count=row["upvote_count"], downvote_count=row["downvote_count"],
            point_count=row["point_count"], platform=row["platform"],
            created_at=_parse_date(row["created_at"])))
    db.session.flush()

    # ---------------------------------------------------------------- trophies
    for row in source["trophies"]:
        db.session.add(Trophy(
            user_id=row["user_id"], name=row["name"], description=row["description"],
            image_path=row["image_path"], awarded_at=_parse_date(row["awarded_at"])))

    # ---------------------------------------------------------------- meme templates
    for row in source["meme_templates"]:
        db.session.add(MemeTemplate(id=row["id"], name=row["name"],
                                   image_path=row["image_path"]))

    # ---------------------------------------------------------------- benchmark state
    for row in source["benchmark_state"]:
        user = db.session.query(User).filter_by(username=row["username"]).first()
        if not user:
            continue
        for favorite in row["favorites"]:
            db.session.add(Favorite(user_id=user.id, post_id=favorite["post_id"],
                                    created_at=_parse_date(favorite["created_at"])))
        for vote in row["votes"]:
            db.session.add(Vote(user_id=user.id, post_id=vote["post_id"],
                                value=vote["value"]))
        for comment in row["comments"]:
            db.session.add(Comment(
                id=comment["id"], post_id=comment["post_id"], parent_id=None,
                author_id=user.id, text=comment["text"], image_path="",
                upvote_count=comment["upvote_count"], downvote_count=comment["downvote_count"],
                point_count=comment["point_count"], platform="web",
                created_at=_parse_date(comment["created_at"])))
            post = db.session.get(Post, comment["post_id"])
            if post:
                post.comment_count += 1
        for followee in row["follow_users"]:
            target = db.session.query(User).filter_by(username=followee).first()
            if target:
                db.session.add(FollowUser(follower_id=user.id, followee_id=target.id))
        for tag_name in row["follow_tags"]:
            db.session.add(FollowTag(user_id=user.id, tag_name=tag_name))

    db.session.commit()


if __name__ == "__main__":
    from app import app, db
    with app.app_context():
        db.create_all()
        seed_database()
        print("seeded", db.session.query(db.metadata.tables["posts"]).count(), "posts")
    import shutil
    os.makedirs(os.path.join(BASE_DIR, "instance_seed"), exist_ok=True)
    shutil.copyfile(os.path.join(BASE_DIR, "instance", "imgur.db"),
                    os.path.join(BASE_DIR, "instance_seed", "imgur.db"))
    print("copied seed to instance_seed/imgur.db")
