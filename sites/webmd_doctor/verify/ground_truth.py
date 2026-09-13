#!/usr/bin/env python3
"""Re-derive every WebMD Doctor task target from a supplied initial SQLite snapshot.

``task_ground_truth(db, n)`` selects the target exactly the way the task text does
(specialty + city, filters, saved list, hospital roster, award class, ...) using
plain SQL and the same haversine formula as the site, then asserts the result is
the target hardcoded in ``verify_N.py``. Any disagreement raises ``ValueError``
and the verifier fails closed (``snapshot_contract_invalid``): a re-frozen seed
can never silently turn a verifier into a false PASS or a false FAIL.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any, Callable

NEWARK = (39.6837, -75.7497)
SPECIALTY = {
    "dermatology": 1, "cardiovascular-disease": 2, "family-medicine": 3, "neurology": 4,
    "orthopedic-surgery": 5, "gastroenterology": 6, "psychiatry": 7, "obstetrics-gynecology": 8,
    "pediatrics": 9, "internal-medicine": 10,
}
CITY = {"newark": 1, "bear": 2, "wilmington": 3, "elkton": 4, "salem": 5, "west-chester": 6, "media": 7, "baltimore": 8}
BCBS_INSURER_ID = 4

# The slug(s) each verifier hardcodes. The derivation below must reproduce them.
EXPECTED_SLUGS: dict[int, str | tuple[str, str]] = {
    0: "jonah-dimitriou-c4ce067c",
    1: "julian-zamora-d412b77d",
    2: "ruth-thackeray-45234b97",
    3: "mateo-alvarado-f727bd61",
    4: "charles-villanueva-13e969b2",
    5: "caroline-danforth-7093653d",
    6: "fatima-jensen-e5a26d53",
    7: "lillian-acosta-4a89e15e",
    8: "adrian-navarro-b338ac81",
    9: "nicole-dubois-243c6e66",
    10: "veronica-nwachukwu-71051d38",
    11: "sean-blackwood-45e84c50",
    12: "joseph-iyer-29b88273",
    13: ("emerson-huang-f6afead5", "gregory-greenwood-34670192"),
    14: ("arjun-bouchard-f3c85053", "colin-ellery-640b0a4a"),
    15: "linda-merriweather-378753c8",
    16: "anita-castellano-14da1f29",
    17: "sarah-keller-f85bed81",
    18: "tariq-huang-c8120504",
    19: "monica-carrington-62f5d8a2",
}

# Every answer fact and stateful id each verifier hardcodes. ``_expect_facts``
# re-derives all of them from the supplied snapshot and fails closed on any
# disagreement, so a re-frozen seed cannot silently invalidate a hardcoded
# school, year, NPI, phone, hours, institution, criterion, date, rating,
# website, user/doctor/location id or reference input. Keeping the table here
# (next to EXPECTED_SLUGS) means the contract covers facts, not only targets.
EXPECTED_FACTS: dict[int, dict[str, Any]] = {
    0: {"school": "Chesapeake Bay School of Medicine", "graduation_year": 2004},
    1: {"npi": "1025647698", "languages": ["English", "Tagalog", "Portuguese"]},
    2: {"phone": "(302) 555-1542", "saturday": ["8:00 am", "1:00 pm"]},
    3: {"office_name": "Providence Road Medical Group - Professional Plaza",
        "street": "3543 Baltimore Pike Bldg B"},
    4: {"board": "American Board of Orthopaedic Surgery", "cert_year": 2014,
        "residency": "Blue Ridge Regional Medical Center"},
    5: {"more_than_most": "Acid Reflux (GERD)", "first_top20": "Anemia"},
    6: {"oldest_date": "2022-11-02", "oldest_rating": 4, "review_count": 7},
    7: {"criterion": 6, "wait_minutes": 15},  # criterion 6 == "Staff was courteous"
    8: {"residency": "Piedmont Atlantic Hospital"},
    9: {"school": "Tuckahoe College of Osteopathic Medicine", "cert_year": 2024},
    10: {"wait_minutes": 25, "residency": "Rappahannock University Hospital"},
    11: {"npi": "1056532702", "residency": "Elk Neck Medical Center"},
    12: {"fellowship": "Allegheny Ridge Medical Center", "fellowship_year": 1987},
    13: {"earlier": "emerson-huang-f6afead5", "graduation_year": 1992},
    14: {"more_recent": "arjun-bouchard-f3c85053", "cert_year": 2004},
    15: {"website": "https://www.rosetreeorthopedicssportsmedicine.example",
         "saturday": ["9:00 am", "2:00 pm"]},
    16: {},
    17: {"location_id": 32},
    18: {},
    19: {"npi": "1074536057"},
}


def _observed_facts(n: int, fact: dict[str, Any]) -> dict[str, Any]:
    """Project a derived task fact onto the EXPECTED_FACTS keys for comparison."""
    out: dict[str, Any] = {}
    get = fact.get
    if n == 0:
        out = {"school": get("school"), "graduation_year": get("graduation_year")}
    elif n == 1:
        out = {"npi": get("npi"), "languages": list(get("languages") or [])}
    elif n == 2:
        out = {"phone": get("phone"), "saturday": list(get("saturday") or [])}
    elif n == 3:
        office = get("other_office") or {}
        out = {"office_name": office.get("name"), "street": office.get("street")}
    elif n == 4:
        out = {"board": get("board"), "cert_year": get("cert_year"), "residency": get("residency")}
    elif n == 5:
        out = {"more_than_most": get("more_than_most"), "first_top20": get("first_top20")}
    elif n == 6:
        out = {"oldest_date": str(get("oldest_date")), "oldest_rating": get("oldest_rating"),
               "review_count": get("review_count")}
    elif n == 7:
        out = {"criterion": get("criterion"), "wait_minutes": get("wait_minutes")}
    elif n == 8:
        out = {"residency": get("residency")}
    elif n == 9:
        out = {"school": get("school"), "cert_year": get("cert_year")}
    elif n == 10:
        out = {"wait_minutes": get("wait_minutes"), "residency": get("residency")}
    elif n == 11:
        out = {"npi": get("npi"), "residency": get("residency")}
    elif n == 12:
        fellowship = get("fellowship") or {}
        out = {"fellowship": fellowship.get("institution"), "fellowship_year": fellowship.get("year")}
    elif n == 13:
        earlier = get("earlier") or {}
        out = {"earlier": earlier.get("slug"), "graduation_year": get("graduation_year")}
    elif n == 14:
        recent = get("more_recent") or {}
        out = {"more_recent": recent.get("slug"), "cert_year": get("cert_year")}
    elif n == 15:
        out = {"website": get("website"), "saturday": list(get("saturday") or [])}
    elif n == 17:
        out = {"location_id": get("location_id")}
    elif n == 19:
        out = {"npi": get("npi")}
    return out


def _expect_facts(n: int, fact: dict[str, Any]) -> None:
    expected = EXPECTED_FACTS.get(n, {})
    observed = _observed_facts(n, fact)
    for key, want in expected.items():
        got = observed.get(key)
        if isinstance(want, list):
            if sorted(str(item) for item in want) != sorted(str(item) for item in (got or [])):
                raise ValueError(f"task {n} fact {key!r} drifted: expected={want!r}, derived={got!r}")
        elif str(got) != str(want):
            raise ValueError(f"task {n} fact {key!r} drifted: expected={want!r}, derived={got!r}")


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _one(rows: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"{description} must be unique; observed {len(rows)} rows: {[row.get('slug') for row in rows]}")
    return rows[0]


def _extreme(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any], maximum: bool, description: str) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"{description} has no candidates")
    value = (max if maximum else min)(key(row) for row in rows)
    return _one([row for row in rows if key(row) == value], description)


def _doctors(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every doctor joined with the primary location (the row the search and city pages use)."""
    rows = connection.execute(
        "SELECT d.*, l.id AS location_id, l.city_id, l.lat AS loc_lat, l.lon AS loc_lon, l.medicaid AS loc_medicaid, "
        "l.practice_id, l.phone AS loc_phone, l.sat_open, l.sat_close "
        "FROM doctors d JOIN locations l ON l.doctor_id = d.id AND l.is_primary = 1 ORDER BY d.id"
    ).fetchall()
    output = [dict(row) for row in rows]
    for row in output:
        row["distance"] = haversine_miles(*NEWARK, row["loc_lat"], row["loc_lon"])
    return output


