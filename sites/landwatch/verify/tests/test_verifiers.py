"""Deterministic verifier contract tests for the 30 LandWatch tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only,
empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct
answer, homepage-only navigation) MUST FAIL for every task whose required surface
is beyond the homepage (tasks 17 and 18 are homepage-surface by design and are
documented accordingly). Read-only tasks MUST FAIL on a mutated after-DB;
stateful tasks MUST FAIL on state-mismatch (claimed success with an unchanged /
wrongly-changed DB) and on a collateral delta. Package tampering (task_id
mismatch, off-site URLs, broken screenshots, tampered seed, unavailable DB)
MUST fail closed.

No docker, no LLM: snapshots are seed copies mutated through sqlite, trajectories
are hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, SEED_DB, RunBuilder, copy_db, mutate_db,  # noqa: E402
                      noop_run, run_verifier, session_statements, build_run)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file(),
                                reason="seed DB not built (materialize instance_seed/landwatch.db)")

STATEFUL = {10, 11, 12, 13, 20, 26, 27}
READ_ONLY = sorted(set(range(30)) - STATEFUL)
LOGIN = {10: "alice.j@test.com", 11: "bob.c@test.com", 12: "carol.d@test.com",
         20: "david.k@test.com", 26: "alice.j@test.com"}

DETAIL_SISTERDALE = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
DETAIL_TUCKED = "/burnet-county-texas-farms-and-ranches-for-sale/pid/428212638"
DETAIL_OHIO = "/allen-county-ohio-farms-and-ranches-for-sale/pid/427843237"
DETAIL_3DM = "/moffat-county-colorado-farms-and-ranches-for-sale/pid/424462143"

# ---------------------------------------------------------------- honest fixtures
# (login email or None, [(path, action, params), ...], honest answer, after-DB mutations)
HONEST = {
    0: (None, [("/", "fill", {"text": "Austin", "selector": "input[name=q]"}),
               ("/search?q=Austin", "click", {"selector": "button[type=submit]"}),
               ("/texas-land-for-sale/austin", "click", {"selector": ".lw-result-title a"})],
        "The Austin, Texas land-for-sale page shows 1 Listings in the results heading. "
        "The first listing is '111 AC In the Heart of the Hill Country' at $6,100,000 "
        "for 111 Acres.", []),
    1: (None, [("/texas-land-for-sale", "click", {}),
               ("/texas-land-for-sale/price-over-1000000", "click", {"selector": ".lw-facet-item a"}),
               ("/texas-land-for-sale/price-over-1000000?sort=price-low", "click",
                {"selector": "[data-sort=price-low]"})],
        "81 listings. The cheapest is 'East Texas Poultry Farm LOCATED NEAR COOKVILLE "
        "TEXAS' at $1,050,000 in Titus County.", []),
    2: (None, [("/hunting-property", "click", {}),
               ("/hunting-property/acres-under-10", "click", {"selector": ".lw-facet-item a"}),
               ("/hunting-property/acres-under-10?sort=newest", "click",
                {"selector": "[data-sort=newest]"})],
        "6 listings total. The most recently listed property is 'Cannon Falls Oasis' "
        "at $1,399,000 in Minnesota.", []),
    3: (None, [(DETAIL_SISTERDALE, "click", {"selector": ".lw-result-title a"})],
        "Sisterdale Farms: price $19,400,000, 310 Acres, 5 Beds and 5 Baths. The "
        "gallery button says 'View all 93 pictures'.", []),
    4: (None, [(DETAIL_SISTERDALE, "click", {"selector": ".lw-result-title a"})],
        "First two Highlights bullets: '11,800± SF custom stone home with 7 Rumford "
        "fireplaces and panoramic Hill Country views' and 'Over one third mile of "
        "Guadalupe River frontage with senior water rights'. Activities: Camping, "
        "Canoeing/Kayaking, Fishing, Horseback Riding, Hunting, Off-roading.", []),
    5: (None, [(DETAIL_TUCKED, "click", {"selector": ".lw-result-title a"})],
        "The listing agent is Jordan Shipley of Shipley Ranches, phone (512) 798-4161. "
        "The gallery lists 90 pictures.", []),
    6: (None, [("/texas-land-for-sale", "click", {}),
               ("/texas-land-for-sale/houston-region", "click",
                {"selector": ".lw-facet-item a"})],
        "The Houston Region page shows 5 listings. The first is 'Kountze Countryside "
        "Retreat' at $510,600 for 74 Acres.", []),
    7: (None, [("/land/auctions", "click", {})],
        "47 auction listings. The first auction is 'Prime Ohio Farmland', 100 Acres, "
        "auction date 2026-09-28.", []),
    8: (None, [("/find-agent", "click", {})],
        "313 agents are listed. The agent with the most total listings is Mac A. "
        "Coalson of Coalson Real Estate.", []),
    9: (None, [("/find-agent", "click", {}),
               ("/profile/louie-swope/1437140", "click", {"selector": ".lw-agent-card-name"})],
        "Louie Swope of West & Swope Ranches: Total Listings 2, Price Range $19M - "
        "$21M, Acre Range 310.00 - 844 ac, based in San Antonio, TX.", []),
    10: ("alice.j@test.com", [("/account", "click", {})],
         "Alice has 5 saved properties and 3 saved searches: 'Boerne, TX Land for "
         "Sale', 'Hunting Land under $250K', and 'Texas Land for Sale'.",
         session_statements(1, "alice.j@test.com")),
    11: ("bob.c@test.com",
         [("/hunting-property/price-250000-499999", "click", {}),
          ("/hunting-property/price-250000-499999", "click", {"selector": "[data-save-search]"}),
          ("/account", "click", {})],
         "The saved search was stored under the name 'Hunting Land for Sale - 1-7 of 7 "
         "Listings' and links to /hunting-property/price-250000-499999.",
         session_statements(2, "bob.c@test.com")
         + [("INSERT INTO saved_searches (user_id, name, url, alerts, created_at) "
             "VALUES (2, 'Hunting Land for Sale - 1-7 of 7 Listings', "
             "'/hunting-property/price-250000-499999', 0, '2026-09-23T00:00:00')", ())]),
    12: ("carol.d@test.com",
         [("/account", "click", {}),
          ("/account", "click", {"selector": ".lw-saved-row form button"})],
         "1 saved search remains: 'Farms and Ranches in Tennessee'.",
         session_statements(3, "carol.d@test.com")
         + [("DELETE FROM saved_searches WHERE id = 5", ())]),
    13: (None, [(DETAIL_OHIO, "click", {"selector": ".lw-result-title a"}),
                (DETAIL_OHIO, "fill", {"text": "Could you share the soil quality "
                                   "reports for this farm?", "selector": "textarea"}),
                (DETAIL_OHIO, "click", {"selector": ".lw-contact-form button"})],
        "The confirmation message said: 'Your message has been sent to the listing "
        "agent.'",
        [("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
          "VALUES (NULL, 427843237, 'Jamie Reviewer', 'reviewer@example.com', '', "
          "'Could you share the soil quality reports for this farm?', "
          "'2026-09-23T00:00:00')", ())]),
    14: (None, [("/", "fill", {"text": "Harris County", "selector": "input[name=q]"}),
                ("/search?q=Harris+County", "click", {"selector": "button[type=submit]"}),
                ("/texas-land-for-sale/harris-county", "click",
                 {"selector": ".lw-suggest-item"})],
        "Harris County, TX shows 1 listing: 'A private 10-acre estate in Cypress' at "
        "$5,750,000 for 10 Acres.", []),
    15: (None, [("/farms-ranches", "click", {})],
        "233 listings. The first three: 'Sisterdale Farms' $19,400,000 (Texas), "
        "'Gaddistown on the Toccoa' $6,500,000 (Georgia), 'Tucked into the Hill "
        "Country' $25,950,000 (Texas).", []),
    16: (None, [("/florida-land-for-sale", "click", {}),
                ("/florida-land-for-sale/waterfront-property", "click",
                 {"selector": ".lw-facet-item a"})],
        "Florida has 1 waterfront land listing. The first one is 'Firefly Resorts- "
        "RV/Tiny Home' at $99,900.", []),
    17: (None, [("/", "click", {})],
        "The four tiles: Land for Sale — 436 Land Properties; Farms and Ranches — 233 "
        "Farms and Ranches Properties; Hunting Land — 176 Hunting Land Properties; "
        "Homesites — 53 Homesites Properties.", []),
    18: (None, [("/", "click", {})],
        "First three featured: $450,000 / 20.18 Acres / West Virginia; $299,000 / 25 "
        "Acres / Virginia; $799,900 / 5.87 Acres / Utah.", []),
    19: (None, [("/colorado-land-for-sale", "click", {}),
                ("/colorado-land-for-sale?sort=acres-high", "click",
                 {"selector": "[data-sort=acres-high]"})],
        "The largest property is '3D Mountain Ranch': 11,764 Acres, $6,995,000, in "
        "Moffat County.", []),
    20: ("david.k@test.com", [("/account", "click", {})],
         "David's saved properties (6): Three W Trophy Ranch; 1,585-Acre Cattle "
         "Empire; Hunting Property Auction; Kentucky Trophy Hunt Auction; Benton's "
         "Prime Land Auction; RRP Real Estate Auction. Which one should I remove?",
         session_statements(4, "david.k@test.com")),
    21: (None, [("/montana-land-for-sale", "click", {}),
                ("/montana-land-for-sale/acres-over-1000", "click",
                 {"selector": ".lw-facet-item a"})],
        "3 listings match: 'Montana Legacy Ranch' (11,689 Acres), '2,341 Ac Montana "
        "Creek Ranch' (3,336 Acres), 'Mullendore Ranch' (10,510 Acres).", []),
    22: (None, [(DETAIL_3DM, "click", {"selector": ".lw-result-title a"})],
        "3D Mountain Ranch: $6,995,000, 11,764 Acres. Type row: Farms and Ranches, "
        "Recreational Property, Hunting Property.", []),
    23: (None, [("/", "fill", {"text": "Boerne", "selector": "input[name=q]"}),
                ("/search?q=Boerne", "click", {"selector": "button[type=submit]"}),
                ("/texas-land-for-sale/boerne", "click", {"selector": ".lw-suggest-item"})],
        "Boerne, TX shows 4 listings. The first is 'Sisterdale Farms' at $19,400,000.", []),
    24: (None, [("/undeveloped-land", "click", {}),
                ("/undeveloped-land/price-50000-99999", "click", {"selector": ".lw-facet-item a"}),
                ("/undeveloped-land/price-50000-99999?sort=price-low", "click",
                 {"selector": "[data-sort=price-low]"})],
        "3 listings. The cheapest is 'Jaz Meadows 2-Acre Homesites' at $77,500 in "
        "Navarro County.", []),
    25: (None, [("/texas-land-for-sale", "click", {}),
                ("/texas-land-for-sale/parker-county", "click", {"selector": ".lw-facet-item a"}),
                ("/texas-land-for-sale/parker-county?sort=price-high", "click",
                 {"selector": "[data-sort=price-high]"})],
        "Parker County leads with 19 listings. The most expensive there is '2,856 "
        "acre Brazos River Ranch' at $39,041,450.", []),
    26: ("alice.j@test.com",
         [("/account/edit", "click", {}),
          ("/account/edit", "fill", {"text": "(919) 555-0139", "selector": "input[name=phone]"}),
          ("/account", "click", {"selector": "button[type=submit]"})],
         "The success message said 'Profile updated.' The profile card now shows the "
         "phone (919) 555-0139.",
         session_statements(1, "alice.j@test.com")
         + [("UPDATE users SET phone = '(919) 555-0139' WHERE id = 1", ())]),
    27: (None, [("/register", "fill", {"text": "New Landbuyer", "selector": "input[name=name]"}),
                ("/register", "fill", {"text": "new.landbuyer@test.com", "selector": "input[name=email]"}),
                ("/register", "fill", {"text": "LandBuyer2026!", "selector": "input[name=password]"}),
                ("/account", "click", {"selector": "button[type=submit]"})],
        "The new account lands on My LandWatch. Favorites empty state: 'You haven't "
        "saved any properties yet. Tap the heart icon on any listing to save it "
        "here.' Saved Searches empty state: 'No saved searches yet. Use the Save "
        "Search button on any search results page.'",
        [("INSERT INTO users (email, password_hash, name, phone, created_at, is_benchmark) "
          "VALUES ('new.landbuyer@test.com', "
          "'b35294c904271b106649528602ef203b3b3621b3c14f7ea81e051a702a1791e7', "
          "'New Landbuyer', NULL, '2026-09-23T00:00:00', 0)", ())]),
    28: (None, [("/land", "click", {}),
                (DETAIL_SISTERDALE, "click", {"selector": ".lw-result-title a"})],
        "The first listing is Sisterdale Farms: status Available, $19,400,000, 310 "
        "Acres, Type row: Farms and Ranches, Recreational Property, Riverfront "
        "Property, Waterfront Property, House. The gallery button says 93 pictures.", []),
    29: (None, [("/find-agent", "click", {}),
                ("/profile/mac-a-coalson/32197", "click", {"selector": ".lw-agent-card-name"})],
        "Mac A. Coalson of Coalson Real Estate: 11 Total Listings, Price Range $1.1M - "
        "$50M, Acre Range 22.50 - 5896 ac. The first listing in the grid is "
        "'5,888-acre W-W Ranch' at $49,985,000.", []),
}

# wrong answers: plausible but contradicted by the frozen seed
WRONG = {
    0: "The Austin page shows 3 listings; the first is 'Hill Country Ranch' at $6,000,000 for 110 Acres.",
    1: "80 listings; the cheapest is 'East Texas Ranch' at $1,100,000 in Titus County.",
    2: "7 listings; the newest is 'Cannon Falls Retreat' at $1,390,000 in Wisconsin.",
    3: "$19,000,000, 300 Acres, 4 Beds and 4 Baths, 90 pictures.",
    4: "The first bullets mention a stone home and river frontage; activities include Camping, Fishing and Hunting.",
    5: "The agent is Jordan Shipley of Shipley Land, phone (512) 798-4160, gallery 89 pictures.",
    6: "4 listings; the first is 'Kountze Country Retreat' at $510,000 for 7 Acres.",
    7: "46 auctions; the first is 'Ohio Farmland' at 100 Acres, auction date 2026-09-30.",
    8: "310 agents; the top agent is Mac Coalson of Coalson Realty.",
    9: "3 Total Listings, $19M - $20M, 300 - 800 ac, based in Austin, TX.",
    10: "4 saved properties and 2 saved searches: 'Boerne, TX Land for Sale' and 'Texas Land for Sale'.",
    11: "The search was saved as 'Hunting Land' and links to /hunting-property.",
    12: "2 saved searches remain: 'Farms and Ranches in Tennessee' and 'Montana Land for Sale'.",
    13: "The confirmation message said: 'Thank you for your inquiry.'",
    14: "2 listings; the first is 'Cypress Estate' at $5,700,000 for 12 Acres.",
    15: "232 listings; the first three are 'Sisterdale Farms', 'Gaddistown', and 'Tucked into the Hill'.",
    16: "Florida has 62 waterfront land listings; the first is 'Firefly Resort' at $99,000.",
    17: "Land for Sale 400, Farms and Ranches 200, Hunting Land 150, Homesites 50.",
    18: "$450,000 / 20 Acres / Virginia; $299,000 / 25 Acres / West Virginia; $799,900 / 5 Acres / Utah.",
    19: "11,000 Acres, $6,500,000, in Rio Blanco County, titled 'Mountain Ranch'.",
    20: "David has 5 saved properties: Three W Trophy Ranch; Hunting Property Auction; RRP Real Estate Auction.",
    21: "2 listings: 'Montana Legacy Ranch' (11,689 Acres) and 'Mullendore Ranch' (10,510 Acres).",
    22: "$6,500,000, 11,000 Acres; types: Farms and Ranches and Recreational Property.",
    23: "5 listings; the first is 'Boerne Farms' at $19,000,000.",
    24: "4 listings; the cheapest is 'Jaz Meadows' at $70,000 in Navarro.",
    25: "Tarrant County leads with 19 listings; the priciest is 'Brazos River Ranch' at $39,000,000.",
    26: "The success message said 'Saved.' and the profile shows (919) 555-0139.",
    27: "The account lands on My Account with empty favorites and no searches yet.",
    28: "Status Available, $19,000,000, 300 Acres; types: Farms and Ranches; 90 pictures.",
    29: "Mac Coalson, 10 Total Listings, $1M - $50M, 20 - 5000 ac; first listing 'W-W Ranch' at $49,000,000.",
}


def honest_run(root: Path, task_n: int) -> tuple[Path, Path, Path]:
    """(run_dir, initial_db, after_db) for the honest fixture of one task."""
    login, steps, answer, mutations = HONEST[task_n]
    run_dir = build_run(root, f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(root / "initial.db")
    after_db = mutate_db(copy_db(root / "after.db"), mutations)
    return run_dir, initial_db, after_db


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("task_n", range(30))
def test_honest_pass(tmp_path, task_n):
    run_dir, initial_db, after_db = honest_run(tmp_path, task_n)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=1)[:2000]


@pytest.mark.parametrize("task_n", range(30))
def test_noop_fail(tmp_path, task_n):
    run_dir = noop_run(tmp_path / "run", f"LandWatch--{task_n}")
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = copy_db(tmp_path / "after.db")
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]
    assert verdict.get("reason") == "final_answer_nonempty"


@pytest.mark.parametrize("task_n", range(30))
def test_wrong_answer_fail(tmp_path, task_n):
    login, steps, _answer, mutations = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps,
                        WRONG[task_n], login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]
    # the failing check must be an answer / navigation fact, never an infra error
    assert not verdict.get("infra_error"), verdict


# tasks 17 and 18 are homepage-surface by design (documented in verify/README.md)
@pytest.mark.parametrize("task_n", [n for n in range(30) if n not in (17, 18)])
def test_shortcut_fail(tmp_path, task_n):
    """Correct answer, homepage-only navigation -> FAIL (anti knowledge-shortcut)."""
    _login, _steps, answer, mutations = HONEST[task_n]
    b = RunBuilder(tmp_path / "run", f"LandWatch--{task_n}")
    b.step("/", "click", {"selector": "body"})
    b.done(answer)
    run_dir = b.write()
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]
    assert verdict.get("reason") != "final_answer_nonempty", verdict


def test_shortcut_homepage_surface_passes(tmp_path):
    """Tasks 17/18 quote homepage facts with homepage navigation: documented PASS."""
    for task_n in (17, 18):
        _login, _steps, answer, mutations = HONEST[task_n]
        b = RunBuilder(tmp_path / f"run{task_n}", f"LandWatch--{task_n}")
        b.step("/", "click", {"selector": "body"})
        b.done(answer)
        run_dir = b.write()
        initial_db = copy_db(tmp_path / f"initial{task_n}.db")
        after_db = mutate_db(copy_db(tmp_path / f"after{task_n}.db"), mutations)
        verdict = run_verifier(task_n, run_dir, initial_db, after_db)
        assert verdict.get("pass") is True, json.dumps(verdict, indent=1)[:1500]


@pytest.mark.parametrize("task_n", READ_ONLY)
def test_readonly_tamper_fail(tmp_path, task_n):
    """Honest trajectory + a mutated after-DB (agent hid a write) -> FAIL."""
    run_dir, initial_db, _after = honest_run(tmp_path / "honest", task_n)
    tampered = mutate_db(copy_db(tmp_path / "after.db"),
                         [("INSERT INTO favorites (user_id, pid, created_at) "
                           "VALUES (1, 428237808, '2026-09-23T00:00:00')", ())])
    verdict = run_verifier(task_n, run_dir, initial_db, tampered)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]
    assert "read_only_db_unchanged" in json.dumps(verdict)


@pytest.mark.parametrize("task_n,mutations", [
    # T11: answer claims the save, DB unchanged -> FAIL
    (11, session_statements(2, "bob.c@test.com")),
    # T11: wrong URL saved -> FAIL
    (11, session_statements(2, "bob.c@test.com")
     + [("INSERT INTO saved_searches (user_id, name, url, alerts, created_at) "
         "VALUES (2, 'Hunting Land for Sale - 1-7 of 7 Listings', '/hunting-property', 0, "
         "'2026-09-23T00:00:00')", ())]),
    # T12: wrong row removed (the Tennessee search) -> FAIL
    (12, session_statements(3, "carol.d@test.com") + [("DELETE FROM saved_searches WHERE id = 6", ())]),
    # T13: no inquiry row written -> FAIL
    (13, []),
    # T26: phone unchanged -> FAIL
    (26, session_statements(1, "alice.j@test.com")),
    # T26: wrong phone -> FAIL
    (26, session_statements(1, "alice.j@test.com")
     + [("UPDATE users SET phone = '(919) 555-0000' WHERE id = 1", ())]),
    # T27: no registered user row -> FAIL
    (27, []),
    # T27: registered with the wrong password -> FAIL
    (27, [("INSERT INTO users (email, password_hash, name, phone, created_at, is_benchmark) "
           "VALUES ('new.landbuyer@test.com', '" + "0" * 64 + "', 'New Landbuyer', NULL, "
           "'2026-09-23T00:00:00', 0)", ())]),
    # T20: two favorites removed (beyond the single-removal reading) -> FAIL
    (20, session_statements(4, "david.k@test.com")
     + [("DELETE FROM favorites WHERE user_id = 4 AND pid IN (428200364, 427912911)", ())]),
    # T20: one favorite removed but another added -> FAIL
    (20, session_statements(4, "david.k@test.com")
     + [("DELETE FROM favorites WHERE user_id = 4 AND pid = 428200364", ()),
        ("INSERT INTO favorites (user_id, pid, created_at) VALUES (4, 428237808, "
         "'2026-09-23T00:00:00')", ())]),
    # T10: collateral write next to the login session -> FAIL
    (10, session_statements(1, "alice.j@test.com")
     + [("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
         "VALUES (1, 427843237, 'Alice', 'alice.j@test.com', '', 'hello', "
         "'2026-09-23T00:00:00')", ())]),
])
def test_stateful_mismatch_fail(tmp_path, task_n, mutations):
    login, steps, answer, _ = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]


@pytest.mark.parametrize("task_n", sorted(STATEFUL))
def test_stateful_collateral_fail(tmp_path, task_n):
    """The required write PLUS an unrelated write -> FAIL."""
    login, steps, answer, mutations = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    extra = mutations + [
        ("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
         "VALUES (NULL, 428237808, 'Extra', 'x@example.com', '', 'collateral', "
         "'2026-09-23T00:00:00')", ())]
    if task_n == 13:
        # inquiries is the allowed table here; tamper favorites instead
        extra = mutations + [
            ("INSERT INTO favorites (user_id, pid, created_at) VALUES (1, 428237808, "
             "'2026-09-23T00:00:00')", ())]
    after_db = mutate_db(copy_db(tmp_path / "after.db"), extra)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2000]


def test_task_id_mismatch_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    verdict = run_verifier(1, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_task_matches"


def test_offsite_url_fails_closed(tmp_path):
    b = RunBuilder(tmp_path / "run", "LandWatch--0")
    b.step("/", "click", {})
    b.step("https://www.landwatch.com/texas-land-for-sale/austin", "goto", {})
    b.done("1 listing, $6,100,000, 111 Acres")
    run_dir = b.write()
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = copy_db(tmp_path / "after.db")
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "all_urls_match_local_origin"


def test_broken_screenshot_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    shot = run_dir / "screenshots" / "step_001.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n not really a png")
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_undone_trajectory_fails_closed(tmp_path):
    _login, steps, answer, mutations = HONEST[0]
    b = RunBuilder(tmp_path / "run", "LandWatch--0")
    for path, action, params in steps:
        b.step(path, action, params)
    b.done(answer)
    run_dir = b.write(terminated=False, reason="max_steps")
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_completed"


def test_tampered_seed_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    mutate_db(initial_db, [("UPDATE listings SET price = 1 WHERE pid = 425766087", ())])
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "snapshot_contract_invalid"


def test_missing_db_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    initial_db.unlink()
    after_db.unlink()
    verdict = run_verifier(0, run_dir, initial_db, after_db, container="wh-never-running")
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "database_unavailable"


def test_foreign_db_fails_closed(tmp_path):
    """A non-landwatch SQLite file as the initial snapshot -> fail closed."""
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    con = sqlite3.connect(str(initial_db))
    con.execute("DROP TABLE listings")
    con.commit()
    con.close()
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "snapshot_contract_invalid"
