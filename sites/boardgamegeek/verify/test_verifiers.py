"""Positive, adversarial, and legal-alternative tests for all BGG verifiers."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote_plus


VERIFY_DIR = Path(__file__).resolve().parent
SEED_DB = VERIFY_DIR.parent / "instance_seed" / "boardgamegeek.db"
PASSWORD = "TestPass123!"


def next_id(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {table}").fetchone()[0])


def game_id(connection: sqlite3.Connection, name: str) -> tuple[int, int]:
    return tuple(connection.execute("SELECT id,bgg_id FROM games WHERE name=?", (name,)).fetchone())


def user_id(connection: sqlite3.Connection, username: str) -> int:
    return int(connection.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0])


def mutation(task: int):
    if task == 5:
        def rate(connection: sqlite3.Connection) -> None:
            gid, _ = game_id(connection, "Brass: Birmingham")
            uid = user_id(connection, "bob_c")
            average, count = connection.execute(
                "SELECT avg_rating,num_ratings FROM games WHERE id=?", (gid,)
            ).fetchone()
            connection.execute(
                "INSERT INTO ratings(id,user_id,game_id,value,review_html,created_at,num_thumbs) VALUES(?,?,?,?,?,?,?)",
                (
                    next_id(connection, "ratings"), uid, gid, 9.5,
                    "<p>A focused and rewarding economic game.</p>",
                    "2026-05-26 12:00:00.000000", 0,
                ),
            )
            connection.execute(
                "UPDATE games SET avg_rating=?,num_ratings=? WHERE id=?",
                (((average * count) + 9.5) / (count + 1), count + 1, gid),
            )
        return rate
    if task == 6:
        def wishlist(connection: sqlite3.Connection) -> None:
            gid, _ = game_id(connection, "Android: Netrunner")
            uid = user_id(connection, "carol_d")
            connection.execute(
                """
                INSERT INTO collections(
                    id,user_id,game_id,own,prevowned,want_to_play,want_to_buy,
                    wishlist,wishlist_priority,preordered,for_trade,comment,
                    acquired_on,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    next_id(connection, "collections"), uid, gid, 0, 0, 0, 0,
                    1, 1, 0, 0, "", "", "2026-05-26 12:00:00.000000",
                ),
            )
        return wishlist
    if task == 9:
        def create_list(connection: sqlite3.Connection) -> None:
            connection.execute(
                "INSERT INTO geeklists(id,title,description_html,author_id,created_at,num_thumbs,num_items) VALUES(?,?,?,?,?,?,?)",
                (
                    next_id(connection, "geeklists"), "My COIN Series Picks",
                    "<p>Light, deep, and historical.</p>", user_id(connection, "david_k"),
                    "2026-05-26 12:00:00.000000", 0, 0,
                ),
            )
        return create_list
    if task == 13:
        def remove_recent(connection: sqlite3.Connection) -> None:
            uid = user_id(connection, "alice_j")
            row = connection.execute(
                "SELECT id FROM collections WHERE user_id=? AND own=1 ORDER BY updated_at DESC LIMIT 1",
                (uid,),
            ).fetchone()
            connection.execute("DELETE FROM collections WHERE id=?", (row[0],))
        return remove_recent
    if task == 15:
        def reply(connection: sqlite3.Connection) -> None:
            uid = user_id(connection, "bob_c")
            thread = connection.execute(
                """
                SELECT t.id,t.forum_id FROM threads t JOIN forums f ON f.id=t.forum_id
                WHERE f.title='Recommendations' AND t.is_pinned=0 AND t.is_locked=0
                  AND (lower(t.subject) LIKE '%2 player%' OR lower(t.subject) LIKE '%two-player%')
                ORDER BY t.id LIMIT 1
                """
            ).fetchone()
            connection.execute(
                "INSERT INTO posts(id,thread_id,author_id,body_html,created_at,edited_at,thumbs) VALUES(?,?,?,?,?,?,?)",
                (
                    next_id(connection, "posts"), thread[0], uid,
                    "<p>Try 7 Wonders Duel as an alternative.</p>",
                    "2026-05-26 12:00:00.000000", None, 0,
                ),
            )
            connection.execute(
                "UPDATE threads SET num_posts=num_posts+1,last_post_at=? WHERE id=?",
                ("2026-05-26 12:00:00.000000", thread[0]),
            )
            connection.execute(
                "UPDATE forums SET num_posts=num_posts+1 WHERE id=?", (thread[1],)
            )
        return reply
    return None


