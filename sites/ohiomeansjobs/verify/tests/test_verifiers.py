"""Synthetic verifier regression fixtures, derived from reviewed visible-UI outcomes.

These tests use tiny placeholder screenshots and explicit SQLite deltas; they
are contract controls, not browser completion evidence. Real recordings remain
in the review dashboard. No model calls are made.
"""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_run, copy_db, mutate_db, noop_run, run_verifier, _acquire_seed
FIXTURES = json.loads(Path(__file__).with_name('contract_fixtures.json').read_text())
STATEFUL = {i for i, f in enumerate(FIXTURES) if f['delta']}
READ_ONLY = sorted(set(range(len(FIXTURES))) - STATEFUL)
CREATED = '2026-09-24 12:00:00.000000'
HONEST_ANSWERS = {i: f['answer'] for i, f in enumerate(FIXTURES)}
def _seed():
    return _acquire_seed()

def honest_run(tmp, index, name=None):
    spec = FIXTURES[index]
    b = build_run(tmp, name or f'honest_{index:02d}', spec['id'])
    for step in spec['steps']:
        b.step(step['url'], step['action'], step['params'], url_after=step.get('url_after'))
    b.done(spec['answer'], final_path='/')
    seed = _seed()
    after = mutate_db(seed, b.root / 'after.db', spec['delta'])
    return b.root, seed, after

HONEST = {i: (lambda tmp, i=i: honest_run(tmp, i)) for i in range(len(FIXTURES))}

@pytest.mark.parametrize("index", range(18))
def test_honest_pass(tmp_path, index):
    run_dir, initial, after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    assert (run_dir / "after.db").is_file()
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)[:2000]


@pytest.mark.parametrize("index", range(18))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", range(18))
def test_wrong_answer_fails(tmp_path, index):
    run_dir, initial, after = honest_run(tmp_path, index, name=f"wrong_{index:02d}")
    # rewrite the final answer with wrong facts
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = "Wrong: the answer is 99, the employer is Acme Corp, " \
                           "the reference code is XX-0000, posted 1999-01-01, no bonus."
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", range(18))
def test_shortcut_fails(tmp_path, index):
    """Correct answer, homepage-only navigation = memory-recall shortcut = FAIL."""
    root = tmp_path / f"shortcut_{index:02d}"
    seed = _seed()
    b = build_run(tmp_path, f"shortcut_{index:02d}", f"OhioMeansJobs--{index}")
    b.step("/", "goto", {})
    b.done(HONEST_ANSWERS[index])
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    verdict = run_verifier(index, root)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_mutation_fails(tmp_path, index):
    """Read-only tasks must FAIL when the after-DB was mutated."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    mutate_db(initial, run_dir / "after.db", [
        ("INSERT INTO contact_messages (name, email, subject, message, created_at) "
         "VALUES ('x', 'x@test.com', 'x', 'x', '2026-09-24 12:00:00')", ()),
    ])
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, index):
    """Stateful tasks must FAIL when the agent reports success but the DB is clean."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    copy_db(initial, run_dir / "after.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp_path, index):
    """Stateful tasks must FAIL on an unrelated DB mutation (wrong delta)."""
    run_dir, initial, _after = honest_run(tmp_path, index)
    copy_db(initial, run_dir / "initial.db")
    mutate_db(initial, run_dir / "after.db", [
        ("INSERT INTO contact_messages (name, email, subject, message, created_at) "
         "VALUES ('x', 'x@test.com', 'x', 'x', '2026-09-24 12:00:00')", ()),
    ])
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)[:800]


# ---------------------------------------------------------------- tamper tests
def test_task_id_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "OhioMeansJobs--17"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_offsite_url_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://evil.example.com/jobs/search"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_missing_screenshot_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    (run_dir / "screenshots" / "step_001.png").unlink()
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_not_done_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    traj["final_answer"] = ""
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, run_dir / "initial.db")
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False


def test_tampered_seed_fails(tmp_path):
    """A tampered initial.db (not the frozen seed) must fail closed."""
    run_dir, initial, after = honest_run(tmp_path, 0)
    mutate_db(initial, run_dir / "initial.db", [
        ("UPDATE jobs SET title = 'HACKED' WHERE jobid = '6931551303'", ()),
    ])
    verdict = run_verifier(0, run_dir)
    assert verdict["pass"] is False
