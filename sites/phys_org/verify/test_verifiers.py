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


CASES = {
    0: Case(("/category/physics", f"/article/{MAGNETIC}"), "Reviews of Modern Physics"),
    1: Case((f"/article/{QUANTUM_CIRCUIT}",), "Technion"),
    2: Case(("/search?q=quantum", f"/article/{TINY_ENERGY}"), "Nature Photonics"),
    3: Case(("/trending", f"/article/{TOP_TRENDING}"), "Elena Yamamoto"),
    4: Case(("/login", "/saved"), "4 Astronomy & Space saved articles"),
    5: Case(("/login", "/saved", f"/article/{PITCH_ARTICLE}"), "Advanced Engineering Materials"),
    6: Case(("/login", "/category/biology", f"/article/{BIOLOGY_ARTICLE}"),
            "Swapping molecular building blocks one by one reveals how receptors tell adrenaline from dopamine",
            stateful=True),
    7: Case(("/login", "/category/nanotechnology", f"/article/{NANO_ARTICLE}", "/saved"),
            "RNA-built droplets create customizable organelles inside living cells", stateful=True),
    8: Case(("/user/carol_d",), "3 comments"),
    9: Case(("/search?q=graphene", f"/article/{GRAPHENE_RECENT}", f"/article/{GRAPHENE_EARLIER}"),
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
    15: Case(("/", f"/article/{MAGNETIC}", "/category/physics?sort=popular"),
             "Magnetic checkerboard separates microparticles by size and sends them along different paths; Physics; rank 1"),
    16: Case(("/search?q=CO2&category=chemistry", f"/article/{CO2_ARTICLE}"),
             "Journal of the American Chemical Society"),
    17: Case(("/login", "/account"), "exoplanet atmosphere"),
}


def _trajectory(run_dir: Path, task_id: int, urls: tuple[str, ...], answer: str) -> None:
    screenshots = run_dir / "screenshots"
    screenshots.mkdir(parents=True)
    steps = []
    for index, suffix in enumerate(urls):
        url = BASE_URL + suffix
        steps.append({
            "step": index,
            "url": url,
            "title": "Phys.org Mirror",
            "action": "done" if index == len(urls) - 1 else "click",
            "params": {},
            "screenshot_before": f"step_{index:03d}.png",
            "screenshot_after": f"step_{index + 1:03d}.png",
        })
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


def _mutate_after_db(task_id: int, db_path: Path) -> None:
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
            con.execute(
                "INSERT INTO saved_articles(user_id,article_id,note,created_at) "
                "SELECT u.id,a.id,?,'2026-08-15 12:00:00' "
                "FROM users u, articles a WHERE u.username='david_k' AND a.slug=?",
                ("Compare with our process", NANO_ARTICLE),
            )
        elif task_id == 13:
            con.execute(
                "INSERT INTO users(username,email,password_hash,full_name,bio,location,interests,created_at) "
                "VALUES('qa_explorer','qa_explorer@example.com','test-hash','QA Explorer','',"
                "'Berlin, Germany','','2026-08-15 12:00:00')"
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
             *, mutate_state: bool = False) -> subprocess.CompletedProcess[str]:
        run_dir = self.temp_dir / f"run-{task_id}-{len(list(self.temp_dir.glob('run-*')))}"
        run_dir.mkdir()
        _trajectory(run_dir, task_id, urls, answer)
        after_db = run_dir / "after.db"
        shutil.copy2(SEED_DB, after_db)
        if mutate_state:
            _mutate_after_db(task_id, after_db)
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

    def test_all_verifiers_reject_no_op(self) -> None:
        for task_id in range(18):
            with self.subTest(task=task_id):
                result = self._run(task_id, ("/",), "")
                self.assert_verdict(result, False)

    def test_all_verifiers_accept_correct_run(self) -> None:
        for task_id, case in CASES.items():
            with self.subTest(task=task_id):
                result = self._run(task_id, case.urls, case.answer,
                                   mutate_state=case.stateful)
                self.assert_verdict(result, True)

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
                                   mutate_state=case.stateful)
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

    def test_recent_search_verifier_rejects_history_mutation(self) -> None:
        case = CASES[17]
        result = self._run(17, case.urls, case.answer, mutate_state=True)
        self.assert_verdict(result, False)


if __name__ == "__main__":
    unittest.main()
