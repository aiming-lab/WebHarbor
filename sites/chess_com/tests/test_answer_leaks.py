"""tasks.jsonl contract tests: five-key rows, no answer leakage, stable ids.

The contributor contract is one row per task with exactly the keys
web_name, id, ques, web, upstream_url (the reviewer appends verifier_path
and judge_rubric later). No row may carry an answer key or a truth string
that would let a solver skip the navigation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
TASKS = SITE / "tasks.jsonl"

CONTRIBUTOR_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}


def _rows():
    return [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_tasks_count_in_expected_range():
    rows = _rows()
    assert 20 <= len(rows) <= 32, f"expected ~30 tasks, got {len(rows)}"


def test_every_row_has_exactly_the_contributor_keys():
    # Reviewer-stage contract (see verify_lib.py / the review-env skill): after the reviewer's
    # pass each row carries the five contributor keys plus exactly the two grading-contract
    # keys (verifier_path, judge_rubric). No other key may appear.
    reviewer_keys = {"verifier_path", "judge_rubric"}
    for i, row in enumerate(_rows()):
        assert set(row) == CONTRIBUTOR_KEYS | reviewer_keys, f"row {i} has keys {sorted(row)}"
        assert row["verifier_path"].startswith("sites/chess_com/verify/verify_"), row["verifier_path"]
        assert row["judge_rubric"].strip(), f"row {i} has an empty judge_rubric"


def test_no_answer_key_anywhere():
    for i, row in enumerate(_rows()):
        for key in row:
            assert "answer" not in key.lower(), f"row {i} key {key}"
    raw = TASKS.read_text(encoding="utf-8")
    assert "answer_key" not in raw


def test_rows_declare_the_site_port_consistently():
    ports = {row["web"] for row in _rows()}
    assert ports == {"http://localhost:40072/"}, ports


def test_ids_sequential_and_unique():
    ids = [row["id"] for row in _rows()]
    assert len(ids) == len(set(ids)), "duplicate task ids"
    assert ids == sorted(ids, key=lambda s: int(s.rsplit("--", 1)[1]))
    web_names = {row["web_name"] for row in _rows()}
    assert web_names == {"Chess.com"}, web_names


def test_questions_are_navigable_prompts_not_statements():
    for i, row in enumerate(_rows()):
        q = row["ques"].strip()
        assert q.endswith("?") or any(w in q.lower() for w in
                                     ("report", "list", "how many", "find", "open",
                                      "make sure", "solve", "join", "log in")), \
            f"row {i} is not an actionable prompt: {q[:60]}"
        assert len(q) >= 60, f"row {i} question suspiciously short"


def test_upstream_urls_are_chess_com_pages():
    for i, row in enumerate(_rows()):
        u = row["upstream_url"]
        assert u.startswith("https://www.chess.com/"), f"row {i} upstream {u}"


def test_stateful_tasks_are_idempotent():
    """Stateful prompts must converge to a state (never a blind toggle), so a
    verifier re-run cannot destroy the state being graded."""
    stateful = [row for row in _rows()
                if re.search(r"\b(follow|join|mark|complete|set your location|solve)\b", row["ques"], re.I)]
    assert len(stateful) >= 4, "expected several stateful tasks"
    for row in stateful:
        q = row["ques"].lower()
        if "log in" in q or "make sure" in q:
            continue
        # any prompt that mutates state without a 'make sure / if not already'
        # guard would toggle on re-run and is a grading hazard
        assert ("make sure" in q) or ("if you are not" in q) or ("set your location" in q) \
            or ("mark all" in q) or ("solve the" in q), row["id"]


def test_no_truth_leak_between_tasks_and_templates():
    """Task ids never embed the literal answers their graders check."""
    template_dir = SITE / "templates"
    for row in _rows():
        # ids are Chess.com--N only
        assert re.fullmatch(r"Chess\.com--\d+", row["id"]), row["id"]
