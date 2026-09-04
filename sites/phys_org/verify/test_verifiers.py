"""Positive and adversarial tests for every Phys.org verifier."""

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

import bcrypt

VERIFY_DIR = Path(__file__).resolve().parent
SEED_DB = VERIFY_DIR.parent / "instance_seed" / "phys_org.db"
BASE_URL = "http://localhost:40017"
PASSWORD = "TestPass123!"

SLUGS = {
    "magnetic": "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-",
    "quantum_circuit": "quantum-circuit-test-finally-exposes-what-has-been-warping-performance",
    "tiny_energy": "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio",
    "hypersonic": "cracking-the-code-of-hypersonic-flight-a-decade-of-experiments-maps-tu",
    "exosomes": "engineered-exosomes-reverse-sleep-deprivation-brain-damage-in-mice",
    "hydrophobic": "machine-learning-proves-that-graphene-is-hydrophobic",
    "hourglass": "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement",
    "star": "how-a-single-star-can-reshape-an-entire-galaxy",
    "geometry": "quantum-geometry-applied-to-light-based-systems-expands-toolkit-for-to",
    "jwst": "jwst-spots-two-early-black-holes-growing-far-faster-than-their-galaxie",
    "vibrations": "good-vibrations-for-quantum-communications-engineers-couple-single-pho",
    "polyionic": "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids",
}
TITLES = {
    "magnetic": "Magnetic checkerboard separates microparticles by size and sends them along different paths",
    "exosomes": "Engineered exosomes reverse sleep deprivation brain damage in mice",
    "hydrophobic": "Machine learning proves that graphene is hydrophobic",
    "hourglass": "Hourglass nanographenes unlock strong, robust multi-spin entanglement",
    "vibrations": "Good vibrations for quantum communications: Engineers couple single phonon to single atomic spin",
    "top_saved": "More Star Wars-like worlds emerge as 27 planet candidates with two suns discovered",
}
REPLY = "Totally agree on the priors point — the new constraint is much tighter though."
COMMENT = "Reviewed for our weekly journal club"
NOTE = "Compare with our process"


def url(path: str) -> str:
    return BASE_URL + path


def navigate(path: str) -> dict:
    return {"url": url(path), "action": "navigate", "params": {}}


def fill(path: str, selector: str, text: str) -> dict:
    return {"url": url(path), "action": "fill", "params": {"css": selector, "text": text}}


def click(path: str, destination: str) -> dict:
    return {"url": url(path), "action": "click", "params": {}, "url_after": url(destination)}


