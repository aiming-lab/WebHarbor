#!/usr/bin/env python3
"""Verify LandWatch--11 — bob.c@test.com saves the Hunting Land $250,000 - $499,999 search.

Ground truth (frozen seed): the search page h1 renders the category label
plus 'Land for Sale' ('Hunting Land Land for Sale - 1-7 of 7 Listings' — see
the h1 duplication finding), so Save Search stores that exact name with URL
/hunting-property/price-250000-499999. The post-fix single-'Land' spelling
is accepted too so a de-duplication fix needs no verifier change.
"""

from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        final_answer, phrases_in_order, contains_phrase,
                        run_verifier, table_delta)

TASK_ID = "LandWatch--11"
BOB_EMAIL = "bob.c@test.com"
FILTER_PATH = "/hunting-property/price-250000-499999"
SAVED_NAMES = ("Hunting Land Land for Sale - 1-7 of 7 Listings",
              "Hunting Land for Sale - 1-7 of 7 Listings")
SAVED_URL = "/hunting-property/price-250000-499999"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB_EMAIL)
    check_visited_path(judge, traj, "visited_filtered_search_page", FILTER_PATH)
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "saved_searches"})
    delta = table_delta(initial_db, after_db, "saved_searches")
    judge.check("exactly_one_saved_search_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"saved_searches delta={delta!r}")
    if delta["added"]:
        # row: id, user_id, name, url, alerts, created_at
        row = delta["added"][0]
        judge.check("saved_search_belongs_to_bob", row[1] == 2, f"row={row!r}")
        judge.check("saved_search_name", row[2] in SAVED_NAMES,
                    f"expected one of {SAVED_NAMES!r}, observed {row[2]!r}")
        judge.check("saved_search_url", row[3] == SAVED_URL,
                    f"expected url {SAVED_URL!r}, observed {row[3]!r}")
    judge.check("answer_saved_name", phrases_in_order(answer, ["Hunting Land", "1-7 of 7 Listings"]),
                "expected the stored name (with or without the h1's duplicated 'Land')")
    judge.check("answer_saved_url", contains_phrase(answer, "hunting-property/price-250000-499999"),
                f"expected the saved URL {SAVED_URL!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
