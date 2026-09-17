#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    run_stateless,
    visited_in_order,
)

SLUG = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"

def checks(t, answer):
    return ([
        ("ordered_trending_to_rank_three", visited_in_order(t, [
            ("/trending", {}), (f"/article/{SLUG}", {})
        ]), "visited Trending before its third article"),
        ("clicked_third_trending", clicked_path_transition(
            t, "/trending", f"/article/{SLUG}"
        ), "clicked the third Trending result"),
    ], [("answer_provider", contains_all(answer, ["University of Tübingen"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(3, checks)
