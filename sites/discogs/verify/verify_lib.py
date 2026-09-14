#!/usr/bin/env python3
"""Deterministic grading helpers for the Discogs task set.

Read-only tasks require both the relevant on-site navigation and a grounded
final answer. Stateful tasks additionally require frozen SQLite snapshots in
the run directory (``initial_state.db`` and ``after_state.db``); live mutable
container state is deliberately never used as grading evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import parse_qs, urlparse


ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
# The mirror is served from a loopback origin. Which host port the operator publishes
# is an operational detail (the repository's own guide runs the same sites on 41000+),
# so grading must not depend on it. What must hold is that every recorded step points at
# one loopback origin: that is what stops a trajectory from citing an outside site or
# mixing the mirror with another local service. An exact origin can still be pinned with
# the WHR_EXPECTED_ORIGIN environment variable when a grader wants that.

READ_ONLY_SPECS = {
    0: {
        "paths": ("/release/8031582", "/release/3376357"),
        "tokens": ("1966", "242", "rs 9242", "11:24"),
    },
    1: {
        "paths": ("/release/7852399", "/release/7251385"),
        "tokens": ("1986", "cd", "cp32-5244", "bellarosa", "4:15"),
    },
    2: {
        "paths": ("/release/4337598", "/release/2379219"),
        "tokens": ("japan", "2007", "ucco-9038", "joe tarantino"),
        "number": 7,
    },
    3: {
        "paths": ("/release/9732909", "/release/8837214"),
        # The live-faithful search card shows the full format description, so the
        # Dolby System / Repress split is readable from the results page. The task now
        # asks for identifier facts that only the detail pages carry.
        "tokens": ("9732909", "8837214", "impuesto de lujo", "6649", "9417-1978"),
        "attribution": (("6649", "9732909", "8837214"),),
    },
    4: {
        "paths": ("/release/35846581",),
        "tokens": ("colin greenwood", "as the waters cover the sea"),
    },
    5: {
        "paths": ("/marketplace", "/release/19878259"),
        "tokens": ("kelly blue", "wynton kelly", "kosmische", "8.27", ("usd", "us$"), "smj-6114", "srs-6059"),
        "marketplace_filters": True,
    },
    6: {
        "paths": ("/lists", "/list/3", "/release/4627265"),
        "tokens": ("jeff beck", "italy", "igda 1063/64"),
    },
}


class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.ok = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "") -> bool:
        if condition:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({
            "task_id": self.task_id,
            "pass": self.ok,
            "reason": self.reason,
            "evidence": self.evidence,
        }, indent=2))
        raise SystemExit(0 if self.ok else 1)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip()


def trajectory_urls(trajectory: dict) -> list[str]:
    urls = []
    for step in trajectory.get("steps", []):
        for key in ("url", "url_after"):
            if step.get(key):
                urls.append(step[key])
    return urls


def is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "http"
            and parsed.hostname in ALLOWED_HOSTS
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def visited_path(trajectory: dict, expected: str) -> bool:
    return any(
        is_allowed_url(url) and urlparse(url).path == expected
        for url in trajectory_urls(trajectory)
    )


def visited_paths_in_order(trajectory: dict, expected_paths: tuple[str, ...]) -> bool:
    urls = trajectory_urls(trajectory)
    cursor = 0
    for expected in expected_paths:
        for index in range(cursor, len(urls)):
            url = urls[index]
            if is_allowed_url(url) and urlparse(url).path == expected:
                cursor = index + 1
                break
        else:
            return False
    return True


def action_mentions(trajectory: dict, text: str) -> bool:
    needle = normalize(text)
    return any(needle in normalize(json.dumps({
        "action": step.get("action"),
        "params": step.get("params"),
        "result": step.get("action_result"),
    }, ensure_ascii=False)) for step in trajectory.get("steps", []))


def final_answer(trajectory: dict) -> str:
    return (trajectory.get("final_answer") or "").strip()


NEGATION_WORDS = {
    "not", "no", "never", "without", "isn't", "isnt", "aren't", "arent",
    "wasn't", "wasnt", "doesn't", "doesnt", "didn't", "didnt",
}


def preceding_clause_is_negated(value: str, start: int) -> bool:
    prefix = value[:start]
    clause = re.split(r"(?:[.!?;:\n]+|\b(?:and|but|however|instead)\b)", prefix)[-1]
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", clause)[-6:]
    return any(word in NEGATION_WORDS for word in words)


def affirmed(text: str, token: str) -> bool:
    value = normalize(text)
    target = normalize(token)
    pattern = re.escape(target)
    if target and target[0].isalnum():
        pattern = rf"(?<!\w){pattern}"
    if target and target[-1].isalnum():
        pattern = rf"{pattern}(?!\w)"
    for match in re.finditer(pattern, value):
        if not preceding_clause_is_negated(value, match.start()):
            return True
    return False


def contains_number(text: str, number: int) -> bool:
    value = normalize(text)
    patterns = [rf"(?<!\d){number}(?!\d)"]
    if number == 7:
        patterns.append(r"\bseven\b")
    return any(
        not preceding_clause_is_negated(value, match.start())
        for pattern in patterns
        for match in re.finditer(pattern, value)
    )


def associated(text: str, left: str, right: str,
               associations: tuple[tuple[str, str], ...]) -> bool:
    value = normalize(text)
    left, right = normalize(left), normalize(right)
    starts_left = [match.start() for match in re.finditer(re.escape(left), value)]
    candidates = [
        (normalize(candidate), match.start())
        for _, candidate in associations
        for match in re.finditer(re.escape(normalize(candidate)), value)
    ]
    for left_start in starts_left:
        if not candidates:
            continue
        distance, nearest = min(
            (abs(left_start - right_start), candidate)
            for candidate, right_start in candidates
        )
        if nearest == right and distance <= 100:
            return True
    return False


def attributed_to(text: str, value: str, target: str, other: str) -> bool:
    """True when `value` is attributed to `target` rather than to `other`.

    Natural phrasing names the edition before the fact ("release X lists ... 6649"),
    so the nearest identifier *preceding* the value decides the binding; if none
    precedes, the nearest one following it is used. A swapped attribution fails even
    though both identifiers appear in the answer.
    """
    body = normalize(text)
    value, target, other = normalize(value), normalize(target), normalize(other)
    value_starts = [m.start() for m in re.finditer(re.escape(value), body)]
    target_starts = [m.start() for m in re.finditer(re.escape(target), body)]
    other_starts = [m.start() for m in re.finditer(re.escape(other), body)]
    if not value_starts or not target_starts:
        return False
    for start in value_starts:
        before = ([(start - s, True) for s in target_starts if s < start]
                  + [(start - s, False) for s in other_starts if s < start])
        if before:
            if min(before)[1]:
                return True
            continue
        after = ([(s - start, True) for s in target_starts if s > start]
                 + [(s - start, False) for s in other_starts if s > start])
        if after and min(after)[1]:
            return True
    return False


def step_origins(trajectory: dict) -> list[str]:
    """Scheme://host:port for every recorded step URL, in order."""
    origins = []
    for url in trajectory_urls(trajectory):
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc:
            origins.append(f"{parsed.scheme}://{parsed.netloc}")
    return origins


