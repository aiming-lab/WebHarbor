"""Tasks contract for the qatar_airways mirror.

Rows carry the five task-definition keys (web_name, id, ques, web,
upstream_url) plus the grading keys verifier_path + judge_rubric appended
inline by the contribution contract. Answer material must never live in
this agent-facing file; the deterministic ground truth is hardcoded in
each sites/qatar_airways/verify/verify_N.py instead.
"""
import json
import pathlib

TASKS = pathlib.Path(__file__).resolve().parent.parent / "tasks.jsonl"
REQUIRED_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
GRADING_KEYS = {"verifier_path", "judge_rubric"}
ALLOWED_KEYS = REQUIRED_KEYS | GRADING_KEYS
FORBIDDEN_KEYS = {"answer", "answers", "expected", "ground_truth", "solution"}
REPO_ROOT = TASKS.parent.parent.parent


def _rows():
    return [json.loads(l) for l in TASKS.read_text().splitlines() if l.strip()]


def test_tasks_file_exists_and_nonempty():
    assert TASKS.exists(), "tasks.jsonl missing"
    rows = _rows()
    assert 15 <= len(rows) <= 25, f"expected 15-25 tasks, found {len(rows)}"


def test_task_rows_have_exactly_the_allowed_keys():
    seen_ids = set()
    for i, row in enumerate(_rows()):
        keys = set(row.keys())
        assert REQUIRED_KEYS <= keys, f"row {i}: missing keys {REQUIRED_KEYS - keys}"
        assert keys <= ALLOWED_KEYS, f"row {i}: unexpected keys {keys - ALLOWED_KEYS}"
        for key, value in row.items():
            assert isinstance(value, str) and value.strip(), f"row {i}: empty {key}"
        assert row["web_name"] == "Qatar Airways", f"row {i}: web_name {row['web_name']!r}"
        assert row["id"] not in seen_ids, f"row {i}: duplicate id {row['id']}"
        seen_ids.add(row["id"])
        assert row["id"] == f"Qatar Airways--{len(seen_ids)-1}", f"row {i}: id {row['id']} out of order"


def test_task_wording_is_goal_style_and_bounded():
    for row in _rows():
        words = len(row["ques"].split())
        assert words <= 100, f"{row['id']}: {words} words exceeds the 100-word cap"
        # mechanical step-by-step instructions are rejected by the design contract
        lowered = row["ques"].lower()
        assert not any(lowered.startswith(p) for p in
                       ("click ", "tap ", "press ", "go to ", "navigate to ")), \
            f"{row['id']}: instruction-style opening"


def test_grading_keys_present_on_every_row():
    rows = _rows()
    with_grading = [r for r in rows if GRADING_KEYS <= set(r)]
    assert len(with_grading) == len(rows), \
        f"grading keys on {len(with_grading)} of {len(rows)} rows (must be all)"
    for row in rows:
        index = int(row["id"].rsplit("--", 1)[1])
        assert row["verifier_path"] == f"sites/qatar_airways/verify/verify_{index}.py", \
            row["verifier_path"]
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS"), row["id"]
        assert (REPO_ROOT / row["verifier_path"]).is_file(), \
            f"{row['id']}: verifier_path missing on disk: {row['verifier_path']}"


def test_task_web_urls_point_at_the_declared_port():
    for row in _rows():
        assert row["web"] == "http://localhost:40130/", row["web"]
        assert row["upstream_url"] == "https://www.qatarairways.com/", row["upstream_url"]


def test_no_answer_key_anywhere_in_rows():
    for row in _rows():
        lowered = {k.lower() for k in row}
        assert not lowered & FORBIDDEN_KEYS, f"{row['id']}: forbidden key present"
    # and no answer leakage inside the rubric: rubrics state rules, not answers
    for row in _rows():
        lowered = row["judge_rubric"].lower()
        for banned in ("the answer is", "the correct answer", "ground truth is"):
            assert banned not in lowered, f"{row['id']}: rubric leaks answers"
