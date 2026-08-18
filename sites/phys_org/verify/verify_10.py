#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_category, visited_path

SLUG = "how-a-single-star-can-reshape-an-entire-galaxy"
PROVIDER = "European Southern Observatory"

def checks(t, answer):
    return ([
        ("nav_astronomy_popular", visited_category(t, "astronomy", "popular"), "opened Popular sort"),
        ("nav_top_article", visited_path(t, f"/article/{SLUG}"), "opened top article"),
    ], [("answer_provider", contains_all(answer, [PROVIDER]), repr(answer))])

if __name__ == "__main__":
    run_stateless(10, checks)
