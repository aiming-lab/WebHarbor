"""Tasks contract for the public_storage mirror.

Contributor rows carry ONLY the task definition keys
(web_name, id, ques, web, upstream_url); the reviewer later appends
the grading keys verifier_path + judge_rubric. Rows in the merged tree
therefore carry exactly those two extra keys (all or none), while
answer material must never live in this agent-facing file.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"
REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}  # appended by the review contract
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected", "ground_truth", "solution"}


def load_tasks():
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_allowed_keys():
    for row in load_tasks():
        keys = set(row.keys())
        assert REQUIRED_KEYS <= keys, f"{row['id']}: missing keys {REQUIRED_KEYS - keys}"
        assert keys <= ALLOWED_KEYS, f"{row['id']}: unexpected keys {keys - ALLOWED_KEYS}"


def test_grading_keys_are_all_or_nothing():
    """verifier_path/judge_rubric are appended to every row or to none."""
    rows = load_tasks()
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) in (0, len(rows)), \
        f"grading keys appended to only {len(with_grading)} of {len(rows)} rows"
    for row in with_grading:
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["verifier_path"] == f"sites/public_storage/verify/verify_{index}.py", row["verifier_path"]
        assert row["judge_rubric"].strip(), f"{row['id']}: empty judge_rubric"
        assert row["judge_rubric"].isascii(), f"{row['id']}: rubric must be plain English"


def test_ids_sequential_and_unique():
    rows = load_tasks()
    assert [r["id"] for r in rows] == [f"Public Storage--{i}" for i in range(len(rows))]


def test_declared_port_is_assigned_port():
    for row in load_tasks():
        assert row["web"] == "http://localhost:40126/", row["id"]
        assert row["upstream_url"] == "https://www.publicstorage.com/"


def test_word_budget():
    for row in load_tasks():
        assert len(row["ques"].split()) <= 100, row["id"]


def test_no_answer_key_material():
    """Reservation codes / account numbers appear only as task *inputs*
    (codes the agent must look up), never as expected outputs."""
    for row in load_tasks():
        low = row["ques"].lower()
        # seeded benchmark passwords may appear (login tasks), but no
        # expected hold codes / payment confirmations
        assert "ps-pay-" not in low
        # reservation codes may appear only as lookup inputs (with the
        # matching email), never as values the agent is asked to produce
        for code in re.findall(r"ps-\d{7}", low):
            assert "@" in row["ques"], f"{row['id']}: bare code {code}"


def test_task_count_in_band():
    count = len(load_tasks())
    assert 15 <= count <= 25
