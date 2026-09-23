"""Deterministic verifier contract tests for the Coolmath4Kids mirror.

Covers, per task (0-31):
  - ground-truth sanity against the frozen seed DB (catalog, lessons, quiz
    ranges, benchmark users and their seeded progress),
  - an honest offline run fixture (valid trajectory + screenshots + DB
    snapshots) MUST PASS,
  - a no-op run MUST FAIL (contentless answer with homepage-only navigation,
    and the empty-answer variant),
  - a wrong-answer run (correct navigation, false values) MUST FAIL,
  - a shortcut run (ground-truth answer, no navigation to the answer page)
    MUST FAIL,
  - tampered run packages (missing/corrupt trajectory, tiny 1x1 screenshots,
    dropped screenshots, foreign-origin URLs, truncated run, DB drift on a
    read-only task) MUST FAIL,
  - stateful tasks (8, 9, 16, 17, 18, 19, 25, 26): a state-mismatch run
    (success claimed, DB unchanged) MUST FAIL, and the honest fixture's DB
    mutation is verified.
The fixtures replicate the agent_demo trajectory schema; no browser and no
docker are needed. The seed DB must exist at
sites/coolmath4kids/instance_seed/coolmath4kids.db (ships in the pinned asset
archive; md5 0e7330da0d3e48c7523979f1561e013d).
"""
import ast
import json
import random
import shutil
import sqlite3
import struct
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
VERIFY = SITE / "verify"
SEED = SITE / "instance_seed" / "coolmath4kids.db"
TASKS = SITE / "tasks.jsonl"
REPO = Path(__file__).resolve().parents[3]
BASE = "http://localhost:46067"

sys.path.insert(0, str(VERIFY))
import grade  # noqa: E402

SEED_MD5 = "0e7330da0d3e48c7523979f1561e013d"


# ---------------------------------------------------------------- PNG fixture
def make_png(seed, width=240, height=160):
    """A valid, distinct, deterministic noise PNG (>= 2000 bytes)."""
    rng = random.Random(seed)
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rng.randrange(256) for _ in range(width * 3))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def tiny_png():
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00", 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- honest fixtures
def S(url, action="goto", params=None, text=""):
    return (url, action, params or {}, text)


