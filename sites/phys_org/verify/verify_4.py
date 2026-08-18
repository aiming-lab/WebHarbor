#!/usr/bin/env python3
from verify_lib import filled_field, has_number, run_stateless, visited_path

def checks(t, answer):
    return ([
        ("nav_login", visited_path(t, "/login"), "visited login"),
        ("login_as_alice", filled_field(t, "email", "alice.j@test.com", "/login"),
         "filled Alice's email on login"),
        ("nav_saved", visited_path(t, "/saved"), "visited saved list"),
    ], [("answer_count_four", has_number(answer, 4), repr(answer))])

if __name__ == "__main__":
    run_stateless(4, checks)
