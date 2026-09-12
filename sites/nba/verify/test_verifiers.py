#!/usr/bin/env python3
"""Positive and adversarial regression tests for every NBA verifier."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib as verifier


TASKS = list(range(20))

POSITIVE = {
    0: (["/players?position=G&team=mavericks", "/players/luka-doncic"], "Luka Doncic — PPG 33.9, RPG 9.2, APG 9.8."),
    1: (["/games"], "Detroit Pistons vs Cleveland Cavaliers — Now TV; San Antonio Spurs vs Minnesota Timberwolves — Viu TV."),
    2: (["/games"], "Detroit Pistons vs Cleveland Cavaliers; Donovan Mitchell has the highest leader mark at 26.6 PPG."),
    3: (["/schedule?season_type=Playoffs"], "Cleveland Cavaliers vs New York Knicks — Madison Square Garden, New York, NY — Game 1."),
    4: (["/standings", "/teams/thunder"], "Oklahoma City Thunder — Paycom Center; head coach Mark Daigneault."),
    5: (["/stats/players?stat=bpg"], "Victor Wembanyama 3.6 BPG; Anthony Davis and Chet Holmgren tied for second at 2.3 BPG; gap 1.3 BPG."),
    6: (["/stats/teams?sort=point_diff"], "Boston Celtics — 64 wins, 18 losses, 120.6 PPG, 109.2 OPPG, +11.4."),
    7: (["/teams", "/teams/clippers"], "LA Clippers — Tyronn Lue — 51-31."),
    8: (["/teams/thunder", "/teams/thunder/roster", "/players/chet-holmgren"], "Chet Holmgren — C-F; 7-1; 208 lb; Gonzaga; USA; 2.3 BPG."),
    9: (["/draft", "/news/mock-draft-board-shifts-after-combine-measurements"], "The article discusses handling pressure and defending multiple positions."),
    10: (["/draft"], "First round June 23, 2026; second round June 24, 2026."),
    11: (["/fantasy"], "Tyrese Haliburton has more assists: 10.9 AST versus Luka Doncic at 9.8 AST."),
    12: (["/stats"], "Points — Joel Embiid; Total Assists — Tyrese Haliburton."),
    13: (["/search?q=spacing", "/news/bucks-focus-on-half-court-spacing"], "Antetokounmpo rim pressure and Lillard range."),
    14: (["/watch"], "Lakers-Warriors condensed game — Los Angeles Lakers and Golden State Warriors."),
    15: (["/tickets"], "Oklahoma City Thunder at Dallas Mavericks — American Airlines Center — $155.00."),
    16: (["/store?category=T-Shirts", "/store/la-clippers-intuit-dome-opening-tee"], "LA Clippers Intuit Dome Opening Tee — LA Clippers — red — $32.99. Features: arena launch graphic; unisex fit; soft cotton."),
    17: (["/store?category=Hoodies", "/store/dallas-mavericks-statement-hoodie"], "Dallas Mavericks Statement Hoodie — $74.99. Fleece lining; front pouch pocket; screen-printed team mark."),
    18: (["/login", "/store?category=Jerseys", "/store/los-angeles-lakers-icon-swingman-jersey", "/cart", "/checkout"], "Pre-order total: $259.78."),
    19: (["/teams", "/standings", "/login", "/account/edit", "/account"], "Favorite team updated to Dallas Mavericks; payment ending 9090."),
}

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8


def copy_seed(root: Path) -> tuple[Path, Path]:
    initial = root / "initial.db"
    after = root / "after.db"
    shutil.copy2(SITE_DIR / "instance_seed" / "nba.db", initial)
    shutil.copy2(initial, after)
    return initial, after


def prepare_state(task: int, initial: Path, after: Path) -> None:
    if task == 18:
        for database in (initial, after):
            with sqlite3.connect(database) as connection:
                connection.execute("DELETE FROM cart_items")
                connection.commit()
        with sqlite3.connect(after) as connection:
            user_id = connection.execute("SELECT id FROM users WHERE email='alice.j@test.com'").fetchone()[0]
            product_id = connection.execute("SELECT id FROM products WHERE slug='los-angeles-lakers-icon-swingman-jersey'").fetchone()[0]
            connection.execute("INSERT INTO cart_items(user_id,product_id,quantity,size,added_at) VALUES(?,?,?,?,?)", (user_id, product_id, 2, "XL", "2026-05-15 12:00:00"))
            connection.commit()
    elif task == 19:
        with sqlite3.connect(after) as connection:
            connection.execute("UPDATE users SET favorite_team_slug='mavericks', payment_last4='9090' WHERE email='alice.j@test.com'")
            connection.commit()


def make_run(root: Path, task: int, paths: list[str], answer: str, *, task_id: str | None = None, foreign: bool = False) -> Path:
    run = root / "run"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    origin = "https://foreign.example" if foreign else "http://127.0.0.1:53431"
    steps = []
    for index, path in enumerate(paths):
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        steps.append({"step": index, "url": origin + path, "action": "click", "action_result": {"success": True}, "screenshot_after": shot})
    final_shot = f"step_{len(paths):03d}.png"
    (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(paths), "url": origin + paths[-1], "action": "done", "action_result": {"success": True}, "screenshot_after": final_shot})
    trajectory = {
        "task_id": task_id or f"NBA--{task}",
        "task": "fixture",
        "start_url": origin + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "steps": steps,
    }
    (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def execute(task: int, *, answer: str | None = None, paths: list[str] | None = None, task_id: str | None = None, foreign: bool = False, mutate=None):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        initial, after = copy_seed(root)
        prepare_state(task, initial, after)
        if mutate:
            with sqlite3.connect(after) as connection:
                mutate(connection)
                connection.commit()
        good_paths, good_answer = POSITIVE[task]
        run = make_run(root, task, paths if paths is not None else good_paths, answer if answer is not None else good_answer, task_id=task_id, foreign=foreign)
        return verifier.grade(task, run, initial, after)


class VerifierTests(unittest.TestCase):
    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                self.assertTrue(execute(task)["pass"], execute(task))

    def test_correct_answer_without_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                self.assertFalse(execute(task, paths=["/"])["pass"])

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                self.assertFalse(execute(task, answer="The requested result is unavailable.")["pass"])

    def test_expected_queries_allow_unrelated_parameters(self):
        paths, answer = POSITIVE[0]
        self.assertTrue(execute(0, paths=[paths[0] + "&name=", paths[1] + "?ref=stats"], answer=answer)["pass"])
        paths, answer = POSITIVE[13]
        self.assertTrue(execute(13, paths=[paths[0] + "&source=header", paths[1] + "?ref=search"], answer=answer)["pass"])

    def test_wrong_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                self.assertFalse(execute(task, task_id="NBA--999")["pass"])

    def test_foreign_origin_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                self.assertFalse(execute(task, foreign=True)["pass"])

    def test_read_only_tasks_reject_database_writes(self):
        for task in range(18):
            with self.subTest(task=task):
                result = execute(task, mutate=lambda db: db.execute("UPDATE teams SET coach=coach||' changed' WHERE id=1"))
                self.assertFalse(result["pass"])

    def test_task_18_rejects_noop_and_seeded_extras(self):
        good_paths, good_answer = POSITIVE[18]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial, after = copy_seed(root)
            for database in (initial, after):
                with sqlite3.connect(database) as connection:
                    connection.execute("DELETE FROM cart_items")
                    connection.commit()
            run = make_run(root, 18, good_paths, good_answer)
            self.assertFalse(verifier.grade(18, run, initial, after)["pass"])
        seeded = execute(18, mutate=lambda db: db.execute("INSERT INTO cart_items(user_id,product_id,quantity,size,added_at) SELECT u.id,p.id,1,'L','2026-05-15 12:00:00' FROM users u,products p WHERE u.email='alice.j@test.com' AND p.slug='boston-celtics-association-edition-jersey'"))
        self.assertFalse(seeded["pass"])

    def test_task_19_rejects_partial_or_unrelated_profile_change(self):
        self.assertFalse(execute(19, mutate=lambda db: db.execute("UPDATE users SET payment_last4='1111' WHERE email='bob.c@test.com'"))["pass"])
        good_paths, good_answer = POSITIVE[19]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial, after = copy_seed(root)
            run = make_run(root, 19, good_paths, good_answer)
            self.assertFalse(verifier.grade(19, run, initial, after)["pass"])


class ContractTests(unittest.TestCase):
    def test_task_file_has_one_verifier_and_rubric_per_task(self):
        rows = [json.loads(line) for line in (SITE_DIR / "tasks.jsonl").read_text().splitlines() if line]
        self.assertEqual([row["id"] for row in rows], [f"NBA--{index}" for index in TASKS])
        self.assertEqual(len({row["verifier_path"] for row in rows}), 20)
        for row in rows:
            path = Path(row["verifier_path"])
            repo_path = SITE_DIR.parent.parent / path
            site_path = SITE_DIR / path.relative_to("sites/nba")
            self.assertTrue(repo_path.is_file() or site_path.is_file(), row["verifier_path"])
        self.assertTrue(all(row["judge_rubric"].startswith("FACT CHECKPOINTS:") for row in rows))
        self.assertNotIn("answer", {key for row in rows for key in row})

    def test_repaired_task_wording(self):
        rows = {row["id"]: row for row in map(json.loads, (SITE_DIR / "tasks.jsonl").read_text().splitlines())}
        self.assertIn("all players tied for second", rows["NBA--5"]["ques"])
        self.assertIn("all listed product features", rows["NBA--16"]["ques"])
        for task_id in ("NBA--18", "NBA--19"):
            self.assertIn("alice.j@test.com", rows[task_id]["ques"])
            self.assertIn("TestPass123!", rows[task_id]["ques"])

    def test_search_form_is_usable_and_does_not_leak_article_answer(self):
        sys.path.insert(0, str(SITE_DIR))
        import app as nba_app
        response = nba_app.app.test_client().get("/search?q=spacing")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="q"', html)
        self.assertIn('value="spacing"', html)
        self.assertNotIn("Antetokounmpo rim pressure", html)
        self.assertNotIn("Lillard range", html)

    def test_homepage_teaser_does_not_leak_article_answer(self):
        sys.path.insert(0, str(SITE_DIR))
        import app as nba_app

        home = nba_app.app.test_client().get("/").get_data(as_text=True)
        detail = nba_app.app.test_client().get(
            "/news/bucks-focus-on-half-court-spacing"
        ).get_data(as_text=True)

        self.assertNotIn("Antetokounmpo rim pressure", home)
        self.assertNotIn("Lillard range", home)
        self.assertIn("Antetokounmpo rim pressure", detail)
        self.assertIn("Lillard range", detail)

    def test_seeded_benchmark_carts_are_empty(self):
        with sqlite3.connect(SITE_DIR / "instance_seed" / "nba.db") as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cart_items").fetchone()[0], 0)

    def test_regular_season_snapshot_is_labeled_2023_24(self):
        templates = "\n".join((SITE_DIR / "templates" / name).read_text() for name in ("standings.html", "fantasy.html"))
        self.assertNotIn("2025-26 Player Stats", templates)
        self.assertNotIn("2025-26 Regular Season Standings", templates)
        self.assertIn("2023-24", templates)
        with sqlite3.connect(SITE_DIR / "instance_seed" / "nba.db") as connection:
            self.assertEqual(
                connection.execute("SELECT wins,losses FROM teams WHERE slug='thunder'").fetchone(),
                (57, 25),
            )

        sys.path.insert(0, str(SITE_DIR))
        import app as nba_app
        html = nba_app.app.test_client().get("/standings").get_data(as_text=True)
        self.assertRegex(html, r"<span>1</span><img[^>]+> Oklahoma City Thunder")

    def test_homepage_hero_text_matches_its_media(self):
        with sqlite3.connect(SITE_DIR / "instance_seed" / "nba.db") as connection:
            title, image = connection.execute(
                "SELECT title,image FROM articles ORDER BY published_at DESC LIMIT 1"
            ).fetchone()
        self.assertNotIn("Celtics", title if "harris-levert" in image else "")

    def test_more_stats_displays_the_metric_used_for_each_ranking(self):
        sys.path.insert(0, str(SITE_DIR))
        import app as nba_app

        html = nba_app.app.test_client().get("/stats").get_data(as_text=True)
        more_stats = html.split('<section class="rail-card more-stats">', 1)[1].split("</section>", 1)[0]

        self.assertRegex(
            more_stats,
            r"(?s)Total Assists.*?Tyrese Haliburton\s*<b>11</b>.*?Luka Doncic\s*<b>10</b>",
        )

    def test_narrow_navigation_contains_overflow(self):
        css = (SITE_DIR / "static" / "css" / "nba.css").read_text()
        responsive = css[css.index("@media (max-width: 1080px)"):]
        self.assertRegex(responsive, r"\.primary-nav nav\s*\{[^}]*overflow-x:\s*auto")


if __name__ == "__main__":
    unittest.main()
