#!/usr/bin/env python3
"""Shared fail-closed helpers for Petfinder task verification."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse


SITE = "petfinder"
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
    trajectory = json.loads((Path(run_dir) / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain an object")
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


def input_values(trajectory: dict[str, Any], path: str | None = None) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_site_url(url, trajectory) or (path and normalized_path(url) != normalized_path(path)):
            continue
        params = step.get("params") or {}
        if isinstance(params, dict):
            value = params.get("text", params.get("value", params.get("option", params.get("label"))))
            if value is not None:
                values.append(str(value))
    return values


def entered_text(trajectory: dict[str, Any], expected: str, path: str | None = None) -> bool:
    return any(normalize_text(value) == normalize_text(expected) for value in input_values(trajectory, path))


NEGATIONS = {"not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt", "doesn't", "doesnt", "didn't", "didnt"}


def _negated_before(text: str, start: int) -> bool:
    clause = re.split(r"[.!?;:\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    return any(word in NEGATIONS for word in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", clause))


def _negated_after(text: str, end: int) -> bool:
    suffix = re.sub(r"^\s*[-,:;!?]*\s*", "", text[end:])
    return re.match(r"(?:(?:is|was|does|did|are|were)\s+)?(?:not|never|no)\b", suffix) is not None


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


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported database kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"petfinder_{kind}_", suffix=".db")
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


def database_tables(path: str) -> list[str]:
    return [str(row["name"]) for row in db_query(path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def table_snapshot(path: str, table: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(path, f'SELECT * FROM "{table}" ORDER BY rowid')]


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    initial_tables = database_tables(initial_db)
    if initial_tables != database_tables(after_db):
        return {"<schema>"}
    return {table for table in initial_tables if table_snapshot(initial_db, table) != table_snapshot(after_db, table)}


def matches_expected_mutation(initial_db: str, after_db: str, sql: str, params: Sequence[Any]) -> bool:
    """Compare after.db with a copy of initial.db containing exactly one allowed mutation."""
    handle, expected_path = tempfile.mkstemp(prefix="petfinder_expected_", suffix=".db")
    os.close(handle)
    try:
        shutil.copyfile(initial_db, expected_path)
        connection = sqlite3.connect(expected_path)
        try:
            cursor = connection.execute(sql, params)
            connection.commit()
            if cursor.rowcount != 1:
                return False
        finally:
            connection.close()
        expected_tables = database_tables(expected_path)
        if expected_tables != database_tables(after_db):
            return False
        return all(table_snapshot(expected_path, table) == table_snapshot(after_db, table) for table in expected_tables)
    finally:
        Path(expected_path).unlink(missing_ok=True)


def favorite_names(path: str, email: str = "alice.j@test.com") -> list[str]:
    rows = db_query(path, "SELECT l.name FROM saved_item s JOIN user u ON u.id=s.user_id JOIN listing l ON l.id=s.listing_id WHERE lower(u.email)=lower(?) ORDER BY s.id", (email,))
    return [str(row["name"]) for row in rows]


def user_preferences(path: str, email: str = "alice.j@test.com") -> tuple[str, str] | None:
    rows = db_query(path, "SELECT home_location,sort_preference FROM user WHERE lower(email)=lower(?)", (email,))
    return (str(rows[0]["home_location"]), str(rows[0]["sort_preference"])) if rows else None


def inquiry_rows(path: str, email: str = "alice.j@test.com") -> list[dict[str, Any]]:
    rows = db_query(path, "SELECT l.slug,i.message,i.status FROM inquiry i JOIN user u ON u.id=i.user_id JOIN listing l ON l.id=i.listing_id WHERE lower(u.email)=lower(?) ORDER BY i.id", (email,))
    return [dict(row) for row in rows]


def check_common(judge: "Judge", trajectory: dict[str, Any], task_id: str) -> None:
    judge.check("task_id_matches", str(trajectory.get("task_id") or "") == task_id, f"observed={trajectory.get('task_id')!r}")
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), repr(final_answer(trajectory)))
    judge.check("start_url_is_site", is_site_url(str(trajectory.get("start_url") or ""), trajectory), f"start={trajectory.get('start_url')!r}")


def check_read_only(judge: "Judge", args: VerifyArgs) -> tuple[str | None, str | None]:
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    judge.check("read_only_database_unchanged", bool(initial and after and not changed_tables(initial, after)), "complete database comparison")
    return initial, after


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


def save_action_used(trajectory: dict[str, Any]) -> bool:
    """Resolve an indexed button against observed DOM, never guess from index alone."""
    steps = trajectory.get("steps") or []
    for i, step in enumerate(steps):
        if step.get("action") not in {"click", "tap", "press"}:
            continue
        before = str(step.get("url_before") or step.get("url") or "")
        if not is_site_url(before, trajectory) or normalized_path(before) != "/pets/milo-labrador-mix":
            continue
        result = step.get("action_result") or {}
        if result.get("error") or result.get("success") is False:
            continue
        params = step.get("params") or {}
        index = params.get("index")
        if isinstance(index, int) and not isinstance(index, bool):
            dom = str(step.get("observed_text_before") or step.get("page_text") or "")
            # browser-use may put a button label on an indented child line.
            lines = dom.splitlines()
            line = ""
            for position, candidate in enumerate(lines):
                if re.search(rf"\[{index}\]", candidate):
                    block = [candidate]
                    indent = len(candidate) - len(candidate.lstrip())
                    for child in lines[position + 1:]:
                        if len(child) - len(child.lstrip()) <= indent or re.search(r"\[\d+\]", child):
                            break
                        block.append(child)
                    line = " ".join(block)
                    break
            target = bool(re.search(r"\bbutton\b", line, re.I) and "save this pet" in line.casefold())
        else:
            locator = " ".join(str(params.get(k) or "") for k in ("locator", "text", "name", "label"))
            target = "save this pet" in locator.casefold()
        after = str(step.get("url_after") or (steps[i + 1].get("url_before") or steps[i + 1].get("url") or "" if i + 1 < len(steps) else trajectory.get("final_url") or ""))
        if target and is_site_url(after, trajectory) and normalized_path(after) == "/account":
            return True
    return False
