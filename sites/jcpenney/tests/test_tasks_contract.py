"""Task contract checks for sites/jcpenney/tasks.jsonl.

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
WEB_NAME = "JCPenney"
PORT = 40089  # branch array position (slot 73 declared; audit re-slots at integration)
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
    assert 15 <= len(rows) <= 25, f"expected the 15-task redesign set, found {len(rows)}"
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
        assert row["verifier_path"] == f"sites/jcpenney/verify/verify_{int(row['id'].rsplit('--', 1)[1])}.py"
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
        assert row["upstream_url"].startswith("https://www.jcpenney.com"), row["upstream_url"]


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
    for phrase in ("bag", "order", "wish list", "coupon", "store", "review"):
        assert phrase in joined, f"no task touches '{phrase}'"
    multi_step = sum(1 for row in rows if len(row["ques"]) >= 160)
    assert multi_step >= 5, f"only {multi_step} long multi-step tasks"
