"""Deterministic seed builder for the NFL.com mirror.

Reads the tracked, upstream-sourced source_data/ snapshots and materialises
the runtime DB. Called at image build time (see the Dockerfile) and
defensively at boot; every seed function early-returns when its data already
exists so /reset/<nfl> stays byte-identical.

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py

Benchmark fixtures (users, subscriptions, orders) are mirror-native and
reference real seeded entities; every date is pinned relative to MIRROR_DATE
so the seed is byte-stable across builds.
"""
from __future__ import annotations

import os

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

import json  # noqa: E402
import shutil  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

MIRROR_DATE = datetime(2026, 9, 24)

from app import (  # noqa: E402
    Game,
    Injury,
    NewsArticle,
    Player,
    PlusOrder,
    StatLeader,
    Subscription,
    Team,
    Transaction,
    User,
    Video,
    app,
    create_schema,
    db,
    game_slug,
    stable_password_hash,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"
INSTANCE_SEED = BASE_DIR / "instance_seed"

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "display": "Alice Johnson", "username": "alice_j",
     "favorite": "KC", "newsletter": True},
    {"email": "bob.c@test.com", "display": "Bob Chen", "username": "bob_c",
     "favorite": "GB", "newsletter": False},
    {"email": "carol.d@test.com", "display": "Carol Davis", "username": "carol_d",
     "favorite": "DAL", "newsletter": False},
    {"email": "david.k@test.com", "display": "David Kim", "username": "david_k",
     "favorite": "NYJ", "newsletter": True},
]


