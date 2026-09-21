"""End-to-end positive and adversarial tests for every Compass verifier."""
from __future__ import annotations

import json
import sqlite3
import sys
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlencode

import bcrypt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as v
from test_support import copied_databases, make_run, next_id, temporary_case

TASKS = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
READ_ONLY = {0, 1, 2, 3, 11, 12, 13, 16, 17}


def detail(listing):
    return v.snapshot_detail_path(listing)


def agent(before, listing):
    return before["agents"][listing["agent_id"]]


def positive_case(task, initial, after):
    before = v.snapshot(initial)
    target = v.task_target(task, before) if task in {0, 1, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17} else None
    with sqlite3.connect(after) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if task == 4:
            uid = next_id(connection, "users")
            password = bcrypt.hashpw(b"compass-test-1234", bcrypt.gensalt(rounds=4)).decode()
            connection.execute("INSERT INTO users(id,email,password_hash,name,phone,city,state,budget_min,budget_max,beds_min,preferred_property_types,move_timeline,has_agent,receive_alerts,agent_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, "taylor.reed+test@example.com", password, "Taylor Reed", "", "", "", 0, 0, 0, "[]", "", 0, 1, None, "2026-09-08 12:00:00"))
            connection.execute("INSERT INTO saved_homes(id,user_id,listing_id,note,saved_at) VALUES(?,?,?,?,?)", (next_id(connection, "saved_homes"), uid, target["id"], "", "2026-09-08 12:01:00"))
        elif task == 5:
            uid = v.user_id(before, "alice.j@test.com")
            connection.execute("UPDATE users SET phone=? WHERE id=?", ("(415) 555-0199", uid))
        elif task == 6:
            uid = v.user_id(before, "carol.lee@test.com")
            connection.execute("INSERT INTO tours(id,user_id,listing_id,requested_date,requested_time,tour_type,contact_phone,notes,status,requested_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (next_id(connection, "tours"), uid, target["id"], "2026-07-12", "11:00 AM", "in-person", before["users"][uid]["phone"], "", "requested", "2026-09-08 12:00:00"))
        elif task in {7, 14}:
            uid = v.user_id(before, "david.kim@test.com")
            cid = next_id(connection, "collections")
            if task == 7:
                members = [v.listing_named(before, "3305 Dolphin Drive")["id"], v.listing_named(before, "1036 Liberty Park Drive, Unit 38A")["id"]]
                name, token = "Austin top picks", "fixture-token-123"
            else:
                members = [target["id"]]
                name, token = "Austin garage picks", "garage-token-123"
            connection.execute("INSERT INTO collections(id,user_id,name,description,listing_ids_json,share_token,created_at) VALUES(?,?,?,?,?,?,?)", (cid, uid, name, "", json.dumps(members), token, "2026-09-08 12:00:00"))
        elif task == 10:
            uid = v.user_id(before, "alice.j@test.com")
            criteria = {"city": "Boston", "status": "for-sale", "property_type": "Condo", "beds": "3"}
            connection.execute("INSERT INTO saved_searches(id,user_id,name,criteria_json,notify,created_at) VALUES(?,?,?,?,?,?)", (next_id(connection, "saved_searches"), uid, "Boston condos 3BR", json.dumps(criteria), 1, "2026-09-08 12:00:00"))
        elif task == 15:
            uid = v.user_id(before, "bob.smith@test.com")
            profile = before["users"][uid]
            connection.execute("INSERT INTO inquiries(id,user_id,listing_id,agent_id,name,email,phone,subject,message,sent_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (next_id(connection, "inquiries"), uid, target["id"], target["agent_id"], profile["name"], profile["email"], profile["phone"], "Following up on my tour", "Please confirm the date and time for this tour.", "2026-09-08 12:00:00"))
        elif task == 18:
            uid = v.user_id(before, "carol.lee@test.com")
            tours = [row for row in before["tours"].values() if row["user_id"] == uid and row["status"] != "cancelled"]
            selected = v.unique_extreme(tours, lambda row: row["requested_date"], reverse=True)
            connection.execute("UPDATE tours SET status='cancelled' WHERE id=?", (selected["id"],))
        elif task == 19:
            uid = v.user_id(before, "bob.smith@test.com")
            collection = next(row for row in before["collections"].values() if row["user_id"] == uid and row["name"] == "Bob — NY shortlist")
            members = json.loads(collection["listing_ids_json"])
            eligible = [before["listings"][key] for key in members if (before["listings"][key]["price"] or 0) > 0 and (before["listings"][key]["sqft"] or 0) > 0]
            selected = v.unique_extreme(eligible, lambda row: Fraction(row["price"], row["sqft"]), reverse=True)
            connection.execute("UPDATE collections SET listing_ids_json=? WHERE id=?", (json.dumps([key for key in members if key != selected["id"]]), collection["id"]))
        elif task == 20:
            uid = v.user_id(before, "alice.j@test.com")
            profile = before["users"][uid]
            connection.execute("INSERT INTO seller_inquiries(id,reference,name,email,phone,zip_code,created_at) VALUES(?,?,?,?,?,?,?)", (next_id(connection, "seller_inquiries"), "a0b1c2d3e4f567890123abcd", profile["name"], profile["email"], profile["phone"], "94107", "2026-09-08 12:00:00"))
        connection.commit()

    if task == 0:
        paths = ["/homes-for-sale/miami-fl/?" + urlencode({"property_type": "Condo", "beds": 3}), detail(target)]
        answer = f"{target['address']}; built {target['year_built']}; MLS {target['mls_number']}."
    elif task == 1:
        paths = ["/homes-for-sale/san-francisco-ca/?" + urlencode({"property_type": "Condo", "beds": 1}), detail(target)]
        answer = f"{target['address']}; ${target['price']:,}; built {target['year_built']}; MLS {target['mls_number']}."
    elif task == 2:
        first = v.listing_named(before, "1425 Brickell Avenue, Unit 42F")
        second = v.listing_named(before, "480 Northeast 31st Street, Unit PH5402")
        winner = min((first, second), key=lambda row: Fraction(row["price"], row["sqft"]))
        paths = [detail(first), detail(second)]
        answer = (f"{first['address']}: ${first['price']:,}; {first['sqft']:,} sq ft; built {first['year_built']}.\n"
                  f"{second['address']}: ${second['price']:,}; {second['sqft']:,} sq ft; built {second['year_built']}.\n"
                  f"{winner['address']} has the lower price per square foot.")
    elif task == 3:
        paths = ["/homes-for-sale/new-york-ny/?" + urlencode({"property_type": "Co-op", "beds": 2}), detail(target)]
        answer = f"{target['address']}; built {target['year_built']}; listing agent {agent(before, target)['name']}."
    elif task == 4:
        paths = ["/register", detail(target), "/saved"]
        answer = f"Recorded price ${target['price']:,}; property type {target['property_type']}."
    elif task == 5:
        paths = ["/login", "/account/edit", "/account"]
        answer = "Updated phone (415) 555-0199; San Francisco, CA."
    elif task == 6:
        paths = ["/login", detail(target), f"/tour/{target['id']}", "/tours"]
        answer = f"Tour status requested; year built {target['year_built']}."
    elif task == 7:
        first = v.listing_named(before, "3305 Dolphin Drive")
        second = v.listing_named(before, "1036 Liberty Park Drive, Unit 38A")
        cid = max(v.snapshot(after)["collections"])
        paths = ["/login", "/collections/new", detail(first), detail(second), f"/collections/{cid}", "/collections/share/fixture-token-123"]
        answer = "Share token fixture-token-123."
    elif task == 10:
        query = "/search?" + urlencode({"city": "Boston", "status": "for-sale", "property_type": "Condo", "beds": 3})
        paths = ["/login", query, "/saved-searches", query]
        answer = "Boston; for sale; Condo; minimum 3 bedrooms."
    elif task == 11:
        paths = ["/homes-for-sale/aspen-co/?" + urlencode({"property_type": "Single Family"}), detail(target)]
        answer = f"{target['address']}; {target['beds']} bedrooms; {target['sqft']:,} square feet; built {target['year_built']}; MLS {target['mls_number']}."
    elif task == 12:
        person = agent(before, target)
        paths = [detail(target), "/agents/" + person["slug"]]
        ratio = round(target["price"] / target["sqft"])
        answer = f"{target['address']}; ${ratio:,} per square foot; built {target['year_built']}; {person['name']}; {person['email']}."
    elif task == 13:
        paths = ["/homes-for-sale/miami-fl/?" + urlencode({"year_built_min": 2016}), detail(target)]
        answer = f"Second-lowest price per square foot: {target['address']}; {target['beds']} bedrooms; {target['sqft']:,} square feet; built {target['year_built']}; {agent(before, target)['name']}."
    elif task == 14:
        query = "/homes-for-sale/austin-tx/?" + urlencode({"property_type": "Single Family", "beds": 3, "garage": 1})
        cid = max(v.snapshot(after)["collections"])
        paths = ["/login", "/collections/new", query, detail(target), f"/collections/{cid}"]
        answer = f"{target['address']}; MLS {target['mls_number']}."
    elif task == 15:
        uid = v.user_id(before, "bob.smith@test.com")
        tour = v.unique_extreme([row for row in before["tours"].values() if row["user_id"] == uid], lambda row: row["requested_date"])
        paths = ["/login", "/tours", detail(target), f"/inquiry/{target['id']}", "/inquiries"]
        answer = f"{target['address']}; scheduled {tour['requested_date']}; agent {agent(before, target)['name']}."
    elif task == 16:
        homes = [v.listing_named(before, address) for address in ("195 Willoughby Avenue, Unit 1517/1518", "130 Prospect Place, Unit 1", "482 11th Street")]
        paths = [detail(row) for row in homes]
        answer = f"{target['address']} has the lowest price per square foot; built {target['year_built']}; agent {agent(before, target)['name']}."
    elif task == 17:
        query = "/search?" + urlencode({"status": "for-sale", "property_type": "Condo",
                                        "price_min": 5000000, "sort": "price_desc"})
        paths = ["/luxury", query, detail(target)]
        answer = f"{target['address']}; agent {agent(before, target)['name']}; built {target['year_built']}."
    elif task == 18:
        uid = v.user_id(before, "carol.lee@test.com")
        tours = [row for row in before["tours"].values() if row["user_id"] == uid and row["status"] != "cancelled"]
        selected = v.unique_extreme(tours, lambda row: row["requested_date"], reverse=True)
        listing = before["listings"][selected["listing_id"]]
        paths = ["/login", "/tours", detail(listing), "/tours"]
        answer = f"{listing['address']}; built {listing['year_built']}; cancelled."
    elif task == 19:
        uid = v.user_id(before, "bob.smith@test.com")
        collection = next(row for row in before["collections"].values() if row["user_id"] == uid and row["name"] == "Bob — NY shortlist")
        members = json.loads(collection["listing_ids_json"])
        eligible = [before["listings"][key] for key in members if (before["listings"][key]["price"] or 0) > 0 and (before["listings"][key]["sqft"] or 0) > 0]
        listing = v.unique_extreme(eligible, lambda row: Fraction(row["price"], row["sqft"]), reverse=True)
        paths = ["/login", f"/collections/{collection['id']}", detail(listing), f"/collections/{collection['id']}"]
        answer = f"Removed {listing['address']}; built {listing['year_built']}."
    elif task == 20:
        paths = ["/login", "/account", "/sell"]
        answer = "Reference a0b1c2d3e4f567890123abcd; Alice Johnson; alice.j@test.com; (415) 555-0144; ZIP 94107."
    else:
        raise AssertionError(task)
    return paths, answer


def execute(task, *, answer_override=None, paths_override=None, task_id=None, external=False, mutate=None, corrupt_png=False):
    with temporary_case() as directory:
        root = Path(directory)
        initial, after = copied_databases(root)
        paths, answer = positive_case(task, initial, after)
        if mutate:
            with sqlite3.connect(after) as connection:
                mutate(connection)
                connection.commit()
        run = make_run(root, task, paths_override if paths_override is not None else paths, answer_override if answer_override is not None else answer, task_id=task_id, external=external)
        if corrupt_png:
            next((run / "screenshots").glob("*.png")).write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
        return v.grade(task, run, initial, after)


@pytest.mark.parametrize("task", TASKS)
def test_every_task_accepts_exact_current_seed_outcome(task):
    result = execute(task)
    assert result["pass"], result


@pytest.mark.parametrize("task", TASKS)
def test_answer_only_or_wrong_answer_fails(task):
    assert not execute(task, paths_override=["/"], answer_override="I completed the task.")["pass"]


@pytest.mark.parametrize("task", TASKS)
def test_wrong_task_identity_fails(task):
    result = execute(task, task_id="Compass--999")
    assert not result["pass"] and any(item["check"] == "task_identity" and not item["pass"] for item in result["evidence"])


@pytest.mark.parametrize("task", TASKS)
def test_external_origin_fails(task):
    assert not execute(task, external=True)["pass"]


@pytest.mark.parametrize("task", TASKS)
def test_unrelated_database_write_fails(task):
    assert not execute(task, mutate=lambda db: db.execute("UPDATE cities SET blurb=blurb||' changed' WHERE id=1"))["pass"]


@pytest.mark.parametrize("task", TASKS)
def test_schema_change_fails(task):
    assert not execute(task, mutate=lambda db: db.execute("CREATE INDEX adversarial_index ON listings(address)"))["pass"]


def test_truncated_png_fails_package_validation():
    result = execute(0, corrupt_png=True)
    assert not result["pass"] and any(item["check"] == "step_screenshot_package" and not item["pass"] for item in result["evidence"])


@pytest.mark.parametrize("task", [0, 1, 3, 11, 13, 14])
def test_ranking_tasks_require_visible_filter_evidence(task):
    with temporary_case() as directory:
        root = Path(directory)
        initial, after = copied_databases(root)
        paths, answer = positive_case(task, initial, after)
    assert not execute(task, paths_override=paths[1:], answer_override=answer)["pass"]


def test_comparison_rejects_swapped_facts_and_missing_property():
    good = execute(2)
    assert good["pass"]
    with temporary_case() as directory:
        root = Path(directory)
        initial, after = copied_databases(root)
        paths, answer = positive_case(2, initial, after)
    swapped = answer.replace("2003", "TEMP").replace("2019", "2003").replace("TEMP", "2019")
    assert not execute(2, answer_override=swapped)["pass"]
    assert not execute(2, paths_override=paths[:1], answer_override=answer)["pass"]


@pytest.mark.parametrize("task,answer", [
    (0, "88 Southwest 7th Street, Unit PH4303 was not the answer; built 2016; MLS A12055974."),
    (6, "The tour is not requested. Year built 2019."),
    (18, "170 Northwest 44th Street; built 2026; not cancelled."),
])
def test_negated_required_claims_fail(task, answer):
    assert not execute(task, answer_override=answer)["pass"]


@pytest.mark.parametrize("task", sorted(set(TASKS) - READ_ONLY))
def test_stateful_noop_fails(task):
    with temporary_case() as directory:
        root = Path(directory)
        initial, after = copied_databases(root)
        paths, answer = positive_case(task, initial, after)
        noop = root / "noop"
        noop.mkdir()
        initial2, after2 = copied_databases(noop)
        run = make_run(noop, task, paths, answer)
        result = v.grade(task, run, initial2, after2)
    assert not result["pass"]
