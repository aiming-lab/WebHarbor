#!/usr/bin/env python3
"""Shared deterministic utilities for the Amazon task verifiers."""

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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, NoReturn, Sequence
from urllib.parse import parse_qs, urlparse

SITE = "amazon"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    container: str


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
        print(json.dumps({
            "task_id": self.task_id,
            "pass": self.passed,
            "reason": self.reason,
            "evidence": self.evidence,
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(json.dumps({
        "task_id": task_id,
        "pass": False,
        "reason": reason,
        "infra_error": True,
        "evidence": [f"[FAIL] {reason}: {detail}"],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def run_safely(task_id: str, callback: Callable[[], None]) -> None:
    try:
        callback()
    except SystemExit:
        raise
    except Exception as error:  # fail closed for malformed or incomplete inputs
        fail_closed(task_id, "verifier_exception", f"{type(error).__name__}: {error}")


class VerifierArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(f"argument error: {message}")


def parse_args() -> VerifyArgs:
    parser = VerifierArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=args.initial_db or (str(initial_snapshot) if initial_snapshot.is_file() else None),
        after_db=args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None),
        container=args.container,
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(run_dir) / "trajectory.json"
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    steps = trajectory.get("steps")
    if steps is not None and not isinstance(steps, list):
        raise ValueError("trajectory steps must be a JSON array")
    return trajectory


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def compact_tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(value)))


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


def query_values(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items() if values}


def visited_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(
        is_target_url(url, trajectory) and normalized_path(url) == expected
        for url in trajectory_urls(trajectory)
    )


def search_visits(trajectory: dict[str, Any]) -> list[str]:
    return [
        url for url in trajectory_urls(trajectory)
        if is_target_url(url, trajectory) and normalized_path(url) == "/search"
    ]


def _value_matches(observed: str, expected: Any) -> bool:
    if isinstance(expected, (tuple, list, set)):
        return any(_value_matches(observed, option) for option in expected)
    try:
        observed_number = Decimal(normalize_text(observed))
        expected_number = Decimal(normalize_text(expected))
        if observed_number.is_finite() and expected_number.is_finite():
            return observed_number == expected_number
    except InvalidOperation:
        pass
    return normalize_text(observed) == normalize_text(expected)


def search_used(
    trajectory: dict[str, Any],
    *,
    terms: Sequence[str] = (),
    params: dict[str, Any] | None = None,
) -> bool:
    for url in search_visits(trajectory):
        query = query_values(url)
        query_tokens = compact_tokens(query.get("q", ""))
        if not all(compact_tokens(term) <= query_tokens for term in terms):
            continue
        if params and not all(_value_matches(query.get(key, ""), value) for key, value in params.items()):
            continue
        return True
    return False


def transition_pairs(trajectory: dict[str, Any]):
    steps = trajectory.get("steps") or []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        current = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(current, trajectory):
            continue
        following = str(step.get("url_after") or "")
        if not following and index + 1 < len(steps) and isinstance(steps[index + 1], dict):
            following = str(steps[index + 1].get("url") or steps[index + 1].get("url_after") or "")
        if following and is_target_url(following, trajectory):
            yield normalize_text(step.get("action")), current, following


def clicked_transition(trajectory: dict[str, Any], from_path: str, to_path: str) -> bool:
    return any(
        action == "click"
        and normalized_path(current) == normalized_path(from_path)
        and normalized_path(following) == normalized_path(to_path)
        for action, current, following in transition_pairs(trajectory)
    )


def clicked_on_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) != "click":
            continue
        current = str(step.get("url") or step.get("url_before") or "")
        if is_target_url(current, trajectory) and normalized_path(current) == expected:
            return True
    return False


def input_values(trajectory: dict[str, Any], path: str | None = None) -> list[str]:
    values: list[str] = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or normalize_text(step.get("action")) not in {"input", "fill", "type", "select"}:
            continue
        url = str(step.get("url") or step.get("url_before") or "")
        if not is_target_url(url, trajectory):
            continue
        if path is not None and normalized_path(url) != normalized_path(path):
            continue
        params = step.get("params") or {}
        if not isinstance(params, dict):
            continue
        value = params.get("text", params.get("value", params.get("option", params.get("label"))))
        if value is not None:
            values.append(str(value))
    return values


def submitted_from_path(trajectory: dict[str, Any], path: str) -> bool:
    expected = normalized_path(path)
    return any(
        action == "click" and normalized_path(current) == expected
        for action, current, _ in transition_pairs(trajectory)
    )


def login_submitted_as(trajectory: dict[str, Any], email: str, password: str) -> bool:
    values = [normalize_text(value) for value in input_values(trajectory, "/login")]
    return (
        visited_path(trajectory, "/login")
        and normalize_text(email) in values
        and normalize_text(password) in values
        and submitted_from_path(trajectory, "/login")
    )


NEGATION_WORDS = {
    "not", "no", "never", "without", "isn't", "isnt", "wasn't", "wasnt",
    "doesn't", "doesnt", "didn't", "didnt", "aren't", "arent", "weren't", "werent",
}


def _negated_at(text: str, start: int) -> bool:
    clause = re.split(r"[.!?;:\n]+|\b(?:and|but|however|instead)\b", text[:start])[-1]
    words = re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", clause)
    return any(word in NEGATION_WORDS for word in words)


def _denied_after(text: str, end: int) -> bool:
    suffix = re.sub(r"^\s*[-—–,:;!?]*\s*", "", text[end:])
    return re.match(r"(?:(?:is|was|does|did|are|were)\s+)?(?:not|never|no)\b", suffix) is not None


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


def number_matches(text: Any, value: float, tolerance: float = 0.005) -> bool:
    normalized = normalize_text(text)
    for match in re.finditer(r"(?<![a-z0-9])\d[\d,]*(?:\.\d+)?(?![a-z0-9])", normalized):
        try:
            observed = float(match.group(0).replace(",", ""))
        except ValueError:
            continue
        if abs(observed - float(value)) <= tolerance and not _negated_at(normalized, match.start()) and not _denied_after(normalized, match.end()):
            return True
    return False


def has_number(text: Any, value: float, tolerance: float = 0.005) -> bool:
    return number_matches(text, value, tolerance)


def has_money(text: Any, amount: float) -> bool:
    return number_matches(text, round(float(amount), 2), 0.005)


def appears_in_order(text: Any, values: Sequence[Any]) -> bool:
    normalized = normalize_text(text)
    cursor = 0
    for value in values:
        position = normalized.find(normalize_text(value), cursor)
        if position < 0:
            return False
        cursor = position + len(normalize_text(value))
    return True


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"amazon_{kind}_", suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}_store.db"
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


def table_snapshot(path: str, table: str) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db_query(path, f'SELECT * FROM "{table}" ORDER BY rowid')]