def load(name: str):
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def seed_database() -> None:
    if Team.query.count() > 0:
        return

    # ---- teams ---------------------------------------------------------- #
    team_details = load("team_details.json")
    teams = load("teams.json")
    team_rows = {}
    for abbr, t in teams.items():
        extra = team_details.get(t["slug"], {})
        team_rows[abbr] = Team(
            abbr=abbr,
            full_name=t["full_name"],
            location=t["location"],
            nickname=t["nickname"],
            conference=t["conference"],
            division=t["division"],
            primary_color=t["primary_color"],
            secondary_color=t["secondary_color"],
            established=t["established"],
            slug=t["slug"],
            logo_file=t.get("logo_file", f"logos/{abbr}.svg"),
            wins=t.get("wins", 0),
            losses=t.get("losses", 0),
            ties=t.get("ties", 0),
            pct=t.get("pct", "0.000"),
            points_for=t.get("points_for", 0),
            points_against=t.get("points_against", 0),
            division_rank=t.get("division_rank", 0),
            head_coach=extra.get("head_coach", ""),
            stadium=extra.get("stadium", ""),
            owners=extra.get("owners", ""),
        )
        db.session.add(team_rows[abbr])
    db.session.flush()

    # ---- players -------------------------------------------------------- #
    details = load("player_details.json")
    for p in load("players.json"):
        d = details.get(p["slug"], {})
        info = d.get("info", {})
        exp = p["experience"]
        try:
            age = int(info.get("age", 0) or 0)
        except ValueError:
            age = 0
        db.session.add(Player(
            slug=p["slug"],
            name=p["name"],
            team_abbr=p["team"],
            number=p["number"],
            pos=p["pos"],
            status=p["status"],
            height_in=int(p["height_in"] or 0),
            weight=int(p["weight"] or 0),
            experience=exp,
            college=p["college"],
            has_headshot=bool(p["headshot_id"]),
            featured=bool(d),
            arms=info.get("arms", ""),
            hands=info.get("hands", ""),
            age=age,
            hometown=info.get("hometown", ""),
            recent_games=json.dumps(d.get("recent_games", [])),
            career=json.dumps(d.get("career", [])),
        ))
    db.session.flush()

    # ---- games ---------------------------------------------------------- #
    for g in load("games.json"):
        home = team_rows[g["home"]]
        away = team_rows[g["away"]]
        db.session.add(Game(
            id=g["id"],
            slug=game_slug(away, home, g["week"]),
            week=g["week"],
            date=g["date"] or "",
            time=g["time"],
            category=g["category"],
            home_abbr=g["home"],
            away_abbr=g["away"],
            venue=g["venue"],
            venue_city=g["venue_city"],
            international=g["international"],
            networks=json.dumps(g["networks"]),
            status=g["status"],
            home_score=g.get("home_score", 0),
            away_score=g.get("away_score", 0),
            home_quarters=json.dumps(g.get("home_quarters", [])),
            away_quarters=json.dumps(g.get("away_quarters", [])),
            attendance=g.get("attendance") or 0,
            weather=g.get("weather", ""),
        ))
    db.session.flush()

    # ---- news ------------------------------------------------------------ #
    for a in load("news.json"):
        published = datetime.strptime(a["published"], "%Y-%m-%dT%H:%M:%S.%fZ") if "." in a["published"] \
            else datetime.strptime(a["published"], "%Y-%m-%dT%H:%M:%SZ")
        db.session.add(NewsArticle(
            slug=a["slug"],
            title=a["title"],
            description=a["description"],
            body=a["body"],
            section=a["section"],
            author=a["author"],
            published=published,
            image_id=a["image_id"],
            keywords=json.dumps(a["keywords"]),
        ))
    db.session.flush()

    # ---- videos ---------------------------------------------------------- #
    for v in load("videos.json"):
        db.session.add(Video(
            slug=v["slug"],
            title=v["title"],
            description=v["description"],
            category=v["category"],
            image_id=v["image_id"],
            channel=v["channel"],
        ))
    db.session.flush()

    # ---- stat leaders ---------------------------------------------------- #
    players_by_name = {}
    for p in Player.query.all():
        players_by_name.setdefault(p.name, p)
    for cat, rows in load("stat_leaders.json").items():
        for rank, row in enumerate(rows, 1):
            name = row.pop("player", "")
            player = players_by_name.get(name)
            team_abbr = player.team_abbr if player else ""
            db.session.add(StatLeader(
                category=cat,
                rank=rank,
                player_name=name,
                team_abbr=team_abbr,
                player_slug=player.slug if player else "",
                stats=json.dumps(row, ensure_ascii=False),
            ))
    db.session.flush()

    # ---- injuries -------------------------------------------------------- #
    for row in load("injuries.json"):
        db.session.add(Injury(**row))
    db.session.flush()

    # ---- transactions ---------------------------------------------------- #
    for row in load("transactions.json"):
        db.session.add(Transaction(
            category=row["category"],
            team=row["team"],
            to_team=row.get("to", ""),
            date=row["date"],
            name=row["name"],
            position=row.get("position", ""),
            transaction=row["transaction"],
        ))
    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    plans = {
        "nfl_plus_premium_monthly": ("NFL+ Premium Monthly", "month", 14.99),
        "nfl_plus_annual": ("NFL+ Annual", "year", 49.99),
        "nfl_plus_premium_annual": ("NFL+ Premium Annual", "year", 99.99),
    }
    fixtures = [
        # (user index, plan code, days ago started, had past order?)
        (0, None, 0, False),
        (1, "nfl_plus_premium_monthly", 12, False),
        (2, "nfl_plus_annual", 40, True),
        (3, "nfl_plus_premium_annual", 5, True),
    ]
    for spec in fixtures:
        idx, code, days_ago, had_order = spec
        u = BENCHMARK_USERS[idx]
        user = User(
            email=u["email"],
            display_name=u["display"],
            username=u["username"],
            favorite_team=u["favorite"],
            newsletter=u["newsletter"],
            created_at=MIRROR_DATE - timedelta(days=200),
        )
        user.password_hash = stable_password_hash(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()
        if code:
            title, cycle, amount = plans[code]
            started = MIRROR_DATE - timedelta(days=days_ago)
            if cycle == "year":
                renews = started + timedelta(days=365)
            else:
                renews = started + timedelta(days=30)
            db.session.add(Subscription(
                user_id=user.id,
                plan_code=code,
                plan_title=title,
                cycle=cycle,
                amount=amount,
                started_at=started,
                renews_at=renews,
            ))
            if had_order:
                tax = round(amount * 0.0895, 2)
                db.session.add(PlusOrder(
                    user_id=user.id,
                    order_ref=f"NFL-{user.id:02d}{code[-4:].upper()[:4]}",
                    plan_code=code,
                    plan_title=title,
                    cycle=cycle,
                    amount=amount,
                    tax=tax,
                    total=round(amount + tax, 2),
                    card_last4="4242",
                    cardholder=u["display"],
                    created_at=started,
                ))
    db.session.commit()


def build_seed_file() -> None:
    """Materialise instance_seed/nfl.db from a fresh runtime build."""
    import hashlib

    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = INSTANCE_DIR / "nfl.db"
    if db_path.exists():
        db_path.unlink()
    with app.app_context():
        create_schema()
        seed_database()
        seed_benchmark_users()
        INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
        seed_path = INSTANCE_SEED / "nfl.db"
        for stale in INSTANCE_SEED.glob("*.db"):
            stale.unlink()
        shutil.copy2(db_path, seed_path)
        size = seed_path.stat().st_size
        digest = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    print(f"[seed] instance_seed/nfl.db written ({size} bytes, sha256 {digest[:16]}…)")


if __name__ == "__main__":
    build_seed_file()
