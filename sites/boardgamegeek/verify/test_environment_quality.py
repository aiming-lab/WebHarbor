"""Regression checks for the BoardGameGeek review fixes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]
SEED_DB = SITE_DIR / "instance_seed" / "boardgamegeek.db"


def _copy_runtime(destination: Path, *, include_templates: bool = False) -> None:
    shutil.copy2(SITE_DIR / "app.py", destination / "app.py")
    shutil.copy2(SITE_DIR / "seed_data.py", destination / "seed_data.py")
    instance = destination / "instance"
    instance.mkdir()
    shutil.copy2(SEED_DB, instance / "boardgamegeek.db")
    if include_templates:
        shutil.copytree(SITE_DIR / "templates", destination / "templates")


class EnvironmentQualityTests(unittest.TestCase):
    def test_task_ids_and_urls_match_registered_port(self) -> None:
        rows = [
            json.loads(line)
            for line in (SITE_DIR / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(21, len(rows))
        for number, row in enumerate(rows):
            with self.subTest(task=number):
                self.assertEqual(f"BoardGameGeek--{number}", row["id"])
                self.assertEqual("http://localhost:40020/", row["web"])

    def test_registration_template_displays_validation_errors(self) -> None:
        template = (SITE_DIR / "templates" / "register.html").read_text(encoding="utf-8")
        for field in ("username", "email", "password"):
            with self.subTest(field=field):
                self.assertIn(f"form.{field}.errors", template)

    def test_task_action_controls_are_exposed_in_the_ui(self) -> None:
        item_template = (SITE_DIR / "templates" / "item.html").read_text(encoding="utf-8")
        user_template = (SITE_DIR / "templates" / "user.html").read_text(encoding="utf-8")
        app_source = (SITE_DIR / "app.py").read_text(encoding="utf-8")
        self.assertIn("url_for('collection_remove'", item_template)
        self.assertIn("Remove from collection", item_template)
        self.assertIn("geeklists_count", user_template)
        self.assertIn("geeklists_count=", app_source)

    def test_direct_start_uses_one_flask_sqlalchemy_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            _copy_runtime(runtime)
            before = hashlib.sha256((runtime / "instance" / "boardgamegeek.db").read_bytes()).hexdigest()
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            env = os.environ.copy()
            env["PORT"] = str(port)
            process = subprocess.Popen(
                [sys.executable, "app.py"],
                cwd=runtime,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/_health", timeout=1
                        ) as response:
                            self.assertEqual(200, response.status)
                        break
                    except Exception:
                        if process.poll() is not None:
                            break
                        time.sleep(0.1)
                else:
                    self.fail("BoardGameGeek app did not become healthy")
            finally:
                process.terminate()
                output, _ = process.communicate(timeout=10)
            after = hashlib.sha256((runtime / "instance" / "boardgamegeek.db").read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertNotIn("SQLAlchemy instance", output)
            self.assertNotIn("[boardgamegeek] seed error", output)

    def test_new_rating_updates_global_aggregate_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            _copy_runtime(runtime)
            script = """
import json
import app as module

module.app.config['WTF_CSRF_ENABLED'] = False
with module.app.app_context():
    game = module.Game.query.filter_by(name='Brass: Birmingham').one()
    user = module.User.query.filter_by(username='bob_c').one()
    before = {'average': game.avg_rating, 'count': game.num_ratings}
    game_id = game.bgg_id
    user_id = user.id

with module.app.test_client() as client:
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    response = client.post(
        f'/rate/{game_id}',
        data={'value': '9.5', 'review': 'A focused and rewarding economic game.'},
    )

with module.app.app_context():
    game = module.Game.query.filter_by(name='Brass: Birmingham').one()
    rating = module.Rating.query.filter_by(user_id=user_id, game_id=game.id).one()
    print(json.dumps({
        'status': response.status_code,
        'before': before,
        'after': {'average': game.avg_rating, 'count': game.num_ratings},
        'rating': rating.value,
        'review': rating.review_html,
    }))
"""
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=runtime,
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout.splitlines()[-1])
            before = result["before"]
            expected_average = (
                before["average"] * before["count"] + 9.5
            ) / (before["count"] + 1)
            self.assertEqual(302, result["status"])
            self.assertEqual(9.5, result["rating"])
            self.assertIn("focused and rewarding", result["review"])
            self.assertEqual(before["count"] + 1, result["after"]["count"])
            self.assertAlmostEqual(expected_average, result["after"]["average"], places=10)


if __name__ == "__main__":
    unittest.main()
