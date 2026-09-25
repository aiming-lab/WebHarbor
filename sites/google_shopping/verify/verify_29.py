#!/usr/bin/env python3
"""Verify david saving the two cheapest edikted glasses in Google Shopping--29."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_phrase,
                        contains_price, final_answer, navigated_search_with, run_verifier,
                        saved_pairs, table_delta)

TASK_ID = "Google Shopping--29"
RECTANGLE_PATH = "/product/gsdbc82b9ec167c52c"   # Blue Light Rectangle Glasses ($4.40)
RAQUELLA_PATH = "/product/gs8613f95434064d79"    # Raquella Rectangle Blue Light Glasses ($4.40)


def product_price_clause(answer, product):
    """Separate sibling products even when both appear in one sentence."""
    import re
    matches = list(re.finditer(r'Blue Light Rectangle|Raquella', answer, re.I))
    parts = []
    for i, match in enumerate(matches):
        if match.group().casefold() == product.casefold():
            end = matches[i+1].start() if i+1 < len(matches) else len(answer)
            parts.append(answer[match.start():end])
    return ' '.join(parts)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    from reviewed import fact_scope
    from verify_lib import contains_price
    judge.check("bound_price_blue", contains_price(product_price_clause(answer, 'Blue Light Rectangle'), 4.4), "price belongs to Blue Light Rectangle")
    judge.check("bound_price_raquella", contains_price(product_price_clause(answer, 'Raquella'), 4.4), "price belongs to Raquella")
    import re
    judge.check("no_denied_price", not re.search(r"(?:not|instead of|rather than)\s*\$(?:4\.40?|45(?:\.00)?|48\.50?)(?![\d.])", answer, re.I), "requested prices must be asserted")
    # Auth + navigation gates: sign in as david, search the edikted glasses, save both from
    # their product pages.
    check_signed_in_as(judge, traj, "david.k@test.com", "David Kim")
    judge.check("visited_edikted_search", navigated_search_with(traj, ["edikted"]),
                "required=/search?q=<edikted glasses>")
    check_visited_path(judge, traj, "visited_rectangle_product_page", RECTANGLE_PATH)
    check_visited_path(judge, traj, "visited_raquella_product_page", RAQUELLA_PATH)
    # Frozen ground truth: edikted glasses rows are $4.40 (x2), $11.00 (x2); the two
    # cheapest are 'Blue Light Rectangle Glasses' and 'Raquella Rectangle Blue Light
    # Glasses', $4.40 each, $8.80 combined.
    judge.check("answer_first_title", contains_phrase(answer, "Blue Light Rectangle Glasses"),
                "expected 'Blue Light Rectangle Glasses'")
    judge.check("answer_second_title", contains_phrase(answer, "Raquella Rectangle Blue Light Glasses"),
                "expected 'Raquella Rectangle Blue Light Glasses'")
    judge.check("answer_combined_price", contains_price(answer, 8.80), "expected $8.80 combined")
    # DB after-state: exactly two saved rows added for (david, {12, 39}).
    judge.check("david_saved_set_exact",
                saved_pairs(after_db, 4) == [(4, 12), (4, 39)],
                f"david saved_pairs={saved_pairs(after_db, 4)} expected=[(4, 12), (4, 39)]")
    delta = table_delta(initial_db, after_db, "saved_items")
    judge.check("saved_delta_exactly_two",
                len(delta["added"]) == 2 and {r[2] for r in delta["added"]} == {12, 39}
                and all(r[1] == 4 for r in delta["added"])
                and not delta["removed"] and not delta["changed"],
                f"saved_items delta={delta}")
    check_only_tables_changed(judge, initial_db, after_db, ("saved_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
