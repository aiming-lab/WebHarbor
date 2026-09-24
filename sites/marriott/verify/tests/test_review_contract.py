"""Independent-review controls: correct target plus collateral harm must fail."""
import json
import sqlite3
import pytest
from test_verifiers import honest_run
from _support import _acquire_seed, run_verifier


@pytest.mark.parametrize('index,sql', [
    (0, "UPDATE reservations SET adults=1 WHERE id=(SELECT max(id) FROM reservations)"),
    (0, "UPDATE reservations SET total_rate=999 WHERE id=1"),
    (5, "UPDATE reservations SET status='canceled' WHERE id=4"),
    (5, "UPDATE reservations SET checkout='2026-11-05' WHERE confirmation_number='ACCEDGHDDR'"),
    (8, "UPDATE users SET points=999999 WHERE id=2"),
    (8, "UPDATE users SET postal_code='00000' WHERE id=2"),
    (9, "UPDATE payment_methods SET last_four='0000' WHERE user_id=1"),
    (9, "UPDATE users SET phone='000' WHERE id=3"),
    (10, "DELETE FROM favorites WHERE user_id=2"),
    (11, "UPDATE users SET points=0 WHERE id=1"),
    (18, "UPDATE reservations SET points_redeemed=1 WHERE id=1"),
])
def test_target_success_does_not_permit_collateral_edits(tmp_path, index, sql):
    run = honest_run(tmp_path, index, _acquire_seed())
    with sqlite3.connect(run / 'after.db') as conn:
        conn.execute(sql)
    assert run_verifier(index, run)['pass'] is False


@pytest.mark.parametrize('index,a,b', [(13, '17,000', '19,000'), (17, '3.7', '3.9'), (20, '$540', '$460')])
def test_swapped_entity_facts_rejected(tmp_path, index, a, b):
    run = honest_run(tmp_path, index, _acquire_seed())
    path = run / 'trajectory.json'
    traj = json.loads(path.read_text())
    traj['final_answer'] = traj['final_answer'].replace(a, 'SWAP').replace(b, a).replace('SWAP', b)
    path.write_text(json.dumps(traj))
    assert run_verifier(index, run)['pass'] is False


def test_natural_profile_confirmation_accepted(tmp_path):
    run = honest_run(tmp_path, 8, _acquire_seed())
    path = run / 'trajectory.json'
    traj = json.loads(path.read_text())
    traj['final_answer'] = 'I saved your updated contact details.'
    path.write_text(json.dumps(traj))
    assert run_verifier(8, run)['pass'] is True


def test_all_letter_confirmation_accepted(tmp_path):
    run = honest_run(tmp_path, 0, _acquire_seed())
    path = run / 'trajectory.json'
    traj = json.loads(path.read_text())
    # The application's random alphabet allows a confirmation with no digits.
    traj['final_answer'] = traj['final_answer'].replace('RT00TEST01', 'ABCDEFGHJK')
    path.write_text(json.dumps(traj))
    with sqlite3.connect(run / 'after.db') as conn:
        conn.execute("UPDATE reservations SET confirmation_number='ABCDEFGHJK' WHERE confirmation_number='RT00TEST01'")
    assert run_verifier(0, run)['pass'] is True
