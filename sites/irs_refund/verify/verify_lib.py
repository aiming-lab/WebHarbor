#!/usr/bin/env python3
"""Deterministic grading helpers for the IRS Refund Tracker tasks.

Every task requires a frozen answer and task-specific URL evidence in the
recorded trajectory. Task 8 additionally compares the seed and live SQLite
databases so a plausible self-report cannot pass without the requested profile
transition.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


SITE = "irs_refund"
TASK_COUNT = 18
STATEFUL_TASKS = {8}


def _alt(*groups):
    """One valid navigation alternative made from required URL groups."""
    return tuple(
        tuple(group) if isinstance(group, (list, tuple)) else (group,)
        for group in groups
    )


def _lookup(reference_code, *extra):
    return _alt(
        f"/refund-status/start?case={reference_code}",
        "/refund-status/verify",
        "/refund-status/result",
        *extra,
    )


NAV_ALTERNATIVES = {
    0: (_lookup("wmr-2024-8554"),),
    1: (_lookup("wmr-2025-8776"),),
    2: (_lookup("wmr-2023-8887"),),
    3: (_lookup("wmr-2024-9009"),),
    4: (_alt("/search", "q=amended return", "/help/amended-return-wait-times"),),
    5: (_alt("/notices", "/notices/id-221"),),
    6: (_alt("/login", ("/account", "/lookup-history")),),
    7: (_alt("/login", ("/account", "/lookup-history")),),
    8: (_alt("/login", "/account/edit"),),
    9: (_alt("/login", "/lookup-history"),),
    10: (_lookup("wmr-2025-8665"),),
    11: (_lookup("wmr-2025-8221", "/notices/id-221"),),
    12: (_lookup("wmr-2025-8776"),),
    13: (_alt(
        "/search",
        "q=split deposit",
        "/refund-status/start?case=wmr-2024-8554",
        "/refund-status/verify",
        "/refund-status/result",
    ),),
    14: (_alt("/notices?stage=refund sent"),),
    15: (_alt("/faq"),),
    16: (_alt("/login", "/lookup-history"),),
    17: (_lookup("wmr-2023-8887", "/refund-status/summary"),),
}


PASS_ANSWERS = {
    0: "Nora Patel's expected delivery method is split deposit.",
    1: "Priya Shah's refund is delayed because identity verification is needed.",
    2: "Theo Martinez's refund is only approved so far; it has not been sent.",
    3: "Grant Okafor's current stage is Return Received.",
    4: "Amended synthetic returns stay in review longer than standard returns.",
    5: "ID-221 asks the user to open the checklist, confirm the demo address, and review the stored contact preference.",
    6: "Bob Chen's 2025 entry is Delayed: Identity Verification Needed.",
    7: "2024 is further along: it is Refund Sent, while 2025 is only Refund Approved.",
    8: "David Kim's preferred contact method is now Email and his city is Spokane.",
    9: "Carol Davis's mismatch practice entry has ZIP code 00000.",
    10: "The result says the ZIP code is incorrect.",
    11: "The linked notice code is ID-221.",
    12: "One checklist item is to verify the stored mailing ZIP code.",
    13: "Nora Patel's result shows split deposit.",
    14: "The split-deposit allocation notice is SP-177.",
    15: "No. A guest session does not save lookup history; the user must sign in to an account.",
    16: "Alice Johnson's prior-year paper-check entry is $980.",
    17: "Theo Martinez's printable summary lists paper check.",
}


EXPECTED = {
    0: "Nora Patel; split deposit",
    1: "Priya Shah; identity-verification delay",
    2: "Refund Approved, not sent",
    3: "Return Received",
    4: "amended returns stay in review longer than standard returns",
    5: "confirm demo address and review stored contact preference",
    6: "Delayed: Identity Verification Needed",
    7: "2024 Refund Sent is further along than 2025 Refund Approved",
    8: "Email and Spokane, plus matching DB state",
    9: "ZIP 00000",
    10: "ZIP code",
    11: "ID-221",
    12: "one identity-verification checklist item",
    13: "split deposit",
    14: "SP-177",
    15: "guest history is not saved; sign-in required",
    16: "$980",
    17: "paper check on printable summary",
}


def load_run(run_dir):
    return json.loads((Path(run_dir) / "trajectory.json").read_text())


def step_urls(traj):
    return [
        unquote(str(step.get("url", ""))).replace("+", " ").casefold()
        for step in traj.get("steps", [])
    ]


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def _navigation_ok(task_index, traj):
    urls = step_urls(traj)
    for alternative in NAV_ALTERNATIVES[task_index]:
        if all(
            any(any(needle.casefold() in url for needle in group) for url in urls)
            for group in alternative
        ):
            return True, urls
    return False, urls


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _has_all(text, *tokens):
    value = _norm(text)
    return all(_norm(token) in value for token in tokens)


def _has_any(text, *tokens):
    value = _norm(text)
    return any(_norm(token) in value for token in tokens)


def _numbers(text):
    cleaned = (text or "").replace(",", "")
    return [
        float(value)
        for value in re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?", cleaned)
    ]


def _has_number(text, expected, tolerance=0.005):
    return any(
        math.isclose(value, expected, abs_tol=tolerance, rel_tol=0)
        for value in _numbers(text)
    )


def answer_ok(task_index, answer):
    if not answer.strip():
        return False
    if task_index in {0, 13}:
        return _has_all(answer, "split deposit")
    if task_index == 1:
        return _has_all(answer, "identity", "verification")
    if task_index == 2:
        return _has_all(answer, "approved") and _has_any(
            answer, "not sent", "not been sent", "only approved"
        )
    if task_index == 3:
        return _has_all(answer, "return received")
    if task_index == 4:
        return _has_all(answer, "longer", "standard", "return")
    if task_index == 5:
        return _has_all(answer, "address", "contact", "preference")
    if task_index == 6:
        return _has_all(answer, "identity", "verification", "needed")
    if task_index == 7:
        return _has_all(answer, "2024", "2025", "sent", "approved")
    if task_index == 8:
        return _has_all(answer, "email", "spokane")
    if task_index == 9:
        return bool(re.search(r"(?<!\d)0{5}(?!\d)", answer))
    if task_index == 10:
        return _has_all(answer, "zip")
    if task_index == 11:
        return _has_all(answer, "id-221")
    if task_index == 12:
        return any(
            _has_all(answer, *tokens)
            for tokens in (
                ("photo", "id", "name"),
                ("mailing", "zip"),
                ("preferred", "contact", "method"),
            )
        )
    if task_index == 14:
        return _has_all(answer, "sp-177")
    if task_index == 15:
        return (
            _has_any(answer, "no", "does not", "doesn't", "not save")
            and _has_all(answer, "history")
            and _has_any(answer, "sign in", "signed in", "account")
        )
    if task_index == 16:
        return _has_number(answer, 980)
    if task_index == 17:
        return _has_all(answer, "paper check")
    raise ValueError(f"unknown task index: {task_index}")


def _fetch_db(container, kind):
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    result = subprocess.run(
        ["docker", "cp", source, path], capture_output=True, text=True
    )
    if result.returncode:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    return path


def _resolve_db(path, container, kind):
    return path or _fetch_db(container, kind)


def _query(db_path, sql, params=()):
    if not db_path or not Path(db_path).exists():
        return None
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _david_profile(db_path):
    rows = _query(
        db_path,
        "SELECT city, preferred_contact_method FROM users WHERE email=?",
        ("david.k@test.com",),
    )
    return rows[0] if rows and len(rows) == 1 else None


def _profile_state_ok(initial_db, after_db):
    before = _david_profile(initial_db)
    after = _david_profile(after_db)
    ok = before == ("Seattle", "Mail") and after == ("Spokane", "Email")
    return ok, f"initial={before!r}; after={after!r}"


STATE_CHECKS = {8: ("profile_after_state", _profile_state_ok)}


def evaluate(task_index, traj, initial_db="", after_db="", container="wh-review"):
    if task_index not in NAV_ALTERNATIVES:
        raise ValueError(f"unknown task index: {task_index}")
    answer = final_answer(traj)
    navigation_ok, urls = _navigation_ok(task_index, traj)
    checks = [
        ("final_answer_nonempty", bool(answer), f"final={answer!r}"),
        ("required_navigation", navigation_ok, f"urls={urls!r}"),
        (
            "frozen_answer",
            answer_ok(task_index, answer),
            f"expected={EXPECTED[task_index]}; final={answer!r}",
        ),
    ]
    if task_index in STATEFUL_TASKS:
        initial_db = _resolve_db(initial_db, container, "instance_seed")
        after_db = _resolve_db(after_db, container, "instance")
        name, state_check = STATE_CHECKS[task_index]
        ok, detail = state_check(initial_db, after_db)
        checks.append((name, ok, detail))

    passed = all(ok for _, ok, _ in checks)
    reason = next((name for name, ok, _ in checks if not ok), "")
    evidence = [
        f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
        for name, ok, detail in checks
    ]
    return {
        "task_id": f"IRS Refund Tracker--{task_index}",
        "pass": passed,
        "reason": reason,
        "evidence": evidence,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument(
        "--container", default=os.environ.get("WH_CONTAINER", "wh-review")
    )
    parser.add_argument("--no_llm", nargs="?", const="True", default="False")
    return parser.parse_args()


def main(task_index):
    args = parse_args()
    verdict = evaluate(
        task_index,
        load_run(args.run_dir),
        initial_db=args.initial_db,
        after_db=args.after_db,
        container=args.container,
    )
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["pass"] else 1)