def database_tables(path: str) -> list[str]:
    rows = db_query(path, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [str(row["name"]) for row in rows]


def changed_tables(initial_db: str, after_db: str) -> set[str]:
    initial_tables = database_tables(initial_db)
    after_tables = database_tables(after_db)
    if initial_tables != after_tables:
        return {"<schema>"}
    return {
        table for table in initial_tables
        if table_snapshot(initial_db, table) != table_snapshot(after_db, table)
    }


def database_unchanged(initial_db: str | None, after_db: str | None) -> bool:
    return bool(initial_db and after_db and not changed_tables(initial_db, after_db))


def _json_value(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(str(value or ""))
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def products(path: str) -> list[dict[str, Any]]:
    rows = row_dicts(path, "SELECT * FROM products ORDER BY id")
    for row in rows:
        row["spec"] = _json_value(row.get("specs"), {})
        row["variants"] = _json_value(row.get("variant_options"), {})
        row["tags"] = _json_value(row.get("feature_tags"), [])
        row["feature_list"] = _json_value(row.get("features"), [])
    return rows


def spec_value(product: dict[str, Any], key: str, default: Any = "") -> Any:
    wanted = normalize_text(key)
    for observed, value in (product.get("spec") or {}).items():
        if normalize_text(observed) == wanted:
            return value
    return default


def numeric_value(value: Any, default: float = -1.0) -> float:
    match = re.search(r"\d+(?:\.\d+)?", normalize_text(value).replace(",", ""))
    return float(match.group(0)) if match else default


def product_path(product: dict[str, Any]) -> str:
    return f"/product/{product['slug']}"


def visited_product_slugs(trajectory: dict[str, Any]) -> list[str]:
    slugs: list[str] = []
    for url in trajectory_urls(trajectory):
        if not is_target_url(url, trajectory):
            continue
        match = re.fullmatch(r"/product/([^/]+)", normalized_path(url))
        if match and match.group(1) not in slugs:
            slugs.append(match.group(1))
    return slugs


def selected_product(
    trajectory: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
    *,
    require_result_click: bool = True,
) -> dict[str, Any] | None:
    by_slug = {str(product["slug"]): product for product in candidates}
    for slug in reversed(visited_product_slugs(trajectory)):
        product = by_slug.get(slug)
        if not product:
            continue
        if require_result_click and not clicked_transition(trajectory, "/search", product_path(product)):
            continue
        return product
    return None


def check_common(judge: Judge, trajectory: dict[str, Any], task_id: str) -> None:
    urls = trajectory_urls(trajectory)
    judge.check("task_id_matches", str(trajectory.get("task_id") or "") == task_id, repr(trajectory.get("task_id")))
    judge.check("final_answer_nonempty", bool(final_answer(trajectory)), repr(final_answer(trajectory)))
    judge.check("start_url_is_target", is_target_url(str(trajectory.get("start_url") or ""), trajectory), repr(trajectory.get("start_url")))
    judge.check("all_urls_stay_on_target", bool(urls) and all(is_target_url(url, trajectory) for url in urls), repr(urls))
    judge.check("recorded_ui_steps", bool(trajectory.get("steps")), f"steps={len(trajectory.get('steps') or [])}")


def check_read_only_databases(judge: Judge, args: VerifyArgs) -> tuple[str | None, str | None]:
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    if initial and after:
        judge.check("read_only_database_unchanged", database_unchanged(initial, after), repr(changed_tables(initial, after)))
    return initial, after
