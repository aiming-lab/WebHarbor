#!/usr/bin/env python3
"""Positive and adversarial regression tests for every Wolfram Alpha verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact /input computation query that renders the
intended seed record and the ground-truth answer the served mirror pages
yield (recorded during the reviewer's Playwright audit of the running
container -- reports/wolfram_alpha/audit/), and the adversarial cases prove
the verifiers reject no-op runs, recall shortcuts, wrong answers, foreign
task ids, broken run packages, and DB writes.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB --no_llm True
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because
the repository tracks no instance assets; set WH_CONTAINER to point at the
site's container when it is not the default wh-ver-wolfram_alpha.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
TASKS_FILE = SITE_DIR / "tasks.jsonl"
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://127.0.0.1:41011"
TASKS = list(range(46))

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8


def input_path(query: str) -> str:
    return "/input?" + urlencode({"i": query})


# task -> (canonical /input computation queries, model answer)
POSITIVE = {
    0: (["d/dx x^2 at 5.6"],
        "The derivative of x^2 is 2x; evaluated at x = 5.6 its value is 11.2."),
    1: (["pentagram"],
        "A constraint on the set of inequalities bounding the inner pentagonal "
        "region of the pentagram is: 2 a + 3 sqrt(5) x + 5 x >= "
        "sqrt(2 (5 + sqrt(5))) y (one of the half-plane clauses; the full system "
        "is a disjunction of 11 such clauses joined with and/or)."),
    2: (["3^71"],
        "3^71 = 7509466514979724803946715958257547; retained to 5 significant "
        "figures in scientific notation: 7.5095 × 10^33."),
    3: (["integral of x^2 cos(2x)"],
        "g(x) = (1/4) ((2x² − 1) sin(2x) + 2x cos(2x)) + C; equivalently "
        "(1/2)x² sin(2x) + (1/2)x cos(2x) − (1/4) sin(2x) + C."),
    4: (["Pack 24 circles in a circle"],
        "Densest known packing: inner-circle radius r ≈ 0.176939 R (75.14% "
        "filled); square packing: r ≈ 0.163961 R (64.52% filled); hexagonal: "
        "r ≈ 0.169724 R."),
    5: (["solution of y''(z) + sin(y(z)) = 0"],
        "y(z) = ±2 am((1/2) sqrt((c1+2) (z+c2)²) | 4/(c1+2)), where am(z|m) is "
        "the Jacobi amplitude function and c1, c2 are arbitrary constants."),
    6: (["Simplify x^5-20x^4+163x^3-676x^2+1424x-1209"],
        "Simplified to fewer items: (x − 4)^5 + 3 (x − 4)^3 + 7."),
    7: (["spring pendulum equilibrium=0.12m initial length=0.24m angle=80 mass=1kg k=120"],
        "After t = 6 s the final angle from vertical is ≈ −73.26° (= −1.279 rad) "
        "and the final spring length is ≈ 25.21 cm (= 0.2521 m)."),
    8: (["12 lbs of 4-cyanoindole to moles percentage C H N"],
        "12 lb = 5442.8 g → 38.29 mol; mass percent: C 76.04%, H 4.25%, "
        "N 19.71%."),
    9: (["Diablo Canyon 2 annual energy production 2010"],
        "Diablo Canyon 2's annual energy production in 2010 was 9752 GWh/yr "
        "(≈ 1.113 GW average power)."),
    10: (["geomagnetic field June 20 2023 Oslo"],
         "Predicted geomagnetic field in Oslo on June 20, 2023: total field "
         "F = 51.5 μT, declination +4.51° E, inclination (dip) +72.888°."),
    11: (["electrical resistivity of UNS A92024",
          "electrical resistivity of UNS G10800"],
         "At 20 °C: UNS A92024 (aluminum 2024) has electrical resistivity "
         "ρ ≈ 4.87 × 10⁻⁸ Ω·m; UNS G10800 (AISI 1080 steel) has "
         "ρ ≈ 1.80 × 10⁻⁷ Ω·m."),
    12: (["unicode 8900 to 8920"],
         "The character that looks like a snowflake is decimal 8902 (U+22C6, "
         "STAR OPERATOR): ⋆"),
    13: (["$10000 in 1980", "$10000 in 1970"],
         "$10,000 today is worth $2,514.25 in 1980 dollars and $1,184.54 in "
         "1970 dollars."),
    14: (["300g whopper vs baconator vs big mac"],
         "At a 300 g serving: Burger King Whopper 657 Cal, Wendy's Baconator "
         "902 Cal, McDonald's Big Mac 729 Cal."),
    15: (["blood relationship fraction father's mother's sister's son"],
         "Father's mother's sister's son is your first cousin once removed; "
         "the blood relationship fraction (coefficient of relationship) is "
         "1/32 = 3.125%."),
    16: (["weight loss 90 kg 40 yr 175 cm 1500 cal -17 kg"],
         "It will take 3 months 6 days (≈ 96 days) to lose 17 kg on the "
         "1500 Cal/day intake."),
    17: (["average price of movie ticket Providence 2023",
          "average price of movie ticket Nashville 2023",
          "average price of movie ticket Boise 2023"],
         "2023 average movie ticket prices: Providence, RI mean $14.37; "
         "Nashville, TN mean $13.30; Boise, ID mean $11.60."),
    18: (["Albert Einstein curve"],
         "The first Albert Einstein curve is a hand-drawn-style line silhouette "
         "of Einstein's face, plotted for t from 0 to 92π; its parametric "
         "equations are Fourier series x(t) = Σ a_n sin(b_n t + c_n), "
         "y(t) = Σ a_n' sin(b_n' t + c_n') with ~30+ terms."),
    19: (["time to sunburn SPF 5 Australia 11 am"],
         "Typical time to sunburn in Australia at 11:00 am with SPF 5, by "
         "Fitzpatrick skin type: I: 1 h 37 min; II: 2 h; III: 3 h; IV: 5 h; "
         "V and VI: sunburn unlikely."),
    20: (["3e^(2x) integral from 0 to 5"],
         "∫₀⁵ 3e^(2x) dx = (3/2)(e^10 − 1) ≈ 33038.47."),
    21: (["(1+0.1i)^8 + (1-0.2i)^8"],
         "(1+0.1i)^8 + (1−0.2i)^8 = 0.717183 − 0.425258 i (polar form "
         "0.833784 e^(−0.535225 i))."),
    22: (["area of regular hexagon side 7 cm"],
         "Area = (147√3)/2 cm² ≈ 127.306 cm² (equivalently 73.5√3 cm²)."),
    23: (["population growth rate Canada"],
         "Canada's population growth 2020–2023: mean 0.9886 %/yr, lowest "
         "0.7392 %/yr (2021), highest 1.231 %/yr (2023)."),
    24: (["y''(t) - 2y'(t) + 10y(t) = 0"],
         "General solution: y(t) = c₁ e^t sin(3t) + c₂ e^t cos(3t)."),
    25: (["projectile 30 m/s 45 degrees, t=3 s"],
         "The mirror's projectile results: horizontal distance traveled "
         "63.64 m, maximum height reached 15.91 m (g = 9.81 m/s²); from the "
         "equations pod, at t = 3 s the velocity is vx = 21.21 m/s, "
         "vy = −8.22 m/s."),
    26: (["15 kg sulfuric acid to moles percentage H S O composition"],
         "15 kg of sulfuric acid (H2SO4) is 153 mol (molar mass 98.079 g/mol); "
         "mass composition: H 2.1%, O 65.2%, S 32.7%."),
    27: (["thermal conductivity copper at 25 c",
          "thermal conductivity aluminum at 25 c"],
         "At 25 °C: copper 401.2 W/(m K); aluminum 236.9 W/(m K)."),
    28: (["unicode 9632 to 9650"],
         "The hollow parallelogram in the range is decimal 9649 (U+25B1, "
         "WHITE PARALLELOGRAM): ▱"),
    29: (["plot cat curve"],
         "The cat curve plot shows a Fourier-series silhouette of a cat traced "
         "parametrically over t in [0, 2π] (part of Wolfram|Alpha's "
         "animal-curves family)."),
    30: (["sunburn 1:00 pm SPF 1 Brasilia Brazil"],
         "In Brasília, Brazil at 1:00 pm with SPF 1, typical time to sunburn by "
         "skin type: I: 17 min; II: 22 min; III: 32 min; IV: 43 min; V: 1 h 1 min; "
         "VI: 3 h."),
    31: (["current temperature wind speed Chicago IL"],
         "Chicago, IL current weather: temperature 54 °F, wind 16 mph from SSW "
         "(partly cloudy, 59% humidity)."),
    32: (["prime numbers between 1000 and 1200"],
         "The primes between 1000 and 1200 (28 in total) are: 1009, 1013, 1019, "
         "1021, 1031, 1033, 1039, 1049, 1051, 1061, 1063, 1069, 1087, 1091, "
         "1093, 1097, 1103, 1109, 1117, 1123, 1129, 1151, 1153, 1163, 1171, "
         "1181, 1187, 1193."),
    33: (["Itaipu Dam"],
         "Itaipu Dam's annual power generation is 89.5 TWh (≈ 3.222 × 10¹⁷ J/yr)."),
    34: (["mass of Jupiter compared to Earth", "Jupiter rotation period"],
         "Jupiter's mass is 317.8 Earth masses (1.898 × 10²⁷ kg vs Earth's "
         "5.972 × 10²⁴ kg); the length of one day on Jupiter is 9.925 hours "
         "(9 h 55 min 30 s, sidereal)."),
    35: (["determinant of 6 by 6 Hilbert matrix"],
         "det(H₆) = 1/186313420339200000 ≈ 5.3673 × 10⁻¹⁸."),
    36: (["convergence of series sum 1/(n^3 + 1) from n=1 to infinity"],
         "The series Σ 1/(n³ + 1) converges; its sum is ≈ 0.686503."),
    37: (["days between February 12 2024 and August 9 2050"],
         "There are 9675 days between February 12, 2024 and August 9, 2050."),
    38: (["arc length of 2x^3 - 3x^2 + 4x - 5 from 0 to 3"],
         "The arc length of y = 2x³ − 3x² + 4x − 5 from x = 0 to x = 3 is "
         "L ≈ 39.249927."),
    39: (["rotate x^2 + 3y^2 = 4 by 33 degrees"],
         "The rotated ellipse: x²(sin(2π/15) − 2) + 2xy cos(2π/15) + 4 = "
         "y²(2 + sin(2π/15)), numerically ≈ 1.5888 x² + 1.8272 xy + "
         "2.4112 y² = 4."),
    40: (["fat burned 28 year old woman 172 cm 70 kg running 30 min 6 min/mile pace"],
         "Fat burned ≈ 0.17 lb (energy expenditure 600 Cal, oxygen consumption "
         "31.7 gallons, 16 METs)."),
    41: (["heart rate reserve 50 year old man 60 bpm"],
         "The Karvonen heart rate reserve for a 50-year-old man with a resting "
         "heart rate of 60 bpm is 110 bpm."),
    42: (["image 100.2 in by 123.5 in at 72 ppi"],
         "The raw memory of the 24-bit true-colour 100.2\" × 123.5\" picture at "
         "72 ppi is 192 MB ≈ 192.45 MB (decimal) ≈ 183.54 MiB (binary) — "
         "64.15 megapixels at 7214 × 8892 px."),
    43: (["polyominoes order 6 2-sided combinations 2 rows"],
         "There are 35 two-sided hexominoes (order 6, with chirality); of them "
         "13 shapes fit in 2 rows total (1×6: 1, 2×5: 6, 2×4: 3, 2×3: 3)."),
    44: (["g' + cos(g) = 0 with g(0) = 1"],
         "g(t) = −arcsin(coth(t − arccoth(sin 1))); in implicit form "
         "log|sec g + tan g| = −t + 1.22617 (the constant pinned by g(0) = 1)."),
    45: (["climbing stairs 175cm 85kg 40 year old 2500 steps 40 steps/min"],
         "Metabolic properties: energy expenditure ≈ 597 Cal, fat burned "
         "≈ 0.1706 lb, oxygen consumption ≈ 31.54 gal, metabolic equivalent "
         "6.4 MET, per-step energy ≈ 0.24 Cal/step."),
}


def make_run(root: Path, task: int, queries, answer, *, task_id=None,
             origin=ORIGIN, drop_trajectory=False, break_screenshot=False,
             verbatim_first=None, step_origin=None):
    """Build a run package whose steps visit /input?i=<query> for each query.

    With verbatim_first set, the first submitted query is the task's verbatim
    wording (which the mirror rejects) before the canonical queries, matching
    the real agent behavior. With step_origin set, the visited /input URLs
    use that origin while start_url keeps `origin` (the off-site navigation
    adversarial)."""
    nav_origin = step_origin or origin
    run = root / f"run_{task}"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    paths = ["/"]
    if verbatim_first is not None:
        paths.append(input_path(verbatim_first))
    paths += [input_path(q) for q in queries]
    steps = []
    for index, path in enumerate(paths):
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        steps.append({"step": index, "url": nav_origin + path, "action": "click",
                      "action_result": {"success": True}, "screenshot_after": shot})
    final_shot = f"step_{len(paths):03d}.png"
    if not break_screenshot:
        (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(paths), "url": nav_origin + paths[-1],
                  "action": "done", "action_result": {"success": True},
                  "screenshot_after": final_shot})
    trajectory = {
        "task_id": task_id or f"Wolfram Alpha--{task}",
        "task": "fixture",
        "start_url": origin + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "steps": steps,
    }
    if not drop_trajectory:
        (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def run_verifier(task: int, run_dir: Path, initial_db: Path, after_db: Path):
    script = VERIFY_DIR / f"verify_{task}.py"
    r = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial_db), "--after_db", str(after_db),
         "--container", "unused-container", "--no_llm", "True"],
        capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    verdict["returncode"] = r.returncode
    return verdict


SEED_DB = None


def seed_db(tmp: Path) -> Path:
    global SEED_DB
    if SEED_DB is None:
        SEED_DB = verify_lib.fetch_db(
            os.environ.get("WH_CONTAINER", "wh-ver-wolfram_alpha"), "instance_seed")
    db = tmp / "seed_copy.db"
    shutil.copy2(SEED_DB, db)
    return db


TASKS_ROWS = [json.loads(line) for line in TASKS_FILE.read_text().splitlines() if line.strip()]


class VerifierTests(unittest.TestCase):
    def execute(self, task, *, answer=None, queries=None, task_id=None,
                 drop_trajectory=False, break_screenshot=False, mutate=None,
                 verbatim_first=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = seed_db(root)
            after = root / "after.db"
            shutil.copy2(initial, after)
            if mutate:
                with sqlite3.connect(after) as connection:
                    mutate(connection)
                    connection.commit()
            good_queries, good_answer = POSITIVE[task]
            run = make_run(root, task,
                           queries if queries is not None else good_queries,
                           answer if answer is not None else good_answer,
                           task_id=task_id, drop_trajectory=drop_trajectory,
                           break_screenshot=break_screenshot,
                           verbatim_first=verbatim_first)
            return run_verifier(task, run, initial, after)

    def test_every_task_accepts_exact_contract(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task)
                self.assertTrue(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 0)

    def test_every_task_accepts_verbatim_first_then_canonical(self):
        # the real agent first submits the task wording (rejected by the
        # mirror's gate), then the canonical query -- both must PASS
        for task in TASKS:
            with self.subTest(task=task):
                verbatim = TASKS_ROWS[task]["ques"]
                result = self.execute(task, verbatim_first=verbatim)
                self.assertTrue(result["pass"], f"task {task}: {result}")

    def test_noop_run_fails_for_every_task(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, queries=[], answer="")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result["returncode"], 1)
                self.assertEqual(result.get("reason"), "final_answer_nonempty")

    def test_shortcut_correct_answer_without_navigation_fails(self):
        # correct answer but only the homepage visited (no /input query):
        # every task's navigation check must FAIL it
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, queries=[])
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertTrue((result.get("reason") or "").startswith("nav"),
                                f"task {task}: {result}")

    def test_wrong_answer_after_required_navigation_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task, answer="The requested computation is not available on "
                                 "this Wolfram Alpha mirror.")
                self.assertFalse(result["pass"], f"task {task}: {result}")

    def test_foreign_task_replay_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, task_id="Wolfram Alpha--999")
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_trajectory_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, drop_trajectory=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_missing_screenshot_fails(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(task, break_screenshot=True)
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "run_package_valid")

    def test_database_write_fails_read_only_check(self):
        for task in TASKS:
            with self.subTest(task=task):
                result = self.execute(
                    task,
                    mutate=lambda db: db.execute(
                        "UPDATE users SET bio = bio || 'x' WHERE id = 1"))
                self.assertFalse(result["pass"], f"task {task}: {result}")
                self.assertEqual(result.get("reason"), "db_state")

    def test_topic_viewcount_change_does_not_fail_read_only_check(self):
        # viewing /topic/<slug> legitimately increments topics.view_count; the
        # read-only check covers only the user-state tables, so a run whose
        # only DB delta is a view_count bump still passes the DB check
        for task in (0, 45):
            with self.subTest(task=task):
                result = self.execute(
                    task,
                    mutate=lambda db: db.execute(
                        "UPDATE topics SET view_count = view_count + 1 WHERE id = 1"))
                self.assertTrue(result["pass"], f"task {task}: {result}")

    # ---------------- per-task content adversarials ----------------
    def test_task14_per_serving_calories_fail(self):
        # the per-actual-serving record (640/830/520) does not answer the
        # 300 g question
        result = self.execute(
            14, queries=["300g whopper vs baconator vs big mac"],
            answer="Whopper 640 Cal, Baconator 830 Cal, Big Mac 520 Cal per "
                   "serving.")
        self.assertFalse(result["pass"], result)

    def test_task14_three_separate_300g_queries_pass(self):
        result = self.execute(
            14, queries=["300g whopper", "300g baconator", "300g big mac"],
            answer="At 300 g: Whopper 657 Cal, Baconator 902 Cal, Big Mac 729 Cal.")
        self.assertTrue(result["pass"], result)

    def test_task30_brazil_texas_values_fail(self):
        # the mirror's bare-'Brazil' disambiguation quirk yields El Brazil,
        # Texas times; the task asks for the country
        result = self.execute(
            30, queries=["sunburn 1:00 pm SPF 1 Brasilia Brazil"],
            answer="Skin type I: 25 min; II: 33 min; III: 49 min; IV: 1 h 6 min; "
                   "V: 1 h 32 min; VI: 4 h 30 min.")
        self.assertFalse(result["pass"], result)

    def test_task30_texas_query_only_fails_navigation(self):
        # only the El Brazil, Texas query, with its own values: fails both nav
        # (no Brasilia qualifier) and answer
        result = self.execute(
            30, queries=["sunburn 1:00 pm SPF 1 Brazil"],
            answer="In El Brazil, Texas at 1:00 pm with SPF 1: skin type I: "
                   "25 min; II: 33 min; III: 49 min; IV: 1 h 6 min; "
                   "V: 1 h 32 min; VI: 4 h 30 min.")
        self.assertFalse(result["pass"], result)

    def test_task2_wrong_rounding_fails(self):
        result = self.execute(
            2, answer="3^71 ≈ 7.51 × 10^33 to 5 significant figures.")
        self.assertFalse(result["pass"], result)

    def test_task21_solve_for_i_quirk_answer_fails(self):
        # the mirror's 'where i is a complex number' quirk record renders the
        # complex roots of the expression set to zero -- not the task's answer
        result = self.execute(
            21, queries=["(1+0.1i)^8 + (1-0.2i)^8 = 0"],
            answer="The roots are i ≈ 0.0875 − 1.32028 i, 0.0875 + 1.32028 i, "
                   "0.945 − 4.244 i, 0.945 + 4.244 i, 3.985 − 7.989 i.")
        self.assertFalse(result["pass"], result)

    def test_task24_doesnotunderstand_answer_fails(self):
        # stopping at the site's doesn't-understand record answers nothing
        result = self.execute(
            24, queries=["y''(t) - 2y'(t) + 10y(t) = 0"],
            answer="WolframAlpha doesn't understand your query as a single "
                   "computation; it is a differential equation (general topic).")
        self.assertFalse(result["pass"], result)

    def test_task27_single_joint_query_fails_navigation(self):
        # the joint copper+aluminum query is rejected by the mirror's gate
        # (renders the mis-parsed multiplication quirk); it must not count as
        # the two required navigations
        result = self.execute(
            27, queries=["thermal conductivity copper aluminum 25 c"],
            answer="Copper 401.2 W/(m K) and aluminum 236.9 W/(m K).")
        self.assertFalse(result["pass"], result)

    def test_task34_day_query_variant_passes(self):
        result = self.execute(
            34, queries=["mass of Jupiter compared to Earth",
                         "length of day on Jupiter"],
            answer="Jupiter is 317.8 Earth masses; one day on Jupiter lasts "
                   "9.925 hours.")
        self.assertTrue(result["pass"], result)

    def test_task30_agent_form_passes(self):
        # recorded live agent form: the mirror renders the Brasilia record for
        # this query (browser-verified); it is a legitimate solve
        result = self.execute(
            30, queries=["estimated time to sunburn for different skin types "
                         "at 1:00 pm with SPF 1 in Brasilia, Brazil"],
            answer="Estimated typical time to sunburn at 1:00 pm in Brasília, "
                   "Brazil, with SPF 1: skin type I: 17 minutes; II: 22 "
                   "minutes; III: 32 minutes; IV: 43 minutes; V: 1 hour 1 "
                   "minute; VI: 3 hours.")
        self.assertTrue(result["pass"], result)

    def test_task34_jupiter_planet_record_query_passes(self):
        # recorded live agent form: renders the Jupiter (planet) record whose
        # Mass and Rotation pods carry both required facts
        result = self.execute(
            34, queries=["Jupiter mass / Earth mass and length of day on "
                         "Jupiter"],
            answer="Jupiter has a mass of 1.898 × 10^27 kg, which is about "
                   "317.8 times Earth’s mass. One sidereal day on Jupiter "
                   "(its rotation period) is 9.925 hours, or approximately 9 "
                   "hours 55 minutes 30 seconds.")
        self.assertTrue(result["pass"], result)

    def test_task43_two_sided_hyphen_query_passes(self):
        # recorded live agent form: 'two-sided' (hyphenated) renders the
        # Polyominoes[order=6, sides=2] record; math_norm keeps hyphens, so
        # the variant list must include the hyphenated form
        result = self.execute(
            43, queries=["polyominoes of order 6 two-sided"],
            answer="There are 35 two-sided hexomino combinations in total. "
                   "Of these, 13 have a bounding box of only one or two rows.")
        self.assertTrue(result["pass"], result)

    def test_task11_swapped_alloy_values_fail(self):
        # value-attribution binding: the right numbers on the wrong alloy FAIL
        result = self.execute(
            11, queries=["electrical resistivity of UNS A92024 at 20 C",
                         "electrical resistivity of UNS G10800 at 20 C"],
            answer="UNS A92024 has resistivity 1.80 × 10^-7 Ω·m and "
                   "UNS G10800 has 4.87 × 10^-8 Ω·m.")
        self.assertFalse(result["pass"], result)

    def test_task11_bullet_format_passes(self):
        # the recorded live agent format: per-alloy bullet clauses
        result = self.execute(
            11, queries=["electrical resistivity of UNS A92024 at 20 C",
                         "electrical resistivity of UNS G10800 at 20 C"],
            answer="At 20 °C:\n- UNS A92024: 9.731 × 10⁻⁵ cm·°C·Ω "
                   "(4.87 × 10⁻⁸ Ω·m)\n- UNS G10800: 3.6 × 10⁻⁴ cm·°C·Ω "
                   "(1.8 × 10⁻⁷ Ω·m)")
        self.assertTrue(result["pass"], result)

    def test_task13_swapped_years_fail(self):
        # value-attribution binding: the right dollar values on the wrong
        # years FAIL
        result = self.execute(
            13, queries=["$10000 in 1980", "$10000 in 1970"],
            answer="$10,000 today is worth $2,514.25 in 1970 and "
                   "$1,184.54 in 1980.")
        self.assertFalse(result["pass"], result)

    def test_task21_swapped_complex_parts_fail(self):
        # order/sign binding: the real and imaginary parts swapped FAIL
        result = self.execute(
            21, queries=["(1+0.1i)^8 + (1-0.2i)^8"],
            answer="The expression evaluates to 0.425258 + 0.717183 i.")
        self.assertFalse(result["pass"], result)

    def test_task21_polar_form_passes(self):
        result = self.execute(
            21, queries=["(1+0.1i)^8 + (1-0.2i)^8"],
            answer="The result is 0.833784 e^(-0.535225 i).")
        self.assertTrue(result["pass"], result)

    def test_task22_wrong_unit_fail(self):
        # unit binding: the right magnitude in the wrong unit FAIL
        result = self.execute(
            22, queries=["area of regular hexagon side 7 cm"],
            answer="The area is exactly 127.306 mm².")
        self.assertFalse(result["pass"], result)

    def test_task22_equivalent_mm_form_passes(self):
        result = self.execute(
            22, queries=["area of regular hexagon side 7 cm"],
            answer="The area is 12731 mm² (= 127.306 cm²).")
        self.assertTrue(result["pass"], result)

    def test_task27_swapped_metals_fail(self):
        # value-attribution binding: copper's and aluminum's conductivities
        # swapped FAIL
        result = self.execute(
            27, queries=["thermal conductivity copper at 25 c",
                         "thermal conductivity aluminum at 25 c"],
            answer="Copper conducts 236.9 W/(m K) and aluminum 401.2 W/(m K).")
        self.assertFalse(result["pass"], result)

    def test_task27_live_bullet_format_passes(self):
        # the recorded live agent format: per-metal bullet clauses
        result = self.execute(
            27, queries=["thermal conductivity copper at 25 c",
                         "thermal conductivity aluminum at 25 c"],
            answer="At 25 °C:\n- Copper (Cu): 401.2 W/(m·K)\n"
                   "- Aluminum (Al): 236.9 W/(m·K)")
        self.assertTrue(result["pass"], result)

    def test_task35_wrong_exponent_fail(self):
        # exponent binding: the right mantissa with the wrong power of ten FAIL
        result = self.execute(
            35, queries=["determinant of 6 by 6 Hilbert matrix"],
            answer="det(H_6) ≈ 5.3673 × 10^-15 (the determinant is tiny).")
        self.assertFalse(result["pass"], result)

    def test_task35_scientific_e_notation_passes(self):
        result = self.execute(
            35, queries=["determinant of 6 by 6 Hilbert matrix"],
            answer="The determinant is approximately 5.3673e-18.")
        self.assertTrue(result["pass"], result)

    def test_task17_swapped_city_prices_fail(self):
        # value-attribution binding (position-based): the right values on the
        # wrong cities FAIL, in both the bullet and the comma layout
        for ans in (
                "Average movie ticket prices in 2023:\n- Providence: $11.60\n"
                "- Nashville: $13.30\n- Boise: $14.37",
                "Average 2023 movie ticket prices: Providence $11.60, "
                "Nashville $13.30, Boise $14.37."):
            with self.subTest(ans=ans[:40]):
                result = self.execute(
                    17, queries=["average price of movie ticket Providence 2023",
                                 "average price of movie ticket Nashville 2023",
                                 "average price of movie ticket Boise 2023"],
                    answer=ans)
                self.assertFalse(result["pass"], result)

    def test_task17_live_and_value_for_name_formats_pass(self):
        # the recorded live bullet format and the 'value for name' pod-quote
        # layout both bind correctly
        for ans in (
                "Average movie ticket prices in 2023:\n- Providence: $14.37\n"
                "- Nashville: $13.30\n- Boise: $11.60",
                "The 2023 means were $14.37 for Providence, $13.30 for "
                "Nashville and $11.60 for Boise."):
            with self.subTest(ans=ans[:40]):
                result = self.execute(
                    17, queries=["average price of movie ticket Providence 2023",
                                 "average price of movie ticket Nashville 2023",
                                 "average price of movie ticket Boise 2023"],
                    answer=ans)
                self.assertTrue(result["pass"], result)

    def test_external_host_input_query_fails(self):
        # D1: /input submissions on the real upstream host are NOT on-site
        # navigation; a correct answer without mirror navigation FAILs
        for task, query, answer in (
                (0, "derivative of x^2 at 5.6",
                 "The derivative of x^2 is 2x. At x = 5.6, it is 11.2."),
                (2, "3^71",
                 "3^71 = 7.5095 × 10^33 to 5 significant figures.")):
            with self.subTest(task=task):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    initial = seed_db(root)
                    after = root / "after.db"
                    shutil.copy2(initial, after)
                    run = make_run(root, task, [query], answer,
                                   step_origin="https://www.wolframalpha.com")
                    result = run_verifier(task, run, initial, after)
                    self.assertFalse(result["pass"], result)
                    self.assertEqual(result["returncode"], 1)

    def test_task11_runon_swapped_values_fail(self):
        # D2: single-clause run-on swaps (comma + while) must FAIL
        result = self.execute(
            11, queries=["electrical resistivity of UNS A92024 at 20 C",
                         "electrical resistivity of UNS G10800 at 20 C"],
            answer="At 20 °C, UNS A92024 has electrical resistivity "
                   "1.80 × 10⁻⁷ Ω·m, while UNS G10800 has 4.87 × 10⁻⁸ Ω·m.")
        self.assertFalse(result["pass"], result)

    def test_task13_runon_swapped_years_fail(self):
        result = self.execute(
            13, queries=["$10000 in 1980", "$10000 in 1970"],
            answer="Your $10,000 today would be worth about $1,184.54 in "
                   "1980 dollars, while in 1970 it would be worth about "
                   "$2,514.25.")
        self.assertFalse(result["pass"], result)

    def test_task13_value_before_year_format_passes(self):
        # the pod-quote layout '$2514.25 in 1980 dollars' must still bind
        result = self.execute(
            13, queries=["$10000 in 1980", "$10000 in 1970"],
            answer="$10,000 today is worth $2,514.25 in 1980 dollars and "
                   "$1,184.54 in 1970 dollars.")
        self.assertTrue(result["pass"], result)

    def test_task27_runon_swapped_metals_fail(self):
        result = self.execute(
            27, queries=["thermal conductivity copper at 25 c",
                         "thermal conductivity aluminum at 25 c"],
            answer="At 25 °C, copper has thermal conductivity 236.9 W/(m·K), "
                   "while aluminum has 401.2 W/(m·K).")
        self.assertFalse(result["pass"], result)

    def test_task22_restate_params_wrong_unit_fail(self):
        # D3: the task parameters restated with 'cm' must not satisfy the
        # unit binding when the value carries mm² (wrong by x100)
        result = self.execute(
            22, queries=["area of regular hexagon side 7 cm"],
            answer="The area of the regular hexagon with side 7 cm is "
                   "127.306 mm².")
        self.assertFalse(result["pass"], result)

    def test_task22_spelled_out_unit_passes(self):
        result = self.execute(
            22, queries=["area of regular hexagon side 7 cm"],
            answer="The area is approximately 127.306 square centimeters.")
        self.assertTrue(result["pass"], result)

    def test_task25_swapped_distance_height_fail(self):
        # D4: distance and height swapped must FAIL
        result = self.execute(
            25, queries=["projectile 30 m/s 45 degrees, t=3 s"],
            answer="The projectile reaches a maximum height of 63.64 m and "
                   "travels a horizontal distance of 15.91 m.")
        self.assertFalse(result["pass"], result)

    def test_task25_x_y_layout_passes(self):
        # the recorded live layout: x = 63.64 m, y = 19.49 m
        result = self.execute(
            25, queries=["projectile 30 m/s 45 degrees, t=3 s"],
            answer="Position: x = 63.64 m; y = 19.49 m. Velocity: "
                   "vx = 21.21 m/s, vy = −8.22 m/s.")
        self.assertTrue(result["pass"], result)

    def test_task30_scrambled_skin_types_fail(self):
        # D4: all values present but the type-time mapping scrambled FAILs
        result = self.execute(
            30, queries=["sunburn 1:00 pm SPF 1 Brasilia Brazil"],
            answer="In Brasília with SPF 1 at 1 pm, typical sunburn times "
                   "are: skin type I: 43 min; II: 32 min; III: 22 min; "
                   "IV: 17 min; V: 3 h; VI: 1 h 1 min.")
        self.assertFalse(result["pass"], result)

    def test_task31_weather_only_queries_pass_navigation(self):
        # D5: the mirror renders the full weather record for weather-only
        # queries (probe-verified); navigation must accept them
        for q in ("weather in Chicago IL now", "Chicago weather"):
            with self.subTest(query=q):
                result = self.execute(
                    31, queries=[q],
                    answer="Chicago, IL is currently 54 °F, with wind at "
                           "16 mph from the SSW.")
                self.assertTrue(result["pass"], result)

    def test_task35_hilbertmatrix_wolfram_form_passes_navigation(self):
        # D6: the mirror renders the determinant record for the Wolfram-syntax
        # query (probe-verified); navigation must accept it
        result = self.execute(
            35, queries=["determinant of HilbertMatrix[6]"],
            answer="The determinant of the 6×6 Hilbert matrix is "
                   "1/186313420339200000 ≈ 5.3673 × 10^-18.")
        self.assertTrue(result["pass"], result)

    def test_task35_abbreviated_det_forms_pass_navigation(self):
        # R2-1: the mirror renders the full determinant record (Determinant
        # pod: 1 / 186 313 420 339 200 000 = 5.367 x 10^-18) for the three
        # abbreviated 'det' forms (browser-probed); navigation must accept
        # them, while the verbatim task wording still FAILs
        for q in ("det of 6 by 6 Hilbert matrix",
                  "Det[HilbertMatrix[6]]",
                  "det HilbertMatrix[6]"):
            with self.subTest(query=q):
                result = self.execute(
                    35, queries=[q],
                    answer="The determinant of the 6×6 Hilbert matrix is "
                           "1/186313420339200000 ≈ 5.3673 × 10^-18.")
                self.assertTrue(result["pass"], result)
        with self.subTest(query="verbatim wording (mirror-rejected)"):
            result = self.execute(
                35, queries=["Calculate the determinant of a 6x6 Hilbert matrix."],
                answer="The determinant of the 6×6 Hilbert matrix is "
                       "1/186313420339200000 ≈ 5.3673 × 10^-18.")
            self.assertFalse(result["pass"], result)

    def test_task34_mass_only_query_fails(self):
        # a query rendering only the mass fact does not cover the day-length
        # requirement
        result = self.execute(
            34, queries=["mass of Jupiter compared to Earth"],
            answer="Jupiter is 317.8 Earth masses; one day on Jupiter lasts "
                   "9.925 hours.")
        self.assertFalse(result["pass"], result)

    def test_task32_partial_prime_list_fails(self):
        result = self.execute(
            32, answer="The primes are 1009, 1013, 1019 and a few more.")
        self.assertFalse(result["pass"], result)

    def test_task44_unpinned_constant_fails(self):
        # the general solution without the g(0)=1 constant does not answer
        result = self.execute(
            44, answer="g(x) = −arcsin(coth(x − c₁)); the constant c₁ is "
                       "arbitrary.")
        self.assertFalse(result["pass"], result)

    # ---------------- tasks.jsonl contract ----------------
    def test_tasks_file_contract(self):
        self.assertEqual(len(TASKS_ROWS), 46)
        for n, row in enumerate(TASKS_ROWS):
            with self.subTest(row=row["id"]):
                self.assertEqual(
                    set(row.keys()),
                    {"web_name", "id", "ques", "web", "upstream_url",
                     "verifier_path", "judge_rubric"})
                self.assertNotIn("answer", row)
                self.assertEqual(row["id"], f"Wolfram Alpha--{n}")
                self.assertEqual(row["verifier_path"],
                                 f"sites/wolfram_alpha/verify/verify_{n}.py")
                self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."))
                self.assertTrue((WORKTREE_ROOT / row["verifier_path"]).is_file())


WORKTREE_ROOT = VERIFY_DIR.parents[2]


if __name__ == "__main__":
    unittest.main()
