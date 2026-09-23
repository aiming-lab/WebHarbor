"""Shared deterministic Coolmath4Kids task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED here (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / tokens / phrases,
     negation-aware, tolerant of separators)
  4. DB after-state: read-only tasks leave every table unchanged; stateful
     tasks must produce exactly the requested rows and preserve the rest

Frozen seed facts the checks are anchored on (instance_seed/coolmath4kids.db,
md5 0e7330da0d3e48c7523979f1561e013d, shipped in the pinned asset archive):
  26 games, 35 lessons (addition 7, subtraction 7, multiplication 2,
  division 2, fractions 17), 11 brain teasers, 4 manipulatives,
  4 benchmark users (alice/bob/carol/david, password TestPass123!) with
  seeded quiz attempts, certificates, favorites and game plays.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, new_rows,
    tables_unchanged, navigated_path, navigated_query, navigated_prefix,
    count_navigated_prefix, url_path, step_urls, contains_number,
    contains_count, affirm_number, affirms, affirms_any, contains_any,
    contains_all, norm, final_answer, step_text, shot_at,
    affirmed_place,
)

# ---------------------------------------------------------------- ground truth
# Catalog facts (frozen seed; asserted against the DB in test_verifiers.py)
MULT_GAMES = 8
MULT_FIRST = "Tortuga Racing"
KINDERGARTEN_ORDER = ["Alien Addition", "123 Tracing", "Jet Ski Addition",
                      "Tugboat Addition"]
TORTUGA_PLAYERS = 1
MATH_FISHER_CONTENTS = "Prime Numbers 1-100"
MATH_FISHER_PLAYERS = 1
WEIGHING_TOPICS = ("Addition", "Subtraction")
GRAND_PRIX_STANDARD = "3.OA.C.7"
GRAND_PRIX_CONTENTS = "Multiplication facts to 12"
OTTER_RUSH_TITLE = "Otter Rush"
OTTER_RUSH_PLAYERS = 12
DOLPHIN_TITLE = "Dolphin Feed"
DOLPHIN_PLAYERS = 4
DOLPHIN_TOPIC = "Addition"
LATTICE_PAGES = 4
ADDITION_LESSON_PAGES = {"how-addition-works": 3, "yardstick-addition": 2,
                         "place-value-review": 2, "adding-numbers-within-100": 2,
                         "adding-numbers-within-100-regrouping": 3,
                         "adding-numbers-within-1000": 3, "scratch-addition": 6}
MOST_ADDITION_LESSON = ("Scratch Addition", 6)
BIGGEST_TOPIC = ("Fractions", 17)
AFTER_MIXED_NUMBERS = "The Magic 1"
FRACTIONS_COUNTING_QUOTE = "counting part of something"
ADDITION_RANGES = ("0-10", "0-5", "11-20", "20-50")
SUBTRACTION_TIMES = ("30", "15", "5")
PERFECT_FEEDBACK = "Great Job!"
SEVENTY_FEEDBACK = "Pretty Good!"
CERT_THRESHOLD_TEXT = "Score 8 out of 10 to earn a certificate."
ALICE = 1
BOB = 2
CAROL = 3
DAVID = 4
ALICE_BEST_MULT = ("90", "0-10")
BOB_CERT = ("Math Ninja", "Bob Chen")
CAROL_DIVISION = (("1-10", "90"), ("1-5", "100"))
DAVID_FAVORITES = ("Meteor Multiplication", "Tractor Multiplication")
DAVID_BEST_PLAY = ("Meteor Multiplication", 7, 10, 2)
ALICE_FAVORITES_AFTER_REMOVE = ("Grand Prix Multiplication", "Alien Addition")
HANDSHAKE_SIX = 15
NUMBER_LINE_PHRASE = "greater flexibility in mental arithmetic"
TEN_FRAME_STATUS = "14 of 20 cells filled"
CERT_SUFFIX = "Certificate of Achievement"
MATHASAURUS_TITLE = "Mathasaurus Rex Certificate of Achievement"
RACE_QUESTIONS = 10


def readonly_gate(j, init_db, after_db):
    """Read-only task: every table must be byte-identical between the snapshots."""
    if not init_db or not after_db:
        j.check("db_available", False, "initial/after DB snapshot unavailable")
        return False
    changed = tables_unchanged(init_db, after_db)
    j.check("db_readonly_unchanged", changed == [],
            f"changed tables: {changed}" if changed else "all tables unchanged")
    return changed == []


def stateful_rows(j, init_db, after_db, table):
    """(ok, new_rows): the after-DB is available and exactly-table rows are new."""
    if not init_db or not after_db:
        j.check("db_available", False, "initial/after DB snapshot unavailable")
        return False, []
    before, after = rows(init_db), rows(after_db)
    if before is None or after is None:
        j.check("db_available", False, "cannot read initial/after DB snapshots")
        return False, []
    if set(before) != set(after):
        j.check("db_schema_stable", False,
                f"tables differ: {sorted(set(before) ^ set(after))}")
        return False, []
    return True, new_rows(before, after, table)


def others_unchanged(j, init_db, after_db, ignore):
    before, after = rows(init_db), rows(after_db)
    if before is not None and after is not None:
        for table in ignore - {"favorites"}:
            old = {row["id"]: row for row in before[table]}
            current = {row["id"]: row for row in after[table]}
            j.check("preserve_existing_" + table, all(current.get(k) == v for k, v in old.items()),
                    "all existing rows retained exactly")
    changed = tables_unchanged(init_db, after_db, ignore=ignore)
    j.check("db_other_tables_unchanged", changed == [],
            f"changed tables: {changed}" if changed else
            f"tables unchanged except {sorted(ignore)}")


# ---------------------------------------------------------------- per-task checks

def t00(j, traj, init_db, after_db):
    """Multiplication topic: 8 games, Tortuga Racing first."""
    j.check("nav_topic_multiplication", navigated_path(traj, "/math-games/multiplication"),
            "the By Topic Multiplication filter page must be opened")
    answer = final_answer(traj)
    j.check("answer_game_count", contains_count(answer, MULT_GAMES),
            f"expected {MULT_GAMES} multiplication games")
    j.check("answer_first_game", affirms(answer, MULT_FIRST),
            f"expected {MULT_FIRST} as the first grid game")
    readonly_gate(j, init_db, after_db)


def t01(j, traj, init_db, after_db):
    """Kindergarten grade page: full ordered game list."""
    j.check("nav_grade_kindergarten", navigated_path(traj, "/math-games/kindergarten"),
            "the By Grade Kindergarten filter page must be opened")
    answer = final_answer(traj)
    positions = []
    for title in KINDERGARTEN_ORDER:
        found = norm(answer).find(norm(title))
        j.check(f"answer_lists_{title.lower().replace(' ', '_')}", found >= 0,
                f"expected {title!r} in the answer")
        if found >= 0:
            positions.append(found)
    j.check("answer_order_matches_grid", positions == sorted(positions),
            f"expected grid order {KINDERGARTEN_ORDER}; answer positions {positions}")
    readonly_gate(j, init_db, after_db)


def t02(j, traj, init_db, after_db):
    """Tortuga Racing: title + supported players."""
    j.check("nav_game_tortuga", navigated_path(traj, "/math-games/tortuga-racing"),
            "the Tortuga Racing game page must be opened")
    answer = final_answer(traj)
    j.check("answer_title", affirms(answer, "Tortuga Racing"), "expected the game title")
    j.check("answer_players", affirm_number(answer, TORTUGA_PLAYERS),
            f"expected {TORTUGA_PLAYERS} player(s)")
    readonly_gate(j, init_db, after_db)


def t03(j, traj, init_db, after_db):
    """Math Fisher: Contents line + players."""
    j.check("nav_game_mathfisher", navigated_path(traj, "/math-games/math-fisher"),
            "the Math Fisher game page must be opened")
    answer = final_answer(traj)
    j.check("answer_contents", affirms(answer, MATH_FISHER_CONTENTS),
            f"expected Contents {MATH_FISHER_CONTENTS!r}")
    j.check("answer_players", affirm_number(answer, MATH_FISHER_PLAYERS),
            f"expected {MATH_FISHER_PLAYERS} player(s)")
    readonly_gate(j, init_db, after_db)


def t04(j, traj, init_db, after_db):
    """Weighing Fruits: listed under Addition and Subtraction."""
    opened_game = navigated_path(traj, "/math-games/weighing-fruits")
    opened_both_topics = (navigated_path(traj, "/math-games/addition")
                          and navigated_path(traj, "/math-games/subtraction"))
    j.check("nav_weighing_evidence", opened_game or opened_both_topics,
            "open the Weighing Fruits page or both topic filter pages")
    answer = final_answer(traj)
    j.check("answer_addition", affirms(answer, "Addition"), "expected the Addition topic")
    j.check("answer_subtraction", affirms(answer, "Subtraction"),
            "expected the Subtraction topic")
    readonly_gate(j, init_db, after_db)


def t05(j, traj, init_db, after_db):
    """Grand Prix Multiplication: standard + contents."""
    j.check("nav_game_grandprix", navigated_path(traj, "/math-games/grand-prix-multiplication"),
            "the Grand Prix Multiplication game page must be opened")
    answer = final_answer(traj)
    j.check("answer_standard", affirms(answer, GRAND_PRIX_STANDARD),
            f"expected standard {GRAND_PRIX_STANDARD!r}")
    j.check("answer_contents", affirms(answer, GRAND_PRIX_CONTENTS),
            f"expected Contents {GRAND_PRIX_CONTENTS!r}")
    readonly_gate(j, init_db, after_db)


def t06(j, traj, init_db, after_db):
    """'Algebraic exponent expressions' -> Otter Rush, 12 players."""
    j.check("nav_game_otterrush", navigated_path(traj, "/math-games/otter-rush"),
            "the Otter Rush game page must be opened")
    answer = final_answer(traj)
    j.check("answer_title", affirms(answer, OTTER_RUSH_TITLE), "expected the game title")
    j.check("answer_players", affirm_number(answer, OTTER_RUSH_PLAYERS),
            f"expected {OTTER_RUSH_PLAYERS} players")
    readonly_gate(j, init_db, after_db)


def t07(j, traj, init_db, after_db):
    """'Making change' -> Dolphin Feed, 4 players, Addition topic."""
    j.check("nav_game_dolphin", navigated_path(traj, "/math-games/dolphin-feed"),
            "the Dolphin Feed game page must be opened")
    answer = final_answer(traj)
    j.check("answer_title", affirms(answer, DOLPHIN_TITLE), "expected the game title")
    j.check("answer_players", affirm_number(answer, DOLPHIN_PLAYERS),
            f"expected {DOLPHIN_PLAYERS} players")
    j.check("answer_topic", affirms(answer, DOLPHIN_TOPIC),
            f"expected the {DOLPHIN_TOPIC} topic filter")
    readonly_gate(j, init_db, after_db)


def _race_play_check(j, traj, init_db, after_db, slug, require_place=False):
    ok, plays = stateful_rows(j, init_db, after_db, "game_plays")
    if not ok:
        return
    j.check("db_play_recorded_once", len(plays) == 1,
            f"expected exactly 1 new game_plays row, found {len(plays)}")
    match = [p for p in plays if p.get("game_slug") == slug]
    j.check(f"db_play_{slug}", len(match) == 1,
            f"new rows: {[(p.get('game_slug'), p.get('facts_correct')) for p in plays]}")
    answer = final_answer(traj)
    j.check("answer_score_10_of_10", contains_number(answer, RACE_QUESTIONS),
            f"expected a facts score of {RACE_QUESTIONS}/{RACE_QUESTIONS}")
    if match:
        play = match[0]
        j.check("db_play_all_correct",
                play.get("facts_total") == RACE_QUESTIONS and
                play.get("facts_correct") == RACE_QUESTIONS,
                f"facts {play.get('facts_correct')}/{play.get('facts_total')}")
        if require_place:
            place = affirmed_place(answer)
            j.check("answer_place_matches_db", place == play.get("position"),
                    f"answer affirms place {place}, DB recorded position {play.get('position')}")
    others_unchanged(j, init_db, after_db, ignore={"game_plays"})


def t08(j, traj, init_db, after_db):
    """Dirt Bike Fractions race: 10/10 facts, report position + score."""
    j.check("nav_game_dirtbike", navigated_path(traj, "/math-games/dirt-bike-fractions"),
            "the Dirt Bike Fractions game page must be opened")
    _race_play_check(j, traj, init_db, after_db, "dirt-bike-fractions", require_place=True)


def t09(j, traj, init_db, after_db):
    """123 Tracing race: counting questions, 10/10 score."""
    j.check("nav_game_tracing", navigated_path(traj, "/math-games/123-tracing"),
            "the 123 Tracing game page must be opened")
    answer = final_answer(traj)
    j.check("answer_question_type", affirms_any(answer, ("counting", "count", "dots", "dot")),
            "expected the question type (counting dots)")
    _race_play_check(j, traj, init_db, after_db, "123-tracing")


def t10(j, traj, init_db, after_db):
    """Lattice Multiplication lesson: 4 pages."""
    j.check("nav_lesson_lattice",
            navigated_path(traj, "/math-help/multiplication/lattice-multiplication"),
            "the Lattice Multiplication lesson must be opened")
    answer = final_answer(traj)
    j.check("answer_page_count", affirm_number(answer, LATTICE_PAGES),
            f"expected {LATTICE_PAGES} pages")
    readonly_gate(j, init_db, after_db)


def t11(j, traj, init_db, after_db):
    """Lesson topic with the most lessons: Fractions, 17."""
    topic_pages = {url_path(u) for u in step_urls(traj)
                   if re.fullmatch(r"/math-help/(addition|subtraction|multiplication|division|fractions)",
                                   url_path(u).rstrip("/") or "")}
    j.check("nav_fractions_lessons", navigated_path(traj, "/math-help/fractions"),
            "the Fractions lessons page must be opened")
    j.check("nav_compared_topics", len(topic_pages) >= 2,
            f"expected >=2 lesson topic pages compared, visited {sorted(topic_pages)}")
    answer = final_answer(traj)
    j.check("answer_topic", affirms(answer, BIGGEST_TOPIC[0]), "expected the Fractions topic")
    j.check("answer_lesson_count", affirm_number(answer, BIGGEST_TOPIC[1]),
            f"expected {BIGGEST_TOPIC[1]} lessons")
    readonly_gate(j, init_db, after_db)


def t12(j, traj, init_db, after_db):
    """Addition lesson with the most pages: Scratch Addition, 6."""
    lesson_pages = {url_path(u).rstrip("/") for u in step_urls(traj)
                    if url_path(u).rstrip("/").startswith("/math-help/addition/")
                    and url_path(u).rstrip("/") != "/math-help/addition"}
    j.check("nav_lesson_scratch",
            navigated_path(traj, "/math-help/addition/scratch-addition"),
            "the Scratch Addition lesson must be opened")
    j.check("nav_compared_lessons", len(lesson_pages) >= 3,
            f"expected >=3 addition lessons compared, visited {sorted(lesson_pages)}")
    answer = final_answer(traj)
    j.check("answer_lesson", affirms(answer, MOST_ADDITION_LESSON[0]),
            "expected Scratch Addition")
    j.check("answer_page_count", affirm_number(answer, MOST_ADDITION_LESSON[1]),
            f"expected {MOST_ADDITION_LESSON[1]} pages")
    readonly_gate(j, init_db, after_db)


def t13(j, traj, init_db, after_db):
    """Lesson after Mixed Numbers in the Fractions list: The Magic 1."""
    j.check("nav_fractions_lessons", navigated_path(traj, "/math-help/fractions"),
            "the Fractions lessons list must be opened")
    answer = final_answer(traj)
    j.check("answer_next_lesson", affirms(answer, AFTER_MIXED_NUMBERS),
            f"expected {AFTER_MIXED_NUMBERS!r}")
    readonly_gate(j, init_db, after_db)


def t14(j, traj, init_db, after_db):
    """What Are Fractions? page 1: the counting sentence."""
    j.check("nav_lesson_whatarefractions",
            navigated_path(traj, "/math-help/fractions/what-are-fractions"),
            "the What Are Fractions? lesson must be opened")
    answer = final_answer(traj)
    j.check("answer_quote", affirms(answer, FRACTIONS_COUNTING_QUOTE),
            f"expected the quote ...{FRACTIONS_COUNTING_QUOTE!r}...")
    readonly_gate(j, init_db, after_db)


def t15(j, traj, init_db, after_db):
    """Addition quiz Numbers Covered options."""
    j.check("nav_quiz_addition", navigated_path(traj, "/quizzes/addition"),
            "the Addition quiz setup page must be opened")
    answer = final_answer(traj)
    for rng in ADDITION_RANGES:
        j.check(f"answer_range_{rng.replace('-', '_')}", affirms(answer, rng),
                f"expected option {rng!r}")
    readonly_gate(j, init_db, after_db)


def _quiz_attempt_check(j, init_db, after_db, operation, range_label,
                        total, correct, score):
    ok, attempts = stateful_rows(j, init_db, after_db, "quiz_attempts")
    if not ok:
        return None
    j.check("db_attempt_recorded_once", len(attempts) == 1,
            f"expected exactly 1 new quiz_attempts row, found {len(attempts)}")
    match = [a for a in attempts
             if a.get("operation") == operation and a.get("range_label") == range_label
             and a.get("total_questions") == total and a.get("status") == "complete"
             and a.get("correct_count") == correct
             and abs((a.get("score_pct") or 0) - score) < 0.01]
    j.check("db_attempt_values", len(match) == 1,
            f"new rows: {[(a.get('operation'), a.get('range_label'), a.get('correct_count'), a.get('score_pct')) for a in attempts]}")
    return match


def t16(j, traj, init_db, after_db):
    """Addition quiz 0-5 x10 Unlimited, all correct: Great Job!, certificate qualified."""
    j.check("nav_quiz_addition", navigated_path(traj, "/quizzes/addition"),
            "the Addition quiz must be opened")
    j.check("nav_quiz_results", navigated_query(traj, "/quizzes/addition", view="results"),
            "the quiz results page must be reached")
    answer = final_answer(traj)
    j.check("answer_feedback", affirms(answer, PERFECT_FEEDBACK),
            f"expected the exact feedback {PERFECT_FEEDBACK!r}")
    j.check("answer_certificate_qualified",
            affirms_any(answer, ("yes", "qualified", "earned", "eligible")),
            "expected that a certificate was qualified")
    _quiz_attempt_check(j, init_db, after_db, "Addition", "0-5", 10, 10, 100.0)
    others_unchanged(j, init_db, after_db, ignore={"quiz_attempts"})


def t17(j, traj, init_db, after_db):
    """Multiplication 7's certificate: Multiplication Star / Mathasaurus Rex."""
    j.check("nav_quiz_multiplication", navigated_path(traj, "/quizzes/multiplication"),
            "the Multiplication quiz must be opened")
    j.check("nav_quiz_results",
            navigated_query(traj, "/quizzes/multiplication", view="results"),
            "the quiz results page must be reached")
    j.check("nav_certificate_page", navigated_prefix(traj, "/certificate"),
            "the issued certificate page must be opened")
    answer = final_answer(traj)
    j.check("answer_certificate_title", affirms(answer, MATHASAURUS_TITLE),
            f"expected the exact title {MATHASAURUS_TITLE!r}")
    _quiz_attempt_check(j, init_db, after_db, "Multiplication", "7's", 10, 10, 100.0)
    ok, certs = stateful_rows(j, init_db, after_db, "certificates")
    if ok:
        j.check("db_certificate_recorded_once", len(certs) == 1,
                f"expected exactly 1 new certificates row, found {len(certs)}")
        match = [c for c in certs
                 if c.get("person_name") == "Multiplication Star"
                 and c.get("theme") == "mathasaurusrex"
                 and c.get("operation") == "Multiplication"
                 and c.get("range_label") == "7's"
                 and c.get("correct") == 10 and c.get("total") == 10]
        j.check("db_certificate_values", len(match) == 1,
                f"new rows: {[(c.get('person_name'), c.get('theme')) for c in certs]}")
    others_unchanged(j, init_db, after_db, ignore={"quiz_attempts", "certificates"})


