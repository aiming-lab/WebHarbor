#!/usr/bin/env python3
"""Shared deterministic utilities for Target task verifiers."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

SITE = "target"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    container: str
    no_llm: bool


def _bool_value(value: str) -> bool:
    return str(value).casefold() in {"1", "true", "yes", "on"}


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", nargs="?", const=True, default=False, type=_bool_value)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=args.initial_db or (str(initial_snapshot) if initial_snapshot.is_file() else None),
        after_db=args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None),
        container=args.container,
        no_llm=bool(args.no_llm),
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(run_dir) / "trajectory.json"
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    return trajectory


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    urls = []
    if trajectory.get("start_url"):
        urls.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = str(step.get(key) or "")
            if value and (not urls or value != urls[-1]):
                urls.append(value)
    if trajectory.get("final_url") and str(trajectory["final_url"]) != (urls[-1] if urls else ""):
        urls.append(str(trajectory["final_url"]))
    return urls


def _is_loopback(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_target_url(url: str, trajectory: dict[str, Any]) -> bool:
    parsed = urlparse(str(url or ""))
    start = urlparse(str(trajectory.get("start_url") or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not start.hostname:
        return False
    return (
        _is_loopback(parsed.hostname)
        and _is_loopback(start.hostname)
        and parsed.scheme == start.scheme
        and parsed.port == start.port
    )


def normalized_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def visited_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(
        is_target_url(url, trajectory) and normalized_path(url) == expected
        for url in trajectory_urls(trajectory)
    )


def query_matches(url: str, expected: dict[str, str]) -> bool:
    params = parse_qs(urlparse(url).query)
    return all(
        normalize_text((params.get(key) or [""])[0]) == normalize_text(value)
        for key, value in expected.items()
    )


def visited_query(trajectory: dict[str, Any], path: str, expected: dict[str, str]) -> bool:
    return any(
        is_target_url(url, trajectory)
        and normalized_path(url) == normalized_path(path)
        and query_matches(url, expected)
        for url in trajectory_urls(trajectory)
    )


def visited_in_order(trajectory: dict[str, Any], requirements: list[tuple[str, dict[str, str]]]) -> bool:
    urls = trajectory_urls(trajectory)
    cursor = 0
    for path, query in requirements:
        found = False
        for index in range(cursor, len(urls)):
            url = urls[index]
            if is_target_url(url, trajectory) and normalized_path(url) == normalized_path(path) and query_matches(url, query):
                cursor = index + 1
                found = True
                break
        if not found:
            return False
    return True


def transition_pairs(trajectory: dict[str, Any]):
    steps = trajectory.get("steps") or []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        current = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(current, trajectory):
            continue
        candidates = []
        if step.get("url_after"):
            candidates.append(str(step["url_after"]))
        elif index + 1 < len(steps) and isinstance(steps[index + 1], dict):
            candidates.append(str(steps[index + 1].get("url") or steps[index + 1].get("url_after") or ""))
        for following in candidates:
            if is_target_url(following, trajectory):
                yield normalize_text(step.get("action")), current, following


def clicked_transition(trajectory: dict[str, Any], from_path: str, to_path: str, to_query: dict[str, str] | None = None) -> bool:
    expected_query = to_query or {}
    for action, current, following in transition_pairs(trajectory):
        if action != "click" or normalized_path(current) != normalized_path(from_path):
            continue
        if normalized_path(following) == normalized_path(to_path) and query_matches(following, expected_query):
            return True
    return False


def submitted_from_path(trajectory: dict[str, Any], path: str, destination: str | None = None) -> bool:
    for action, current, following in transition_pairs(trajectory):
        if action != "click" or normalized_path(current) != normalized_path(path):
            continue
        if destination is None or normalized_path(following) == normalized_path(destination):
            return True
    return False


def input_values(trajectory: dict[str, Any], path: str | None = None) -> list[str]:
    values = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(url, trajectory):
            continue
        if path is not None and normalized_path(url) != normalized_path(path):
            continue
        params = step.get("params") or {}
        value = params.get("text", params.get("value", params.get("option", params.get("label")))) if isinstance(params, dict) else None
        if value is not None:
            values.append(str(value))
    return values


def entered_text(trajectory: dict[str, Any], expected: str, path: str | None = None) -> bool:
    expected_normalized = normalize_text(expected)
    return any(normalize_text(value) == expected_normalized for value in input_values(trajectory, path))


def last_entered_email(trajectory: dict[str, Any], path: str = "/login") -> str:
    emails = [normalize_text(value) for value in input_values(trajectory, path) if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip())]
    return emails[-1] if emails else ""


def login_submitted_as(trajectory: dict[str, Any], email: str) -> bool:
    return (
        visited_path(trajectory, "/login")
        and last_entered_email(trajectory) == normalize_text(email)
        and entered_text(trajectory, "TestPass123!", "/login")
        and submitted_from_path(trajectory, "/login")
    )


NEGATION_WORDS = {"not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt", "doesn't", "doesnt", "didn't", "didnt"}


def _negated_at(text: str, start: int) -> bool:
    clause = re.split(r"[.!?;:\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    words = re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", clause)
    return any(word in NEGATION_WORDS for word in words)


def _denied_after(text: str, end: int) -> bool:
    suffix = re.sub(r"^\s*[-—–,:;!?]*\s*", "", text[end:])
    return re.match(r"(?:(?:is|was|does|did|are|were)\s+)?(?:not|never|no)\b|(?:isn't|isnt|wasn't|wasnt|doesn't|doesnt|didn't|didnt|aren't|arent|weren't|werent)\b", suffix) is not None


def affirmative_contains(text: Any, expected: Any) -> bool:
    normalized = normalize_text(text)
    needle = normalize_text(expected)
    matches = list(re.finditer(re.escape(needle), normalized))
    if not needle or not matches:
        return False
    match = matches[-1]
    return not _negated_at(normalized, match.start()) and not _denied_after(normalized, match.end())


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    return all(affirmative_contains(text, value) for value in expected)


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    return any(affirmative_contains(text, value) for value in expected)


def number_matches(text: Any, value: float, tolerance: float = 0.005) -> list[re.Match[str]]:
    normalized = normalize_text(text)
    matches = []
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", normalized):
        try:
            observed = float(match.group(0).replace(",", ""))
        except ValueError:
            continue
        if abs(observed - float(value)) <= tolerance and not _negated_at(normalized, match.start()) and not _denied_after(normalized, match.end()):
            matches.append(match)
    return matches


def has_number(text: Any, value: float, tolerance: float = 0.005) -> bool:
    return bool(number_matches(text, value, tolerance))


def has_money(text: Any, amount: float) -> bool:
    return has_number(text, round(float(amount), 2), 0.005)


def number_bound_to(text: Any, value: float, labels: Sequence[str], distance: int = 120) -> bool:
    normalized = normalize_text(text)
    for match in number_matches(normalized, value):
        left = max(0, match.start() - distance)
        right = min(len(normalized), match.end() + distance)
        window = normalized[left:right]
        if any(normalize_text(label) in window for label in labels):
            return True
    return False


def claims_relation(text: Any, winner_labels: Sequence[str], loser_labels: Sequence[str], relation_words: Sequence[str]) -> bool:
    normalized = normalize_text(text)
    if not any(affirmative_contains(normalized, label) for label in winner_labels):
        return False
    winner_positions = [normalized.rfind(normalize_text(label)) for label in winner_labels if normalize_text(label) in normalized]
    loser_positions = [normalized.rfind(normalize_text(label)) for label in loser_labels if normalize_text(label) in normalized]
    relation_positions = [normalized.rfind(normalize_text(word)) for word in relation_words if normalize_text(word) in normalized]
    if not winner_positions or not relation_positions:
        return False
    winner = max(winner_positions)
    relation = min(relation_positions, key=lambda position: abs(position - winner))
    if abs(relation - winner) > 160 or _negated_at(normalized, relation):
        return False
    if loser_positions:
        loser = min(loser_positions, key=lambda position: abs(position - relation))
        if loser < relation < winner and any(word in normalized[loser:winner] for word in ("less", "lower", "lowest", "higher")):
            return False
    return True


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"target_{kind}_", suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, destination], capture_output=True, text=True, check=False)
    if result.returncode:
        Path(destination).unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or f"could not copy {source}")
    return destination


def resolve_db(explicit: str | None, container: str, kind: str) -> str | None:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def db_query(path: str, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def table_snapshot(path: str, table: str) -> list[tuple[Any, ...]]:
    rows = db_query(path, f'SELECT * FROM "{table}" ORDER BY rowid')
    return [tuple(row) for row in rows]


def database_tables(path: str) -> list[str]:
    rows = db_query(path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [str(row["name"]) for row in rows]


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    initial_tables = database_tables(initial_db)
    after_tables = database_tables(after_db)
    if initial_tables != after_tables:
        return {"<schema>"}
    return {table for table in initial_tables if table_snapshot(initial_db, table) != table_snapshot(after_db, table)}


def database_unchanged(initial_db: str | None, after_db: str | None) -> bool:
    return bool(initial_db and after_db and not changed_tables(initial_db, after_db))


def row_dicts(path: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db_query(path, sql, params)]


def user_id(path: str, email: str) -> int | None:
    rows = db_query(path, "SELECT id FROM users WHERE lower(email)=lower(?)", (email,))
    return int(rows[0]["id"]) if rows else None


def cart_snapshot(path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT c.id,p.sku,c.quantity,c.fulfillment_method,c.store_id,c.delivery_option_id,c.protection_plan_id,c.created_at FROM cart_items c JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id WHERE lower(u.email)=lower(?) ORDER BY c.id", (email,))


def wishlist_snapshot(path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT w.id,p.sku,w.created_at FROM wishlist_items w JOIN users u ON u.id=w.user_id JOIN products p ON p.id=w.product_id WHERE lower(u.email)=lower(?) ORDER BY w.id", (email,))


def orders_snapshot(path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT o.* FROM orders o JOIN users u ON u.id=o.user_id WHERE lower(u.email)=lower(?) ORDER BY o.id", (email,))


def order_items(path: str, order_number: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT oi.*,p.sku FROM order_items oi JOIN orders o ON o.id=oi.order_id LEFT JOIN products p ON p.id=oi.product_id WHERE o.order_number=? ORDER BY oi.id", (order_number,))


def check_common(judge: "Judge", trajectory: dict[str, Any], task_id: str) -> None:
    judge.check("task_id_matches", str(trajectory.get("task_id") or "") == task_id, f"observed={trajectory.get('task_id')!r}")
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), repr(final_answer(trajectory)))
    judge.check("start_url_is_target", is_target_url(str(trajectory.get("start_url") or ""), trajectory), f"start_url={trajectory.get('start_url')!r}")


class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "") -> bool:
        self.evidence.append(f"[{'PASS' if condition else 'FAIL'}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.passed, "reason": self.reason, "evidence": self.evidence}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({"task_id": task_id, "pass": False, "reason": reason, "infra_error": True, "evidence": [f"[FAIL] {reason}: {detail}"]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)
