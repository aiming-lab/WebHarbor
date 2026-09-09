"""Positive and adversarial tests for all seven production verifiers."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bcrypt
from PIL import Image

from test_support import ensure_seed

VERIFY = Path(__file__).resolve().parent
SEED = ensure_seed()
BASE = 'http://localhost:40021'
TASKS = (0, 3, 8, 9, 11, 14, 18)


def nav(path):
    return {'url': BASE + path, 'action': 'navigate', 'params': {}}


def input_step(path, value):
    return {'url': BASE + path, 'action': 'input', 'params': {'index': 1, 'text': value}}


def transition(source, destination):
    return [
        {'url': BASE + source, 'action': 'click', 'params': {'index': 1}},
        nav(destination),
    ]


class VerifierTests(unittest.TestCase):
    def run_verifier(self, task, steps, answer, mutate=None, task_id=None, complete=True, valid_screenshots=True):
        with tempfile.TemporaryDirectory(prefix=f'rt-{task}-') as directory:
            root = Path(directory)
            initial = root / 'initial.db'
            after = root / 'after.db'
            run = root / 'run'
            run.mkdir()
            screenshots = run / 'screenshots'
            screenshots.mkdir()
            for index, step in enumerate(steps):
                step['screenshot_before'] = f'step_{index:03d}.png'
                step['screenshot_after'] = f'step_{index + 1:03d}.png'
            for index in range(len(steps) + 1):
                image = Image.effect_noise((320, 200), 32).convert('RGB') if valid_screenshots else Image.new('RGB', (1, 1))
                image.save(screenshots / f'step_{index:03d}.png')
            shutil.copy2(SEED, initial)
            shutil.copy2(SEED, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            trajectory = {
                'task_id': task_id or f'RottenTomatoes--{task}',
                'start_url': BASE + '/',
                'steps': steps,
                'terminated': complete,
                'termination_reason': 'agent_done' if complete else 'max_steps',
                'success_self_report': complete,
                'final_answer': answer,
            }
            (run / 'trajectory.json').write_text(json.dumps(trajectory), encoding='utf-8')
            result = subprocess.run([
                sys.executable, str(VERIFY / f'verify_{task}.py'), '--run_dir', str(run),
                '--initial_db', str(initial), '--after_db', str(after), '--no_llm', 'true',
            ], capture_output=True, text=True, timeout=45)
            try:
                verdict = json.loads(result.stdout)
            except Exception as error:
                self.fail(f'task {task}: stdout={result.stdout!r} stderr={result.stderr!r}: {error}')
            return result.returncode, verdict

    def positive(self, task):
        r0 = ['bugonia', 'frankenstein_2025', 'godzilla_minus_one', 'jurassic_world_rebirth',
              'the_hunger_games', 'the_hunger_games_catching_fire',
              'the_hunger_games_the_ballad_of_songbirds_and_snakes', 'war_machine']
        r18 = ['avengers_endgame', 'deadpool_and_wolverine', 'spider_man_brand_new_day',
               'the_fantastic_four_first_steps']
        if task == 0:
            filtered = '/browse/movies_at_home/?genre=sci-fi&platform=Netflix'
            steps = [nav(filtered)]
            for slug in r0:
                steps += transition(filtered, '/m/' + slug) + [nav(filtered)]
            return steps, '| Movie | Release Date (Streaming) | Screenwriter(s) |\n| War Machine | Mar 6, 2026 | Patrick Hughes, James Beaufort |', None
        if task == 3:
            search = '/search?search=Christopher+Nolan'
            steps = [nav(search)]
            for slug in ('oppenheimer_2023', 'the_dark_knight'):
                steps += transition(search, '/m/' + slug) + [nav(search)]
            answer = 'Shared producers: Emma Thomas, Charles Roven\nOppenheimer | Nov 21, 2023\nThe Dark Knight | Jun 14, 2010'
            return steps, answer, None
        if task == 8:
            steps = [nav('/register'), input_step('/register', 'Test Reviewer'),
                     input_step('/register', 'testreviewer@test.com'),
                     input_step('/register', 'ReviewPass456!'), input_step('/register', 'ReviewPass456!')]
            steps += transition('/register', '/') + transition('/', '/account')
            def mutation(connection):
                password_hash = bcrypt.hashpw(b'ReviewPass456!', bcrypt.gensalt()).decode()
                connection.execute("INSERT INTO users(email,password_hash,name,created_at) VALUES(?,?,?,?)",
                                   ('testreviewer@test.com', password_hash, 'Test Reviewer', '2026-09-08 12:00:00'))
            return steps, 'Account page is accessible for Test Reviewer (testreviewer@test.com).', mutation
        if task == 9:
            steps = [nav('/login'), input_step('/login', 'bob.c@test.com'), input_step('/login', 'TestPass123!')]
            steps += transition('/login', '/') + transition('/', '/account') + transition('/account', '/account/edit')
            steps += [input_step('/account/edit', 'Robert Clark')] + transition('/account/edit', '/account')
            return steps, 'The display name is now Robert Clark.', lambda c: c.execute(
                "UPDATE users SET name='Robert Clark' WHERE email='bob.c@test.com'")
        if task == 11:
            steps = [nav('/login'), input_step('/login', 'david.k@test.com'), input_step('/login', 'TestPass123!')]
            steps += transition('/login', '/') + transition('/', '/user/watchlist') + transition('/user/watchlist', '/user/watchlist')
            def mutation(connection):
                connection.execute("""DELETE FROM watchlist_items WHERE user_id=(SELECT id FROM users WHERE email='david.k@test.com')
                    AND movie_id=(SELECT id FROM movies WHERE title='Deadpool & Wolverine')""")
            return steps, "David's watchlist has 3 movies remaining.", mutation
        if task == 14:
            steps = [nav('/login'), input_step('/login', 'carol.d@test.com'), input_step('/login', 'TestPass123!')]
            steps += transition('/login', '/') + transition('/', '/account')
            steps += transition('/account', '/user/ratings') + transition('/user/ratings', '/user/watchlist')
            return steps, '| Movie | Personal score |\n| Oddity | 5/5 |', None
        if task == 18:
            search = '/search?search=Kevin+Feige'
            steps = [nav(search)]
            for slug in r18:
                steps += transition(search, '/m/' + slug) + [nav(search)]
            return steps, '| Movie | Audience score | Release Date (Streaming) |\n| Spider-Man: Brand New Day | 97% | Not listed |', None
        raise AssertionError(task)

    def test_all_positive(self):
        for task in TASKS:
            with self.subTest(task=task):
                steps, answer, mutation = self.positive(task)
                code, verdict = self.run_verifier(task, steps, answer, mutation)
                self.assertEqual(code, 0, verdict)

    def test_answer_only_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                _steps, answer, mutation = self.positive(task)
                code, verdict = self.run_verifier(task, [], answer, mutation)
                self.assertNotEqual(code, 0)
                self.assertFalse(verdict['pass'])

    def test_wrong_task_and_unfinished_fail(self):
        for task in TASKS:
            steps, answer, mutation = self.positive(task)
            self.assertNotEqual(self.run_verifier(task, steps, answer, mutation, 'RottenTomatoes--999')[0], 0)
            self.assertNotEqual(self.run_verifier(task, steps, answer, mutation, complete=False)[0], 0)

    def test_missing_or_tiny_screenshots_fail(self):
        steps, answer, mutation = self.positive(3)
        self.assertNotEqual(self.run_verifier(3, steps, answer, mutation, valid_screenshots=False)[0], 0)

    def test_external_origin_fails(self):
        steps, answer, mutation = self.positive(18)
        steps.append({'url': 'https://evil.invalid/m/spider_man_brand_new_day', 'action': 'navigate', 'params': {}})
        self.assertNotEqual(self.run_verifier(18, steps, answer, mutation)[0], 0)

    def test_read_only_database_mutation_fails(self):
        def mutate(connection):
            connection.execute("UPDATE movies SET audience_score=1 WHERE slug='spider_man_brand_new_day'")
        for task in (0, 3, 14, 18):
            steps, answer, _mutation = self.positive(task)
            self.assertNotEqual(self.run_verifier(task, steps, answer, mutate)[0], 0)

    def test_missing_candidate_visit_fails(self):
        for task in (0, 3, 18):
            steps, answer, mutation = self.positive(task)
            steps = steps[:-2]
            self.assertNotEqual(self.run_verifier(task, steps, answer, mutation)[0], 0)

    def test_wrong_or_extra_answers_fail(self):
        cases = {
            0: 'Bugonia | Nov 25, 2025 | Will Tracy',
            3: 'Shared producers: Emma Thomas, Charles Roven, Christopher Nolan\nOppenheimer | Jun 14, 2010\nThe Dark Knight | Nov 21, 2023',
            11: "David's watchlist has 4 movies remaining.",
            14: 'Oddity | 4/5\nThe Substance | 4/5',
            18: 'Spider-Man: Brand New Day | 97% | Aug 2026\nDeadpool & Wolverine | 94% | Oct 1, 2024',
        }
        for task, wrong in cases.items():
            steps, _answer, mutation = self.positive(task)
            self.assertNotEqual(self.run_verifier(task, steps, wrong, mutation)[0], 0, task)

    def test_extra_state_change_fails(self):
        for task in (8, 9, 11):
            steps, answer, mutation = self.positive(task)
            def changed(connection, base=mutation):
                base(connection)
                connection.execute("UPDATE movies SET title=title||' changed' WHERE id=1")
            self.assertNotEqual(self.run_verifier(task, steps, answer, changed)[0], 0, task)

    def test_missing_required_form_input_fails(self):
        for task in (8, 9, 11, 14):
            steps, answer, mutation = self.positive(task)
            steps = [step for step in steps if not (step['action'] == 'input' and step['params'].get('text') in
                     {'ReviewPass456!', 'Robert Clark', 'TestPass123!'})]
            self.assertNotEqual(self.run_verifier(task, steps, answer, mutation)[0], 0, task)


if __name__ == '__main__':
    unittest.main()
