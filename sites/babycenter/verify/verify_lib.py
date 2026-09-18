#!/usr/bin/env python3
"""Deterministic, fail-closed verifiers for the BabyCenter benchmark tasks."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sqlite3
import struct
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class Judge:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.evidence: list[dict] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.evidence.append({"check": name, "pass": bool(passed), "detail": detail})

    def emit(self) -> None:
        passed = all(item["pass"] for item in self.evidence)
        failed = [item["check"] for item in self.evidence if not item["pass"]]
        result = {
            "task_id": self.task_id,
            "pass": passed,
            "reason": "all deterministic checks passed"
            if passed
            else f"failed checks: {', '.join(failed)}",
            "evidence": self.evidence,
        }
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if passed else 1)


def normalize(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default="wh-review")
    parser.add_argument("--no_llm", nargs="?", const=True, default=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    args.initial_db = args.initial_db or str(run_dir / "initial.db")
    args.after_db = args.after_db or str(run_dir / "after.db")
    return args


def load_run(run_dir: str) -> dict:
    data = json.loads((Path(run_dir) / "trajectory.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trajectory must be an object")
    data["_run_dir"] = str(Path(run_dir))
    return data


def url_path(url: str) -> str:
    return urlparse(str(url or "")).path.rstrip("/") or "/"


def is_local_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def urls(trajectory: dict) -> list[str]:
    found = []
    if trajectory.get("start_url"):
        found.append(str(trajectory["start_url"]))
    for step in trajectory.get("steps") or []:
        for key in ("url", "url_before", "url_after"):
            if step.get(key):
                found.append(str(step[key]))
    if trajectory.get("final_url"):
        found.append(str(trajectory["final_url"]))
    return found


def visited(trajectory: dict, path: str) -> bool:
    return any(is_local_url(url) and url_path(url) == path for url in urls(trajectory))


def visited_query(trajectory: dict, path: str, **expected: str) -> bool:
    for url in urls(trajectory):
        parsed = urlparse(url)
        if not is_local_url(url) or (parsed.path.rstrip("/") or "/") != path:
            continue
        query = parse_qs(parsed.query, keep_blank_values=True)
        if all(
            normalize((query.get(key) or [""])[0]) == normalize(value)
            for key, value in expected.items()
        ):
            return True
    return False


def paths_in_order(trajectory: dict, paths: list[str]) -> bool:
    cursor = 0
    for url in urls(trajectory):
        if cursor < len(paths) and is_local_url(url) and url_path(url) == paths[cursor]:
            cursor += 1
    return cursor == len(paths)


def action_on(
    trajectory: dict, action: str, path: str, value: str | None = None
) -> bool:
    for step in trajectory.get("steps") or []:
        if (
            normalize(step.get("action")) != normalize(action)
            or url_path(step.get("url")) != path
        ):
            continue
        if value is None:
            return True
        params = step.get("params") or {}
        if any(normalize(item) == normalize(value) for item in params.values()):
            return True
    return False


def schema(path: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()


def check_common(
    judge: Judge, trajectory: dict, task_id: str, initial_db: str, after_db: str
) -> str:
    answer = str(trajectory.get("final_answer") or "").strip()
    judge.check(
        "trajectory_identity",
        trajectory.get("task_id") == task_id,
        repr(trajectory.get("task_id")),
    )
    judge.check(
        "terminated",
        trajectory.get("terminated") is True,
        repr(trajectory.get("termination_reason")),
    )
    judge.check("answer_present", bool(answer), repr(answer))
    observed_urls = urls(trajectory)
    judge.check(
        "local_origin_only",
        bool(observed_urls) and all(is_local_url(url) for url in observed_urls),
        repr(observed_urls),
    )
    start = urlparse(trajectory.get("start_url", ""))

    def origin(url):
        value = urlparse(url)
        return (
            value.scheme,
            value.hostname,
            value.port or (443 if value.scheme == "https" else 80),
        )

    judge.check(
        "same_origin",
        bool(start.hostname)
        and all(
            origin(url) == origin(trajectory["start_url"]) for url in observed_urls
        ),
        "same scheme/host/port as task start",
    )
    judge.check(
        "snapshots_exist",
        Path(initial_db).is_file() and Path(after_db).is_file(),
        f"{initial_db} {after_db}",
    )
    if Path(initial_db).is_file() and Path(after_db).is_file():
        judge.check(
            "schema_unchanged", schema(initial_db) == schema(after_db), "sqlite_master"
        )
    run_dir = Path(trajectory["_run_dir"])
    declared = set()
    for step in trajectory.get("steps") or []:
        for key in ("screenshot_before", "screenshot_after"):
            if step.get(key):
                declared.add(str(step[key]))
    screenshots_ok = bool(declared)
    dimensions = []
    for name in sorted(declared):
        path = run_dir / "screenshots" / name
        try:
            header = path.read_bytes()[:24]
            if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise ValueError("not a PNG")
            width, height = struct.unpack(">II", header[16:24])
            dimensions.append((name, width, height))
            screenshots_ok &= width >= 320 and height >= 240
        except Exception:
            screenshots_ok = False
    judge.check("screenshots_plausible", screenshots_ok, repr(dimensions))
    return answer


def run_checks(
    task_number: int, judge: Judge, trajectory: dict, initial_db: str, after_db: str
) -> None:
    from answers import check_answer
    from state_checks import check_state

    answer = check_common(
        judge, trajectory, f"BabyCenter--{task_number}", initial_db, after_db
    )
    check_answer(task_number, answer, judge)
    check_state(task_number, initial_db, after_db, judge)

    def path(value):
        judge.check("visit_" + value, visited(trajectory, value), value)

    def query(value, **fields):
        judge.check(
            "filter_" + value + repr(fields),
            visited_query(trajectory, value, **fields),
            repr(fields),
        )

    def source_group(index, targets):
        path(index)
        for target in targets:
            judge.check(
                "source_path_" + target,
                paths_in_order(trajectory, [index, target]),
                target,
            )

    def filtered_source(index, target, **fields):
        observed = urls(trajectory)
        valid = False
        for offset, url in enumerate(observed):
            parsed = urlparse(url)
            values = parse_qs(parsed.query)
            if url_path(url) != index or not all(
                normalize((values.get(k) or [""])[0]) == normalize(v)
                for k, v in fields.items()
            ):
                continue
            if any(url_path(later) == target for later in observed[offset + 1 :]):
                valid = True
        judge.check("filtered_source_" + target, valid, repr(fields))

    def account():
        path("/account")
        final_url = trajectory.get("final_url") or (
            urls(trajectory)[-1] if urls(trajectory) else ""
        )
        judge.check("finish_on_account", url_path(final_url) == "/account", final_url)
        observations = trajectory.get("final_observed_text", "")
        if not observations:
            steps = trajectory.get("steps") or []
            if steps:
                observations = (
                    steps[-1].get("observed_text")
                    if steps[-1].get("action") == "done"
                    else steps[-1].get("extracted_content")
                )
        email = "jordan.lee@example.test" if task_number == 14 else "alice.j@test.com"
        judge.check(
            "authenticated_account_visible",
            email in str(observations),
            "final rendered account identity",
        )

    if task_number == 0:
        path("/due-date-calculator")
        judge.check(
            "linked_guide",
            paths_in_order(trajectory, ["/due-date-calculator", "/pregnancy/week-13"]),
            "calculator to linked guide",
        )
        # Both computed results must be observed. The cycles share one guide,
        # so do not require a duplicate visit or particular input/click events.
        observations = " ".join(
            str(step.get(key, ""))
            for step in trajectory.get("steps", [])
            if url_path(step.get("url", "")) == "/due-date-calculator"
            for key in ("observed_text", "extracted_content")
        )
        for day in (27, 30):
            judge.check(
                f"calculated_result_{day}",
                bool(re.search(rf"November\s+{day},?\s+2026", observations, re.I)),
                "due date observed in the rendered calculator result, not final answer",
            )
    elif task_number == 1:
        path("/baby/month-6")
        path("/baby/month-2")
    elif task_number == 2:
        path("/articles/prenatal-screening-explained")
        path("/articles/amniocentesis")
    elif task_number == 3:
        query("/articles", category="Prenatal Testing", trimester="Second trimester")
        targets = [
            "/articles/amniocentesis",
            "/articles/first-second-third-trimester-screen",
        ]
        source_group("/articles", targets)
        for target in targets:
            filtered_source(
                "/articles",
                target,
                category="Prenatal Testing",
                trimester="Second trimester",
            )
    elif task_number == 4:
        for week in (18, 20, 30):
            path(f"/pregnancy/week-{week}")
    elif task_number == 5:
        path("/pregnancy/week-30")
        path("/articles/fetal-growth-rate")
        account()
    elif task_number == 6:
        for month in (2, 6, 7, 10):
            path(f"/baby/month-{month}")
    elif task_number == 7:
        query("/search", q="sleep")
        source_group(
            "/search",
            ["/articles/infant-sleep-approaches", "/community/newborn-night-wakings"],
        )
        for target in (
            "/articles/infant-sleep-approaches",
            "/community/newborn-night-wakings",
        ):
            filtered_source("/search", target, q="sleep")
    elif task_number == 8:
        path("/community/starting-solids-allergens")
        path("/community/newborn-night-wakings")
    elif task_number in (9, 11):
        path("/articles/how-births-are-classified")
        path("/pregnancy/week-18")
        account()
    elif task_number == 10:
        path("/articles/infant-sleep-approaches")
        account()
    elif task_number in (12, 13):
        account()
    elif task_number == 14:
        path("/register")
        account()
    if task_number in (5, 9, 10, 11, 12, 13):
        judge.check(
            "alice_login",
            action_on(trajectory, "input", "/login", "alice.j@test.com"),
            "benchmark login input",
        )
    if task_number not in range(15):
        judge.check("known_task", False, str(task_number))


def fail_closed(task_id: str, error: Exception) -> None:
    print(
        json.dumps(
            {
                "task_id": task_id,
                "pass": False,
                "reason": f"verifier_error: {type(error).__name__}: {error}",
                "evidence": [],
            }
        )
    )
    raise SystemExit(1)


def main(task_number: int) -> None:
    task_id = f"BabyCenter--{task_number}"
    try:
        args = parse_args()
        trajectory = load_run(args.run_dir)
        judge = Judge(task_id)
        run_checks(task_number, judge, trajectory, args.initial_db, args.after_db)
        judge.emit()
    except SystemExit:
        raise
    except Exception as error:
        fail_closed(task_id, error)
