"""Reviewer-authored test suite for the qatar_airways grading contract.

Covers, per the review-env skill's Step 7 soundness bar:
  * honest runs PASS for all 20 tasks (synthetic trajectories + the exact DB
    deltas the app writes; ground truths independently re-derived by the
    reviewer from live page reads)
  * no-op runs FAIL for all 20 tasks (homepage only, empty answer, clean DB)
  * wrong-answer runs FAIL (sampled: T0/T3/T9/T16)
  * shortcut runs FAIL (correct answer, no on-site navigation: T0/T3/T10)
  * state-mismatch runs FAIL (answer claims success, DB unchanged: T5/T7/T17)
  * wrong-delta / collateral-write runs FAIL (T0 wrong total, T2 collateral)
  * package tampering FAILs closed (wrong task_id, cross-origin URL, broken
    screenshot, missing trajectory)
  * seed-identity gate FAILs a run whose initial DB is not the frozen seed
  * tasks.jsonl contract: 7 keys, 5 definition keys byte-identical to the
    contributor rows, verifier_path exists, rubric rules-only English, no
    answer key anywhere

    python3 -m pytest sites/qatar_airways/verify/tests -q
"""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from _support import (BASE, CONTAINER, PNG, VERIFY_DIR, REPO_ROOT, _acquire_seed,
                      build_run, copy_db, db_one, honest_run, mutate_db,
                      noop_run, run_verifier)

TASKS_JSONL = REPO_ROOT / "sites" / "qatar_airways" / "tasks.jsonl"


# ---------------------------------------------------------------- honest runs PASS
@pytest.mark.parametrize("index", range(20))
def test_honest_run_passes(tmp_path, index):
    run_dir, _answer = honest_run(tmp_path, index)
    result = run_verifier(index, run_dir)
    assert result["pass"] is True, json.dumps(result, indent=1)


# ---------------------------------------------------------------- no-op runs FAIL
@pytest.mark.parametrize("index", range(20))
def test_noop_run_fails(tmp_path, index):
    run_dir = noop_run(tmp_path, index)
    result = run_verifier(index, run_dir)
    assert result["pass"] is False, json.dumps(result, indent=1)


# ---------------------------------------------------------------- wrong answers FAIL
def test_wrong_total_fails_t0(tmp_path):
    run_dir, _ = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("1,490", "1,850")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] in ("answer_total", "pnr_in_answer", "added_booking_row") or \
        result["reason"] == "answer_total"


