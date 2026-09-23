"""Task contract checks for sites/landwatch/tasks.jsonl.

A contributor's tasks.jsonl carries the task definition per row:
web_name, id, ques, web, upstream_url. The reviewer's grading contract
appends verifier_path + judge_rubric inline (see verify/README.md) — the
appended keys point at the deterministic verifiers and are checked for
integrity below. Ground truth (answer keys) must never live in this
agent-facing file.
"""
import json
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent
TASKS = SITE / "tasks.jsonl"

REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
REVIEWER_KEYS = {"verifier_path", "judge_rubric"}
FORBIDDEN_KEYS = {"answer", "answers", "expected"}
WEB_NAME = "LandWatch"
PORT = 40089
LOGIN_BOILERPLATE = re.compile(
    r"Log in with the demo account \(email: [a-z.]+@test\.com, password: TestPass123!\),?\s*")


def read_rows():
    assert TASKS.exists(), f"missing {TASKS}"
    rows = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_rows_have_exactly_the_basic_keys():
    rows = read_rows()
    assert 25 <= len(rows) <= 35, f"expected ~30 tasks, found {len(rows)}"
    for index, row in enumerate(rows):
        keys = set(row)
        assert REQUIRED_KEYS <= keys, f"row {index} missing keys: {REQUIRED_KEYS - keys}"
        assert keys <= REQUIRED_KEYS | REVIEWER_KEYS, (
            f"row {index} carries unexpected keys: {keys - REQUIRED_KEYS - REVIEWER_KEYS}")
        leaked = keys & FORBIDDEN_KEYS
        assert not leaked, f"row {index} leaks grading keys: {leaked}"


def test_reviewer_keys_point_at_the_contract():
    rows = read_rows()
    for index, row in enumerate(rows):
        if "verifier_path" not in row:
            continue
        assert row["verifier_path"] == f"sites/landwatch/verify/verify_{index}.py", row["id"]
        assert (SITE.parent.parent / row["verifier_path"]).is_file(), row["verifier_path"]
        assert "FACT CHECKPOINTS" in row["judge_rubric"], row["id"]
        assert "Empty answer = FAIL" in row["judge_rubric"], row["id"]


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
        assert row["upstream_url"].startswith("https://www.landwatch.com"), row["upstream_url"]


def test_questions_are_substantial_and_varied():
    rows = read_rows()
    openings = set()
    for row in rows:
        question = row["ques"]
        assert 40 <= len(question) <= 800, f"task {row['id']} question length {len(question)}"
        lowered = question.lower()
        if "demo account" in lowered:
            assert "TestPass123!" in question, f"{row['id']}: login task missing credentials"
            assert re.search(r"[a-z.]+@test\.com", question), f"{row['id']}: login task missing email"
        stripped = LOGIN_BOILERPLATE.sub("", question)[:60]
        assert stripped not in openings, f"duplicate task opening: {stripped!r}"
        openings.add(stripped)


def test_no_answer_like_artifacts():
    rows = read_rows()
    for row in rows:
        assert "```" not in row["ques"], f"{row['id']}: code block in question"
        assert not re.search(r"\bsha256\b", row["ques"].lower()), f"{row['id']}: hash artifact"


def test_functional_breadth():
    rows = read_rows()
    joined = " ".join(row["ques"].lower() for row in rows)
    for phrase in ("land for sale", "filter", "sort", "agent", "log in",
                   "saved search", "listing", "price"):
        assert phrase in joined, f"no task touches '{phrase}'"
    multi_step = sum(1 for row in rows if len(row["ques"]) >= 160)
    assert multi_step >= 8, f"only {multi_step} long multi-step tasks"
