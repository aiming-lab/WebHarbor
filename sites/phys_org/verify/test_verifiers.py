"""Contract tests for the Phys.org reviewer grading artifacts.

The suite exercises every verifier against a correct run, a no-op run, a
knowledge-shortcut run, and a wrong-answer run. Stateful tasks also receive a
correct self-report paired with an unchanged database and must reject it.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SITE_DIR.parents[1]
VERIFY_DIR = SITE_DIR / "verify"
SEED_DB = SITE_DIR / "instance_seed" / "phys_org.db"
TASKS_FILE = SITE_DIR / "tasks.jsonl"
BASE_URL = "http://localhost:40016"


@dataclass(frozen=True)
class Case:
    urls: tuple[str, ...]
    answer: str
    stateful: bool = False
    login_email: str | None = None


MAGNETIC = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"
MAGNETIC_TITLE = (
    "Magnetic checkerboard separates microparticles by size and sends them along different paths"
)
QUANTUM_CIRCUIT = "quantum-circuit-test-finally-exposes-what-has-been-warping-performance"
TINY_ENERGY = "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio"
TOP_TRENDING = "operational-test-demonstrates-100-electric-furnace-for-ceramic-frit-me"
PITCH_ARTICLE = "cracking-the-code-of-hypersonic-flight-a-decade-of-experiments-maps-tu"
BIOLOGY_ARTICLE = "swapping-molecular-building-blocks-one-by-one-reveals-how-receptors-te"
NANO_ARTICLE = "rna-built-droplets-create-customizable-organelles-inside-living-cells"
GRAPHENE_RECENT = "machine-learning-proves-that-graphene-is-hydrophobic"
GRAPHENE_EARLIER = "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement"
STAR_ARTICLE = "how-a-single-star-can-reshape-an-entire-galaxy"
QUANTUM_GEOMETRY = "quantum-geometry-applied-to-light-based-systems-expands-toolkit-for-to"
QUANTUM_GEOMETRY_TITLE = (
    "Quantum geometry applied to light-based systems expands toolkit for topological photonics"
)
JWST = "jwst-spots-two-early-black-holes-growing-far-faster-than-their-galaxie"
CO2_ARTICLE = "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids"
VALID_BCRYPT_HASH = "$2b$12$zV7HfiJmZTqLsgP30kyvJemamXfJyBv66FPuQOrwYXXsyQvrafvie"


CASES = {
    0: Case(("/category/physics", f"/article/{MAGNETIC}"), "Reviews of Modern Physics"),
    1: Case((f"/article/{QUANTUM_CIRCUIT}",), "Technion"),
    2: Case(("/search?q=quantum", f"/article/{TINY_ENERGY}"), "Nature Photonics"),
    3: Case(("/trending", f"/article/{TOP_TRENDING}"), "Elena Yamamoto"),
    4: Case(("/login", "/saved"), "4 Astronomy & Space saved articles",
            login_email="alice.j@test.com"),
    5: Case(("/login", "/saved", f"/article/{PITCH_ARTICLE}"), "Advanced Engineering Materials",
            login_email="bob.c@test.com"),
    6: Case(("/login", "/category/biology", f"/article/{BIOLOGY_ARTICLE}"),
            "Swapping molecular building blocks one by one reveals how receptors tell adrenaline from dopamine",
            stateful=True),
    7: Case(("/login", "/category/nanotechnology", f"/article/{NANO_ARTICLE}", "/saved"),
            "RNA-built droplets create customizable organelles inside living cells", stateful=True),
    8: Case(("/user/carol_d",), "3 comments"),
    9: Case(("/search?q=graphene+systems", f"/article/{GRAPHENE_RECENT}", f"/article/{GRAPHENE_EARLIER}"),
            "Hourglass nanographenes unlock strong, robust multi-spin entanglement was earlier — Nano Letters"),
    10: Case(("/category/astronomy?sort=popular", f"/article/{STAR_ARTICLE}"),
             "How a single star can reshape an entire galaxy"),
    11: Case((f"/article/{MAGNETIC}", f"/article/{QUANTUM_GEOMETRY}"),
             "Quantum geometry applied to light-based systems expands toolkit for topological photonics was published earlier"),
    12: Case((f"/article/{JWST}",),
             "Totally agree on the priors point — the new constraint is much tighter though."),
    13: Case(("/register", "/account"), "qa_explorer", stateful=True),
    14: Case(("/login", f"/article/{STAR_ARTICLE}", "/saved"),
             "5 remain; More Star Wars-like worlds emerge as 27 planet candidates with two suns discovered is first",
             stateful=True),
    15: Case(("/", f"/article/{MAGNETIC}", "/category/physics",
              "/category/physics?sort=popular"),
             "Magnetic checkerboard separates microparticles by size and sends them along different paths; Physics; rank 1"),
    16: Case(("/search?q=CO2+systems&category=chemistry", f"/article/{CO2_ARTICLE}"),
             "Journal of the American Chemical Society"),
    17: Case(("/login", "/account"), "exoplanet atmosphere",
             login_email="alice.j@test.com"),
}


def _trajectory(run_dir: Path, task_id: int, urls: tuple[str, ...], answer: str,
                login_email: str | None = None,
                login_email_overwrite: str | None = None,
                login_search_text: str | None = None,
                actions: tuple[str, ...] | None = None,
                base_url: str = BASE_URL) -> None:
    screenshots = run_dir / "screenshots"
    screenshots.mkdir(parents=True)
    steps = []
    for index, suffix in enumerate(urls):
        url = base_url + suffix
        steps.append({
            "step": index,
            "url": url,
            "title": "Phys.org Mirror",
            "action": (actions[index] if actions is not None else
                       ("done" if index == len(urls) - 1 else "click")),
            "params": {},
            "screenshot_before": f"step_{index:03d}.png",
            "screenshot_after": f"step_{index + 1:03d}.png",
        })
    if login_email:
        steps.insert(1, {
            "step": 1,
            "url": base_url + "/login",
            "title": "Phys.org Mirror",
            "action": "input",
            "params": {"index": 1, "text": login_email},
            "screenshot_before": "login_email_before.png",
            "screenshot_after": "login_email_after.png",
        })
        steps.insert(2, {
            "step": 2,
            "url": base_url + "/login",
            "title": "Phys.org Mirror",
            "action": "input",
            "params": {"index": 2, "text": "TestPass123!"},
            "screenshot_before": "login_password_before.png",
            "screenshot_after": "login_password_after.png",
        })
        if login_search_text is not None:
            steps.insert(1, {
                "step": 1,
                "url": base_url + "/login",
                "title": "Phys.org Mirror",
                "action": "input",
                "params": {"index": 0, "text": login_search_text},
                "screenshot_before": "header_search_before.png",
                "screenshot_after": "header_search_after.png",
            })
        if login_email_overwrite is not None:
            steps.insert(2, {
                "step": 2,
                "url": base_url + "/login",
                "title": "Phys.org Mirror",
                "action": "input",
                "params": {"index": 1, "text": login_email_overwrite},
                "screenshot_before": "login_email_overwrite_before.png",
                "screenshot_after": "login_email_overwrite_after.png",
            })
        for index, step in enumerate(steps):
            step["step"] = index
    payload = {
        "task": f"contract fixture for Phys.org--{task_id}",
        "task_id": f"Phys.org--{task_id}",
        "start_url": BASE_URL + "/",
        "steps": steps,
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "success_self_report": True,
        "verifier_path": f"sites/phys_org/verify/verify_{task_id}.py",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(payload), encoding="utf-8")


def _mutate_after_db(task_id: int, db_path: Path,
                     registration_password_hash: str = VALID_BCRYPT_HASH,
                     task_7_resave: bool = False) -> None:
    con = sqlite3.connect(db_path)
    try:
        if task_id == 6:
            con.execute(
                "INSERT INTO comments(text,user_id,article_id,parent_id,score,created_at) "
                "SELECT ?,u.id,a.id,NULL,0,'2026-08-15 12:00:00' "
                "FROM users u, articles a WHERE u.username='carol_d' AND a.slug=?",
                ("Reviewed for our weekly journal club", BIOLOGY_ARTICLE),
            )
        elif task_id == 7:
            if task_7_resave:
                con.execute(
                    "UPDATE saved_articles SET note=?,created_at='2026-08-15 12:00:00' "
                    "WHERE user_id=(SELECT id FROM users WHERE username='david_k') "
                    "AND article_id=(SELECT id FROM articles WHERE slug=?)",
                    ("Compare with our process", NANO_ARTICLE),
                )
            else:
                con.execute(
                    "INSERT INTO saved_articles(user_id,article_id,note,created_at) "
                    "SELECT u.id,a.id,?,'2026-08-15 12:00:00' "
                    "FROM users u, articles a WHERE u.username='david_k' AND a.slug=?",
                    ("Compare with our process", NANO_ARTICLE),
                )
        elif task_id == 13:
            con.execute(
                "INSERT INTO users(username,email,password_hash,full_name,bio,location,interests,created_at) "
                "VALUES('qa_explorer','qa_explorer@example.com',?,'QA Explorer','',"
                "'Berlin, Germany','','2026-08-15 12:00:00')",
                (registration_password_hash,),
            )
        elif task_id == 14:
            con.execute(
                "DELETE FROM saved_articles WHERE user_id=(SELECT id FROM users WHERE username='alice_j') "
                "AND article_id=(SELECT id FROM articles WHERE slug=?)",
                (STAR_ARTICLE,),
            )
        elif task_id == 17:
            con.execute(
                "INSERT INTO search_history(user_id,query,created_at) "
                "SELECT id,'verifier tampering probe','2026-08-15 12:00:00' "
                "FROM users WHERE username='alice_j'"
            )
        con.commit()
    finally:
        con.close()


class VerifierContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phys-org-verifier-test-"))
        self.initial_db = self.temp_dir / "initial.db"
        shutil.copy2(SEED_DB, self.initial_db)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _run(self, task_id: int, urls: tuple[str, ...], answer: str,
             *, mutate_state: bool = False,
             login_email: str | None = None,
             login_email_overwrite: str | None = None,
             login_search_text: str | None = None,
             registration_password_hash: str = VALID_BCRYPT_HASH,
             task_7_resave: bool = False,
             actions: tuple[str, ...] | None = None,
             base_url: str = BASE_URL) -> subprocess.CompletedProcess[str]:
        run_dir = self.temp_dir / f"run-{task_id}-{len(list(self.temp_dir.glob('run-*')))}"
        run_dir.mkdir()
        _trajectory(run_dir, task_id, urls, answer, login_email,
                    login_email_overwrite, login_search_text, actions, base_url)
        after_db = run_dir / "after.db"
        shutil.copy2(self.initial_db, after_db)
        if mutate_state:
            _mutate_after_db(task_id, after_db, registration_password_hash, task_7_resave)
        verifier = VERIFY_DIR / f"verify_{task_id}.py"
        return subprocess.run(
            [sys.executable, str(verifier), "--run_dir", str(run_dir),
             "--initial_db", str(self.initial_db), "--after_db", str(after_db),
             "--no_llm", "True"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def assert_verdict(self, result: subprocess.CompletedProcess[str], expected: bool) -> None:
        self.assertEqual(result.returncode, 0 if expected else 1,
                         msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        verdict = json.loads(result.stdout)
        self.assertEqual(verdict["pass"], expected, verdict)
        self.assertTrue(verdict["evidence"], verdict)

    def test_task_metadata_declares_all_grading_artifacts(self) -> None:
        rows = [json.loads(line) for line in TASKS_FILE.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 18)
        self.assertEqual([row["id"] for row in rows], [f"Phys.org--{i}" for i in range(18)])
        for index, row in enumerate(rows):
            with self.subTest(task=index):
                self.assertEqual(row.get("verifier_path"),
                                 f"sites/phys_org/verify/verify_{index}.py")
                self.assertIn("FACT CHECKPOINTS", row.get("judge_rubric", ""))
                self.assertNotIn("answer", row)
        self.assertNotIn("count shown next to the search term", rows[9]["ques"])
        self.assertIn("Popular", rows[15]["ques"])
        self.assertIn("password of your choice", rows[13]["ques"])
        self.assertNotIn("BenchmarkPass2026", rows[13]["ques"])
        self.assertIn("graphene systems", rows[9]["ques"])
        self.assertIn("CO2 systems", rows[16]["ques"])

    def test_all_verifiers_reject_no_op(self) -> None:
        for task_id in range(18):
            with self.subTest(task=task_id):
                result = self._run(task_id, ("/",), "")
                self.assert_verdict(result, False)

    def test_all_verifiers_accept_correct_run(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer,
                                   mutate_state=case.stateful,
                                   login_email=case.login_email)
                self.assert_verdict(result, True)

    def test_login_tasks_reject_wrong_account(self) -> None:
        for task_id in (4, 5, 17):
            case = CASES[task_id]
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer,
                                   login_email="wrong.user@example.com")
                self.assert_verdict(result, False)

    def test_login_tasks_reject_overwritten_expected_email(self) -> None:
        for task_id in (4, 5, 17):
            case = CASES[task_id]
            with self.subTest(task=task_id):
                result = self._run(
                    task_id, case.urls, case.answer,
                    login_email=case.login_email,
                    login_email_overwrite="wrong.user@example.com",
                )
                self.assert_verdict(result, False)

    def test_login_tasks_reject_expected_email_typed_into_search(self) -> None:
        for task_id in (4, 5, 17):
            case = CASES[task_id]
            with self.subTest(task=task_id):
                result = self._run(
                    task_id, case.urls, case.answer,
                    login_email="wrong.user@example.com",
                    login_search_text=case.login_email,
                )
                self.assert_verdict(result, False)

    def test_registration_rejects_missing_password_hash(self) -> None:
        case = CASES[13]
        result = self._run(13, case.urls, case.answer, mutate_state=True,
                           registration_password_hash="")
        self.assert_verdict(result, False)

    def test_save_task_rejects_resaving_an_initially_saved_article(self) -> None:
        con = sqlite3.connect(self.initial_db)
        try:
            con.execute(
                "INSERT INTO saved_articles(user_id,article_id,note,created_at) "
                "SELECT u.id,a.id,'Existing note','2026-08-14 12:00:00' "
                "FROM users u, articles a WHERE u.username='david_k' AND a.slug=?",
                (NANO_ARTICLE,),
            )
            con.commit()
        finally:
            con.close()
        case = CASES[7]
        result = self._run(7, case.urls, case.answer, mutate_state=True,
                           task_7_resave=True)
        self.assert_verdict(result, False)

    def test_task_11_accepts_direct_winner_title(self) -> None:
        result = self._run(11, CASES[11].urls, QUANTUM_GEOMETRY_TITLE)
        self.assert_verdict(result, True)

    def test_task_11_direct_title_answer_must_be_unambiguous(self) -> None:
        answers = [
            MAGNETIC_TITLE,
            f"{QUANTUM_GEOMETRY_TITLE}; {MAGNETIC_TITLE}",
        ]
        for answer in answers:
            with self.subTest(answer=answer):
                result = self._run(11, CASES[11].urls, answer)
                self.assert_verdict(result, False)

    def test_all_verifiers_reject_knowledge_shortcut(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, ("/",), case.answer,
                                   mutate_state=case.stateful)
                self.assert_verdict(result, False)

    def test_all_verifiers_reject_wrong_answer(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, "incorrect answer",
                                   mutate_state=case.stateful,
                                   login_email=case.login_email)
                self.assert_verdict(result, False)

    def test_all_verifiers_reject_negated_correct_answer(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, f"Not {case.answer}",
                                   mutate_state=case.stateful,
                                   login_email=case.login_email)
                self.assert_verdict(result, False)

    def test_negation_scope_stops_at_sentence_boundary(self) -> None:
        case = CASES[0]
        answer = "Not visible. Reviews of Modern Physics"
        result = self._run(0, case.urls, answer)
        self.assert_verdict(result, True)

    def test_answer_corrections_use_the_final_claim(self) -> None:
        case = CASES[0]
        accepted = [
            "Not Reviews of Modern Physics? Correction: Reviews of Modern Physics.",
            "No, Reviews of Modern Physics is the source journal.",
            "I did not stop at search and found Reviews of Modern Physics.",
        ]
        rejected = [
            "It is not in any reasonable sense actually Reviews of Modern Physics.",
            "Reviews of Modern Physics, but not Reviews of Modern Physics.",
            "Reviews of Modern Physics is not the source journal.",
            "Reviews of Modern Physics is definitely not the source journal.",
            "Reviews of Modern Physics? No, that is wrong.",
            "Reviews of Modern Physics — definitely not the source.",
            "Reviews of Modern Physics, however, is not the source.",
            "Reviews of Modern Physics; no, that is wrong.",
        ]
        for answer in accepted:
            with self.subTest(answer=answer):
                self.assert_verdict(self._run(0, case.urls, answer), True)
        for answer in rejected:
            with self.subTest(answer=answer):
                self.assert_verdict(self._run(0, case.urls, answer), False)

    def test_task_15_rejects_direct_navigation_between_checkpoints(self) -> None:
        case = CASES[15]
        result = self._run(
            15, case.urls, case.answer,
            actions=("navigate", "navigate", "navigate", "done"),
        )
        self.assert_verdict(result, False)

    def test_all_verifiers_reject_wrong_host_navigation(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer,
                                   mutate_state=case.stateful,
                                   login_email=case.login_email,
                                   base_url="https://example.com")
                self.assert_verdict(result, False)

    def test_all_verifiers_reject_navigation_outside_start_origin(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer,
                                   mutate_state=case.stateful,
                                   login_email=case.login_email,
                                   base_url="http://localhost:40015")
                self.assert_verdict(result, False)

    def test_stateful_verifiers_reject_unchanged_db(self) -> None:
        for task_id, case in CASES.items():
            if not case.stateful:
                continue
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer, mutate_state=False)
                self.assert_verdict(result, False)

    def test_comparison_verifiers_reject_reversed_claim(self) -> None:
        reversed_answers = {
            9: "Hourglass nanographenes unlock strong, robust multi-spin entanglement was "
               "published later; its journal is Nano Letters.",
            11: "Quantum geometry applied to light-based systems expands toolkit for "
                "topological photonics was published later.",
        }
        for task_id, answer in reversed_answers.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, CASES[task_id].urls, answer)
                self.assert_verdict(result, False)

    def test_comparison_relation_is_bound_to_the_expected_title(self) -> None:
        task_11_answers = {
            False: (
                f"{QUANTUM_GEOMETRY_TITLE} was later; "
                f"{MAGNETIC_TITLE} was earlier."
            ),
            True: (
                f"{QUANTUM_GEOMETRY_TITLE} was earlier; "
                f"{MAGNETIC_TITLE} was later."
            ),
        }
        for expected, answer in task_11_answers.items():
            with self.subTest(task=11, expected=expected):
                self.assert_verdict(
                    self._run(11, CASES[11].urls, answer), expected
                )
        task_9_wrong = (
            "Hourglass nanographenes unlock strong, robust multi-spin entanglement "
            "was later and Machine learning proves that graphene is hydrophobic "
            "was earlier; Nano Letters."
        )
        self.assert_verdict(self._run(9, CASES[9].urls, task_9_wrong), False)

    def test_comparison_understands_pair_direction_and_pronouns(self) -> None:
        task_11_answers = {
            False: (
                f"{MAGNETIC_TITLE} was published earlier than "
                f"{QUANTUM_GEOMETRY_TITLE}."
            ),
            True: (
                f"{MAGNETIC_TITLE} was published later than "
                f"{QUANTUM_GEOMETRY_TITLE}."
            ),
        }
        for expected, answer in task_11_answers.items():
            with self.subTest(kind="than", expected=expected):
                self.assert_verdict(
                    self._run(11, CASES[11].urls, answer), expected
                )
        accepted = [
            f"{QUANTUM_GEOMETRY_TITLE}, not {MAGNETIC_TITLE}, was published earlier.",
            f"Between {QUANTUM_GEOMETRY_TITLE} and {MAGNETIC_TITLE}, "
            "the former was published earlier.",
        ]
        for answer in accepted:
            with self.subTest(kind="reference", answer=answer):
                self.assert_verdict(self._run(11, CASES[11].urls, answer), True)

    def test_number_answer_rejects_direct_post_value_denial(self) -> None:
        answer = "4 is definitely not the count."
        self.assert_verdict(self._run(4, CASES[4].urls, answer,
                                      login_email=CASES[4].login_email), False)

    def test_comparison_correction_uses_final_relation(self) -> None:
        answer = (
            "It was not later. Correction: "
            f"{QUANTUM_GEOMETRY_TITLE} was published earlier."
        )
        result = self._run(11, CASES[11].urls, answer)
        self.assert_verdict(result, True)

    def test_multihop_task_rejects_out_of_order_navigation(self) -> None:
        case = CASES[15]
        out_of_order = (
            "/category/physics?sort=popular",
            f"/article/{MAGNETIC}",
            "/",
        )
        result = self._run(15, out_of_order, case.answer)
        self.assert_verdict(result, False)

    def test_recent_search_verifier_rejects_history_mutation(self) -> None:
        case = CASES[17]
        result = self._run(17, case.urls, case.answer, mutate_state=True)
        self.assert_verdict(result, False)


if __name__ == "__main__":
    unittest.main()
