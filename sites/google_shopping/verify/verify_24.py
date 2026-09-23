#!/usr/bin/env python3
"""Verify carol tracking all three Syght Glass products in Google Shopping--24."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, run_verifier, table_delta, tracked_pairs)

TASK_ID = "Google Shopping--24"
CRUISE_PATH = "/product/gs6d8bbb715e54c510"    # Buy Cruise ... Peach  ($48.50)
EMBER_PATH = "/product/gs365bc2213e4c5230"    # Buy Ember ... Blue     ($45.00)
STRIKE_PATH = "/product/gs6ab428ebf7cb3419"   # Buy Strike ... Tortoise ($45.00)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Auth + navigation gates: sign in as carol, open every Syght Glass product page (the
    # Track price button lives there), then open the tracking page.
    check_signed_in_as(judge, traj, "carol.d@test.com", "Carol Davis")
    for name, path in (("cruise", CRUISE_PATH), ("ember", EMBER_PATH), ("strike", STRIKE_PATH)):
        check_visited_path(judge, traj, f"visited_syght_{name}_product_page", path)
    check_visited_path(judge, traj, "visited_price_tracking_page", "/tracked")
    # Frozen ground truth: the most expensive tracked Syght product is
    # 'Buy Cruise - Blue Light Blocking Prescription & Non-Prescription Glasses, Peach'
    # at $48.50 (the Ember and Strike rows both cost $45.00).
    judge.check("answer_most_expensive_tracked",
                contains_phrase(answer, "Buy Cruise"), "expected 'Buy Cruise ...' as most expensive")
    judge.check("answer_most_expensive_price", contains_price(answer, 48.50), "expected $48.50")
    # DB after-state: exactly three tracked rows added for (carol, {13, 14, 15}).
    judge.check("carol_tracked_set_exact",
                tracked_pairs(after_db, 3) == [(3, 13), (3, 14), (3, 15)],
                f"carol tracked_pairs={tracked_pairs(after_db, 3)} expected=[(3, 13), (3, 14), (3, 15)]")
    delta = table_delta(initial_db, after_db, "tracked_products")
    judge.check("tracked_delta_exactly_three",
                len(delta["added"]) == 3 and {r[2] for r in delta["added"]} == {13, 14, 15}
                and all(r[1] == 3 for r in delta["added"])
                and not delta["removed"] and not delta["changed"],
                f"tracked_products delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("tracked_products",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
