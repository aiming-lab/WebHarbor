#!/usr/bin/env python3
"""Verify Michaels--10.

Carol (carol.d@test.com / TestPass123!) is switching from canvas painting to ribbon crafts. Remove every canvas item from her wishlist, then save the 6" Glitter Tulle and the 1/4" x 10yd. Grosgrain Ribbon by Celebrate It® Classic in any color to it. Report how many items her wishlist holds now.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        final_answer, navigated_product, navigated_search, run_verifier,
                        wrong_count_claim_absent, wishlist_of)

TASK_ID = "Michaels--10"
TULLE_SLUG = "6-glitter-tulle-by-celebrate-it-occasions-10217915"
RIBBON_SLUG = "1-4-x-10yd-grosgrain-ribbon-by-celebrate-it-classic-10264009"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, wishlist, both product pages
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_wishlist", "/wishlist")
    judge.check("searched_tulle", navigated_search(traj, "Glitter Tulle"),
                "required: a glitter tulle search")
    judge.check("searched_ribbon", navigated_search(traj, "Grosgrain Ribbon"),
                "required: a grosgrain ribbon search")
    judge.check("visited_tulle_pdp", navigated_product(traj, TULLE_SLUG),
                f"required: /product/{TULLE_SLUG}")
    judge.check("visited_ribbon_pdp", navigated_product(traj, RIBBON_SLUG),
                f"required: /product/{RIBBON_SLUG}")
    # answer: the new wishlist count
    judge.check("answer_wishlist_count", contains_count(answer, 3),
                "expected: wishlist now shows 3 items")
    judge.check("answer_wishlist_count_claim", wrong_count_claim_absent(answer, 3),
                "the wishlist count claim must not contradict the expected 3 items")
    # DB after-state: 3 canvas rows removed, 2 rows added, nothing else
    before = wishlist_of(initial_db, "carol.d@test.com")
    after = wishlist_of(after_db, "carol.d@test.com")
    b_ids = {w["id"] for w in before}
    removed = [w for w in before if w["id"] not in {x["id"] for x in after}]
    added = [w for w in after if w["id"] not in b_ids]
    judge.check("canvas_items_removed",
                len(removed) == 3 and all(w["product_id"] in (115, 116, 118) for w in removed),
                f"expected 3 canvas wishlist rows removed; removed={removed!r}")
    judge.check("ribbon_items_added",
                len(added) == 2 and {w["product_id"] for w in added} == {114, 42},
                f"expected tulle (114) + grosgrain (42) added; added={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("wishlist_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
