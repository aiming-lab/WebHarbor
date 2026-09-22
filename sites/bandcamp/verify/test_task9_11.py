"""9/11 专项：完整 schema、变体真值、反例与独立 standalone exit 检查。"""
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import verify_lib as v
import test_verifiers as legacy

HERE = Path(__file__).resolve().parent
NEW = 'BC-20260426-0002'
OLD = 'BC-20260414-0001'
REAL9 = 'Signed in as Alice Johnson. Her most recent seeded order number is BC-20260426-0002, dated April 26, 2026.'
REAL11 = 'The release is Elastic Hearts by Fever Arcade (London, pop), released December 5, 2025. It offers two physical formats: Colored Vinyl — 12-inch, Ocean Blue ($24.50), and Compact Disc — Gatefold ($17.00).'

POS9 = [
    NEW, REAL9, NEW.lower(), '**bc ‑ 20260426 – 0002**', 'ＢＣ－２０２６０４２６－０００２',
    f'Her latest order number is {NEW}.', f'{NEW} is the latest.',
    f'The latest order is {NEW}, dated April 26, 2026.',
    f'Latest: {NEW}, not {OLD}.', f'Latest: {NEW}; older order: {OLD}.',
    f'{OLD} is older; {NEW} is latest.', f'Not {OLD}; {NEW}.',
    f'Latest: {NEW}, compared with older order {OLD}.',
    f'{NEW}; {NEW}.', f'{NEW} on 2026-04-26.',
]
NEG9 = [
    '', OLD, 'BC-20260425-0005', 'BC-20990101-9999', 'BC-20260426-00020',
    'XBC-20260426-0002', NEW + '-extra', NEW + 'x', 'BC-20260426-000',
    f'Not {NEW}.', f'{NEW} is not latest.', f'Her latest order is not {NEW}.',
    f'{NEW}, {OLD}', f'Either {NEW} or {OLD}.', f'{NEW} or unknown.',
    f'Latest: {OLD}; older order: {NEW}.', f'Latest: {NEW}; latest: {OLD}.',
    f'{NEW}. Not {NEW}.', f'It is false that {NEW}.',
    f"Bob Chen's latest order is {NEW}.", f'Signed in as Bob Chen. {NEW}.',
    f'{NEW}, dated April 14, 2026.', f'Maybe {NEW}.', f'{NEW}?',
    f'Older order: {NEW}.', f'I saw {NEW} but cannot tell which is latest.',
    f'Latest: {NEW}; older order BC-20260425-0005.',
    f'orderref999; {NEW}', f'orderref0; {NEW}',
]
POS11 = [
    REAL11, 'CD and vinyl', 'Compact Disc and Colored Vinyl.', 'compact disk and LP',
    'CDs & vinyl records', 'CD / vinyl', 'Elastic Hearts offers CD and vinyl.',
    'The physical formats are CD and vinyl.', 'It offers 2 physical formats: CD and vinyl.',
    'It offers both physical formats: CD and vinyl.',
    'Not cassette, CD and vinyl.', 'CD and vinyl, not cassette.',
    'CD and vinyl; no MiniDisc.', 'CD and vinyl. Digital is not physical.',
    'CD and vinyl (digital is not physical).', 'CD and vinyl; digital does not count as a physical format.',
    'CD and vinyl, not digital.', 'CD is available; vinyl is offered.',
    'Colored Vinyl / 12-inch / Ocean Blue ($24.50), Compact Disc / Gatefold ($17).',
    'CD — Gatefold, vinyl — 12-inch, Ocean Blue.', 'CD and CD and vinyl.',
    'The artist is Fever Arcade, from London. CD and vinyl.',
    'CD ($17.00 USD) and LP ($24.5).', 'CD\n- Vinyl',
]
NEG11 = [
    '', 'CD', 'vinyl', 'Colored Vinyl and LP', 'CD and Compact Disc',
    'CD, vinyl and cassette.', 'CD, vinyl and digital.', 'CD, vinyl and MiniDisc.',
    'CD, vinyl and USB.', 'CD, vinyl and DVD.', 'CD, vinyl and holographic cube.',
    'CD and vinyl. It offers holographic cube.',
    'Not CD and vinyl.', 'Neither CD nor vinyl.', 'No CD, no vinyl.',
    'CD and vinyl but no CD.', 'CD and vinyl; CD is unavailable.',
    'CD is not available; vinyl is offered.', 'Vinyl and CD (not offered).',
    'CD and vinyl are not available.', 'CD and vinyl but it is false that CD is offered.',
    'Either CD or vinyl.', 'CD or vinyl.', 'Maybe CD and vinyl.',
    'Tidal Memory offers CD and vinyl.', "Tidal Memory's physical formats are CD and vinyl.",
    'For Tidal Memory: CD and vinyl.', 'Elastic Hearts has no physical formats. Tidal Memory has CD and vinyl.',
    'CD and vinyl, but not for Elastic Hearts.', 'Not Elastic Hearts. CD and vinyl.',
    'The release is Imaginary Album. Imaginary Album offers CD and vinyl.',
    'The release is Imaginary Album. CD and vinyl.',
    'CD and vinyl. None are available.', 'It offers no physical formats: CD and vinyl.',
    'Not physical formats are CD and vinyl.', 'It offers three physical formats: CD and vinyl.',
    'CD — Ocean Blue and vinyl — Gatefold.', 'CD ($24.50) and vinyl ($17.00).',
    'CD and vinyl — 12-inch, Red.', 'CD and vinyl and',
    'I cannot confirm CD and vinyl.', 'CD and vinyl?', 'CD-ROM and vinyl.',
    'CD ($17.0017.00) and vinyl.', 'CD and vinyl (12-inchOcean Blue).',
]


class FocusedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.before = self.root / 'initial.db'
        self.after = self.root / 'after.db'
        self.sql(self.before, (HERE / 'test_seed.sql').read_text())
        shutil.copyfile(self.before, self.after)

    def sql(self, path, sql):
        with closing(sqlite3.connect(path)) as db:
            db.executescript(sql)
            db.commit()

    def reseed(self, sql):
        self.sql(self.before, sql)
        shutil.copyfile(self.before, self.after)

    def verdict(self, index, answer, urls=None):
        return v.evaluate(index, legacy.trajectory(index, answer, urls), self.before, self.after)

    def test9_truth_is_account_and_time_not_id_or_number(self):
        # A smaller row ID and lexically smaller, differently shaped number win.
        self.reseed("UPDATE orders SET order_number='ZX-7-A', placed_at='2027-01-03 00:00:00.000000' WHERE id=1; UPDATE orders SET placed_at='2099-01-01 00:00:00.000000' WHERE user_id!=1")
        self.assertTrue(self.verdict(9, 'ZX-7-A')['pass'])
        self.assertFalse(self.verdict(9, NEW)['pass'])
        self.assertTrue(self.verdict(9, 'ZX-7-A', [legacy.ORIGIN + '/orders/ZX-7-A'])['pass'])
        self.assertFalse(self.verdict(9, 'ZX-7-A', [legacy.ORIGIN + '/orders/' + NEW])['pass'])

    def test9_same_day_precise_time(self):
        self.reseed("UPDATE orders SET placed_at='2026-04-26 12:00:00.000001' WHERE id=1")
        self.assertTrue(self.verdict(9, OLD)['pass'])
        self.assertFalse(self.verdict(9, NEW)['pass'])

    def test9_invalid_fixture_is_infra_even_for_empty_answer(self):
        for sql in [
            "UPDATE users SET email='elsewhere@test.com' WHERE email='alice.j@test.com'",
            "UPDATE orders SET user_id=2 WHERE user_id=1",
            "UPDATE orders SET placed_at='2026-04-26 12:00:00.000000' WHERE user_id=1",
            "UPDATE orders SET placed_at='not a date' WHERE id=2",
            "UPDATE orders SET placed_at='2026-02-30 12:00:00' WHERE id=2",
            "UPDATE orders SET placed_at='2026-04-26 12:00:00' WHERE id=1",
            "UPDATE orders SET order_number='bc-20260426-0002' WHERE id=1",
        ]:
            with self.subTest(sql=sql):
                data = v.snapshot(self.before)[0]
                tmp = self.root / 'invalid.db'
                shutil.copyfile(self.before, tmp)
                self.sql(tmp, sql)
                with self.assertRaises(ValueError):
                    v.evaluate(9, legacy.trajectory(9, ''), tmp, tmp)
                self.assertEqual(data, v.snapshot(self.before)[0])

    def test9_protected_paths_exact(self):
        for path in ['/account', '/orders', '/orders/' + NEW]:
            with self.subTest(path=path):
                self.assertTrue(self.verdict(9, NEW, [legacy.ORIGIN + path])['pass'])
        for path in ['/account/edit', '/accounting', '/account/child', '/account/', '/orders/' + OLD,
                     '/orders/' + NEW + '/extra', '/login?next=/account', '/?next=/orders', '/orderlist', '/orderdetail']:
            with self.subTest(path=path):
                self.assertFalse(self.verdict(9, NEW, [legacy.ORIGIN + path])['pass'])

    def test_both_origins_pages_and_identity(self):
        for i, answer, path in [(9, NEW, '/account'), (11, 'CD and vinyl', '/album/elastic-hearts')]:
            for url in ['https://evil.example' + path, 'http://127.0.0.1:47931' + path,
                        'https://127.0.0.1:47930' + path, 'http://evil@127.0.0.1:47930' + path,
                        legacy.ORIGIN + '/login?next=' + path, legacy.ORIGIN + '/album/tidal-memory']:
                with self.subTest(task=i, url=url):
                    self.assertFalse(self.verdict(i, answer, [url])['pass'])
            for task_id in ['Bandcamp--0', 'wrong']:
                traj = dict(legacy.trajectory(i, answer), task_id=task_id)
                with self.assertRaises(ValueError):
                    v.evaluate(i, traj, self.before, self.after)

    def test11_different_physical_set_and_zero_stock(self):
        self.reseed("UPDATE format_variants SET kind='cassette',name='Cobalt Tape',option_a='',option_b='',inventory=0 WHERE album_id=19 AND kind='cd'; UPDATE format_variants SET inventory=0 WHERE album_id=19")
        self.assertTrue(self.verdict(11, 'Cobalt Tape and LP')['pass'])
        self.assertTrue(self.verdict(11, 'cassette and vinyl')['pass'])
        self.assertFalse(self.verdict(11, 'CD and vinyl')['pass'])
        self.assertFalse(self.verdict(11, 'cassette, vinyl and digital')['pass'])

    def test11_third_kind_and_kind_dedup(self):
        self.reseed("INSERT INTO format_variants SELECT 10000,album_id,merch_item_id,'minidisc','Mini Disc',option_a,option_b,price,0,'extra-md',shipping_note,edition_note,0 FROM format_variants WHERE album_id=19 AND kind='cd'")
        self.assertTrue(self.verdict(11, 'CD, vinyl and MiniDisc')['pass'])
        self.assertTrue(self.verdict(11, 'It offers three physical formats: CD, vinyl and MiniDisc')['pass'])
        self.assertFalse(self.verdict(11, 'CD and vinyl')['pass'])
        self.reseed("UPDATE format_variants SET kind='cd',name='Bonus Disc' WHERE id=10000")
        self.assertTrue(self.verdict(11, 'CD and vinyl')['pass'])
        self.assertTrue(self.verdict(11, 'Bonus Disc and vinyl')['pass'])

    def test11_different_name_price_and_options(self):
        self.reseed("UPDATE format_variants SET name='Archival Disc',option_a='Booklet',price=19.25 WHERE album_id=19 AND kind='cd'")
        self.assertTrue(self.verdict(11, 'Archival Disc / Booklet ($19.25), LP')['pass'])
        self.assertTrue(self.verdict(11, 'compact disk and vinyl')['pass'])
        self.assertFalse(self.verdict(11, 'CD / Gatefold ($17.00), LP')['pass'])

    def test11_kind_case_does_not_make_digital_physical(self):
        self.reseed("UPDATE format_variants SET kind='Digital' WHERE album_id=19 AND kind='digital'")
        self.assertTrue(self.verdict(11, 'CD and vinyl')['pass'])
        self.assertFalse(self.verdict(11, 'CD, vinyl and digital')['pass'])

    def test11_fixture_errors(self):
        for sql in ["UPDATE albums SET slug='elsewhere' WHERE slug='elastic-hearts'",
                    "UPDATE format_variants SET name='vinyl' WHERE album_id=19 AND kind='cd'",
                    "UPDATE format_variants SET kind='' WHERE album_id=19 AND kind='cd'"]:
            with self.subTest(sql=sql):
                tmp = self.root / 'invalid.db'
                shutil.copyfile(self.before, tmp)
                self.sql(tmp, sql)
                with self.assertRaises(ValueError):
                    v.evaluate(11, legacy.trajectory(11, ''), tmp, tmp)

    def test_supplemental_prose_is_not_certified(self):
        result = self.verdict(11, 'The artist lives on Mars. CD and vinyl.')
        self.assertTrue(result['pass'])  # Only the requested format proposition.
        self.assertIn('not_verified_requires_review', result['evidence'][-1])
        self.assertFalse(self.verdict(11, 'CD and vinyl. It offers unknown format X.')['pass'])

    def test_snapshot_readonly_and_all_table_mutations(self):
        original_hash = hashlib.sha256(self.before.read_bytes()).hexdigest()
        for i, answer in [(9, REAL9), (11, REAL11)]:
            for table in v.COLUMNS:
                with self.subTest(task=i, table=table):
                    shutil.copyfile(self.before, self.after)
                    self.sql(self.after, f'DELETE FROM "{table}" WHERE rowid=(SELECT MIN(rowid) FROM "{table}")')
                    self.assertFalse(self.verdict(i, answer)['pass'])
        self.assertEqual(hashlib.sha256(self.before.read_bytes()).hexdigest(), original_hash)

    def test_standalone_codes_and_explicit_paths(self):
        for i, answer in [(9, REAL9), (11, REAL11)]:
            run = self.root / f'cli-{i}'
            run.mkdir()
            cmd = [sys.executable, '-B', str(HERE / f'verify_{i}.py'), '--run_dir', str(run),
                   '--initial_db', str(self.before), '--after_db', str(self.after), '--no_llm', 'True']
            for expected, traj in [(0, legacy.trajectory(i, answer)), (1, legacy.trajectory(i, '', [])),
                                   (1, legacy.trajectory(i, 'unsupported unknown answer')), (2, {'task_id': 'wrong'})]:
                (run / 'trajectory.json').write_text(json.dumps(traj))
                reply = subprocess.run(cmd, capture_output=True, text=True)
                with self.subTest(task=i, exit=expected, case=traj):
                    self.assertEqual(reply.returncode, expected, reply.stdout + reply.stderr)
            (run / 'trajectory.json').write_text(json.dumps(legacy.trajectory(i, answer)))
            for sql in ['ALTER TABLE users ADD COLUMN unrequested TEXT', 'DROP TABLE order_items']:
                shutil.copyfile(self.before, self.after)
                self.sql(self.after, sql)
                reply = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(reply.returncode, 2, reply.stdout + reply.stderr)
            self.after.unlink()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            shutil.copyfile(self.before, self.after)
            missing_initial = cmd.copy()
            missing_initial[missing_initial.index('--initial_db') + 1] = str(self.root / 'missing.db')
            self.assertEqual(subprocess.run(missing_initial, capture_output=True).returncode, 2)
            (run / 'task.json').write_text('{"id":"wrong"}')
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)

    def test9_standalone_fixture_errors_exit2(self):
        run = self.root / 'fixture-cli'
        run.mkdir()
        (run / 'trajectory.json').write_text(json.dumps(legacy.trajectory(9, '')))
        fixture = self.root / 'fixture.db'
        cmd = [sys.executable, '-B', str(HERE / 'verify_9.py'), '--run_dir', str(run),
               '--initial_db', str(fixture), '--after_db', str(fixture)]
        for sql in ["UPDATE orders SET placed_at='2026-04-26 12:00:00.000000' WHERE user_id=1",
                    "UPDATE orders SET user_id=2 WHERE user_id=1",
                    "UPDATE users SET email='elsewhere@test.com' WHERE email='alice.j@test.com'"]:
            with self.subTest(sql=sql):
                shutil.copyfile(self.before, fixture)
                self.sql(fixture, sql)
                reply = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(reply.returncode, 2, reply.stdout + reply.stderr)
                self.assertEqual(json.loads(reply.stdout)['reason'], 'infrastructure_error')

    @unittest.skipUnless(os.environ.get('BANDCAMP_FROZEN_SESSION'), 'requires explicit frozen audit session')
    def test_actual_frozen_answers_and_inputs(self):
        s = Path(os.environ['BANDCAMP_FROZEN_SESSION'])
        for i, job, exact in [(9, 'job-0009-3e25a850fb60', REAL9), (11, 'job-0011-4b73af1be5bd', REAL11)]:
            actor = s / 'runs/bandcamp-n5-001/jobs' / job / 'actor'
            traj = json.loads((actor / 'trajectory.json').read_text())
            self.assertEqual(traj['final_answer'], exact)
            result = v.evaluate(i, traj, actor / 'backend/before.db', actor / 'backend/after.db')
            self.assertTrue(result['pass'], result)

    @unittest.skipUnless(os.environ.get('BANDCAMP_FROZEN_SESSION'), 'requires explicit frozen audit session')
    def test_other16_differential_frozen_regression(self):
        s = Path(os.environ['BANDCAMP_FROZEN_SESSION'])
        spec = importlib.util.spec_from_file_location('frozen_verify', s / 'builds/bandcamp-002/context/site/sites/bandcamp/verify/verify_lib.py')
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        for i in set(range(18)) - {9, 11}:
            shutil.copyfile(self.before, self.after)
            legacy.complete(self.after, i)
            for answer in [legacy.CASES[i][0], '', 'Unknown', 'It is false that ' + legacy.CASES[i][0]]:
                for urls in [None, [], [legacy.ORIGIN + '/wrong'], ['https://evil.example' + legacy.CASES[i][1]]]:
                    with self.subTest(task=i, answer=answer, urls=urls):
                        traj = legacy.trajectory(i, answer, urls)
                        self.assertEqual(v.evaluate(i, traj, self.before, self.after), old.evaluate(i, traj, self.before, self.after))


def add_case(index, answer, expected, number):
    def test(self):
        result = self.verdict(index, answer)
        self.assertEqual(result['pass'], expected, (answer, result))
    test.__doc__ = answer
    setattr(FocusedTests, f'test_{index}_{"accept" if expected else "reject"}_{number:03d}', test)


for index, positives, negatives in [(9, POS9, NEG9), (11, POS11, NEG11)]:
    for number, answer in enumerate(positives):
        add_case(index, answer, True, number)
    for number, answer in enumerate(negatives):
        add_case(index, answer, False, number)


if __name__ == '__main__':
    unittest.main()