HONEST = {
    0: dict(steps=[S(BASE + "/math-games"), S(BASE + "/math-games/multiplication")],
            answer="The Multiplication topic lists 8 games in total. "
                   "The first game in the grid is Tortuga Racing."),
    1: dict(steps=[S(BASE + "/math-games"), S(BASE + "/math-games/kindergarten")],
            answer="The Kindergarten games page lists, in order: Alien Addition, "
                   "123 Tracing, Jet Ski Addition, Tugboat Addition."),
    2: dict(steps=[S(BASE + "/search?q=customize+your+turtle"),
                   S(BASE + "/math-games/tortuga-racing")],
            answer="The game is Tortuga Racing. It supports 1 player."),
    3: dict(steps=[S(BASE + "/math-games/math-fisher")],
            answer="Math Fisher covers 'Prime Numbers 1-100' according to its "
                   "Contents line and supports 1 player."),
    4: dict(steps=[S(BASE + "/math-games/weighing-fruits"),
                   S(BASE + "/math-games/addition"),
                   S(BASE + "/math-games/subtraction")],
            answer="Weighing Fruits appears under two topics: Addition and Subtraction."),
    5: dict(steps=[S(BASE + "/math-games/grand-prix-multiplication")],
            answer="The page lists standard 3.OA.C.7 (Fluently multiply and divide "
                   "within 100), and the Contents line says 'Multiplication facts to 12'."),
    6: dict(steps=[S(BASE + "/search?q=algebraic+exponent+expressions"),
                   S(BASE + "/math-games/otter-rush")],
            answer="Otter Rush covers 'Algebraic exponent expressions' and supports "
                   "12 players."),
    7: dict(steps=[S(BASE + "/search?q=making+change"),
                   S(BASE + "/math-games/dolphin-feed")],
            answer="Dolphin Feed covers 'Making change', supports 4 players, and is "
                   "listed under the Addition topic."),
    8: dict(steps=[S(BASE + "/math-games/dirt-bike-fractions")],
            answer="I finished the race in 1st place with a facts score of 10/10."),
    9: dict(steps=[S(BASE + "/math-games/123-tracing")],
            answer="The game asks counting questions (how many dots). My final facts "
                   "score was 10/10."),
    10: dict(steps=[S(BASE + "/math-help/multiplication"),
                    S(BASE + "/math-help/multiplication/lattice-multiplication")],
             answer="The Lattice Multiplication lesson has 4 pages in total."),
    11: dict(steps=[S(BASE + "/math-help"), S(BASE + "/math-help/addition"),
                    S(BASE + "/math-help/subtraction"), S(BASE + "/math-help/multiplication"),
                    S(BASE + "/math-help/division"), S(BASE + "/math-help/fractions")],
             answer="Fractions contains the most lessons, with 17 lessons."),
    12: dict(steps=[S(BASE + "/math-help/addition"),
                    S(BASE + "/math-help/addition/how-addition-works"),
                    S(BASE + "/math-help/addition/scratch-addition"),
                    S(BASE + "/math-help/addition/adding-numbers-within-1000")],
             answer="Scratch Addition has the most pages: 6 pages."),
    13: dict(steps=[S(BASE + "/math-help/fractions")],
             answer="The lesson that comes immediately after Mixed Numbers is The Magic 1."),
    14: dict(steps=[S(BASE + "/math-help/fractions/what-are-fractions")],
             answer="The lesson says: 'Fractions are for counting PART of something.'"),
    15: dict(steps=[S(BASE + "/quizzes/addition")],
             answer="The Numbers Covered options are: 0-10, 0-5, 11-20, 20-50."),
    16: dict(steps=[S(BASE + "/quizzes/addition"),
                    S(BASE + "/quizzes/addition?attempt=fixt16"),
                    S(BASE + "/quizzes/addition?attempt=fixt16&view=results")],
             answer="The results page shows 'Great Job!'. Yes, I qualified for a "
                    "certificate (10 out of 10)."),
    17: dict(steps=[S(BASE + "/quizzes/multiplication"),
                    S(BASE + "/quizzes/multiplication?attempt=fixt17&view=results"),
                    S(BASE + "/certificate/9")],
             answer="The certificate page title is 'Mathasaurus Rex Certificate of "
                    "Achievement'."),
    18: dict(steps=[S(BASE + "/quizzes/division"),
                    S(BASE + "/quizzes/division?attempt=fixt18&view=results")],
             answer="The feedback message is 'Pretty Good!' and the page says "
                    "'Score 8 out of 10 to earn a certificate.'"),
    19: dict(steps=[S(BASE + "/quizzes/addition"),
                    S(BASE + "/quizzes/addition?attempt=fixt19&view=results")],
             answer="My final score was 20 out of 20."),
    20: dict(steps=[S(BASE + "/quizzes/subtraction")],
             answer="The three time-per-question options besides Unlimited are "
                    "30 Sec., 15 Sec. and 5 Sec."),
    21: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="My best Multiplication quiz score is 90%, scored on the 0-10 "
                    "numbers range."),
    22: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="My Subtraction certificate uses the Math Ninja theme and the "
                    "name printed on it is Bob Chen."),
    23: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="My two completed Division attempts: Numbers Covered 1-10 with "
                    "9/10 (90%), and 1-5 with 10/10 (100%)."),
    24: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="My favorite games are Meteor Multiplication and Tractor "
                    "Multiplication. My best game result is on Meteor Multiplication "
                    "with a facts score of 7/10 and a finishing position of 2nd place."),
    25: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="I removed Tugboat Addition from my favorites. My remaining "
                    "favorites are Grand Prix Multiplication and Alien Addition."),
    26: dict(steps=[S(BASE + "/login"), S(BASE + "/account")],
             answer="I removed Meteor Multiplication from my favorites. Tractor "
                    "Multiplication remains."),
    27: dict(steps=[S(BASE + "/brain-teasers/handshake-puzzle")],
             answer="When SIX people are in the room and each shakes hands exactly "
                    "once with everyone else, there will be 15 handshakes."),
    28: dict(steps=[S(BASE + "/manipulatives/number-line")],
             answer="The About panel says the Number Line helps students develop "
                    "'greater flexibility in mental arithmetic'."),
    29: dict(steps=[S(BASE + "/manipulatives/ten-frame")],
             answer="The status line reads: '14 of 20 cells filled — click cells to "
                    "add or remove counters.'"),
    30: dict(steps=[S(BASE + "/search?q=lattice")],
             answer="The search for 'lattice' returns the Lattice Multiplication "
                    "lesson, grouped under the Lessons section heading."),
    31: dict(steps=[S(BASE + "/search?q=prime+numbers"),
                    S(BASE + "/math-games/math-fisher")],
             answer="The search returns the game Math Fisher, and its Contents line "
                    "says 'Prime Numbers 1-100'."),
}


