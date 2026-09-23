#!/usr/bin/env python3
"""Verify LandWatch--9 — bob.c@test.com buyer session: favorites + saved search + removal.

Ground truth (frozen seed): bob.c@test.com starts with 4 saved properties.
Favoriting 'Sisterdale Farms' (pid 425766087) and 'Tucked into the Hill
Country' (pid 428212638) brings the account to 6 saved properties; saving
the Hunting Land $250,000 - $499,999 search stores the h1-derived name
'Hunting Land for Sale - 1-7 of 7 Listings' with URL
/hunting-property/price-250000-499999 (the pre-dedup double-'Land' spelling
is accepted too). Removing the smaller candidate (Sisterdale Farms) leaves 5
saved properties with 'Tucked into the Hill Country' still among them; the
favorites delta is then exactly one added row for pid 428212638.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, expected_session_token,
                        final_answer, navigated_to, phrases_in_order, run_verifier,
                        table_delta)

TASK_ID = "LandWatch--9"
BOB_EMAIL = "bob.c@test.com"
SISTERDALE_DETAIL = "/kendall-county-texas-farms-and-ranches-for-sale/pid/425766087"
TUCKED_DETAIL = "/burnet-county-texas-farms-and-ranches-for-sale/pid/428212638"
HUNTING_FILTER = "/hunting-property/price-250000-499999"
SAVED_NAMES = ("Hunting Land for Sale - 1-7 of 7 Listings",
               "Hunting Land Land for Sale - 1-7 of 7 Listings")
KEPT_PID = 428212638  # Tucked into the Hill Country (the larger candidate, kept)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL)
    # navigation gates: both candidate surfaces (results card or detail page),
    # the filtered hunting page, and the account page
    judge.check("located_sisterdale_candidate",
                navigated_to(traj, "q=boerne") or navigated_to(traj, "q=kendall")
                or navigated_to(traj, "/texas-land-for-sale/boerne")
                or navigated_to(traj, SISTERDALE_DETAIL),
                "expected the Boerne/Kendall results or the Sisterdale detail page")
    judge.check("located_tucked_candidate",
                navigated_to(traj, "q=burnet") or navigated_to(traj, "/texas-land-for-sale/burnet-county")
                or navigated_to(traj, TUCKED_DETAIL),
                "expected the Burnet County results or the Tucked detail page")
    check_visited_path(judge, traj, "visited_hunting_filter_page", HUNTING_FILTER)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    # exactly the allowed tables changed
    check_only_tables_changed(judge, initial_db, after_db,
                              {"sessions", "favorites", "saved_searches"})
    # session delta: exactly bob's deterministic session token
    sessions = table_delta(initial_db, after_db, "sessions")
    judge.check("exactly_one_session_added",
                sessions["removed"] == [] and len(sessions["added"]) == 1
                and sessions["changed"] == [],
                f"sessions delta={sessions!r}")
    if sessions["added"]:
        judge.check("session_is_bobs",
                    sessions["added"][0][0] == expected_session_token(2, BOB_EMAIL)
                    and sessions["added"][0][1] == 2,
                    f"expected bob's session token, observed {sessions['added'][0]!r}")
    # favorites delta: both candidates favorited, then the smaller one removed,
    # leaving exactly one added row for the kept listing
    favorites = table_delta(initial_db, after_db, "favorites")
    judge.check("favorites_net_delta_is_kept_listing",
                favorites["removed"] == [] and favorites["changed"] == []
                and len(favorites["added"]) == 1
                and favorites["added"][0][1] == 2 and favorites["added"][0][2] == KEPT_PID,
                f"expected exactly bob's kept favorite pid {KEPT_PID}, delta={favorites!r}")
    # saved-search delta: exactly one row, h1-derived name, filtered URL
    searches = table_delta(initial_db, after_db, "saved_searches")
    judge.check("exactly_one_saved_search_added",
                searches["removed"] == [] and len(searches["added"]) == 1
                and searches["changed"] == [],
                f"saved_searches delta={searches!r}")
    if searches["added"]:
        row = searches["added"][0]
        judge.check("saved_search_belongs_to_bob", row[1] == 2, f"row={row!r}")
        judge.check("saved_search_name", row[2] in SAVED_NAMES,
                    f"expected one of {SAVED_NAMES!r}, observed {row[2]!r}")
        judge.check("saved_search_url", row[3] == HUNTING_FILTER,
                    f"expected url {HUNTING_FILTER!r}, observed {row[3]!r}")
    # answer gates
    judge.check("answer_six_saved_properties", contains_count(answer, 6),
                "expected 6 saved properties after favoriting both candidates")
    judge.check("answer_saved_name",
                phrases_in_order(answer, ["Hunting Land", "1-7 of 7 Listings"]),
                "expected the stored name 'Hunting Land for Sale - 1-7 of 7 Listings'")
    judge.check("answer_saved_url",
                contains_phrase(answer, "hunting-property/price-250000-499999"),
                "expected the stored URL /hunting-property/price-250000-499999")
    judge.check("answer_five_saved_after_removal", contains_count(answer, 5),
                "expected 5 saved properties after removing the smaller candidate")
    judge.check("answer_names_kept_candidate",
                contains_phrase(answer, "Tucked into the Hill Country"),
                "expected 'Tucked into the Hill Country' named as still saved")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
