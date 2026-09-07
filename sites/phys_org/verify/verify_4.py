#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    entered_text,
    filled_field,
    has_labeled_number,
    run_stateless,
    submitted_from_path,
    visited_in_order,
)


def checks(t, answer):
    return ([
        ("login_as_alice", filled_field(t, "email", "alice.j@test.com", "/login")
         and entered_text(t, "TestPass123!", "/login")
         and submitted_from_path(t, "/login"), "submitted Alice's credentials"),
        ("ordered_login_to_saved", visited_in_order(t, [
            ("/login", {}), ("/saved", {})
        ]), "visited Saved after login"),
        ("clicked_saved", clicked_path_transition(t, "/", "/saved"),
         "clicked Saved after login"),
    ], [("answer_astronomy_count", has_labeled_number(
        answer, 4, ("astronomy", "astronomy & space")
    ), repr(answer))])

if __name__ == "__main__":
    run_stateless(4, checks)
