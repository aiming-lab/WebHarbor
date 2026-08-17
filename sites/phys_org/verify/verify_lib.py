#!/usr/bin/env python3
"""Shared deterministic utilities for Phys.org task verifiers."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse


SITE = "phys_org"


def load_run(run_dir: str | Path) -> dict:
    path = Path(run_dir) / "trajectory.json"
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    trajectory["_run_dir"] = str(Path(run_dir))
    return trajectory


def step_urls(trajectory: dict) -> list[str]:
    return [str(step.get("url", "")) for step in trajectory.get("steps", [])]


def visited_path(trajectory: dict, path: str) -> bool:
    return any(urlparse(url).path == path for url in step_urls(trajectory))


def visited_search(trajectory: dict, query: str, category: str | None = None) -> bool:
    for url in step_urls(trajectory):
        parsed = urlparse(url)
        if parsed.path != "/search":
            continue
        params = parse_qs(parsed.query)
        if norm((params.get("q") or [""])[0]) != norm(query):
            continue
        if category is not None and norm((params.get("category") or [""])[0]) != norm(category):
            continue
        return True
    return False


def visited_category(trajectory: dict, slug: str, sort: str | None = None) -> bool:
    path = f"/category/{slug}"
    for url in step_urls(trajectory):
        parsed = urlparse(url)
        if parsed.path != path:
            continue
        if sort is None:
            return True
        params = parse_qs(parsed.query)
        if norm((params.get("sort") or [""])[0]) == norm(sort):
            return True
    return False


def final_answer(trajectory: dict) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def contains_all(text: str, expected: list[str] | tuple[str, ...]) -> bool:
    normalized = norm(text)
    return all(norm(item) in normalized for item in expected)


def contains_any(text: str, expected: list[str] | tuple[str, ...]) -> bool:
    normalized = norm(text)
    return any(norm(item) in normalized for item in expected)


def has_number(text: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", unicodedata.normalize("NFKC", text)) is not None


def claims_earlier(text: str, expected_title: str) -> bool:
    """Require an affirmative earlier/older claim and reject reversed wording."""
    normalized = norm(text)
    if norm(expected_title) not in normalized:
        return False
    if _reverses_earlier_claim(normalized):
        return False
    return re.search(r"\b(?:earlier|older|first|before)\b", normalized) is not None


def answers_earlier_comparison(text: str, expected_title: str, other_title: str) -> bool:
    """Accept an explicit earlier claim or an unambiguous direct-title answer.

    A prompt that asks which of two named items is earlier can be answered with
    the winning title alone. If both titles are repeated, relational wording is
    still required so the answer cannot pass while remaining ambiguous.
    """
    if claims_earlier(text, expected_title):
        return True
    normalized = norm(text)
    return (
        norm(expected_title) in normalized
        and norm(other_title) not in normalized
        and not _reverses_earlier_claim(normalized)
    )


def _reverses_earlier_claim(normalized: str) -> bool:
    return re.search(
        r"\b(?:later|newer|after)\b|\bnot\s+(?:the\s+)?(?:earlier|older|first)\b",
        normalized,
    ) is not None


def fetch_db(container: str, kind: str) -> str:
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    descriptor, path = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    result = subprocess.run(["docker", "cp", source, path], capture_output=True, text=True)
    if result.returncode != 0:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError(f"docker cp {source} failed: {result.stderr.strip()}")
    return path


def resolve_db(path: str, container: str, kind: str) -> str | None:
    if path:
        return path
    try:
        return fetch_db(container, kind)
    except Exception:
        return None


def db_query(path: str | None, sql: str, params: tuple = ()) -> list[tuple] | None:
    if not path:
        return None
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


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
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.ok else 1)


def _bool_value(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", type=_bool_value, default=False)
    return parser.parse_args()


def stateless_main(task_number: int, navigation_checks: list[tuple[str, bool, str]],
                   answer_checks: list[tuple[str, bool, str]]) -> None:
    judge = Judge(f"Phys.org--{task_number}")
    for name, condition, evidence in navigation_checks + answer_checks:
        judge.check(name, condition, evidence)
    judge.emit()


def run_stateless(task_number: int, check_builder) -> None:
    args = parse_args()
    trajectory = load_run(args.run_dir)
    navigation, answers = check_builder(trajectory, final_answer(trajectory))
    stateless_main(task_number, navigation, answers)
