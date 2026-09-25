"""Task contract checks for sites/medicare_gov/tasks.jsonl.

A contributor's tasks.jsonl carries ONLY the task definition per row:
web_name, id, ques, web, upstream_url. Ground truth (verifier_path,
judge_rubric) is appended later by the reviewer's grading contract — rows in
the merged tree therefore carry exactly those two extra keys, while answer
material must never live in this agent-facing file.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}  # appended by the review contract
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected"}
WEB_NAME = "Medicare.gov"
PORT = 40085


def read_rows():
    assert TASKS.exists(), f"missing {TASKS}"
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    # depth-review round 2 rebuilt the task set: 30 shallow tasks -> 15 deep
    # functional-chain tasks (see sites/medicare_gov/verify/README.md)
    assert len(rows) == 15, f"expected the 15 redesigned deep tasks, found {len(rows)}"
    for index, row in enumerate(rows):
        keys = set(row)
        assert REQUIRED_KEYS <= keys, f"row {index} missing keys: {REQUIRED_KEYS - keys}"
        extra = keys - ALLOWED_KEYS
        assert not extra, f"row {index} carries unexpected keys: {extra}"
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"row {index} leaks answer keys: {leaked}"


def test_grading_keys_are_all_or_nothing():
    """verifier_path/judge_rubric are appended to every row or to none."""
    rows = read_rows()
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) in (0, len(rows)), \
        f"grading keys appended to only {len(with_grading)} of {len(rows)} rows"
    for row in with_grading:
        assert row["verifier_path"] == f"sites/medicare_gov/verify/verify_{int(row['id'].rsplit('--', 1)[1])}.py"
        assert row["judge_rubric"].strip()


def test_ids_are_unique_and_sequential():
    rows = read_rows()
    ids = [row["id"] for row in rows]
    assert len(set(ids)) == len(ids), "duplicate task ids"
    for index, row in enumerate(rows):
        assert row["id"] == f"{WEB_NAME}--{index}", f"row {index} id {row['id']!r}"


def test_web_and_upstream_urls():
    rows = read_rows()
    for row in rows:
        assert row["web_name"] == WEB_NAME
        assert row["web"] == f"http://localhost:{PORT}/", row["web"]
        assert row["upstream_url"].startswith("https://www.medicare.gov"), row["upstream_url"]


def test_login_tasks_carry_demo_credentials():
    rows = read_rows()
    login_rows = [r for r in rows if "Log in" in r["ques"]]
    assert login_rows, "expected at least one login task"
    for row in login_rows:
        assert "alice.j@test.com" in row["ques"] or "bob.c@test.com" in row["ques"] \
            or "carol.d@test.com" in row["ques"] or "david.k@test.com" in row["ques"], row["id"]
        assert "TestPass123!" in row["ques"], row["id"]


def test_ques_length_and_distinctness():
    rows = read_rows()
    questions = [r["ques"] for r in rows]
    assert len(set(questions)) == len(questions), "duplicate task questions"
    for row in rows:
        assert 40 <= len(row["ques"]) <= 700, f"{row['id']} has an out-of-band question length"
