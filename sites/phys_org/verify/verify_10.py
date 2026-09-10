#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    has_rank,
    run_stateless,
    visited_in_order,
)

SLUG = "how-a-single-star-can-reshape-an-entire-galaxy"
PROVIDER = "European Southern Observatory"

def checks(t, answer):
    return ([
        ("ordered_popular_to_article", visited_in_order(t, [
            ("/category/astronomy", {"sort": "popular"}),
            (f"/article/{SLUG}", {})
        ]), "opened the named article from Astronomy Popular"),
        ("clicked_named_article", clicked_path_transition(
            t, "/category/astronomy", f"/article/{SLUG}"
        ), "clicked the named article from Popular"),
    ], [
        ("answer_rank", has_rank(answer, 3), repr(answer)),
        ("answer_provider", contains_all(answer, ["Leiden University"]), repr(answer)),
    ])

if __name__ == "__main__":
    run_stateless(10, checks)
