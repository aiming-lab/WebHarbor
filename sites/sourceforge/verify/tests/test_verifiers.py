"""Deterministic verifier contract tests for the 21 sourceforge tasks.

Covers, per task: the honest trajectory (from the reviewer's live runs, frozen
in fixtures_data.SPECS) MUST PASS; a no-op run (homepage only, empty answer,
clean DB) MUST FAIL; a knowledge-shortcut (correct answer + delta, homepage-only
navigation) MUST FAIL; a wrong answer MUST FAIL; a state-mismatch (success
claim, no DB delta) MUST FAIL for stateful tasks. Read-only tasks MUST FAIL on
a mutated after-DB. Package tampering (task_id mismatch, off-site URL, missing
screenshot, non-done trajectory, undecodable screenshot) MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _support import (BASE, RunBuilder, copy_db, exec_sql, honest_run,  # noqa: E402
                       noop_run, run_verifier, shortcut_run, state_mismatch_run,
                       task_ques, wrong_answer_run, acquire_seed)
from fixtures_data import SPECS, WRONG_ANSWERS  # noqa: E402

STATEFUL = {7, 13, 18}
READ_ONLY = set(range(21)) - STATEFUL
ALL = sorted(STATEFUL | READ_ONLY)


# ---------------------------------------------------------------- happy path
@pytest.mark.parametrize("task_no", ALL)
def test_honest_run_passes(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=True)


# ---------------------------------------------------------------- no-op fails
@pytest.mark.parametrize("task_no", ALL)
def test_noop_run_fails(tmp_path, task_no):
    run = noop_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- shortcut fails
@pytest.mark.parametrize("task_no", ALL)
def test_shortcut_run_fails(tmp_path, task_no):
    run = shortcut_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- wrong answers fail
@pytest.mark.parametrize("task_no", ALL)
def test_wrong_answer_fails(tmp_path, task_no):
    run = wrong_answer_run(tmp_path, task_no, WRONG_ANSWERS[task_no])
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- state mismatch fails
@pytest.mark.parametrize("task_no", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, task_no):
    run = state_mismatch_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- read-only mutation fails
@pytest.mark.parametrize("task_no", sorted(READ_ONLY))
def test_readonly_mutation_fails(tmp_path, task_no):
    """A read-only task whose after-DB was mutated anyway must FAIL."""
    run = honest_run(tmp_path, task_no)
    db = sqlite3.connect(run / "after.db")
    db.execute("UPDATE projects SET name = name || ' tampered' WHERE id = 1")
    db.commit()
    db.close()
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- package tampering
@pytest.mark.parametrize("task_no", ALL)
def test_task_id_mismatch_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["task_id"] = "SourceForge--999"
    (run / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(task_no, run, expect_pass=False)


@pytest.mark.parametrize("task_no", ALL)
def test_offsite_url_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["steps"][0]["url_after"] = "https://example.org/"
    (run / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(task_no, run, expect_pass=False)


@pytest.mark.parametrize("task_no", ALL)
def test_missing_screenshot_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    shots = sorted((run / "screenshots").glob("step_*.png"))
    shots[0].unlink()
    run_verifier(task_no, run, expect_pass=False)


@pytest.mark.parametrize("task_no", ALL)
def test_undecodable_screenshot_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    shots = sorted((run / "screenshots").glob("step_*.png"))
    shots[0].write_bytes(b"not a png at all")
    run_verifier(task_no, run, expect_pass=False)


@pytest.mark.parametrize("task_no", ALL)
def test_not_terminated_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = None
    (run / "trajectory.json").write_text(json.dumps(traj))
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- seed contract
def test_seed_digests_match_frozen_contract():
    db_path = acquire_seed()
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    sys.path.insert(0, str(Path(__file__).parents[1]))
    import verify_lib
    assert verify_lib.schema_digest(db) == verify_lib.SCHEMA_SHA256
    assert verify_lib.rows_digest(db) == verify_lib.SEED_ROWS_SHA256
    counts = verify_lib.table_counts(db)
    assert counts == verify_lib.SEED_COUNTS


def test_tasks_jsonl_has_no_answer_key():
    for line in (Path(__file__).parents[2] / "tasks.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert "answer" not in row
        assert "verifier_path" in row and "judge_rubric" in row
        assert set(row) == {"id", "ques", "upstream_url", "web", "web_name",
                            "verifier_path", "judge_rubric"}
