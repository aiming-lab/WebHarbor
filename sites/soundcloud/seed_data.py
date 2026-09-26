"""Deterministic seed builder for the SoundCloud mirror.

Reads the tracked, upstream-sourced source_data/ snapshots (captured from
api-v2.soundcloud.com on 2026-09-25/26) and materialises the runtime DB.
Called at image build time (see the Dockerfile stanza) and defensively at
boot; every seed function early-returns when its data already exists so
/reset/soundcloud stays byte-identical.

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, likes, follows, playlists, history,
subscriptions) are mirror-native and reference real seeded entities; every
date is pinned to MIRROR_DATE so the seed is byte-stable across builds.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (Artist, Comment, Follow, Like, PlayEvent, Playlist,  # noqa: E402
                 PlaylistTrack, Repost, Subscription, Track, User,
                 UserPlaylist, UserPlaylistTrack, app, create_schema, db)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"
INSTANCE_SEED = BASE_DIR / "instance_seed"

MIRROR_DATE = datetime(2026, 9, 26)

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display": "Alice Johnson",
     "city": "Los Angeles, CA", "bio": "Alt-pop fan, bedroom producer, always hunting the New & Hot chart."},
    {"username": "bob_c", "email": "bob.c@test.com", "display": "Bob Chen",
     "city": "Brooklyn, NY", "bio": "Hip hop head. If it's buzzing on the Lookout I've heard it."},
    {"username": "carol_d", "email": "carol.d@test.com", "display": "Carol Davis",
     "city": "Austin, TX", "bio": "House + techno. Warehouse sets only."},
    {"username": "david_k", "email": "david.k@test.com", "display": "David Kim",
     "city": "Seattle, WA", "bio": "Indie rock & shoegaze. Vinyl first, streams second."},
]


def load(name: str):
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def image_variant(url, size):
    if not url:
        return ""
    if "default_avatar" in url:
        return "DEFAULT"
    return re.sub(r"-(?:large|original|t\d+x\d+)\.(jpg|png|gif)$", f"-{size}.\\1", url)


def _stable_hash(*parts) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16)


def seed_database() -> None:
    if Track.query.count() > 0:
        return

    # ---- artists --------------------------------------------------------- #
    artists_src = load("artists.json")
    artist_rows = {}
    for a in artists_src:
        avatar = image_variant(a.get("avatar_url"), "t200x200")
        if avatar == "DEFAULT":
            avatar_rel = "/static/images/avatars/_default.png"
        else:
            ext = ".png" if avatar.endswith(".png") else ".jpg"
            avatar_rel = f"/static/images/avatars/{a['permalink']}{ext}" if avatar else ""
        banner_rel = ""
        if a.get("banner"):
            bext = ".png" if a["banner"].endswith(".png") else ".jpg"
            banner_rel = f"/static/images/banners/{a['permalink']}{bext}"
        row = Artist(
            id=a["id"],
            permalink=a["permalink"],
            username=a["username"],
            avatar=avatar_rel,
            banner=banner_rel,
            followers=a.get("followers") or 0,
            followings=a.get("followings") or 0,
            track_count=a.get("track_count") or 0,
            description=a.get("description") or "",
            city=(a.get("city") or "").strip(),
            country_code=a.get("country_code") or "",
            verified=bool(a.get("verified")),
            pro=bool(a.get("pro")),
            pro_unlimited=bool(a.get("pro_unlimited")),
            created_at=parse_date(a.get("created_at")),
        )
        artist_rows[a["permalink"]] = row
        db.session.add(row)
    db.session.flush()

    # ---- tracks ---------------------------------------------------------- #
    tracks_src = load("tracks.json")
    track_rows = {}
    for t in tracks_src:
        art = image_variant(t.get("artwork_url"), "t500x500")
        art_rel = f"/static/images/tracks/{t['id']}.jpg" if art else ""
        artist = artist_rows.get(t.get("artist_permalink"))
        if not artist:
            continue
        row = Track(
            id=t["id"],
            permalink=t["permalink"],
            title=t["title"],
            artist_id=artist.id,
            duration=t.get("duration") or 0,
            plays=t.get("plays") or 0,
            likes=t.get("likes") or 0,
            reposts=t.get("reposts") or 0,
            comment_count=t.get("comment_count") or 0,
            genre=(t.get("genre") or "").strip(),
            tag_list=t.get("tag_list") or "",
            description=t.get("description") or "",
            artwork=art_rel,
            waveform=json.dumps(t.get("waveform") or []),
            created_at=parse_date(t.get("created_at")),
            display_date=parse_date(t.get("display_date")) or parse_date(t.get("created_at")),
            license=t.get("license") or "all-rights-reserved",
            label_name=t.get("label_name") or "",
            publisher_artist=t.get("publisher_artist") or "",
            explicit=bool(t.get("explicit")),
        )
        track_rows[t["id"]] = row
        db.session.add(row)
    db.session.flush()

    # ---- playlists ------------------------------------------------------- #
    playlists_src = load("playlists.json")
    pl_rows = {}
    for p in playlists_src:
        owner = artist_rows.get(p["owner_permalink"])
        if not owner:
            continue
        art_rel = f"/static/images/playlists/{p['id']}.jpg" if p.get("artwork_url") else ""
        row = Playlist(
            id=p["id"],
            permalink=p["permalink"],
            title=p["title"],
            owner_id=owner.id,
            description=p.get("description") or "",
            genre=(p.get("genre") or "").strip(),
            tag_list=p.get("tag_list") or "",
            likes=p.get("likes") or 0,
            reposts=p.get("reposts") or 0,
            track_count=p.get("track_count") or 0,
            duration=p.get("duration") or 0,
            is_chart=bool(p.get("is_chart")),
            chart_country=p.get("chart_country") or "",
            display_date=parse_date(p.get("display_date")),
            created_at=parse_date(p.get("created_at")),
            artwork=art_rel,
        )
        pl_rows[p["id"]] = row
        db.session.add(row)
    db.session.flush()

    # ---- playlist membership -------------------------------------------- #
    for p in playlists_src:
        row = pl_rows.get(p["id"])
        if not row:
            continue
        for pos, tid in enumerate(p.get("track_ids", []), 1):
            track = track_rows.get(tid)
            if not track:
                continue
            db.session.add(PlaylistTrack(playlist_id=row.id, track_id=track.id, position=pos))
    db.session.flush()

    # ---- comments -------------------------------------------------------- #
    comments_src = load("comments.json")
    for c in comments_src:
        track = track_rows.get(c["track_id"])
        if not track:
            continue
        avatar = image_variant(c.get("user_avatar"), "t50x50")
        if avatar == "DEFAULT":
            avatar_rel = "/static/images/avatars/_default.png"
        elif avatar and c.get("user_permalink"):
            ext = ".png" if avatar.endswith(".png") else ".jpg"
            avatar_rel = f"/static/images/commenters/{c['user_permalink']}{ext}"
        else:
            avatar_rel = ""
        db.session.add(Comment(
            id=c.get("id"),
            track_id=track.id,
            author_name=c.get("user_name") or "",
            author_permalink=c.get("user_permalink") or "",
            author_avatar=avatar_rel,
            body=c.get("body") or "",
            created_at=parse_date(c.get("created_at")) or MIRROR_DATE,
            timestamp_ms=c.get("timestamp") or 0,
        ))
    db.session.flush()
    db.session.commit()


def _pick(playlist_permalink, country, offset, count, skip_ids=()):
    """Deterministic track picks from a chart playlist for benchmark fixtures."""
    pl = Playlist.query.filter_by(permalink=playlist_permalink, chart_country=country).first()
    if not pl:
        return []
    tracks = [e.track for e in pl.entries if e.track and e.track.id not in skip_ids]
    return tracks[offset:offset + count]


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = {}
    for i, u in enumerate(BENCHMARK_USERS):
        row = User(
            username=u["username"], email=u["email"], display_name=u["display"],
            city=u["city"], bio=u["bio"],
            created_at=datetime(2024, 1, 10 + i),
        )
        row.set_password(BENCHMARK_PASSWORD)
        users[u["username"]] = row
        db.session.add(row)
    db.session.flush()

    # ---- follows (real artists, deterministic picks) --------------------- #
    top_artists = Artist.query.filter(Artist.followers > 1000) \
        .order_by(Artist.followers.desc()).all()
    follow_plan = {
        "alice_j": (0, 4), "bob_c": (4, 4), "carol_d": (8, 4), "david_k": (12, 4),
    }
    follow_rows = {}
    for uname, (start, count) in follow_plan.items():
        picks = top_artists[start:start + count]
        follow_rows[uname] = picks
        for a in picks:
            db.session.add(Follow(user_id=users[uname].id, artist_id=a.id,
                                  created_at=datetime(2025, 6, 1)))
    db.session.flush()

    # ---- likes / reposts / history -------------------------------------- #
    like_plan = {
        "alice_j": [("all-music-genres", "US", 0, 4), ("new-hot", "US", 0, 2)],
        "bob_c": [("hip-hop", "US", 0, 5), ("new-hot", "US", 2, 1)],
        "carol_d": [("dance", "UK", 0, 4), ("all-music-genres", "UK", 0, 2)],
        "david_k": [("rock", "US", 0, 3), ("folk", "US", 0, 2)],
    }
    used = {}
    for uname, plan in like_plan.items():
        seen = set()
        for plink, country, offset, count in plan:
            for t in _pick(plink, country, offset, count, skip_ids=seen):
                seen.add(t.id)
                db.session.add(Like(user_id=users[uname].id, track_id=t.id,
                                   created_at=datetime(2025, 9, 1)))
        # two reposts from the liked set
        for t in list(seen)[:2]:
            db.session.add(Repost(user_id=users[uname].id, track_id=t,
                                 created_at=datetime(2025, 9, 2)))
        # listening history: three plays per user
        for t in list(seen)[:3]:
            db.session.add(PlayEvent(user_id=users[uname].id, track_id=t,
                                    played_at=datetime(2026, 9, 20)))
    db.session.flush()

    # ---- user playlists -------------------------------------------------- #
    pl_specs = [
        ("alice_j", "Late Night Drive", "Alternative"),
        ("bob_c", "Gym Rotation", "Hip-hop & Rap"),
        ("carol_d", "Warehouse Warmup", "House"),
        ("david_k", "Rainy Day Indie", "Indie"),
    ]
    for uname, title, genre in pl_specs:
        pl = UserPlaylist(user_id=users[uname].id,
                          permalink=re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")),
                          title=title, genre=genre, created_at=datetime(2025, 8, 15))
        db.session.add(pl)
        db.session.flush()
        source_pl = ("all-music-genres", "US") if uname in ("alice_j", "bob_c") else \
                    ("dance", "UK") if uname == "carol_d" else ("rock", "US")
        picks = _pick(source_pl[0], source_pl[1], 10, 3)
        for pos, t in enumerate(picks, 1):
            db.session.add(UserPlaylistTrack(playlist_id=pl.id, track_id=t.id,
                                             position=pos, added_at=datetime(2025, 8, 15)))
    db.session.flush()

    # ---- subscriptions --------------------------------------------------- #
    plan_map = {
        "alice_j": ("go-plus", "Go+", "monthly", 1199, datetime(2026, 3, 26), datetime(2026, 10, 26)),
        "bob_c": ("next-pro", "Next Pro", "yearly", 9900, datetime(2025, 10, 26), datetime(2026, 10, 26)),
    }
    for uname, (code, title, cycle, amount, started, renews) in plan_map.items():
        db.session.add(Subscription(user_id=users[uname].id, plan_code=code,
                                   plan_title=title, cycle=cycle, amount=amount,
                                   started_at=started, renews_at=renews,
                                   card_last4="4242"))
    db.session.commit()


def build_seed_file() -> None:
    """Materialise instance_seed/soundcloud.db from a fresh runtime build."""
    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = INSTANCE_DIR / "soundcloud.db"
    if db_path.exists():
        db_path.unlink()
    with app.app_context():
        create_schema()
        seed_database()
        seed_benchmark_users()
        INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
        seed_path = INSTANCE_SEED / "soundcloud.db"
        for stale in INSTANCE_SEED.glob("*.db"):
            stale.unlink()
        shutil.copy2(db_path, seed_path)
        size = seed_path.stat().st_size
        digest = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    print(f"[seed] instance_seed/soundcloud.db written ({size} bytes, sha256 {digest[:16]}…)")


if __name__ == "__main__":
    build_seed_file()
