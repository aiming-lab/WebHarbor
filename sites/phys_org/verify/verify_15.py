#!/usr/bin/env python3
from verify_lib import (clicked_path_transition, contains_all, has_number,
                        run_stateless, visited_category, visited_path)

SLUG = "magnetic-checkerboard-separates-microparticles-by-size-and-sends-them-"
TITLE = "Magnetic checkerboard separates microparticles by size and sends them along different paths"

def checks(t, answer):
    return ([
        ("nav_home", visited_path(t, "/"), "visited homepage sidebar"),
        ("nav_third_trending_article", visited_path(t, f"/article/{SLUG}"), "opened third sidebar entry"),
        ("nav_physics_popular", visited_category(t, "physics", "popular"), "opened category Popular view"),
        ("click_third_trending",
         clicked_path_transition(t, "/", f"/article/{SLUG}"),
         "clicked from home into the third Trending article"),
        ("click_article_category",
         clicked_path_transition(t, f"/article/{SLUG}", "/category/physics"),
         "followed the Physics category link from the article"),
        ("click_category_popular",
         clicked_path_transition(t, "/category/physics", "/category/physics",
                                 {"sort": "popular"}),
         "switched the category view to Popular by click"),
    ], [
        ("answer_title_category_rank",
         contains_all(answer, [TITLE, "Physics"]) and has_number(answer, 1), repr(answer)),
    ])

if __name__ == "__main__":
    run_stateless(15, checks)
