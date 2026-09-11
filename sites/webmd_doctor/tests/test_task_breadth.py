"""Task-file breadth and verifier wiring for the WebMD Doctor mirror."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
TASKS = SITE / "tasks.jsonl"


def _load_tasks() -> list[dict]:
    rows = [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]
    return rows


def test_twenty_unique_tasks_with_required_fields():
    tasks = _load_tasks()
    assert len(tasks) == 20, f"expected 20 tasks, got {len(tasks)}"
    ids = [task["id"] for task in tasks]
    assert ids == [f"WebMD Doctor--{index}" for index in range(20)], ids
    for task in tasks:
        assert task["web_name"] == "WebMD Doctor"
        assert task["web"] == "http://localhost:40024/"
        assert task["upstream_url"].startswith("https://doctor.webmd.com/"), task["id"]
        assert len(task["ques"]) >= 40, f"task question too thin: {task['id']}"
        assert len(task["judge_rubric"]) >= 80, f"rubric too thin: {task['id']}"
        verifier = SITE.parent.parent / task["verifier_path"]
        assert verifier.is_file(), f"missing verifier {task['verifier_path']}"


def test_every_verifier_exposes_run_checks():
    sys.path.insert(0, str(SITE / "verify"))
    try:
        for index in range(20):
            name = f"verify_{index}"
            path = SITE / "verify" / f"{name}.py"
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert callable(getattr(module, "run_checks", None)), f"{name} lacks run_checks"
    finally:
        sys.path.pop(0)


def test_ground_truth_matches_embedded_expectations():
    sys.path.insert(0, str(SITE / "verify"))
    try:
        import ground_truth

        facts = ground_truth.all_ground_truth(SITE / "instance_seed" / "webmd_doctor.db")
        assert sorted(facts) == list(range(20))
    finally:
        sys.path.pop(0)
