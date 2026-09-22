#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    has_labeled_number,
    run_stateless,
    visited_in_order,
)


def checks(t, answer):
    return ([("ordered_members_to_carol", visited_in_order(t, [
                ("/users", {}), ("/user/carol_d", {})
            ]), "opened Carol's profile from Members"),
             ("clicked_carol_profile", clicked_path_transition(
                 t, "/users", "/user/carol_d"
             ), "clicked Carol's profile from Members")],
            [("answer_comment_count", has_labeled_number(answer, 3, ("comment", "comments")), repr(answer))])

if __name__ == "__main__":
    run_stateless(8, checks)
