"""Deterministic verifier contract tests for the 30 Chess.com tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only, empty answer,
clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer, no navigation)
MUST FAIL. Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
state-mismatch and collateral writes. Package tampering (task_id mismatch, off-site URLs,
broken/missing screenshots, tampered seed) MUST fail closed.

No docker, no LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, SEED_DB, RunBuilder, build_run, copy_db, mutate_db,  # noqa: E402
                      run_verifier, tiny_png)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file(), reason="seed DB not built (run seed_data.py)")

STATEFUL = {8, 23, 24, 25, 29}
READ_ONLY = sorted(set(range(30)) - STATEFUL)

# ---------------------------------------------------------------- honest fixtures
HONEST = {
    0: (
        [("/leaderboard/live", "click", {})],
        "The player ranked #3 on the Blitz leaderboard is Sina-Movahed, with a rating of 3334 "
        "and 4761 games won (the number in the Won column).",
    ),
    1: (
        [("/leaderboard/live", "click", {}), ("/leaderboard/live/bullet", "click", {})],
        "Hikaru appears in the top 3 of BOTH the Blitz and the Bullet leaderboards. "
        "The #1 Bullet player is ArkadiiKhromaev with a rating of 3602.",
    ),
    2: (
        [("/leaderboard/live", "click", {})],
        "2 of the top 10 Blitz players are from the United States: Hikaru (#1) and HansOnTwitch (#6).",
    ),
    3: (
        [("/leaderboard/live/rapid", "click", {})],
        "The player ranked exactly #50 on the Rapid leaderboard is SahibSinghKnight with a rating of 2695.",
    ),
    4: (
        [("/leaderboard/tactics", "click", {})],
        "The #1 ranked player on the Tactics leaderboard is denghao with a rating of 4394; "
        "the player ranked #5 on the same page is petergrieco with a rating of 4352.",
    ),
    5: (
        [("/search?q=MagnusCarlsen", "click", {}), ("/member/MagnusCarlsen", "click", {})],
        "MagnusCarlsen's full real name is Magnus Carlsen. The profile shows 317,377 followers "
        "and a Rapid rating of 2941.",
    ),
    6: (
        [("/members", "click", {}), ("/member/Firouzja2003", "click", {})],
        "Firouzja2003 is from France and has 32,264 followers.",
    ),
    7: (
        [("/members/titled-players", "click", {})],
        "The first three GMs in the Grandmasters section are Hikaru, MagnusCarlsen, and GMKrikor. "
        "The Woman Grandmaster (WGM) section lists 1 player.",
    ),
    8: (
        "alice",
        [("/member/GMBrewChess", "click", {}), ("/settings", "click", {})],
        "I logged in as alice.j@test.com and followed GMBrewChess. My Settings page now shows "
        "that I am following 4 members.",
    ),
    9: (
        [("/news", "click", {}), ("/news/view/wesley-so-tan-win-2026-sinquefield-cairns-cup", "click", {})],
        "According to the article body, the Cairns Cup winner (Tan Zhongyi) took home $65,000 "
        "in prize money and won the tournament with a score of 6.5 points.",
    ),
    10: (
        [("/news", "click", {}), ("/news/view/vladimir-kramnik-sues-new-in-chess-naroditsky-article", "click", {})],
        "The August 2026 Kramnik article was published on 2026-08-21 by tarjeijs. The article "
        "page says it belongs to the chess-politics category.",
    ),
    11: (
        [("/news", "click", {}), ("/news/view/washington-square-park-hustler-chichi-detained-by-ice", "click", {})],
        "The article about 'Chichi' being detained by ICE was written by anthonylevin. From the "
        "article body, Chichi's real full name is Chikwere Onyekwere.",
    ),
    12: (
        [("/news/category/misc", "click", {})],
        "The Misc category lists 1 article, and the most recent one is titled 'Welcome to the "
        "Worst Band Class Ever'.",
    ),
    13: (
        [("/news?page=2", "click", {})],
        "Page 2 of the News index shows 12 article cards. The most recent (first) article on "
        "the page is 'Carlsen Calls Sindarov 'Significant Favorite,' Gives Verdict On Gukesh'.",
    ),
    14: (
        [("/openings", "click", {}), ("/openings/Sicilian-Defense", "click", {})],
        "The Sicilian Defense has ECO code B20 with 919,742 games played in the explorer. Its "
        "main line starts with the first two moves 1.e4 c5.",
    ),
    15: (
        [("/openings/French-Defense", "click", {}), ("/openings/Caro-Kann-Defense", "click", {})],
        "The French Defense has the higher Games Played count: 262,713 games versus the "
        "Caro-Kann Defense's 187,337 games.",
    ),
    16: (
        [("/openings/Ruy-Lopez-Opening", "click", {})],
        "The top three players in the Ruy Lopez Top Players panel, in order, are Viswanathan "
        "Anand, Maxime Vachier-Lagrave, and Vasily Smyslov.",
    ),
    17: (
        [("/lessons", "click", {}), ("/lessons/gambit-buffet", "click", {})],
        "The 'Gambit Buffet' course contains 16 lessons, is named after the grandmaster author "
        "GM Simon Williams, and carries the Beginner level label.",
    ),
    18: (
        [("/lessons?category=endgames", "click", {})],
        "'How To Win With Zugzwang' has 5 lessons. It appears in the Endgames skill category "
        "filter (the course also carries the Tactics chip).",
    ),
    19: (
        [("/puzzles", "click", {}), ("/daily", "click", {})],
        "Today's Daily Puzzle is 'Discover Your Gift', dated September 22, 2026, and its stated "
        "goal is 'Win material'.",
    ),
    20: (
        [("/puzzles/archive?page=19", "click", {}), ("/puzzles/problem/73", "click", {})],
        "The 2025-03-15 puzzle page shows Puzzle #12976. Its details panel shows the theme "
        "'Tactics', and its solution line starts with the first move 1. Qc4+.",
    ),
    21: (
        [("/search?q=Gukesh", "click", {})],
        "Searching for 'Gukesh' returns exactly one lesson course: 'Play Like Gukesh "
        "Dommaraju'. The News section of the results page contains 11 articles in total.",
    ),
    22: (
        [("/clubs", "click", {})],
        "The three clubs with the most members, in order, are: Chess.com - India (296,915 "
        "members), Chess.com Community (166,207 members), and Chess School (147,770 members).",
    ),
    23: (
        "bob",
        [("/club/chess-school", "click", {})],
        "I joined the Chess School club. Its page shows a member count of 147,770 and the club "
        "description names Evergreen_Warrior as the Super Admin.",
    ),
    24: (
        "carol",
        [("/settings", "fill", {"text": "Berlin, Germany", "selector": "input[name=location]"})],
        "I set my location to 'Berlin, Germany' and saved. The settings page now shows the "
        "exact location text 'Berlin, Germany'.",
    ),
    25: (
        "david",
        [("/puzzles", "click", {})],
        "I solved the puzzle shown in the trainer. The feedback text the trainer displays "
        "once solved is 'Correct! Well played.' and the goal stated for that puzzle is 'Win material'.",
    ),
    26: (
        [("/games", "click", {}), ("/games/magnus-carlsen", "click", {})],
        "Magnus Carlsen's games page shows a total of 6,806 games, and his 'As White' win "
        "stat is 61%.",
    ),
    27: (
        [("/games/hikaru-nakamura", "click", {}), ("/games/view/18242674", "click", {})],
        "The most recent game is Hikaru Nakamura vs Anastasia Avramidou. The opening is the "
        "Indian Game: Yusupov-Rubinstein System and the result is 1-0.",
    ),
    28: (
        [("/events", "click", {})],
        "The first three events are the FIDE World Rapid Chess Championship 2022, the FIDE "
        "Women's World Rapid Chess Championship 2022, and the FIDE World Blitz Chess "
        "Championship 2022. The first event starts on 2022-12-25 and has 178 players.",
    ),
    29: (
        "david",
        [("/lessons/gambit-buffet", "click", {})],
        "I marked all of the 'Gambit Buffet' lessons complete. The course page now shows the "
        "progress text 'Your progress: 16/16 lessons completed.'",
    ),
}

LOGIN_USERNAMES = {"alice": ("alice.j@test.com", "alice_j"), "bob": ("bob.c@test.com", "bob_c"),
                   "carol": ("carol.d@test.com", "carol_d"), "david": ("david.k@test.com", "david_k")}

# after-DB mutations for the honest stateful runs: (sql, params) lists
HONEST_MUTATIONS = {
    8: [("INSERT INTO follows (follower_id, followed_id, created_at) VALUES (1176, 279, '2026-09-22T12:00:00+00:00')", ())],
    23: [("INSERT INTO club_memberships (user_id, club_id, joined_at) VALUES (1177, 15, '2026-09-22T12:00:00+00:00')", ())],
    24: [("UPDATE users SET location = 'Berlin, Germany' WHERE id = 1178", ())],
    25: [],  # unrated solve records nothing; a rated variant is covered separately
    29: [("INSERT INTO lesson_progress (user_id, course_id, lessons_done, completed_at) "
          "VALUES (1179, 4, 16, '2026-09-22T12:00:00+00:00')", ())],
}

# ---------------------------------------------------------------- helpers
def snapshots(tmp_path, mutations=()):
    initial = copy_db(tmp_path / "initial.db")
    after = copy_db(tmp_path / "after.db")
    if mutations:
        mutate_db(after, [m if len(m) == 2 else (m[0], ()) for m in mutations])
    return initial, after


def honest_run(tmp_path, n):
    spec = HONEST[n]
    if n in STATEFUL:
        login_key, steps, answer = spec
        login = LOGIN_USERNAMES[login_key]
    else:
        steps, answer = spec
        login = None
    run_dir = tmp_path / f"run{n}_honest"
    run_dir.mkdir()
    build_run(run_dir, f"Chess.com--{n}", steps, answer, login=login)
    initial, after = snapshots(tmp_path, HONEST_MUTATIONS.get(n, []))
    return run_dir, initial, after


@pytest.fixture()
def noop_run(tmp_path):
    run_dir = tmp_path / "run_noop"
    run_dir.mkdir()
    b = RunBuilder(run_dir, "Chess.com--0")
    b.step("/", "noop", {})
    b.done("")
    b.write()
    initial, after = snapshots(tmp_path)
    return run_dir, initial, after


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("n", range(30), ids=[f"task{n:02d}" for n in range(30)])
def test_honest_run_passes(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=1)[:2000]
    assert verdict["_returncode"] == 0


def test_stateful_rated_solve_variant_passes(tmp_path):
    """T25 in rated mode records a solved attempt — still PASS."""
    run_dir = tmp_path / "run25_rated"
    run_dir.mkdir()
    build_run(run_dir, "Chess.com--25",
              [("/puzzles?mode=rated", "click", {})],
              "I solved the rated puzzle. The trainer displays 'Correct! Well played.' and the "
              "goal stated for the puzzle is 'Win material'.",
              login=LOGIN_USERNAMES["david"])
    initial, after = snapshots(tmp_path, [
        ("INSERT INTO puzzle_attempts (user_id, puzzle_id, solved, used_hint, rating_before, "
         "rating_after, attempted_at) VALUES (1179, 1, 1, 0, 1800, 1820, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(25, run_dir, initial, after)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=1)[:2000]


# ---------------------------------------------------------------- no-op FAIL (every task)
@pytest.mark.parametrize("n", range(30), ids=[f"task{n:02d}" for n in range(30)])
def test_noop_run_fails(tmp_path, n):
    run_dir = tmp_path / "run_noop"
    run_dir.mkdir()
    b = RunBuilder(run_dir, f"Chess.com--{n}")
    b.step("/", "noop", {})
    b.done("")
    b.write()
    initial, after = snapshots(tmp_path)
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert verdict["_returncode"] == 1


# ---------------------------------------------------------------- wrong answer FAIL
WRONG_ANSWERS = {
    0: "The player ranked #3 is MagnusCarlsen with rating 3000 and 999 wins.",
    1: "GMBrewChess appears in both top-3 lists; the #1 Bullet rating is 3500.",
    2: "5 of the top 10 are from the United States: Hikaru and gurelediz.",
    3: "The player ranked #50 is denghao with a rating of 2700.",
    4: "The #1 is Hikaru with 4394; #5 is petergrieco with 4300.",
    5: "His real name is Magnus Carlson, with 300,000 followers and Rapid 2900.",
    6: "Firouzja2003 is from Iran and has 30,000 followers.",
    7: "The first three GMs are GMKrikor, Hikaru, and MagnusCarlsen; the WGM section lists 3 players.",
    8: "My settings page shows I am following 3 members.",
    9: "The Cairns Cup winner took home $50,000 in prize money and won the tournament with a score of 6 points.",
    10: "It was published on 2026-09-02 by anthonylevin in the misc category.",
    11: "The author is colin_mcgourty and his real name is Chichi Onyekwere.",
    12: "The Misc category lists 4 articles; the most recent is 'Nakamura Makes It Back-To-Back Bullet Brawls'.",
    13: "Page 2 shows 10 cards and the first article is 'U.S. Wins 3.5-0.5 In Both Sections'.",
    14: "The Sicilian Defense is ECO B30 with 500,000 games and starts 1.d4 Nf6.",
    15: "The Caro-Kann Defense has the higher count: 187,337 versus the French Defense's 262,713.",
    16: "The top three are Vasily Smyslov, Viswanathan Anand, and Maxime Vachier-Lagrave.",
    17: "Gambit Buffet has 12 lessons by GM Dejan Bojkov at the Intermediate level.",
    18: "The course has 8 lessons and appears under the Openings category filter.",
    19: "The Daily Puzzle is 'Tactical Slow Clap' dated 2026-09-21 with goal 'Checkmate'.",
    20: "The 2025-03-15 puzzle page shows Puzzle #12800, its details panel shows the theme 'Endgame', and its solution starts with the move 1. h4.",
    21: "The search returns the lesson 'Gambit Buffet' and 5 news articles.",
    22: "The top three clubs are Chess School (296,915), Chess.com Community (166,207), Chess.com - India (147,770).",
    23: "The club has 80,000 members and the Super Admin is chesscom.",
    24: "The settings page now shows the location text 'Paris, France'.",
    25: "The trainer displays 'Solved!' and the goal is 'Checkmate'.",
    26: "The page shows 9,765 games and a 50% win rate as White.",
    27: "The game is Hikaru Nakamura vs Sergei Zhigalko, a Sicilian Defense, drawn 0.5-0.5.",
    28: "The first three events are all 2026 championships; the first starts Dec 25, 2026 with 98 players.",
    29: "The course page shows 'Your progress: 15/16 lessons completed.'",
}


@pytest.mark.parametrize("n", range(30), ids=[f"task{n:02d}" for n in range(30)])
def test_wrong_answer_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    # rewrite only the final answer with the wrong one
    traj_path = run_dir / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["final_answer"] = WRONG_ANSWERS[n]
    traj_path.write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert verdict.get("reason", "") != ""


# ---------------------------------------------------------------- shortcut FAIL (no navigation)
@pytest.mark.parametrize("n", range(30), ids=[f"task{n:02d}" for n in range(30)])
def test_shortcut_fails(tmp_path, n):
    """Correct final answer, but the agent never left the homepage: MUST FAIL."""
    run_dir, initial, after = honest_run(tmp_path, n)
    traj_path = run_dir / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    homepage = BASE + "/"
    for step in traj["steps"]:
        step["url"] = homepage
        step.pop("url_after", None)
    traj["final_url"] = homepage
    traj_path.write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "visited" in verdict.get("reason", "") or "signed" in verdict.get("reason", "")


# ---------------------------------------------------------------- read-only DB tamper FAIL
@pytest.mark.parametrize("n", READ_ONLY, ids=[f"task{n:02d}" for n in READ_ONLY])
def test_readonly_db_tamper_fails(tmp_path, n):
    run_dir, initial, after = honest_run(tmp_path, n)
    mutate_db(after, [("INSERT INTO follows (follower_id, followed_id, created_at) "
                       "VALUES (1179, 279, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(n, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "read_only" in verdict.get("reason", "")


# ---------------------------------------------------------------- stateful mismatches
def test_t8_state_mismatch_fails(tmp_path):
    """Alice self-reports the follow but the DB is unchanged: FAIL."""
    run_dir, initial, after = honest_run(tmp_path, 8)
    shutil.copyfile(initial, after)  # undo the honest mutation
    verdict = run_verifier(8, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "follows_exact_delta" in verdict.get("reason", "")


def test_t8_wrong_follow_target_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [("DELETE FROM follows WHERE follower_id = 1176 AND followed_id = 279", ()),
                      ("INSERT INTO follows (follower_id, followed_id, created_at) "
                       "VALUES (1176, 246, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(8, run_dir, initial, after)
    assert verdict.get("pass") is False


def test_t8_collateral_write_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 8)
    mutate_db(after, [("UPDATE users SET location = 'Oops' WHERE id = 1179", ())])
    verdict = run_verifier(8, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "no_collateral_writes" in verdict.get("reason", "")


def test_t23_state_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 23)
    shutil.copyfile(initial, after)
    verdict = run_verifier(23, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "club_membership_exact_delta" in verdict.get("reason", "")


def test_t24_state_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 24)
    shutil.copyfile(initial, after)
    verdict = run_verifier(24, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "carol_location_exact_delta" in verdict.get("reason", "")


def test_t24_wrong_location_value_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 24)
    mutate_db(after, [("UPDATE users SET location = 'Berlin' WHERE id = 1178", ())])
    verdict = run_verifier(24, run_dir, initial, after)
    assert verdict.get("pass") is False


def test_t24_collateral_change_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 24)
    mutate_db(after, [("UPDATE users SET name = 'Wrong Name' WHERE id = 1178", ())])
    verdict = run_verifier(24, run_dir, initial, after)
    assert verdict.get("pass") is False


def test_t25_collateral_write_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 25)
    mutate_db(after, [("INSERT INTO follows (follower_id, followed_id, created_at) "
                       "VALUES (1179, 279, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(25, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "no_collateral_writes" in verdict.get("reason", "")


def test_t25_foreign_attempt_fails(tmp_path):
    """Attempt rows belong to someone other than david: FAIL."""
    run_dir, initial, after = honest_run(tmp_path, 25)
    mutate_db(after, [("INSERT INTO puzzle_attempts (user_id, puzzle_id, solved, used_hint, "
                       "rating_before, rating_after, attempted_at) "
                       "VALUES (1178, 1, 1, 0, 1800, 1820, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(25, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "puzzle_attempts_only_david" in verdict.get("reason", "")


def test_t29_state_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 29)
    shutil.copyfile(initial, after)
    verdict = run_verifier(29, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "lesson_progress_exact_delta" in verdict.get("reason", "")


def test_t29_wrong_progress_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 29)
    mutate_db(after, [("UPDATE lesson_progress SET lessons_done = 9 WHERE user_id = 1179", ())])
    verdict = run_verifier(29, run_dir, initial, after)
    assert verdict.get("pass") is False


# ---------------------------------------------------------------- T15 comparison-direction regressions
# The direction check must accept any honest phrasing that attributes the upward
# comparative to the French Defense (or the downward one to the Caro-Kann Defense)
# in its own sentence — including answers that state both numbers first — while
# still rejecting reversed comparisons.
def _t15_with_answer(tmp_path, answer):
    run_dir, initial, after = honest_run(tmp_path, 15)
    traj_path = run_dir / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["final_answer"] = answer
    traj_path.write_text(json.dumps(traj, indent=2))
    return run_dir, initial, after


def test_t15_both_named_before_comparative_passes(tmp_path):
    """Audit-walk phrasing: both openings named in the preamble, then
    'so the French Defense has the higher Games Played count' — the
    comparative's sentence attributes 'higher' to the French Defense."""
    run_dir, initial, after = _t15_with_answer(
        tmp_path,
        "The French Defense has 262,713 games played and the Caro-Kann Defense has "
        "187,337 games played, so the French Defense has the higher Games Played count.")
    verdict = run_verifier(15, run_dir, initial, after)
    assert verdict.get("pass") is True, verdict


