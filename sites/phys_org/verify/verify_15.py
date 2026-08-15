#!/usr/bin/env python3
from verify_lib import contains_all, has_number, run_stateless, visited_category, visited_path

SLUG = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"
TITLE = "Magnetic checkerboard separates microparticles by size and sends them along different paths"

def checks(t, answer):
    return ([
        ("nav_home", visited_path(t, "/"), "visited homepage sidebar"),
        ("nav_third_trending_article", visited_path(t, f"/article/{SLUG}"), "opened third sidebar entry"),
        ("nav_physics_popular", visited_category(t, "physics", "popular"), "opened category Popular view"),
    ], [
        ("answer_title_category_rank",
         contains_all(answer, [TITLE, "Physics"]) and has_number(answer, 1), repr(answer)),
    ])

if __name__ == "__main__":
    run_stateless(15, checks)
