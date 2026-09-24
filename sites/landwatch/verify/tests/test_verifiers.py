"""Deterministic verifier contract tests for the 15 redesigned LandWatch tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage
only, empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a
shortcut (correct answer, homepage-only navigation) MUST FAIL for every
task — each redesigned task requires a surface beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL
on state-mismatch (claimed success with an unchanged / wrongly-changed /
wrong-row DB) and on a collateral delta. Package tampering (task_id
mismatch, off-site URLs, broken screenshots, tampered seed, unavailable DB)
MUST fail closed.

No docker, no LLM: snapshots are seed copies mutated through sqlite, and
trajectories are hand-written in the agent_demo/agent.py shape.
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

N_TASKS = 15
STATEFUL = {9, 10, 11}
READ_ONLY = sorted(set(range(N_TASKS)) - STATEFUL)
BOB = "bob.c@test.com"
ALICE = "alice.j@test.com"
TS = "2026-09-24T00:00:00"

DETAIL_SISTERDALE = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
DETAIL_TUCKED = "/burnet-county-texas-farms-and-ranches-for-sale/pid/428212638"
DETAIL_3DM = "/moffat-county-colorado-farms-and-ranches-for-sale/pid/424462143"
DETAIL_WW = "/palo-pinto-county-texas-farms-and-ranches-for-sale/pid/419682125"
DETAIL_OHIO = "/allen-county-ohio-farms-and-ranches-for-sale/pid/427843237"
SWOPE_PROFILE = "/profile/louie-swope/1437140"
COALSON_PROFILE = "/profile/mac-a-coalson/32197"


def bob_favorite_statements(pid: int, ts: str = TS):
    return [("INSERT INTO favorites (user_id, pid, created_at) VALUES (2, ?, ?)", (pid, ts))]


def bob_saved_search_statements(url="/hunting-property/price-250000-499999",
                                name="Hunting Land for Sale - 1-7 of 7 Listings", ts=TS):
    return [("INSERT INTO saved_searches (user_id, name, url, alerts, created_at) "
             "VALUES (2, ?, ?, 0, ?)", (name, url, ts))]


def alice_saved_search_statements(ts: str = TS):
    return [("INSERT INTO saved_searches (user_id, name, url, alerts, created_at) "
             "VALUES (1, 'Montana Land for Sale - 1-8 of 8 Listings', "
             "'/montana-land-for-sale', 0, ?)", (ts,))]


def register_statements(ts: str = TS):
    return ([("INSERT INTO users (email, password_hash, name, phone, created_at, is_benchmark) "
              "VALUES ('new.landbuyer@test.com', "
              "'b35294c904271b106649528602ef203b3b3621b3c14f7ea81e051a702a1791e7', "
              "'Alex Reviewer', NULL, ?, 0)", (ts,))]
            + session_statements(5, "new.landbuyer@test.com", ts)
            + [("INSERT INTO favorites (user_id, pid, created_at) VALUES (5, 424029660, ?)", (ts,)),
               ("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
               "VALUES (5, 427843237, 'Alex Reviewer', 'alex.reviewer@test.com', '', "
               "'Could you share the soil quality reports for this farmland?', ?)", (ts,))])


# ---------------------------------------------------------------- honest fixtures
# (login email or None, [(path, action, params), ...], honest answer, after-DB mutations)
HONEST = {
    0: (None, [("/", "fill", {"text": "Austin", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/austin", "click", {"selector": ".lw-suggest-item"}),
               ("/texas-land-for-sale/austin", "read", {}),
               ("/", "fill", {"text": "Harris", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/harris-county", "click", {"selector": ".lw-suggest-item"}),
               ("/texas-land-for-sale/harris-county", "read", {}),
               ("/", "fill", {"text": "Boerne", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/boerne", "click", {"selector": ".lw-suggest-item"}),
               ("/texas-land-for-sale/boerne", "read", {})],
        "Austin, TX shows 1 listing: '111 AC In the Heart of the Hill Country' at $6,100,000 "
        "for 111 Acres. Harris County, TX shows 1 listing: 'A private 10-acre estate in "
        "Cypress' at $5,750,000 for 10 Acres. Boerne, TX shows 4 listings, the first being "
        "'Sisterdale Farms' at $19,400,000 for 310 Acres. On price per acre, Austin's first "
        "listing (about $54,955 per acre) is the better value.", []),
    1: (None, [("/", "fill", {"text": "Boerne", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/boerne", "click", {"selector": ".lw-suggest-item"}),
               (DETAIL_SISTERDALE, "click", {"selector": ".lw-result-title a"}),
               ("/", "fill", {"text": "Burnet", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/burnet-county", "click", {"selector": ".lw-suggest-item"}),
               (DETAIL_TUCKED, "click", {"selector": ".lw-result-title a"})],
        "Sisterdale Farms is listed at $19,400,000 for 310 Acres with listing agent Louie "
        "Swope of West & Swope Ranches. 'Tucked into the Hill Country' is listed at "
        "$25,950,000 for 1,228 Acres with listing agent Jordan Shipley of Shipley Ranches. "
        "Tucked into the Hill Country is the larger property by 918 acres.", []),
    2: (None, [("/", "fill", {"text": "Kendall", "selector": "input[name=q]"}),
               ("/texas-land-for-sale/kendall-county", "click", {"selector": ".lw-suggest-item"}),
               (DETAIL_SISTERDALE, "click", {"selector": ".lw-result-title a"}),
               ("/find-agent", "click", {}),
               ("/find-agent?state=TX", "click", {"selector": "button[type=submit]"}),
               (SWOPE_PROFILE, "click", {"selector": ".lw-agent-card-name"})],
        "Sisterdale Farms: $19,400,000, 310 Acres, 5 Beds and 5 Baths, 'View all 93 "
        "pictures'. The first two Highlights bullets: '11,800\u00b1 SF custom stone home "
        "with 7 Rumford fireplaces and panoramic Hill Country views' and 'Over one third "
        "mile of Guadalupe River frontage with senior water rights'. Activities: Camping, "
        "Canoeing/Kayaking, Fishing, Horseback Riding, Hunting, Off-roading. The listing "
        "agent Louie Swope's profile shows 2 Total Listings, a $19M - $21M Price Range, a "
        "310.00 - 844 ac Acre Range, and he is based in San Antonio, TX.", []),
    3: (None, [("/texas-land-for-sale", "click", {}),
               ("/texas-land-for-sale/price-over-1000000", "click", {"selector": ".lw-facet-item a"}),
               ("/texas-land-for-sale/price-over-1000000?sort=price-low", "click",
                {"selector": "[data-sort=price-low]"}),
               ("/undeveloped-land", "click", {}),
               ("/undeveloped-land/price-50000-99999", "click", {"selector": ".lw-facet-item a"}),
               ("/undeveloped-land/price-50000-99999?sort=price-low", "click",
                {"selector": "[data-sort=price-low]"})],
        "Texas at $1,000,000 and up, sorted cheapest first: 81 listings. The three cheapest "
        "are 'East Texas Poultry Farm LOCATED NEAR COOKVILLE TEXAS' at $1,050,000 in Titus "
        "County, 'Gorgeous 42 Acres' at $1,050,000 in Parker County, and 'Carlton Longleaf "
        "Tract' at $1,072,500 in Trinity County. Undeveloped Land in the $50,000 - $99,999 "
        "band: 3 listings, the cheapest being 'Jaz Meadows 2-Acre Homesites' at $77,500 in "
        "Navarro County. The undeveloped track's cheapest property costs less.", []),
    4: (None, [("/hunting-property", "click", {}),
               ("/hunting-property/acres-under-10", "click", {"selector": ".lw-facet-item a"}),
               ("/hunting-property/acres-under-10/with-residence", "click",
                {"selector": ".lw-facet-item a"}),
               ("/hunting-property/acres-under-10/with-residence?sort=price-low", "click",
                {"selector": "[data-sort=price-low]"}),
               ("/hunting-property/acres-under-10/beds-over-4/with-residence", "click",
                {"selector": ".lw-facet-item a"}),
               ("/hunting-property/acres-under-10/beds-over-4/with-residence?sort=newest",
                "click", {"selector": "[data-sort=newest]"})],
        "Hunting Land narrows from 176 listings to 6 after the 0 - 10 Acres layer and to "
        "3 after the Residence: Yes layer. With those two filters stacked and sorted "
        "Price: Low to High, the cheapest property is 'Private Log Home & Workshop' at "
        "$640,000 in Albemarle County, VA. Adding the 4+ Bedrooms filter leaves 1 "
        "listing. Sorted by newest, the most recently listed property is 'Cannon Falls "
        "Oasis' at $1,399,000 in MN.", []),
    5: (None, [("/colorado-land-for-sale", "click", {}),
               ("/colorado-land-for-sale?sort=acres-high", "click", {"selector": "[data-sort=acres-high]"}),
               (DETAIL_3DM, "click", {"selector": ".lw-result-title a"}),
               ("/colorado-land-for-sale?sort=acres-high", "click", {"selector": ".lw-back-btn"}),
               ("/montana-land-for-sale", "click", {}),
               ("/montana-land-for-sale/acres-over-1000", "click", {"selector": ".lw-facet-item a"})],
        "Colorado's largest property is '3D Mountain Ranch': $6,995,000 for 11,764 Acres; "
        "the Type row reads Farms and Ranches, Recreational Property, Hunting Property. The "
        "second-largest Colorado property is 'Ragged Spur Ranch' at 3,760 Acres. Montana "
        "over 1,000 acres has 3 matches: 'Montana Legacy Ranch' (11,689 Acres), 'Mullendore "
        "Ranch' (10,510 Acres), and '2,341 Ac Montana Creek Ranch' (3,336 Acres). Colorado's "
        "largest ranch is bigger by 75 acres.", []),
    6: (None, [("/land/auctions", "click", {}),
               ("/land/auctions/page-2", "click", {"selector": ".lw-pagination a"}),
               ("/hunting-property/auctions", "click", {})],
        "The all-land auction page shows 47 listings. The first two auctions are 'Prime Ohio "
        "Farmland' (100 Acres, auction date 2026-09-28) and 'Prime 225-Acre Iowa Farm' "
        "(225 Acres, auction date 2026-10-28). On page two, the very last auction is "
        "'40\u00b1 Acres of Farmland, Woods & Pasture near Hillsdale, WI' (40 Acres, "
        "auction date 2026-09-08). The Hunting Land auctions page shows 25 listings.", []),
    7: (None, [("/texas-land-for-sale", "click", {}),
               ("/texas-land-for-sale/houston-region", "click", {"selector": ".lw-facet-item a"}),
               ("/texas-land-for-sale", "click", {}),
               ("/texas-land-for-sale/parker-county", "click", {"selector": ".lw-facet-item a"}),
               ("/texas-land-for-sale/parker-county?sort=price-high", "click",
                {"selector": "[data-sort=price-high]"})],
        "The Houston Region results page shows 5 listings; the first is 'Kountze "
        "Countryside Retreat' at $510,600 for 74 Acres. Parker County leads the County "
        "filter group with 19 listings; sorted by price high to low, its most expensive "
        "listing is '2,856 acre Brazos River Ranch' at $39,041,450.", []),
    8: (None, [("/find-agent", "click", {}),
               (COALSON_PROFILE, "click", {"selector": ".lw-agent-card-name"}),
               (DETAIL_WW, "click", {"selector": ".lw-card-photo a"})],
        "The busiest broker is Mac A. Coalson of Coalson Real Estate, based in Weatherford, "
        "TX: 11 Total Listings, a $1.1M - $50M Price Range, and a 22.50 - 5896 ac Acre "
        "Range. The first listing in his grid, '5,888-acre W-W Ranch', is Available at "
        "$49,985,000 for 5,896 Acres; its Type row reads Farms and Ranches, Recreational "
        "Property, Hunting Property, House.", []),
    9: (BOB, [("/", "fill", {"text": "Boerne", "selector": "input[name=q]"}),
              ("/texas-land-for-sale/boerne", "click", {"selector": ".lw-suggest-item"}),
              ("/texas-land-for-sale/boerne", "click", {"selector": "[data-favorite-pid]"}),
              ("/", "fill", {"text": "Burnet", "selector": "input[name=q]"}),
              ("/texas-land-for-sale/burnet-county", "click", {"selector": ".lw-suggest-item"}),
              ("/texas-land-for-sale/burnet-county", "click", {"selector": "[data-favorite-pid]"}),
              ("/hunting-property", "click", {}),
              ("/hunting-property/price-250000-499999", "click", {"selector": ".lw-facet-item a"}),
              ("/hunting-property/price-250000-499999", "click", {"selector": "[data-save-search]"}),
              ("/account", "click", {}),
              ("/account", "click", {"selector": ".lw-mini-listing form button"})],
        "After saving both candidates the account shows 6 saved properties. The Hunting "
        "Land search was stored under the exact name 'Hunting Land for Sale - 1-7 of 7 "
        "Listings' linking to /hunting-property/price-250000-499999. After removing the "
        "smaller candidate, 5 saved properties remain, with 'Tucked into the Hill Country' "
        "still saved.",
        session_statements(2, BOB) + bob_favorite_statements(428212638)
        + bob_saved_search_statements()),
    10: (ALICE, [("/account/edit", "click", {}),
                 ("/account/edit", "fill", {"text": "(512) 555-0164", "selector": "input[name=phone]"}),
                 ("/account", "click", {"selector": "button[type=submit]"}),
                 ("/montana-land-for-sale", "click", {}),
                 ("/montana-land-for-sale", "click", {"selector": "[data-save-search]"}),
                 ("/account", "click", {})],
         "The success message said 'Profile updated.' and the profile card now shows the "
         "phone (512) 555-0164. The Montana land-for-sale page was stored under the exact "
         "name 'Montana Land for Sale - 1-8 of 8 Listings'. The account ends up with 4 "
         "saved searches.",
         session_statements(1, ALICE)
         + [("UPDATE users SET phone = '(512) 555-0164' WHERE id = 1", ())]
         + alice_saved_search_statements()),
    11: (None, [("/log-in", "click", {}),
                ("/register", "click", {}),
                ("/register", "fill", {"text": "Alex Reviewer", "selector": "input[name=name]"}),
                ("/register", "fill", {"text": "new.landbuyer@test.com", "selector": "input[name=email]"}),
                ("/register", "fill", {"text": "LandBuyer2026!", "selector": "input[name=password]"}),
                ("/account", "click", {"selector": "button[type=submit]"}),
                ("/", "fill", {"text": "Boerne", "selector": "input[name=q]"}),
                ("/texas-land-for-sale/boerne", "click", {"selector": ".lw-suggest-item"}),
                ("/texas-land-for-sale/boerne", "click", {"selector": "[data-favorite-pid]"}),
                ("/", "fill", {"text": "Allen", "selector": "input[name=q]"}),
                ("/ohio-land-for-sale/allen-county", "click", {"selector": ".lw-suggest-item"}),
                (DETAIL_OHIO, "click", {"selector": ".lw-result-title a"}),
                (DETAIL_OHIO, "fill", {"text": "Alex Reviewer", "selector": "input[name=name]"}),
                (DETAIL_OHIO, "fill", {"text": "alex.reviewer@test.com", "selector": "input[name=email]"}),
                (DETAIL_OHIO, "fill", {"text": "Could you share the soil quality reports "
                                     "for this farmland?", "selector": "textarea[name=message]"}),
                (DETAIL_OHIO, "click", {"selector": ".lw-contact-form button[type=submit]"}),
                ("/account", "click", {})],
        "The new account lands on My LandWatch. Favorites empty state: 'You haven't saved "
        "any properties yet. Tap the heart icon on any listing to save it here.' Saved "
        "Searches empty state: 'No saved searches yet. Use the Save Search button on any "
        "search results page.' My Inquiries empty state: 'No inquiries yet. Use the contact "
        "form on any listing page.' After the first session: '43 ac Iron Rapids Ranch' is "
        "saved in Favorites; the inquiry was confirmed with 'Your message has been sent to "
        "the listing agent.' and My Inquiries shows the record to Alex Reviewer — "
        "alex.reviewer@test.com with the soil-quality question.", register_statements()),
    12: (None, [("/", "click", {"selector": "body"}),
                ("/hunting-property", "click", {})],
        "Featured carousel, first three properties: $450,000 / 20.18 Acres / WV; $299,000 / "
        "25 Acres / VA; $799,900 / 5.87 Acres / UT. The first four category tiles: Land for "
        "Sale 436 Land Properties, Farms and Ranches 233 Farms and Ranches Properties, "
        "Hunting Land 176 Hunting Land Properties, Homesites 53 Homesites Properties. The "
        "Hunting Land category page's results heading shows 176 listings — it matches the "
        "tile count.", []),
    13: (None, [("/texas-land-for-sale", "click", {}),
                ("/texas-land-for-sale/waterfront-property", "click", {"selector": ".lw-facet-item a"}),
                ("/texas-land-for-sale/waterfront-property?sort=price-high", "click",
                 {"selector": "[data-sort=price-high]"}),
                ("/texas-land-for-sale", "click", {"selector": ".lw-chip a"}),
                ("/texas-land-for-sale?sort=price-high", "click", {"selector": "[data-sort=price-high]"})],
        "Texas has 27 waterfront land listings. The most expensive is '2,856 acre Brazos "
        "River Ranch' at $39,041,450 for 2,359 Acres. Clearing the waterfront filter, the "
        "single most expensive land listing in all of Texas is 'Blake Ranch' at "
        "$56,997,000. Blake Ranch costs more, and it is not a waterfront property.", []),
    14: (None, [("/land", "click", {}),
                ("/land?priceMin=100000&priceMax=250000", "click", {"selector": ".lw-custom-range button"}),
                ("/land", "click", {"selector": ".lw-chip a"}),
                ("/land?acresMin=100&acresMax=200", "click", {"selector": ".lw-custom-range button"})],
        "Within the custom price range $100,000 - $250,000, 38 listings match; the first is "
        "'Beautiful Live Water Property' at $209,800 in Williamson County, and the Sale "
        "Type filter group counts 38 For Sale and 0 Auction within the budget. With the "
        "custom size range of 100 - 200 acres, 71 listings match; the first is 'Gaddistown "
        "on the Toccoa' at $6,500,000.", []),
}

# wrong answers: plausible but contradicted by the frozen seed
WRONG = {
    0: "Austin shows 2 listings, the first 'Hill Country Retreat' at $6,000,000 for 110 "
       "Acres. Harris County shows 2 listings at $5,700,000 for 12 Acres. Boerne shows 5 "
       "listings, the first 'Boerne Farms' at $19,000,000 for 300 Acres. Harris County is "
       "the better value per acre.",
    1: "Sisterdale Farms: $19,000,000 for 300 Acres with Louie Swope of West & Swope "
       "Ranches. Tucked into the Hill Country: $25,000,000 for 1,200 Acres with Jordan "
       "Shipley of Shipley Land. Sisterdale Farms is the larger property by 100 acres.",
    2: "$19,000,000, 300 Acres, 4 Beds and 4 Baths, 90 pictures. The Highlights mention a "
       "stone home and river frontage; the activities are Camping, Fishing and Hunting. "
       "Louie Swope: 3 Total Listings, $19M - $20M, 300 - 800 ac, based in Austin, TX.",
    3: "Texas $1M+: 80 listings; the cheapest are 'East Texas Ranch' at $1,100,000 in "
       "Titus County, 'Gorgeous 40 Acres' at $1,060,000 in Parker County, and 'Carlton "
       "Tract' at $1,080,000. Undeveloped $50-99K: 4 listings, the cheapest 'Jaz Meadows' "
       "at $70,000 in Navarro. The Texas track costs less.",
    4: "Hunting Land: 6 listings after 0 - 10 Acres, 4 after Residence: Yes, and 2 after 4+ "
       "Bedrooms. The cheapest under the stacked filters is 'Hunt, Fish, Boat, Hike!!' at "
       "$749,000 in Missoula County, MT. The newest listing is 'Cannon Falls Retreat' at "
       "$1,390,000 in Wisconsin.",
    5: "Colorado's largest is '3D Mountain Ranch': 11,000 Acres at $6,500,000; Type row: "
       "Farms and Ranches and Recreational Property. Second-largest: 'Ragged Spur Ranch' "
       "at 3,700 Acres. Montana: 'Montana Legacy Ranch' (11,700 Acres) and 'Mullendore "
       "Ranch' (10,500 Acres). Montana's largest ranch is bigger by 50 acres.",
    6: "46 auctions. The first two are 'Prime Ohio Farmland' (100 Acres, 2026-09-30) and "
       "'Prime Iowa Farm' (220 Acres, 2026-10-30). Page two ends with 'Hillsdale Farmland' "
       "(45 Acres, 2026-09-10). The Hunting Land auctions page shows 24 listings.",
    7: "The Houston Region shows 4 listings; the first is 'Kountze Country Retreat' at "
       "$510,000 for 7 Acres. Tarrant County leads with 19 listings; the priciest there is "
       "'Brazos Ranch' at $39,000,000.",
    8: "Mac Coalson of Coalson Realty: 10 Total Listings, $1M - $50M, 20 - 5000 ac, based "
       "in Fort Worth. The first listing 'W-W Ranch' is Under Contract at $49,000,000 for "
       "5,000 Acres; Type row: Farms and Ranches, Recreational Property, House.",
    9: "The account now has 7 saved properties. The search was saved as 'Hunting Land' "
       "with URL /hunting-property. After removing one candidate, 4 saved properties "
       "remain with 'Sisterdale Farms' still saved.",
    10: "The success message said 'Saved.' and the profile card shows (512) 555-0139. The "
        "Montana search was stored under the name 'Montana Land'. The account ends up with "
        "3 saved searches.",
    11: "The account lands on My Account. Favorites: 'No saved properties yet.' Saved "
        "Searches: 'No searches yet.' My Inquiries: 'No messages yet.' The saved property "
        "is 'Iron Rapids Ranch' and the inquiry was confirmed with 'Thank you for your "
        "inquiry.'",
    12: "The first three featured properties: $450,000 / 20 Acres / Virginia; $299,000 / "
        "25 Acres / West Virginia; $799,900 / 5 Acres / Utah. Tiles: Land for Sale 400, "
        "Farms and Ranches 200, Hunting Land 150, Homesites 50. The Hunting Land page "
        "shows 176 listings, which does not match the tile count.",
    13: "Texas has 62 waterfront listings; the most expensive is 'BW Ranch' at $24,500,000 "
        "for 1,900 Acres. The most expensive listing in all of Texas is 'Blake Ranch' at "
        "$56,000,000. The Brazos River Ranch costs more, and Blake Ranch is a waterfront "
        "property.",
    14: "The $100,000 - $250,000 range shows 30 listings; the first is '190 BLUFFS ON THE "
        "POTOMAC ~ 24.02 AC' at $150,000 in Mineral County. Sale Type: 30 For Sale and 1 "
        "Auction. The 100 - 200 acre range shows 70 listings; the first is 'Clay County "
        "MN Farm Land' at $1.",
}


def honest_run(root: Path, task_n: int) -> tuple[Path, Path, Path]:
    """(run_dir, initial_db, after_db) for the honest fixture of one task."""
    login, steps, answer, mutations = HONEST[task_n]
    run_dir = build_run(root, f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(root / "initial.db")
    after_db = mutate_db(copy_db(root / "after.db"), mutations)
    return run_dir, initial_db, after_db


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_honest_pass(tmp_path, task_n):
    run_dir, initial_db, after_db = honest_run(tmp_path, task_n)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=1)[:2400]


@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_noop_fail(tmp_path, task_n):
    run_dir = noop_run(tmp_path / "run", f"LandWatch--{task_n}")
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = copy_db(tmp_path / "after.db")
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]
    assert verdict.get("reason") == "final_answer_nonempty"


@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_wrong_answer_fail(tmp_path, task_n):
    login, steps, _answer, mutations = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps,
                        WRONG[task_n], login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]
    # the failing check must be an answer / navigation fact, never an infra error
    assert not verdict.get("infra_error"), verdict


@pytest.mark.parametrize("task_n", range(N_TASKS))
def test_shortcut_fail(tmp_path, task_n):
    """Correct answer, homepage-only navigation -> FAIL (anti knowledge-shortcut).

    Every redesigned task grades a surface beyond the homepage, so the old
    'homepage-surface by design' exceptions are gone.
    """
    _login, _steps, answer, mutations = HONEST[task_n]
    b = RunBuilder(tmp_path / "run", f"LandWatch--{task_n}")
    b.step("/", "click", {"selector": "body"})
    b.done(answer)
    run_dir = b.write()
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]
    assert verdict.get("reason") != "final_answer_nonempty", verdict


@pytest.mark.parametrize("task_n", READ_ONLY)
def test_readonly_tamper_fail(tmp_path, task_n):
    """Honest trajectory + a mutated after-DB (agent hid a write) -> FAIL."""
    run_dir, initial_db, _after = honest_run(tmp_path / "honest", task_n)
    tampered = mutate_db(copy_db(tmp_path / "after.db"),
                         [("INSERT INTO favorites (user_id, pid, created_at) "
                           "VALUES (1, 428237808, '2026-09-24T00:00:00')", ())])
    verdict = run_verifier(task_n, run_dir, initial_db, tampered)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]
    assert "read_only_db_unchanged" in json.dumps(verdict)


@pytest.mark.parametrize("task_n,mutations", [
    # T9: claimed the session but no favorites/search rows -> FAIL
    (9, session_statements(2, BOB)),
    # T9: wrong listing kept (Sisterdale instead of Tucked) -> FAIL
    (9, session_statements(2, BOB) + bob_favorite_statements(425766087)
     + bob_saved_search_statements()),
    # T9: saved under the wrong URL -> FAIL
    (9, session_statements(2, BOB) + bob_favorite_statements(428212638)
     + bob_saved_search_statements(url="/hunting-property")),
    # T9: cross-user tamper — the favorite row belongs to carol -> FAIL
    (9, session_statements(2, BOB)
     + [("INSERT INTO favorites (user_id, pid, created_at) VALUES (3, 428212638, ?)", (TS,))]
     + bob_saved_search_statements()),
    # T9: over-eager run keeps BOTH candidates -> FAIL (two added favorite rows)
    (9, session_statements(2, BOB) + bob_favorite_statements(425766087)
     + bob_favorite_statements(428212638) + bob_saved_search_statements()),
    # T10: phone unchanged -> FAIL
    (10, session_statements(1, ALICE) + alice_saved_search_statements()),
    # T10: wrong phone saved -> FAIL
    (10, session_statements(1, ALICE)
     + [("UPDATE users SET phone = '(512) 555-0000' WHERE id = 1", ())]
     + alice_saved_search_statements()),
    # T10: saved search missing -> FAIL
    (10, session_statements(1, ALICE)
     + [("UPDATE users SET phone = '(512) 555-0164' WHERE id = 1", ())]),
    # T10: saved search stored under the wrong name -> FAIL
    (10, session_statements(1, ALICE)
     + [("UPDATE users SET phone = '(512) 555-0164' WHERE id = 1", ())]
     + [("INSERT INTO saved_searches (user_id, name, url, alerts, created_at) "
         "VALUES (1, 'Montana Land for Sale', '/montana-land-for-sale', 0, ?)", (TS,))]),
    # T11: no registered user row -> FAIL
    (11, []),
    # T11: registered with the wrong password -> FAIL
    (11, [("INSERT INTO users (email, password_hash, name, phone, created_at, is_benchmark) "
           "VALUES ('new.landbuyer@test.com', '" + "0" * 64 + "', 'Alex Reviewer', NULL, "
           "?, 0)", (TS,))]),
    # T11: favorite row missing -> FAIL
    (11, [stmt for stmt in register_statements()
          if not stmt[0].startswith("INSERT INTO favorites")]),
    # T11: inquiry row missing -> FAIL
    (11, [stmt for stmt in register_statements()
          if not stmt[0].startswith("INSERT INTO inquiries")]),
    # T11: inquiry on the wrong listing -> FAIL
    (11, register_statements()
     + [("DELETE FROM inquiries WHERE id = 4", ()),
        ("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
         "VALUES (5, 428237808, 'Alex Reviewer', 'alex.reviewer@test.com', '', "
         "'Could you share the soil quality reports?', ?)", (TS,))]),
    # T11: inquiry message does not ask about soil -> FAIL
    (11, register_statements()
     + [("DELETE FROM inquiries WHERE id = 4", ()),
        ("INSERT INTO inquiries (user_id, pid, name, email, phone, message, created_at) "
         "VALUES (5, 427843237, 'Alex Reviewer', 'alex.reviewer@test.com', '', "
         "'When can I visit the property?', ?)", (TS,))]),
])
def test_stateful_mismatch_fail(tmp_path, task_n, mutations):
    login, steps, answer, _ = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = mutate_db(copy_db(tmp_path / "after.db"), mutations)
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]


@pytest.mark.parametrize("task_n", sorted(STATEFUL))
def test_stateful_collateral_fail(tmp_path, task_n):
    """The required write PLUS an unrelated write -> FAIL."""
    login, steps, answer, mutations = HONEST[task_n]
    run_dir = build_run(tmp_path / "run", f"LandWatch--{task_n}", steps, answer, login=login)
    initial_db = copy_db(tmp_path / "initial.db")
    # inquiries is allowed only on task 11; tamper favorites instead there
    extra_table, extra_sql = "inquiries", ("INSERT INTO inquiries (user_id, pid, name, email, "
                                          "phone, message, created_at) VALUES (NULL, "
                                          "428237808, 'Extra', 'x@example.com', '', "
                                          "'collateral', ?)")
    if task_n == 11:
        extra_table, extra_sql = "favorites", ("INSERT INTO favorites (user_id, pid, "
                                              "created_at) VALUES (1, 428237808, ?)")
    after_db = mutate_db(copy_db(tmp_path / "after.db"),
                         mutations + [(extra_sql, (TS,))])
    verdict = run_verifier(task_n, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)[:2400]
    assert "no_collateral_writes" in json.dumps(verdict), verdict


def test_task_id_mismatch_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    verdict = run_verifier(1, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "trajectory_task_matches"


def test_offsite_url_fails_closed(tmp_path):
    b = RunBuilder(tmp_path / "run", "LandWatch--0")
    b.step("/", "click", {})
    b.step("https://www.landwatch.com/texas-land-for-sale/austin", "goto", {})
    b.done("Austin shows 1 listing, $6,100,000, 111 Acres")
    run_dir = b.write()
    initial_db = copy_db(tmp_path / "initial.db")
    after_db = copy_db(tmp_path / "after.db")
    verdict = run_verifier(0, run_dir, initial_db, after_db)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "all_urls_match_local_origin"


def test_broken_screenshot_fails_closed(tmp_path):
    run_dir, initial_db, after_db = honest_run(tmp_path, 0)
    shot = run_dir / "screenshots" / "step_001.png"
    shot.write_bytes(b"\x89PNG\r\n\n not really a png")
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
