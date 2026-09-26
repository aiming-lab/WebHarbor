"""Shared fixture builders for the parkers verifier tests.

Adversarial fixtures are derived from the honest fixtures (real browser
trajectories) by mutating exactly one thing: the final answer, the navigation,
the after-DB, or the trajectory identity. No docker required — every fixture
carries its own initial.db / after.db copies.
"""
import json
import shutil
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY_DIR = HERE.parent
FIXTURES = Path('/data/zhaoyang-user-projects/websyn/wh-parkers-r2-rereview-evidence/'
                'verify_results/fixtures')
SEED = Path('/data/zhaoyang-user-projects/websyn/wh-parkers-r2-wt/sites/parkers/'
            'instance_seed/parkers.db')
START = 'http://localhost:40125/'


def run_verifier(task, run_dir):
    """Run verify_<task>.py against run_dir; returns (exit_code, verdict_dict)."""
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, str(VERIFY_DIR / f'verify_{task}.py'),
         '--run_dir', str(run_dir)],
        capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        verdict = {'pass': False, 'reason': 'unparseable output: ' + proc.stdout[:200]}
    return proc.returncode, verdict


def clone(src, dst):
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def set_answer(run_dir, answer):
    p = Path(run_dir) / 'trajectory.json'
    traj = json.loads(p.read_text())
    traj['final_answer'] = answer
    p.write_text(json.dumps(traj, indent=1))


def set_steps(run_dir, steps):
    p = Path(run_dir) / 'trajectory.json'
    traj = json.loads(p.read_text())
    traj['steps'] = steps
    traj['final_url'] = steps[-1]['url'] if steps else START
    p.write_text(json.dumps(traj, indent=1))


def mutate_db(run_dir, sql, args=()):
    p = Path(run_dir) / 'after.db'
    con = sqlite3.connect(p)
    try:
        con.execute(sql, args)
        con.commit()
    finally:
        con.close()


def noop_fixture(task, base=None):
    """Homepage-only trajectory with an empty answer."""
    src = base or (FIXTURES / f'honest_{task}')
    dst = clone(src, FIXTURES / f'noop_{task}')
    set_steps(dst, [{'action': 'navigate', 'url': START, 'params': {}}])
    set_answer(dst, '')
    return dst


def shortcut_fixture(task):
    """Correct answer, but homepage-only navigation (memory-recall shortcut)."""
    src = FIXTURES / f'honest_{task}'
    dst = clone(src, FIXTURES / f'shortcut_{task}')
    honest_answer = json.loads((dst / 'trajectory.json').read_text())['final_answer']
    set_steps(dst, [{'action': 'navigate', 'url': START, 'params': {}}])
    set_answer(dst, honest_answer)
    return dst


def wrong_answer_fixture(task):
    """Honest navigation, but every amount/number in the answer is wrong."""
    src = FIXTURES / f'honest_{task}'
    dst = clone(src, FIXTURES / f'wrong_{task}')
    wrong = {
        0: "The Fiesta values at £9,999 - £11,111 privately, £12,222 - £13,333 from "
           "a dealer, part-exchange £8,888 - £9,999.",
        1: "The valuation refers to the Corsa 1.0 Life 5dr: £4,444 - £5,555 "
           "privately and £6,666 - £7,777 from a dealer. The cheapest Corsa is "
           "£8,888, which sits above the dealer range.",
        2: "The 318d M Sport values at £1,111 - £2,222 privately, £3,333 - £4,444 "
           "from a dealer, part-ex £5,555 - £6,666. The dealer route earns more.",
        3: "The Tucson has the bigger boot at 911 litres against the Kodiaq's 621, "
           "a difference of 291 litres.",
        4: "The most economical diesel Civic is the EX 120PS at 12.3 mpg, £99,999 "
           "new; another diesel does 13.4 mpg.",
        5: "The Polo's lowest group is 22 and the Fiesta's is 33, so the Fiesta is "
           "cheaper to insure.",
        6: "Parkers rate the 3 Series 2 out of 5. They like the poor ride, dislike "
           "everything, reliability 1. The most expensive is £12,345 with 999 miles.",
        7: "The Cooper scores 4 for practicality against the A3's 2.2, so the Cooper "
           "leads by 1.8; luggage difference is 42 litres.",
        8: "The cheapest match is a Ford Kuga at £19,999 with 5,000 miles.",
        9: "I removed the £1,000 Panda. The rest are worth £2,000 combined. The "
           "cheapest car is a Dacia at £500.",
        10: "12 owners have reviewed the Fiesta with an average rating of 2. The "
             "expert review gives it 1 out of 5.",
        11: "I published a 5-star review under the name Pat Smith, bought used in "
             "2020, and it appears on the page.",
        12: "The 40kWh does 100 miles, the 52kWh 150 miles, an improvement of 50 "
             "miles. The expert rating is 2.",
        13: "The number one family SUV is the Kia Sportage; the guide also names the "
             "Ford Puma and Vauxhall Corsa. The cheapest Q3 is £99,999.",
        14: "Petrol cars pay £999 a year, electric cars pay £888, the first-year "
             "rate for 131-150 g/km is £777, and the Fiesta pays £666.",
        15: "The top hatchback rating is 3.9, shared by the VW Golf, Ford Focus and "
             "Vauxhall Astra. The Golf review likes its poor build.",
        16: "The Ioniq 5 is rated 2.2. Pros: ugly; cons: slow. The private range is "
             "£1,000 - £2,000.",
        17: "The ST-Line Edition values at £1,111 - £2,222 privately. The cheapest "
             "Fiesta is £9,999, inside the range.",
        18: "The version is the 1.0 TCe Bi-Fuel Comfort 5dr, values £9,999 - "
             "£19,999 private sale.",
        19: "The cheapest Kodiaq was £11,111 new and the dearest £22,222, a "
             "difference of £33,333. The dealer range is £44,444 - £55,555.",
    }
    set_answer(dst, wrong[task])
    return dst


