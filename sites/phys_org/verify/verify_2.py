#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    run_stateless,
    visited_in_order,
)

SLUG = "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio"

def checks(t, answer):
    return ([
        ("ordered_search_to_article", visited_in_order(t, [
            ("/search", {"q": "quantum"}), (f"/article/{SLUG}", {})
        ]), "searched for quantum before opening the target"),
        ("clicked_target_from_search", clicked_path_transition(
            t, "/search", f"/article/{SLUG}"
        ), "clicked the target from search results"),
    ], [("answer_source_journal", contains_all(answer, ["Nature Electronics"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(2, checks)
