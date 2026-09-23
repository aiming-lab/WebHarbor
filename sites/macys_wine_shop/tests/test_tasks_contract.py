"""Contract tests for macys_wine_shop tasks.jsonl (contributor schema + merged grading keys)."""
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

# Five basic task-definition keys (contributor schema).
BASIC_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
# Post-review 7-key row shape (same merged convention as the other audited sites):
# the basic keys plus the reviewer-appended grading keys verifier_path + judge_rubric.
MERGED_KEYS = BASIC_KEYS | {"verifier_path", "judge_rubric"}
FORBIDDEN_KEYS = {"answer", "expected", "solution"}


def test_tasks_file_exists():
    assert TASKS.exists(), "tasks.jsonl missing"


def test_thirty_tasks():
    rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert 25 <= len(rows) <= 35
    assert len(rows) == 30


def test_only_basic_keys():
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert set(row.keys()) == MERGED_KEYS, f"keys must be {sorted(MERGED_KEYS)}: {row.keys()}"
        for key in FORBIDDEN_KEYS:
            assert key not in row
        # the appended grading keys must point at this site's verifier contract
        assert row["verifier_path"].startswith("sites/macys_wine_shop/verify/verify_"), row["verifier_path"]
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS"), row["judge_rubric"][:40]


def test_sequential_ids():
    rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    for i, row in enumerate(rows):
        assert row["id"] == f"MacysWineShop--{i}", row["id"]


def test_port_matches_registry():
    rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        # audit-stage declared slot: parallel-station index 89 -> 40089
        assert row["web"] == "http://localhost:40089/", row["web"]
        assert row["upstream_url"] == "https://macyswineshop.com/"


def test_no_ground_truth_leak():
    text = TASKS.read_text(encoding="utf-8").lower()
    for token in ("answer:", "expected:", "solution:", "the answer is"):
        assert token not in text


def test_login_tasks_carry_credentials():
    rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    login_rows = [r for r in rows if "Log in with the demo account" in r["ques"]]
    assert len(login_rows) >= 4
    for row in login_rows:
        assert "alice.j@test.com" in row["ques"] or \
               "bob.c@test.com" in row["ques"] or \
               "carol.d@test.com" in row["ques"] or \
               "david.k@test.com" in row["ques"]
        assert "TestPass123!" in row["ques"]