def t18(j, traj, init_db, after_db):
    """Division 1-5 x10, 7 correct: Pretty Good! + threshold text."""
    j.check("nav_quiz_division", navigated_path(traj, "/quizzes/division"),
            "the Division quiz must be opened")
    j.check("nav_quiz_results", navigated_query(traj, "/quizzes/division", view="results"),
            "the quiz results page must be reached")
    answer = final_answer(traj)
    j.check("answer_feedback", affirms(answer, SEVENTY_FEEDBACK),
            f"expected the exact feedback {SEVENTY_FEEDBACK!r}")
    j.check("answer_threshold", affirms(answer, CERT_THRESHOLD_TEXT),
            f"expected the threshold text {CERT_THRESHOLD_TEXT!r}")
    _quiz_attempt_check(j, init_db, after_db, "Division", "1-5", 10, 7, 70.0)
    others_unchanged(j, init_db, after_db, ignore={"quiz_attempts"})


def t19(j, traj, init_db, after_db):
    """Addition 0-10 x20 Unlimited, all correct: 20 out of 20."""
    j.check("nav_quiz_addition", navigated_path(traj, "/quizzes/addition"),
            "the Addition quiz must be opened")
    j.check("nav_quiz_results", navigated_query(traj, "/quizzes/addition", view="results"),
            "the quiz results page must be reached")
    answer = final_answer(traj)
    j.check("answer_score_20_of_20", affirms(answer, "20 out of 20"),
            "expected '20 out of 20' as shown on the results page")
    _quiz_attempt_check(j, init_db, after_db, "Addition", "0-10", 20, 20, 100.0)
    others_unchanged(j, init_db, after_db, ignore={"quiz_attempts"})


