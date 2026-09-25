"""Task contract checks for sites/mta/tasks.jsonl.

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
WEB_NAME = "MTA"
PORT = 40093


def read_rows():
    assert TASKS.exists(), f"missing {TASKS}"
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    assert 15 <= len(rows) <= 25, f"expected 15-25 tasks, found {len(rows)}"
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
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["verifier_path"] == f"sites/mta/verify/verify_{index}.py"
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
        assert row["upstream_url"].startswith("https://new.mta.info"), row["upstream_url"]


def test_login_tasks_carry_demo_credentials():
    rows = read_rows()
    login_rows = [r for r in rows if "Log in" in r["ques"]]
    assert login_rows, "expected at least one login task"
    for row in login_rows:
        assert re.search(r"(alice\.j|bob\.c|carol\.d|david\.k)@test\.com", row["ques"]), row["id"]
        assert "TestPass123!" in row["ques"], row["id"]


def test_ques_length_and_distinctness():
    rows = read_rows()
    questions = [row["ques"] for row in rows]
    assert len(set(questions)) == len(questions), "duplicate task questions"
    for row in rows:
        words = len(row["ques"].split())
        assert words <= 100, f"{row['id']} exceeds the 100-word wording budget ({words})"
        assert words >= 25, f"{row['id']} suspiciously short ({words} words)"


def test_tasks_are_goal_oriented_not_step_lists():
    """Reject mechanical step-by-step instruction lists (see design-tasks)."""
    rows = read_rows()
    step_markers = re.compile(
        r"\b(click the|tap the|press the|select the (first|second) result|go back to|then click|"
        r"step 1|first click|next click)\b", re.I)
    for row in rows:
        assert not step_markers.search(row["ques"]), \
            f"{row['id']} reads like a mechanical step list"
