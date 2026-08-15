#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path

SLUG = "operational-test-demonstrates-100-electric-furnace-for-ceramic-frit-me"

def checks(t, answer):
    return ([
        ("nav_trending", visited_path(t, "/trending"), "visited Trending"),
        ("nav_rank_one_article", visited_path(t, f"/article/{SLUG}"), "visited rank-one article"),
    ], [("answer_author", contains_all(answer, ["Elena Yamamoto"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(3, checks)
