#!/usr/bin/env python3
from verify_lib import has_number, run_stateless, visited_path

def checks(t, answer):
    return ([("nav_carol_profile", visited_path(t, "/user/carol_d"), "visited public profile")],
            [("answer_comment_count", has_number(answer, 3), repr(answer))])

if __name__ == "__main__":
    run_stateless(8, checks)
