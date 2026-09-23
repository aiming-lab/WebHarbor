"""Deterministic Chess.com mirror seed builder.

Reads the tracked, upstream-sourced `source_data.json` and materialises the
runtime seed database (instance/chess_com.db -> instance_seed/chess_com.db).
Run at image build time (PYTHONHASHSEED=0) so the seed is byte-reproducible
from tracked inputs and every row is reviewable in the repository diff.

    PYTHONHASHSEED=0 python3 seed_data.py

The benchmark users use a fixed bcrypt digest so re-running the build is
byte-identical (a fresh random salt would change the DB bytes every build).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (Bot, ChessEvent, Club, ClubMembership, Follow, LeaderboardEntry,
                 LeaderboardStats, LessonCourse, LessonProgress, MasterGame, MasterPlayer,
                 NewsArticle, Opening, OpeningTopPlayer, PlayerRating, Puzzle, PuzzleAttempt,
                 TodayItem, TvSlot, User, app, db)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data.json"
INSTANCE = BASE_DIR / "instance"
INSTANCE_SEED = BASE_DIR / "instance_seed"
DB_FILE = INSTANCE / "chess_com.db"

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_DIGEST = "$2b$12$kBUukusSVCcDD62RFBy6guhS0wqXeJLhVSuDNsS3SLhFos851kLHe"
BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "name": "Alice Johnson",
     "country_code": "US", "country_name": "United States", "location": "Seattle, WA"},
    {"username": "bob_c", "email": "bob.c@test.com", "name": "Bob Chen",
     "country_code": "US", "country_name": "United States", "location": "San Jose, CA"},
    {"username": "carol_d", "email": "carol.d@test.com", "name": "Carol Davis",
     "country_code": "GB", "country_name": "United Kingdom", "location": "London"},
    {"username": "david_k", "email": "david.k@test.com", "name": "David Kim",
     "country_code": "US", "country_name": "United States", "location": "Chicago, IL"},
]


def img_name(url):
    """Local filename for an upstream image URL (downloaded into static/images)."""
    if not url:
        return None
    import re
    tail = url.rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9._-]", "_", tail).replace("@2x", "")


def seed_from_source(db):
    src = json.loads(SOURCE.read_text(encoding="utf-8"))

    # ---- members (upstream profiles + leaderboard faces)
    for m in src.get("members", []):
        if not m.get("is_real_member") and not m.get("avatar_small"):
            continue
        user = User(
            username=m["username"],
            name=m.get("name"),
            title=m.get("chess_title"),
            country_code=m.get("country_code"),
            country_name=m.get("country_name"),
            country_id=m.get("country_id"),
            location=m.get("location"),
            avatar=img_name(m.get("avatar")),
            avatar_small=img_name(m.get("avatar_small") or m.get("avatar")),
            flair_svg=img_name(m.get("flair_svg")) if m.get("flair_svg") else None,
            flair_label=m.get("flair_label"),
            followers=m.get("followers") or 0,
            joined=m.get("joined"),
            last_online=m.get("last_online"),
            status=m.get("status"),
            is_streamer=bool(m.get("is_streamer")),
            twitch_url=m.get("twitch_url"),
            league=m.get("league"),
            verified=bool(m.get("verified")),
            views=0,
            is_real_member=True,
        )
        db.session.add(user)
    db.session.flush()

    # ---- ratings per member
    for m in src.get("members", []):
        user = User.query.filter_by(username=m["username"]).first()
        if not user:
            continue
        for cat, r in (m.get("ratings") or {}).items():
            if r.get("rating") is None:
                continue
            db.session.add(PlayerRating(
                user_id=user.id, category=cat,
                rating=r.get("rating"), best_rating=r.get("best_rating"),
                rank=r.get("rank"), wins=r.get("wins") or 0,
                losses=r.get("losses") or 0, draws=r.get("draws") or 0))

    # ---- leaderboard entries
    for e in src.get("leaderboard_entries", []):
        db.session.add(LeaderboardEntry(
            category=e["category"], rank=e["rank"], score=e["score"],
            username=e["username"], chess_title=e.get("chess_title"),
            country_name=e.get("country_name"), country_id=e.get("country_id"),
            avatar_url=img_name(e.get("avatar_url")),
            membership_level=e.get("membership_level"),
            flair_svg=img_name(e.get("flair_svg")) if e.get("flair_svg") else None,
            flair_label=e.get("flair_label"),
            total_games=e.get("total_games"), wins=e.get("wins"),
            draws=e.get("draws"), losses=e.get("losses"),
            trend_direction=e.get("trend_direction"), trend_delta=e.get("trend_delta"),
            snapshot_time=e.get("snapshot_time")))

    # ---- leaderboard stats
    for s in src.get("leaderboard_stats", []):
        db.session.add(LeaderboardStats(
            category=s["category"], avg_rating=s.get("avg_rating"),
            player_count=s.get("player_count"), distribution=s.get("distribution")))

    # ---- news
    for i, a in enumerate(src.get("news", [])):
        db.session.add(NewsArticle(
            slug=a["slug"], title=a["title"], author=a.get("author"),
            author_title=a.get("author_title"), published=a.get("published"),
            hero_image=img_name(a.get("hero_image")),
            excerpt=a.get("excerpt"), body=a.get("body") or [],
            inline_images=[img_name(u) for u in (a.get("inline_images") or [])],
            categories=a.get("categories") or [], featured=i == 0,
            page=i // 12 + 1))

    # ---- openings (+ variations + top players)
    seen_opening_slugs = set()
    for order, o in enumerate(src.get("openings", [])):
        if o["slug"] in seen_opening_slugs:
            continue
        seen_opening_slugs.add(o["slug"])
        row = Opening(
            slug=o["slug"], name=o["name"], eco=o.get("eco"), moves=o.get("moves"),
            description=o.get("description"), sections=o.get("sections") or [],
            popularity=o.get("popularity"), games_count=o.get("games_count"),
            is_variation=bool(o.get("parent")), parent_slug=o.get("parent"), sort_order=order)
        db.session.add(row)
        db.session.flush()
        for tp in o.get("top_players") or []:
            db.session.add(OpeningTopPlayer(
                opening_id=row.id, name=tp.get("name"), chess_title=tp.get("chess_title"),
                country_name=tp.get("country_name"), games_count=tp.get("games_count"),
                avatar_url=img_name(tp.get("avatar_url")),
                member_url=tp.get("member_url")))

    # ---- lessons
    for course in src.get("lessons", []):
        db.session.add(LessonCourse(
            slug=course["slug"], title=course["title"],
            description=course.get("description"), author=course.get("author"),
            level=course.get("level") or 0, n_lessons=course.get("n_lessons") or 1,
            mastery=bool(course.get("mastery")),
            image=img_name(course.get("image")),
            categories=course.get("categories") or [],
            featured=bool(course.get("featured"))))

    # ---- puzzles (daily-puzzle archive)
    for p in src.get("puzzles", []):
        db.session.add(Puzzle(
            legacy_id=p["legacy_id"], title=p.get("title"), fen=p["fen"],
            uci_moves=p.get("uci_moves") or [], san_moves=p.get("san_moves") or [],
            themes=p.get("themes") or [], goals=p.get("goals"),
            rating=p.get("rating"), pgn=p.get("pgn"),
            comment_count=p.get("comment_count"), solved_count=p.get("solved_count"),
            author_username=p.get("author_username"), author_title=p.get("author_title"),
            author_name=p.get("author_name"),
            is_daily=bool(p.get("is_daily")), daily_date=p.get("daily_date")))

    # ---- master players + games
    for p in src.get("master_players", []):
        db.session.add(MasterPlayer(
            slug=p["slug"], name=p["name"], image=img_name(p.get("image")),
            photo_credit=p.get("photo_credit"), born=p.get("born"),
            birthplace=p.get("birthplace"), federation=p.get("federation"),
            total_games=p.get("total_games"), as_white=p.get("as_white"),
            as_black=p.get("as_black")))
    for g in src.get("master_games", []):
        db.session.add(MasterGame(
            game_id=str(g["game_id"]), player_slug=g.get("player_slug"),
            white=g.get("white"), white_rating=g.get("white_rating"),
            black=g.get("black"), black_rating=g.get("black_rating"),
            result=g.get("result"), opening_name=g.get("opening_name"),
            opening_slug=g.get("opening_slug"), first_moves=g.get("first_moves"),
            move_count=g.get("move_count"), year=g.get("year"),
            date=g.get("date"), event=g.get("event"),
            san_moves=g.get("san_moves") or [], final_fen=g.get("final_fen"),
            has_detail=bool(g.get("has_detail")), colors_known=bool(g.get("colors_known"))))

    # ---- clubs
    for c in src.get("clubs", []):
        db.session.add(Club(
            slug=c["slug"], name=c["name"], icon=img_name(c.get("icon")),
            description=c.get("description"), members_count=c.get("members_count"),
            created=c.get("created"), last_activity=c.get("last_activity"),
            country_code=c.get("country_code")))

    # ---- events
    for e in src.get("events", []):
        db.session.add(ChessEvent(
            event_id=e.get("event_id"), name=e["name"], slug=e["slug"],
            image=img_name(e.get("image")), start_at=e.get("start_at"),
            end_at=e.get("end_at"), player_count=e.get("player_count"),
            round_count=e.get("round_count"), description=None,
            location=None, streams=e.get("streams") or [], extra=e.get("extra")))

    # ---- ChessTV + today
    for s in src.get("tv_slots", []):
        db.session.add(TvSlot(start=s.get("start"), end=s.get("end"),
                              title=s.get("title"), url=s.get("url"), color=s.get("color")))
    for it in src.get("today_items", []):
        db.session.add(TodayItem(
            kind=it["kind"], title=it.get("title"), url=it.get("url"),
            image=img_name(it.get("image")), author=it.get("author"),
            published=it.get("published"), meta=None))

    # ---- bots
    seen_bot_slugs = set()
    for b in src.get("bots", []):
        slug = ((b.get("username") or b.get("name") or "bot").lower()
                .replace(" ", "-").replace("_", "-"))
        while slug in seen_bot_slugs:
            slug += "-2"
        seen_bot_slugs.add(slug)
        db.session.add(Bot(
            name=b.get("name"), slug=slug,
            rating=int(re_int(b.get("rating")) or 1000),
            image=img_name(b.get("image")), description=b.get("description"),
            group_name=b.get("group"), sort_order=b.get("sort")))

    db.session.commit()


def re_int(value):
    import re
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    return m.group(0) if m else None


def seed_benchmark_users(db, bcrypt=None):
    """Four benchmark users with pre-existing follows, club memberships and
    lesson progress (fixed bcrypt digest keeps the seed byte-identical)."""
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    users = []
    for spec in BENCHMARK_USERS:
        user = User(
            username=spec["username"], email=spec["email"],
            password_hash=BENCHMARK_DIGEST, name=spec["name"],
            country_code=spec["country_code"], country_name=spec["country_name"],
            location=spec.get("location"), avatar=None, avatar_small=None,
            followers=0, joined="2021-04-10", last_online="2026-09-21",
            status="premium", league="Champion", is_real_member=False)
        db.session.add(user)
        users.append(user)
    db.session.flush()

    # ratings for the benchmark users (deterministic fixture values)
    fixture = {
        "alice_j": {"blitz": (1842, 1901, 512, 320, 148), "bullet": (1720, 1810, 388, 245, 96),
                    "rapid": (1930, 2010, 210, 90, 62), "tactics": (2250, None, None, None, None)},
        "bob_c": {"blitz": (1565, 1612, 700, 500, 210), "bullet": (1440, 1490, 420, 350, 130),
                  "rapid": (1610, 1665, 260, 120, 80), "tactics": (2010, None, None, None, None)},
        "carol_d": {"blitz": (2210, 2290, 810, 300, 240), "bullet": (2050, 2120, 560, 220, 140),
                    "rapid": (2280, 2350, 320, 110, 70), "tactics": (2480, None, None, None, None)},
        "david_k": {"blitz": (1395, 1450, 640, 560, 190), "bullet": (1310, 1360, 380, 330, 120),
                    "rapid": (1470, 1525, 240, 130, 60), "tactics": (1880, None, None, None, None)},
    }
    for user in users:
        for cat, (rating, best, w, l, d) in fixture[user.username].items():
            db.session.add(PlayerRating(user_id=user.id, category=cat, rating=rating,
                                        best_rating=best, wins=w or 0, losses=l or 0,
                                        draws=d or 0))

    # follows: each benchmark user follows a few real members (deterministic)
    follow_plan = {
        "alice_j": ["Hikaru", "MagnusCarlsen", "Firouzja2003"],
        "bob_c": ["MagnusCarlsen", "nihalsarin"],
        "carol_d": ["Hikaru", "FabianoCaruana", "GukeshDommaraju", "Firouzja2003"],
        "david_k": ["MagnusCarlsen", "Hikaru"],
    }
    for user in users:
        for username in follow_plan[user.username]:
            target = User.query.filter_by(username=username).first()
            if target:
                db.session.add(Follow(follower_id=user.id, followed_id=target.id,
                                     created_at="2026-08-14T10:00:00+00:00"))

    # club memberships (deterministic: first two clubs by member count)
    club_slugs = ["chess-com-community", "chess-com-india"]
    for user in users[:3]:
        for slug in club_slugs[:2 if user.username != "carol_d" else 1]:
            club = Club.query.filter_by(slug=slug).first()
            if club:
                db.session.add(ClubMembership(user_id=user.id, club_id=club.id,
                                               joined_at="2026-07-02T09:30:00+00:00"))

    # lesson progress
    progress_plan = {"alice_j": ("how-to-win-with-zugzwang", 4),
                     "bob_c": ("learn-to-play-chess", 12),
                     "carol_d": ("gambit-buffet", 9)}
    for username, (slug, done) in progress_plan.items():
        user = next(u for u in users if u.username == username)
        course = LessonCourse.query.filter_by(slug=slug).first()
        if course:
            db.session.add(LessonProgress(user_id=user.id, course_id=course.id,
                                          lessons_done=done,
                                          completed_at="2026-09-01T12:00:00+00:00"))

    # a few solved puzzles for alice
    puzzles = Puzzle.query.order_by(Puzzle.id).limit(3).all()
    if puzzles:
        alice = next(u for u in users if u.username == "alice_j")
        for i, pz in enumerate(puzzles):
            db.session.add(PuzzleAttempt(user_id=alice.id, puzzle_id=pz.id,
                                         solved=True, used_hint=False,
                                         rating_before=1800 + i,
                                         rating_after=1810 + i * 8,
                                         attempted_at="2026-09-20T18:00:00+00:00"))
    db.session.commit()


def normalize_index_order():
    """Recreate every explicit index in sorted (table, name) order.

    db.create_all() emits each table's auto-indexes by iterating a set of
    Column objects, whose order follows object ids and varies between
    processes. The sqlite_master entry order shapes the file bytes, so a
    build is only byte-reproducible after normalizing it: drop every explicit
    index, then recreate them in a fixed order.
    """
    rows = db.session.execute(
        db.text("SELECT name, tbl_name, sql FROM sqlite_master "
                "WHERE type='index' AND sql IS NOT NULL")).fetchall()
    for name, _tbl, _sql in rows:
        db.session.execute(db.text(f'DROP INDEX "{name}"'))
    for name, tbl, sql in sorted(rows, key=lambda r: (r[1], r[0])):
        db.session.execute(db.text(sql))
    db.session.commit()


def main():
    INSTANCE.mkdir(exist_ok=True)
    with app.app_context():
        db_path = Path(db.engine.url.database)
        if db_path.exists():
            db_path.unlink()
        db.create_all()
        normalize_index_order()
        if NewsArticle.query.count() == 0:
            seed_from_source(db)
        if not User.query.filter_by(email="alice.j@test.com").first():
            seed_benchmark_users(db, None)
    INSTANCE_SEED.mkdir(exist_ok=True)
    shutil.copy2(db_path, INSTANCE_SEED / "chess_com.db")
    print(f"[seed] wrote {db_path} and {INSTANCE_SEED}/chess_com.db "
          f"({(INSTANCE_SEED / 'chess_com.db').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
