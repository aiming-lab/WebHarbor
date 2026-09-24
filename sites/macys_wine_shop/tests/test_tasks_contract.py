"""Contract tests for macys_wine_shop tasks.jsonl (seven-key grading rows).

Per the round-2 depth re-review (F1): every tasks.jsonl row carries the
contributor task definition AND the grading contract — web_name, id, ques,
web, upstream_url (five keys, no answer key) plus the two appended grading
keys verifier_path + judge_rubric, in the repo-wide seven-key convention
(imgur/chase). The five-key prefix stays byte-identical; the two grading
keys are string-appended (never answer keys). The redesigned set is 16 deep
functional-chain tasks (MacysWineShop--0..--15), sequential ids, one row per
task, each row wired to its own deterministic verifier.
"""
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}  # appended grading contract
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected", "solution"}
LOGIN_EMAILS = ("alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com")
REPO_ROOT = SITE.parents[1]


def read_rows():
    assert TASKS.exists(), "tasks.jsonl missing"
    return [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_sixteen_deep_tasks():
    rows = read_rows()
    assert 15 <= len(rows) <= 18, f"expected the redesigned 15-18 task set, found {len(rows)}"
    assert len(rows) == 16


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    for index, row in enumerate(rows):
        keys = set(row)
        assert REQUIRED_KEYS <= keys, f"row {index} missing keys: {REQUIRED_KEYS - keys}"
        extra = keys - ALLOWED_KEYS
        assert not extra, f"row {index} carries unexpected keys: {extra}"
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"row {index} leaks answer keys: {leaked}"


def test_grading_keys_on_every_row():
    """The 7-key contract: verifier_path/judge_rubric appended to ALL 16 rows
    (round-2 re-review F1 — five-key rows break the scoring pipeline: agent_demo
    reads judge_rubric/verifier_path straight from the row)."""
    rows = read_rows()
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) == len(rows) == 16, \
        f"grading keys appended to only {len(with_grading)} of {len(rows)} rows"
    for index, row in enumerate(rows):
        assert row["verifier_path"] == f"sites/macys_wine_shop/verify/verify_{index}.py", \
            row["verifier_path"]
        assert len(str(row["judge_rubric"])) >= 80, \
            f"row {index} carries no substantive judge_rubric"


def test_verifier_path_wires_row_to_matching_verifier():
    """verifier_path points at a tracked verifier whose TASK_ID is the row id."""
    import re

    rows = read_rows()
    for index, row in enumerate(rows):
        verifier = REPO_ROOT / row["verifier_path"]
        assert verifier.is_file(), f"missing verifier for row {index}: {verifier}"
        text = verifier.read_text(encoding="utf-8")
        task_ids = re.findall(r'^TASK_ID = "(MacysWineShop--\d+)"', text, re.M)
        assert task_ids == [row["id"]], \
            f"verifier for row {index} declares TASK_ID={task_ids!r}, row id={row['id']!r}"


def test_sequential_ids():
    rows = read_rows()
    for index, row in enumerate(rows):
        assert row["id"] == f"MacysWineShop--{index}", row["id"]


def test_port_and_upstream_match_registry():
    rows = read_rows()
    for row in rows:
        assert row["web_name"] == "Macy's Wine Shop"
        # audit-stage declared slot: parallel-station index 89 -> 40082
        assert row["web"] == "http://localhost:40082/", row["web"]
        assert row["upstream_url"] == "https://macyswineshop.com/"


def test_no_ground_truth_leak():
    text = TASKS.read_text(encoding="utf-8").lower()
    for token in ("answer:", "expected:", "solution:", "the answer is"):
        assert token not in text


def test_goal_style_wording():
    rows = read_rows()
    for row in rows:
        words = len(row["ques"].split())
        assert 20 <= words <= 100, f"{row['id']} has an out-of-band question length ({words})"


def test_login_tasks_carry_demo_credentials():
    rows = read_rows()
    login_rows = [r for r in rows if "Log in with the demo account" in r["ques"]]
    assert len(login_rows) >= 4
    for row in login_rows:
        assert any(email in row["ques"] for email in LOGIN_EMAILS), row["id"]
        assert "TestPass123!" in row["ques"], row["id"]


def test_questions_are_distinct():
    questions = [r["ques"] for r in read_rows()]
    assert len(set(questions)) == len(questions), "duplicate task questions"