def test_wrong_time_fails_t3(tmp_path):
    run_dir, _ = honest_run(tmp_path, 3)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("15:05", "15:50")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(3, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "answer_sched_dep"


def test_wrong_avios_fails_t9(tmp_path):
    run_dir, _ = honest_run(tmp_path, 9)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("3,766", "2,500")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(9, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "answer_avios"


def test_wrong_support_number_fails_t16(tmp_path):
    run_dir, _ = honest_run(tmp_path, 16)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("833 607 2675", "800 123 4567")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(16, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "answer_support_number"


# ---------------------------------------------------------------- shortcuts FAIL
def _shortcut_run(tmp_path, index, answer):
    """Correct final answer, but the trajectory never left the homepage."""
    root = tmp_path / f"shortcut_{index}"
    root.mkdir(parents=True)
    seed = _acquire_seed()
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = build_run(tmp_path, f"shortcut_{index}_b", f"Qatar Airways--{index}")
    b.step("/", "goto", {})
    b.done(answer)
    return b.root


def test_shortcut_fails_t0(tmp_path):
    run_dir = _shortcut_run(tmp_path, 0,
                            "Booked the cheapest Economy Lite flight QR105 for John "
                            "and Mary Smith. Booking reference AA12CD. Total charged "
                            "USD 1,490.")
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_search"


def test_shortcut_fails_t3(tmp_path):
    run_dir = _shortcut_run(tmp_path, 3,
                            "QR004 on 24 September 2026 is En route. Scheduled "
                            "departure 15:05, estimated arrival 23:47, operated by "
                            "the Airbus A380-800, which offers First, Business and "
                            "Economy cabins.")
    result = run_verifier(3, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_status_by_number"


def test_shortcut_fails_t10(tmp_path):
    run_dir = _shortcut_run(tmp_path, 10,
                            "320 Qpoints within 12 months qualifies for Gold, which "
                            "comes with oneworld Sapphire status. The next tier up, "
                            "Platinum, needs 600 Qpoints within 12 months, so 280 "
                            "more. Gold gives a 20kg extra baggage allowance, or one "
                            "piece depending on the route.")
    result = run_verifier(10, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_tiers"


# ---------------------------------------------------------------- state mismatch FAIL
def test_state_mismatch_fails_t5(tmp_path):
    """Answer claims cancellation, DB untouched."""
    run_dir, answer = honest_run(tmp_path, 5)
    seed = _acquire_seed()
    copy_db(seed, run_dir / "after.db")  # undo the mutation: DB unchanged
    result = run_verifier(5, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "booking_cancelled"


def test_state_mismatch_fails_t7(tmp_path):
    run_dir, _ = honest_run(tmp_path, 7)
    seed = _acquire_seed()
    copy_db(seed, run_dir / "after.db")
    result = run_verifier(7, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "checked_in"


def test_state_mismatch_fails_t17(tmp_path):
    run_dir, _ = honest_run(tmp_path, 17)
    seed = _acquire_seed()
    copy_db(seed, run_dir / "after.db")
    result = run_verifier(17, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "member_created"


# ------------------------------------------ r2 redesign adversarial negatives

def test_shortcut_fails_t16_all_new_facts(tmp_path):
    """Correct r2 five-fact answer, zero navigation: must fail closed."""
    run_dir = _shortcut_run(tmp_path, 16,
                            "The dedicated 24-hour support number for hard-of-hearing "
                            "passengers is +1 833 607 2675. The medical assistance form "
                            "must be submitted between 7 days and 48 hours before "
                            "departure. Firearms for Oman must be declared more than "
                            "19 days prior. Proof-of-travel certificates can be "
                            "requested for up to 12 months from the date of travel. "
                            "Infants can carry one baby stroller or collapsible "
                            "carrycot at no additional cost.")
    result = run_verifier(16, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_help"


def test_missing_route_status_fails_t3(tmp_path):
    """Honest T3 run minus the London-Doha route-status query."""
    run_dir, _ = honest_run(tmp_path, 3)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"] = [s for s in traj["steps"]
                     if "mode=route" not in str(s.get("url", ""))]
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(3, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_status_by_route"


def test_missing_baggage_checker_fails_t6(tmp_path):
    """Honest T6 run minus the First Elite allowance lookup."""
    run_dir, _ = honest_run(tmp_path, 6)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"] = [s for s in traj["steps"]
                     if "/en/baggage.html" not in str(s.get("url", ""))]
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(6, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "visited_baggage_checker"


def test_wrong_certificate_window_fails_t16(tmp_path):
    run_dir, _ = honest_run(tmp_path, 16)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["final_answer"] = traj["final_answer"].replace("12 months", "6 months")
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(16, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "answer_certificate_window"


def test_wrong_second_passenger_fails_t19(tmp_path):
    """Booking made for Ravi + the wrong companion: named_passengers must fail."""
    run_dir, _ = honest_run(tmp_path, 19)
    con = sqlite3.connect(str(run_dir / "after.db"))
    try:
        con.execute("UPDATE passengers SET first_name='Priya' WHERE first_name='Anaya'")
        con.commit()
    finally:
        con.close()
    result = run_verifier(19, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "named_passengers"


# ---------------------------------------------------------------- wrong deltas FAIL
def test_wrong_total_in_db_fails_t0(tmp_path):
    """A booking row exists but with the wrong total: FAIL."""
    run_dir, _ = honest_run(tmp_path, 0)
    con = sqlite3.connect(run_dir / "after.db")
    con.execute("UPDATE bookings SET total_paid=1600 WHERE pnr='AA12CD'")
    con.commit()
    con.close()
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "added_booking_row"


def test_collateral_write_fails_t2(tmp_path):
    """The right booking plus an unrelated subscription row: FAIL."""
    run_dir, _ = honest_run(tmp_path, 2)
    con = sqlite3.connect(run_dir / "after.db")
    con.execute("INSERT INTO subscriptions (email, departure_city, created_at)"
                " VALUES ('spam@example.com', 'DOH', '2026-09-24')")
    con.commit()
    con.close()
    result = run_verifier(2, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "no_collateral_writes"


def test_dearer_flight_fails_t0(tmp_path):
    """A Lite booking on a dearer flight (total inflated to match): FAIL."""
    run_dir, _ = honest_run(tmp_path, 0)
    con = sqlite3.connect(run_dir / "after.db")
    con.execute("UPDATE booking_legs SET flight_number=103 WHERE "
                "booking_id=(SELECT id FROM bookings WHERE pnr='AA12CD')")
    con.commit()
    con.close()
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "cheapest_flight_selected"


def test_readonly_violation_fails_t3(tmp_path):
    """A read-only task whose DB was touched: FAIL."""
    run_dir, _ = honest_run(tmp_path, 3)
    con = sqlite3.connect(run_dir / "after.db")
    con.execute("UPDATE users SET avios=avios+1 WHERE email='alice.j@test.com'")
    con.commit()
    con.close()
    result = run_verifier(3, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "read_only_run"


# ---------------------------------------------------------------- package tampering
def test_wrong_task_id_fails_closed(tmp_path):
    run_dir, _ = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "Qatar Airways--19"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "task_id"


def test_cross_origin_url_fails_closed(tmp_path):
    run_dir, _ = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][1]["url"] = "http://127.0.0.1:47090/en/search-results.html?from=DOH"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "same_origin"


def test_broken_screenshot_fails_closed(tmp_path):
    run_dir, _ = honest_run(tmp_path, 0)
    (run_dir / "screenshots" / "step_001.png").write_bytes(b"not a png")
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "screenshots_decode"


def test_missing_trajectory_fails_closed(tmp_path, capfd=None):
    root = tmp_path / "notraj"
    root.mkdir()
    copy_db(_acquire_seed(), root / "initial.db")
    copy_db(_acquire_seed(), root / "after.db")
    result = run_verifier(0, root)
    assert result["pass"] is False
    assert result.get("infra_error") is True
    assert result["reason"] == "trajectory_unavailable"


def test_unterminated_run_fails_closed(tmp_path):
    run_dir, _ = honest_run(tmp_path, 0)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "terminated"


# ---------------------------------------------------------------- seed identity gate
def test_premutated_initial_db_fails_closed(tmp_path):
    """A run whose initial DB is not the frozen seed fails the seed gate."""
    run_dir, _ = honest_run(tmp_path, 0)
    con = sqlite3.connect(run_dir / "initial.db")
    con.execute("UPDATE users SET avios=avios+100 WHERE email='alice.j@test.com'")
    con.commit()
    con.close()
    result = run_verifier(0, run_dir)
    assert result["pass"] is False
    assert result["reason"] == "seed_identity"


# ---------------------------------------------------------------- tasks.jsonl contract
def _rows():
    return [json.loads(l) for l in TASKS_JSONL.read_text().splitlines() if l.strip()]


def test_tasks_rows_have_exactly_seven_keys():
    required = {"web_name", "id", "ques", "web", "upstream_url"}
    grading = {"verifier_path", "judge_rubric"}
    for i, row in enumerate(_rows()):
        assert set(row) == required | grading, f"row {i}: keys {sorted(row)}"
        assert row["id"] == f"Qatar Airways--{i}", f"row {i}: id {row['id']}"


def test_tasks_definition_keys_byte_identical_to_contributor():
    """The five definition keys are byte-identical to the contributor's rows
    (checked against the frozen 5-key prefix recorded at review time)."""
    import hashlib
    rows = _rows()
    prefix = hashlib.sha256(
        "\n".join(json.dumps({k: r[k] for k in
                              ("web_name", "id", "ques", "web", "upstream_url")},
                             ensure_ascii=False, separators=(",", ":"))
                  for r in rows).encode()).hexdigest()
    # frozen from the contributor branch 648fe506's tasks.jsonl (r2 fix commit)
    # at review time; re-frozen at integration after the mandated slot
    # re-normalization of the `web` origin (40089 -> 40130 per the parallel-
    # queue registration, same re-port every integrate branch carries).
    # Every other definition byte is unchanged from the contributor's rows.
    assert prefix == "e79944afe5c9c96f6520d11ed4db931ae368b49a081da14fc581727afcca9f44", prefix


def test_verifier_paths_exist_and_match_ids():
    for i, row in enumerate(_rows()):
        assert row["verifier_path"] == f"sites/qatar_airways/verify/verify_{i}.py"
        assert (REPO_ROOT / row["verifier_path"]).is_file(), row["verifier_path"]


def test_rubrics_are_rules_only_english():
    banned = ("the answer is", "the correct answer", "ground truth is",
              "答案是", "正确答案")
    for row in _rows():
        rubric = row["judge_rubric"]
        assert rubric.startswith("FACT CHECKPOINTS"), row["id"]
        low = rubric.lower()
        for b in banned:
            assert b not in low, f"{row['id']}: rubric leaks answers ({b!r})"


def test_no_answer_key_in_rows():
    for row in _rows():
        lowered = {k.lower() for k in row}
        assert not lowered & {"answer", "answers", "expected", "ground_truth",
                              "solution"}, row["id"]


def test_task_wording_within_100_words():
    for row in _rows():
        words = len(row["ques"].split())
        assert words <= 100, f"{row['id']}: {words} words"
        assert not row["ques"].lower().startswith(
            ("click ", "tap ", "press ", "go to ", "navigate to ")), row["id"]
