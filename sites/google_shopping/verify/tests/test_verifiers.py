"""Deterministic verifier contract tests for the 30 Google Shopping tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only, empty
answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer,
homepage-only navigation) MUST FAIL for every task whose required surface is beyond the
homepage (tasks 0 and 3 are homepage-surface by design and are documented accordingly).
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
state-mismatch and on collateral writes. Package tampering (task_id mismatch, off-site
URLs, broken/missing screenshots, tampered seed, unavailable DB) MUST fail closed.

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
                      noop_run, run_verifier, tiny_png)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file(), reason="seed DB not built (run seed_data.py)")

STATEFUL = {21, 22, 23, 24, 25, 26, 28, 29}
READ_ONLY = sorted(set(range(30)) - STATEFUL)
LOGIN = {"alice": ("alice.j@test.com", "Alice Johnson"), "bob": ("bob.c@test.com", "Bob Chen"),
         "carol": ("carol.d@test.com", "Carol Davis"), "david": ("david.k@test.com", "David Kim")}

# ---------------------------------------------------------------- honest fixtures
# (login key or None, [(path, action, params), ...], honest answer extracted from the live DOM)
HONEST = {
    0: (None, [("/", "click", {})],
        'On the homepage, the section "The iconic trench" carries the subtitle line '
        '"Popular products". The card for "Gap Factory Women\'s Modern Trench Coat" shows '
        'a current price of $64.99.'),
    1: (None, [("/departments", "click", {})],
        'The Departments page lists 15 departments. The very first tile shows the '
        'department "Apparel".'),
    2: (None, [("/", "click", {}), ("/search?q=Blue-light+glasses", "click", {})],
        'Clicking Explore on the "Bye bye blue light" section loads the search query '
        '"Blue-light glasses" and the page reports 31 results.'),
    3: (None, [("/", "click", {})],
        'The FIRST section heading is "The iconic trench" and the SECOND section heading '
        'is "Bye bye blue light", in that order on the homepage feed.'),
    4: (None, [("/search?q=trench+coat", "press", {"key": "Enter"}),
               ("/search?q=trench+coat&price_max=100", "click", {"selector": ".filters button"}),
               ("/search?q=trench+coat&price_max=100&sort=price_asc", "select", {"value": "price_asc"})],
        'With a maximum price of 100 dollars sorted by price low to high, the cheapest '
        'result is "Women\'s Loft Drapey Trench Coat" at $51.95.'),
    5: (None, [("/search?q=blue+light+glasses", "press", {"key": "Enter"}),
               ("/search?q=blue+light+glasses&store=Fashion+Nova", "click", {"selector": "input[name=store]"})],
        'Filtering the "blue light glasses" search by store Fashion Nova shows 6 results. '
        'The lowest current price among them is $2.98 (for "Fashion Nova Women\'s Leave A '
        'Memo Blue Light Glasses").'),
    6: (None, [("/search?q=trench", "press", {"key": "Enter"}),
               ("/search?q=trench&price_min=50&price_max=100", "click", {"selector": ".filters button"})],
        'Searching "trench" with the price range 50 to 100 dollars returns 12 results. '
        'The most expensive result within that range is "Trenchcoat" sold by NOBA at $88.00.'),
    7: (None, [("/search?q=glasses", "press", {"key": "Enter"}),
               ("/search?q=glasses&sort=price_desc", "select", {"value": "price_desc"})],
        'Sorted by price high to low, the top two "glasses" results are "BlockBlueLight '
        'NightFall Billie Blue Blocking Glasses Red Lenses Glasses" at $71.96 and '
        '"BlockBlueLight Nightfall Taylor Blue Blocking Glasses Black Red Lenses Glasses" '
        'at $71.96.'),
    8: (None, [("/search?q=St+Barts+Bluelight", "press", {"key": "Enter"}),
               ("/product/gsd18d8163a9c64bef", "click", {})],
        'On the St Barts product page, the "Compare with similar items" section lists 8 '
        'products, of which 3 are sold by the merchant TikTok Shop. The second listed '
        'product is "Arlo Oval Blue Light Glasses".'),
    9: (None, [("/search?q=", "goto", {}),
               ("/search?q=&sort=price_desc", "select", {"value": "price_desc"})],
        'The most expensive product on the whole site is "trench", sold by Reversible, '
        'priced at $1,704.'),
    10: (None, [("/search?q=Yes+Sir", "press", {"key": "Enter"})],
         'The product\'s full exact title is "Fashion Nova Yes Sir Bluelight". Its current '
         'price is $5.99 and its discount is 33% OFF.'),
    11: (None, [("/search?q=Imily+Bela", "press", {"key": "Enter"}),
                ("/product/gs712912b8114732bd", "click", {})],
         'The product shows a star rating of 3.5 and 4 reviews.'),
    12: (None, [("/search?q=Klassy", "press", {"key": "Enter"}),
                ("/product/gsb43c9633d0a7d9f3", "click", {})],
         'On the Klassy product page, the "Compare with similar items" section lists 8 '
         'products, of which 2 are sold by the merchant BlockBlueLight. The first listed '
         "product is \"AE Classic Tortoise Shell Blue Light Glasses Women's\"."),
    13: (None, [("/search?q=BlockBlueLight", "press", {"key": "Enter"})],
         'The two BlockBlueLight products are "BlockBlueLight NightFall Billie Blue '
         'Blocking Glasses Red Lenses Glasses" at $71.96 and "BlockBlueLight Nightfall '
         'Taylor Blue Blocking Glasses Black Red Lenses Glasses" at $71.96. They cost the '
         'same price.'),
    14: (None, [("/search?q=trench+jacket", "press", {"key": "Enter"}),
                ("/product/gsf3cad2d7c9135f80", "click", {}),
                ("/search?q=COTTON+TRENCH+COAT", "press", {"key": "Enter"}),
                ("/product/gs8d6aa700e365d4d3", "click", {})],
         'The "trench jacket" by Reversible costs $1,290 and the "COTTON TRENCH COAT" by '
         'yoox.com costs $1,294. The trench jacket is cheaper, and the difference in '
         'dollars is $4.00.'),
    15: (None, [("/search?q=UNIQLO", "press", {"key": "Enter"}),
                ("/product/gs266d85b487aa667d", "click", {})],
         'In the "Compare with similar items" section, 2 of the listed products are '
         'sold by "yoox.com", and the first listed product is "AMUR Edikted Women\'s '
         'Amur Maxi Trench Coat".'),
    16: (None, [("/search?q=trench+coat", "press", {"key": "Enter"}),
                ("/search?q=trench+coat&price_max=70", "click", {"selector": ".filters button"})],
         'The cheapest trench coat discounted by at least 50% and costing less than 70 '
         'dollars is "Women\'s Loft Drapey Trench Coat", sold by LOFT, at a current price '
         'of $51.95.'),
    17: (None, [("/deals", "click", {})],
         'The product with the biggest discount on the Deals page is "Trench coat" with a '
         'discount of 82% OFF (sold by yoox.com).'),
    18: (None, [("/deals", "click", {})],
         '12 products on the Deals page have a discount of 70% or more. The merchant that '
         'appears most often on this page is Fashion Nova (shown 6 times).'),
    19: (None, [("/deals", "click", {})],
         'The most expensive product on the Deals page is "trench", priced at $1,704, '
         'with a discount of 22% OFF.'),
    20: ("alice", [("/saved", "click", {})],
         'The shopping list contains "Gap Factory Women\'s Modern Trench Coat" (merchant '
         'Gap Factory, current price $64.99).'),
    21: ("bob", [("/search?q=St+Barts+Bluelight", "press", {"key": "Enter"}),
                 ("/product/gsd18d8163a9c64bef", "click", {}),
                 ("/saved", "click", {})],
         'After saving, the shopping list contains 1 saved item. The saved item "St Barts '
         'Bluelight" shows a price of $50.'),
    22: ("carol", [("/search?q=MVMT+Rover+Frame", "press", {"key": "Enter"}),
                   ("/product/gsac58ccba92d47538", "click", {}),
                   ("/tracked", "click", {})],
         'The Price tracking page shows the tracked product "MVMT Rover Frame — Blue Light '
         'Glasses" at a current price of $19.20.'),
    23: ("alice", [("/product/gsbd9380806ca7e025", "click", {}),
                   ("/saved", "click", {})],
         'After adding the Finch coat and removing the item that costs $64.99, the list '
         'still contains "Aritzia Women\'s The Finch Trench Coat" at $265.'),
    24: ("carol", [("/search?q=Syght", "press", {"key": "Enter"}),
                   ("/product/gs6d8bbb715e54c510", "click", {}),
                   ("/search?q=Syght", "press", {"key": "Enter"}),
                   ("/product/gs365bc2213e4c5230", "click", {}),
                   ("/search?q=Syght", "press", {"key": "Enter"}),
                   ("/product/gs6ab428ebf7cb3419", "click", {}),
                   ("/tracked", "click", {})],
         'All three Syght Glass products are now tracked. The most expensive of the three '
         'is "Buy Cruise - Blue Light Blocking Prescription & Non-Prescription Glasses, '
         'Peach" at $48.50; the other two are "Buy Ember - Blue Light Blocking Computer '
         'Glasses for Digital Generation, Blue" at $45.00 and "Buy Strike Blue Light '
         'Blocking Glasses for Computer & Gaming User, Tortoise" at $45.00.'),
    25: ("david", [("/search?q=&sort=price_desc", "select", {"value": "price_desc"}),
                   ("/product/gs3d82a7d8551f4422", "click", {}),
                   ("/tracked", "click", {})],
         'The Price tracking page shows the tracked product "trench" at a current price '
         'of $1,704.'),
    26: (None, [("/register", "fill", {"text": "Jordan Lee", "selector": "input[name=name]"}),
                ("/register", "fill", {"text": "jordan.lee@test.com", "selector": "input[name=email]"}),
                ("/register", "fill", {"text": "JordanPass99!", "selector": "input[name=password]"}),
                ("/register", "click", {"selector": ".auth-card button[type=submit]"}),
                ("/saved", "click", {})],
         'After registering the new account, the shopping list contains 0 saved items.'),
    27: ("alice", [("/account", "click", {})],
         'The account\'s display name is Alice Johnson. It has 1 saved item(s) and 0 '
         'tracked item(s).'),
    28: ("bob", [("/search?q=Fashion+Nova+blue+light+glasses", "press", {"key": "Enter"}),
                 ("/product/gs0bd853df962d4d0f", "click", {}),
                 ("/saved", "click", {})],
         'I saved "Fashion Nova Women\'s Beauty And Brains Blue Light Glasses" to the '
         'shopping list; it is the cheapest Fashion Nova blue-light glasses product priced '
         'above 3 dollars, at $3.98.'),
    29: ("david", [("/search?q=edikted+glasses", "press", {"key": "Enter"}),
                   ("/product/gsdbc82b9ec167c52c", "click", {}),
                   ("/search?q=edikted+glasses", "press", {"key": "Enter"}),
                   ("/product/gs8613f95434064d79", "click", {}),
                   ("/saved", "click", {})],
         'I saved the two cheapest edikted blue-light glasses products: "Blue Light '
         'Rectangle Glasses" ($4.40) and "Raquella Rectangle Blue Light Glasses" ($4.40). '
         'The total price of the two items combined is $8.80.'),
}

# after-DB mutations for the honest stateful runs: (sql, params) lists
SAVED = "INSERT INTO saved_items (user_id, product_id, added) VALUES (?, ?, '2026-09-22')"
TRACKED = "INSERT INTO tracked_products (user_id, product_id, created) VALUES (?, ?, '2026-09-22')"
HONEST_MUTATIONS = {
    21: [(SAVED, (2, 41))],
    22: [(TRACKED, (3, 36))],
    23: [(SAVED, (1, 3)),
         ("DELETE FROM saved_items WHERE user_id = 1 AND product_id = 28", ())],
    24: [(TRACKED, (3, 13)), (TRACKED, (3, 14)), (TRACKED, (3, 15))],
    25: [(TRACKED, (4, 59))],
    26: [("INSERT INTO users (email, display_name, password_hash, created) VALUES "
          "('jordan.lee@test.com', 'Jordan Lee', '$2b$12$D/eRvVSrDoJ8.PZPF9Q/NOMd64jKdJ82.HbfdAntTLr58aoJs6gj.', "
          "'2026-09-22')", ())],
    28: [(SAVED, (2, 22))],
    29: [(SAVED, (4, 12)), (SAVED, (4, 39))],
}

# wrong answers: honest navigation, one key fact altered (must FAIL)
WRONG = {
    0: 'The subtitle line reads "Top deals" and the Gap Factory card shows $130.',
    1: 'The Departments page lists 14 departments and the first tile is "Electronics".',
    2: 'The Explore button loads the query "Trench coats" with 30 results.',
    3: 'The FIRST section is "Bye bye blue light" and the SECOND is "The iconic trench".',
    4: 'The cheapest result is "Gap Factory Women\'s Modern Trench Coat" at $64.99.',
    5: 'The search shows 5 results and the lowest current price is $3.98.',
    6: 'The search returns 13 results and the most expensive is sold by LOFT.',
    7: 'The top two results are "St Barts Bluelight" at $50 and "Buy Cruise" at $48.50.',
    8: '4 of the listed products are sold by TikTok Shop and the second listed '
       "product is \"AE Classic Tortoise Shell Blue Light Glasses Women's\".",
    9: 'The most expensive product is "COTTON TRENCH COAT" at $1,294 from yoox.com.',
    10: 'The title is "Fashion Nova Yes Sir Bluelight", the price is $5.99 and the discount is 35% OFF.',
    11: 'The product shows a star rating of 4.5 and 12 reviews.',
    12: '4 of the listed products are sold by BlockBlueLight and the first listed product is "BlockBlueLight NightFall Billie Blue Blocking Glasses Red Lenses Glasses".',
    13: 'The Billie glasses cost $71.96 and the Taylor glasses cost $69.96, so the Taylor is cheaper.',
    14: 'The trench jacket costs $1,290 and the COTTON TRENCH COAT costs $1,294; the COTTON TRENCH COAT is cheaper by $4.00.',
    15: 'In the "Compare with similar items" section, 3 of the listed products are sold by "yoox.com", and the first listed product is "Aritzia Women\'s The Finch Trench Coat".',
    16: 'The cheapest qualifying trench coat is "Gap Factory Women\'s Modern Trench Coat" from Gap Factory at $64.99.',
    17: 'The biggest discount on the Deals page is "COTTON TRENCH COAT" with 72% OFF.',
    18: '9 products have a discount of 70% or more and the most frequent merchant is edikted.',
    19: 'The most expensive deal is "Trench coat" at $234 with an 82% discount.',
    20: 'The list contains "Aritzia Women\'s The Finch Trench Coat" from Aritzia at $265.',
    21: 'The shopping list contains 2 items and the saved item shows $45.',
    22: 'The tracked product is "St Barts Bluelight" at $50.',
    23: 'The list still contains "Gap Factory Women\'s Modern Trench Coat" at $64.99.',
    24: 'The most expensive tracked product is "Buy Strike" at $47.00.',
    25: 'The tracked product is "COTTON TRENCH COAT" at $1,294.',
    26: 'After registering, the shopping list contains 3 items.',
    27: 'The display name is Alice Johnson, with 2 saved items and 1 tracked item.',
    28: 'I saved "Fashion Nova Women\'s Leave A Memo Blue Light Glasses" at $2.98.',
    29: 'I saved "Arlo Oval Blue Light Glasses" ($11.00) and "Clark Oval Blue Light Glasses" ($11.00), totaling $22.00.',
}


def honest_fixture(tmp_path: Path, n: int, answer: str | None = None):
    login_key, steps, honest_answer = HONEST[n]
    run_dir = tmp_path / f"honest_{n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    if login_key:
        email, display = LOGIN[login_key]
        build_run(run_dir, f"Google Shopping--{n}", steps, answer or honest_answer, login=(email, display))
    else:
        build_run(run_dir, f"Google Shopping--{n}", steps, answer or honest_answer)
    initial_db = copy_db(tmp_path / f"initial_{n}.db")
    after_db = copy_db(tmp_path / f"after_{n}.db")
    for sql, params in HONEST_MUTATIONS.get(n, []):
        mutate_db(after_db, [(sql, params)])
    return run_dir, initial_db, after_db


# ---------------------------------------------------------------- honest PASS x30
@pytest.mark.parametrize("n", range(30))
def test_honest_passes(tmp_path, n):
    run_dir, initial_db, after_db = honest_fixture(tmp_path, n)
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- no-op FAIL x30
@pytest.mark.parametrize("n", range(30))
def test_noop_fails(tmp_path, n):
    run_dir = noop_run(tmp_path / f"noop_{n}", f"Google Shopping--{n}")
    initial_db = copy_db(tmp_path / f"noop_initial_{n}.db")
    after_db = copy_db(tmp_path / f"noop_after_{n}.db")
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "final_answer_nonempty"


# ---------------------------------------------------------------- wrong answer FAIL x30
@pytest.mark.parametrize("n", range(30))
def test_wrong_answer_fails(tmp_path, n):
    run_dir, initial_db, after_db = honest_fixture(tmp_path, n, answer=WRONG[n])
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] != "all checks passed"
    assert verdict.get("infra_error") is not True  # a substantive answer failure, not a crash


# ---------------------------------------------------------------- shortcut FAIL
# Correct answer but the agent never left the homepage: every task whose required surface
# is beyond the homepage MUST FAIL (tasks 0 and 3 are homepage-surface by design — their
# navigation gate is the homepage itself, so a homepage-only correct run is legitimate).
SHORTCUT_EXPECT_FAIL = sorted(set(range(30)) - {0, 3})


@pytest.mark.parametrize("n", SHORTCUT_EXPECT_FAIL)
def test_shortcut_fails(tmp_path, n):
    _, _, honest_answer = HONEST[n]
    run_dir = build_run(tmp_path / f"shortcut_{n}", f"Google Shopping--{n}",
                        [("/", "click", {})], honest_answer)
    initial_db = copy_db(tmp_path / f"shortcut_initial_{n}.db")
    after_db = copy_db(tmp_path / f"shortcut_after_{n}.db")
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)


@pytest.mark.parametrize("n", [0, 3])
def test_homepage_surface_tasks_documented(tmp_path, n):
    """Tasks 0 and 3 are homepage-surface by design: a homepage-only run with the correct
    facts is a legitimate solve (their facts are catalog-specific and cannot be recalled
    without opening the mirror), so the shortcut case reduces to the honest case."""
    run_dir, initial_db, after_db = honest_fixture(tmp_path, n)
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is True


# ---------------------------------------------------------------- read-only DB tamper
@pytest.mark.parametrize("n", READ_ONLY)
def test_readonly_db_tamper_fails(tmp_path, n):
    run_dir, initial_db, after_db = honest_fixture(tmp_path, n)
    mutate_db(after_db, [(SAVED, (2, 41))])  # a rogue saved row the task never wrote
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "read_only_db_unchanged"


# ---------------------------------------------------------------- stateful: state mismatch + collateral
@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_state_mismatch_fails(tmp_path, n):
    """Agent self-reports success but the DB is unchanged -> FAIL."""
    login_key, steps, honest_answer = HONEST[n]
    run_dir = build_run(tmp_path / f"sm_{n}", f"Google Shopping--{n}", steps, honest_answer,
                        login=LOGIN[login_key] if login_key else None)
    initial_db = copy_db(tmp_path / f"sm_initial_{n}.db")
    after_db = copy_db(tmp_path / f"sm_after_{n}.db")  # clean: the expected delta is missing
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False


@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_collateral_write_fails(tmp_path, n):
    """The honest delta PLUS a collateral row another user never asked for -> FAIL."""
    run_dir, initial_db, after_db = honest_fixture(tmp_path, n)
    if n in (21, 28, 29):          # saved-item tasks get a rogue tracked row and vice versa
        mutate_db(after_db, [(TRACKED, (1, 5))])
    else:
        mutate_db(after_db, [(SAVED, (3, 10))])
    verdict = run_verifier(n, run_dir, initial_db, after_db)
    assert verdict["pass"] is False


# ---------------------------------------------------------------- package tampering (task 8 shape)
def _task8_honest(tmp_path):
    return honest_fixture(tmp_path, 8)


def test_tampered_task_id_fails(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["task_id"] = "Google Shopping--12"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "trajectory_task_matches"


def test_offsite_url_fails(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://example.com/search?q=St+Barts"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "all_urls_match_local_origin"


def test_broken_screenshot_fails(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    (run_dir / "screenshots" / "step_001.png").write_bytes(b"this is not a png")
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "screenshots_decode"


def test_missing_screenshot_fails(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    (run_dir / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "screenshots_decode"


def test_tampered_seed_fails_closed(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    mutate_db(initial_db, [("UPDATE products SET price = 1.0 WHERE id = 41", ())])
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True
    assert verdict["reason"] == "snapshot_contract_invalid"


def test_unavailable_db_fails_closed(tmp_path):
    run_dir, _, _ = _task8_honest(tmp_path)
    verdict = run_verifier(8, run_dir, Path("/nonexistent/initial.db"),
                           Path("/nonexistent/after.db"), container="definitely-not-a-container")
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True
    assert verdict["reason"] == "database_unavailable"


def test_terminated_without_done_fails(tmp_path):
    run_dir, initial_db, after_db = _task8_honest(tmp_path)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    traj["termination_reason"] = "max_steps"
    (run_dir / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(8, run_dir, initial_db, after_db)
    assert verdict["pass"] is False
    assert verdict["reason"] == "trajectory_completed"
