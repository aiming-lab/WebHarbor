#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    entered_text,
    filled_field,
    run_stateless,
    submitted_from_path,
    visited_in_order,
)

SLUG = "cracking-the-code-of-hypersonic-flight-a-decade-of-experiments-maps-tu"

def checks(t, answer):
    return ([
        ("login_as_bob", filled_field(t, "email", "bob.c@test.com", "/login")
         and entered_text(t, "TestPass123!", "/login")
         and submitted_from_path(t, "/login"), "submitted Bob's credentials"),
        ("ordered_saved_to_article", visited_in_order(t, [
            ("/login", {}), ("/saved", {}), (f"/article/{SLUG}", {})
        ]), "opened the noted article from Saved"),
        ("clicked_noted_article", clicked_path_transition(
            t, "/saved", f"/article/{SLUG}"
        ), "clicked the noted article from Saved"),
    ], [("answer_publication_venue", contains_all(answer, ["AIAA SCITECH 2026 Forum"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(5, checks)