# Expanded reviewer tasks retain the independent component fixture expectations.
_ORIGINAL_HONEST = HONEST.copy()
_REVIEW_COMPONENTS = json.loads(((SITE / "verify") / "review_components.json").read_text())

for _n, _parts in _REVIEW_COMPONENTS.items():
    HONEST[int(_n)] = dict(_ORIGINAL_HONEST[int(_n)],
        steps=[step for k in _parts for step in _ORIGINAL_HONEST[k]["steps"]],
        answer="\n".join(_ORIGINAL_HONEST[k]["answer"] for k in _parts))

WRONG_ANSWERS = {
    0: "The Multiplication topic lists 9 games in total. The first game in the grid "
       "is Grand Prix Multiplication.",
    1: "The Kindergarten games page lists, in order: Alien Addition, Jet Ski "
       "Addition, 123 Tracing, Tugboat Addition.",
    2: "The game is Tortuga Racing. It supports 4 players.",
    3: "Math Fisher covers 'Addition facts to 12' according to its Contents line "
       "and supports 4 players.",
    4: "Weighing Fruits appears under two topics: Addition and Fractions.",
    5: "The page lists standard 4.NF.A.2, and the Contents line says 'Division "
       "facts to 12'.",
    6: "Meteor Multiplication covers 'Algebraic exponent expressions' and supports "
       "8 players.",
    7: "Island Chase covers 'Making change', supports 4 players, and is listed "
       "under the Subtraction topic.",
    8: "I finished the race in 3rd place with a facts score of 8/10.",
    9: "The game asks multiplication questions. My final facts score was 9/10.",
    10: "The Lattice Multiplication lesson has 3 pages in total.",
    11: "Addition contains the most lessons, with 7 lessons.",
    12: "How Addition Works has the most pages: 3 pages.",
    13: "The lesson that comes immediately after Mixed Numbers is Simplifying "
        "Fractions.",
    14: "The lesson says: 'Fractions are for dividing whole things into pieces.'",
    15: "The Numbers Covered options are: 0-10, 0-5, 11-20, 0-100.",
    16: "The results page shows 'Nice Job!'. No, I did not qualify for a certificate.",
    17: "The certificate page title is 'Math Ninja Certificate of Achievement'.",
    18: "The feedback message is 'Keep Trying!' and the page says 'Score 6 out of "
        "10 to earn a certificate.'",
    19: "My final score was 19 out of 20.",
    20: "The three time-per-question options besides Unlimited are 30 Sec., 15 Sec. "
        "and 10 Sec.",
    21: "My best Multiplication quiz score is 100%, scored on the 0-5 numbers range.",
    22: "My Subtraction certificate uses the Math Girl theme and the name printed "
        "on it is Alice Johnson.",
    23: "My two completed Division attempts: 1-10 with 10/10 (100%), and 1-5 with "
        "8/10 (80%).",
    24: "My favorite games are Meteor Multiplication and Canoe Penguins. My best "
        "game result is on Canoe Penguins with a facts score of 9/10 in 1st place.",
    25: "I removed Grand Prix Multiplication. My remaining favorites are Tugboat "
        "Addition and Alien Addition.",
    26: "I removed Island Chase from my favorites. Canoe Penguins remains.",
    27: "When SIX people are in the room there will be 21 handshakes.",
    28: "The About panel says the Number Line helps students develop 'basic number "
        "sense'.",
    29: "The status line reads: '14 of 10 cells filled'.",
    30: "The search for 'lattice' returns the Math Fisher game, grouped under the "
        "Math Games section heading.",
    31: "The search returns the game Math Fisher, and its Contents line says "
        "'Decimal conversion'.",
}

