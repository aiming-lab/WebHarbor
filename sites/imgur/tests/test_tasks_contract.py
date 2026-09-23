"""Task contract checks for sites/imgur/tasks.jsonl.

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
WEB_NAME = "Imgur"
PORT = 40076


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
        assert row["verifier_path"] == f"sites/imgur/verify/verify_{int(row['id'].rsplit('--', 1)[1])}.py"
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
        assert row["upstream_url"].startswith("https://imgur.com"), row["upstream_url"]


def test_questions_are_substantial_and_varied():
    rows = read_rows()
    questions = set()
    for row in rows:
        question = row["ques"]
        assert len(question) >= 40, f"task {row['id']} question too short"
        assert len(question) <= 600, f"task {row['id']} question too long"
        # login tasks must carry the demo credentials
        if "log in" in question.lower() or "sign in" in question.lower():
            assert "TestPass123!" in question, f"{row['id']}: login task missing credentials"
        # strip the boilerplate login prefix so only the real task differs
        stripped = question.replace("Log in with the demo account (email: alice.j@test.com, password: TestPass123!)", "") \
                           .replace("Log in with the demo account (email: bob.c@test.com, password: TestPass123!)", "") \
                           .replace("Log in with the demo account (email: carol.d@test.com, password: TestPass123!)", "") \
                           .replace("Log in with the demo account (email: david.k@test.com, password: TestPass123!)", "")
        stripped = re.sub(r'^Log in as [^ ]+ \(password: [^)]+\)\. ', '', stripped)
        key = stripped[:60]
        assert key not in questions, f"duplicate task opening: {key!r}"
        questions.add(key)


def test_no_answer_like_artifacts():
    """The question text must not embed the answer for another task's DB fact."""
    rows = read_rows()
    for row in rows:
        # cheap sanity: no base64 blobs, no JSON payloads
        assert "{" not in row["ques"] or "TestPass123" in row["ques"]
        assert not re.search(r"[A-Za-z0-9+/]{40,}={0,2}", row["ques"])
