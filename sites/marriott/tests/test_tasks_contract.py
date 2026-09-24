"""Tasks contract for the marriott mirror.

Contributor rows carry ONLY the task definition keys
(web_name, id, ques, web, upstream_url); the reviewer later appends the
grading keys verifier_path + judge_rubric. Rows in the merged tree therefore
carry exactly those two extra keys (all or none), while answer material must
never live in this agent-facing file.
"""
import json
import pathlib

TASKS = pathlib.Path(__file__).resolve().parent.parent / "tasks.jsonl"
REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}  # appended by the review contract
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected", "ground_truth", "solution"}


def test_tasks_file_exists_and_nonempty():
    assert TASKS.exists(), "tasks.jsonl missing"
    lines = [l for l in TASKS.read_text().splitlines() if l.strip()]
    assert 15 <= len(lines) <= 25, (
        f"expected 15-25 tasks, found {len(lines)}")


def test_task_rows_have_exactly_the_basic_keys():
    seen_ids = set()
    for i, line in enumerate(TASKS.read_text().splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        keys = set(row.keys())
        assert REQUIRED_KEYS <= keys, f"row {i}: missing keys {REQUIRED_KEYS - keys}"
        assert keys <= ALLOWED_KEYS, f"row {i}: unexpected keys {keys - ALLOWED_KEYS}"
        for key, value in row.items():
            assert isinstance(value, str) and value.strip(), f"row {i}: empty {key}"
        assert row["web_name"] == "Marriott", f"row {i}: web_name {row['web_name']!r}"
        assert row["id"] not in seen_ids, f"row {i}: duplicate id {row['id']}"
        seen_ids.add(row["id"])
        assert row["id"] == f"Marriott--{len(seen_ids)-1}", f"row {i}: id {row['id']} out of order"


def test_grading_keys_are_all_or_nothing():
    """verifier_path/judge_rubric are appended to every row or to none."""
    lines = [l for l in TASKS.read_text().splitlines() if l.strip()]
    rows = [json.loads(l) for l in lines]
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) in (0, len(rows)), \
        f"grading keys appended to only {len(with_grading)} of {len(rows)} rows"
    for row in with_grading:
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["verifier_path"] == f"sites/marriott/verify/verify_{index}.py", row["verifier_path"]
        assert row["judge_rubric"].strip(), f"{row['id']}: empty judge_rubric"


def test_task_web_urls_point_at_the_declared_port():
    for line in TASKS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert row["web"] == "http://localhost:40104/", row["web"]
        assert row["upstream_url"] == "https://www.marriott.com/", row["upstream_url"]


def test_no_answer_key_anywhere_in_rows():
    raw = TASKS.read_text()
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        lowered = {k.lower() for k in row}
        assert not lowered & {"answer", "answers", "expected", "ground_truth", "solution"}