STATEFUL = {8, 9, 16, 17, 18, 19, 25, 26}


# ---------------------------------------------------------------- fixture builder
def build_run(root, steps, final_answer, n, *, terminated=True, shots_n=None,
              tiny_shots=False, drop_shots=False, no_traj=False, corrupt_traj=False,
              foreign=False, mutate=None):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)          # a fresh package: no stale trajectory/shots
    root.mkdir(parents=True, exist_ok=True)
    frames = shots_n if shots_n is not None else len(steps) + 1
    if not drop_shots:
        (root / "screenshots").mkdir(exist_ok=True)
        for i in range(frames):
            data = tiny_png() if tiny_shots else make_png(1000 + i)
            (root / "screenshots" / f"step_{i:03d}.png").write_bytes(data)
    shutil.copy2(SEED, root / "initial.db")
    shutil.copy2(SEED, root / "after.db")
    if mutate:
        mutate(root / "after.db")
    if no_traj:
        return root
    traj_steps = []
    for i, (url, action, params, text) in enumerate(steps):
        if foreign:
            url = url.replace(BASE, "https://www.coolmath4kids.com")
        traj_steps.append({
            "step": i, "url": url, "title": "fixture", "page_text": text,
            "thought": "fixture thought", "action": action, "params": params,
            "observed_text": text, "observed_text_before": text,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
        })
    last = len(traj_steps)
    traj_steps.append({
        "step": last, "url": steps[-1][0] if steps else BASE + "/",
        "title": "fixture", "page_text": "final", "thought": "done",
        "action": "done", "params": {"text": final_answer, "success": True},
        "observed_text": "final", "observed_text_before": "final",
        "observed_text_after": "final",
        "screenshot_before": f"step_{last:03d}.png",
        "screenshot_after": f"step_{last:03d}.png",
    })
    traj = {
        "task": "fixture", "task_id": f"Coolmath4Kids--{n}",
        "start_url": steps[0][0] if steps else BASE + "/",
        "model": "fixture", "max_steps": 40, "steps": traj_steps,
        "terminated": terminated, "termination_reason": "agent_done" if terminated else None,
        "final_answer": final_answer, "success_self_report": True,
        "judge_rubric": "", "verifier_path": f"sites/coolmath4kids/verify/verify_{n}.py",
    }
    text = json.dumps(traj, indent=1)
    if corrupt_traj:
        text = text[: len(text) // 2]
    (root / "trajectory.json").write_text(text)
    return root


def run_verifier(number, run_dir):
    proc = subprocess.run(
        [sys.executable, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run_dir)],
        capture_output=True, text=True, timeout=180,
        env={**__import__("os").environ, "WH_SITE": "coolmath4kids"},
    )
    try:
        verdict = json.loads(proc.stdout)
    except ValueError:
        verdict = {"pass": False, "reason": "verifier crashed", "stdout": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


# ---------------------------------------------------------------- DB mutations
def _insert_attempt(db, token, operation, range_label, total, correct, score):
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO quiz_attempts (token, user_id, operation, range_label, "
        "total_questions, time_per_question, status, questions, answers, elapsed_ms, "
        "correct_count, score_pct, avg_seconds, created_at, completed_at) "
        "VALUES (?, NULL, ?, ?, ?, 'Unlimited', 'complete', '[]', '[]', '[]', "
        "?, ?, 1.2, '2026-09-26 10:00:00', '2026-09-26 10:02:00')",
        (token, operation, range_label, total, correct, score))
    con.commit()
    rowid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return rowid


def mut_t8(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO game_plays (user_id, game_slug, facts_total, "
                "facts_correct, position, duration_seconds, created_at) VALUES "
                "(NULL, 'dirt-bike-fractions', 10, 10, 1, 9.8, '2026-09-26 10:00:00')")
    con.commit()
    con.close()


def mut_t9(db):
    con = sqlite3.connect(db)
    con.execute("INSERT INTO game_plays (user_id, game_slug, facts_total, "
                "facts_correct, position, duration_seconds, created_at) VALUES "
                "(NULL, '123-tracing', 10, 10, 1, 7.4, '2026-09-26 10:00:00')")
    con.commit()
    con.close()


def mut_t16(db):
    _insert_attempt(db, "fixture-t16", "Addition", "0-5", 10, 10, 100.0)


def mut_t17(db):
    rowid = _insert_attempt(db, "fixture-t17", "Multiplication", "7's", 10, 10, 100.0)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO certificates (user_id, attempt_id, person_name, theme, "
                "operation, range_label, correct, total, issued_at) VALUES "
                "(NULL, ?, 'Multiplication Star', 'mathasaurusrex', 'Multiplication', "
                "'7''s', 10, 10, '2026-09-26 10:02:00')", (rowid,))
    con.commit()
    con.close()


def mut_t18(db):
    _insert_attempt(db, "fixture-t18", "Division", "1-5", 10, 7, 70.0)


def mut_t19(db):
    _insert_attempt(db, "fixture-t19", "Addition", "0-10", 20, 20, 100.0)


def mut_t25(db):
    con = sqlite3.connect(db)
    con.execute("DELETE FROM favorites WHERE user_id=1 AND game_slug='tugboat-addition'")
    con.commit()
    con.close()


def mut_t26(db):
    con = sqlite3.connect(db)
    con.execute("DELETE FROM favorites WHERE user_id=4 AND game_slug='meteor-multiplication'")
    con.commit()
    con.close()


def mut_db_drift(db):
    """Silent DB drift on any task (a catalog value changed under the agent)."""
    con = sqlite3.connect(db)
    con.execute("UPDATE games SET players=99 WHERE slug='tortuga-racing'")
    con.commit()
    con.close()


HONEST_MUTATIONS = {8: mut_t8, 9: mut_t9, 16: mut_t16, 17: mut_t17, 18: mut_t18,
                     19: mut_t19, 25: mut_t25, 26: mut_t26}


# ---------------------------------------------------------------- the suite
class VerifierContract(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if not SEED.is_file():
            raise unittest.SkipTest(
                f"seed DB missing: {SEED} (fetch the pinned asset archive first)")
        cls.tmp = Path(__import__("tempfile").mkdtemp(prefix="wh-cmk-verify-test-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fixture(self, kind, n, **kw):
        h = HONEST[n]
        steps = h["steps"]
        answer = h["answer"]
        mutate = kw.pop("mutate", None)  # None = unspecified; False = explicitly none
        if kind == "noop":
            steps = [S(BASE + "/")]
            answer = "I opened the homepage but could not find the information " \
                     "requested by this task."
        elif kind == "noopempty":
            steps = [S(BASE + "/")]
            answer = ""
        elif kind == "wrong":
            answer = WRONG_ANSWERS[n]
        elif kind == "shortcut":
            steps = [S(BASE + "/")]
        elif kind == "honest":
            if n in HONEST_MUTATIONS and mutate is None:
                mutate = HONEST_MUTATIONS[n]
        if mutate is False:               # explicit "no mutation" (state mismatch)
            mutate = None
        return build_run(self.tmp / kind / f"{n:02d}", steps, answer, n, mutate=mutate, **kw)

    # ---- ground-truth sanity against the frozen seed --------------------
    def test_ground_truth_matches_seed_db(self):
        import hashlib
        digest = hashlib.md5(SEED.read_bytes()).hexdigest()
        self.assertEqual(digest, SEED_MD5)
        con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        try:
            def one(sql, *params):
                return con.execute(sql, params).fetchone()

            # health counts
            self.assertEqual(one("SELECT COUNT(*) FROM games")[0], 26)
            self.assertEqual(one("SELECT COUNT(*) FROM lessons")[0], 35)
            self.assertEqual(one("SELECT COUNT(*) FROM teasers")[0], 11)
            self.assertEqual(one("SELECT COUNT(*) FROM manipulatives")[0], 4)
            self.assertEqual(one("SELECT COUNT(*) FROM users")[0], 4)
            self.assertEqual(one("SELECT COUNT(*) FROM favorites")[0], 10)
            self.assertEqual(one("SELECT COUNT(*) FROM quiz_attempts")[0], 8)
            self.assertEqual(one("SELECT COUNT(*) FROM certificates")[0], 2)
            self.assertEqual(one("SELECT COUNT(*) FROM game_plays")[0], 4)
            # T0: multiplication membership + first grid game
            mult = con.execute("SELECT slug, topic_position FROM games "
                               "WHERE topics LIKE '%multiplication%'").fetchall()
            self.assertEqual(len(mult), grade.MULT_GAMES)
            first = min(mult, key=lambda r: json.loads(r[1])["multiplication"])
            self.assertEqual(first[0].lower().replace("-", "-"),
                             grade.MULT_FIRST.lower().replace(" ", "-"))
            # T1: kindergarten order
            kinder = con.execute("SELECT slug, grade_position FROM games "
                                 "WHERE grades LIKE '%kindergarten%'").fetchall()
            order = sorted(kinder, key=lambda r: json.loads(r[1])["kindergarten"])
            self.assertEqual([r[0] for r in order],
                             ["alien-addition", "123-tracing", "jet-ski-addition",
                              "tugboat-addition"])
            # T2/T3: players
            self.assertEqual(one("SELECT players FROM games WHERE "
                                 "slug='tortuga-racing'")[0], grade.TORTUGA_PLAYERS)
            row = one("SELECT contents, players FROM games WHERE slug='math-fisher'")
            self.assertEqual((row[0], row[1]),
                             (grade.MATH_FISHER_CONTENTS, grade.MATH_FISHER_PLAYERS))
            # T4: weighing fruits topics
            self.assertEqual(one("SELECT topics FROM games WHERE "
                                 "slug='weighing-fruits'")[0], "addition,subtraction")
            # T5: grand prix standard + contents
            row = one("SELECT contents, standards FROM games WHERE "
                      "slug='grand-prix-multiplication'")
            self.assertIn("3.OA.C.7", row[1])
            self.assertEqual(row[0], grade.GRAND_PRIX_CONTENTS)
            # T6: otter rush
            row = one("SELECT contents, players FROM games WHERE slug='otter-rush'")
            self.assertEqual((row[0], row[1]),
                             ("Algebraic exponent expressions", grade.OTTER_RUSH_PLAYERS))
            # T7: dolphin feed
            row = one("SELECT contents, players, topic FROM games WHERE slug='dolphin-feed'")
            self.assertEqual((row[0], row[1], row[2]),
                             ("Making change", grade.DOLPHIN_PLAYERS, "addition"))
            # T10/T12: lesson page counts
            pages = {slug: len(json.loads(p)) for slug, p in con.execute(
                "SELECT slug, pages FROM lessons WHERE topic='addition'")}
            self.assertEqual(pages, grade.ADDITION_LESSON_PAGES)
            best = max(pages, key=pages.get)
            self.assertEqual(best, "scratch-addition")
            self.assertEqual(pages[best], grade.MOST_ADDITION_LESSON[1])
            lattice = one("SELECT pages FROM lessons WHERE slug='lattice-multiplication'")
            self.assertEqual(len(json.loads(lattice[0])), grade.LATTICE_PAGES)
            # T11: fractions has the most lessons
            counts = dict(con.execute("SELECT topic, COUNT(*) FROM lessons "
                                      "GROUP BY topic").fetchall())
            self.assertEqual(counts, {"addition": 7, "subtraction": 7,
                                      "multiplication": 2, "division": 2,
                                      "fractions": 17})
            self.assertEqual(max(counts, key=counts.get), "fractions")
            # T13: lesson after Mixed Numbers in the fractions list
            after = one("SELECT slug FROM lessons WHERE topic='fractions' AND "
                         "order_in_topic=(SELECT order_in_topic+1 FROM lessons WHERE "
                         "topic='fractions' AND slug='mixed-numbers')")
            self.assertEqual(after[0], "magic-1")
            # T14: the counting sentence on page 1
            waf = one("SELECT pages FROM lessons WHERE slug='what-are-fractions'")
            self.assertIn("Fractions are for counting PART of something",
                          json.loads(waf[0])[0])
            # T21-T24: benchmark users' seeded progress
            self.assertEqual(one("SELECT score_pct, range_label FROM quiz_attempts "
                                 "WHERE user_id=1 AND operation='Multiplication'"),
                             (90.0, "0-10"))
            self.assertEqual(one("SELECT theme, person_name FROM certificates "
                                 "WHERE user_id=2"), ("mathninja", "Bob Chen"))
            carol = con.execute("SELECT range_label, score_pct FROM quiz_attempts "
                                "WHERE user_id=3 AND operation='Division' "
                                "ORDER BY id").fetchall()
            self.assertEqual(carol, [("1-10", 90.0), ("1-5", 100.0)])
            david_favs = [r[0] for r in con.execute(
                "SELECT game_slug FROM favorites WHERE user_id=4 ORDER BY id")]
            self.assertEqual(david_favs, ["meteor-multiplication", "tractor-multiplication"])
            self.assertEqual(one("SELECT game_slug, facts_total, facts_correct, position "
                                 "FROM game_plays WHERE user_id=4"),
                             ("meteor-multiplication", 10, 7, 2))
            # T25: alice's seeded favorites include tugboat
            alice_favs = sorted(r[0] for r in con.execute(
                "SELECT game_slug FROM favorites WHERE user_id=1"))
            self.assertEqual(alice_favs, ["alien-addition", "grand-prix-multiplication",
                                          "tugboat-addition"])
            # T28: number line about text
            self.assertIn("greater flexibility in mental arithmetic",
                          one("SELECT about FROM manipulatives WHERE "
                              "slug='number-line'")[0])
            # T27: the handshake solution image ships and is a real PNG
            sol = SITE / "static/images/teasers/extra/handshake-puzzle-solution-5.png"
            self.assertTrue(sol.is_file())
            self.assertEqual(sol.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        finally:
            con.close()
        # T15/T20: quiz dropdown options (app source, not DB)
        tree = ast.parse((SITE / "app.py").read_text())
        ranges = standards = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "QUIZ_RANGES":
                    ranges = ast.literal_eval(node.value)
                if node.targets[0].id == "CERTIFICATE_THEMES":
                    themes = ast.literal_eval(node.value)
        self.assertEqual(ranges["addition"], list(grade.ADDITION_RANGES))
        self.assertEqual(ranges["subtraction"], ["0-5", "0-10", "0-20"])
        labels = {t["key"]: t["label"] for t in themes}
        self.assertEqual(labels["mathasaurusrex"], "Mathasaurus Rex")
        quiz_page = (SITE / "templates/quiz_page.html").read_text()
        for value in ("30", "15", "5", "unlimited"):
            self.assertIn(f'value="{value}"', quiz_page)
        # T29: the ten-frame status format
        manip_js = (SITE / "static/js/manipulatives.js").read_text()
        self.assertIn("' cells filled", manip_js)
        # T17: the certificate title template
        cert_tpl = (SITE / "templates/certificate.html").read_text()
        self.assertIn("Certificate of Achievement", cert_tpl)

    # ---- tasks.jsonl contract -------------------------------------------
    def test_tasks_jsonl_contract(self):
        rows = [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 32)
        expected_keys = {"web_name", "id", "ques", "web", "upstream_url",
                         "verifier_path", "judge_rubric"}
        for i, row in enumerate(rows):
            with self.subTest(row=i):
                self.assertEqual(set(row), expected_keys)
                self.assertNotIn("answer", row)
                self.assertEqual(row["id"], f"Coolmath4Kids--{i}")
                self.assertEqual(row["verifier_path"],
                                 f"sites/coolmath4kids/verify/verify_{i}.py")
                self.assertTrue((REPO / row["verifier_path"]).is_file(),
                                row["verifier_path"])
                self.assertTrue(row["judge_rubric"].strip())
                self.assertIn("FAIL", row["judge_rubric"])

    # ---- per-task matrix ------------------------------------------------
    def test_honest_run_passes(self):
        for n in range(32):
            with self.subTest(task=n):
                run = self.fixture("honest", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), True,
                                 f"honest run must pass: {verdict.get('reason')} "
                                 f"{verdict.get('evidence')}")
                self.assertEqual(rc, 0)

    def test_noop_run_fails(self):
        for n in range(32):
            with self.subTest(task=n):
                for kind in ("noop", "noopempty"):
                    run = self.fixture(kind, n)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                    f"{kind} run must fail for task {n}")

    def test_wrong_answer_fails(self):
        for n in range(32):
            with self.subTest(task=n):
                run = self.fixture("wrong", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"wrong answer must fail for task {n}: "
                                 f"{verdict.get('reason')}")

    def test_shortcut_run_fails(self):
        for n in range(32):
            with self.subTest(task=n):
                run = self.fixture("shortcut", n)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"shortcut run must fail for task {n}: "
                                 f"{verdict.get('reason')}")

    def test_tampered_packages_fail(self):
        variants = {
            "tamper-no-traj": dict(no_traj=True),
            "tamper-corrupt-traj": dict(corrupt_traj=True),
            "tamper-tiny-shots": dict(tiny_shots=True),
            "tamper-no-shots": dict(drop_shots=True),
            "tamper-foreign": dict(foreign=True),
            "tamper-truncated": dict(terminated=False),
            "tamper-db-drift": dict(mutate=mut_db_drift),
        }
        for name, kw in variants.items():
            for n in range(32):
                with self.subTest(task=n, variant=name):
                    run = self.fixture("honest", n, **kw)
                    rc, verdict = run_verifier(n, run)
                    self.assertEqual(verdict.get("pass"), False,
                                    f"{name} must fail for task {n}")

    def test_state_mismatch_fails(self):
        for n in sorted(STATEFUL):
            with self.subTest(task=n):
                # success claimed with a correct-sounding report, DB untouched
                run = self.fixture("honest", n, mutate=False)
                rc, verdict = run_verifier(n, run)
                self.assertEqual(verdict.get("pass"), False,
                                 f"state mismatch must fail for task {n}: "
                                 f"{verdict.get('reason')}")
                self.assertIn("db_", verdict.get("reason", ""))

    def test_honest_mutation_is_exactly_the_task_outcome(self):
        """The honest fixture's after-DB matches the task's requested state change."""
        def favs(db, user):
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                return sorted(r[0] for r in con.execute(
                    "SELECT game_slug FROM favorites WHERE user_id=?", (user,)))
            finally:
                con.close()

        for n in sorted(STATEFUL):
            with self.subTest(task=n):
                run = self.fixture("honest", n)
                after = str(run / "after.db")
                con = sqlite3.connect(f"file:{after}?mode=ro", uri=True)
                try:
                    if n in (8, 9):
                        slug = "dirt-bike-fractions" if n == 8 else "123-tracing"
                        rows_ = con.execute(
                            "SELECT game_slug, facts_total, facts_correct, position "
                            "FROM game_plays WHERE game_slug=?", (slug,)).fetchall()
                        self.assertEqual(rows_, [(slug, 10, 10, 1)])
                    if n == 16:
                        self.assertEqual(con.execute(
                            "SELECT operation, range_label, total_questions, "
                            "correct_count, score_pct FROM quiz_attempts "
                            "WHERE token='fixture-t16'").fetchall(),
                            [("Addition", "0-5", 10, 10, 100.0)])
                    if n == 17:
                        self.assertEqual(con.execute(
                            "SELECT operation, range_label, correct_count, score_pct "
                            "FROM quiz_attempts WHERE token='fixture-t17'").fetchall(),
                            [("Multiplication", "7's", 10, 100.0)])
                        self.assertEqual(con.execute(
                            "SELECT person_name, theme, correct, total FROM certificates "
                            "WHERE person_name='Multiplication Star'").fetchall(),
                            [("Multiplication Star", "mathasaurusrex", 10, 10)])
                    if n == 18:
                        self.assertEqual(con.execute(
                            "SELECT operation, range_label, correct_count, score_pct "
                            "FROM quiz_attempts WHERE token='fixture-t18'").fetchall(),
                            [("Division", "1-5", 7, 70.0)])
                    if n == 19:
                        self.assertEqual(con.execute(
                            "SELECT operation, range_label, total_questions, "
                            "correct_count, score_pct FROM quiz_attempts "
                            "WHERE token='fixture-t19'").fetchall(),
                            [("Addition", "0-10", 20, 20, 100.0)])
                finally:
                    con.close()
                if n == 25:
                    self.assertEqual(favs(after, 1),
                                     ["alien-addition", "grand-prix-multiplication"])
                if n == 26:
                    self.assertEqual(favs(after, 4), ["tractor-multiplication"])


if __name__ == "__main__":
    unittest.main()