def _has_specialty(row: dict[str, Any], specialty_id: int) -> bool:
    return row["primary_specialty_id"] == specialty_id or row["secondary_specialty_id"] == specialty_id


def _insurer_ids(connection: sqlite3.Connection, doctor_id: int) -> set[int]:
    return {
        int(r[0]) for r in connection.execute(
            "SELECT p.insurer_id FROM doctor_insurances di JOIN insurance_plans p ON p.id = di.plan_id WHERE di.doctor_id = ?",
            (doctor_id,),
        )
    }


def _education(connection: sqlite3.Connection, doctor_id: int, kind: str) -> list[dict[str, Any]]:
    return [dict(r) for r in connection.execute("SELECT * FROM education WHERE doctor_id = ? AND kind = ? ORDER BY id", (doctor_id, kind))]


def _certifications(connection: sqlite3.Connection, doctor_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in connection.execute("SELECT * FROM certifications WHERE doctor_id = ? ORDER BY id", (doctor_id,))]


def _locations(connection: sqlite3.Connection, doctor_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in connection.execute("SELECT * FROM locations WHERE doctor_id = ? ORDER BY is_primary DESC, id", (doctor_id,))]


def _user_id(connection: sqlite3.Connection, email: str) -> int:
    row = connection.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
    if row is None:
        raise ValueError(f"missing benchmark user {email}")
    return int(row[0])