def test_t15_mixed_up_and_down_passes(tmp_path):
    """Both an upward and a downward comparative, each correctly attributed."""
    run_dir, initial, after = _t15_with_answer(
        tmp_path,
        "The French Defense has more games (262,713); the Caro-Kann Defense has fewer "
        "(187,337).")
    verdict = run_verifier(15, run_dir, initial, after)
    assert verdict.get("pass") is True, verdict


def test_t15_downward_attribution_passes(tmp_path):
    """The Caro-Kann Defense named as the lower count in its own sentence."""
    run_dir, initial, after = _t15_with_answer(
        tmp_path,
        "262,713 games for the French Defense against 187,337 for the Caro-Kann Defense: "
        "the Caro-Kann Defense has the lower Games Played count.")
    verdict = run_verifier(15, run_dir, initial, after)
    assert verdict.get("pass") is True, verdict


def test_t15_reversed_direction_fails(tmp_path):
    """Attributing the upward comparative to the Caro-Kann Defense is reversed."""
    run_dir, initial, after = _t15_with_answer(
        tmp_path,
        "The French Defense has 262,713 games played and the Caro-Kann Defense has "
        "187,337 games played, so the Caro-Kann Defense has the higher Games Played count.")
    verdict = run_verifier(15, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "answer_names_french_as_higher" in verdict.get("reason", "")


def test_t15_reversed_via_downward_fails(tmp_path):
    """Calling the French Defense the lower count is also a reversal."""
    run_dir, initial, after = _t15_with_answer(
        tmp_path,
        "The French Defense has 262,713 games played and the Caro-Kann Defense has "
        "187,337 games played, so the French Defense has the lower Games Played count.")
    verdict = run_verifier(15, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "answer_names_french_as_higher" in verdict.get("reason", "")



# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj_path = run_dir / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["task_id"] = "Chess.com--1"
    traj_path.write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "trajectory_task_matches" in verdict.get("reason", "")


def test_offsite_url_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    traj_path = run_dir / "trajectory.json"
    traj = json.loads(traj_path.read_text())
    traj["steps"][0]["url"] = "http://example.com/leaderboard/live"
    traj_path.write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "all_urls_match_local_origin" in verdict.get("reason", "")


def test_broken_screenshot_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    shot = run_dir / "screenshots" / "step_001.png"
    shot.write_bytes(b"this is not a png at all")
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "screenshots_decode" in verdict.get("reason", "")


def test_missing_trajectory_fails_closed(tmp_path):
    run_dir = tmp_path / "run_missing"
    run_dir.mkdir()
    initial, after = snapshots(tmp_path)
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "trajectory_unavailable"


def test_missing_screenshot_fails(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert "screenshots_decode" in verdict.get("reason", "")


def test_tampered_seed_fails_closed(tmp_path):
    """A doctored initial.db (not the frozen seed) must fail closed for every task."""
    run_dir, initial, after = honest_run(tmp_path, 0)
    mutate_db(initial, [("INSERT INTO follows (follower_id, followed_id, created_at) "
                         "VALUES (1179, 246, '2026-09-22T12:00:00+00:00')", ())])
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "snapshot_contract_invalid"


def test_wrong_site_schema_fails_closed(tmp_path):
    run_dir, initial, after = honest_run(tmp_path, 0)
    con = sqlite3.connect(str(initial))
    con.execute("CREATE TABLE sneaky_table (id INTEGER PRIMARY KEY, x TEXT)")
    con.execute("INSERT INTO sneaky_table (x) VALUES ('nope')")
    con.commit()
    con.close()
    verdict = run_verifier(0, run_dir, initial, after)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "snapshot_contract_invalid"


def test_missing_dbs_fail_closed(tmp_path):
    run_dir, initial, _ = honest_run(tmp_path, 0)
    verdict = run_verifier(0, run_dir, tmp_path / "initial_missing.db", tmp_path / "after_missing.db")
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "database_unavailable"
