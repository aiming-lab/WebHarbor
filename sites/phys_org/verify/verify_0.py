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
        ("ordered_physics_to_article", visited_in_order(t, [
            ("/category/physics", {}), (f"/article/{SLUG}", {})
        ]), "visited Physics before the target article"),
        ("clicked_target_from_physics", clicked_path_transition(
            t, "/category/physics", f"/article/{SLUG}"
        ), "clicked the target from the category list"),
    ], [("answer_source_journal", contains_all(answer, ["Physical Review Letters"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(0, checks)