def fixture(task: int, *, alternate: bool = False) -> tuple[list[dict], str, object | None]:
    base = "http://127.0.0.1:40021" if alternate else "http://localhost:40021"

    def url(path: str) -> str:
        return base + path

    def nav(path: str) -> dict:
        return {"url": url(path), "action": "navigate", "params": {}}

    def click(path: str, destination: str) -> dict:
        return {"url": url(path), "url_after": url(destination), "action": "click", "params": {}}

    def enter(path: str, text: str) -> dict:
        return {"url": url(path), "action": "input", "params": {"text": text}}

    def game(bgg_id: int, slug: str) -> str:
        return f"/boardgame/{bgg_id}" if alternate else f"/boardgame/{bgg_id}/{slug}"

    def subpage(bgg_id: int, slug: str, page: str) -> str:
        return f"/boardgame/{bgg_id}/{page}" if alternate else f"/boardgame/{bgg_id}/{slug}/{page}"

    def login(username: str) -> list[dict]:
        return [
            nav("/login"), enter("/login", username), enter("/login", PASSWORD),
            click("/login", f"/user/{username}"), nav(f"/user/{username}"),
        ]

    mutate = mutation(task)
    if task == 0:
        paths = [nav("/browse/boardgame"), click("/browse/boardgame", game(224517, "brass-birmingham")), nav(game(224517, "brass-birmingham"))]
        answer = "Brass: Birmingham is #1; its designers are Gavan Brown, Matt Tolman, and Martin Wallace."
    elif task == 1:
        search = "/search?q=Gloomhaven&type=boardgame"
        paths = [nav(search), click(search, game(174430, "gloomhaven")), nav(game(174430, "gloomhaven"))]
        answer = "Gloomhaven has average rating 8.5389, weight 3.91917, and 67,165 voters."
    elif task == 2:
        paths = [nav("/browse/boardgame?sort=weight&dir=desc")]
        answer = "On Mars has the highest qualifying weight: 4.62606."
    elif task == 3:
        worker = "/boardgamemechanic/2082" if alternate else "/boardgamemechanic/2082/worker-placement"
        target = game(397598, "dune-imperium-uprising")
        paths = [nav("/boardgamemechanic"), click("/boardgamemechanic", worker), nav(worker), click(worker, target), nav(target)]
        answer = "Dune: Imperium – Uprising is highest-ranked; its designer is Paul Dennen."
    elif task == 4:
        paths = login("alice_j") + [nav("/collection/alice_j")]
        answer = "alice_j has 18 owned games in her collection."
    elif task == 5:
        target = game(224517, "brass-birmingham")
        paths = login("bob_c") + [nav(target), enter(target, "9.5"), enter(target, "A focused and rewarding economic game."), click(target, target), nav(target)]
        answer = "The 9.5 rating and one-sentence review were saved."
    elif task == 6:
        deck_a = "/boardgamemechanic/3004" if alternate else "/boardgamemechanic/3004/deck-construction"
        deck_b = "/boardgamemechanic/2664" if alternate else "/boardgamemechanic/2664/deck-bag-and-pool-building"
        target = game(124742, "android-netrunner")
        paths = login("carol_d") + [nav(deck_a), nav(deck_b), nav(target), enter(target, "Must have"), click(target, target), nav(target)]
        answer = "Android: Netrunner was added to carol_d's wishlist as Must have."
    elif task == 7:
        paths = [nav("/hot" if alternate else "/hotness")]
        answer = "The latest year is 2025; The Lord of the Rings: Fate of the Fellowship is the highest-ranked game from that year."
    elif task == 8:
        target = game(167355, "nemesis")
        paths = [nav("/geeklists"), click("/geeklists", "/geeklist/7"), nav("/geeklist/7"), click("/geeklist/7", target), nav(target)]
        answer = "The #7 entry is Nemesis, with a weight of 3.49."
    elif task == 9:
        new_id = 17
        paths = login("david_k") + [nav("/geeklist/new"), enter("/geeklist/new", "My COIN Series Picks"), enter("/geeklist/new", "Light, deep, and historical."), click("/geeklist/new", f"/geeklist/{new_id}"), nav(f"/geeklist/{new_id}")]
        answer = "My COIN Series Picks was created."
    elif task == 10:
        brass = game(224517, "brass-birmingham")
        ark = game(342942, "ark-nova")
        paths = [nav(brass), nav(ark)]
        answer = "Brass: Birmingham is heavier than Ark Nova (3.86 versus 3.80)."
    elif task == 11:
        index = "/boardgamepublisher?q=" + quote_plus("Z-Man Games")
        detail = "/boardgamepublisher/538" if alternate else "/boardgamepublisher/538/z-man-games"
        paths = [nav(index), click(index, detail), nav(detail)]
        answer = "Z-Man Games has 116 games listed in the catalog."
    elif task == 12:
        detail = "/boardgamemechanic/2001" if alternate else "/boardgamemechanic/2001/action-points"
        paths = [nav("/boardgamemechanic"), click("/boardgamemechanic", detail), nav(detail)]
        answer = "Pandemic Legacy: Season 1 is highest, at overall rank #3."
    elif task == 13:
        collection = "/collection/alice_j?status=own&sort=recent"
        target = game(284378, "kanban-ev")
        paths = login("alice_j") + [nav(collection), click(collection, target), nav(target), click(target, target), nav(target)]
        answer = "Kanban EV, the most recently updated entry, was removed."
    elif task == 14:
        target = game(266192, "wingspan")
        ratings = subpage(266192, "wingspan", "ratings") + "?sort=thumbs"
        paths = [nav(target), click(target, ratings), nav(ratings)]
        answer = "The top review is by ogzz with 23 thumbs."
    elif task == 15:
        target = "/thread/4004"
        paths = login("bob_c") + [nav("/forums"), nav("/forum/3"), nav(target), enter(target, "Try 7 Wonders Duel as an alternative."), click(target, target), nav(target)]
        answer = "Posted a reply suggesting 7 Wonders Duel."
    elif task == 16:
        paths = [nav("/geeklists"), click("/geeklists", "/geeklist/1"), nav("/geeklist/1")]
        answer = "The #1 entry is Pax Renaissance: 2nd Edition."
    elif task == 17:
        paths = login("david_k") + [nav("/plays/david_k")]
        answer = "david_k has logged plays for 7 distinct games."
    elif task == 18:
        index = "/boardgamedesigner?q=" + quote_plus("Vital Lacerda")
        detail = "/boardgamedesigner/12396?sort=average" if alternate else "/boardgamedesigner/12396/vital-lacerda?sort=average"
        paths = [nav(index), click(index, detail), nav(detail)]
        answer = "Speakeasy has Vital Lacerda's highest average rating."
    elif task == 19:
        search = "/search?q=mike&type=user"
        paths = [nav(search), click(search, "/user/EViLMiKE"), nav("/user/EViLMiKE")]
        answer = "The first match is EViLMiKE, with 0 GeekLists authored."
    elif task == 20:
        target = game(12333, "twilight-struggle")
        expansions = subpage(12333, "twilight-struggle", "expansions")
        paths = [nav(target), click(target, expansions), nav(expansions)]
        answer = "Twilight Struggle has 11 expansions listed."
    else:
        raise ValueError(task)
    return paths, answer, mutate


