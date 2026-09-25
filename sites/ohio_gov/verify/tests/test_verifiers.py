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

@pytest.mark.parametrize("index", range(21))
def test_honest_pass(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    verdict = run_verifier(index, run_dir)
    assert verdict["pass"], f"honest run must PASS: {verdict}"


@pytest.mark.parametrize("index", range(21))
def test_noop_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"no-op run must FAIL: {verdict}"
    assert verdict["reason"] == "final_answer_nonempty" or not verdict["pass"]


@pytest.mark.parametrize("index", range(21))
def test_wrong_answer_fails(tmp_path, index):
    """Honest navigation + honest DB, but the final answer is wrong/empty."""
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = "I could not find the information."
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"wrong answer must FAIL: {verdict}"


@pytest.mark.parametrize("index", range(21))
def test_shortcut_fails(tmp_path, index):
    """Correct answer but homepage-only navigation: knowledge shortcut = FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    # rebuild the same run with ONLY the homepage step, same final answer
    b = build_run(tmp_path, f"shortcut_{index:02d}", f"Ohio.gov--{index}")
    b.step("/", "goto", {})
    b.done(traj["final_answer"], final_path="/")
    copy_db(seed, b.root / "initial.db")
    copy_db(after, b.root / "after.db")
    verdict = run_verifier(index, b.root)
    assert not verdict["pass"], f"shortcut must FAIL: {verdict}"



@pytest.mark.parametrize("index", READ_ONLY)
def test_readonly_mutation_fails(tmp_path, index):
    """Read-only task: any DB mutation (collateral write) must FAIL."""
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    mutate_db(seed, run_dir / "after.db", [
        ("INSERT INTO contact_messages (user_id, full_name, email, subject, message, "
         "created_at) VALUES (NULL, 'X', 'x@example.com', 's', 'm', ?)", (CREATED,)),
    ])
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"read-only mutation must FAIL: {verdict}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, index):
    """Stateful task: honest answer + navigation but DB unchanged = FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    copy_db(seed, run_dir / "after.db")  # no mutation: state mismatch
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"state mismatch must FAIL: {verdict}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp_path, index):
    """Stateful task: the wrong DB delta (a collateral write) must FAIL."""
    seed = _seed()
    run_dir, _, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    mutate_db(seed, run_dir / "after.db", [
        ("INSERT INTO contact_messages (user_id, full_name, email, subject, message, "
         "created_at) VALUES (NULL, 'X', 'x@example.com', 's', 'm', ?)", (CREATED,)),
    ])
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"], f"wrong delta must FAIL: {verdict}"


@pytest.mark.parametrize("index", range(21))
def test_task_id_tamper_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "Ohio.gov--99"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "trajectory_task_matches"


@pytest.mark.parametrize("index", range(21))
def test_offsite_url_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://example.com/ohio"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "all_urls_match_local_origin"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_missing_screenshot_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "screenshots_decode"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_nondone_trajectory_fails(tmp_path, index):
    run_dir, seed, after = HONEST[index](tmp_path)
    copy_db(seed, run_dir / "initial.db")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "trajectory_completed"


@pytest.mark.parametrize("index", (0, 6, 12))
def test_tampered_seed_fails(tmp_path, index):
    """A mutated initial.db breaks the frozen-seed contract: fail closed."""
    run_dir, seed, after = HONEST[index](tmp_path)
    mutate_db(seed, run_dir / "initial.db", [
        ("UPDATE resources SET summary = 'tampered' WHERE id = 1", ()),
    ])
    # after.db was already materialized by the honest fixture; only the seed
    # snapshot is tampered here.
    verdict = run_verifier(index, run_dir)
    assert not verdict["pass"] and verdict["reason"] == "snapshot_contract_invalid"
