"""test_verifiers.py — adversarial contract tests for the parkers verifiers.

Every test runs a real verifier as a subprocess against a fixture derived from
the honest fixtures (real Playwright trajectories recorded against the live
review container):

  - honest fixtures (real trajectories + real answers)        must PASS
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

READ_ONLY = [t for t in range(20) if t not in (8, 9, 11)]
STATEFUL = [8, 9, 11]


def test_honest_fixtures_pass():
    for t in range(20):
        code, verdict = S.run_verifier(t, S.FIXTURES / f'honest_{t}')
        assert code == 0 and verdict['pass'], \
            f'T{t} honest fixture must pass: {verdict["reason"]}'


def test_noop_all_fail():
    fails = 0
    for t in range(20):
        d = S.noop_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} no-op must fail (got pass)'
        fails += 1
    assert fails == 20


def test_shortcut_all_fail():
    for t in range(20):
        d = S.shortcut_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} shortcut must fail (got pass)'


def test_wrong_answers_fail():
    for t in range(20):
        d = S.wrong_answer_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} wrong answer must fail (got pass)'


def test_mutated_readonly_db_fails():
    for t in READ_ONLY:
        d = S.mutated_db_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} mutated after-DB must fail (got pass)'


def test_state_mismatch_fails():
    for t in STATEFUL:
        d = S.state_mismatch_fixture(t)
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} state mismatch must fail (got pass)'


def test_tamper_wrong_task_id_fails():
    for t in (0, 8, 15):
        d = S.tamper_fixture(t, 'task_id')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_offsite_url_fails():
    for t in (0, 12):
        d = S.tamper_fixture(t, 'offsite_url')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_not_terminated_fails():
    for t in (3, 19):
        d = S.tamper_fixture(t, 'not_terminated')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_bad_png_fails():
    for t in (5, 10):
        d = S.tamper_fixture(t, 'bad_png')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_tamper_empty_answer_fails():
    for t in (1, 14):
        d = S.tamper_fixture(t, 'empty_answer')
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass']


def test_seed_contract_gates_mutated_seed():
    """A trajectory run against a non-seed initial DB must fail (seed contract)."""
    import shutil
    import sqlite3
    for t in (0, 6):
        d = S.clone(S.FIXTURES / f'honest_{t}', S.FIXTURES / f'seedmut_{t}')
        con = sqlite3.connect(d / 'initial.db')
        con.execute("UPDATE listings SET price = price + 3 WHERE id = 2")
        con.commit()
        con.close()
        code, verdict = S.run_verifier(t, d)
        assert code != 0 and not verdict['pass'], \
            f'T{t} mutated seed must fail (got pass)'