def _named(doctors: list[dict[str, Any]], first: str, last: str, specialty: str, city: str) -> dict[str, Any]:
    rows = [
        row for row in doctors
        if row["first_name"] == first and row["last_name"] == last
        and row["primary_specialty_id"] == SPECIALTY[specialty] and row["city_id"] == CITY[city]
    ]
    return _one(rows, f"{first} {last} ({specialty}, {city})")


def _expect(slugs: Any, task_number: int) -> None:
    expected = EXPECTED_SLUGS[task_number]
    observed = tuple(slugs) if isinstance(slugs, (list, tuple)) else slugs
    if isinstance(expected, tuple):
        if set(observed) != set(expected):
            raise ValueError(f"task {task_number} targets differ: expected={expected}, derived={observed}")
    elif observed != expected:
        raise ValueError(f"task {task_number} target differs: expected={expected!r}, derived={observed!r}")


def task_ground_truth(db_path: str | Path, task_number: int) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        return _derive(connection, task_number)
    finally:
        connection.close()


def _derive(c: sqlite3.Connection, n: int) -> dict[str, Any]:
    doctors = _doctors(c)
    fact: dict[str, Any] = {"task": n}

    if n == 0:
        t = _named(doctors, "Jonah", "Dimitriou", "dermatology", "newark")
        fact.update(target=t, school=t["medical_school"], graduation_year=t["graduation_year"])
    elif n == 1:
        t = _named(doctors, "Julian", "Zamora", "cardiovascular-disease", "wilmington")
        languages = [r[0] for r in c.execute("SELECT language FROM doctor_languages WHERE doctor_id=? ORDER BY position", (t["id"],))]
        fact.update(target=t, npi=t["npi"], languages=languages)
    elif n == 2:
        t = _named(doctors, "Ruth", "Thackeray", "family-medicine", "newark")
        if not t["sat_open"]:
            raise ValueError("task 2 primary office is closed on Saturday")
        fact.update(target=t, phone=t["loc_phone"], saturday=(t["sat_open"], t["sat_close"]))
    elif n == 3:
        t = _named(doctors, "Mateo", "Alvarado", "neurology", "west-chester")
        locations = _locations(c, t["id"])
        if len(locations) != 2:
            raise ValueError(f"task 3 needs exactly two offices; observed {len(locations)}")
        fact.update(target=t, other_office=locations[1])
    elif n == 4:
        t = _named(doctors, "Charles", "Villanueva", "orthopedic-surgery", "elkton")
        certs = _certifications(c, t["id"])
        residency = _education(c, t["id"], "Residency")
        if len(certs) != 1 or len(residency) != 1:
            raise ValueError("task 4 needs exactly one certification and one residency row")
        fact.update(target=t, board=certs[0]["issuer"], cert_year=certs[0]["year"], residency=residency[0]["institution"])
    elif n == 5:
        t = _named(doctors, "Caroline", "Danforth", "gastroenterology", "newark")
        rows = [dict(r) for r in c.execute(
            "SELECT dc.tier, cd.name FROM doctor_conditions dc JOIN conditions cd ON cd.id = dc.condition_id "
            "WHERE dc.doctor_id = ? ORDER BY dc.position", (t["id"],))]
        top5 = [r for r in rows[:5] if r["tier"] == "More Than Most"]
        if len(top5) != 1 or len(rows) < 6:
            raise ValueError("task 5 needs exactly one More Than Most condition among the first five and a sixth row")
        fact.update(target=t, more_than_most=top5[0]["name"], first_top20=rows[5]["name"])
    elif n == 6:
        t = _named(doctors, "Fatima", "Jensen", "psychiatry", "media")
        reviews = [dict(r) for r in c.execute("SELECT rating, review_date FROM reviews WHERE doctor_id=? ORDER BY review_date, id", (t["id"],))]
        if len(reviews) < 6:
            raise ValueError("task 6 needs a second review page (more than five reviews)")
        if len(reviews) > 1 and reviews[0]["review_date"] == reviews[1]["review_date"]:
            raise ValueError("task 6 oldest review date is tied")
        fact.update(target=t, oldest_date=reviews[0]["review_date"], oldest_rating=reviews[0]["rating"], review_count=len(reviews))
    elif n == 7:
        t = _named(doctors, "Lillian", "Acosta", "obstetrics-gynecology", "salem")
        rows = [dict(r) for r in c.execute("SELECT criterion, needs_improvement FROM doctor_perspectives WHERE doctor_id=?", (t["id"],))]
        worst = _extreme(rows, lambda r: r["needs_improvement"], True, "task 7 most needs-improvement votes")
        fact.update(target=t, criterion=worst["criterion"], wait_minutes=t["avg_wait_minutes"])
    elif n == 8:
        alice = _user_id(c, "alice.j@test.com")
        saved = {int(r[0]) for r in c.execute("SELECT doctor_id FROM saved_providers WHERE user_id=?", (alice,))}
        derms = [row for row in doctors if row["id"] in saved and row["primary_specialty_id"] == SPECIALTY["dermatology"]]
        t = _one(derms, "task 8 alice's saved Dermatologist")
        residency = _education(c, t["id"], "Residency")
        fact.update(target=t, user_id=alice, residency=_one(residency, "task 8 residency")["institution"])
    elif n == 9:
        rows = [
            row for row in doctors
            if _has_specialty(row, SPECIALTY["dermatology"]) and row["gender"] == "f" and row["accepting_new_patients"]
            and row["distance"] <= 40 and BCBS_INSURER_ID in _insurer_ids(c, row["id"])
        ]
        if len(rows) < 6:
            raise ValueError(f"task 9 filtered set too small: {len(rows)}")
        t = _one([row for row in rows if row["years_experience"] < 5], "task 9 under-5-years candidate")
        certs = _certifications(c, t["id"])
        fact.update(target=t, candidates=rows, school=t["medical_school"], cert_year=_one(certs, "task 9 certification")["year"])
    elif n == 10:
        rows = [
            row for row in doctors
            if _has_specialty(row, SPECIALTY["psychiatry"]) and row["loc_medicaid"] and row["avg_rating"] is not None
            and row["avg_rating"] >= 4 and row["distance"] <= 40
        ]
        t = _one([row for row in rows if row["virtual_visit"]], "task 10 virtual-visit candidate")
        residency = _education(c, t["id"], "Residency")
        fact.update(target=t, candidates=rows, wait_minutes=t["avg_wait_minutes"], residency=_one(residency, "task 10 residency")["institution"])
    elif n == 11:
        rows = [row for row in doctors if _has_specialty(row, SPECIALTY["family-medicine"]) and row["distance"] <= 10]
        rows.sort(key=lambda row: (-row["ratings_count"], row["id"]))
        if len(rows) < 3 or len({row["ratings_count"] for row in rows[:3]}) != 3:
            raise ValueError("task 11 needs three distinct ratings counts at the top of the 10-mile list")
        t = rows[1]
        residency = _education(c, t["id"], "Residency")
        fact.update(target=t, ranked=rows, npi=t["npi"], residency=_one(residency, "task 11 residency")["institution"])
    elif n == 12:
        rows = [
            row for row in doctors
            if _has_specialty(row, SPECIALTY["cardiovascular-disease"]) and row["city_id"] == CITY["west-chester"]
            and row["avg_rating"] is not None and row["avg_rating"] >= 4
        ]
        t = _one([row for row in rows if row["gender"] == "m"], "task 12 only male candidate")
        fellowship = _education(c, t["id"], "Fellowship")
        fact.update(target=t, candidates=rows, fellowship=_one(fellowship, "task 12 fellowship"))
    elif n == 13:
        a = _named(doctors, "Gregory", "Greenwood", "dermatology", "wilmington")
        b = _named(doctors, "Emerson", "Huang", "dermatology", "wilmington")
        for row in (a, b):
            if BCBS_INSURER_ID not in _insurer_ids(c, row["id"]):
                raise ValueError(f"task 13 candidate {row['slug']} does not accept the named insurer")
        earlier = _extreme([a, b], lambda row: row["graduation_year"], False, "task 13 earlier graduate")
        fact.update(targets=(a, b), earlier=earlier, graduation_year=earlier["graduation_year"])
    elif n == 14:
        hospital = c.execute("SELECT id, slug, name FROM hospitals WHERE slug='christina-creek-medical-center'").fetchone()
        if hospital is None:
            raise ValueError("task 14 hospital is missing")
        rows = [row for row in doctors if row["hospital_id"] == hospital["id"] and row["primary_specialty_id"] == SPECIALTY["psychiatry"]]
        if len(rows) != 2:
            raise ValueError(f"task 14 needs exactly two Psychiatrists at the hospital; observed {len(rows)}")
        for row in rows:
            row["cert_year"] = _one(_certifications(c, row["id"]), f"task 14 certification {row['slug']}")["year"]
        recent = _extreme(rows, lambda row: row["cert_year"], True, "task 14 more recent certification")
        fact.update(targets=tuple(rows), hospital=dict(hospital), more_recent=recent, cert_year=recent["cert_year"])
    elif n == 15:
        winners = {int(r[0]) for r in c.execute("SELECT doctor_id FROM awards WHERE award_class='Patient'")}
        rows = [row for row in doctors if row["id"] in winners and row["primary_specialty_id"] == SPECIALTY["orthopedic-surgery"] and row["city_id"] == CITY["media"]]
        t = _one(rows, "task 15 Patient's Choice orthopedic surgeon in Media")
        practice = c.execute("SELECT * FROM practices WHERE id=?", (t["practice_id"],)).fetchone()
        if practice is None or not practice["sat_open"]:
            raise ValueError("task 15 practice is missing or closed on Saturday")
        fact.update(target=t, practice=dict(practice), website=practice["website"], saturday=(practice["sat_open"], practice["sat_close"]))
    elif n == 16:
        t = _named(doctors, "Anita", "Castellano", "pediatrics", "newark")
        bob = _user_id(c, "bob.c@test.com")
        if c.execute("SELECT 1 FROM saved_providers WHERE user_id=? AND doctor_id=?", (bob, t["id"])).fetchone():
            raise ValueError("task 16 target is already saved by bob in the initial snapshot")
        fact.update(target=t, user_id=bob)
    elif n == 17:
        t = _named(doctors, "Sarah", "Keller", "cardiovascular-disease", "newark")
        if t["profile_type"] != "Enhanced":
            raise ValueError("task 17 target must be Enhanced (bookable)")
        offices = [row for row in _locations(c, t["id"]) if row["name"] == "Riverfront Heart & Vascular - Wellness Center"]
        office = _one(offices, "task 17 named office")
        carol = _user_id(c, "carol.d@test.com")
        if c.execute("SELECT 1 FROM appointment_requests WHERE user_id=? AND doctor_id=?", (carol, t["id"])).fetchone():
            raise ValueError("task 17 initial snapshot already has a carol/keller request")
        fact.update(target=t, user_id=carol, location_id=office["id"])
    elif n == 18:
        t = _named(doctors, "Tariq", "Huang", "dermatology", "elkton")
        david = _user_id(c, "david.k@test.com")
        if c.execute("SELECT 1 FROM user_reviews WHERE user_id=? AND doctor_id=?", (david, t["id"])).fetchone():
            raise ValueError("task 18 initial snapshot already has a david review for the target")
        fact.update(target=t, user_id=david)
    elif n == 19:
        rows = [row for row in doctors if _has_specialty(row, SPECIALTY["neurology"]) and row["virtual_visit"] and row["distance"] <= 40]
        t = _one([row for row in rows if row["first_name"] == "Monica" and row["last_name"] == "Carrington"], "task 19 Monica Carrington")
        if len(rows) < 6:
            raise ValueError(f"task 19 filtered set too small: {len(rows)}")
        fact.update(target=t, candidates=rows, npi=t["npi"])
    else:
        raise ValueError(f"unsupported WebMD Doctor task {n}")

    if "targets" in fact:
        _expect([row["slug"] for row in fact["targets"]], n)
    else:
        _expect(fact["target"]["slug"], n)
    _expect_facts(n, fact)
    return fact


def all_ground_truth(db_path: str | Path) -> dict[int, dict[str, Any]]:
    return {number: task_ground_truth(db_path, number) for number in range(20)}


if __name__ == "__main__":  # pragma: no cover - manual inspection
    import json
    import sys

    facts = all_ground_truth(sys.argv[1])
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("candidates", "ranked")} for k, v in facts.items()}, indent=1, default=str))