def check_origin_discipline(trajectory: dict, judge: Judge) -> None:
    """Every step must sit on one loopback origin, and none may sit off it."""
    urls = trajectory_urls(trajectory)
    judge.check("trajectory_has_urls", bool(urls), f"count={len(urls)}")
    foreign = sorted({u for u in urls if not is_allowed_url(u)})
    judge.check("no_foreign_origins", not foreign, f"foreign={foreign[:5]}")
    origins = sorted(set(step_origins(trajectory)))
    judge.check("single_origin", len(origins) == 1, f"origins={origins}")
    expected = os.environ.get("WHR_EXPECTED_ORIGIN", "").rstrip("/")
    if expected:
        judge.check("origin_matches_expected", origins == [expected],
                    f"expected={expected} actual={origins}")


def marketplace_filters_used(trajectory: dict) -> bool:
    for url in trajectory_urls(trajectory):
        if not is_allowed_url(url):
            continue
        parsed = urlparse(url)
        if parsed.path != "/marketplace":
            continue
        query = parse_qs(parsed.query)
        if (query.get("media") == ["Near Mint (NM or M-)"]
                and query.get("currency", ["USD"]) == ["USD"]
                and query.get("sort", ["price_asc"]) == ["price_asc"]):
            return True
    return False


def verify_read_only(index: int, trajectory: dict, judge: Judge) -> None:
    spec = READ_ONLY_SPECS[index]
    answer = final_answer(trajectory)
    judge.check("final_answer_present", bool(answer), f"length={len(answer)}")
    for path in spec["paths"]:
        judge.check(f"visited_{path}", visited_path(trajectory, path), path)
    missing = []
    for token in spec["tokens"]:
        alternatives = token if isinstance(token, tuple) else (token,)
        if not any(affirmed(answer, option) for option in alternatives):
            missing.append(" | ".join(alternatives))
    judge.check("grounded_answer_fields", not missing, f"missing={missing}")
    if "number" in spec:
        judge.check("requested_count", contains_number(answer, spec["number"]), f"expected={spec['number']}")
    associations = spec.get("associations", ())
    for left, right in associations:
        judge.check(
            f"bind_{left}_{right}",
            associated(answer, left, right, associations),
            "expected descriptor is nearest to its release ID",
        )
    for value, target, other in spec.get("attribution", ()):
        judge.check(
            f"bind_{target}_{value}",
            attributed_to(answer, value, target, other),
            f"'{value}' must be attributed to {target}, not {other}",
        )
    if spec.get("marketplace_filters"):
        judge.check("marketplace_filters", marketplace_filters_used(trajectory),
                    "USD + Near Mint + price ascending")