class VerifierTests(unittest.TestCase):
    maxDiff = None

    def run_verifier(
        self,
        task: int,
        steps: list[dict],
        answer: str,
        mutate=None,
        *,
        start_url: str | None = None,
    ) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory(prefix=f"bgg-verify-{task}-") as temp_dir:
            root = Path(temp_dir)
            initial = root / "initial.db"
            after = root / "after.db"
            run = root / "run"
            run.mkdir()
            shutil.copy2(SEED_DB, initial)
            shutil.copy2(SEED_DB, after)
            if mutate:
                connection = sqlite3.connect(after)
                try:
                    mutate(connection)
                    connection.commit()
                finally:
                    connection.close()
            origin = start_url or (
                "http://127.0.0.1:40021/"
                if steps and "127.0.0.1" in steps[0]["url"]
                else "http://localhost:40021/"
            )
            trajectory = {
                "task_id": f"BoardGameGeek--{task}",
                "start_url": origin,
                "steps": steps,
                "final_url": steps[-1].get("url_after", steps[-1].get("url")) if steps else origin,
                "final_answer": answer,
            }
            (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_DIR / f"verify_{task}.py"),
                    "--run_dir", str(run),
                    "--initial_db", str(initial),
                    "--after_db", str(after),
                    "--no_llm", "true",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            try:
                verdict = json.loads(result.stdout)
            except Exception as error:
                self.fail(f"task {task} emitted invalid JSON: {error}\nstdout={result.stdout}\nstderr={result.stderr}")
            return result.returncode, verdict

    def test_positive_trajectories_pass_every_verifier(self) -> None:
        for task in range(21):
            with self.subTest(task=task):
                steps, answer, mutate = fixture(task)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_legal_alternative_paths_pass_every_verifier(self) -> None:
        for task in range(21):
            with self.subTest(task=task):
                steps, answer, mutate = fixture(task, alternate=True)
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_close_but_wrong_results_fail_every_verifier(self) -> None:
        mutation_tasks = {5, 6, 9, 13, 15}
        for task in range(21):
            with self.subTest(task=task):
                steps, answer, mutate = fixture(task)
                if task in mutation_tasks:
                    mutate = None
                else:
                    answer = "I visited the requested pages but could not determine the answer."
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, code, verdict)
                self.assertFalse(verdict["pass"], verdict)

    def test_answer_or_state_without_navigation_fails_every_verifier(self) -> None:
        for task in range(21):
            with self.subTest(task=task):
                _steps, answer, mutate = fixture(task)
                code, verdict = self.run_verifier(task, [], answer, mutate)
                self.assertNotEqual(0, code, verdict)
                self.assertFalse(verdict["pass"], verdict)

    def test_prompt_permitted_browse_and_compare_paths_pass(self) -> None:
        variants = {}

        steps, answer, mutate = fixture(11)
        for step in steps:
            for key in ("url", "url_after"):
                if key in step:
                    step[key] = step[key].replace(
                        "/boardgamepublisher?q=Z-Man+Games", "/boardgamepublisher"
                    )
        variants[11] = (steps, answer, mutate)

        steps, answer, mutate = fixture(18)
        for step in steps:
            for key in ("url", "url_after"):
                if key in step:
                    step[key] = step[key].replace(
                        "/boardgamedesigner?q=Vital+Lacerda", "/boardgamedesigner"
                    ).replace("?sort=average", "")
        variants[18] = (steps, answer, mutate)

        for task, (steps, answer, mutate) in variants.items():
            with self.subTest(task=task):
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_keyboard_form_submission_passes_stateful_tasks(self) -> None:
        for task in (5, 6, 9, 13, 15):
            with self.subTest(task=task):
                steps, answer, mutate = fixture(task)
                for step in reversed(steps):
                    if step["action"] == "click":
                        step["action"] = "press"
                        step["params"] = {"key": "Enter"}
                        break
                code, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, code, verdict)
                self.assertTrue(verdict["pass"], verdict)


if __name__ == "__main__":
    unittest.main()
