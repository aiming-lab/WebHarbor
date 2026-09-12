"""Independent full-schema synthetic seed fixtures. These are not browser E2E."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from verify_lib import evaluate, answer_ok, STATEFUL_TASKS

HERE = Path(__file__).parent
ORIGIN = 'http://127.0.0.1:47930'
# Manually authored responses and page observations, not verifier PASS constants.
CASES = [
    ('Tidal Memory cassette: $15.00.', '/album/tidal-memory'),
    ('The third track is Between Stations.', '/album/between-stations'),
    ('Pair is cheaper than Glow Pair: $22 versus $27.', '/merch/ashen-circuit-grid-slipmat'),
    ('Saved.', '/album/machine-prayer'),
    ('Done.', '/cart'),
    ('Tidal Memory is longer at 20:10; Harbor Burn is 17:55.', '/compare/releases?right=tidal-memory&left=harbor-burn'),
    ('Track 4 lasts 4:31.', '/album/tidal-memory'),
    ('Checkout completed.', '/checkout'),
    ('Updated.', '/account'),
    ('BC-20260426-0002', '/orders'),
    ('Resin Language digital price: $8.50.', '/album/resin-language'),
    ('The physical formats are CD and vinyl. Digital is not physical.', '/album/elastic-hearts'),
    ('The signed poster costs $27.00.', '/merch/velvet-avenue-night-shift-poster'),
    ('Digital Album is cheapest at $9.50.', '/album/blue-hour-broadcast'),
    ('The favorite track is Between Stations.', '/collection'),
    ('The newest album is Static Bloom by Glass Choir.', '/album/static-bloom'),
    ('The closing track is Wide Exit.', '/album/harbor-burn'),
    ('Natural and Forest.', '/merch/salt-meadow-field-notes-tote'),
]


def mutate(path, sql):
    with sqlite3.connect(path) as db:
        db.executescript(sql)


def complete(path, index):
    if index == 3:
        mutate(path, "INSERT INTO wishlist_items VALUES (17,1,6,NULL,'2026-09-09')")
    elif index == 4:
        mutate(path, "INSERT INTO cart_items VALUES (10,2,NULL,7,40,1,'2026-09-09')")
    elif index == 8:
        mutate(path, "UPDATE users SET city='Eugene',favorite_format='vinyl' WHERE id=4")
    elif index == 7:
        mutate(path, """
            INSERT INTO orders VALUES (6,2,'BC-20260501-0006','paid',36.5,6.5,3.01,46.01,
                'Bob Chen','77 Fulton Market','Chicago','United States','Mock card','','2026-05-01 12:06:00.000000');
            INSERT INTO order_items (id,order_id,album_id,merch_item_id,format_variant_id,title,artist_name,image_path,variant_label,quantity,unit_price)
                SELECT 10,6,a.id,NULL,55,a.title,ar.name,a.cover_image,'Digital Album / MP3 + FLAC',1,8.5
                FROM albums a JOIN artists ar ON ar.id=a.artist_id WHERE a.id=11;
            INSERT INTO order_items (id,order_id,album_id,merch_item_id,format_variant_id,title,artist_name,image_path,variant_label,quantity,unit_price)
                SELECT 11,6,NULL,m.id,60,m.title,ar.name,m.image,'Signed / 18x24',1,28
                FROM merch_items m JOIN artists ar ON ar.id=m.artist_id WHERE m.id=11;
            DELETE FROM cart_items WHERE user_id=2;
            UPDATE albums SET fan_count=fan_count+1 WHERE id=11;
            UPDATE format_variants SET inventory=inventory-1 WHERE id=60;
        """)


def trajectory(index, answer=None, urls=None):
    return dict(task_id=f'Bandcamp--{index}', start_url=ORIGIN + '/',
                final_answer=CASES[index][0] if answer is None else answer,
                steps=[dict(url=u) for u in ([ORIGIN + CASES[index][1]] if urls is None else urls)])


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.before = cls.root / 'initial.db'
        mutate(cls.before, (HERE / 'test_seed.sql').read_text())
        cls.after = {}
        for i in range(18):
            cls.after[i] = cls.root / f'after-{i}.db'
            shutil.copyfile(cls.before, cls.after[i])
            complete(cls.after[i], i)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, i, answer=None, urls=None, after=None):
        return evaluate(i, trajectory(i, answer, urls), self.before, after or self.after[i])

    def test_all_task_matrix(self):
        for i in range(18):
            with self.subTest(task=i):
                self.assertTrue(self.verdict(i)['pass'])
                self.assertFalse(self.verdict(i, '', [ORIGIN + '/'], self.before)['pass'])
                self.assertFalse(self.verdict(i, urls=[])['pass'])
                self.assertFalse(self.verdict(i, urls=['https://evil.example' + CASES[i][1]])['pass'])
                self.assertFalse(self.verdict(i, urls=[ORIGIN + '/?next=' + CASES[i][1]])['pass'])
                self.assertFalse(self.verdict(i, urls=['http://127.0.0.1:47931' + CASES[i][1]])['pass'])
                if i in STATEFUL_TASKS:
                    self.assertFalse(self.verdict(i, after=self.before)['pass'])
                    self.assertTrue(self.verdict(i, '\u5df2\u5b8c\u6210\u3002')['pass'])
                    # State wording does not substitute for or invalidate authoritative state.
                    self.assertTrue(self.verdict(i, 'An unrelated sentence.')['pass'])
                else:
                    self.assertFalse(self.verdict(i, 'Unknown; I did not find an answer.')['pass'])
                    self.assertFalse(self.verdict(i, 'It is false that ' + CASES[i][0])['pass'])
                wrong = trajectory(i)
                wrong['task_id'] = f'Bandcamp--{(i + 1) % 18}'
                with self.assertRaises(ValueError):
                    evaluate(i, wrong, self.before, self.after[i])

    def test_information_near_misses(self):
        negatives = {
            0: ['The cassette is not $15.00.', 'The cassette costs $8.50.', "Harbor Burn's cassette costs $15.00.", 'Cassette is $15. Cassette is not $15.'],
            1: ['The album is Between Stations.', 'The second track is Between Stations.'],
            2: ['Glow Pair is cheaper than Pair.', 'Pair is not cheaper.', 'Pair costs $27 and Glow Pair $22; Pair is cheaper.'],
            5: ['Tidal Memory is not longer.', 'Harbor Burn is longer than Tidal Memory.', 'Tidal Memory is longer at 17:55, Harbor Burn at 20:10.'],
            6: ['Track 4 is not 4:31.', 'Track 4 lasts 4:30.'],
            9: ['Not BC-20260426-0002.', 'BC-20260414-0001'],
            10: ['The digital album is not $8.50.', 'Digital: $9.50.'],
            11: ['CD, vinyl and cassette.', 'CD, vinyl and digital.', 'Neither CD nor vinyl.', 'CD, vinyl and USB.'],
            12: ['Signed is not $27.00.', 'Standard costs $27.00.'],
            13: ['Digital is the most expensive at $9.50.', 'Digital is not $9.50.'],
            14: ['The album is Between Stations.', 'The favorite track is not Between Stations.'],
            15: ['Static Bloom is not the newest album.', 'The oldest is Static Bloom.'],
            16: ['Wide Exit is not the closing track.', 'The opening track is Wide Exit.'],
            17: ['Natural, Forest and Black.', 'Neither Natural nor Forest.'],
        }
        for i, answers in negatives.items():
            for answer in answers:
                with self.subTest(task=i, answer=answer):
                    self.assertFalse(self.verdict(i, answer)['pass'])

    def test_legal_alternatives(self):
        self.assertTrue(self.verdict(15, urls=[ORIGIN + '/search?q=guitar+songs', ORIGIN + '/artist/glass-choir', ORIGIN + '/album/static-bloom'])['pass'])
        for answer in ['Pair is cheaper, not Glow Pair.', 'Pair is cheaper than Glow Pair.', 'Glow Pair is not cheaper. Pair is cheaper at $22.']:
            self.assertTrue(self.verdict(2, answer)['pass'], answer)
        self.assertTrue(self.verdict(11, 'CD and vinyl, not digital.')['pass'])
        self.assertTrue(self.verdict(11, 'CD and vinyl (digital is not physical).')['pass'])
        self.assertTrue(self.verdict(5, 'Tidal Memory is not shorter than Harbor Burn.')['pass'])
        for i, answer in [(0, '$15.00'), (2, 'Pair ($22.00)'), (5, 'Tidal Memory'), (10, '$8.50'), (12, '$27.00'),
                          (17, 'The two colors available for the tote are Natural and Forest.')]:
            with self.subTest(task=i, answer=answer):
                self.assertTrue(self.verdict(i, answer)['pass'])

    def test_extra_mutation_every_table(self):
        for i in range(18):
            for table in ('users', 'artists', 'albums', 'tracks', 'cart_items', 'orders', 'order_items', 'wishlist_items',
                          'fan_collection_items', 'fan_comments', 'format_variants', 'genres', 'labels', 'scenes', 'tags', 'merch_items', 'album_tags'):
                with self.subTest(task=i, table=table):
                    path = self.root / 'mutated.db'
                    shutil.copyfile(self.after[i], path)
                    mutate(path, f'DELETE FROM {table} WHERE rowid=(SELECT MIN(rowid) FROM {table})')
                    self.assertFalse(self.verdict(i, after=path)['pass'])

    def test_state_specific_mutations(self):
        cases = {
            3: ["UPDATE wishlist_items SET user_id=2 WHERE id=17", "UPDATE wishlist_items SET album_id=1 WHERE id=17", "INSERT INTO wishlist_items VALUES (18,1,6,NULL,'extra')"],
            4: ["UPDATE cart_items SET user_id=1 WHERE id=10", "UPDATE cart_items SET quantity=2 WHERE id=10", "UPDATE cart_items SET quantity=1.5 WHERE id=10", "UPDATE cart_items SET format_variant_id=39 WHERE id=10", "UPDATE cart_items SET album_id=1 WHERE id=10", "INSERT INTO cart_items VALUES (11,2,NULL,7,40,1,'extra')"],
            7: ["UPDATE orders SET user_id=1 WHERE id=6", "UPDATE orders SET total=0 WHERE id=6", "UPDATE orders SET shipping_name='Alice' WHERE id=6", "UPDATE order_items SET quantity=2 WHERE id=11", "UPDATE order_items SET format_variant_id=59 WHERE id=11", "UPDATE order_items SET order_id=1 WHERE id=11", "UPDATE order_items SET unit_price=1 WHERE id=11", "UPDATE format_variants SET inventory=25 WHERE id=60", "UPDATE users SET bio='extra' WHERE id=2", "INSERT INTO orders SELECT 7,user_id,'extra',status,subtotal,shipping,tax,total,shipping_name,shipping_line1,shipping_city,shipping_country,payment_label,note,placed_at FROM orders WHERE id=6"],
            8: ["UPDATE users SET city='Portland' WHERE id=4", "UPDATE users SET favorite_format='Vinyl' WHERE id=4", "UPDATE users SET address_line1='extra' WHERE id=4", "UPDATE users SET city='Eugene' WHERE id=1"],
        }
        for i, sqls in cases.items():
            for sql in sqls:
                with self.subTest(task=i, sql=sql):
                    path = self.root / 'mutated.db'
                    shutil.copyfile(self.after[i], path)
                    mutate(path, sql)
                    self.assertFalse(self.verdict(i, after=path)['pass'])

    def test_task4_full_noncart_fields_remain_protected(self):
        with sqlite3.connect(self.before) as db:
            columns = [(table, r[1], r[2]) for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='cart_items'")
                       for r in db.execute(f'PRAGMA table_info("{table}")')]
        for table, column, dtype in columns:
            with self.subTest(table=table, column=column):
                path = self.root / 'fields.db'
                shutil.copyfile(self.after[4], path)
                value = f'COALESCE("{column}",0)+10000' if dtype == 'INTEGER' else "'unrequested'"
                mutate(path, f'UPDATE "{table}" SET "{column}"={value} WHERE rowid=(SELECT MIN(rowid) FROM "{table}")')
                self.assertFalse(self.verdict(4, after=path)['pass'])

    def test_wrapper_codes_and_snapshot_discovery(self):
        for i in range(18):
            run = self.root / f'cli-{i}'
            run.mkdir()
            shutil.copyfile(self.before, run / 'before.db')
            shutil.copyfile(self.after[i], run / 'after.db')
            command = [sys.executable, '-B', str(HERE / f'verify_{i}.py'), '--run_dir', str(run)]
            for expected, traj in [(0, trajectory(i)), (1, trajectory(i, '', [])), (2, dict(trajectory(i), task_id='wrong'))]:
                (run / 'trajectory.json').write_text(json.dumps(traj))
                reply = subprocess.run(command, capture_output=True, text=True)
                with self.subTest(task=i, exit=expected):
                    self.assertEqual(reply.returncode, expected, reply.stdout + reply.stderr)
                    result = json.loads(reply.stdout)
                    self.assertIs(result['pass'], expected == 0)
            (run / 'trajectory.json').write_text(json.dumps(trajectory(i)))
            (run / 'after.db').unlink()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            (run / 'after.db').write_text('not sqlite')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            shutil.copyfile(self.after[i], run / 'after.db')
            mutate(run / 'after.db', 'ALTER TABLE users ADD COLUMN surprise TEXT')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            (run / 'trajectory.json').write_text('{broken')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_mapping_and_rubrics(self):
        tasks = [json.loads(line) for line in (HERE.parent / 'tasks.jsonl').read_text().splitlines()]
        self.assertEqual(len(tasks), 18)
        for i, task in enumerate(tasks):
            self.assertEqual(task['id'], f'Bandcamp--{i}')
            self.assertEqual(task['verifier_path'], f'sites/bandcamp/verify/verify_{i}.py')
            self.assertTrue((HERE / f'verify_{i}.py').is_file())
            self.assertNotIn('answer', task)
            self.assertNotIn('$', task['judge_rubric'])
            self.assertNotIn('BC-2026', task['judge_rubric'])
            self.assertTrue(task['judge_rubric'].startswith('FACT CHECKPOINTS:'))


if __name__ == '__main__':
    unittest.main()
