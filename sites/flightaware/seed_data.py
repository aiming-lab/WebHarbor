#!/usr/bin/env python3
"""Deterministic seed for the FlightAware mirror.

`python seed_data.py` regenerates the reset seed DB (instance_seed/flightaware.db)
from the tracked _seed_*.py source snapshots alone — no scraped_data, no wall
clock, no random salt (frozen bcrypt hashes), so the SQLite artifact is
byte-reproducible on every build. The same seed functions run at every
container boot and early-return on a populated DB, preserving the
byte-identical reset invariant.

Content provenance: airports, flight boards, flight details, aircraft types,
airlines, photos, squawks, delay and cancellation statistics come from the
tracked _seed_*.py snapshots captured from flightaware.com live pages on
2026-09-22. Benchmark users and their alerts are generated deterministically
below.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _seed_airports import AIRPORTS
from _seed_airlines import AIRLINES
from _seed_types import AIRCRAFT_TYPES
from _seed_boards import BOARD_ROWS
from _seed_flights import FLIGHTS
from _seed_photos import PHOTOS
from _seed_squawks import SQUAWKS
from _seed_stats import STATS

MIRROR_DATE = "2026-09-22"
PASSWORD = "TestPass123!"
# bcrypt hash of TestPass123! — frozen so the seed DB is byte-reproducible
# (generated with bcrypt.gensalt(rounds=12) once; identical for all users).
PASSWORD_HASH = "$2b$12$D/eRvVSrDoJ8.PZPF9Q/NOMd64jKdJ82.HbfdAntTLr58aoJs6gj."

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]

# Pre-existing alerts per benchmark user (flight alerts mirror the upstream
# "Status Alerts" feature; idents reference flights on today's boards).
USER_ALERTS = {
    "alice.j@test.com": [
        {"ident": "UAL1063", "alert_type": "basic", "created_text": "about a week ago"},
        {"ident": "", "origin_code": "KJFK", "dest_code": "EGLL", "alert_type": "basic",
         "created_text": "about 3 days ago"},
    ],
    "bob.c@test.com": [
        {"ident": "AAL954", "alert_type": "full", "created_text": "about 2 days ago"},
        {"ident": "JBU1024", "alert_type": "basic", "created_text": "about a month ago"},
        {"ident": "", "origin_code": "KSFO", "dest_code": "RJTT", "alert_type": "full",
         "created_text": "about 5 hours ago"},
    ],
    "carol.d@test.com": [
        {"ident": "DAL667", "alert_type": "basic", "created_text": "about 12 hours ago"},
    ],
    "david.k@test.com": [
        {"ident": "UAE203", "alert_type": "full", "created_text": "about 9 hours ago"},
        {"ident": "", "origin_code": "KEWR", "dest_code": "MMMX", "alert_type": "basic",
         "created_text": "about 2 weeks ago"},
    ],
}


def _flight_origin_name(airports_by_code, f):
    if f.get("origin_name"):
        return f["origin_name"]
    a = airports_by_code.get(f.get("origin_code") or "")
    return a.name if a else ""


def seed_static_data(db):
    """Populate all public content. Idempotent at the function level."""
    from app import (Airport, Airline, AircraftType, Flight, BoardRow,
                     AirportDelay, CancelStat, DailyStat, Photo, PhotoComment,
                     Squawk)

    airports_by_code = {}
    for a in AIRPORTS:
        row = Airport(code=a["code"], iata=a.get("iata", ""), name=a["name"],
                      city=a.get("city", ""), region=a.get("region", ""),
                      country=a.get("country", ""), tz_label=a.get("tz_label", ""),
                      elevation_ft=a.get("elevation_ft"),
                      weather_text=a.get("weather_text", ""),
                      remarks_text=a.get("remarks_text", ""),
                      is_major=a.get("is_major", False))
        db.session.add(row)
        airports_by_code[a["code"]] = row
    db.session.flush()

    airlines = {}
    for a in AIRLINES:
        row = Airline(code=a["code"], iata=a.get("iata", ""), name=a["name"],
                      country=a.get("country", ""), flights_count=a.get("flights_count", 0))
        db.session.add(row)
        airlines[a["code"]] = row
    db.session.flush()

    types = {}
    for t in AIRCRAFT_TYPES:
        row = AircraftType(code=t["code"], name=t["name"],
                           manufacturer=t.get("manufacturer", ""),
                           flights_count=t.get("flights_count", 0))
        db.session.add(row)
        types[t["code"]] = row
    db.session.flush()

    # flights: today's instances + history rows
    for f in FLIGHTS["today"]:
        row = Flight(
            ident=f["ident"], airline_code=f.get("airline_code", ""),
            flight_date=f.get("flight_date", MIRROR_DATE),
            aircraft_type=f.get("aircraft_type", ""),
            origin_code=f.get("origin_code", ""), origin_name=f.get("origin_name", ""),
            dest_code=f.get("dest_code", ""), dest_name=f.get("dest_name", ""),
            sched_dep=f.get("sched_dep", ""), actual_dep=f.get("actual_dep", ""),
            sched_arr=f.get("sched_arr", ""), actual_arr=f.get("actual_arr", ""),
            dep_text=f.get("dep_text", ""), arr_text=f.get("arr_text", ""),
            gate_dep=f.get("gate_dep", ""), gate_arr=f.get("gate_arr", ""),
            arr_terminal=f.get("arr_terminal", ""),
            status=f.get("status", ""), status_detail=f.get("status_detail", ""),
            elapsed_text=f.get("elapsed_text", ""), total_travel_text=f.get("total_travel_text", ""),
            remaining_text=f.get("remaining_text", ""), flown_mi=f.get("flown_mi"),
            togo_mi=f.get("togo_mi"),
            distance_mi=f.get("distance_mi"), speed_mph=f.get("speed_mph"),
            planned_speed_mph=f.get("planned_speed_mph"),
            altitude_ft=f.get("altitude_ft"), planned_altitude_ft=f.get("planned_altitude_ft"),
            route=f.get("route", ""), is_today=True)
        db.session.add(row)
    for h in FLIGHTS["history"]:
        db.session.add(Flight(
            ident=h["ident"], airline_code=h["ident"][:3] if h["ident"][:3].isalpha() else "",
            flight_date=h["date"], aircraft_type=h.get("aircraft_type", ""),
            origin_code=h.get("origin_code", ""), origin_name=h.get("origin_name", ""),
            dest_code=h.get("dest_code", ""), dest_name=h.get("dest_name", ""),
            dep_text=h.get("dep_time", ""), arr_text=h.get("arr_time", ""),
            duration_text=h.get("duration", ""), is_today=False))
    db.session.flush()

    # board rows
    for r in BOARD_ROWS:
        db.session.add(BoardRow(
            airport_code=r["airport_code"], board=r["board"], ident=r["ident"],
            aircraft_type=r["aircraft_type"], other_label=r["other_label"],
            dep_text=r["dep_text"], arr_text=r["arr_text"],
            sort_min=r.get("sort_min"), row_index=r.get("row_index", 0)))
    db.session.flush()

    # delay + cancellation stats
    for d in STATS.get("delays", []):
        db.session.add(AirportDelay(
            airport_code=d.get("airport_code", ""), airport_label=d.get("airport_label", ""),
            dep_delay_text=d.get("dep_delay_text", ""), arr_delay_text=d.get("arr_delay_text", "")))
    for scope_key in ("cancel_airline", "cancel_origin", "cancel_dest"):
        for c in STATS.get(scope_key, []):
            db.session.add(CancelStat(
                scope=c.get("scope", ""), label=c.get("label", ""),
                cancelled=c.get("cancelled", 0), cancelled_pct=c.get("cancelled_pct", "0%"),
                delayed=c.get("delayed", 0), delayed_pct=c.get("delayed_pct", "0%")))
    for s in STATS.get("daily", []):
        db.session.add(DailyStat(key=s["key"], value_int=s.get("value_int"), value=""))
    db.session.flush()

    # photos + comments
    for p in PHOTOS:
        row = Photo(
            pid=p["pid"], view_hash=p.get("view_hash", ""), title=p.get("title", ""),
            aircraft_type=p.get("aircraft_type", ""), registration=p.get("registration", ""),
            airline_prefix=p.get("airline_prefix", ""), airport_code=p.get("airport_code", ""),
            photographer=p.get("photographer", ""), description=p.get("description", ""),
            submitted_text=p.get("submitted_text", ""), votes=p.get("votes", 0),
            vote_average=p.get("vote_average", 0.0), views=p.get("views", 0),
            staff_pick=bool(p.get("staff_pick")), week_top=bool(p.get("week_top")),
            reg_rank=p.get("reg_rank"), type_rank=p.get("type_rank"),
            image_file=p.get("image_file", ""))
        db.session.add(row)
        db.session.flush()
        for c in p.get("comments", []):
            db.session.add(PhotoComment(photo_id=row.id, author=c.get("author", ""),
                                        when_text=c.get("when_text", ""), text=c.get("text", "")))
    db.session.flush()

    # squawks + comments
    for s in SQUAWKS:
        row = Squawk(
            sid=s.get("sid", ""), title=s.get("title", ""), slug=s.get("slug", ""),
            source_label=s.get("source_label", ""), source_url=s.get("source_url", ""),
            summary=s.get("summary", ""), submitter=s.get("submitter", ""),
            submitted_text=s.get("submitted_text", ""), votes=s.get("votes", 0),
            comment_count=s.get("comment_count", 0),
            staff_pick=bool(s.get("staff_pick")), lists=s.get("lists", ""))
        db.session.add(row)
        db.session.flush()
        for c in s.get("comments", []):
            db.session.add(SquawkComment(squawk_id=row.id, author=c.get("author", ""),
                                         when_text=c.get("when_text", ""), text=c.get("text", "")))
    db.session.commit()


def seed_users(db, bcrypt):
    """Seed the four benchmark users with pre-existing flight alerts."""
    from app import User, Alert

    for spec in BENCHMARK_USERS:
        user = User(username=spec["username"], email=spec["email"],
                    password_hash=PASSWORD_HASH, display_name=spec["display_name"])
        db.session.add(user)
    db.session.flush()
    for spec in BENCHMARK_USERS:
        user = User.query.filter_by(email=spec["email"]).first()
        for a in USER_ALERTS.get(spec["email"], []):
            db.session.add(Alert(user_id=user.id, ident=a.get("ident", ""),
                                 origin_code=a.get("origin_code", ""),
                                 dest_code=a.get("dest_code", ""),
                                 alert_type=a.get("alert_type", "basic"),
                                 created_text=a.get("created_text", "about a week ago")))
    db.session.commit()


def main():
    """Standalone rebuild: python seed_data.py"""
    import os
    import shutil

    base = os.path.dirname(os.path.abspath(__file__))
    instance = os.path.join(base, "instance")
    seed_dir = os.path.join(base, "instance_seed")
    os.makedirs(instance, exist_ok=True)
    os.makedirs(seed_dir, exist_ok=True)
    db_path = os.path.join(instance, "flightaware.db")
    seed_path = os.path.join(seed_dir, "flightaware.db")
    # Remove the DB BEFORE importing app: the app module's import-time
    # bootstrap creates and seeds a fresh DB, so main() must not seed again.
    for path in (db_path, seed_path):
        if os.path.exists(path):
            os.remove(path)

    import app as app_module  # noqa: E402  (import seeds the fresh DB)
    with app_module.app.app_context():
        from app import db, Flight, User, Photo, Squawk  # noqa: E402
        assert Flight.query.count() > 0, "bootstrap seed produced no flights"
        assert User.query.filter_by(email="alice.j@test.com").first() is not None
        assert Photo.query.count() > 0
        if SQUAWKS:
            assert Squawk.query.count() > 0
    shutil.copyfile(db_path, seed_path)
    print(f"[seed] rebuilt {db_path} and copied to instance_seed/flightaware.db")


if __name__ == "__main__":
    main()
