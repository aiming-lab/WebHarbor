"""Build-time / boot-time seeder for the mta mirror.

Everything loads from the tracked source_data/ snapshots (captured from the
live site on 2026-09-23). The heavy GTFS timetables are bulk-loaded with raw
sqlite3 executemany so a full seed takes ~1 minute instead of ~20.

Every seed function is gated at the top (see AGENTS.md: idempotent seeding).
The instance_seed/mta.db ships in the HF dataset, so the boot path normally
finds a populated DB and returns immediately.
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import sqlite3
import zipfile

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"
GTFS = SOURCE / "gtfs"

# Frozen bcrypt digest for the benchmark password 'TestPass123!' (frozen
# rather than re-generated so the seed DB is byte-identical on every rebuild).
BENCHMARK_PASSWORD_DIGEST = (
    "$2b$12$mTNQa9oqZyOoIJBpKN.0p.LVaApMSu9gZnYufEZrciM5QgBN7EM7u"
)

MIRROR_NOW = datetime.datetime(2026, 9, 23, 19, 0)

SUBWAY_SLUGS = {
    "1": "1-train", "2": "2-train", "3": "3-train", "4": "4-train", "5": "5-train",
    "6": "6-train", "7": "7-train", "A": "a-train", "C": "c-train", "E": "e-train",
    "B": "b-train", "D": "d-train", "F": "f-train", "M": "m-train", "G": "g-train",
    "J": "j-train", "L": "l-train", "N": "n-train", "Q": "q-train", "R": "r-train",
    "W": "w-train", "GS": "42-st-shuttle", "FS": "franklin-avenue-shuttle",
    "H": "rockaway-park-shuttle", "SI": "staten-island-railway",
}


def _read_json(name):
    return json.loads((SOURCE / name).read_text())


db = None


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def _load_reference(db):
    sub = _read_json("subway.json")
    db.session.execute(db.text("DELETE FROM subway_routes"))
    for r in sub["routes"]:
        db.session.execute(db.text(
            "INSERT INTO subway_routes (id, name, desc, color, text_color, slug) "
            "VALUES (:i, :n, :d, :c, :t, :s)"),
            {"i": r["id"], "n": r["name"], "d": r["desc"], "c": r["color"],
             "t": r["text_color"], "s": SUBWAY_SLUGS.get(r["id"], r["id"].lower())})
    stations = []
    for s in sub["stations"]:
        stations.append({"id": s["id"], "name": s["name"], "agency": "subway",
                         "lat": s["lat"], "lon": s["lon"], "borough": s["borough"],
                         "wheelchair": bool(s["wheelchair"]),
                         "lines": json.dumps(s["lines"]), "zone": None, "url_slug": ""})
    for which in ("lirr", "metro_north"):
        data = _read_json(f"{which}.json")
        prefix = "LIR-" if which == "lirr" else "MNR-"
        for s in data["stations"]:
            stations.append({"id": prefix + s["id"], "name": s["name"],
                             "gtfs": s["id"],
                             "agency": "lirr" if which == "lirr" else "mnr",
                             "lat": s["lat"], "lon": s["lon"], "borough": "",
                             "wheelchair": bool(s["wheelchair"]), "lines": "[]",
                             "zone": s.get("zone"),
                             "url_slug": (s.get("url") or "").rsplit("/", 1)[-1]})
    db.session.execute(db.text("DELETE FROM stations"))
    for st in stations:
        db.session.execute(db.text(
            "INSERT INTO stations (id, name, agency, gtfs_stop_id, lat, lon, borough, "
            "wheelchair, lines, zone, url_slug) VALUES (:id, :name, :agency, :gtfs, :lat, "
            ":lon, :borough, :wheelchair, :lines, :zone, :url_slug)"),
            {"id": st["id"], "name": st["name"], "agency": st["agency"],
             "gtfs": st.get("gtfs", st["id"]), "lat": st["lat"],
             "lon": st["lon"], "borough": st["borough"], "wheelchair": int(st["wheelchair"]),
             "lines": st["lines"], "zone": st["zone"], "url_slug": st["url_slug"]})
    db.session.execute(db.text("DELETE FROM transfers"))
    for a, b in sub["transfers"]:
        db.session.execute(db.text(
            "INSERT INTO transfers (from_station, to_station) VALUES (:a, :b)"),
            {"a": a, "b": b})
    _apply_accessibility(db)
    db.session.commit()


def _apply_accessibility(db):
    """Mark ADA-accessible stations from the upstream accessible-stations list.

    The GTFS feeds carry no wheelchair_boarding values, so accessibility comes
    from the MTA Accessible Stations page snapshot instead (see
    scripts_dev/harvest_accessibility.py): every station whose GTFS id appears
    in the list is accessible, and the upstream partial-accessibility notes
    ("downtown only", "L only; 4/5/6 is not accessible") are preserved.
    """
    data = _read_json("accessible_stations.json")
    for entry in data["stations"]:
        for gid in entry["gtfs_ids"]:
            db.session.execute(db.text(
                "UPDATE stations SET wheelchair = 1, access_note = :note "
                "WHERE id = :gid"),
                {"gid": gid, "note": entry["note"]})


def _load_alerts(db):
    alerts = _read_json("service_alerts.json")
    db.session.execute(db.text("DELETE FROM service_alerts"))
    ref = int(MIRROR_NOW.timestamp())
    for a in alerts:
        routes = a["routes"]
        modes = set()
        for r in routes:
            agency = r.get("agency", "")
            if agency in ("MTASBWY",):
                modes.add("subway")
            elif agency in ("MTABC",) or (agency == "MTA NYCT"):
                modes.add("bus")
            elif agency == "LI":
                modes.add("lirr")
            elif agency == "MNR":
                modes.add("mnr")
        if not modes:
            continue
        mode = "bus" if "bus" in modes else sorted(modes)[0]
        start = a["active_period"][0].get("start") if a["active_period"] else None
        end = None
        for p in a["active_period"]:
            if p.get("end"):
                end = p["end"]
        planned = bool(a["alert_type"].startswith("Planned"))
        db.session.execute(db.text(
            "INSERT INTO service_alerts (alert_id, alert_type, mode, routes, stops, "
            "start_ts, end_ts, header_html, desc_html, header_text, desc_text, "
            "created_ts, updated_ts, planned) VALUES (:a, :t, :m, :r, :s, :st, :e, "
            ":hh, :dh, :ht, :dt, :c, :u, :p)"),
            {"a": a["id"], "t": a["alert_type"], "m": mode,
             "r": json.dumps(routes), "s": json.dumps(a["stops"]),
             "st": start, "e": end, "hh": a["header_html"], "dh": a["description_html"],
             "ht": a["header_text"], "dt": a["description_text"],
             "c": a["created_at"], "u": a["updated_at"], "p": int(planned)})
    db.session.commit()


def _load_elevators(db):
    data = _read_json("elevators.json")
    db.session.execute(db.text("DELETE FROM equipment"))
    for e in data["equipment"]:
        db.session.execute(db.text(
            "INSERT INTO equipment (equipmentno, station, trainno, equipmenttype, "
            "serving, ada, is_active, short_desc, lines, gtfs_stop_id, "
            "alternative_route) VALUES (:e, :s, :t, :y, :sv, :ada, :act, :sd, :l, :g, :ar)"),
            {"e": e.get("equipmentno", ""), "s": e.get("station", ""),
             "t": e.get("trainno", ""), "y": e.get("equipmenttype", "EL"),
             "sv": e.get("serving", ""), "ada": int(e.get("ADA") == "Y"),
             "act": int(e.get("isactive") == "Y"), "sd": e.get("shortdescription", ""),
             "l": e.get("linesservedbyelevator", ""), "g": e.get("elevatorsgtfsstopid", ""),
             "ar": e.get("alternativeroute", "")})
    db.session.execute(db.text("DELETE FROM outages"))
    for o in data["outages"]:
        db.session.execute(db.text(
            "INSERT INTO outages (equipmentno, station, trainno, equipmenttype, "
            "serving, ada, outage_date, estimated_return, reason, is_active, "
            "is_upcoming) VALUES (:e, :s, :t, :y, :sv, :ada, :od, :er, :r, :act, :up)"),
            {"e": o.get("equipment", ""), "s": o.get("station", ""),
             "t": o.get("trainno", ""), "y": o.get("equipmenttype", "EL"),
             "sv": o.get("serving", ""), "ada": int(o.get("ADA") == "Y"),
             "od": o.get("outagedate", ""), "er": o.get("estimatedreturntoservice", ""),
             "r": o.get("reason", ""), "act": 1, "up": int(o.get("isupcomingoutage") == "Y")})
    db.session.commit()


def _load_fares(db):
    fares = _read_json("railroad_fares.json")
    db.session.execute(db.text("DELETE FROM rail_fares"))
    zones = fares["lirr"]["zones"]
    for origin, rows in fares["lirr"]["matrix"].items():
        for ticket, prices in rows.items():
            for dest, price in zip(zones, prices):
                if price is None:
                    continue
                db.session.execute(db.text(
                    "INSERT INTO rail_fares (origin_zone, dest_zone, ticket_type, price) "
                    "VALUES (:o, :d, :t, :p)"),
                    {"o": origin, "d": dest, "t": ticket, "p": price})
    db.session.execute(db.text("DELETE FROM mnr_fares"))
    for section in fares["mnr_harlem_hudson"]:
        for ticket, prices in section["prices"].items():
            db.session.execute(db.text(
                "INSERT INTO mnr_fares (line, zone, ticket_type, price, price_peak, "
                "price_offpeak) VALUES ('harlem_hudson', :z, :t, :p, :pk, :po)"),
                {"z": section["zone"], "t": ticket,
                 "p": prices[0] if prices else None,
                 "pk": prices[0] if prices else None,
                 "po": prices[1] if len(prices) > 1 else None})
    for section in fares["mnr_newhaven"]:
        for ticket, prices in section["prices"].items():
            db.session.execute(db.text(
                "INSERT INTO mnr_fares (line, zone, ticket_type, price, price_peak, "
                "price_offpeak) VALUES ('new_haven', :z, :t, :p, :pk, :po)"),
                {"z": section["zone"], "t": ticket,
                 "p": prices[0] if prices else None,
                 "pk": prices[0] if prices else None,
                 "po": prices[1] if len(prices) > 1 else None})
    db.session.execute(db.text("DELETE FROM port_jervis_fares"))
    for entry in fares["port_jervis_pascack"]:
        for ticket, prices in entry["prices"].items():
            db.session.execute(db.text(
                "INSERT INTO port_jervis_fares (station, ticket_type, price_hoboken, "
                "price_penn) VALUES (:s, :t, :h, :p)"),
                {"s": entry["name"], "t": ticket,
                 "h": prices[0] if prices else None,
                 "p": prices[1] if len(prices) > 1 else None})
    db.session.commit()


def _load_content(db):
    content = _read_json("content.json")
    db.session.execute(db.text("DELETE FROM content_pages"))
    for path, page in content.items():
        db.session.execute(db.text(
            "INSERT INTO content_pages (path, title, label, hero, updated, blocks) "
            "VALUES (:p, :t, :l, :h, :u, :b)"),
            {"p": path, "t": page["title"], "l": page.get("label", ""),
             "h": page.get("hero", ""), "u": page.get("updated", ""),
             "b": json.dumps(page["blocks"])})
    db.session.execute(db.text("DELETE FROM projects"))
    projects = _read_json("projects.json")
    for slug, p in projects.items():
        db.session.execute(db.text(
            "INSERT INTO projects (slug, title, blocks) VALUES (:s, :t, :b)"),
            {"s": slug, "t": p["title"], "b": json.dumps(p["blocks"])})
    db.session.execute(db.text("DELETE FROM press_releases"))
    press = _read_json("press_releases.json")
    for art in press:
        db.session.execute(db.text(
            "INSERT INTO press_releases (path, title, date, blocks) VALUES "
            "(:p, :t, :d, :b)"),
            {"p": art["path"], "t": art["title"], "d": art.get("date", ""),
             "b": json.dumps(art["blocks"])})
    db.session.commit()


# ---------------------------------------------------------------------------
# GTFS timetables (bulk)
# ---------------------------------------------------------------------------

def _service_day_types(which: str) -> dict[str, list[str]]:
    """Map service_id -> [day_type] ('weekday' | 'saturday' | 'sunday')."""
    out: dict[str, list[str]] = {}
    with zipfile.ZipFile(GTFS / f"{which}.zip") as z:
        names = z.namelist()
        if "calendar.txt" in names:
            for row in csv.DictReader(z.read("calendar.txt").decode("utf-8-sig").splitlines()):
                if row.get("monday") == "1" or row.get("tuesday") == "1" or \
                   row.get("wednesday") == "1" or row.get("thursday") == "1" or \
                   row.get("friday") == "1":
                    out.setdefault(row["service_id"], set()).add("weekday")
                if row.get("saturday") == "1":
                    out.setdefault(row["service_id"], set()).add("saturday")
                if row.get("sunday") == "1":
                    out.setdefault(row["service_id"], set()).add("sunday")
        if "calendar_dates.txt" in names:
            for row in csv.DictReader(z.read("calendar_dates.txt").decode("utf-8-sig").splitlines()):
                if row.get("exception_type") != "1":
                    continue
                try:
                    d = datetime.datetime.strptime(row["date"], "%Y%m%d")
                except ValueError:
                    continue
                dow = d.strftime("%a")
                day = ("weekday" if dow in ("Mon", "Tue", "Wed", "Thu", "Fri")
                       else ("saturday" if dow == "Sat" else "sunday"))
                out.setdefault(row["service_id"], set()).add(day)
    return {k: sorted(v) for k, v in out.items()}


def _load_trips(db):
    # resolve the SQLite file from the app's engine so the MTA_DB_PATH test
    # hook (scratch database copies) stays honored by the bulk loader too
    url = str(db.engine.url)
    if url.startswith("sqlite:///" ):
        db_file = url[len("sqlite:///"):]
    else:
        db_file = str(BASE_DIR / "instance" / "mta.db")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("DELETE FROM stop_times")
    cur.execute("DELETE FROM trips")
    conn.commit()

    for which, agency in (("subway", "subway"), ("lirr", "lirr"),
                          ("metro_north", "mnr")):
        day_types = _service_day_types(which)
        with zipfile.ZipFile(GTFS / f"{which}.zip") as z:
            trips_reader = csv.DictReader(
                z.read("trips.txt").decode("utf-8-sig").splitlines())
            stop_times_reader = csv.DictReader(
                z.read("stop_times.txt").decode("utf-8-sig").splitlines())
            trips = list(trips_reader)
            trip_rows = []
            for t in trips:
                days = day_types.get(t["service_id"], ["weekday"])
                for day in days:
                    trip_rows.append((
                        f"{t['trip_id']}@{day}", agency, t["route_id"],
                        t.get("trip_headsign", ""), int(t.get("direction_id") or 0),
                        day, int(t.get("peak_offpeak") or 0) == 1))
            cur.executemany(
                "INSERT INTO trips (gtfs_trip_id, agency, route_id, headsign, "
                "direction_id, day_type, peak) VALUES (?, ?, ?, ?, ?, ?, ?)",
                trip_rows)
            cur.execute("SELECT id, gtfs_trip_id FROM trips")
            pk_by_gtfs = {}
            for pk, gtfs_id in cur.fetchall():
                # gtfs ids carry a @day suffix for weekend-duplicated trips;
                # stop_times reference the raw GTFS trip id
                pk_by_gtfs.setdefault(gtfs_id.rsplit("@", 1)[0], []).append(pk)

            def to_seconds(t):
                h, m, s = t.split(":")
                return int(h) * 3600 + int(m) * 60 + int(s)

            batch = []
            for st in stop_times_reader:
                pks = pk_by_gtfs.get(st["trip_id"], [])
                for pk in pks:
                    batch.append((pk, st["stop_id"], int(st["stop_sequence"]),
                                  to_seconds(st["arrival_time"]),
                                  to_seconds(st["departure_time"])))
                if len(batch) >= 50000:
                    cur.executemany(
                        "INSERT INTO stop_times (trip_pk, stop_id, stop_sequence, "
                        "arrival, departure) VALUES (?, ?, ?, ?, ?)", batch)
                    batch = []
            if batch:
                cur.executemany(
                    "INSERT INTO stop_times (trip_pk, stop_id, stop_sequence, "
                    "arrival, departure) VALUES (?, ?, ?, ?, ?)", batch)
    conn.commit()
    cur.execute("CREATE INDEX IF NOT EXISTS ix_stop_times_stop_departure "
                "ON stop_times (stop_id, departure)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_stop_times_trip "
                "ON stop_times (trip_pk, stop_sequence)")
    cur.execute("ANALYZE")
    conn.close()


# ---------------------------------------------------------------------------
# Benchmark users
# ---------------------------------------------------------------------------

def _seed_user(db, email, username, display_name, omny_serial, favorites,
               subscriptions, taps, claims, cases, aar):
    db.session.execute(db.text(
        "INSERT INTO users (email, username, display_name, password_hash, omny_serial) "
        "VALUES (:e, :u, :d, :p, :o)"),
        {"e": email, "u": username, "d": display_name,
         "p": BENCHMARK_PASSWORD_DIGEST, "o": omny_serial})
    row = db.session.execute(db.text("SELECT id FROM users WHERE email = :e"),
                             {"e": email}).fetchone()
    uid = row[0]
    for stype, sid in favorites:
        db.session.execute(db.text(
            "INSERT INTO favorites (user_id, service_type, service_id) "
            "VALUES (:u, :t, :s)"), {"u": uid, "t": stype, "s": sid})
    for stype, sid in subscriptions:
        db.session.execute(db.text(
            "INSERT INTO alert_subscriptions (user_id, email, service_type, service_id) "
            "VALUES (:u, :e, :t, :s)"), {"u": uid, "e": email, "t": stype, "s": sid})
    for tapped_at, route, fare, express, device in taps:
        db.session.execute(db.text(
            "INSERT INTO omny_taps (user_id, tapped_at, route, fare, express, device) "
            "VALUES (:u, :t, :r, :f, :x, :d)"),
            {"u": uid, "t": tapped_at, "r": route, "f": fare, "x": int(express),
             "d": device})
    for c in claims:
        db.session.execute(db.text(
            "INSERT INTO lost_claims (claim_ref, user_id, agency, date_lost, "
            "line_route, station, item_type, item_description, contact_name, "
            "contact_email, contact_phone, status) VALUES "
            "(:ref, :u, :ag, :d, :lr, :st, :it, :id, :cn, :ce, :cp, :s)"),
            {"ref": c["ref"], "u": uid, "ag": c["agency"], "d": c["date_lost"],
             "lr": c["line_route"], "st": c["station"], "it": c["item_type"],
             "id": c["item_description"], "cn": c["contact_name"],
             "ce": c["contact_email"], "cp": c.get("contact_phone", ""), "s": c["status"]})
    for c in cases:
        db.session.execute(db.text(
            "INSERT INTO feedback_cases (case_ref, user_id, category, subject, "
            "message, status) VALUES (:ref, :u, :cat, :sub, :msg, :s)"),
            {"ref": c["ref"], "u": uid, "cat": c["category"], "sub": c["subject"],
             "msg": c["message"], "s": c["status"]})
    for t in aar:
        db.session.execute(db.text(
            "INSERT INTO aar_trips (trip_ref, user_id, pickup_address, "
            "destination_address, trip_date, pickup_time, passengers, mobility_aid, "
            "purpose, status) VALUES (:ref, :u, :pk, :ds, :d, :t, :n, :m, :p, :s)"),
            {"ref": t["ref"], "u": uid, "pk": t["pickup"], "ds": t["destination"],
             "d": t["date"], "t": t["time"], "n": t.get("passengers", 1),
             "m": t.get("mobility_aid", ""), "p": t.get("purpose", ""),
             "s": t["status"]})


def seed_benchmark_users():
    from app import User  # noqa: PLC0415
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    real_db = _get_db()

    D = datetime.datetime

    _seed_user(
        real_db, "alice.j@test.com", "alice_j", "Alice Johnson", "OMNY-4A21B9C3",
        favorites=[("subway", "2"), ("subway", "5"), ("rail", "Babylon Branch")],
        subscriptions=[("subway", "2"), ("subway", "5")],
        taps=[
            (D(2026, 9, 21, 8, 12), "Subway 2", 3.00, False, "OMNY Card"),
            (D(2026, 9, 21, 18, 40), "Subway 2", 3.00, False, "OMNY Card"),
            (D(2026, 9, 22, 8, 5), "Subway 2", 3.00, False, "OMNY Card"),
            (D(2026, 9, 22, 18, 55), "Bus M15", 3.00, False, "OMNY Card"),
            (D(2026, 9, 22, 19, 30), "Subway 5", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 8, 2), "Subway 2", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 9, 15), "Subway 5", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 18, 48), "Subway 2", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 19, 20), "Subway 5", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 19, 55), "Bus M15", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 20, 30), "Subway 2", 3.00, False, "OMNY Card"),
        ],
        claims=[{
            "ref": "LF-26094217", "agency": "nyct", "date_lost": "2026-09-22",
            "line_route": "2 train", "station": "Flatbush Av-Brooklyn College",
            "item_type": "Backpack", "item_description":
                "Navy blue JanSport backpack with a water bottle in the side pocket "
                "and a gray laptop sleeve inside.",
            "contact_name": "Alice Johnson", "contact_email": "alice.j@test.com",
            "contact_phone": "555-0142", "status": "Received",
        }],
        cases=[{
            "ref": "CS-26093118", "category": "Elevator or escalator outage",
            "subject": "Elevator out at 34 St-Penn Station",
            "message": "The A/C/E elevator at 34 St-Penn Station has been out since "
                       "Monday morning. Please post an update.",
            "status": "Open",
        }],
        aar=[],
    )

    _seed_user(
        real_db, "bob.c@test.com", "bob_c", "Bob Chen", "OMNY-77D0E5A2",
        favorites=[("subway", "A"), ("subway", "E"), ("subway", "7")],
        subscriptions=[("subway", "A"), ("rail", "Hudson")],
        taps=[
            (D(2026, 9, 21, 7, 45), "Subway E", 3.00, False, "Credit card"),
            (D(2026, 9, 21, 17, 50), "Subway A", 3.00, False, "Credit card"),
            (D(2026, 9, 22, 7, 40), "Subway E", 3.00, False, "Credit card"),
            (D(2026, 9, 22, 17, 55), "Subway A", 3.00, False, "Credit card"),
            (D(2026, 9, 22, 19, 5), "Subway 7", 3.00, False, "Credit card"),
            (D(2026, 9, 23, 7, 38), "Subway E", 3.00, False, "Credit card"),
            (D(2026, 9, 23, 8, 30), "Bus Q58", 3.00, False, "Credit card"),
            (D(2026, 9, 23, 17, 42), "Subway A", 3.00, False, "Credit card"),
            (D(2026, 9, 23, 19, 0), "Bus X27", 7.25, True, "Credit card"),
        ],
        claims=[{
            "ref": "LF-26095803", "agency": "lirr", "date_lost": "2026-09-20",
            "line_route": "Babylon Branch", "station": "Penn Station",
            "item_type": "Umbrella", "item_description":
                "Black compact umbrella with a wooden handle, left on the overhead rack.",
            "contact_name": "Bob Chen", "contact_email": "bob.c@test.com",
            "contact_phone": "555-0177", "status": "In Review",
        }],
        cases=[{
            "ref": "CS-26094402", "category": "Train or bus service",
            "subject": "E train skipped my stop",
            "message": "The 8:05 a.m. E train skipped 23 St-Ely Av on Tuesday. "
                       "Any reason for the skipped stop?",
            "status": "Resolved",
        }],
        aar=[],
    )

    _seed_user(
        real_db, "carol.d@test.com", "carol_d", "Carol Davis", "OMNY-9B33C1F7",
        favorites=[("subway", "7"), ("subway", "F"), ("rail", "Ronkonkoma Branch")],
        subscriptions=[("subway", "7"), ("subway", "F")],
        taps=[
            (D(2026, 9, 21, 9, 20), "Subway 7", 3.00, False, "OMNY Card"),
            (D(2026, 9, 21, 16, 40), "Subway F", 3.00, False, "OMNY Card"),
            (D(2026, 9, 22, 9, 15), "Subway 7", 3.00, False, "OMNY Card"),
            (D(2026, 9, 22, 16, 45), "Subway F", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 9, 10), "Subway 7", 3.00, False, "OMNY Card"),
            (D(2026, 9, 23, 16, 50), "Subway F", 3.00, False, "OMNY Card"),
        ],
        claims=[{
            "ref": "LF-26096625", "agency": "mnr", "date_lost": "2026-09-18",
            "line_route": "Hudson Line", "station": "Grand Central",
            "item_type": "Jacket", "item_description":
                "Beige rain jacket, size medium, left on the 5:42 p.m. Hudson Line train.",
            "contact_name": "Carol Davis", "contact_email": "carol.d@test.com",
            "contact_phone": "555-0129", "status": "Matched - Pickup Pending",
        }],
        cases=[],
        aar=[{
            "ref": "AAR-26093354", "pickup": "120-55 Queens Blvd, Kew Gardens, NY",
            "destination": "Jamaica Center-Parsons/Archer station",
            "date": "2026-09-25", "time": "10:15", "passengers": 1,
            "mobility_aid": "Walker", "purpose": "Medical appointment",
            "status": "Scheduled",
        }, {
            "ref": "AAR-26092817", "pickup": "120-55 Queens Blvd, Kew Gardens, NY",
            "destination": "Queens Center Mall, Elmhurst",
            "date": "2026-09-19", "time": "13:00", "passengers": 1,
            "mobility_aid": "Walker", "purpose": "Shopping", "status": "Completed",
        }],
    )

    _seed_user(
        real_db, "david.k@test.com", "david_k", "David Kim", "OMNY-2E54A8D0",
        favorites=[("subway", "F"), ("subway", "G"), ("rail", "Hudson")],
        subscriptions=[("subway", "G"), ("rail", "Hudson")],
        taps=[
            (D(2026, 9, 21, 8, 30), "Subway G", 3.00, False, "Smartphone"),
            (D(2026, 9, 21, 18, 20), "Subway F", 3.00, False, "Smartphone"),
            (D(2026, 9, 22, 8, 25), "Subway G", 3.00, False, "Smartphone"),
            (D(2026, 9, 22, 18, 15), "Subway F", 3.00, False, "Smartphone"),
            (D(2026, 9, 23, 8, 28), "Subway G", 3.00, False, "Smartphone"),
            (D(2026, 9, 23, 12, 5), "Bus Bx12", 3.00, False, "Smartphone"),
            (D(2026, 9, 23, 18, 18), "Subway F", 3.00, False, "Smartphone"),
        ],
        claims=[],
        cases=[{
            "ref": "CS-26095281", "category": "Station or facility",
            "subject": "Lighting out in the G line mezzanine",
            "message": "Several lights are out in the 21 St-Queensbridge mezzanine "
                       "on the G line. It is very dark in the evenings.",
            "status": "Open",
        }],
        aar=[{
            "ref": "AAR-26094599", "pickup": "45-10 Court Sq, Long Island City, NY",
            "destination": "Mount Sinai Queens, 25-10 30th Ave, Astoria",
            "date": "2026-09-26", "time": "9:00", "passengers": 2,
            "mobility_aid": "Power wheelchair", "purpose": "Medical appointment",
            "status": "Scheduled",
        }],
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def seed_database():
    from app import Station  # noqa: PLC0415
    if Station.query.count() > 0:
        return
    real_db = _get_db()
    _load_reference(real_db)
    _load_alerts(real_db)
    _load_elevators(real_db)
    _load_fares(real_db)
    _load_content(real_db)
    _load_trips(real_db)


def _get_db():
    """Lazily resolve the SQLAlchemy db from the app module."""
    global db
    if db is None:
        from app import db as app_db  # noqa: PLC0415
        db = app_db
    return db


if __name__ == "__main__":
    import os
    import shutil
    import sys
    # The Dockerfile seed gate wipes instance/ and instance_seed/ before
    # rerunning this script, so the instance directory must be (re)created
    # here before the app engine opens instance/mta.db (same contract as the
    # imgur / instructure build-generated seeds).
    os.makedirs(BASE_DIR / "instance", exist_ok=True)
    sys.path.insert(0, str(BASE_DIR))
    from app import app, db as app_db
    with app.app_context():
        app_db.create_all()
        seed_database()
        seed_benchmark_users()
    seed_dir = BASE_DIR / "instance_seed"
    seed_dir.mkdir(exist_ok=True)
    shutil.copyfile(BASE_DIR / "instance" / "mta.db", seed_dir / "mta.db")
    print("seed complete; copied instance/mta.db to instance_seed/mta.db")
