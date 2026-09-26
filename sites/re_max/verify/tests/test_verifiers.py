"""test_verifiers.py — adversarial contract tests for the re_max verifiers.

Every test runs a real verifier as a subprocess against a fixture derived from
the honest fixtures (real Playwright trajectories recorded against the live
review container):

  - honest fixtures (real trajectories + real answers)        must PASS
    (task 7 is the documented exception: its honest walk dead-ends because
    the offices finder is not reachable from any on-site link; the verifier
    correctly FAILs that run — see test_t7_honest_deadend_fails)
  - no-op (homepage only, empty answer)                       must FAIL
  - shortcut (correct answer, no navigation)                   must FAIL
  - wrong answer (honest navigation, wrong numbers)           must FAIL
  - mutated after-DB (read-only tasks)                         must FAIL
  - state mismatch (stateful tasks, wrong DB delta)            must FAIL
  - tamper (wrong task_id / off-site URL / not terminated /
    corrupt PNG / empty answer)                               must FAIL

Run:  python3 -m pytest tests/test_verifiers.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _support as S  # noqa: E402


def test_honest_fixtures_pass():
    # r2: all 20 tasks are feasible after the A-2 office-finder fix; every
    # honest fixture (real browser trajectory + real answer) must pass
    for t in range(20):
        code, verdict = S.run_verifier(t, S.honest_dir(t))
        assert code == 0 and verdict['pass'], \
            f'T{t} honest fixture must pass: {verdict["reason"]}'


def test_t7_deadend_trajectory_fails():
    """r2 regression gate: a trajectory that dead-ends like the r1 honest
    walk (search + browse only, no office detail page) must still FAIL —
    no false positive for an uncompleted task."""
    import json as _json
    import shutil as _shutil
    d = S.clone(S.honest_dir(7), S.FIXTURES / 'deadend_7')
    p = d / 'trajectory.json'
    traj = _json.loads(p.read_text())
    # strip every office-detail navigation, keep search + browse only
    traj['steps'] = [s for s in traj['steps']
                     if '/office/' not in str(s.get('url', ''))]
    p.write_text(_json.dumps(traj, indent=1))
    code, verdict = S.run_verifier(7, d)
    assert code != 0 and not verdict['pass'], \
        f'T7 dead-end must fail (got pass: {verdict["reason"]})'
    fails = [e['check'] for e in verdict.get('evidence', []) if not e['ok']]
    assert any(f.startswith('nav_office_') for f in fails), \
        f'expected an office navigation gate to fail, saw: {fails}'


def test_noop_all_fail():
    for t in range(20):
        d = S.noop_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} no-op must fail (got pass)'


def test_shortcut_all_fail():
    for t in range(20):
        d = S.shortcut_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} shortcut must fail (got pass: {verdict["reason"]})'


def test_wrong_answers_fail():
    for t in range(20):
        d = S.wrong_answer_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} wrong answer must fail (got pass: {verdict["reason"]})'


def test_mutated_readonly_db_fails():
    for t in S.READ_ONLY:
        d = S.mutated_db_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} mutated after-DB must fail (got pass: {verdict["reason"]})'


def test_state_mismatch_fails():
    for t in S.STATEFUL:
        d = S.state_mismatch_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} state mismatch must fail (got pass: {verdict["reason"]})'


def test_tamper_wrong_task_id_fails():
    for t in (0, 4, 15):
        d = S.tamper_fixture(t, 'task_id')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_offsite_url_fails():
    for t in (0, 12):
        d = S.tamper_fixture(t, 'offsite_url')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_not_terminated_fails():
    for t in (2, 11):
        d = S.tamper_fixture(t, 'not_terminated')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_empty_answer_fails():
    for t in (5, 16):
        d = S.tamper_fixture(t, 'empty_answer')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_corrupt_png_fails():
    for t in (1, 19):
        d = S.tamper_fixture(t, 'corrupt_png')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_seed_freeze_detects_seed_tamper():
    """A mutated SEED (initial.db) must fail the frozen-seed contract."""
    import json
    import shutil
    import sqlite3
    d = S.clone(S.honest_dir(0), S.FIXTURES / 'seedtamper_0')
    con = sqlite3.connect(d / 'initial.db')
    con.execute("UPDATE agents SET years = years + 1 WHERE id = 1")
    con.commit()
    con.close()
    code, verdict = S.run_verifier(0, d)
    assert code != 0 and not verdict['pass'], \
        f'seed tamper must fail (got pass: {verdict["reason"]})'
