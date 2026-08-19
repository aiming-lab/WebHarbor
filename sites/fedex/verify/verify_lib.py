#!/usr/bin/env python3
"""Shared deterministic verifier harness for the FedEx task contract."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


SITE = "fedex"


@dataclass(frozen=True)
class VerifyArgs:
    run_dir: str
    initial_db: str = ""
    after_db: str = ""
    container: str = os.environ.get("WH_CONTAINER", "wh-review")
    no_llm: bool = False


@dataclass(frozen=True)
class TaskSpec:
    required_paths: tuple[str, ...]
    answer_groups: tuple[tuple[str, ...], ...]
    state_check: Callable[[VerifyArgs], tuple[bool, str]] | None = None


def parse_args() -> VerifyArgs:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument("--container", default=os.environ.get("WH_CONTAINER", "wh-review"))
    parser.add_argument("--no_llm", nargs="?", const="true", default="false")
    values = parser.parse_args()
    return VerifyArgs(
        run_dir=values.run_dir,
        initial_db=values.initial_db,
        after_db=values.after_db,
        container=values.container,
        no_llm=str(values.no_llm).casefold() in {"1", "true", "yes", "on"},
    )


def load_run(run_dir: str) -> dict:
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def navigated_to(trajectory: dict, path_fragment: str) -> bool:
    expected = path_fragment.casefold()
    return any(expected in str(step.get("url", "")).casefold() for step in trajectory.get("steps", []))


def final_answer(trajectory: dict) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def answer_contains(answer: str, alternative: str) -> bool:
    normalized_answer = normalized(answer)
    normalized_alternative = normalized(alternative)
    left_boundary = r"(?<![a-z0-9])" if normalized_alternative[:1].isalnum() else ""
    right_boundary = r"(?![a-z0-9])" if normalized_alternative[-1:].isalnum() else ""
    return bool(re.search(left_boundary + re.escape(normalized_alternative) + right_boundary, normalized_answer))


def fetch_db(container: str, kind: str) -> str | None:
    fd, target = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, target], capture_output=True, text=True)
    if result.returncode == 0:
        return target
    Path(target).unlink(missing_ok=True)
    return None


def resolve_db(explicit_path: str, container: str, kind: str) -> str | None:
    if explicit_path:
        return explicit_path if Path(explicit_path).is_file() else None
    return fetch_db(container, kind)


def query_one(db_path: str, sql: str, params: tuple = ()) -> tuple | None:
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, params).fetchone()
    finally:
        connection.close()


class Judge:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.passed = True
        self.reason = ""
        self.evidence: list[str] = []

    def check(self, name: str, condition: bool, evidence: str) -> None:
        if condition:
            self.evidence.append(f"[PASS] {name}: {evidence}")
            return
        self.passed = False
        if not self.reason:
            self.reason = name
        self.evidence.append(f"[FAIL] {name}: {evidence}")

    def emit(self) -> None:
        print(json.dumps({"task_id": self.task_id, "pass": self.passed, "reason": self.reason, "evidence": self.evidence}, indent=2))
        raise SystemExit(0 if self.passed else 1)


def shipment_state_matches(args: VerifyArgs) -> tuple[bool, str]:
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        return False, "initial or after-state database unavailable"
    initial_row = query_one(initial_db, "SELECT COUNT(*) FROM shipments WHERE tracking_number = ?", ("FDX260000061",))
    row = query_one(
        after_db,
        """SELECT COUNT(*), u.email, s.recipient_name, s.origin_city, s.origin_state,
                  s.destination_city, s.destination_state, s.package_type,
                  s.package_weight, s.declared_value, s.service_slug, s.reference_label
             FROM shipments s JOIN users u ON u.id = s.user_id
            WHERE s.tracking_number = ?""",
        ("FDX260000061",),
    )
    expected = (1, "alice.j@test.com", "Alex Brown", "Seattle", "WA", "Boston", "MA", "Box", 6.0, 240.0, "fedex-2day", "Local demo shipment")
    ok = bool(initial_row and initial_row[0] == 0 and row == expected)
    return ok, f"initial_count={initial_row[0] if initial_row else None}; after={row!r}"


def pickup_state_matches(args: VerifyArgs) -> tuple[bool, str]:
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        return False, "initial or after-state database unavailable"
    initial_row = query_one(initial_db, "SELECT COUNT(*) FROM pickup_requests WHERE confirmation_code = ?", ("PU-2609",))
    row = query_one(
        after_db,
        """SELECT COUNT(*), u.email, l.slug, p.slot_date, p.time_window,
                  p.package_count, p.status
             FROM pickup_requests p
             JOIN users u ON u.id = p.user_id
             JOIN locations l ON l.id = p.location_id
            WHERE p.confirmation_code = ?""",
        ("PU-2609",),
    )
    expected = (1, "alice.j@test.com", "seattle-downtown-wa", "2026-06-05", "9:00 AM - 11:00 AM", 1, "Scheduled")
    ok = bool(initial_row and initial_row[0] == 0 and row == expected)
    return ok, f"initial_count={initial_row[0] if initial_row else None}; after={row!r}"


TASK_SPECS: dict[int, TaskSpec] = {
    0: TaskSpec(("/track/results", "/tracking/FDX260000004"), (("los angeles",), ("weather",))),
    1: TaskSpec(("/track/results", "/tracking/FDX260000001"), (("fdx260000001",), ("delivered",), ("required", "yes"))),
    2: TaskSpec(("/support", "/support/shipment-exception-status"), (("demo workflow",), ("tracking help",))),
    3: TaskSpec(("/rate-estimate",), (("fedex ground home delivery",), ("$37.40", "37.4"))),
    4: TaskSpec(("/rate-estimate",), (("fedex priority overnight",), ("fedex ground home delivery",), ("$43.80", "43.8"))),
    5: TaskSpec(("/login", "/account/shipments", "/invoices"), (("inv-260001",),)),
    6: TaskSpec(("/login", "/claims"), (("clm-2623",), ("fdx260000023",))),
    7: TaskSpec(("/login", "/account"), (("pu-2621",), ("9:00 am", "9 am"), ("11:00 am", "11 am"))),
    8: TaskSpec(("/login", "/account/shipments"), (("sh-260050",), ("charlotte",), ("sh-260055",), ("los angeles",), ("sh-260060",), ("seattle",))),
    9: TaskSpec(("/locations", "/locations/dallas-arts-tx"), (("freight cutoff",), ("4:45 pm",))),
    10: TaskSpec(("/locations", "/locations/miami-brickell-fl"), (("international docs",), ("5:45 pm",))),
    11: TaskSpec(("/search", "/support/weather-delay-guidance"), (("tracking",), ("billing",), ("pickup",))),
    12: TaskSpec(("/login", "/ship", "/ship/service", "/ship/review", "/ship/confirmation"), (("fdx260000061",),), shipment_state_matches),
    13: TaskSpec(("/login", "/pickup", "/account"), (("pu-2609",),), pickup_state_matches),
    14: TaskSpec(("/search", "/locations/seattle-downtown-wa"), (("7:00 am", "7 am"), ("9:00 pm", "9 pm"))),
    15: TaskSpec(("/login", "/claims"), (("clm-2653",), ("fdx260000053",))),
    16: TaskSpec(("/track/results", "/tracking/FDX260000500"), (("delivered",), ("los angeles",), ("ca", "california"))),
    17: TaskSpec(("/rate-estimate",), (("fedex freight economy",), ("$191.40", "191.4"))),
}


def run_task(index: int) -> None:
    args = parse_args()
    task_id = f"FedEx--{index}"
    spec = TASK_SPECS[index]
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    judge = Judge(task_id)
    judge.check("task_id_matches", trajectory.get("task_id") == task_id, f"trajectory_task_id={trajectory.get('task_id')!r}")
    for required_path in spec.required_paths:
        judge.check(f"navigated_{required_path}", navigated_to(trajectory, required_path), f"required_path={required_path}")
    judge.check("non_empty_answer", bool(answer), f"final={answer!r}")
    for group_number, alternatives in enumerate(spec.answer_groups, start=1):
        matched = any(answer_contains(answer, alternative) for alternative in alternatives)
        judge.check(f"answer_fact_{group_number}", matched, f"accepted_alternatives={alternatives!r}; final={answer!r}")
    if spec.state_check:
        matched, evidence = spec.state_check(args)
        judge.check("after_state_matches", matched, evidence)
    judge.emit()


if __name__ == "__main__":
    raise SystemExit("Run a per-task verify_N.py entry point.")
