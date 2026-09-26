"""Deterministic verifier contract tests for the 21 ryanair tasks.

Covers, per task: the honest trajectory (from the reviewer's live runs, frozen
in fixtures_data.SPECS) MUST PASS; a no-op run (homepage only, empty answer,
clean DB) MUST FAIL; a knowledge-shortcut (correct answer + delta, homepage-only
navigation) MUST FAIL; a wrong answer MUST FAIL; a state-mismatch (success
claim, no DB delta) MUST FAIL for stateful tasks. Read-only tasks (9, 11) MUST
FAIL on a mutated after-DB. Package tampering (task_id mismatch, off-site URL,
missing screenshot, non-done trajectory) MUST fail closed.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, copy_db, exec_sql, honest_run,  # noqa: E402
                       noop_run, run_verifier, shortcut_run, state_mismatch_run,
                       task_ques, wrong_answer_run, acquire_seed)

STATEFUL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20}
READ_ONLY = {9, 11}
ALL = sorted(STATEFUL | READ_ONLY)

# wrong answers per task: plausible but contradicts frozen ground truth
WRONG_ANSWERS = {
    0: "Booking reference 4CVM95. Total charged £99.99.",
    1: "Cheapest departure day Tuesday 13 October (£17.98); cheapest return day "
       "Wednesday 21 October (£14.99). Total paid £19.99.",
    2: "Flexi Plus costs £100.00 more per person; Flexi Plus allows free changes. "
       "Reference NYASBH, total £442.64.",
    3: "Booked MAN-DUB on Plus. The seats added £12.00. Reference PDUXTV.",
    4: "The bags added £64.00. Final total £260.04. Reference 6HS4BL.",
    5: "The extras total was £50.00. Reference 6YKRJL.",
    6: "Used promo code RYANAIR10, discount £9.99, total paid £29.56. Reference H2M97H.",
    7: "The cheapest destination was Vienna at £19.99. Reference LC9KEJ.",
    8: "Alice has 2 saved cards; the Visa ending 4242 is the default. Booking T7W3ND "
        "total £311.07, boarding pass seat 9C. Logged out.",
    9: "Booking M9D2XV: outbound FR 540 at 09:15, return 14:30, 3 passengers, "
        "total £120.00. 20kg bag £10 online vs £60 airport; cheapest XL £9.99. "
        "Check-in has opened.",
    10: "David has 2 saved cards; the Visa is default. Flight FR 1111 at 11:11, "
        "seat 99Z, total £200.00, re-issue fee £5.",
    11: "Bob has 2 saved cards; the Visa ending 4242 is default. The booking is on "
        "the Flexi Plus fare. Check-in opens 60 days before departure. Airport fee "
         "£20, 20kg bag £10 vs £5, gate closes 60 minutes before.",
    12: "Flight FR 1921 departs 10:00 arrives 12:00; it does not operate Monday and "
        "Tuesday. Price paid £60.68, reference RAUP78.",
    13: "The site charged £30.00 for the bag, saving £20.00. Total £45.36, ref YJVGVQ.",
    14: "STANDARD INSURANCE offers the nil-excess £5m cover. Insurance cost £30.40, "
        "total £168.67, reference BT6G8Y.",
    15: "Total £199.99, reference ZFVARW. The Regular fare includes a 20kg check-in bag.",
    16: "The cheapest morning flight was FR 31 departing 08:30. Total paid £28.04, "
        "reference RHUARY.",
    17: "Greek destinations: Athens (ATH) and Rome (FCO). The cheapest was Santorini "
        "at £19.99. Reference 3C6632.",
    18: "Carol has 2 saved cards; the Mastercard is default. Krakow booking K5R7JT is "
        "on the Basic fare, flight FR 1111 at 09:00, seat 1A, total £100.00. "
        "Re-issue fee £5.",
    19: "Reference FCHPCH. Total paid £400.00 with the full breakdown.",
    20: "The Birmingham fare was £19.99 on 20 Oct. Promo RYANAIR10 gave £5.00 off; "
        "total paid £12.22. Reference G2E28Q.",
}


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("task_no", ALL)
def test_honest_pass(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    verdict = run_verifier(task_no, run, expect_pass=True)
    assert verdict["reason"] == "all checks passed"


# ---------------------------------------------------------------- no-op FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_noop_fails(tmp_path, task_no):
    run = noop_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- shortcut FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_shortcut_fails(tmp_path, task_no):
    run = shortcut_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- wrong answer FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_wrong_answer_fails(tmp_path, task_no):
    run = wrong_answer_run(tmp_path, task_no, WRONG_ANSWERS[task_no])
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- state mismatch FAIL
@pytest.mark.parametrize("task_no", sorted(STATEFUL))
def test_state_mismatch_fails(tmp_path, task_no):
    run = state_mismatch_run(tmp_path, task_no)
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- read-only mutation FAIL
@pytest.mark.parametrize("task_no", sorted(READ_ONLY))
def test_readonly_mutation_fails(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    after = run / "after.db"
    con = sqlite3.connect(str(after))
    con.execute("UPDATE bookings SET checked_in = 1 WHERE booking_ref = 'M9D2XV'")
    con.commit()
    con.close()
    run_verifier(task_no, run, expect_pass=False)


# ---------------------------------------------------------------- tamper: task_id
def test_tampered_task_id_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    traj_path = run / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["task_id"] = "Ryanair--19"
    traj_path.write_text(json.dumps(traj))
    run_verifier(0, run, expect_pass=False)


# ---------------------------------------------------------------- tamper: off-site URL
def test_tampered_offsite_url_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    traj_path = run / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["steps"][0]["url"] = "http://evil.example.com/gb/en"
    traj_path.write_text(json.dumps(traj))
    run_verifier(0, run, expect_pass=False)


# ---------------------------------------------------------------- tamper: missing screenshot
def test_tampered_missing_screenshot_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    (run / "screenshots" / "step_001.png").unlink()
    run_verifier(0, run, expect_pass=False)


# ---------------------------------------------------------------- tamper: not done
def test_tampered_not_done_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    traj_path = run / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    traj_path.write_text(json.dumps(traj))
    run_verifier(0, run, expect_pass=False)


# ---------------------------------------------------------------- tamper: wrong seed
def test_tampered_initial_db_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    bad_seed = tmp_path / "bad_initial.db"
    shutil.copy(acquire_seed(), bad_seed)
    con = sqlite3.connect(str(bad_seed))
    con.execute("UPDATE airports SET name = 'Tampered' WHERE code = 'STN'")
    con.commit()
    con.close()
    import subprocess, sys as _sys
    script = Path(__file__).resolve().parents[1] / "verify_0.py"
    r = subprocess.run([_sys.executable, str(script), "--run_dir", str(run),
                        "--initial_db", str(bad_seed)],
                       capture_output=True, text=True)
    verdict = json.loads(r.stdout)
    assert verdict["pass"] is False and verdict.get("infra_error") is True
