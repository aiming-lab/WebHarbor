"""Deterministic verifier contract tests for the 21 NFL tasks (r2 sync).

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a
wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
navigation) MUST FAIL: every task's required surface is beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(task_id mismatch, off-site URLs, missing screenshots, non-done trajectory)
MUST fail closed.

r2 sync: honest fixtures re-written for the 20 redesigned tasks from the
reviewer's independent live walkthroughs (answers verified against the
rendered pages of the rereview container); NFL--1 keeps its r1 fixture
(task text unchanged). STATEFUL now includes NFL--15 (the plan switch).
No LLM: snapshots are seed copies mutated through sqlite, trajectories are
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
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, mutate_db, noop_run,
                       run_verifier)

STATEFUL = {0, 1, 2, 12, 15, 20}
READ_ONLY = sorted(set(range(21)) - STATEFUL)
CREATED = "2026-09-24 14:30:00.000000"


def _seed():
    return _acquire_seed()


# ---------------------------------------------------------------- honest fixtures
def honest_run_00(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 0: Bob -> Premium Annual + newsletter on + My Team read. After-DB:
    Bob's monthly subscription cancelled, a new active Premium Annual
    subscription (id 4), one order row NFL-47C7FF, Bob's users row flips
    newsletter 0 -> 1."""
    seed = _seed()
    b = build_run(tmp, "honest_00", "NFL--0")
    b.login("bob.c@test.com")
    b.step("/plus/", "goto", {})
    b.step("/plus/subscribe/nfl_plus_premium_annual/", "click",
           {"selector": "a[href*='nfl_plus_premium_annual']"})
    b.fill("/plus/subscribe/nfl_plus_premium_annual/", "Bob Chen", "input[name=cardholder]")
    b.fill("/plus/subscribe/nfl_plus_premium_annual/", "4242424242424242", "input[name=card_number]")
    b.fill("/plus/subscribe/nfl_plus_premium_annual/", "12", "input[name=exp_month]")
    b.fill("/plus/subscribe/nfl_plus_premium_annual/", "2029", "input[name=exp_year]")
    b.fill("/plus/subscribe/nfl_plus_premium_annual/", "123", "input[name=cvv]")
    b.step("/plus/subscribe/nfl_plus_premium_annual/", "click", {"selector": "button[type=submit]"},
           url_after="/plus/confirmation/NFL-47C7FF")
    b.step("/account/", "goto", {})
    b.step("/account/edit/", "click", {"selector": "a[href*='/account/edit/']"})
    b.fill("/account/edit/", "on", "input[name=newsletter]")
    b.step("/account/edit/", "click", {"selector": "button[type=submit]"}, url_after="/account/")
    b.step("/", "goto", {})
    b.done("Bob is now on NFL+ Premium Annual. The order reference is NFL-47C7FF and the "
           "total charged was $108.94 ($99.99 plus $8.95 tax). The account shows NFL+ "
           "Premium Annual renews September 24, 2027. My Team: the Packers (1-1) host the "
           "Falcons THU 8:15pm ET. The newsletter is now on.",
           final_path="/")
    after = mutate_db(seed, tmp / "honest_00" / "after.db", [
        ("UPDATE users SET newsletter=1 WHERE id=2", ()),
        ("UPDATE subscriptions SET status='cancelled' WHERE id=1", ()),
        ("INSERT INTO subscriptions (id, user_id, plan_code, plan_title, cycle, amount, "
         "status, started_at, renews_at) VALUES (4, 2, 'nfl_plus_premium_annual', "
         "'NFL+ Premium Annual', 'year', 99.99, 'active', ?, '2027-09-24 00:00:00.000000')",
         (CREATED,)),
        ("INSERT INTO plus_orders (id, user_id, order_ref, plan_code, plan_title, cycle, "
         "amount, tax, total, card_last4, cardholder, created_at, status) VALUES "
         "(3, 2, 'NFL-47C7FF', 'nfl_plus_premium_annual', 'NFL+ Premium Annual', 'year', "
         "99.99, 8.95, 108.94, '4242', 'Bob Chen', ?, 'complete')", (CREATED,)),
    ])
    return tmp / "honest_00", seed, after


