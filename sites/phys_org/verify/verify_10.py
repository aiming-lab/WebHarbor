#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_category, visited_path

SLUG = "how-a-single-star-can-reshape-an-entire-galaxy"
TITLE = "How a single star can reshape an entire galaxy"

def checks(t, answer):
    return ([
        ("nav_astronomy_popular", visited_category(t, "astronomy", "popular"), "opened Popular sort"),
        ("nav_top_article", visited_path(t, f"/article/{SLUG}"), "opened top article"),
    ], [("answer_article_title", contains_all(answer, [TITLE]), repr(answer))])

if __name__ == "__main__":
    run_stateless(10, checks)