def t20(j, traj, init_db, after_db):
    """Subtraction quiz time options besides Unlimited: 30, 15, 5 Sec."""
    j.check("nav_quiz_subtraction", navigated_path(traj, "/quizzes/subtraction"),
            "the Subtraction quiz setup page must be opened")
    answer = final_answer(traj)
    for secs in SUBTRACTION_TIMES:
        j.check(f"answer_time_{secs}", affirm_number(answer, int(secs)),
                f"expected a {secs} Sec. option")
    readonly_gate(j, init_db, after_db)


def t21(j, traj, init_db, after_db):
    """Alice: best Multiplication score 90% on 0-10."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    j.check("answer_best_score", affirm_number(answer, 90), "expected the best score 90%")
    j.check("answer_range", affirms(answer, ALICE_BEST_MULT[1]),
            f"expected the numbers range {ALICE_BEST_MULT[1]!r}")
    readonly_gate(j, init_db, after_db)


def t22(j, traj, init_db, after_db):
    """Bob: Subtraction certificate theme Math Ninja, name Bob Chen."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    j.check("answer_theme", affirms(answer, BOB_CERT[0]), "expected the Math Ninja theme")
    j.check("answer_name", affirms(answer, BOB_CERT[1]), "expected the printed name")
    readonly_gate(j, init_db, after_db)


