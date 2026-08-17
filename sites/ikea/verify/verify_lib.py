#!/usr/bin/env python3
"""Shared deterministic helpers for IKEA task verifiers.

Each verifier consumes an agent run directory plus before/after SQLite snapshots
and emits ``{task_id, pass, reason, evidence[]}`` with exit code 0/1.
"""
from __future__ import annotations

import argparse
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
from urllib.parse import urlparse


SITE = "ikea"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str | None
    after_db: str | None
    container: str
    no_llm: bool


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    initial_snapshot = run_dir / "initial.db"
    after_snapshot = run_dir / "after.db"
    return VerifyArgs(
        run_dir=args.run_dir,
        initial_db=(
            args.initial_db
            or (str(initial_snapshot) if initial_snapshot.is_file() else None)
        ),
        after_db=(
            args.after_db or (str(after_snapshot) if after_snapshot.is_file() else None)
        ),
        container=args.container,
        no_llm=args.no_llm,
    )


def load_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(run_dir) / "trajectory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory.json must contain a JSON object")
    return data


def final_answer(trajectory: dict[str, Any]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def final_url(trajectory: dict[str, Any]) -> str:
    direct = trajectory.get("final_url")
    if direct:
        return str(direct)
    for step in reversed(trajectory.get("steps") or []):
        if isinstance(step, dict) and step.get("url"):
            return str(step["url"])
    return ""


def trajectory_urls(trajectory: dict[str, Any]) -> list[str]:
    """Return every browser URL recorded by supported trajectory producers."""
    urls: list[str] = []
    for key in ("start_url", "final_url"):
        value = trajectory.get(key)
        if value:
            urls.append(str(value))
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("url", "url_before", "url_after"):
            value = step.get(key)
            if value:
                urls.append(str(value))
    return urls


def normalized_url_path(url: str) -> str:
    path = urlparse(str(url or "")).path or "/"
    return path.rstrip("/") or "/"


def navigated_to_path(trajectory: dict[str, Any], expected_path: str) -> bool:
    """Require an exact on-site path while allowing any host and query string."""
    expected = normalized_url_path(expected_path)
    return any(normalized_url_path(url) == expected for url in trajectory_urls(trajectory))


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def contains_all(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return all(normalize_text(value) in normalized for value in expected)


def contains_any(text: Any, expected: Iterable[Any]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(value) in normalized for value in expected)


def contains_money(text: Any, dollars: int, cents: int = 0) -> bool:
    """Match a US dollar amount while tolerating whitespace and comma grouping."""
    raw = unicodedata.normalize("NFKC", str(text or ""))
    amount = f"{dollars:,}".replace(",", r",?")
    return bool(re.search(rf"\$\s*{amount}\s*[.]\s*{cents:02d}\b", raw))


def explicitly_denies_label(text: Any, label: str) -> bool:
    """Return true only when the answer explicitly negates a named label."""
    normalized = normalize_text(text)
    escaped = re.escape(normalize_text(label))
    patterns = (
        rf"\b(?:no|not|isn't|is not|wasn't|was not)\b.{{0,28}}\b{escaped}\b",
        rf"\b{escaped}\b\s*(?::|[-–—])?\s*\b(?:no|false|none|not)\b",
        rf"\b(?:doesn't|does not|isn't|is not)\b.{{0,28}}\bmarked\b.{{0,18}}\b{escaped}\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def contains_hyphenated_phrase(text: Any, words: Sequence[str]) -> bool:
    """Match words separated by whitespace or common dash characters."""
    normalized = normalize_text(text)
    separator = r"(?:\s|[-–—])+"
    pattern = r"\b" + separator.join(re.escape(normalize_text(w)) for w in words) + r"\b"
    return bool(re.search(pattern, normalized))


def contains_dimensions_inches(text: Any, width: int, height: int) -> bool:
    """Match equivalent W x H inch formats, including quotes and multiplication signs."""
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    inch = r'(?:["″]|in(?:ch(?:es)?)?\.?)'
    pattern = rf"\b{width}\s*{inch}?\s*[x×]\s*{height}\s*{inch}"
    return bool(re.search(pattern, normalized))


def extract_order_numbers(text: Any) -> set[str]:
    raw = unicodedata.normalize("NFKC", str(text or ""))
    matches = re.findall(r"(?<![A-Za-z0-9])IK\s*[-–—]\s*\d{6}(?!\d)", raw, re.I)
    return {
        re.sub(r"\s+", "", value).replace("–", "-").replace("—", "-").upper()
        for value in matches
    }


def db_query(
    db_path: str | os.PathLike[str], sql: str, params: Sequence[Any] = ()
) -> list[sqlite3.Row]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def fetch_db(container: str, kind: str) -> str:
    if kind not in {"instance", "instance_seed"}:
        raise ValueError(f"unsupported DB kind: {kind}")
    handle, destination = tempfile.mkstemp(prefix=f"ikea_{kind}_", suffix=".db")
    os.close(handle)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(
        ["docker", "cp", source, destination], capture_output=True, text=True
    )
    if result.returncode:
        Path(destination).unlink(missing_ok=True)
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"could not copy {source}: {detail}")
    return destination


def resolve_db(explicit_path: str | None, container: str, kind: str) -> str | None:
    if explicit_path:
        path = Path(explicit_path)
        return str(path) if path.is_file() else None
    try:
        return fetch_db(container, kind)
    except (OSError, RuntimeError):
        return None


def user_id_for_email(db_path: str, email: str) -> int | None:
    rows = db_query(
        db_path,
        "SELECT id FROM users WHERE lower(email) = lower(?) ORDER BY id LIMIT 1",
        (email,),
    )
    return int(rows[0]["id"]) if rows else None


def user_emails(db_path: str) -> set[str]:
    rows = db_query(db_path, "SELECT email FROM users")
    return {normalize_text(row["email"]) for row in rows if row["email"]}


def new_user_emails(initial_db: str, after_db: str) -> set[str]:
    initial_ids = {int(row["id"]) for row in db_query(initial_db, "SELECT id FROM users")}
    after_rows = db_query(after_db, "SELECT id, email FROM users")
    return {
        normalize_text(row["email"])
        for row in after_rows
        if int(row["id"]) not in initial_ids and row["email"]
    }


def product_id_for_sku(db_path: str, sku: str) -> int | None:
    rows = db_query(
        db_path,
        "SELECT id FROM products WHERE upper(sku) = upper(?) ORDER BY id LIMIT 1",
        (sku,),
    )
    return int(rows[0]["id"]) if rows else None


def relation_count(db_path: str, table: str, email: str, sku: str) -> int | None:
    allowed_tables = {"wishlist_items", "compare_items", "cart_items"}
    if table not in allowed_tables:
        raise ValueError(f"unsupported relation table: {table}")
    user_id = user_id_for_email(db_path, email)
    product_id = product_id_for_sku(db_path, sku)
    if user_id is None or product_id is None:
        return None
    rows = db_query(
        db_path,
        f"SELECT COUNT(*) AS count FROM {table} WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    return int(rows[0]["count"])


def relation_skus(db_path: str, table: str, email: str) -> set[str] | None:
    allowed_tables = {"wishlist_items", "compare_items", "cart_items"}
    if table not in allowed_tables:
        raise ValueError(f"unsupported relation table: {table}")
    user_id = user_id_for_email(db_path, email)
    if user_id is None:
        return None
    rows = db_query(
        db_path,
        f"SELECT p.sku FROM {table} r "
        "JOIN products p ON p.id = r.product_id WHERE r.user_id = ?",
        (user_id,),
    )
    return {str(row["sku"]).upper() for row in rows}


def cart_quantity(db_path: str, email: str, sku: str) -> int | None:
    user_id = user_id_for_email(db_path, email)
    product_id = product_id_for_sku(db_path, sku)
    if user_id is None or product_id is None:
        return None
    rows = db_query(
        db_path,
        "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM cart_items "
        "WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    return int(rows[0]["quantity"])


def cart_snapshot(db_path: str, email: str) -> dict[str, int] | None:
    user_id = user_id_for_email(db_path, email)
    if user_id is None:
        return None
    rows = db_query(
        db_path,
        "SELECT p.sku, SUM(c.quantity) AS quantity FROM cart_items c "
        "JOIN products p ON p.id = c.product_id WHERE c.user_id = ? "
        "GROUP BY p.sku ORDER BY p.sku",
        (user_id,),
    )
    return {str(row["sku"]).upper(): int(row["quantity"]) for row in rows}


def order_numbers(db_path: str, email: str) -> set[str] | None:
    user_id = user_id_for_email(db_path, email)
    if user_id is None:
        return None
    rows = db_query(
        db_path,
        "SELECT order_number FROM orders WHERE user_id = ? ORDER BY order_number",
        (user_id,),
    )
    return {str(row["order_number"]) for row in rows}


class Judge:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str) -> bool:
        marker = "PASS" if condition else "FAIL"
        self.evidence.append(f"[{marker}] {name}: {evidence}")
        if not condition:
            self.passed = False
            if not self.reason:
                self.reason = name
        return condition

    def emit(self) -> None:
        result = {
            "task_id": self.task_id,
            "pass": self.passed,
            "reason": self.reason or "all checks passed",
            "evidence": self.evidence,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if self.passed else 1)


def fail_closed(task_id: str, reason: str, detail: str) -> None:
    print(
        json.dumps(
            {
                "task_id": task_id,
                "pass": False,
                "infra_error": True,
                "reason": reason,
                "evidence": [f"[FAIL] {reason}: {detail}"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(1)