def open_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def resolve_snapshot(run_dir: Path, explicit: str, names: tuple[str, ...]) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    for name in names:
        path = run_dir / name
        if path.is_file():
            return path
    return None


def table_map(db: sqlite3.Connection, table: str) -> dict[int, dict]:
    rows = db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    return {row["id"]: dict(row) for row in rows}


def database_schema(db: sqlite3.Connection) -> list[tuple]:
    return [
        tuple(row)
        for row in db.execute(
            """SELECT type,name,tbl_name,sql FROM sqlite_master
               WHERE name NOT LIKE 'sqlite_%'
               ORDER BY type,name"""
        ).fetchall()
    ]


def database_tables(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name NOT LIKE 'sqlite_%'"""
        ).fetchall()
    }


def quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_rows(db: sqlite3.Connection, table: str) -> list[tuple]:
    columns = [row[1] for row in db.execute(f"PRAGMA table_info({quoted(table)})")]
    order = ",".join(quoted(column) for column in columns)
    query = f"SELECT * FROM {quoted(table)}"
    if order:
        query += f" ORDER BY {order}"
    return [tuple(row) for row in db.execute(query).fetchall()]


def table_delta(before: sqlite3.Connection, after: sqlite3.Connection, table: str) -> dict:
    old, new = table_map(before, table), table_map(after, table)
    return {
        "added": [new[key] for key in new.keys() - old.keys()],
        "removed": [old[key] for key in old.keys() - new.keys()],
        "changed": [(old[key], new[key]) for key in old.keys() & new.keys() if old[key] != new[key]],
    }


def changed_tables(before: sqlite3.Connection, after: sqlite3.Connection) -> set[str]:
    before_tables = database_tables(before)
    after_tables = database_tables(after)
    common = before_tables & after_tables
    changed = {
        table
        for table in common
        if table_rows(before, table) != table_rows(after, table)
    }
    return changed | (before_tables ^ after_tables)


def one(db: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = db.execute(sql, params).fetchone()
    return dict(row) if row else None


def changed_columns(old: dict, new: dict) -> set[str]:
    return {key for key in old if old[key] != new[key]}


def check_navigation(trajectory: dict, judge: Judge, paths: tuple[str, ...]) -> None:
    for path in paths:
        judge.check(f"visited_{path}", visited_path(trajectory, path), path)


def check_allowed_tables(before: sqlite3.Connection, after: sqlite3.Connection,
                         judge: Judge, allowed: set[str]) -> None:
    schema_matches = database_schema(before) == database_schema(after)
    judge.check("database_schema_unchanged", schema_matches, "complete sqlite_master")
    changed = changed_tables(before, after)
    judge.check("no_unrequested_table_changes", changed <= allowed,
                f"changed={sorted(changed)} allowed={sorted(allowed)}")


def check_release_counter(before: sqlite3.Connection, after: sqlite3.Connection,
                          judge: Judge, discogs_id: int, field: str, delta: int) -> None:
    old = one(before, "SELECT * FROM releases WHERE discogs_id=?", (discogs_id,))
    new = one(after, "SELECT * FROM releases WHERE discogs_id=?", (discogs_id,))
    judge.check("target_release_exists", bool(old and new), f"discogs_id={discogs_id}")
    if not old or not new:
        return
    judge.check("release_counter_delta", new[field] == old[field] + delta,
                f"{field}: {old[field]} -> {new[field]}")
    judge.check("release_only_expected_counter_changed", changed_columns(old, new) == {field},
                f"columns={sorted(changed_columns(old, new))}")
    release_delta = table_delta(before, after, "releases")
    only_target_changed = (
        not release_delta["added"]
        and not release_delta["removed"]
        and len(release_delta["changed"]) == 1
        and release_delta["changed"][0][0]["discogs_id"] == discogs_id
        and release_delta["changed"][0][1]["discogs_id"] == discogs_id
    )
    judge.check("no_other_release_changes", only_target_changed, str(release_delta))


def verify_collection_add(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/release/3376357"))
    user = one(after, "SELECT id FROM users WHERE username='alice_crate'")
    release = one(after, "SELECT id FROM releases WHERE discogs_id=3376357")
    rows = after.execute("""SELECT c.* FROM collection_items c
        JOIN users u ON u.id=c.user_id JOIN releases r ON r.id=c.release_id
        WHERE u.username='alice_crate' AND r.discogs_id=3376357""").fetchall()
    old_rows = before.execute("""SELECT c.id FROM collection_items c
        JOIN users u ON u.id=c.user_id JOIN releases r ON r.id=c.release_id
        WHERE u.username='alice_crate' AND r.discogs_id=3376357""").fetchall()
    delta = table_delta(before, after, "collection_items")
    judge.check("precondition_absent", len(old_rows) == 0, f"rows={len(old_rows)}")
    judge.check("one_collection_row_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"], str(delta))
    good = len(rows) == 1 and rows[0]["folder"] == "Vinyl" and rows[0]["media_condition"] == "Near Mint (NM or M-)"
    judge.check("collection_row_matches", good, f"user={user} release={release}")
    check_release_counter(before, after, judge, 3376357, "have_count", 1)
    check_allowed_tables(before, after, judge, {"collection_items", "releases"})


def verify_wantlist_add(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/release/11554424"))
    rows = after.execute("""SELECT w.* FROM wantlist_items w
        JOIN users u ON u.id=w.user_id JOIN releases r ON r.id=w.release_id
        WHERE u.username='bob_vinyl' AND r.discogs_id=11554424""").fetchall()
    old_rows = before.execute("""SELECT w.id FROM wantlist_items w
        JOIN users u ON u.id=w.user_id JOIN releases r ON r.id=w.release_id
        WHERE u.username='bob_vinyl' AND r.discogs_id=11554424""").fetchall()
    delta = table_delta(before, after, "wantlist_items")
    judge.check("precondition_absent", len(old_rows) == 0, f"rows={len(old_rows)}")
    judge.check("one_wantlist_row_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"], str(delta))
    judge.check("wantlist_row_matches", len(rows) == 1 and rows[0]["min_grade"] == "Very Good (VG)", f"rows={len(rows)}")
    check_release_counter(before, after, judge, 11554424, "want_count", 1)
    check_allowed_tables(before, after, judge, {"wantlist_items", "releases"})


def verify_list_create(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/release/3376357", "/release/2379219", "/list/new"))
    user = one(after, "SELECT id FROM users WHERE username='dave_techno'")
    old = before.execute("SELECT id FROM lists WHERE title='Jazz Reissue Reference'").fetchall()
    rows = after.execute("SELECT * FROM lists WHERE title='Jazz Reissue Reference'").fetchall()
    list_delta = table_delta(before, after, "lists")
    item_delta = table_delta(before, after, "list_items")
    judge.check("precondition_absent", not old, f"rows={len(old)}")
    judge.check("one_list_added", len(list_delta["added"]) == 1 and not list_delta["removed"] and not list_delta["changed"], str(list_delta))
    good_list = (len(rows) == 1 and user and rows[0]["user_id"] == user["id"] and rows[0]["is_public"] == 1
                 and rows[0]["description"] == "Compare these two reissues before the next listening session.")
    judge.check("list_fields_match", bool(good_list), f"rows={len(rows)}")
    if rows:
        items = after.execute("""SELECT li.position, li.comment, r.discogs_id FROM list_items li
            JOIN releases r ON r.id=li.release_id WHERE li.list_id=? ORDER BY li.position""", (rows[0]["id"],)).fetchall()
        expected = [(1, "1966 US stereo edition", 3376357), (2, "2007 Japan CD edition", 2379219)]
        actual = [(row["position"], row["comment"], row["discogs_id"]) for row in items]
        judge.check("ordered_items_match", actual == expected, f"actual={actual}")
    else:
        judge.check("ordered_items_match", False, "new list missing")
    judge.check("two_list_items_added", len(item_delta["added"]) == 2 and not item_delta["removed"] and not item_delta["changed"], str(item_delta))
    check_allowed_tables(before, after, judge, {"lists", "list_items"})


def verify_listing_add(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/release/5741659", "/sell"))
    delta = table_delta(before, after, "listings")
    judge.check("one_listing_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"], str(delta))
    if delta["added"]:
        row = delta["added"][0]
        user = one(after, "SELECT username FROM users WHERE id=?", (row["user_id"],))
        release = one(after, "SELECT discogs_id FROM releases WHERE id=?", (row["release_id"],))
        good = (user and user["username"] == "bob_vinyl" and release and release["discogs_id"] == 5741659
                and row["price"] == 42.0 and row["currency"] == "GBP"
                and row["media_condition"] == "Very Good Plus (VG+)"
                and row["sleeve_condition"] == "Near Mint (NM or M-)"
                and row["shipping_from"] == "United Kingdom" and row["allow_offers"] == 1
                and row["comments"] == "Clean Spanish reissue; play-graded." and row["status"] == "For Sale")
        judge.check("listing_fields_match", bool(good), f"listing_id={row['id']}")
    else:
        judge.check("listing_fields_match", False, "listing missing")
    check_release_counter(before, after, judge, 5741659, "num_for_sale", 1)
    user_delta = table_delta(before, after, "users")
    one_seller_change = (
        not user_delta["added"]
        and not user_delta["removed"]
        and len(user_delta["changed"]) == 1
        and user_delta["changed"][0][0]["username"] == "bob_vinyl"
        and user_delta["changed"][0][1]["username"] == "bob_vinyl"
        and changed_columns(*user_delta["changed"][0]) == {"is_seller"}
        and user_delta["changed"][0][1]["is_seller"] == 1
    )
    judge.check("seller_flag_only", one_seller_change, str(user_delta))
    check_allowed_tables(before, after, judge, {"listings", "releases", "users"})


def verify_forum_post(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/forum/vinyl", "/thread/12", "/login"))
    judge.check(
        "returned_to_thread_after_login",
        visited_paths_in_order(
            trajectory, ("/forum/vinyl", "/thread/12", "/login", "/thread/12")
        ),
        "forum -> thread -> login -> thread",
    )
    delta = table_delta(before, after, "posts")
    judge.check("one_post_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"], str(delta))
    if delta["added"]:
        row = delta["added"][0]
        user = one(after, "SELECT username FROM users WHERE id=?", (row["user_id"],))
        good = (user and user["username"] == "carol_jazz" and row["thread_id"] == 12
                and row["body"] == "For acoustic jazz, I prefer MC for the extra detail in cymbals and upper mids.")
        judge.check("post_fields_match", bool(good), f"post_id={row['id']}")
    else:
        judge.check("post_fields_match", False, "post missing")
    check_allowed_tables(before, after, judge, {"posts"})


def verify_registration(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/register", "/settings", "/login"))
    judge.check("logout_action", action_mentions(trajectory, "log out"), "logout visible action recorded")
    judge.check(
        "new_credentials_entered",
        action_mentions(trajectory, "craterunner99")
        and action_mentions(trajectory, "discogs2026"),
        "new username and password appear in recorded input actions",
    )
    judge.check(
        "login_succeeded_after_logout",
        visited_paths_in_order(
            trajectory, ("/register", "/settings", "/", "/login", "/")
        ),
        "registration -> settings -> logout -> login -> authenticated destination",
    )
    delta = table_delta(before, after, "users")
    judge.check("one_user_added", len(delta["added"]) == 1 and not delta["removed"] and not delta["changed"], str(delta))
    if delta["added"]:
        row = delta["added"][0]
        good = (row["username"] == "craterunner99" and row["email"] == "craterunner99@test.com"
                and row["location"] == "Portland, USA" and row["real_name"] == "Casey Runner"
                and row["bio"] == "Digging since 2010." and row["password_hash"]
                and row["password_hash"] != "discogs2026")
        judge.check("user_fields_match", bool(good), f"username={row['username']}")
    else:
        judge.check("user_fields_match", False, "user missing")
    check_allowed_tables(before, after, judge, {"users"})


def verify_collection_remove(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/user/alice_crate/collection"))
    folder_ok = any(urlparse(url).path == "/user/alice_crate/collection"
                    and parse_qs(urlparse(url).query).get("folder") == ["Vinyl"]
                    for url in trajectory_urls(trajectory))
    judge.check("vinyl_folder_used", folder_ok, "folder=Vinyl")
    delta = table_delta(before, after, "collection_items")
    judge.check("one_collection_row_removed", len(delta["removed"]) == 1 and not delta["added"] and not delta["changed"], str(delta))
    if delta["removed"]:
        row = delta["removed"][0]
        user = one(before, "SELECT username FROM users WHERE id=?", (row["user_id"],))
        release = one(before, "SELECT discogs_id FROM releases WHERE id=?", (row["release_id"],))
        judge.check("removed_target_matches", bool(user and user["username"] == "alice_crate"
                    and release and release["discogs_id"] == 20271358), f"item_id={row['id']}")
    else:
        judge.check("removed_target_matches", False, "removed row missing")
    check_release_counter(before, after, judge, 20271358, "have_count", -1)
    check_allowed_tables(before, after, judge, {"collection_items", "releases"})


def verify_rating_review(before, after, trajectory, judge):
    check_navigation(trajectory, judge, ("/login", "/release/35846581"))
    rating_delta = table_delta(before, after, "ratings")
    review_delta = table_delta(before, after, "reviews")
    judge.check("one_rating_added", len(rating_delta["added"]) == 1 and not rating_delta["removed"] and not rating_delta["changed"], str(rating_delta))
    judge.check("one_review_added", len(review_delta["added"]) == 1 and not review_delta["removed"] and not review_delta["changed"], str(review_delta))
    user = one(after, "SELECT id FROM users WHERE username='dave_techno'")
    release = one(after, "SELECT id FROM releases WHERE discogs_id=35846581")
    if rating_delta["added"] and review_delta["added"] and user and release:
        rating, review = rating_delta["added"][0], review_delta["added"][0]
        judge.check("rating_fields_match", rating["user_id"] == user["id"] and rating["release_id"] == release["id"] and rating["value"] == 4, f"rating_id={rating['id']}")
        judge.check("review_fields_match", review["user_id"] == user["id"] and review["release_id"] == release["id"] and review["rating"] == 4 and review["body"] == "The live arrangements reward a focused listen from start to finish.", f"review_id={review['id']}")
    else:
        judge.check("rating_fields_match", False, "required rows missing")
        judge.check("review_fields_match", False, "required rows missing")
    old_release = one(before, "SELECT * FROM releases WHERE discogs_id=35846581")
    new_release = one(after, "SELECT * FROM releases WHERE discogs_id=35846581")
    changes = changed_columns(old_release, new_release)
    aggregate = after.execute("SELECT avg(value), count(*) FROM ratings WHERE release_id=?", (new_release["id"],)).fetchone()
    judge.check("rating_aggregate_updated", changes == {"avg_rating", "rating_count"}
                and abs(new_release["avg_rating"] - aggregate[0]) < 1e-9
                and new_release["rating_count"] == aggregate[1], f"columns={sorted(changes)}")
    release_delta = table_delta(before, after, "releases")
    only_target_changed = (
        not release_delta["added"]
        and not release_delta["removed"]
        and len(release_delta["changed"]) == 1
        and release_delta["changed"][0][0]["discogs_id"] == 35846581
        and release_delta["changed"][0][1]["discogs_id"] == 35846581
    )
    judge.check("no_other_release_changes", only_target_changed, str(release_delta))
    check_allowed_tables(before, after, judge, {"ratings", "reviews", "releases"})


STATE_VERIFIERS = {
    7: verify_collection_add,
    8: verify_wantlist_add,
    9: verify_list_create,
    10: verify_listing_add,
    11: verify_forum_post,
    12: verify_registration,
    13: verify_collection_remove,
    14: verify_rating_review,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default="")  # accepted for interface compatibility; never read live
    parser.add_argument("--no_llm", nargs="?", const="true", default="false")
    return parser.parse_args()


def run(index: int) -> None:
    args = parse_args()
    task_id = f"Discogs--{index}"
    judge = Judge(task_id)
    run_dir = Path(args.run_dir)
    try:
        trajectory = json.loads((run_dir / "trajectory.json").read_text())
    except Exception as error:
        judge.check("trajectory_load", False, str(error))
        judge.emit()
    judge.check("task_identity", trajectory.get("task_id") == task_id,
                f"actual={trajectory.get('task_id')!r}")
    check_origin_discipline(trajectory, judge)
    if index in READ_ONLY_SPECS:
        verify_read_only(index, trajectory, judge)
        initial = resolve_snapshot(run_dir, args.initial_db, ("initial_state.db", "before.db"))
        after = resolve_snapshot(run_dir, args.after_db, ("after_state.db", "after.db"))
        judge.check("frozen_initial_db", initial is not None, str(initial) if initial else "missing")
        judge.check("frozen_after_db", after is not None, str(after) if after else "missing")
        if initial is not None and after is not None:
            try:
                with open_db(initial) as before_db, open_db(after) as after_db:
                    check_allowed_tables(before_db, after_db, judge, set())
            except Exception as error:
                judge.check("state_verification", False, f"{type(error).__name__}: {error}")
        judge.emit()

    answer = final_answer(trajectory)
    judge.check("final_answer_present", bool(answer), f"length={len(answer)}")
    initial = resolve_snapshot(run_dir, args.initial_db, ("initial_state.db", "before.db"))
    after = resolve_snapshot(run_dir, args.after_db, ("after_state.db", "after.db"))
    judge.check("frozen_initial_db", initial is not None, str(initial) if initial else "missing")
    judge.check("frozen_after_db", after is not None, str(after) if after else "missing")
    if initial is None or after is None:
        judge.emit()
    try:
        with open_db(initial) as before_db, open_db(after) as after_db:
            STATE_VERIFIERS[index](before_db, after_db, trajectory, judge)
    except Exception as error:
        judge.check("state_verification", False, f"{type(error).__name__}: {error}")
    judge.emit()