def t23(j, traj, init_db, after_db):
    """Carol: two Division attempts (1-10 -> 90%, 1-5 -> 100%)."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    clauses = re.split(r"[;\n]|,\s+(?:and\s+)?|\band\b|(?<=[.!?])\s+", answer, flags=re.I)
    for rng, score in CAROL_DIVISION:
        fraction = "9/10" if score == "90" else "10/10"
        ok = any(affirms(clause, rng) and
                 (re.search(r"(?<!\d)" + score + r"\s*%", clause) or
                  re.search(r"(?<!\d)" + fraction.replace("/", r"\s*(?:/|out of)\s*") + r"(?!\d)", clause))
                 for clause in clauses)
        j.check("answer_score_for_" + rng, ok, "score bound to its numbers range")
    readonly_gate(j, init_db, after_db)


def t24(j, traj, init_db, after_db):
    """David: favorites + best game result (Meteor Multiplication 7/10, 2nd)."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    for title in DAVID_FAVORITES:
        j.check(f"answer_favorite_{title.lower().replace(' ', '_')}",
                affirms(answer, title), f"expected favorite {title!r}")
    j.check("answer_best_game", affirms(answer, DAVID_BEST_PLAY[0]),
            f"expected best result on {DAVID_BEST_PLAY[0]!r}")
    j.check("answer_facts_score",
            affirm_number(answer, DAVID_BEST_PLAY[1]) and affirm_number(answer, DAVID_BEST_PLAY[2]),
            f"expected {DAVID_BEST_PLAY[1]} of {DAVID_BEST_PLAY[2]} facts")
    j.check("answer_position", any(affirmed_place(clause) == DAVID_BEST_PLAY[3] for clause in re.split(r"(?<=[.!?])\s+|\n", answer) if re.search(r"finishing|best game result|finished", clause, re.I)),
            f"expected finishing place {DAVID_BEST_PLAY[3]}")
    readonly_gate(j, init_db, after_db)


