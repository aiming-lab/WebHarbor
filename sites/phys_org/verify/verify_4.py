#!/usr/bin/env python3
from verify_lib import has_number, run_stateless, visited_path

def checks(t, answer):
    return ([
        ("nav_login", visited_path(t, "/login"), "visited login"),
        ("nav_saved", visited_path(t, "/saved"), "visited saved list"),
    ], [("answer_count_four", has_number(answer, 4), repr(answer))])

if __name__ == "__main__":
    run_stateless(4, checks)
