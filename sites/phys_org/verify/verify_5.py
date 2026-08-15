#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path

SLUG = "cracking-the-code-of-hypersonic-flight-a-decade-of-experiments-maps-tu"

def checks(t, answer):
    return ([
        ("nav_login", visited_path(t, "/login"), "visited login"),
        ("nav_saved", visited_path(t, "/saved"), "visited saved list"),
        ("nav_noted_article", visited_path(t, f"/article/{SLUG}"), "opened noted article"),
    ], [("answer_source_journal", contains_all(answer, ["Advanced Engineering Materials"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(5, checks)