def honest_run_01(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 1 (text unchanged from the contribution): register Emma (favorite
    CHI) -> NFL+ Monthly checkout -> confirmation -> account page for the
    renewal date. After-DB: +1 user, +1 subscription (renews 2026-10-24), +1
    order NFL-D0768F ($7.62)."""
    seed = _seed()
    b = build_run(tmp, "honest_01", "NFL--1")
    b.step("/account/signup/", "goto", {})
    b.fill("/account/signup/", "Emma Sister", "input[name=display_name]")
    b.fill("/account/signup/", "emma.sister@example.com", "input[name=email]")
    b.fill("/account/signup/", "SisterPass123!", "input[name=password]")
    b.step("/account/signup/", "select", {"value": "CHI", "selector": "select[name=favorite_team]"})
    b.step("/account/signup/", "click", {"selector": "button[type=submit]"}, url_after="/account/")
    b.step("/plus/", "goto", {})
    b.step("/plus/subscribe/nfl_plus_monthly/", "click", {"selector": "a[href*='nfl_plus_monthly']"})
    b.fill("/plus/subscribe/nfl_plus_monthly/", "Emma Sister", "input[name=cardholder]")
    b.fill("/plus/subscribe/nfl_plus_monthly/", "5555555555554444", "input[name=card_number]")
    b.fill("/plus/subscribe/nfl_plus_monthly/", "11", "input[name=exp_month]")
    b.fill("/plus/subscribe/nfl_plus_monthly/", "2029", "input[name=exp_year]")
    b.fill("/plus/subscribe/nfl_plus_monthly/", "321", "input[name=cvv]")
    b.step("/plus/subscribe/nfl_plus_monthly/", "click", {"selector": "button[type=submit]"},
           url_after="/plus/confirmation/NFL-D0768F")
    b.step("/account/", "goto", {})
    b.done("Emma's NFL+ Monthly subscription is active. The order reference is NFL-D0768F, "
           "the total charged was $7.62 ($6.99 plus $0.63 tax), and it renews on "
           "October 24, 2026.", final_path="/account/")
    after = mutate_db(seed, tmp / "honest_01" / "after.db", [
        ("INSERT INTO users (id, email, password_hash, display_name, username, favorite_team, "
         "newsletter, created_at) VALUES (5, 'emma.sister@example.com', 'x', 'Emma Sister', "
         "'emma.sister', 'CHI', 0, ?)", (CREATED,)),
        ("INSERT INTO subscriptions (id, user_id, plan_code, plan_title, cycle, amount, "
         "status, started_at, renews_at) VALUES (4, 5, 'nfl_plus_monthly', 'NFL+ Monthly', "
         "'month', 6.99, 'active', ?, '2026-10-24 00:00:00.000000')", (CREATED,)),
        ("INSERT INTO plus_orders (id, user_id, order_ref, plan_code, plan_title, cycle, "
         "amount, tax, total, card_last4, cardholder, created_at, status) VALUES "
         "(3, 5, 'NFL-D0768F', 'nfl_plus_monthly', 'NFL+ Monthly', 'month', 6.99, 0.63, "
         "7.62, '4444', 'Emma Sister', ?, 'complete')", (CREATED,)),
    ])
    return tmp / "honest_01", seed, after


def honest_run_02(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 2: Carol cancels, switches the newsletter on, sets a new password,
    signs out and back in. After-DB: subscription id 2 -> cancelled; Carol's
    users row changes (newsletter + new password hash)."""
    seed = _seed()
    b = build_run(tmp, "honest_02", "NFL--2")
    b.login("carol.d@test.com")
    b.step("/account/", "goto", {})
    b.step("/account/cancel-subscription/", "click", {"selector": "form[action*='cancel'] button"})
    b.step("/account/edit/", "goto", {})
    b.fill("/account/edit/", "on", "input[name=newsletter]")
    b.fill("/account/edit/", "CarolFan2026!", "input[name=new_password]")
    b.step("/account/edit/", "click", {"selector": "button[type=submit]"}, url_after="/account/")
    b.step("/account/signout/", "goto", {})
    b.step("/account/signin/", "goto", {})
    b.fill("/account/signin/", "carol.d@test.com", "input[name=email]")
    b.fill("/account/signin/", "CarolFan2026!", "input[name=password]")
    b.step("/account/signin/", "click", {"selector": "button[type=submit]"}, url_after="/account/")
    b.step("/", "goto", {})
    b.done("Carol was on NFL+ Annual at $49.99 per year. Her original order reference is "
           "NFL-03NUAL and it totaled $54.46. After cancelling, her subscription section "
           "shows no active NFL+ subscription. The newsletter is on, and the new password "
           "works (signed out and back in). My Team: the Cowboys (1-1) host the Ravens "
           "INTL SUN 4:25pm ET.",
           final_path="/")
    after = mutate_db(seed, tmp / "honest_02" / "after.db", [
        ("UPDATE subscriptions SET status='cancelled' WHERE id=2", ()),
        ("UPDATE users SET newsletter=1, password_hash='newhash' WHERE id=3", ()),
    ])
    return tmp / "honest_02", seed, after


def honest_run_03(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_03", "NFL--3")
    b.step("/", "goto", {})
    b.step("/stats/", "click", {"selector": "a[href='/stats/']"})
    b.step("/stats/rushing/", "click", {"selector": "a[href='/stats/rushing/']"})
    b.step("/players/kenneth-walker-iii/", "click", {"selector": "a"})
    b.step("/teams/kansas-city-chiefs/", "click", {"selector": "a"})
    b.step("/games/chiefs-at-dolphins-2026-reg-3/", "click", {"selector": "a"})
    b.step("/stats/", "click", {"selector": "a[href='/stats/']"})
    b.step("/stats/rushing/", "click", {"selector": "a[href='/stats/rushing/']"})
    b.step("/players/derrick-henry/", "click", {"selector": "a"})
    b.step("/teams/baltimore-ravens/", "click", {"selector": "a"})
    b.step("/games/ravens-at-cowboys-2026-reg-3/", "click", {"selector": "a"})
    b.step("/stats/", "click", {"selector": "a[href='/stats/']"})
    b.step("/stats/passing/", "click", {"selector": "a[href='/stats/passing/']"})
    b.step("/injuries/", "click", {"selector": "a[href='/injuries/']"})
    b.step("/", "click", {"selector": "a[href='/']"})
    b.step("/standings/", "click", {"selector": "a[href='/standings/']"})
    b.done("Top two rushers: Kenneth Walker III (Chiefs) 290 rush yds, 47 att (6.2 y/a), 1 TD; "
           "Derrick Henry (Ravens) 212 yds, 40 att (5.3 y/a), 4 TDs. Walker: #9, 211 lbs, "
           "Michigan State; Henry: #22, 252 lbs, Alabama. Coaches/stadiums: Chiefs — Andy Reid, "
           "Arrowhead Stadium; Ravens — Jesse Minter, M&T Bank Stadium. QB passing ranks: "
           "Mahomes 5th with 566 yds; Lamar Jackson 6th with 559 yds. W3: Chiefs at Dolphins, "
           "SUN Sep 27 1:00pm ET, Hard Rock Stadium (KC 2-0, MIA 0-2; diffs +24/-36); Ravens at "
           "Cowboys (INTL) SUN 4:25pm ET, Maracana Stadium (BAL 1-1, DAL 1-1; diffs +11/+9). "
           "Mahomes IS on the W3 injury report (Full Participation in Practice); no Ravens QB "
           "is listed.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_03" / "initial.db")
    copy_db(seed, tmp / "honest_03" / "after.db")
    return tmp / "honest_03", seed, seed


def honest_run_04(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_04", "NFL--4")
    b.step("/standings/", "goto", {})
    b.step("/scores/2026/REG3/", "goto", {})
    b.step("/games/chargers-at-bills-2026-reg-3/", "click", {"selector": "a"})
    b.step("/scores/2026/REG4/", "goto", {})
    b.step("/games/patriots-at-bills-2026-reg-4/", "click", {"selector": "a"})
    b.step("/scores/2026/REG1/", "goto", {})
    b.step("/scores/2026/REG2/", "goto", {})
    b.step("/standings/", "goto", {})
    b.step("/teams/los-angeles-chargers/", "click", {"selector": "a"})
    b.step("/standings/", "goto", {})
    b.step("/teams/new-england-patriots/", "click", {"selector": "a"})
    b.done("The highest-scoring undefeated team is the Buffalo Bills: 1st AFC East, 2-0, "
           "77 points scored, 62 allowed. W1: won 36-31 at the Texans; W2: beat the Lions "
           "41-31. Next two: W3 vs the Chargers (SUN 1:00pm, Highmark Stadium; LAC 0-2, "
           "-24, Jim Harbaugh, SoFi Stadium) and W4 vs the Patriots (SUN 1:00pm, "
           "Highmark Stadium; NE 1-1, +14, Mike Vrabel, Gillette Stadium).",
           final_path="/teams/new-england-patriots/")
    seed = _seed()
    copy_db(seed, tmp / "honest_04" / "initial.db")
    copy_db(seed, tmp / "honest_04" / "after.db")
    return tmp / "honest_04", seed, seed


def honest_run_05(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_05", "NFL--5")
    for w in (1, 3, 4, 5, 6, 7, 9, 10, 11):
        b.step(f"/scores/2026/REG{w}/", "goto", {})
    b.step("/games/49ers-at-rams-2026-reg-1/", "click", {"selector": "a"})
    b.step("/standings/", "goto", {})
    b.done("International games by week: W1 49ers at Rams (Melbourne, INTL THU 8:35pm — "
           "played); W3 Ravens at Cowboys (Rio de Janeiro, INTL SUN 4:25pm); W4 Colts at "
           "Commanders (London); W5 Eagles at Jaguars (London); W6 Texans at Jaguars "
           "(London); W7 Steelers at Saints (Saint-Denis); W9 Bengals at Falcons (Madrid); "
           "W10 Patriots at Lions (Munich); W11 Vikings at 49ers (Mexico City, 8:20pm). "
           "The played one: 49ers won 27-7, attendance 100,021, Melbourne Cricket Ground, "
           "East Melbourne, on Netflix. Records now: 49ers 2-0, Rams 1-1.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_05" / "initial.db")
    copy_db(seed, tmp / "honest_05" / "after.db")
    return tmp / "honest_05", seed, seed


def honest_run_06(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_06", "NFL--6")
    b.step("/injuries/", "goto", {})
    b.step("/scores/2026/REG3/", "goto", {})
    b.step("/games/falcons-at-packers-2026-reg-3/", "click", {"selector": "a"})
    b.step("/teams/green-bay-packers/roster/?position=WR", "goto", {})
    b.step("/teams/atlanta-falcons/roster/?position=DE", "goto", {})
    b.step("/teams/green-bay-packers/", "goto", {})
    b.step("/teams/atlanta-falcons/", "goto", {})
    b.done("OUT: Samson Ebukam (ATL DE, hamstring), Aaron Banks (GB G, knee/toe), Warren "
           "Brinson (GB DT, calf), Jayden Reed (GB WR, neck), Zach Bako-Bewele (GB T, "
           "knee). QUESTIONABLE: Billy Bowman Jr. (ATL CB, Achilles), Anthony Campbell "
           "(GB DT, ankle), Javon Hargrave (GB DT, knee/concussion). Game: THU 8:15pm ET, "
           "Lambeau Field, ATL 0-2 vs GB 1-1. Reed: #11, 5-11, 187, Michigan State. "
           "Ebukam: #52, 6-3, 245, Eastern Washington. Kevin Stefanski / Mercedes-Benz "
           "Stadium; Matt LaFleur / Lambeau Field.",
           final_path="/teams/atlanta-falcons/")
    seed = _seed()
    copy_db(seed, tmp / "honest_06" / "initial.db")
    copy_db(seed, tmp / "honest_06" / "after.db")
    return tmp / "honest_06", seed, seed


def honest_run_07(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_07", "NFL--7")
    b.step("/teams/green-bay-packers/roster/?position=WR", "goto", {})
    b.step("/players/jayden-reed/", "click", {"selector": "a"})
    b.step("/teams/atlanta-falcons/roster/?position=WR", "goto", {})
    b.step("/injuries/", "goto", {})
    b.step("/games/falcons-at-packers-2026-reg-3/", "goto", {})
    b.step("/teams/green-bay-packers/", "goto", {})
    b.step("/teams/atlanta-falcons/", "goto", {})
    b.done("Packers active WRs under 200 lbs: Jayden Reed (#11, 5-11, 187, 4 yrs, Michigan "
           "State), Bo Melton (no number, 5-11, 189, 3 yrs, Rutgers), Matthew Golden (no "
           "number, 5-11, 191, 2 yrs, Texas), Skyy Moore (#23, 5-10, 195, 5 yrs, Western "
           "Michigan). Falcons active WRs under 200 lbs: Zachariah Branch (#17, 5-10, 180, "
           "R, Georgia), Jahan Dotson (#4, 5-11, 184, 5 yrs, Penn State), Olamide "
           "Zaccheaus (#14, 5-8, 194, 8 yrs, Virginia). Cross-check: Jayden Reed is OUT "
           "(neck); his player page lists WR / Michigan State. Game: THU 8:15pm ET, Lambeau "
           "Field; ATL 0-2 (Kevin Stefanski), GB 1-1 (Matt LaFleur).",
           final_path="/teams/atlanta-falcons/")
    seed = _seed()
    copy_db(seed, tmp / "honest_07" / "initial.db")
    copy_db(seed, tmp / "honest_07" / "after.db")
    return tmp / "honest_07", seed, seed


def honest_run_08(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_08", "NFL--8")
    b.step("/", "goto", {})
    b.step("/players/active/all", "click", {"selector": "a[href='/players/active/all']"})
    b.fill("/players/active/all?query=Barkley", "Barkley", "input[name=query]")
    b.step("/players/active/all?query=Barkley", "click", {"selector": "button[type=submit]"})
    b.step("/players/saquon-barkley/", "click", {"selector": "a"})
    b.step("/teams/philadelphia-eagles/", "click", {"selector": "a"})
    b.step("/teams/philadelphia-eagles/roster/", "click", {"selector": "a"})
    b.step("/teams/philadelphia-eagles/roster/?position=RB", "select",
           {"value": "RB", "selector": "select[name=position]"})
    b.step("/teams/philadelphia-eagles/roster/?position=RB", "click",
           {"selector": "button[type=submit]"})
    b.step("/teams/philadelphia-eagles/roster/?position=QB", "select",
           {"value": "QB", "selector": "select[name=position]"})
    b.step("/teams/philadelphia-eagles/roster/?position=QB", "click",
           {"selector": "button[type=submit]"})
    b.step("/scores/", "click", {"selector": "a[href='/scores/']"})
    b.step("/scores/2026/REG2/", "click", {"selector": "a[href='/scores/2026/REG2/']"})
    b.step("/games/eagles-at-bears-2026-reg-3/", "click", {"selector": "a"})
    b.step("/teams/chicago-bears/", "click", {"selector": "a"})
    b.done("Saquon Barkley: #26, 6-0, 232 lbs, 9 years experience, Penn State. Eagles: head coach "
           "Nick Sirianni, home stadium Lincoln Financial Field, 2-0 and 1st in the NFC East. "
           "Other active RBs: Will Shipley (#28), Tank Bigsby (#8). Active QBs: Jalen Hurts "
           "(#1), Andy Dalton (#14), Tanner McKee (#16), Cole Payton (#18). Week 2 final: "
           "Eagles won 24-20 at the Titans. Week 3 MNF: Eagles at Bears, MON Sep 28 8:15pm "
           "ET, Soldier Field. Bears: head coach Ben Johnson, home stadium Soldier Field.",
           final_path="/teams/chicago-bears/")
    seed = _seed()
    copy_db(seed, tmp / "honest_08" / "initial.db")
    copy_db(seed, tmp / "honest_08" / "after.db")
    return tmp / "honest_08", seed, seed


def honest_run_09(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_09", "NFL--9")
    b.step("/", "goto", {})
    b.step("/transactions/", "click", {"selector": "a[href='/transactions/']"})
    b.step("/transactions/?category=Reserve%20List", "click", {"selector": "a"})
    b.step("/transactions/?category=Waivers", "click", {"selector": "a"})
    b.step("/news/", "click", {"selector": "a[href='/news/']"})
    b.step("/news/?page=2", "click", {"selector": "a"})
    b.step("/news/?page=3", "click", {"selector": "a"})
    b.step("/news/te-zach-ertz-reuniting-with-eagles-signing-to-philadelphia-s-practice-squad/",
           "click", {"selector": "a"})
    b.step("/players/active/all", "click", {"selector": "a[href='/players/active/all']"})
    b.fill("/players/active/all?query=Hekker", "Hekker", "input[name=query]")
    b.step("/players/active/all?query=Hekker", "click", {"selector": "button[type=submit]"})
    b.step("/players/johnny-hekker/", "click", {"selector": "a"})
    b.step("/teams/minnesota-vikings/", "click", {"selector": "a"})
    b.step("/teams/minnesota-vikings/schedule/", "click", {"selector": "a"})
    b.step("/", "click", {"selector": "a[href='/']"})
    b.step("/standings/", "click", {"selector": "a[href='/standings/']"})
    b.done("Sept 23 practice-squad signings (15): Hardy (Jets), Loudermilk (Jets, veteran), "
           "Hekker (Vikings, veteran), Anderson (Dolphins), Pancol (Colts), Ross (Browns, "
           "veteran), Bachie (Lions, veteran), Harris (Vikings, veteran), Toia (Cardinals), "
           "Meiga (Seahawks), Seumalo (Seahawks), Whitley (Patriots), Moore II (Eagles, "
           "veteran), Johnson (Bills, veteran), Cooks (49ers, veteran). Teams with more "
           "than one: Jets, Vikings, Seahawks. Reserve/Injured that day: McCrary-Ball, "
           "Onyemata, Arian Smith (Jets), Brooks (Panthers), Banks Jr. (Saints), Will "
           "Johnson (Cardinals), Njoku (Chargers), Bradford (Seahawks), Pettus (Patriots), "
           "C.J. West (49ers), Rivers (Rams). Waiver terminations: Gardner (Bears), "
           "Jennings (Chargers), Taimani (Vikings), Estimé (Saints). Ertz article: 'TE Zach "
           "Ertz reuniting with Eagles, signing to Philadelphia's practice squad' by Bobby "
           "Kownack. Hekker: Vikings, P, 15 years experience. Vikings: head coach Kevin "
           "O'Connell, 2-0, 1st NFC North, +23 point differential (48 PF, 25 PA). Week 3: "
           "at the Buccaneers, Sunday September 27, 2026, 4:05pm.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_09" / "initial.db")
    copy_db(seed, tmp / "honest_09" / "after.db")
    return tmp / "honest_09", seed, seed


def honest_run_10(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_10", "NFL--10")
    b.step("/news/", "goto", {})
    b.step("/news/giants-qb-jaxson-dart-season-ending-knee-surgery/", "click", {"selector": "a"})
    b.step("/news/?page=2", "goto", {})
    b.step("/news/?page=3", "goto", {})
    b.step("/news/bears-qb-caleb-williams-considered-week-to-week-after-suffering-hamstring-injury/",
           "click", {"selector": "a"})
    b.step("/search?q=Dart", "goto", {})
    b.step("/news/nfl-network-giants-jaxson-dart-potentially-out-for-season-after-testing-shows-worse-knee-injury/",
           "click", {"selector": "a"})
    b.step("/teams/new-york-giants/", "goto", {})
    b.step("/teams/chicago-bears/", "goto", {})
    b.done("Giants QB Jaxson Dart: knee, season-ending surgery (out for the season) — "
           "'Giants QB Jaxson Dart to undergo season-ending knee surgery' by Kevin Patra, "
           "Sep 23, 2026. Bears QB Caleb Williams: hamstring, 'week to week' — by Kevin "
           "Patra, Sep 21, 2026. Sep 22 report: 'NFL Network: Giants' Jaxson Dart "
           "potentially out for season after testing shows worse knee injury' by Nick "
           "Shook. Giants: John Harbaugh, 1-1, 3rd NFC East, W3 vs Titans. Bears: Ben "
           "Johnson, 1-1, 2nd NFC North, W3 vs Eagles (MNF).",
           final_path="/teams/chicago-bears/")
    seed = _seed()
    copy_db(seed, tmp / "honest_10" / "initial.db")
    copy_db(seed, tmp / "honest_10" / "after.db")
    return tmp / "honest_10", seed, seed


def honest_run_11(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_11", "NFL--11")
    b.step("/videos/", "goto", {})
    b.step("/videos/falcons-vs-packers-week-3-tnf-preview-nfl-daily/", "click", {"selector": "a"})
    b.step("/videos/channel/the-insiders/", "goto", {})
    b.step("/videos/packers-rb-josh-jacobs-has-been-placed-on-the-commissioner-s-exempt-list-the-insiders/",
           "click", {"selector": "a"})
    b.step("/videos/channel/latest-buzz/", "goto", {})
    b.step("/videos/packers-vs-jets-week-2-recap-nfl-daily/", "click", {"selector": "a"})
    b.step("/videos/channel/good-morning-football/", "goto", {})
    b.step("/videos/lb-devin-lloyd-says-week-2-game-vs-falcons-was-most-complete-nfl-game-of-career-gmfb/",
           "click", {"selector": "a"})
    b.step("/videos/channel/game-highlights/", "goto", {})
    b.done('TNF preview: "Falcons vs. Packers Week 3 TNF Preview | NFL Daily" on Latest '
           'Buzz; description: "Gregg Rosenthal, Colleen Wolfe and Nick Shook preview the '
           'Week Thursday Night Football game between the Falcons and Packers". Other W3 '
           'previews on that channel: "Rams vs. Broncos Week 3 Preview | NFL Daily", '
           '"Vikings vs. Buccaneers Week 3 Preview | NFL Daily". Jacobs video: "Packers RB '
           'Josh Jacobs has been placed on the Commissioner\'s Exempt List | \'The '
           'Insiders\'" (The Insiders channel). Packers W2 recap: "Packers vs. Jets Week 2 '
           'Recap | NFL Daily" (Latest Buzz). GMFB: "LB Devin Lloyd says Week 2 game vs. '
           'Falcons was most complete NFL game of career | GMFB". Fewest videos: Latest '
           'Buzz (40; the other three channels list 80 each).',
           final_path="/videos/channel/game-highlights/")
    seed = _seed()
    copy_db(seed, tmp / "honest_11" / "initial.db")
    copy_db(seed, tmp / "honest_11" / "after.db")
    return tmp / "honest_11", seed, seed


def honest_run_12(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_12", "NFL--12")
    b.login("david.k@test.com")
    b.step("/account/edit/", "goto", {})
    b.step("/account/edit/", "select", {"value": "MIA", "selector": "select[name=favorite_team]"})
    b.step("/account/edit/", "click", {"selector": "button[type=submit]"}, url_after="/account/")
    b.step("/", "goto", {})
    b.step("/teams/miami-dolphins/", "goto", {})
    b.step("/teams/miami-dolphins/schedule/", "goto", {})
    b.step("/games/chiefs-at-dolphins-2026-reg-3/", "click", {"selector": "a"})
    b.step("/teams/miami-dolphins/schedule/", "goto", {})
    b.step("/games/dolphins-at-vikings-2026-reg-4/", "click", {"selector": "a"})
    b.step("/standings/", "goto", {})
    b.done("My Team now: Miami Dolphins (0-2), 4th AFC East; Week 3: Kansas City Chiefs at "
           "Miami Dolphins, SUN 1:00pm ET. Coach Jeff Hafley, home stadium Hard Rock "
           "Stadium. Next two: W3 vs the Chiefs (SUN 1:00pm, Hard Rock Stadium, on CBS) and "
           "W4 at the Vikings (SUN 4:05pm, U.S. Bank Stadium). Division rank 4th AFC East, "
           "point differential -36.",
           final_path="/standings/")
    seed = _seed()
    after = mutate_db(seed, tmp / "honest_12" / "after.db", [
        ("UPDATE users SET favorite_team='MIA' WHERE id=4", ()),
    ])
    return tmp / "honest_12", seed, after


def honest_run_13(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_13", "NFL--13")
    b.step("/", "goto", {})
    b.step("/games/falcons-at-packers-2026-reg-3/", "click", {"selector": "a"})
    b.step("/games/rams-at-broncos-2026-reg-3/", "click", {"selector": "a"})
    b.step("/games/eagles-at-bears-2026-reg-3/", "click", {"selector": "a"})
    b.step("/", "click", {"selector": "a[href='/']"})
    b.step("/standings/", "click", {"selector": "a[href='/standings/']"})
    b.step("/videos/", "click", {"selector": "a[href='/videos/']"})
    b.step("/videos/falcons-vs-packers-week-3-tnf-preview-nfl-daily/", "click", {"selector": "a"})
    b.step("/videos/rams-vs-broncos-week-3-preview-nfl-daily/", "click", {"selector": "a"})
    b.step("/videos/falcons-vs-packers-week-3-tnf-preview-nfl-daily/", "click", {"selector": "a"},
           url_after="/videos/")
    b.step("/videos/eagles-vs-bears-week-3-preview-nfl-daily/", "click", {"selector": "a"})
    b.step("/news/", "click", {"selector": "a[href='/news/']"})
    b.step("/news/falcons-vs-packers-three-must-know-storylines-for-thursday-s-week-3-prime-time-game/",
           "click", {"selector": "a"})
    b.done("TNF: Falcons at Packers, THU Sep 24 8:15pm ET, Prime Video, Lambeau Field (ATL 0-2, GB "
           "1-1). SNF: Rams at Broncos, SUN Sep 27 8:20pm ET, NBC, Empower Field at Mile High "
           "(LAR 1-1, DEN 1-1). MNF: Eagles at Bears, MON Sep 28 8:15pm ET, ESPN, Soldier Field "
           "(PHI 2-0, CHI 1-1). Still undefeated of the six: the Eagles (2-0, standings). Video "
           "previews (all Latest Buzz channel): 'Falcons vs. Packers Week 3 TNF Preview | NFL "
           "Daily' (first Up Next: 'Rams vs. Broncos Week 3 Preview | NFL Daily'), 'Rams vs. "
           "Broncos Week 3 Preview | NFL Daily' (first Up Next: 'Vikings vs. Buccaneers Week 3 "
           "Preview | NFL Daily'), 'Eagles vs. Bears Week 3 Preview | NFL Daily' (first Up "
           "Next: 'Rams vs. Broncos Week 3 Preview | NFL Daily'). TNF storylines article: "
           "'Falcons vs. Packers: Three must-know storylines for Thursday's Week 3 prime-time "
           "game' by Dan Parr, September 23, 2026.",
           final_path="/news/falcons-vs-packers-three-must-know-storylines-for-thursday-s-week-3-prime-time-game/")
    seed = _seed()
    copy_db(seed, tmp / "honest_13" / "initial.db")
    copy_db(seed, tmp / "honest_13" / "after.db")
    return tmp / "honest_13", seed, seed


def honest_run_14(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_14", "NFL--14")
    b.step("/", "goto", {})
    b.step("/standings/", "click", {"selector": "a[href='/standings/']"})
    b.step("/teams/las-vegas-raiders/", "click", {"selector": "a"})
    b.step("/teams/las-vegas-raiders/schedule/", "click", {"selector": "a"})
    b.step("/games/dolphins-at-raiders-2026-reg-1/", "click", {"selector": "a"})
    b.step("/teams/las-vegas-raiders/schedule/", "click", {"selector": "a"},
           url_after="/teams/las-vegas-raiders/schedule/")
    b.step("/games/raiders-at-chargers-2026-reg-2/", "click", {"selector": "a"})
    b.step("/teams/las-vegas-raiders/schedule/", "click", {"selector": "a"},
           url_after="/teams/las-vegas-raiders/schedule/")
    b.step("/games/chargers-at-raiders-2026-reg-14/", "click", {"selector": "a"})
    b.step("/teams/los-angeles-chargers/", "click", {"selector": "a"})
    b.step("/games/raiders-at-saints-2026-reg-3/", "click", {"selector": "a"})
    b.step("/news/", "click", {"selector": "a[href='/news/']"})
    b.step("/news/?page=2", "click", {"selector": "a"})
    b.step("/news/?page=3", "click", {"selector": "a"})
    b.step("/news/nfl-week-2-sunday-aftermath-top-5-storylines/", "click", {"selector": "a"})
    b.done("The AFC West's other undefeated team is the Las Vegas Raiders: 2-0, +26 point "
           "differential (53 PF, 27 PA), 2nd AFC West. W1: beat the Dolphins 27-13; W2: won 26-14 "
           "at the Chargers. Bye week: Week 13 (the schedule skips REG 13). First home game after "
           "the bye: W14 vs the Chargers, Sunday December 13, 4:05pm ET (LV 2-0, LAC 0-2). Coach "
           "Klint Kubiak, home stadium Allegiant Stadium. W3: at the Saints, SUN 4:25pm "
           "ET, Caesars Superdome. Post-bye opponent's coach: Jim Harbaugh. Week 2 aftermath "
           "article: 'NFL Week 2 Sunday aftermath: Surprising Raiders, soaring Chiefs and "
           "sinking Chargers in spotlight' by Kevin Patra, September 21, 2026.",
           final_path="/news/nfl-week-2-sunday-aftermath-top-5-storylines/")
    seed = _seed()
    copy_db(seed, tmp / "honest_14" / "initial.db")
    copy_db(seed, tmp / "honest_14" / "after.db")
    return tmp / "honest_14", seed, seed


def honest_run_15(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 15 (stateful): David switches Premium Annual -> Premium Monthly.
    After-DB: subscription id 3 -> cancelled, new monthly subscription (id 4,
    renews 2026-10-24), one new order NFL-D6DE08 (id 3, $16.33)."""
    seed = _seed()
    b = build_run(tmp, "honest_15", "NFL--15")
    b.step("/plus/", "goto", {})
    b.login("david.k@test.com")
    b.step("/plus/", "goto", {})
    b.step("/plus/subscribe/nfl_plus_premium_monthly/", "click",
           {"selector": "a[href*='nfl_plus_premium_monthly']"})
    b.fill("/plus/subscribe/nfl_plus_premium_monthly/", "David Kim", "input[name=cardholder]")
    b.fill("/plus/subscribe/nfl_plus_premium_monthly/", "4242424242424242", "input[name=card_number]")
    b.fill("/plus/subscribe/nfl_plus_premium_monthly/", "10", "input[name=exp_month]")
    b.fill("/plus/subscribe/nfl_plus_premium_monthly/", "2029", "input[name=exp_year]")
    b.fill("/plus/subscribe/nfl_plus_premium_monthly/", "456", "input[name=cvv]")
    b.step("/plus/subscribe/nfl_plus_premium_monthly/", "click", {"selector": "button[type=submit]"},
           url_after="/plus/confirmation/NFL-D6DE08")
    b.step("/account/", "goto", {})
    b.done("Plans: NFL+ Monthly $6.99/mo, NFL+ Annual $49.99/yr, NFL+ Premium Monthly "
           "$14.99/mo (RedZone), NFL+ Premium Annual $99.99/yr (RedZone). David was on "
           "NFL+ Premium Annual at $99.99. New order NFL-D6DE08, total $16.33 ($14.99 plus "
           "$1.34 tax), renews October 24, 2026. Monthly costs MORE per year: 14.99 x 12 = "
           "179.88 vs 99.99, i.e. $79.89 more.",
           final_path="/account/")
    after = mutate_db(seed, tmp / "honest_15" / "after.db", [
        ("UPDATE subscriptions SET status='cancelled' WHERE id=3", ()),
        ("INSERT INTO subscriptions (id, user_id, plan_code, plan_title, cycle, amount, "
         "status, started_at, renews_at) VALUES (4, 4, 'nfl_plus_premium_monthly', "
         "'NFL+ Premium Monthly', 'month', 14.99, 'active', ?, '2026-10-24 00:00:00.000000')",
         (CREATED,)),
        ("INSERT INTO plus_orders (id, user_id, order_ref, plan_code, plan_title, cycle, "
         "amount, tax, total, card_last4, cardholder, created_at, status) VALUES "
         "(3, 4, 'NFL-D6DE08', 'nfl_plus_premium_monthly', 'NFL+ Premium Monthly', "
         "'month', 14.99, 1.34, 16.33, '4242', 'David Kim', ?, 'complete')", (CREATED,)),
    ])
    return tmp / "honest_15", seed, after


def honest_run_16(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_16", "NFL--16")
    b.step("/search?q=Mahomes", "goto", {})
    b.step("/news/nfl-qb-rankings-index-week-3-2026-nfl-season/", "click", {"selector": "a"})
    b.step("/search?q=Mahomes", "goto", {})
    b.step("/videos/patrick-mahomes-first-pass-of-night-is-16-yard-strike-to-xavier-worthy-in-colts-territory/",
           "click", {"selector": "a"})
    b.step("/search?q=Mahomes", "goto", {})
    b.step("/videos/is-patrick-mahomes-still-the-face-of-the-league-gmfb/", "click", {"selector": "a"})
    b.step("/search?q=Mahomes", "goto", {})
    b.step("/videos/patrick-mahomes-s-best-plays-from-3-td-game-week-2/", "click", {"selector": "a"})
    b.step("/search?q=Mahomes", "goto", {})
    b.step("/players/patrick-mahomes/", "click", {"selector": "a"})
    b.step("/teams/kansas-city-chiefs/", "click", {"selector": "a"})
    b.step("/standings/", "goto", {})
    b.done("Search 'Mahomes': 1 player result, 8 news articles, 6 videos (counted the "
           "result rows; the page shows no count labels). Most recent article: 'NFL QB "
           "rankings, Week 3: Patrick Mahomes, Dak Prescott, Matthew Stafford heating up' "
           "by Nick Shook, Sep 23, 2026 — two facts from the body: Mahomes is 'completely "
           "back from the knee injury that ended his 2025 season', and per Next Gen Stats "
           "he completed 8 of 9 passes for 133 yards and two TDs against man coverage in "
           "Week 1. Three video results opened (Latest Buzz channel). Player page: Chiefs, "
           "#15, 6-2, 10 years experience. Team page: Andy Reid, 2-0. Standings: 1st AFC "
           "West, +24.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_16" / "initial.db")
    copy_db(seed, tmp / "honest_16" / "after.db")
    return tmp / "honest_16", seed, seed


def honest_run_17(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_17", "NFL--17")
    b.step("/players/?query=Mahomes", "goto", {})
    b.step("/players/patrick-mahomes/", "click", {"selector": "a"})
    b.step("/stats/passing/", "goto", {})
    b.step("/scores/2026/REG2/", "goto", {})
    b.step("/games/colts-at-chiefs-2026-reg-2/", "click", {"selector": "a"})
    b.step("/teams/kansas-city-chiefs/", "goto", {})
    b.step("/teams/kansas-city-chiefs/schedule/", "goto", {})
    b.step("/videos/", "goto", {})
    b.step("/standings/", "goto", {})
    b.done("Mahomes career totals: 128 games, 4,747 attempts, 36,505 passing yards, 272 "
           "TDs, 86 INTs; single-season best 5,097 yards in 2018; 2026 row: 2 games, 47/74, "
           "566 yards, 5 TDs, 1 INT; Week 2 stat line: 32/47, 382 yards, 3 TDs, 0 INTs in "
           "the 33-30 overtime win over the Colts; college Texas Tech. Passing leaderboard: "
           "ranks 5th with 566 yards. W2 final: Chiefs 33, Colts 30 (FINAL/OT). W3 "
           "(schedule): at the Dolphins, SUN 1:00pm ET. Preview video: 'Chiefs vs. Dolphins "
           "Week 3 Preview | NFL Daily'. Division rank: 1st AFC West.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_17" / "initial.db")
    copy_db(seed, tmp / "honest_17" / "after.db")
    return tmp / "honest_17", seed, seed


def honest_run_18(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_18", "NFL--18")
    b.step("/standings/", "goto", {})
    for cat in ("passing", "rushing", "receiving", "tackles", "interceptions"):
        b.step(f"/stats/{cat}/", "goto", {})
    b.step("/teams/san-francisco-49ers/", "goto", {})
    b.step("/teams/san-francisco-49ers/schedule/", "goto", {})
    b.step("/games/cardinals-at-49ers-2026-reg-3/", "click", {"selector": "a"})
    b.step("/teams/philadelphia-eagles/", "goto", {})
    b.step("/teams/philadelphia-eagles/schedule/", "goto", {})
    b.step("/games/eagles-at-bears-2026-reg-3/", "click", {"selector": "a"})
    b.done("Best point-differential division leader: San Francisco 49ers (NFC West, 2-0, "
           "62 scored, 20 allowed, +42). Worst: Philadelphia Eagles (+6, 2-0). Leaders: "
           "passing Tyler Shough (Saints), rushing Kenneth Walker III (Chiefs), receiving "
           "Amon-Ra St. Brown (Lions), tackles Anthony Hill Jr. (Titans), interceptions "
           "Jevon Holland (Giants). Only Walker III plays for a division leader (Chiefs, "
           "1st AFC West). 49ers: Kyle Shanahan, Levi's Stadium, next game W3 vs the "
           "Cardinals (SUN 4:05pm, Levi's Stadium). Eagles: Nick Sirianni, Lincoln "
           "Financial Field, next game W3 at the Bears (MON 8:15pm, Soldier Field).",
           final_path="/games/eagles-at-bears-2026-reg-3/")
    seed = _seed()
    copy_db(seed, tmp / "honest_18" / "initial.db")
    copy_db(seed, tmp / "honest_18" / "after.db")
    return tmp / "honest_18", seed, seed


def honest_run_19(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_19", "NFL--19")
    b.step("/players/?query=Williams&team=AZ", "goto", {})
    b.step("/injuries/", "goto", {})
    b.step("/teams/arizona-cardinals/", "goto", {})
    b.step("/teams/arizona-cardinals/roster/?position=QB", "goto", {})
    b.step("/scores/2026/REG3/", "goto", {})
    b.step("/games/cardinals-at-49ers-2026-reg-3/", "click", {"selector": "a"})
    b.step("/standings/", "goto", {})
    b.done("Cardinals named Williams: Garrett Williams (CB, ACT, #21, Syracuse), Jayden "
           "Williams (OT, ACT, #66, Mississippi), Wydett Williams Jr. (SAF, ACT, #31, "
           "Mississippi), Damonic Williams (DT, DEV, #96, Oklahoma). Garrett Williams is "
           "on the W3 injury report: Limited Participation in Practice. Cardinals: Mike "
           "LaFleur, State Farm Stadium, 1-1. Active QBs: Gardner Minshew (#15), Carson "
           "Beck (#19), Jacoby Brissett (#7). Division rank 4th NFC West, differential "
           "-12. W3: at the 49ers, SUN 4:05pm ET, Levi's Stadium.",
           final_path="/standings/")
    seed = _seed()
    copy_db(seed, tmp / "honest_19" / "initial.db")
    copy_db(seed, tmp / "honest_19" / "after.db")
    return tmp / "honest_19", seed, seed


def honest_run_20(tmp: Path) -> tuple[Path, Path, Path]:
    b = build_run(tmp, "honest_20", "NFL--20")
    b.step("/", "goto", {})
    b.fill("/", "gameday.fan@example.com", "footer input[name=email]")
    b.step("/", "select", {"value": "KC", "selector": "select[name=team]"})
    b.step("/", "click", {"selector": "footer button[type=submit]"})
    b.fill("/", "tailgate.buddy@example.com", "footer input[name=email]")
    b.step("/", "select", {"value": "MIA", "selector": "select[name=team]"})
    b.step("/", "click", {"selector": "footer button[type=submit]"})
    b.step("/teams/kansas-city-chiefs/schedule/", "goto", {})
    b.step("/games/chiefs-at-dolphins-2026-reg-3/", "click", {"selector": "a"})
    b.step("/teams/kansas-city-chiefs/schedule/", "goto", {})
    b.step("/games/chiefs-at-raiders-2026-reg-4/", "click", {"selector": "a"})
    b.step("/teams/miami-dolphins/", "goto", {})
    b.step("/teams/las-vegas-raiders/", "goto", {})
    b.done("Both signups confirmed ('You're signed up for the NFL newsletter.'): "
           "gameday.fan@example.com (Chiefs) and tailgate.buddy@example.com (Dolphins). "
           "Chiefs' next two: W3 at the Dolphins (SUN 1:00pm ET, Hard Rock Stadium; MIA "
           "0-2, Jeff Hafley) and W4 at the Raiders (SUN 4:25pm ET, Allegiant Stadium; LV "
           "2-0, Klint Kubiak). Combined record: 2-2.",
           final_path="/teams/las-vegas-raiders/")
    seed = _seed()
    after = mutate_db(seed, tmp / "honest_20" / "after.db", [
        ("INSERT INTO newsletter_signups (id, email, team_abbr, created_at) VALUES "
         "(1, 'gameday.fan@example.com', 'KC', ?)", (CREATED,)),
        ("INSERT INTO newsletter_signups (id, email, team_abbr, created_at) VALUES "
         "(2, 'tailgate.buddy@example.com', 'MIA', ?)", (CREATED,)),
    ])
    return tmp / "honest_20", seed, after


HONEST = {0: honest_run_00, 1: honest_run_01, 2: honest_run_02, 3: honest_run_03,
          4: honest_run_04, 5: honest_run_05, 6: honest_run_06, 7: honest_run_07,
          8: honest_run_08, 9: honest_run_09, 10: honest_run_10, 11: honest_run_11,
          12: honest_run_12, 13: honest_run_13, 14: honest_run_14, 15: honest_run_15,
          16: honest_run_16, 17: honest_run_17, 18: honest_run_18, 19: honest_run_19,
          20: honest_run_20}


# ---------------------------------------------------------------- parametrized suites
@pytest.mark.parametrize("index", range(21))
def test_honest_run_passes(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    result = run_verifier(index, run_dir)
    assert result["pass"] is True, json.dumps(result, indent=1)[:2400]


@pytest.mark.parametrize("index", range(21))
def test_noop_run_fails(index, tmp_path):
    run_dir = noop_run(tmp_path, index)
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert not result.get("infra_error")


@pytest.mark.parametrize("index", range(21))
def test_wrong_answer_fails(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    traj = json.loads((Path(run_dir) / "trajectory.json").read_text())
    traj["final_answer"] = "I visited the site but I could not find the answer. " \
                           "Everything is 42 and the team is nobody."
    (Path(run_dir) / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert not result.get("infra_error")


@pytest.mark.parametrize("index", range(21))
def test_shortcut_homepage_only_fails(index, tmp_path):
    """Correct answer, but the agent never left the homepage: knowledge-recall
    shortcut MUST FAIL on the navigation gate."""
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    traj = json.loads((Path(run_dir) / "trajectory.json").read_text())
    for step in traj["steps"]:
        step["url"] = BASE + "/"
        step.pop("url_after", None)
    traj["final_url"] = BASE + "/"
    traj["steps"] = traj["steps"][:1]
    # stateful shortcuts keep homepage-only navigation AND a clean DB
    (Path(run_dir) / "trajectory.json").write_text(json.dumps(traj))
    seed = _acquire_seed()
    copy_db(seed, Path(run_dir) / "initial.db")
    copy_db(seed, Path(run_dir) / "after.db")
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert not result.get("infra_error")


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_mutation_fails(index, tmp_path):
    """A read-only task whose after-DB was mutated MUST FAIL on the DB gate."""
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    con = sqlite3.connect(str(Path(run_dir) / "after.db"))
    con.execute("UPDATE teams SET wins = wins + 1 WHERE abbr='KC'")
    con.commit()
    con.close()
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert "db_read_only" in result["reason"] or not result.get("infra_error")


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(index, tmp_path):
    """Stateful task: agent self-reports success but the DB is unchanged."""
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    seed = _acquire_seed()
    copy_db(seed, Path(run_dir) / "after.db")  # no delta at all
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert not result.get("infra_error")


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(index, tmp_path):
    """Stateful task: the DB changed, but not in the way the task requires."""
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    con = sqlite3.connect(str(Path(run_dir) / "after.db"))
    con.execute("UPDATE users SET favorite_team='DAL' WHERE id=1")
    con.commit()
    con.close()
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
    assert not result.get("infra_error")


@pytest.mark.parametrize("index", range(21))
def test_tampered_task_id_fails(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    traj = json.loads((Path(run_dir) / "trajectory.json").read_text())
    traj["task_id"] = "NFL--99"
    (Path(run_dir) / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(index, run_dir)
    assert result["pass"] is False


@pytest.mark.parametrize("index", range(21))
def test_offsite_url_fails(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    traj = json.loads((Path(run_dir) / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "http://example.com/phish"
    (Path(run_dir) / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(index, run_dir)
    assert result["pass"] is False


@pytest.mark.parametrize("index", range(21))
def test_missing_screenshot_fails(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    (Path(run_dir) / "screenshots" / "step_001.png").unlink()
    result = run_verifier(index, run_dir)
    assert result["pass"] is False


@pytest.mark.parametrize("index", range(21))
def test_not_terminated_fails(index, tmp_path):
    run_dir, initial_db, after_db = HONEST[index](tmp_path)
    traj = json.loads((Path(run_dir) / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (Path(run_dir) / "trajectory.json").write_text(json.dumps(traj))
    result = run_verifier(index, run_dir)
    assert result["pass"] is False
