#!/usr/bin/env python3
"""Shared deterministic helpers for TED task verifiers."""

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

SITE = "ted"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")
SEED_EMAILS = {"alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"}


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
    trajectory = json.loads((Path(run_dir) / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    return trajectory


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    if trajectory.get("start_url"):
        urls.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url_before", "url", "url_after"):
            value = str(step.get(key) or "")
            if value and (not urls or value != urls[-1]):
                urls.append(value)
    final_url = str(trajectory.get("final_url") or "")
    if final_url and (not urls or final_url != urls[-1]):
        urls.append(final_url)
    return urls


def _loopback(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_site_url(url: str, trajectory: dict[str, Any]) -> bool:
    parsed = urlparse(str(url or ""))
    start = urlparse(str(trajectory.get("start_url") or ""))
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and start.hostname
        and _loopback(parsed.hostname)
        and _loopback(start.hostname)
        and parsed.scheme == start.scheme
        and parsed.port == start.port
    )


def normalized_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def query_matches(url: str, expected: dict[str, str]) -> bool:
    params = parse_qs(urlparse(url).query)
    return all(normalize_text((params.get(key) or [""])[0]) == normalize_text(value) for key, value in expected.items())


def visited_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(is_site_url(url, trajectory) and normalized_path(url) == expected for url in trajectory_urls(trajectory))


def visited_query(trajectory: dict[str, Any], path: str, expected: dict[str, str]) -> bool:
    return any(
        is_site_url(url, trajectory)
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
            if is_site_url(url, trajectory) and normalized_path(url) == normalized_path(path) and query_matches(url, query):
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
        if not is_site_url(current, trajectory):
            continue
        following = str(step.get("url_after") or "")
        if not following and index + 1 < len(steps) and isinstance(steps[index + 1], dict):
            following = str(steps[index + 1].get("url") or steps[index + 1].get("url_after") or "")
        if following and is_site_url(following, trajectory):
            yield normalize_text(step.get("action")), current, following


def clicked_transition(trajectory: dict[str, Any], from_path: str, to_path: str) -> bool:
    return any(
        action == "click"
        and normalized_path(current) == normalized_path(from_path)
        and normalized_path(following) == normalized_path(to_path)
        for action, current, following in transition_pairs(trajectory)
    )


def submitted_from_path(trajectory: dict[str, Any], path: str, destination: str | None = None) -> bool:
    for action, current, following in transition_pairs(trajectory):
        if action != "click" or normalized_path(current) != normalized_path(path):
            continue
        if destination is None or normalized_path(following) == normalized_path(destination):
            return True
    return False


def input_values(trajectory: dict[str, Any], path: str | None = None) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_site_url(url, trajectory) or (path and normalized_path(url) != normalized_path(path)):
            continue
        params = step.get("params") or {}
        value = params.get("text", params.get("value", params.get("option", params.get("label")))) if isinstance(params, dict) else None
        if value is not None:
            values.append(str(value))
    return values


def entered_text(trajectory: dict[str, Any], expected: str, path: str | None = None) -> bool:
    expected_value = normalize_text(expected)
    return any(normalize_text(value) == expected_value for value in input_values(trajectory, path))


def last_entered_email(trajectory: dict[str, Any], path: str = "/login") -> str:
    emails = [normalize_text(value) for value in input_values(trajectory, path) if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip())]
    return emails[-1] if emails else ""


def login_submitted_as(trajectory: dict[str, Any], email: str) -> bool:
    return visited_path(trajectory, "/login") and last_entered_email(trajectory) == normalize_text(email) and submitted_from_path(trajectory, "/login")


NEGATIONS = {"not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt", "doesn't", "doesnt", "didn't", "didnt"}


def _negated_before(text: str, start: int) -> bool:
    clause = re.split(r"[.!?;:\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", clause)
    return any(word in NEGATIONS for word in words)


def _negated_after(text: str, end: int) -> bool:
    suffix = re.sub(r"^\s*[-,:;!?]*\s*", "", text[end:])
    return re.match(r"(?:(?:is|was|does|did|are|were)\s+)?(?:not|never|no)\b|(?:isn't|isnt|wasn't|wasnt|doesn't|doesnt|didn't|didnt|aren't|arent|weren't|werent)\b", suffix) is not None


def affirmative_contains(text: Any, expected: Any) -> bool:
    normalized = normalize_text(text)
    needle = normalize_text(expected)
    matches = list(re.finditer(re.escape(needle), normalized))
    if not needle or not matches:
        return False
    match = matches[-1]
    return not _negated_before(normalized, match.start()) and not _negated_after(normalized, match.end())


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    return all(affirmative_contains(text, value) for value in expected)


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    return any(affirmative_contains(text, value) for value in expected)


def number_matches(text: Any, value: int | float, tolerance: float = 0.001) -> list[re.Match[str]]:
    normalized = normalize_text(text)
    matches = []
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", normalized):
        observed = float(match.group(0).replace(",", ""))
        if abs(observed - float(value)) <= tolerance and not _negated_before(normalized, match.start()) and not _negated_after(normalized, match.end()):
            matches.append(match)
    return matches


def has_number(text: Any, value: int | float) -> bool:
    return bool(number_matches(text, value))


def number_bound_to(text: Any, value: int | float, labels: Sequence[str], distance: int = 140) -> bool:
    normalized = normalize_text(text)
    for match in number_matches(normalized, value):
        window = normalized[max(0, match.start() - distance):min(len(normalized), match.end() + distance)]
        if any(normalize_text(label) in window for label in labels):
            return True
    return False


def number_bound_in_comparison(text: Any, value: int | float, labels: Sequence[str]) -> bool:
    normalized = normalize_text(text)
    segments = re.split(r"\b(?:versus|vs\.?|while|compared (?:with|to))\b|[;\n]", normalized)
    return any(has_number(segment, value) and any(normalize_text(label) in segment for label in labels) for segment in segments)


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported database kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"ted_{kind}_", suffix=".db")
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


def row_dicts(path: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db_query(path, sql, params)]


def database_tables(path: str) -> list[str]:
    return [str(row["name"]) for row in db_query(path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def table_snapshot(path: str, table: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(path, f'SELECT * FROM "{table}" ORDER BY rowid')]


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    initial_tables = database_tables(initial_db)
    if initial_tables != database_tables(after_db):
        return {"<schema>"}
    return {table for table in initial_tables if table_snapshot(initial_db, table) != table_snapshot(after_db, table)}


def database_unchanged(initial_db: str | None, after_db: str | None) -> bool:
    return bool(initial_db and after_db and not changed_tables(initial_db, after_db))


def saved_snapshot(path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT s.id,t.slug,t.title,t.topics_json,s.note,s.saved_at FROM saved_talk s JOIN user u ON u.id=s.user_id JOIN talk t ON t.id=s.talk_id WHERE lower(u.email)=lower(?) ORDER BY s.id", (email,))


def registration_snapshot(path: str, email: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT r.id,e.slug,e.name,r.status FROM registration r JOIN user u ON u.id=r.user_id JOIN event e ON e.id=r.event_id WHERE lower(u.email)=lower(?) ORDER BY r.id", (email,))


def user_snapshot(path: str) -> list[dict[str, Any]]:
    return row_dicts(path, "SELECT * FROM user ORDER BY id")


def check_common(judge: "Judge", trajectory: dict[str, Any], task_id: str) -> None:
    judge.check("task_id_matches", str(trajectory.get("task_id") or "") == task_id, f"observed={trajectory.get('task_id')!r}")
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), repr(final_answer(trajectory)))
    judge.check("start_url_is_site", is_site_url(str(trajectory.get("start_url") or ""), trajectory), f"start_url={trajectory.get('start_url')!r}")


def check_read_only(judge: "Judge", args: VerifyArgs) -> tuple[str | None, str | None]:
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    return initial, after


class Judge:
    def __init__(self, task_id: str, no_llm: bool = False):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str = "", llm: bool = False) -> bool:
        self.evidence.append(f"[{'PASS' if condition else 'FAIL'}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return bool(condition)

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.passed, "reason": self.reason, "evidence": self.evidence}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)
