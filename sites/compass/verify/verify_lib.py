"""Deterministic Compass grading against frozen runs and explicit DB snapshots.

The recorder is trusted to report browser observations honestly. Image existence
checks validate packaging; they do not claim to interpret screenshot pixels.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image

STATEFUL = {4, 5, 6, 7, 10, 14, 15, 18, 19, 20}
TABLES = {"agents", "cities", "listings", "users", "saved_homes",
          "saved_searches", "collections", "tours", "inquiries",
          "neighborhood_guides", "seller_inquiries", "seed_metadata"}


def norm(value):
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)
    return re.sub(r"\s+", " ", text).strip()


def words(value):
    return re.sub(r"[^\w]+", " ", norm(value)).strip()


def phrase(text, expected):
    return bool(re.search(r"(?<!\w)" + re.escape(words(expected)) + r"(?!\w)", words(text)))


def affirmative_phrase(text, expected):
    normalized = words(text)
    matches = list(re.finditer(r"(?<!\w)" + re.escape(words(expected)) + r"(?!\w)", normalized))
    if not matches:
        return False
    match = matches[-1]
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead)\b", normalized[:match.start()])[-1]
    after = normalized[match.end():]
    return not re.search(r"\b(?:not|no|never|without|isnt|wasnt|incorrect)\b", before) and not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|incorrect)\b", after)


def address_text(text):
    text = words(text)
    for full, short in {"southwest": "sw", "southeast": "se", "northeast": "ne",
                        "northwest": "nw", "avenue": "ave", "street": "st",
                        "saint": "st", "drive": "dr", "place": "pl", "boulevard": "blvd",
                        "west": "w", "east": "e", "north": "n", "south": "s"}.items():
        text = re.sub(r"\b" + full + r"\b", short, text)
    return re.sub(r"\b(unit|apt|apartment|suite)\s+", "", text)


def address_matches(text, listing):
    expected = address_text(listing["address"])
    return bool(re.search(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", address_text(text)))


def affirmative_address_matches(text, listing):
    if not address_matches(text, listing):
        return False
    normalized = address_text(text)
    match = list(re.finditer(r"(?<!\w)" + re.escape(address_text(listing["address"])) + r"(?!\w)", normalized))[-1]
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead)\b", normalized[:match.start()])[-1]
    after = normalized[match.end():]
    return not re.search(r"\b(?:not|no|never|without|incorrect)\b", before) and not re.match(r"\s*(?:is|was|are|were)?\s*(?:not|incorrect)\b", after)


def number_values(text):
    """Handle ordinary dollar amounts, grouped numbers and million notation."""
    text = norm(text)
    output = set()
    for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(million|thousand|m\b|k\b)?", text):
        amount = float(match[1])
        amount *= {"million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(match[2], 1)
        output.add(amount)
    return output


def construction_years(text):
    """Exclude numbers explicitly used as dates, money, areas or ratios."""
    text = norm(text)
    month = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    patterns = [
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        rf"\b{month}\s+\d{{1,2}},?\s+\d{{4}}\b",
        rf"\b\d{{1,2}}\s+{month}\s+\d{{4}}\b",
        r"(?:\$|\busd\s*)\d+(?:\.\d+)?",
        r"\b\d+(?:\.\d+)?\s*(?:sq\.?\s*ft\.?|square feet|sf)\b",
        r"\b\d+\.\d+\b",
    ]
    for pattern in patterns:
        text = re.sub(pattern, " ", text)
    return {int(year) for year in re.findall(r"\b(?:18|19|20)\d{2}\b", text)}


def requested_tour_status(text):
    """Confirming a page is not an assertion that the appointment is confirmed."""
    text = norm(text)
    if not phrase(text, "requested") or re.search(r"\bnot\s+requested\b", text):
        return False
    text = re.sub(
        r"\bconfirmed\s+(?:it|(?:its|the|my)\s+(?:details|request|tour))"
        r"\s+(?:on|in)\s+(?:(?:the|my)\s+)?tours?(?:\s+page)?\b", " ", text)
    text = re.sub(r"\bnot\s+(?:confirmed|cancelled|canceled)\b", " ", text)
    return not re.search(r"\b(?:confirmed|cancelled|canceled|pending)\b", text)


def scalar(text, value, field):
    if field == "year":
        return construction_years(text) == {value}
    if value not in number_values(text):
        if field != "beds" or not phrase(text, {4: "four", 7: "seven"}.get(value, str(value))):
            return False
    normalized = norm(text)
    patterns = {
        "beds": [r"(\d+)\s*(?:bedrooms?|beds?|br)\b", r"(?:bedrooms?|beds?)\s*[:=]\s*(\d+)"],
        "sqft": [r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft\.?|square feet|sf)\b",
                 r"(?:sq\.?\s*ft\.?|square feet|floor area)\s*[:=]\s*(\d+)"],
    }
    for pattern in patterns.get(field, []):
        found = re.findall(pattern, normalized)
        if any(float(item) != value for item in found):
            return False
    if field == "price":
        for match in re.finditer(r"(?:\$|usd\s*)(\d+(?:\.\d+)?\s*(?:million|thousand|m\b|k\b)?)", normalized):
            if re.match(r"\s*(?:/\s*(?:sq|sf)|per\s+(?:sq|square))", normalized[match.end():]):
                continue
            if number_values(match[1]) != {float(value)}:
                return False
    return True


def loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def local_url(url, trajectory):
    if not isinstance(url, str):
        return False
    try:
        target, start = urlsplit(url), urlsplit(trajectory.get("start_url", ""))
        return (target.scheme == start.scheme == "http" and loopback(start.hostname)
                and loopback(target.hostname) and target.port == start.port
                and not target.username and not target.password)
    except ValueError:
        return False


def recorded_urls(trajectory):
    values = []
    if trajectory.get("start_url"):
        values.append(trajectory["start_url"])
    for step in trajectory.get("steps", []):
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = step.get(key)
            if value and (not values or value != values[-1]):
                values.append(value)
    if trajectory.get("final_url"):
        values.append(trajectory["final_url"])
    return values


def urls(trajectory):
    for value in recorded_urls(trajectory):
        if local_url(value, trajectory):
            yield value


def visited(trajectory, path):
    return any(unquote(urlsplit(url).path).rstrip("/") == path.rstrip("/") for url in urls(trajectory))


def query_matches(url, expected):
    params = parse_qs(urlsplit(url).query, keep_blank_values=True)
    for key, value in expected.items():
        observed = params.get(key)
        if observed is None or len(observed) != 1 or norm(observed[0]) != norm(value):
            return False
    return True


def visited_query(trajectory, path, expected):
    wanted = path.rstrip("/") or "/"
    return any(unquote(urlsplit(url).path).rstrip("/") == wanted and query_matches(url, expected)
               for url in urls(trajectory))


def visited_in_order(trajectory, requirements):
    recorded = list(urls(trajectory))
    cursor = 0
    for path, query in requirements:
        wanted = path.rstrip("/") or "/"
        for index in range(cursor, len(recorded)):
            url = recorded[index]
            if unquote(urlsplit(url).path).rstrip("/") == wanted and query_matches(url, query):
                cursor = index + 1
                break
        else:
            return False
    return True


def transitioned(trajectory, source, target, query=None):
    """Only explicit task requirements use a transition check; no fixed route elsewhere."""
    steps = trajectory.get("steps", [])
    for index, step in enumerate(steps):
        before = step.get("url", "")
        after = step.get("url_after") or (steps[index + 1].get("url", "") if index + 1 < len(steps) else "")
        if not (local_url(before, trajectory) and local_url(after, trajectory)):
            continue
        if urlsplit(before).path != source or urlsplit(after).path != target:
            continue
        if step.get("action") not in {"click", "press", "key", "select", "select_option"}:
            continue
        params = {key: value[-1] for key, value in parse_qs(urlsplit(after).query).items()}
        if query is None or query(params):
            return True
    return False


def snapshot(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != TABLES:
            raise ValueError(f"Unexpected Compass database schema: {sorted(tables)}")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise ValueError("Foreign-key integrity failed")
        return {table: {row["slug" if table == "neighborhood_guides" else "id"]: dict(row)
                        for row in connection.execute('SELECT * FROM "' + table + '"')}
                for table in sorted(tables)}


def schema_snapshot(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()


def only_new(before, after, table):
    return [row for key, row in after[table].items() if key not in before[table]]


def user_id(snapshot_data, email):
    matches = [row["id"] for row in snapshot_data["users"].values() if row["email"] == email]
    return matches[0] if len(matches) == 1 else None


def listing_named(snapshot_data, address):
    matches = [row for row in snapshot_data["listings"].values()
               if address_text(row["address"]) == address_text(address)]
    if len(matches) != 1:
        raise ValueError(f"Expected one listing for {address!r}, found {len(matches)}")
    return matches[0]


def unique_extreme(rows, key, reverse=False, position=0):
    ordered = sorted(rows, key=lambda row: (key(row), row["id"]), reverse=reverse)
    if len(ordered) <= position:
        raise ValueError("No eligible task target")
    target = ordered[position]
    if position == 0 and len(ordered) > 1 and key(ordered[0]) == key(ordered[1]):
        raise ValueError("Task target is tied")
    if position > 0 and (key(ordered[position - 1]) == key(target)
                         or (len(ordered) > position + 1 and key(ordered[position + 1]) == key(target))):
        raise ValueError("Ranked task target is tied")
    return target


def task_target(task, snapshot_data):
    listings = list(snapshot_data["listings"].values())
    fixed = {
        4: "50 King Street, Unit 9A",
        6: "480 Northeast 31st Street, Unit PH5402",
        12: "17145 Southwest 90th Avenue",
    }
    if task in fixed:
        return listing_named(snapshot_data, fixed[task])
    if task == 0:
        rows = [row for row in listings if norm(row["market_city"]) == "miami"
                and row["status"] == "for-sale" and row["property_type"] == "Condo"
                and (row["beds"] or 0) >= 3 and (row["sqft"] or 0) > 0 and (row["price"] or 0) > 0]
        return unique_extreme(rows, lambda row: Fraction(row["price"], row["sqft"]))
    if task == 1:
        rows = [row for row in listings if norm(row["market_city"]) == "san francisco"
                and row["status"] == "for-sale" and row["property_type"] == "Condo"
                and (row["beds"] or 0) >= 1 and (row["price"] or 0) > 0]
        return unique_extreme(rows, lambda row: row["price"])
    if task == 3:
        rows = [row for row in listings if norm(row["market_city"]) == "new york"
                and row["status"] == "for-sale" and row["property_type"] == "Co-op"
                and (row["beds"] or 0) >= 2 and (row["price"] or 0) > 0]
        return unique_extreme(rows, lambda row: row["price"])
    if task == 11:
        rows = [row for row in listings if norm(row["market_city"]) == "aspen"
                and row["status"] == "for-sale" and row["property_type"] == "Single Family"
                and (row["price"] or 0) > 0]
        return unique_extreme(rows, lambda row: row["price"], reverse=True)
    if task == 13:
        rows = [row for row in listings if norm(row["market_city"]) == "miami"
                and row["status"] == "for-sale" and (row["year_built"] or 0) >= 2016
                and (row["price"] or 0) > 0 and (row["sqft"] or 0) > 0]
        return unique_extreme(rows, lambda row: Fraction(row["price"], row["sqft"]), position=1)
    if task == 14:
        rows = [row for row in listings if norm(row["market_city"]) == "austin"
                and row["status"] == "for-sale" and row["property_type"] == "Single Family"
                and (row["beds"] or 0) >= 3 and row["has_garage"] == 1 and (row["price"] or 0) > 0]
        return unique_extreme(rows, lambda row: row["price"])
    if task == 15:
        uid = user_id(snapshot_data, "bob.smith@test.com")
        tours = [row for row in snapshot_data["tours"].values() if row["user_id"] == uid]
        tour = unique_extreme(tours, lambda row: row["requested_date"])
        return snapshot_data["listings"][tour["listing_id"]]
    if task == 16:
        rows = [listing_named(snapshot_data, address) for address in (
            "195 Willoughby Avenue, Unit 1517/1518", "130 Prospect Place, Unit 1", "482 11th Street")]
        return unique_extreme(rows, lambda row: Fraction(row["price"], row["sqft"]))
    if task == 17:
        rows = [row for row in listings if row["is_luxury"] == 1 and row["status"] == "for-sale"
                and row["property_type"] == "Condo" and (row["price"] or 0) >= 5_000_000]
        return unique_extreme(rows, lambda row: row["price"], reverse=True)
    raise ValueError(f"Task {task} does not have one listing target")


def listing_with_agent(snapshot_data, listing):
    result = dict(listing)
    agent = snapshot_data["agents"].get(listing.get("agent_id"))
    result["agent_name"] = agent.get("name", "") if agent else ""
    result["agent_email"] = agent.get("email", "") if agent else ""
    result["agent_slug"] = agent.get("slug", "") if agent else ""
    return result


def criteria_ok(criteria):
    locations = [norm(criteria.get(key, "")) for key in ("q", "city") if criteria.get(key)]
    return (bool(locations) and all(value in {"boston", "boston ma", "boston, ma"} for value in locations)
            and criteria.get("status") == "for-sale" and criteria.get("property_type") == "Condo"
            and str(criteria.get("beds")) == "3"
            and not any(value for key, value in criteria.items() if key not in {"q", "city", "status", "property_type", "beds", "sort"}))


class Checks:
    def __init__(self, task):
        self.task = task
        self.results = []

    def check(self, name, condition, detail=""):
        self.results.append({"check": name, "pass": bool(condition), "detail": detail})

    def result(self):
        failures = [item["check"] for item in self.results if not item["pass"]]
        return {"task_id": f"Compass--{self.task}", "pass": not failures,
                "reason": "; ".join(failures) if failures else "All applicable checks passed",
                "evidence": self.results}


def package_checks(judge, trajectory, run_dir):
    steps = trajectory.get("steps")
    raw_urls = recorded_urls(trajectory)
    judge.check("task_identity", trajectory.get("task_id") == f"Compass--{judge.task}")
    judge.check("local_ui_evidence", isinstance(steps, list) and bool(steps) and bool(raw_urls))
    judge.check("same_origin_navigation", bool(raw_urls) and all(local_url(url, trajectory) for url in raw_urls))
    judge.check("final_answer", isinstance(trajectory.get("final_answer"), str) and bool(trajectory["final_answer"].strip()))
    judge.check("completed_run", trajectory.get("terminated") is True and trajectory.get("termination_reason") in {"agent_done", "guided_done"})
    screenshots = Path(run_dir).resolve() / "screenshots"
    valid = isinstance(steps, list) and bool(steps)
    referenced = []
    for step in steps or []:
        if not isinstance(step, dict):
            valid = False
            continue
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            if not isinstance(name, str) or Path(name).name != name:
                valid = False
                continue
            referenced.append(name)
            path = screenshots / name
            try:
                if path.resolve().parent != screenshots or path.stat().st_size < 1000:
                    valid = False
                    continue
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    valid &= image.format == "PNG" and image.width >= 320 and image.height >= 200
            except (OSError, ValueError, SyntaxError):
                valid = False
    valid &= bool(referenced)
    judge.check("step_screenshot_package", valid)


def state_checks(judge, trajectory, before, after):
    task = judge.task
    allowed = {4: {"users", "saved_homes"}, 5: {"users"}, 6: {"tours"},
               7: {"collections", "saved_homes"}, 10: {"saved_searches"},
               14: {"collections", "saved_homes"}, 15: {"inquiries"}}.get(task, set())
    judge.check("same_table_set", before.keys() == after.keys())
    for table in before.keys() | after.keys():
        if table not in before or table not in after:
            continue  # Reported by same_table_set, including empty added tables.
        if table not in allowed:
            judge.check("unchanged_" + table, before[table] == after[table])
        else:
            for key, row in before[table].items():
                expected = dict(row)
                if task == 5 and table == "users" and row["email"] == "alice.j@test.com":
                    expected["phone"] = "(415) 555-0199"
                judge.check(f"preserve_{table}_{key}", after[table].get(key) == expected)
    if task not in STATEFUL:
        return
    email = {4: "taylor.reed+test@example.com", 5: "alice.j@test.com", 6: "carol.lee@test.com",
             7: "david.kim@test.com", 10: "alice.j@test.com", 14: "david.kim@test.com", 15: "bob.smith@test.com"}[task]
    uid = user_id(after, email)
    judge.check("target_account", uid is not None)
    judge.check("authentication_workflow", visited(trajectory, "/register") if task == 4 else visited(trajectory, "/login"))
    if task == 4:
        new = only_new(before, after, "users")
        judge.check("one_registered_account", len(new) == 1 and new[0]["id"] == uid and new[0]["name"] == "Taylor Reed")
        password_ok = False
        if len(new) == 1:
            try:
                import bcrypt
                password_ok = bcrypt.checkpw(b"compass-test-1234", new[0]["password_hash"].encode())
            except (ImportError, ValueError):
                pass
        judge.check("registered_password", password_ok)
        defaults = {"phone": "", "city": "", "state": "", "budget_min": 0, "budget_max": 0,
                    "beds_min": 0, "preferred_property_types": "[]", "move_timeline": "",
                    "has_agent": 0, "receive_alerts": 1, "agent_id": None}
        judge.check("registration_defaults", len(new) == 1 and all(new[0][key] == value for key, value in defaults.items()))
        saved = only_new(before, after, "saved_homes")
        target = task_target(4, before)
        judge.check("one_target_save", len(saved) == 1 and saved[0]["user_id"] == uid and saved[0]["listing_id"] == target["id"])
        judge.check("saved_homes_confirmation", visited(trajectory, "/saved"))
    elif task == 5:
        judge.check("no_new_users", not only_new(before, after, "users"))
        judge.check("phone_changed", uid in before["users"] and before["users"][uid]["phone"] != "(415) 555-0199")
        judge.check("account_overview_confirmation", visited(trajectory, "/account"))
    elif task == 6:
        new = only_new(before, after, "tours")
        target = task_target(6, before)
        expected = {"user_id": uid, "listing_id": target["id"], "requested_date": "2026-07-12", "requested_time": "11:00 AM", "tour_type": "in-person", "contact_phone": before["users"][uid]["phone"], "notes": "", "status": "requested"}
        judge.check("one_exact_tour", len(new) == 1 and all(new[0][key] == value for key, value in expected.items()))
        judge.check("tours_confirmation", visited(trajectory, "/tours"))
    elif task in {7, 14}:
        new = only_new(before, after, "collections")
        members = ({listing_named(before, "3305 Dolphin Drive")["id"],
                    listing_named(before, "1036 Liberty Park Drive, Unit 38A")["id"]}
                   if task == 7 else {task_target(14, before)["id"]})
        name = "Austin top picks" if task == 7 else "Austin garage picks"
        valid = False
        if len(new) == 1:
            collection = new[0]
            ids = json.loads(collection["listing_ids_json"])
            valid = (collection["user_id"] == uid and collection["name"] == name
                     and len(ids) == len(members) and set(ids) == members
                     and re.fullmatch(r"[A-Za-z0-9_-]{12,64}", collection["share_token"] or "") is not None)
            path = f'/collections/share/{collection["share_token"]}' if task == 7 else f'/collections/{collection["id"]}'
            if task == 7:
                first = listing_named(before, "3305 Dolphin Drive")
                second = listing_named(before, "1036 Liberty Park Drive, Unit 38A")
                judge.check("collection_confirmation_order", visited_in_order(trajectory, [
                    ("/login", {}), ("/collections/new", {}),
                    (snapshot_detail_path(first), {}), (snapshot_detail_path(second), {}),
                    (f'/collections/{collection["id"]}', {}), (path, {})]))
                judge.check("answer_share_token", bool(re.search(r"(?<![\w-])" + re.escape(collection["share_token"]) + r"(?![\w-])", trajectory["final_answer"])))
            else:
                judge.check("collection_confirmation_order", visited_in_order(trajectory, [
                    ("/login", {}), ("/collections/new", {}),
                    (snapshot_detail_path(task_target(14, before)), {}), (path, {})]))
        judge.check("one_exact_collection", valid)
        saves = only_new(before, after, "saved_homes")
        save_pairs = [(row["user_id"], row["listing_id"]) for row in saves]
        judge.check("optional_target_saves_only", len(saves) <= len(members)
                    and len(save_pairs) == len(set(save_pairs))
                    and all(row["user_id"] == uid and row["listing_id"] in members for row in saves))
    elif task == 10:
        new = only_new(before, after, "saved_searches")
        valid = (len(new) == 1 and new[0]["user_id"] == uid and new[0]["name"] == "Boston condos 3BR"
                 and criteria_ok(json.loads(new[0]["criteria_json"])))
        judge.check("one_exact_saved_search", valid)
        judge.check("saved_search_confirmation_order", any(visited_in_order(trajectory, [
            ("/login", {}), ("/search", {location_key: "Boston", "status": "for-sale",
                                         "property_type": "Condo", "beds": "3"}),
            ("/saved-searches", {}), ("/search", {location_key: "Boston", "status": "for-sale",
                                                   "property_type": "Condo", "beds": "3"})])
            for location_key in ("city", "q")))
        judge.check("reopened_saved_search", transitioned(trajectory, "/saved-searches", "/search", criteria_ok))
    elif task == 15:
        new = only_new(before, after, "inquiries")
        target = task_target(15, before)
        profile = before["users"][uid]
        expected = {"user_id": uid, "listing_id": target["id"], "agent_id": target["agent_id"],
                    "name": profile["name"], "email": profile["email"], "phone": profile["phone"],
                    "subject": "Following up on my tour", "message": "Please confirm the date and time for this tour."}
        judge.check("one_exact_inquiry", len(new) == 1 and all(new[0][key] == value for key, value in expected.items()))
        judge.check("tour_and_inquiry_ui", visited(trajectory, "/tours") and visited(trajectory, f"/inquiry/{target['id']}"))


def snapshot_detail_path(listing):
    return "/listing/" + listing["slug"]


def filter_route_seen(trajectory, city_slug, city_name, expected):
    city_path = f"/homes-for-sale/{city_slug}"
    if visited_query(trajectory, city_path, expected):
        return True
    return any(visited_query(trajectory, "/search", {
        **expected, location_key: city_name, "status": "for-sale"})
        for location_key in ("city", "q"))


def navigation_checks(judge, trajectory, before):
    task = judge.task
    target = task_target(task, before) if task in {0, 1, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17} else None
    filters = {
        0: ("miami-fl", "Miami", {"property_type": "Condo", "beds": "3"}),
        1: ("san-francisco-ca", "San Francisco", {"property_type": "Condo", "beds": "1"}),
        3: ("new-york-ny", "New York", {"property_type": "Co-op", "beds": "2"}),
        11: ("aspen-co", "Aspen", {"property_type": "Single Family"}),
        13: ("miami-fl", "Miami", {"year_built_min": "2016"}),
        14: ("austin-tx", "Austin", {"property_type": "Single Family", "beds": "3", "garage": "1"}),
    }
    if task in filters:
        judge.check("required_search_filters", filter_route_seen(trajectory, *filters[task]))
    if target is not None and task not in {4, 6, 14, 15}:
        judge.check("target_property_details", visited(trajectory, snapshot_detail_path(target)))
    if task == 2:
        for address in ("1425 Brickell Avenue, Unit 42F", "480 Northeast 31st Street, Unit PH5402"):
            listing = listing_named(before, address)
            judge.check(f"details_{listing['id']}", visited(trajectory, snapshot_detail_path(listing)))
    elif task == 4:
        judge.check("registration_save_confirmation_order", visited_in_order(trajectory, [
            ("/register", {}), (snapshot_detail_path(target), {}), ("/saved", {})]))
    elif task == 5:
        judge.check("profile_edit_workflow", visited_in_order(trajectory, [
            ("/login", {}), ("/account/edit", {}), ("/account", {})]))
    elif task == 6:
        judge.check("tour_request_workflow", visited_in_order(trajectory, [
            ("/login", {}), (snapshot_detail_path(target), {}),
            (f"/tour/{target['id']}", {}), ("/tours", {})]))
    elif task == 7:
        first = listing_named(before, "3305 Dolphin Drive")
        second = listing_named(before, "1036 Liberty Park Drive, Unit 38A")
        judge.check("collection_property_details", visited(trajectory, snapshot_detail_path(first))
                    and visited(trajectory, snapshot_detail_path(second)))
    elif task == 10:
        judge.check("saved_search_source_filters", filter_route_seen(
            trajectory, "boston-ma", "Boston", {"property_type": "Condo", "beds": "3"}))
    elif task == 12:
        agent = listing_with_agent(before, target)
        judge.check("followed_agent_profile", transitioned(
            trajectory, snapshot_detail_path(target), "/agents/" + agent["agent_slug"]))
    elif task == 15:
        judge.check("tour_listing_inquiry_workflow", visited_in_order(trajectory, [
            ("/login", {}), ("/tours", {}), (snapshot_detail_path(target), {}),
            (f"/inquiry/{target['id']}", {}), ("/inquiries", {})]))
    elif task == 16:
        for address in ("195 Willoughby Avenue, Unit 1517/1518",
                        "130 Prospect Place, Unit 1", "482 11th Street"):
            listing = listing_named(before, address)
            judge.check(f"comparison_details_{listing['id']}", visited(
                trajectory, snapshot_detail_path(listing)))
    elif task == 17:
        judge.check("luxury_filter_workflow", visited_in_order(trajectory, [
            ("/luxury", {}), ("/search", {"status": "for-sale",
                                           "property_type": "Condo",
                                           "price_min": "5000000"}),
            (snapshot_detail_path(target), {})]))


def answer_field(judge, text, listing, field, expected):
    if isinstance(expected, (int, float)):
        ok = scalar(text, expected, "year" if field == "year_built" else field)
    else:
        ok = affirmative_phrase(text, expected)
    if field == "agent_email":
        ok = bool(re.search(r"(?<![\w.@+-])" + re.escape(expected) + r"(?![\w@+-]|\.[\w])", norm(text)))
    judge.check("answer_" + field, ok)


def entity_answer_text(text, listing, before):
    mentioned = [row for row in before["listings"].values() if address_matches(text, row)]
    if len(mentioned) <= 1:
        return text
    matching_lines = [line for line in text.splitlines() if address_matches(line, listing)]
    return "\n".join(matching_lines)


def answer_checks(judge, trajectory, before):
    task = judge.task
    text = trajectory.get("final_answer") or ""
    if task == 7:
        return
    if task == 5:
        judge.check("answer_phone", "4155550199" in re.sub(r"\D", "", text))
        judge.check("answer_existing_location", affirmative_phrase(text, "San Francisco")
                    and (affirmative_phrase(text, "CA") or affirmative_phrase(text, "California")))
        return
    if task == 10:
        judge.check("answer_saved_criteria", affirmative_phrase(text, "Boston")
                    and (affirmative_phrase(text, "for sale") or affirmative_phrase(text, "for-sale"))
                    and (affirmative_phrase(text, "Condo") or affirmative_phrase(text, "Condos"))
                    and scalar(text, 3, "beds"))
        return
    if task == 2:
        rows = [row for row in text.splitlines() if row.strip()]
        listings = [listing_named(before, "1425 Brickell Avenue, Unit 42F"),
                    listing_named(before, "480 Northeast 31st Street, Unit PH5402")]
        for listing in listings:
            judge.check(f"associated_facts_{listing['id']}", any(
                affirmative_address_matches(row, listing)
                and scalar(row, listing["price"], "price")
                and scalar(row, listing["sqft"], "sqft")
                and scalar(row, listing["year_built"], "year") for row in rows))
        winner = unique_extreme(listings, lambda row: Fraction(row["price"], row["sqft"]))
        judge.check("lower_ratio_selection", any(
            affirmative_address_matches(row, winner)
            and re.search(r"\b(lower|lowest|cheaper|less expensive)\b", norm(row))
            and not re.search(r"\bnot\b", norm(row)) for row in rows))
        return
    listing = listing_with_agent(before, task_target(task, before))
    if task not in {4, 6}:
        judge.check("answer_target_address", affirmative_address_matches(text, listing))
    fields = {
        0: ["year_built", "mls_number"],
        1: ["price", "year_built", "mls_number"],
        3: ["year_built", "agent_name"],
        4: ["price", "property_type"],
        6: ["year_built"],
        11: ["beds", "sqft", "year_built", "mls_number"],
        12: ["year_built", "agent_name", "agent_email"],
        13: ["beds", "sqft", "year_built", "agent_name"],
        14: ["mls_number"],
        15: ["agent_name"],
        16: ["year_built", "agent_name"],
        17: ["agent_name", "year_built"],
    }
    bound_text = entity_answer_text(text, listing, before)
    for field in fields.get(task, []):
        answer_field(judge, bound_text, listing, field, listing[field])
    if task == 6:
        judge.check("answer_tour_status", requested_tour_status(text))
    if task == 12:
        ratio = math.floor(listing["price"] / listing["sqft"] + 0.5)
        ratio_context = re.search(
            rf"(?:price\s+per\s+square\s+foot|per\s+(?:square\s+foot|sq\.?\s*ft)|/\s*(?:sqft|sf)).{{0,40}}{ratio}|{ratio}.{{0,40}}(?:price\s+per\s+square\s+foot|per\s+(?:square\s+foot|sq\.?\s*ft)|/\s*(?:sqft|sf))",
            norm(bound_text))
        judge.check("answer_rounded_price_per_sqft", scalar(bound_text, ratio, "ratio")
                    and ratio_context is not None)
    if task == 13:
        judge.check("answer_second_lowest_ratio", re.search(
            r"\bsecond[- ]lowest\b.*\b(?:price per square foot|ppsf|\$/sqft)\b|\b(?:price per square foot|ppsf|\$/sqft)\b.*\bsecond[- ]lowest\b",
            norm(text)) is not None)
    if task == 15:
        uid = user_id(before, "bob.smith@test.com")
        tour = unique_extreme([row for row in before["tours"].values()
                               if row["user_id"] == uid], lambda row: row["requested_date"])
        accepted = {tour["requested_date"]}
        parsed = date.fromisoformat(tour["requested_date"])
        accepted |= {parsed.strftime("%B %-d, %Y").casefold(),
                     parsed.strftime("%-d %B %Y").casefold(),
                     parsed.strftime("%m/%d/%Y")}
        judge.check("answer_tour_date", any(value in norm(text) for value in accepted))


def grade(task, run_dir, initial_db, after_db):
    judge = Checks(task)
    try:
        trajectory = json.loads((Path(run_dir) / "trajectory.json").read_text())
        package_checks(judge, trajectory, run_dir)
        before, after = snapshot(initial_db), snapshot(after_db)
        judge.check("exact_database_schema", schema_snapshot(initial_db) == schema_snapshot(after_db))
        marker = before["seed_metadata"].get(1)
        judge.check("current_seed_version", marker is not None and marker["version"] == "compass-source-v3")
        if task in {18, 19, 20}:
            from verify_expansion import check
            check(judge, trajectory, before, after)
        else:
            state_checks(judge, trajectory, before, after)
            navigation_checks(judge, trajectory, before)
            answer_checks(judge, trajectory, before)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, sqlite3.Error) as error:
        judge.check("valid_inputs", False, f"{type(error).__name__}: {error}")
    return judge.result()


def _bool_value(value):
    return str(value).casefold() in {"1", "true", "yes", "on"}


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default="wh-review")
    parser.add_argument("--no_llm", nargs="?", const=True, default=False,
                        type=_bool_value, help="Accepted for harness compatibility; grading is always deterministic")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="compass-verifier-") as temporary:
        paths = []
        try:
            for explicit, kind in ((args.initial_db, "instance_seed"), (args.after_db, "instance")):
                if explicit:
                    paths.append(explicit)
                else:
                    destination = str(Path(temporary) / (kind + ".db"))
                    subprocess.run(["docker", "cp", f"{args.container}:/opt/WebSyn/compass/{kind}/compass.db", destination], check=True, capture_output=True)
                    paths.append(destination)
            result = grade(task, args.run_dir, *paths)
        except (OSError, subprocess.CalledProcessError) as error:
            result = {"task_id": f"Compass--{task}", "pass": False, "reason": "Database snapshot unavailable", "evidence": [type(error).__name__]}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result["pass"] else 1)
