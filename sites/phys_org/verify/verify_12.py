#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    equivalent_phrase,
    run_stateless,
    visited_in_order,
)

SLUG = "jwst-spots-two-early-black-holes-growing-far-faster-than-their-galaxie"
REPLY = "Totally agree on the priors point — the new constraint is much tighter though."

def checks(t, answer):
    return ([("ordered_popular_to_comment_thread", visited_in_order(t, [
                ("/category/astronomy", {"sort": "popular"}),
                (f"/article/{SLUG}", {})
            ]), "opened the second Popular article before its comments"),
             ("clicked_second_popular", clicked_path_transition(
                 t, "/category/astronomy", f"/article/{SLUG}"
             ), "clicked the second Popular article")],
            [("answer_full_reply", equivalent_phrase(answer, REPLY), repr(answer))])

if __name__ == "__main__":
    run_stateless(12, checks)
