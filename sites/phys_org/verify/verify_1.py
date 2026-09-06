#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    run_stateless,
    visited_in_order,
)

SLUG = "quantum-circuit-test-finally-exposes-what-has-been-warping-performance"

def checks(t, answer):
    return ([("ordered_physics_to_article", visited_in_order(t, [
                ("/category/physics", {}), (f"/article/{SLUG}", {})
            ]), "visited Physics Recent before the target article"),
             ("clicked_target_from_physics", clicked_path_transition(
                 t, "/category/physics", f"/article/{SLUG}"
             ), "clicked the target from Physics Recent")],
            [("answer_provider", contains_all(answer, ["Massachusetts Institute of Technology"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(1, checks)