def login_steps(email: str) -> list[dict]:
    return [
        navigate("/login"),
        fill("/login", "input[name=email]", email),
        fill("/login", "input[name=password]", PASSWORD),
        click("/login", "/"),
        navigate("/"),
    ]


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        connection = sqlite3.connect(SEED_DB)
        try:
            row = connection.execute(
                "SELECT a.slug,a.title FROM articles a JOIN categories c ON c.id=a.category_id WHERE c.slug='biology' ORDER BY a.published_at DESC LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
        cls.biology_slug, cls.biology_title = row

    def run_verifier(self, task: int, steps: list[dict], answer: str,
                     mutate=None, task_id: str | None = None) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory(prefix=f"phys-verifier-{task}-") as temp_dir:
            temp = Path(temp_dir)
            initial = temp / "initial.db"
            after = temp / "after.db"
            shutil.copy2(SEED_DB, initial)
            shutil.copy2(SEED_DB, after)
            if mutate is not None:
                connection = sqlite3.connect(after)
                try:
                    mutate(connection)
                    connection.commit()
                finally:
                    connection.close()
            run_dir = temp / "run"
            run_dir.mkdir()
            trajectory = {
                "task_id": task_id if task_id is not None else f"Phys.org--{task}",
                "start_url": url("/"),
                "steps": steps,
                "final_answer": answer,
            }
            (run_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(VERIFY_DIR / f"verify_{task}.py"),
                 "--run_dir", str(run_dir), "--initial_db", str(initial),
                 "--after_db", str(after), "--no_llm", "true"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            try:
                verdict = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                self.fail(f"Verifier {task} produced invalid JSON. stdout={result.stdout!r} stderr={result.stderr!r}: {error}")
            return result.returncode, verdict

    def mutate_comment(self, connection: sqlite3.Connection) -> None:
        user_id = connection.execute("SELECT id FROM users WHERE username='carol_d'").fetchone()[0]
        article_id = connection.execute("SELECT id FROM articles WHERE slug=?", (self.biology_slug,)).fetchone()[0]
        connection.execute(
            "INSERT INTO comments(text,user_id,article_id,parent_id,score,created_at) VALUES(?,?,?,?,?,?)",
            (COMMENT, user_id, article_id, None, 0, "2026-05-14 12:00:00"),
        )

    @staticmethod
    def mutate_save(connection: sqlite3.Connection) -> None:
        user_id = connection.execute("SELECT id FROM users WHERE username='david_k'").fetchone()[0]
        article_id = connection.execute("SELECT id FROM articles WHERE slug=?", (SLUGS["exosomes"],)).fetchone()[0]
        connection.execute(
            "INSERT INTO saved_articles(user_id,article_id,note,created_at) VALUES(?,?,?,?)",
            (user_id, article_id, NOTE, "2026-05-14 12:00:00"),
        )

    @staticmethod
    def mutate_register(connection: sqlite3.Connection) -> None:
        password_hash = bcrypt.hashpw(b"VerifierPass123!", bcrypt.gensalt()).decode()
        connection.execute(
            "INSERT INTO users(username,email,password_hash,full_name,bio,location,interests,created_at) VALUES(?,?,?,?,?,?,?,?)",
            ("qa_explorer", "qa_explorer@example.com", password_hash, "QA Explorer", "", "Berlin, Germany", "", "2026-05-14 12:00:00"),
        )

    @staticmethod
    def mutate_remove(connection: sqlite3.Connection) -> None:
        connection.execute(
            "DELETE FROM saved_articles WHERE user_id=(SELECT id FROM users WHERE username='alice_j') AND article_id=(SELECT id FROM articles WHERE slug=?)",
            (SLUGS["star"],),
        )

    def positive_case(self, task: int):
        def article(key):
            return f"/article/{SLUGS[key]}"

        def transition(source, destination):
            return [click(source, destination), navigate(destination)]

        graphene_search = f"/search?q={quote_plus('graphene spin')}"
        capture_search = f"/search?q={quote_plus('capture materials')}&category=chemistry"
        cases = {
            0: ([navigate("/category/physics")] + transition("/category/physics", article("magnetic")), "Physical Review Letters", None),
            1: ([navigate("/category/physics")] + transition("/category/physics", article("quantum_circuit")), "Massachusetts Institute of Technology", None),
            2: ([navigate("/search?q=quantum")] + transition("/search?q=quantum", article("tiny_energy")), "Nature Electronics", None),
            3: ([navigate("/trending")] + transition("/trending", article("magnetic")), "University of Tübingen", None),
            4: (login_steps("alice.j@test.com") + transition("/", "/saved"), "There are 4 Astronomy & Space saved articles.", None),
            5: (login_steps("bob.c@test.com") + transition("/", "/saved") + transition("/saved", article("hypersonic")), "The publication venue is the AIAA SCITECH 2026 Forum.", None),
            6: (login_steps("carol.d@test.com") + [navigate("/category/biology")] + transition("/category/biology", f"/article/{self.biology_slug}") + [
                fill(f"/article/{self.biology_slug}", "textarea[name=text]", COMMENT),
                click(f"/article/{self.biology_slug}", f"/article/{self.biology_slug}"),
                navigate(f"/article/{self.biology_slug}"),
            ], self.biology_title, self.mutate_comment),
            7: (login_steps("david.k@test.com") + [navigate("/category/nanotechnology")] + transition("/category/nanotechnology", article("exosomes")) + [
                fill(article("exosomes"), "input[name=note]", NOTE),
                click(article("exosomes"), article("exosomes")),
                navigate(article("exosomes")),
                navigate("/saved"),
            ], "The article subsection is Bio & Medicine.", self.mutate_save),
            8: ([navigate("/users")] + transition("/users", "/user/carol_d"), "Carol has 3 public comments.", None),
            9: ([navigate(graphene_search)] + transition(graphene_search, article("hydrophobic")) + [navigate(graphene_search)] + transition(graphene_search, article("hourglass")), f"{TITLES['hourglass']} was published earlier; its journal is Nature Synthesis.", None),
            10: ([navigate("/category/astronomy?sort=popular")] + transition("/category/astronomy?sort=popular", article("star")), "The article is rank #3; Provided by Leiden University.", None),
            11: ([navigate(article("magnetic")), navigate(article("geometry"))], "Quantum geometry applied to light-based systems expands toolkit for topological photonics was published earlier than " + TITLES["magnetic"] + ".", None),
            12: ([navigate("/category/astronomy?sort=popular")] + transition("/category/astronomy?sort=popular", article("jwst")), REPLY, None),
            13: ([
                navigate("/register"),
                fill("/register", "input[name=username]", "qa_explorer"),
                fill("/register", "input[name=email]", "qa_explorer@example.com"),
                fill("/register", "input[name=full_name]", "QA Explorer"),
                fill("/register", "input[name=password]", "VerifierPass123!"),
                click("/register", "/"),
                navigate("/"),
                navigate("/account"),
                fill("/account", "input[name=location]", "Berlin, Germany"),
                click("/account", "/account"),
                navigate("/account"),
            ], "The username in the header is qa_explorer.", self.mutate_register),
            14: (login_steps("alice.j@test.com") + transition("/", "/saved") + transition("/saved", article("star")) + [
                click(article("star"), article("star")),
                navigate(article("star")),
                navigate("/saved"),
            ], f"5 saved articles remain; the most recent item at the top is {TITLES['top_saved']}.", self.mutate_remove),
            15: ([
                click("/", article("vibrations")),
                navigate(article("vibrations")),
                click(article("vibrations"), "/category/physics"),
                navigate("/category/physics"),
                click("/category/physics", "/category/physics?sort=popular"),
                navigate("/category/physics?sort=popular"),
            ], f"{TITLES['vibrations']} is in Physics and is rank #2 in Popular.", None),
            16: ([navigate(capture_search)] + transition(capture_search, article("polyionic")), "Reaction Chemistry & Engineering", None),
            17: (login_steps("alice.j@test.com") + transition("/", "/account"), "The second query is dark matter halo.", None),
        }
        return cases[task]

    def test_all_positive_cases_pass(self) -> None:
        for task in range(18):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                returncode, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertEqual(0, returncode, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_wrong_task_id_fails_every_verifier(self) -> None:
        for task in range(18):
            with self.subTest(task=task):
                steps, answer, mutate = self.positive_case(task)
                returncode, verdict = self.run_verifier(task, steps, answer, mutate, task_id="Phys.org--999")
                self.assertNotEqual(0, returncode)
                self.assertFalse(verdict["pass"])
                self.assertEqual("task_id_matches", verdict["reason"])

    def test_empty_answer_fails_every_verifier(self) -> None:
        for task in range(18):
            with self.subTest(task=task):
                steps, _, mutate = self.positive_case(task)
                returncode, verdict = self.run_verifier(task, steps, "", mutate)
                self.assertNotEqual(0, returncode)
                self.assertFalse(verdict["pass"])
                self.assertEqual("final_answer_nonempty", verdict["reason"])

    def test_answer_only_trajectory_fails_every_verifier(self) -> None:
        for task in range(18):
            with self.subTest(task=task):
                _, answer, mutate = self.positive_case(task)
                returncode, verdict = self.run_verifier(task, [], answer, mutate)
                self.assertNotEqual(0, returncode)
                self.assertFalse(verdict["pass"])

    def test_external_origin_spoof_fails(self) -> None:
        spoofed = [
            {"url": "https://evil.example/category/physics", "action": "navigate", "params": {}},
            {"url": f"https://evil.example/article/{SLUGS['magnetic']}", "action": "navigate", "params": {}},
        ]
        returncode, verdict = self.run_verifier(0, spoofed, "Physical Review Letters")
        self.assertNotEqual(0, returncode)
        self.assertFalse(verdict["pass"])

    def test_reversed_order_fails(self) -> None:
        steps = [navigate(f"/article/{SLUGS['tiny_energy']}"), navigate("/search?q=quantum")]
        returncode, verdict = self.run_verifier(2, steps, "Nature Electronics")
        self.assertNotEqual(0, returncode)
        self.assertEqual("ordered_search_to_article", verdict["reason"])

    def test_ordered_url_visits_without_a_result_click_fail(self) -> None:
        steps = [navigate("/category/physics"), navigate(f"/article/{SLUGS['magnetic']}")]
        returncode, verdict = self.run_verifier(0, steps, "Physical Review Letters")
        self.assertNotEqual(0, returncode)
        self.assertEqual("clicked_target_from_physics", verdict["reason"])

    def test_unsubmitted_login_fails(self) -> None:
        steps = [navigate("/login"), fill("/login", "input[name=email]", "alice.j@test.com"), fill("/login", "input[name=password]", PASSWORD), navigate("/saved")]
        returncode, verdict = self.run_verifier(4, steps, "There are 4 Astronomy & Space saved articles.")
        self.assertNotEqual(0, returncode)
        self.assertEqual("login_as_alice", verdict["reason"])

    def test_overwritten_login_email_fails(self) -> None:
        steps = login_steps("alice.j@test.com")
        steps.insert(3, fill("/login", "input[name=email]", "bob.c@test.com"))
        steps.append(navigate("/saved"))
        returncode, verdict = self.run_verifier(4, steps, "There are 4 Astronomy & Space saved articles.")
        self.assertNotEqual(0, returncode)
        self.assertEqual("login_as_alice", verdict["reason"])

    def test_numbers_must_be_bound_to_requested_labels(self) -> None:
        steps4, _, _ = self.positive_case(4)
        returncode4, _ = self.run_verifier(4, steps4, "Physics has 4 saved articles; Astronomy & Space has 3.")
        self.assertNotEqual(0, returncode4)
        steps8, _, _ = self.positive_case(8)
        returncode8, _ = self.run_verifier(8, steps8, "Carol has 3 saved articles and 2 comments.")
        self.assertNotEqual(0, returncode8)

    def test_written_counts_and_ordinal_ranks_pass(self) -> None:
        steps4, _, _ = self.positive_case(4)
        returncode4, verdict4 = self.run_verifier(4, steps4, "There are four Astronomy & Space saved articles.")
        self.assertEqual(0, returncode4, verdict4)
        steps8, _, _ = self.positive_case(8)
        returncode8, verdict8 = self.run_verifier(8, steps8, "Carol has three public comments.")
        self.assertEqual(0, returncode8, verdict8)
        steps10, _, _ = self.positive_case(10)
        returncode10, verdict10 = self.run_verifier(10, steps10, "The article ranks third and is provided by Leiden University.")
        self.assertEqual(0, returncode10, verdict10)
        steps15, _, _ = self.positive_case(15)
        answer15 = f"{TITLES['vibrations']} is in Physics and ranks second in Popular."
        returncode15, verdict15 = self.run_verifier(15, steps15, answer15)
        self.assertEqual(0, returncode15, verdict15)

    def test_comparison_journal_must_be_bound_to_winner(self) -> None:
        steps, _, _ = self.positive_case(9)
        bad = f"{TITLES['hourglass']} was earlier; its journal is Advanced Materials. Nature Synthesis belongs to the other article."
        returncode, verdict = self.run_verifier(9, steps, bad)
        self.assertNotEqual(0, returncode)
        self.assertFalse(verdict["pass"])

    def test_full_reply_accepts_dash_equivalence_and_rejects_partial(self) -> None:
        steps, _, _ = self.positive_case(12)
        returncode, verdict = self.run_verifier(12, steps, f'bob_c replied, "{REPLY.replace(" — ", " - ")}"')
        self.assertEqual(0, returncode, verdict)
        returncode, verdict = self.run_verifier(12, steps, "the new constraint is much tighter though")
        self.assertNotEqual(0, returncode)
        self.assertFalse(verdict["pass"])

    def test_state_verifiers_reject_unrelated_extra_changes(self) -> None:
        cases = (6, 7, 13, 14, 17)
        for task in cases:
            with self.subTest(task=task):
                steps, answer, base_mutate = self.positive_case(task)
                def mutate(connection, base_mutate=base_mutate, task=task):
                    if base_mutate:
                        base_mutate(connection)
                    connection.execute("UPDATE users SET bio='unrelated change' WHERE username='bob_c'")
                    if task == 6:
                        connection.execute("UPDATE comments SET score=score+1 WHERE id=(SELECT min(id) FROM comments)")
                    elif task in {7, 14}:
                        connection.execute("UPDATE saved_articles SET note='unrelated change' WHERE id=(SELECT min(id) FROM saved_articles)")
                    elif task == 13:
                        connection.execute("UPDATE users SET bio='unrelated change' WHERE username='alice_j'")
                    elif task == 17:
                        connection.execute("UPDATE search_history SET query='unrelated change' WHERE id=(SELECT min(id) FROM search_history)")
                returncode, verdict = self.run_verifier(task, steps, answer, mutate)
                self.assertNotEqual(0, returncode)
                self.assertFalse(verdict["pass"])

    def test_task_13_accepts_an_arbitrary_new_identity(self) -> None:
        steps, _, _ = self.positive_case(13)
        replacements = {
            "qa_explorer": "science_rover",
            "qa_explorer@example.com": "science_rover@example.com",
            "QA Explorer": "Science Rover",
        }
        for step in steps:
            text = (step.get("params") or {}).get("text")
            if text in replacements:
                step["params"]["text"] = replacements[text]

        def mutate(connection):
            password_hash = bcrypt.hashpw(b"VerifierPass123!", bcrypt.gensalt()).decode()
            connection.execute(
                "INSERT INTO users(username,email,password_hash,full_name,bio,location,interests,created_at) VALUES(?,?,?,?,?,?,?,?)",
                ("science_rover", "science_rover@example.com", password_hash, "Science Rover", "", "Berlin, Germany", "", "2026-05-14 12:00:00"),
            )

        returncode, verdict = self.run_verifier(
            13, steps, "The username in the header is science_rover.", mutate
        )
        self.assertEqual(0, returncode, verdict)

    def test_task_7_rejects_a_different_new_nanotechnology_save(self) -> None:
        steps, answer, _ = self.positive_case(7)
        def mutate(connection):
            user_id = connection.execute("SELECT id FROM users WHERE username='david_k'").fetchone()[0]
            article_id = connection.execute(
                "SELECT a.id FROM articles a JOIN categories c ON c.id=a.category_id WHERE c.slug='nanotechnology' AND a.slug<>? AND NOT EXISTS (SELECT 1 FROM saved_articles s WHERE s.article_id=a.id AND s.user_id=?) LIMIT 1",
                (SLUGS["exosomes"], user_id),
            ).fetchone()[0]
            connection.execute("INSERT INTO saved_articles(user_id,article_id,note,created_at) VALUES(?,?,?,?)", (user_id, article_id, NOTE, "2026-05-14 12:00:00"))
        returncode, verdict = self.run_verifier(7, steps, answer, mutate)
        self.assertNotEqual(0, returncode)
        self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()
