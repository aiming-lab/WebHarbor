"""Deterministic Compass grading against frozen runs and explicit DB snapshots.

The recorder is trusted to report browser observations honestly. Image existence
checks validate packaging; they do not claim to interpret screenshot pixels.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

FACTS = json.loads(Path(__file__).with_name("facts.json").read_text())
TARGETS = {int(k): v for k, v in FACTS["target_ids"].items()}
LISTINGS = {int(k): v for k, v in FACTS["listings"].items()}
STATEFUL = {4, 5, 6, 7, 10, 14, 15}
TABLES = {"agents", "cities", "listings", "users", "saved_homes",
          "saved_searches", "collections", "tours", "inquiries"}


def norm(value):
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)
    return re.sub(r"\s+", " ", text).strip()


def words(value):
    return re.sub(r"[^\w]+", " ", norm(value)).strip()


def phrase(text, expected):
    return bool(re.search(r"(?<!\w)" + re.escape(words(expected)) + r"(?!\w)", words(text)))


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


def urls(trajectory):
    for step in trajectory.get("steps", []):
        for key in ("url", "url_after"):
            value = step.get(key, "")
            if local_url(value, trajectory):
                yield value


def visited(trajectory, path):
    return any(unquote(urlsplit(url).path).rstrip("/") == path.rstrip("/") for url in urls(trajectory))


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
            raise ValueError("Unexpected or incomplete Compass database schema")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise ValueError("Foreign-key integrity failed")
        return {table: {row["id"]: dict(row) for row in connection.execute('SELECT * FROM "' + table + '"')}
                for table in sorted(tables)}


def only_new(before, after, table):
    return [row for key, row in after[table].items() if key not in before[table]]


def user_id(snapshot_data, email):
    matches = [row["id"] for row in snapshot_data["users"].values() if row["email"] == email]
    return matches[0] if len(matches) == 1 else None


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
    judge.check("task_identity", trajectory.get("task_id") == f"Compass--{judge.task}")
    judge.check("local_ui_evidence", bool(list(urls(trajectory))) and bool(trajectory.get("steps")))
    judge.check("final_answer", isinstance(trajectory.get("final_answer"), str) and bool(trajectory["final_answer"].strip()))
    judge.check("completed_run", trajectory.get("terminated") is True and trajectory.get("termination_reason") in {"agent_done", "guided_done"})
    screenshots = Path(run_dir).resolve() / "screenshots"
    valid = True
    for step in trajectory.get("steps", []):
        for key in ("screenshot_before", "screenshot_after"):
            name = step.get(key)
            if not isinstance(name, str) or Path(name).name != name:
                valid = False
                continue
            path = screenshots / name
            try:
                if path.resolve().parent != screenshots:
                    valid = False
                    continue
                with path.open("rb") as image:
                    header = image.read(24)
                valid &= header[:8] == b"\x89PNG\r\n\x1a\n"
                width, height = struct.unpack(">II", header[16:24])
                valid &= width >= 320 and height >= 200
            except (OSError, ValueError, struct.error):
                valid = False
    judge.check("step_screenshot_package", valid)


def state_checks(judge, trajectory, before, after):
    task = judge.task
    allowed = {4: {"users", "saved_homes"}, 5: {"users"}, 6: {"tours"},
               7: {"collections", "saved_homes"}, 10: {"saved_searches"},
               14: {"collections", "saved_homes"}, 15: {"inquiries"}}.get(task, set())
    for table in TABLES:
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
        judge.check("one_target_save", len(saved) == 1 and saved[0]["user_id"] == uid and saved[0]["listing_id"] == 36)
        judge.check("saved_homes_confirmation", visited(trajectory, "/saved"))
    elif task == 5:
        judge.check("no_new_users", not only_new(before, after, "users"))
        judge.check("phone_changed", uid in before["users"] and before["users"][uid]["phone"] != "(415) 555-0199")
        judge.check("account_overview_confirmation", visited(trajectory, "/account"))
    elif task == 6:
        new = only_new(before, after, "tours")
        expected = {"user_id": uid, "listing_id": 110, "requested_date": "2026-07-12", "requested_time": "11:00 AM", "tour_type": "in-person", "status": "requested"}
        judge.check("one_exact_tour", len(new) == 1 and all(new[0][key] == value for key, value in expected.items()))
        judge.check("tours_confirmation", visited(trajectory, "/tours"))
    elif task in {7, 14}:
        new = only_new(before, after, "collections")
        members = {252, 253} if task == 7 else {233}
        name = "Austin top picks" if task == 7 else "Austin garage picks"
        valid = False
        if len(new) == 1:
            collection = new[0]
            ids = json.loads(collection["listing_ids_json"])
            valid = (collection["user_id"] == uid and collection["name"] == name
                     and len(ids) == len(members) and set(ids) == members and bool(collection["share_token"]))
            path = f'/collections/share/{collection["share_token"]}' if task == 7 else f'/collections/{collection["id"]}'
            judge.check("collection_confirmation", visited(trajectory, path))
            if task == 7:
                judge.check("answer_share_token", bool(re.search(r"(?<![\w-])" + re.escape(collection["share_token"]) + r"(?![\w-])", trajectory["final_answer"])))
        judge.check("one_exact_collection", valid)
        saves = only_new(before, after, "saved_homes")
        judge.check("optional_target_saves_only", all(row["user_id"] == uid and row["listing_id"] in members for row in saves))
    elif task == 10:
        new = only_new(before, after, "saved_searches")
        valid = (len(new) == 1 and new[0]["user_id"] == uid and new[0]["name"] == "Boston condos 3BR"
                 and criteria_ok(json.loads(new[0]["criteria_json"])))
        judge.check("one_exact_saved_search", valid)
        judge.check("reopened_saved_search", transitioned(trajectory, "/saved-searches", "/search", criteria_ok))
    elif task == 15:
        new = only_new(before, after, "inquiries")
        expected = {"user_id": uid, "listing_id": 38, "agent_id": LISTINGS[38]["agent_id"],
                    "subject": "Following up on my tour", "message": "Please confirm the date and time for this tour."}
        judge.check("one_exact_inquiry", len(new) == 1 and all(new[0][key] == value for key, value in expected.items()))
        judge.check("tour_and_inquiry_ui", visited(trajectory, "/tours") and visited(trajectory, "/inquiry/38"))


def detail_path(listing_id):
    return "/listing/" + LISTINGS[listing_id]["slug"]


def answer_checks(judge, trajectory):
    task = judge.task
    text = trajectory["final_answer"] or ""
    if task == 7:
        return  # generated token is checked against this run's after snapshot
    if task == 5:
        judge.check("answer_phone", re.sub(r"\D", "", text).find("4155550199") >= 0)
        judge.check("answer_existing_location", phrase(text, "San Francisco") and (phrase(text, "CA") or phrase(text, "California")))
        return
    if task == 10:
        judge.check("answer_saved_criteria", phrase(text, "Boston") and phrase(text, "for sale")
                    and (phrase(text, "Condo") or phrase(text, "Condos"))
                    and scalar(text, 3, "beds"))
        return
    listing = LISTINGS[TARGETS[task]]
    if task not in {4, 6, 12}:
        judge.check("answer_target_address", address_matches(text, listing))
    if task not in {4, 6, 14, 15}:
        judge.check("target_property_details", visited(trajectory, detail_path(listing["id"])))
    fields = {0: ["year_built", "mls_number"], 1: ["price", "year_built", "mls_number"],
              3: ["year_built", "agent_name"], 4: ["price", "property_type"], 6: ["year_built"],
              11: ["beds", "sqft", "year_built", "mls_number"], 12: ["year_built", "agent_name", "agent_email"],
              13: ["beds", "sqft", "year_built", "agent_name"], 14: ["mls_number"],
              15: ["agent_name"], 16: ["year_built", "agent_name"], 17: ["agent_name", "year_built"]}
    for field in fields.get(task, []):
        expected = listing[field]
        ok = scalar(text, expected, "year" if field == "year_built" else field) if isinstance(expected, (int, float)) else phrase(text, expected)
        if field == "agent_email":
            ok = bool(re.search(r"(?<![\w.@+-])" + re.escape(expected) + r"(?![\w@+-]|\.[\w])", norm(text)))
        judge.check("answer_" + field, ok)
    if task == 2:
        # The task explicitly requests one line per home, so row association is
        # meaningful. Markdown tables and ordinary sentences both work.
        rows = text.splitlines()
        for listing_id in (115, 110):
            item = LISTINGS[listing_id]
            judge.check(f"details_{listing_id}", visited(trajectory, detail_path(listing_id)))
            judge.check(f"associated_facts_{listing_id}", any(address_matches(row, item)
                        and scalar(row, item["price"], "price") and scalar(row, item["sqft"], "sqft")
                        and scalar(row, item["year_built"], "year") for row in rows))
        judge.check("lower_ratio_selection", any(address_matches(row, LISTINGS[110])
                    and re.search(r"\b(lower|lowest|cheaper|less expensive)\b", norm(row))
                    and not re.search(r"\bnot\b", norm(row)) for row in rows))
    if task == 6:
        judge.check("answer_tour_status", requested_tour_status(text))
    if task == 12:
        judge.check("answer_rounded_price_per_sqft", scalar(text, 1090, "ratio"))
        judge.check("followed_agent_profile", transitioned(trajectory, detail_path(89), "/agents/" + listing["agent_slug"]))
    if task == 15:
        judge.check("answer_tour_date", any(value in norm(text) for value in ("2026-06-06", "june 6, 2026", "june 6 2026", "6 june 2026", "06/06/2026")))


def grade(task, run_dir, initial_db, after_db):
    judge = Checks(task)
    try:
        trajectory = json.loads((Path(run_dir) / "trajectory.json").read_text())
        package_checks(judge, trajectory, run_dir)
        before, after = snapshot(initial_db), snapshot(after_db)
        state_checks(judge, trajectory, before, after)
        answer_checks(judge, trajectory)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, sqlite3.Error) as error:
        judge.check("valid_inputs", False, f"{type(error).__name__}: {error}")
    return judge.result()


def main(task):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default="wh-review")
    parser.add_argument("--no_llm", action="store_true", help="Accepted for harness compatibility; grading is always deterministic")
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