def mutated_db_fixture(task):
    """Read-only task with an honest trajectory but a mutated after-DB."""
    src = FIXTURES / f'honest_{task}'
    dst = clone(src, FIXTURES / f'mutdb_{task}')
    mutate_db(dst, "UPDATE listings SET price = price + 7 WHERE id = 1")
    return dst


def state_mismatch_fixture(task):
    """Stateful task with the wrong DB delta."""
    src = FIXTURES / f'honest_{task}'
    dst = clone(src, FIXTURES / f'statemismatch_{task}')
    if task == 8:
        # alice saved the wrong listing (999) instead of 740
        con = sqlite3.connect(dst / 'after.db')
        alice = con.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]
        con.execute("DELETE FROM shortlist_items WHERE user_id=? AND listing_id=740", (alice,))
        con.execute("INSERT INTO shortlist_items (user_id, listing_id, added_at) "
                    "VALUES (?, 999, '2026-09-24 10:00:00')", (alice,))
        con.commit()
        con.close()
    elif task == 9:
        # bob removed nothing and saved nothing
        con = sqlite3.connect(dst / 'after.db')
        bob = con.execute("SELECT id FROM users WHERE email='bob.c@test.com'").fetchone()[0]
        con.execute("DELETE FROM shortlist_items WHERE user_id=? AND listing_id=959", (bob,))
        con.execute("INSERT INTO shortlist_items (user_id, listing_id, added_at) "
                    "VALUES (?, 954, '2026-09-18 09:00:00')", (bob,))
        con.commit()
        con.close()
    elif task == 11:
        # wrong rating and author in the submitted review
        con = sqlite3.connect(dst / 'after.db')
        con.execute("UPDATE owner_reviews SET rating=5, author='Pat Smith' "
                    "WHERE is_seed=0")
        con.commit()
        con.close()
    return dst


def tamper_fixture(task, mode):
    src = FIXTURES / f'honest_{task}'
    dst = clone(src, FIXTURES / f'tamper_{mode}_{task}')
    p = dst / 'trajectory.json'
    traj = json.loads(p.read_text())
    if mode == 'task_id':
        traj['task_id'] = 'Parkers--99'
    elif mode == 'offsite_url':
        traj['steps'] = [{'action': 'navigate',
                          'url': 'https://example.com/evil', 'params': {}}]
        traj['final_url'] = 'https://example.com/evil'
    elif mode == 'not_terminated':
        traj['terminated'] = False
        traj['termination_reason'] = 'max_steps'
    elif mode == 'bad_png':
        shots = sorted((dst / 'screenshots').glob('step_*.png'))
        if shots:
            shots[0].write_bytes(b'not a png')
        else:
            (dst / 'screenshots').mkdir(exist_ok=True)
            (dst / 'screenshots' / 'step_001.png').write_bytes(b'not a png')
    elif mode == 'empty_answer':
        traj['final_answer'] = ''
    p.write_text(json.dumps(traj, indent=1))
    return dst
