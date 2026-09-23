#!/usr/bin/env python3
"""Deterministic verification for the NBA mirror's frozen task runs."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


READ_ONLY = set(range(18))
EXPECTED_TABLES = {
    "articles", "cart_items", "favorites", "games", "order_items", "orders",
    "players", "products", "teams", "ticket_requests", "users",
}


def norm(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def words(value) -> str:
    return re.sub(r"[^\w.+&'-]+", " ", norm(value)).strip()


def affirmative_phrase(text, expected) -> bool:
    normalized = words(text)
    wanted = words(expected)
    matches = list(re.finditer(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)", normalized))
    if not matches:
        return False
    match = matches[-1]
    before = re.split(r"[.!?;:\n]+|\b(?:but|however|instead)\b", normalized[:match.start()])[-1]
    after = normalized[match.end():]
    return not re.search(r"\b(?:not|no|never|without|incorrect|wrong)\b", before) and not re.match(
        r"\s*(?:is|was|are|were)?\s*(?:not|incorrect|wrong)\b", after
    )


def loopback(hostname: str | None) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname or "").is_loopback
    except ValueError:
        return False


def recorded_urls(trajectory: dict) -> list[str]:
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


def local_url(url: str, trajectory: dict) -> bool:
    try:
        target = urlsplit(url)
        start = urlsplit(trajectory.get("start_url", ""))
        return (
            target.scheme == start.scheme == "http"
            and loopback(start.hostname)
            and loopback(target.hostname)
            and target.port == start.port
            and not target.username
            and not target.password
        )
    except (TypeError, ValueError):
        return False


def query_matches(url: str, expected: dict[str, str]) -> bool:
    params = parse_qs(urlsplit(url).query, keep_blank_values=True)
    return all(len(params.get(key, [])) == 1 and norm(params[key][0]) == norm(value) for key, value in expected.items())


def requirement_matches(url: str, requirement: tuple[str, dict[str, str]]) -> bool:
    path, query = requirement
    actual = unquote(urlsplit(url).path).rstrip("/") or "/"
    wanted = path.rstrip("/") or "/"
    return actual == wanted and query_matches(url, query)


def visited_in_order(trajectory: dict, requirements: list[tuple[str, dict[str, str]]]) -> bool:
    urls = [url for url in recorded_urls(trajectory) if local_url(url, trajectory)]
    cursor = 0
    for requirement in requirements:
        for index in range(cursor, len(urls)):
            if requirement_matches(urls[index], requirement):
                cursor = index + 1
                break
        else:
            return False
    return True


def snapshot(path: Path) -> tuple[list[tuple], dict[str, list[tuple]]]:
    resolved = Path(path).resolve(strict=True)
    with sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if tables != EXPECTED_TABLES:
            raise ValueError(f"unexpected NBA database tables: {sorted(tables)}")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise ValueError("foreign-key integrity failed")
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        rows = {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall() for table in sorted(tables)}
    return schema, rows


def resolve_db(trajectory: dict, explicit: Path | str | None, kind: str) -> Path | None:
    if explicit:
        return Path(explicit)
    field = "initial_state" if kind == "initial" else "after_state"
    value = trajectory.get(field, {})
    path = value.get("path") if isinstance(value, dict) else None
    return Path(path) if path else None


def fetch_container_db(container: str, kind: str, target_dir: Path) -> Path | None:
    source_dir = "instance_seed" if kind == "initial" else "instance"
    target = target_dir / f"{kind}.db"
    try:
        result = subprocess.run(
            ["docker", "cp", f"{container}:/opt/WebSyn/nba/{source_dir}/nba.db", str(target)],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    return target if result.returncode == 0 and target.is_file() else None


ROUTES = {
    0: [("/players", {"position": "G", "team": "mavericks"}), ("/players/luka-doncic", {})],
    1: [("/games", {})],
    2: [("/games", {})],
    3: [("/schedule", {"season_type": "Playoffs"})],
    4: [("/standings", {}), ("/teams/thunder", {})],
    5: [("/stats/players", {"stat": "bpg"})],
    6: [("/stats/teams", {"sort": "point_diff"})],
    7: [("/teams", {}), ("/teams/clippers", {})],
    8: [("/teams/thunder", {}), ("/teams/thunder/roster", {}), ("/players/chet-holmgren", {})],
    9: [("/draft", {}), ("/news/mock-draft-board-shifts-after-combine-measurements", {})],
    10: [("/draft", {})],
    11: [("/fantasy", {})],
    12: [("/stats", {})],
    13: [("/search", {"q": "spacing"}), ("/news/bucks-focus-on-half-court-spacing", {})],
    14: [("/watch", {})],
    15: [("/tickets", {})],
    16: [("/store", {"category": "T-Shirts"}), ("/store/la-clippers-intuit-dome-opening-tee", {})],
    17: [("/store", {"category": "Hoodies"}), ("/store/dallas-mavericks-statement-hoodie", {})],
    18: [("/login", {}), ("/store", {"category": "Jerseys"}), ("/store/los-angeles-lakers-icon-swingman-jersey", {}), ("/cart", {}), ("/checkout", {})],
    19: [("/teams", {}), ("/standings", {}), ("/login", {}), ("/account/edit", {}), ("/account", {})],
}


ANSWER_PHRASES = {
    0: ["Luka Doncic", "PPG", "33.9", "RPG", "9.2", "APG", "9.8"],
    1: ["Detroit Pistons", "Cleveland Cavaliers", "Now TV", "San Antonio Spurs", "Minnesota Timberwolves", "Viu TV"],
    2: ["Detroit Pistons", "Cleveland Cavaliers", "Donovan Mitchell", "26.6"],
    3: ["Cleveland Cavaliers", "New York Knicks", "Madison Square Garden", "New York", "Game 1"],
    4: ["Oklahoma City Thunder", "Paycom Center", "Mark Daigneault"],
    5: ["Victor Wembanyama", "3.6", "Anthony Davis", "Chet Holmgren", "2.3", "1.3"],
    6: ["Boston Celtics", "64", "18", "120.6", "109.2", "+11.4"],
    7: ["LA Clippers", "Tyronn Lue", "51-31"],
    8: ["Chet Holmgren", "C-F", "7-1", "208", "Gonzaga", "USA", "2.3"],
    9: ["pressure", "multiple positions"],
    10: ["June 23", "2026", "June 24"],
    11: ["Tyrese Haliburton", "10.9", "Luka Doncic", "9.8"],
    12: ["Points", "Joel Embiid", "Total Assists", "Tyrese Haliburton"],
    13: ["Antetokounmpo", "rim pressure", "Lillard", "range"],
    14: ["Lakers-Warriors condensed game", "Los Angeles Lakers", "Golden State Warriors"],
    15: ["Oklahoma City Thunder", "Dallas Mavericks", "American Airlines Center", "155"],
    16: ["LA Clippers Intuit Dome Opening Tee", "LA Clippers", "red", "32.99", "arena launch graphic", "unisex fit", "soft cotton"],
    17: ["Dallas Mavericks Statement Hoodie", "74.99", "fleece lining", "front pouch pocket", "screen-printed team mark"],
    18: ["259.78"],
    19: ["Dallas Mavericks", "9090"],
}


BINDINGS = {
    0: [("Luka Doncic", ["33.9", "9.2", "9.8"])],
    1: [("Detroit Pistons", ["Cleveland Cavaliers", "Now TV"]), ("San Antonio Spurs", ["Minnesota Timberwolves", "Viu TV"])],
    2: [("Donovan Mitchell", ["26.6"])],
    5: [("Victor Wembanyama", ["3.6"]), ("Anthony Davis", ["2.3"]), ("Chet Holmgren", ["2.3"])],
    6: [("Boston Celtics", ["64", "18", "120.6", "109.2", "+11.4"])],
    7: [("LA Clippers", ["Tyronn Lue", "51-31"])],
    8: [("Chet Holmgren", ["C-F", "7-1", "208", "Gonzaga", "USA", "2.3"])],
    11: [("Tyrese Haliburton", ["10.9"]), ("Luka Doncic", ["9.8"])],
    12: [("Points", ["Joel Embiid"]), ("Total Assists", ["Tyrese Haliburton"])],
    15: [("Oklahoma City Thunder", ["Dallas Mavericks", "American Airlines Center", "155"])],
    16: [("LA Clippers Intuit Dome Opening Tee", ["LA Clippers", "red", "32.99", "arena launch graphic", "unisex fit", "soft cotton"])],
    17: [("Dallas Mavericks Statement Hoodie", ["74.99", "fleece lining", "front pouch pocket", "screen-printed team mark"])],
}


def bound_values(text: str, anchor: str, values: list[str], window: int = 260) -> bool:
    normalized = words(text)
    match = re.search(r"(?<!\w)" + re.escape(words(anchor)) + r"(?!\w)", normalized)
    if not match:
        return False
    nearby = normalized[max(0, match.start() - 40):match.end() + window]
    return all(words(value) in nearby for value in values)


def check_screenshots(run_dir: Path, trajectory: dict) -> bool:
    screenshots = run_dir / "screenshots"
    refs = [step.get("screenshot_after") for step in trajectory.get("steps", []) if step.get("screenshot_after")]
    if not refs:
        return False
    for reference in refs:
        path = screenshots / Path(reference).name
        if not path.is_file() or path.stat().st_size < 32 or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            return False
    return True


def table_subset(rows: dict[str, list[tuple]], excluded: set[str]) -> dict[str, list[tuple]]:
    return {table: data for table, data in rows.items() if table not in excluded}


def state_check(task: int, before: dict[str, list[tuple]], after: dict[str, list[tuple]]) -> tuple[bool, str]:
    if task in READ_ONLY:
        return before == after, "read-only task preserves every table"
    if task == 18:
        if table_subset(before, {"cart_items"}) != table_subset(after, {"cart_items"}):
            return False, "tables other than cart_items changed"
        with_rows = after["cart_items"]
        if before["cart_items"]:
            return False, "initial cart is not empty"
        if len(with_rows) != 1:
            return False, f"expected one cart row, observed {len(with_rows)}"
        return True, "only one cart row changed; row identity checked separately"
    if task == 19:
        if table_subset(before, {"users"}) != table_subset(after, {"users"}):
            return False, "tables other than users changed"
        return True, "only users table changed; target fields checked separately"
    return False, "unknown state contract"


def sqlite_row(path: Path, sql: str, params=()):
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None


def stateful_detail(task: int, initial: Path, after: Path) -> tuple[bool, str]:
    if task == 18:
        before_count = sqlite_row(initial, "SELECT COUNT(*) AS count FROM cart_items c JOIN users u ON u.id=c.user_id WHERE u.email=?", ("alice.j@test.com",))["count"]
        rows = []
        with sqlite3.connect(after) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(
                "SELECT p.slug,c.size,c.quantity FROM cart_items c JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id WHERE u.email=? ORDER BY c.id",
                ("alice.j@test.com",),
            )]
            orders = connection.execute("SELECT COUNT(*) FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=?", ("alice.j@test.com",)).fetchone()[0]
        with sqlite3.connect(initial) as connection:
            initial_orders = connection.execute("SELECT COUNT(*) FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=?", ("alice.j@test.com",)).fetchone()[0]
        ok = before_count == 0 and rows == [{"slug": "los-angeles-lakers-icon-swingman-jersey", "size": "XL", "quantity": 2}] and orders == initial_orders
        return ok, f"initial_cart={before_count}, after_cart={rows}, orders={initial_orders}->{orders}"
    if task == 19:
        before = sqlite_row(initial, "SELECT * FROM users WHERE email=?", ("alice.j@test.com",))
        after_row = sqlite_row(after, "SELECT * FROM users WHERE email=?", ("alice.j@test.com",))
        if not before or not after_row:
            return False, "benchmark user missing"
        with sqlite3.connect(initial) as before_db, sqlite3.connect(after) as after_db:
            other_before = before_db.execute(
                "SELECT * FROM users WHERE email<>? ORDER BY id", ("alice.j@test.com",)
            ).fetchall()
            other_after = after_db.execute(
                "SELECT * FROM users WHERE email<>? ORDER BY id", ("alice.j@test.com",)
            ).fetchall()
        if other_before != other_after:
            return False, "a non-target user changed"
        changed = {key for key in before if before[key] != after_row[key]}
        ok = changed == {"favorite_team_slug", "payment_last4"} and after_row["favorite_team_slug"] == "mavericks" and after_row["payment_last4"] == "9090"
        return ok, f"changed={sorted(changed)}, favorite_team={after_row['favorite_team_slug']}, payment_last4={after_row['payment_last4']}"
    return True, "read-only"


def grade(
    task: int,
    run_dir: Path | str,
    initial_db: Path | str | None = None,
    after_db: Path | str | None = None,
    container: str = "",
) -> dict:
    run_dir = Path(run_dir)
    trajectory = json.loads((run_dir / "trajectory.json").read_text(encoding="utf-8"))
    evidence = []

    def check(name: str, condition: bool, detail: str) -> None:
        evidence.append({"check": name, "pass": bool(condition), "detail": detail})

    check("task_identity", trajectory.get("task_id") == f"NBA--{task}", f"observed={trajectory.get('task_id')!r}")
    check("terminated", trajectory.get("terminated") is True and trajectory.get("termination_reason") == "agent_done", f"terminated={trajectory.get('terminated')}, reason={trajectory.get('termination_reason')}")
    urls = recorded_urls(trajectory)
    check("local_origin", bool(urls) and all(local_url(url, trajectory) for url in urls), f"urls={urls}")
    check("required_navigation", visited_in_order(trajectory, ROUTES[task]), f"requirements={ROUTES[task]}")
    check("step_screenshot_package", check_screenshots(run_dir, trajectory), "every recorded after-shot exists and is a PNG")
    answer = trajectory.get("final_answer") or ""
    check("nonempty_answer", bool(answer.strip()), f"answer={answer!r}")
    phrases_ok = all(affirmative_phrase(answer, phrase) for phrase in ANSWER_PHRASES[task])
    check("answer_facts", phrases_ok, f"required={ANSWER_PHRASES[task]}, answer={answer!r}")
    bindings_ok = all(bound_values(answer, anchor, values) for anchor, values in BINDINGS.get(task, []))
    check("answer_bindings", bindings_ok, f"bindings={BINDINGS.get(task, [])}")

    initial = resolve_db(trajectory, initial_db, "initial")
    after = resolve_db(trajectory, after_db, "after")
    temporary = None
    if (not initial or not initial.is_file() or not after or not after.is_file()) and container:
        temporary = tempfile.TemporaryDirectory()
        temporary_path = Path(temporary.name)
        initial = initial if initial and initial.is_file() else fetch_container_db(container, "initial", temporary_path)
        after = after if after and after.is_file() else fetch_container_db(container, "after", temporary_path)
    if not initial or not after or not initial.is_file() or not after.is_file():
        check("bound_state_snapshots", False, f"initial={initial}, after={after}")
    else:
        try:
            before_schema, before = snapshot(initial)
            after_schema, after_rows = snapshot(after)
            check("schema_unchanged", before_schema == after_schema, "SQLite schema is unchanged")
            ok, detail = state_check(task, before, after_rows)
            check("allowed_database_delta", ok, detail)
            ok, detail = stateful_detail(task, initial, after)
            check("stateful_target", ok, detail)
        except Exception as error:
            check("bound_state_snapshots", False, f"{type(error).__name__}: {error}")

    if temporary:
        temporary.cleanup()

    passed = all(item["pass"] for item in evidence)
    reason = "" if passed else next(item["check"] for item in evidence if not item["pass"])
    return {"task_id": f"NBA--{task}", "pass": passed, "reason": reason, "evidence": evidence}


def main(task: int) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", nargs="?", default="False")
    args = parser.parse_args()
    result = grade(task, args.run_dir, args.initial_db, args.after_db, args.container)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)
