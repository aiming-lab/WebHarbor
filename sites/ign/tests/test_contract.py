"""Answer and navigation regressions; UI/state controls are documented in verify/README.md."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verify'))
from task_contract import comparison_answer, snapshot
from verify_lib import navigated_to


class ComparisonTests(unittest.TestCase):
    def test_positive_prose_bullets_and_tables(self):
        answers = [
            'Turtle Beach Stealth Pro II Review.',
            'The headset tag belongs to Turtle Beach Stealth Pro II, not Corsair One A600.',
            'Corsair does not have the headset tag; Turtle Beach does.',
            'Not Corsair, but Turtle Beach.',
            'Turtle Beach rather than Corsair.',
            '- Turtle Beach: headset tag present\n- Corsair: headset tag absent',
            '| Review | Headset tag |\n|---|---|\n| Turtle Beach | Yes |\n| Corsair | No |',
            'I opened both Turtle Beach and Corsair. The headset tag is on Turtle Beach.',
            'Turtle Beach has the tag, while Corsair does not.',
            'Unlike Corsair, Turtle Beach includes the headset tag.',
            'Turtle Beach, not Corsair, has the headset tag.',
            'The headset tag is on the Stealth Pro II review.',
        ]
        for answer in answers:
            with self.subTest(answer=answer):
                self.assertTrue(comparison_answer(answer, 4))
        for answer in [
            'Amazon Prime Video.',
            'Nintendo Switch 2 appears on Amazon Prime Video, not HBO Max.',
            'HBO Max does not list Nintendo Switch 2; Amazon Prime Video does.',
            'Amazon Prime Video lists Nintendo Switch 2; HBO Max does not.',
            '| Story | Nintendo Switch 2 |\n| Amazon Prime Video | Yes |\n| HBO Max | No |',
        ]:
            with self.subTest(answer=answer):
                self.assertTrue(comparison_answer(answer, 17))

    def test_negations_conflicts_and_ambiguous_answers(self):
        for task, answers in [(4, [
            '', 'Corsair One A600.',
            'Corsair includes the headset tag; Turtle Beach does not.',
            'Turtle Beach does not have the headset tag.',
            'Both Turtle Beach and Corsair have the headset tag.',
            'Turtle Beach has the headset tag. Corsair also has it.',
            'Turtle Beach or Corsair.',
            'I compared Turtle Beach with Corsair.',
            'Perhaps Turtle Beach.',
            'Not Turtle Beach, but Corsair.',
            'Turtle Beach lacks the tag; Corsair has it.',
            'Turtle Beach has the tag. Turtle Beach does not have it.',
        ]), (17, [
            'HBO Max has Nintendo Switch 2; Amazon Prime Video does not.',
            'Both Amazon Prime Video and HBO Max list Nintendo Switch 2.',
            'Amazon Prime Video does not list Nintendo Switch 2.',
            'HBO Max rather than Amazon Prime Video.',
            'I visited Amazon Prime Video and HBO Max.',
        ])]:
            for answer in answers:
                with self.subTest(task=task, answer=answer):
                    self.assertFalse(comparison_answer(answer, task))


class NavigationTests(unittest.TestCase):
    def trajectory(self, url):
        return {'start_url': 'http://localhost:40050/', 'steps': [{'url': url}]}

    def test_query_fragment_and_foreign_origin_are_not_visits(self):
        for url in ['http://localhost:40050/search?q=/account',
                    'http://localhost:40050/#/account', 'https://elsewhere.test/account',
                    'http://localhost:40051/account', 'http://localhost:40050/account/edit']:
            with self.subTest(url=url):
                self.assertFalse(navigated_to(self.trajectory(url), '/account'))

    def test_local_exact_path(self):
        self.assertTrue(navigated_to(self.trajectory('http://localhost:40050/account?tab=profile'), '/account'))
        self.assertTrue(navigated_to(self.trajectory('http://localhost:40050/account/'), '/account'))

    def test_missing_snapshot_fails_without_creating_a_database(self):
        with self.assertRaises(ValueError):
            snapshot('/this/database/does/not/exist.db')


# Integration-level state assertions use the real tracked catalog/seed generator
# in an isolated directory. SQL mutations below are synthetic grading controls,
# never evidence of browser task completion.
import shutil
import sqlite3
import subprocess
import tempfile
from types import SimpleNamespace
from task_contract import check_contract
from verify_lib import Judge


class StateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        site = Path(__file__).resolve().parents[1]
        for filename in ['app.py', 'seed_data.py', 'content_seed.py']:
            shutil.copy2(site / filename, cls.root / filename)
        subprocess.run([sys.executable, '-c', 'import app'], cwd=cls.root, check=True,
                       capture_output=True)
        cls.seed = cls.root / 'instance/ign.db'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def verdict(self, task, sql, paths, answer='', missing=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copy2(self.seed, root / 'after.db')
            if not missing:
                shutil.copy2(self.seed, root / 'initial.db')
            with sqlite3.connect(root / 'after.db') as db:
                db.executescript(sql)
            origin = 'http://localhost:40050'
            t = {'start_url': origin + '/', 'steps': [{'url': origin + p} for p in paths],
                 'final_url': origin + paths[-1], 'final_answer': answer}
            j = Judge(f'IGN--{task}', no_llm=True)
            check_contract(j, t, SimpleNamespace(initial_db=str(root / 'initial.db'),
                           after_db=str(root / 'after.db'), container='unused'))
            return j.ok

    def test_only_target_saved_item_removed(self):
        where = "user_id=(SELECT id FROM users WHERE email='alice.j@test.com') AND folder='Deals'"
        self.assertTrue(self.verdict(14, 'DELETE FROM saved_items WHERE ' + where, ['/login', '/saved']))
        self.assertFalse(self.verdict(14, "UPDATE saved_items SET folder='Weekend' WHERE " + where,
                                      ['/login', '/saved']))
        self.assertFalse(self.verdict(14, 'DELETE FROM saved_items', ['/login', '/saved']))

    def test_profile_values_and_unrelated_fields(self):
        sql = "UPDATE users SET region='San Francisco, CA', favorite_platform='Nintendo Switch 2' WHERE email='carol.d@test.com';"
        self.assertTrue(self.verdict(5, sql, ['/login', '/account/edit', '/account']))
        self.assertFalse(self.verdict(5, sql.replace('San Francisco, CA', 'San Francisco, TX'), ['/login', '/account/edit']))
        self.assertFalse(self.verdict(5, sql + "UPDATE users SET bio='unrequested' WHERE email='bob.c@test.com';", ['/login', '/account/edit']))

    def test_alert_requires_whole_keyword(self):
        sql = "INSERT INTO alert_subscriptions (user_id,section_slug,keyword,frequency,active,created_at) VALUES (4,'games','PlayStation','daily',1,'2026-07-02');"
        self.assertTrue(self.verdict(3, sql, ['/login', '/alerts']))
        self.assertFalse(self.verdict(3, sql.replace("'PlayStation'", "'NotPlayStation'"), ['/login', '/alerts']))

    def test_comment_text_cannot_be_negated(self):
        sql = "INSERT INTO comments (user_id,item_id,body,sentiment,created_at) VALUES (1,3,'Watch this before the finale.','neutral','2026-07-02');"
        paths = ['/login', '/articles/silo-season-3-review']
        self.assertTrue(self.verdict(7, sql, paths))
        self.assertFalse(self.verdict(7, sql.replace('Watch this', 'Do not Watch this'), paths))

    def test_registration_password_initial_state_and_end_page(self):
        import bcrypt
        password = bcrypt.hashpw(b'TestPass123!', bcrypt.gensalt()).decode()
        wrong = bcrypt.hashpw(b'WrongPass123!', bcrypt.gensalt()).decode()
        sql = f"INSERT INTO users (email,username,password_hash,display_name,region,favorite_platform,bio,avatar_color,notification_email,created_at) VALUES ('henry.m@test.com','henry_m','{password}','Henry M','United States','PC','','#bf1313',1,'2026-07-02');"
        paths = ['/register', '/account']
        self.assertTrue(self.verdict(19, sql, paths))
        self.assertFalse(self.verdict(19, sql.replace(password, wrong), paths))
        self.assertFalse(self.verdict(19, sql, ['/register', '/']))
        self.assertFalse(self.verdict(19, sql, paths, missing=True))

    def test_read_only_task_cannot_change_account(self):
        paths = ['/reviews?genre=tech', '/articles/turtle-beach-stealth-pro-ii-review', '/articles/corsair-one-a600-review']
        self.assertTrue(self.verdict(4, '', paths, 'Turtle Beach.'))
        self.assertFalse(self.verdict(4, "UPDATE users SET bio='unrequested';", paths, 'Turtle Beach.'))
        self.assertFalse(self.verdict(4, '', paths[1:], 'Turtle Beach.'))


if __name__ == '__main__':
    unittest.main()