def _favorites_after(j, init_db, after_db, user_id):
    ok, favs = stateful_rows(j, init_db, after_db, "favorites")
    if not ok:
        return None
    before, after = rows(init_db), rows(after_db)
    old = {r["id"]: r for r in before["favorites"]}
    current = {r["id"]: r for r in after["favorites"]}
    removed = [old[k] for k in old.keys() - current.keys()]
    allowed = {"tugboat-addition"} if user_id == ALICE else {"meteor-multiplication", "tractor-multiplication"}
    exact = len(removed) == 1 and removed[0]["user_id"] == user_id and removed[0]["game_slug"] in allowed
    exact = exact and current.keys() <= old.keys() and all(old[k] == v for k, v in current.items())
    j.check("db_exact_favorite_removal", exact, "only the requested favorite removed; every other row preserved")
    return [f.get("game_slug") for f in after["favorites"] if f.get("user_id") == user_id]


def t25(j, traj, init_db, after_db):
    """Alice removes Tugboat Addition; Grand Prix Multiplication + Alien Addition remain."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    for title in ALICE_FAVORITES_AFTER_REMOVE:
        j.check(f"answer_remaining_{title.lower().replace(' ', '_')}",
                affirms(answer, title), f"expected remaining favorite {title!r}")
    favs = _favorites_after(j, init_db, after_db, ALICE)
    if favs is not None:
        j.check("db_alice_favorites_after_remove",
                sorted(favs) == sorted(f.replace("-", "-") for f in
                                        ("grand-prix-multiplication", "alien-addition")),
                f"alice favorites after: {sorted(favs)}")
    others_unchanged(j, init_db, after_db, ignore={"favorites"})


def t26(j, traj, init_db, after_db):
    """David removes one multiplication favorite; exactly one of the two remains."""
    j.check("nav_account", navigated_path(traj, "/account"),
            "the My Progress page must be opened")
    answer = final_answer(traj)
    for title in DAVID_FAVORITES:
        j.check(f"answer_names_{title.lower().replace(' ', '_')}",
                affirms(answer, title),
                f"expected {title!r} named as removed or remaining")
    favs = _favorites_after(j, init_db, after_db, DAVID)
    if favs is not None:
        remaining = {"meteor-multiplication", "tractor-multiplication"} & set(favs)
        j.check("db_david_one_favorite_removed", len(remaining) == 1,
                f"david favorites after: {sorted(favs)} (exactly one of the two must remain)")
    others_unchanged(j, init_db, after_db, ignore={"favorites"})


def t27(j, traj, init_db, after_db):
    """Handshake Puzzle solution: SIX people -> 15 handshakes."""
    j.check("nav_teaser_handshake", navigated_path(traj, "/brain-teasers/handshake-puzzle"),
            "the Handshake Puzzle brain teaser must be opened")
    answer = final_answer(traj)
    j.check("answer_handshakes", affirm_number(answer, HANDSHAKE_SIX),
            f"expected {HANDSHAKE_SIX} handshakes")
    readonly_gate(j, init_db, after_db)


def t28(j, traj, init_db, after_db):
    """Number Line About panel: 'greater flexibility in mental arithmetic'."""
    j.check("nav_manipulative_numberline", navigated_path(traj, "/manipulatives/number-line"),
            "the Number Line manipulative page must be opened")
    answer = final_answer(traj)
    j.check("answer_quote", affirms(answer, NUMBER_LINE_PHRASE),
            f"expected the quote ...{NUMBER_LINE_PHRASE!r}...")
    readonly_gate(j, init_db, after_db)


def t29(j, traj, init_db, after_db):
    """Ten Frame 20-frame with 14 cells: exact status line."""
    j.check("nav_manipulative_tenframe", navigated_path(traj, "/manipulatives/ten-frame"),
            "the Ten Frame manipulative page must be opened")
    answer = final_answer(traj)
    j.check("answer_status_line", affirms(answer, TEN_FRAME_STATUS),
            f"expected the status line containing {TEN_FRAME_STATUS!r}")
    readonly_gate(j, init_db, after_db)


def t30(j, traj, init_db, after_db):
    """Search 'lattice': Lattice Multiplication under the Lessons heading."""
    j.check("nav_search_lattice", navigated_query(traj, "/search", q="lattice"),
            "the site search for 'lattice' must be performed")
    answer = final_answer(traj)
    j.check("answer_result", affirms(answer, "Lattice Multiplication"),
            "expected the Lattice Multiplication lesson")
    j.check("answer_section", affirms(answer, "Lessons"),
            "expected the Lessons section heading")
    readonly_gate(j, init_db, after_db)


def t31(j, traj, init_db, after_db):
    """Search 'prime numbers': Math Fisher, Contents 'Prime Numbers 1-100'."""
    j.check("nav_search_prime", navigated_query(traj, "/search", q={"prime", "prime numbers", "prime+numbers"}),
            "the site search for 'prime numbers' must be performed")
    j.check("nav_game_mathfisher", navigated_path(traj, "/math-games/math-fisher"),
            "the Math Fisher game page must be opened for its Contents line")
    answer = final_answer(traj)
    j.check("answer_game", affirms(answer, "Math Fisher"), "expected the Math Fisher game")
    j.check("answer_contents", affirms(answer, MATH_FISHER_CONTENTS),
            f"expected Contents {MATH_FISHER_CONTENTS!r}")
    readonly_gate(j, init_db, after_db)


TASKS = {0: t00, 1: t01, 2: t02, 3: t03, 4: t04, 5: t05, 6: t06, 7: t07,
         8: t08, 9: t09, 10: t10, 11: t11, 12: t12, 13: t13, 14: t14,
         15: t15, 16: t16, 17: t17, 18: t18, 19: t19, 20: t20, 21: t21,
         22: t22, 23: t23, 24: t24, 25: t25, 26: t26, 27: t27, 28: t28,
         29: t29, 30: t30, 31: t31}


def grade(number, emit=True):
    args = parse_args()
    traj = load_run(args.run_dir)
    j = Judge(f"Coolmath4Kids--{number}", no_llm=args.no_llm)
    shot_urls = {
        0: "/math-games/multiplication", 1: "/math-games/kindergarten",
        2: "/math-games/tortuga-racing", 3: "/math-games/math-fisher",
        4: "/math-games/", 5: "/math-games/grand-prix-multiplication",
        6: "/math-games/otter-rush", 7: "/math-games/dolphin-feed",
        8: "/math-games/dirt-bike-fractions", 9: "/math-games/123-tracing",
        10: "/math-help/multiplication/lattice-multiplication",
        11: "/math-help/fractions", 12: "/math-help/addition/scratch-addition",
        13: "/math-help/fractions", 14: "/math-help/fractions/what-are-fractions",
        15: "/quizzes/addition", 16: "/quizzes/addition",
        17: "/quizzes/multiplication", 18: "/quizzes/division",
        19: "/quizzes/addition", 20: "/quizzes/subtraction",
        21: "/account", 22: "/account", 23: "/account", 24: "/account",
        25: "/account", 26: "/account",
        27: "/brain-teasers/handshake-puzzle", 28: "/manipulatives/number-line",
        29: "/manipulatives/ten-frame", 30: "/search", 31: "/search",
    }
    j.bind_run(traj, shot_url=shot_urls.get(number))
    init_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    TASKS[number](j, traj, init_db, after_db)
    if emit:
        j.emit()
    return j
