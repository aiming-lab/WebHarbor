#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    run_stateless,
    visited_in_order,
)

SLUG = "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids"

def checks(t, answer):
    return ([
        ("ordered_filtered_search_to_article", visited_in_order(t, [
            ("/search", {"q": "capture materials", "category": "chemistry"}),
            (f"/article/{SLUG}", {})
        ]), "opened the target from filtered results"),
        ("clicked_target_from_results", clicked_path_transition(
            t, "/search", f"/article/{SLUG}"
        ), "clicked the target from filtered results"),
    ], [("answer_source_journal",
         contains_all(answer, ["Reaction Chemistry & Engineering"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(16, checks)
