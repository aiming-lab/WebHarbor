#!/usr/bin/env python3
"""test_verifiers.py — pytest suite for the chronicle_jobs grading contract.

Runs the FULL verification matrix (all 30 tasks, 7 legs each):

  honest      real Playwright drives of every task; every verifier MUST PASS
  no_op       homepage-only run, empty answer, clean DB; every verifier MUST FAIL
  shortcut    correct answer but no on-site navigation; MUST FAIL
  wrong       honest navigation but a wrong final answer; MUST FAIL
  tamper_id   run package with a foreign task_id; MUST FAIL
  tamper_url  run package with an off-origin URL; MUST FAIL
  tamper_shot run package with a missing screenshot; MUST FAIL

Prerequisites (skipped with a clear reason when absent):
  * the review container is up and exposes the control plane
    (docker exec $WH_CONTAINER ... /reset/chronicle_jobs works);
  * the mirror answers at $WH_MIRROR_URL (default http://127.0.0.1:46066).

Invocation (agent_demo uv project provides playwright + simpleArgParser;
pytest itself is injected with --with pytest):

    cd agent_demo
    WH_CONTAINER=wh-rev-chronicle_jobs uv run --with pytest python -m pytest \
        ../sites/chronicle_jobs/verify/test_verifiers.py -v

The full matrix takes roughly 30-40 minutes (30 honest browser drives, 180
negative cases, each preceded by a control-plane DB reset). Set
WH_MATRIX_TASKS / WH_MATRIX_LEGS to scope it down, e.g.
WH_MATRIX_TASKS=0,1 WH_MATRIX_LEGS=honest,no_op.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drive_tasks  # noqa: E402
import run_matrix  # noqa: E402

CONTAINER = os.environ.get("WH_CONTAINER", "wh-rev-chronicle_jobs")


def _infra_available() -> tuple[bool, str]:
    if not drive_tasks.site_ready():
        return False, f"mirror not reachable at {drive_tasks.BASE}"
    probe = subprocess.run(
        ["docker", "exec", CONTAINER, "sh", "-c",
         'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" '
         'http://127.0.0.1:8101/health'],
        capture_output=True, text=True, timeout=60)
    if probe.stdout.strip() not in ("200", "503"):
        return False, f"control plane not reachable in container {CONTAINER} ({probe.stdout.strip()!r})"
    return True, ""


@pytest.fixture(scope="session")
def matrix():
    ok, why = _infra_available()
    if not ok:
        pytest.skip(f"chronicle_jobs review infra unavailable: {why}")
    tasks = os.environ.get("WH_MATRIX_TASKS", "all")
    legs = os.environ.get("WH_MATRIX_LEGS", "all")
    idxs = list(range(30)) if tasks == "all" else [int(x) for x in tasks.split(",") if x.strip()]
    leg_list = ["honest"] + list(run_matrix.NEG_LEGS) if legs == "all" else legs.split(",")
    out_root = os.environ.get("WH_MATRIX_OUT", "/tmp/wh-rev-cj/pytest_matrix")
    results, failures = run_matrix.run_legs(idxs, leg_list, out_root)
    summary = {tid: {leg: row[leg]["pass"] for leg in row if leg in (["honest"] + list(run_matrix.NEG_LEGS))}
               for tid, row in results.items()}
    return {"results": results, "failures": failures, "summary": summary, "legs": leg_list}


def _leg(matrix, leg, expect_pass: bool):
    checked = {tid: row[leg]["pass"] for tid, row in matrix["results"].items() if leg in row}
    assert checked, f"leg '{leg}' was not run (legs={matrix['legs']})"
    bad = sorted(tid for tid, p in checked.items() if p != expect_pass)
    detail = {tid: matrix["results"][tid][leg].get("reason", "") for tid in bad}
    if expect_pass:
        assert not bad, f"leg '{leg}': tasks failed to PASS: {bad} reasons={detail}"
    else:
        assert not bad, f"leg '{leg}': FALSE POSITIVES on: {bad} reasons={detail}"


def test_honest_runs_all_pass(matrix):
    _leg(matrix, "honest", expect_pass=True)


def test_noop_runs_all_fail(matrix):
    _leg(matrix, "no_op", expect_pass=False)


def test_shortcut_answers_fail(matrix):
    _leg(matrix, "shortcut", expect_pass=False)


def test_wrong_answers_fail(matrix):
    _leg(matrix, "wrong", expect_pass=False)


def test_tampered_task_id_fails(matrix):
    _leg(matrix, "tamper_id", expect_pass=False)


def test_tampered_foreign_url_fails(matrix):
    _leg(matrix, "tamper_url", expect_pass=False)


def test_tampered_missing_screenshot_fails(matrix):
    _leg(matrix, "tamper_shot", expect_pass=False)


def test_matrix_summary(matrix):
    """Human-readable summary written next to the matrix output for the report."""
    out = Path(os.environ.get("WH_MATRIX_OUT", "/tmp/wh-rev-cj/pytest_matrix")) / "matrix_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix["summary"], indent=1, sort_keys=True))
    print(f"\nsummary -> {out}")
    assert True
