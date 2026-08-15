#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_category, visited_path

SLUG = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"

def checks(t, answer):
    return ([
        ("nav_physics", visited_category(t, "physics"), "visited Physics category"),
        ("nav_target_article", visited_path(t, f"/article/{SLUG}"), "visited target article"),
    ], [("answer_source_journal", contains_all(answer, ["Reviews of Modern Physics"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(0, checks)
