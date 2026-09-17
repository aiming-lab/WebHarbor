#!/usr/bin/env python3
from verify_lib import (
    clicked_path_transition,
    contains_all,
    has_rank,
    run_stateless,
    visited_category,
    visited_in_order,
    visited_path,
)

SLUG = "good-vibrations-for-quantum-communications-engineers-couple-single-pho"
TITLE = "Good vibrations for quantum communications: Engineers couple single phonon to single atomic spin"

def checks(t, answer):
    return ([
        ("nav_home", visited_path(t, "/"), "visited homepage sidebar"),
        ("nav_sixth_trending_article", visited_path(t, f"/article/{SLUG}"), "opened sixth sidebar entry"),
        ("nav_physics_popular", visited_category(t, "physics", "popular"), "opened category Popular view"),
        ("ordered_full_flow", visited_in_order(t, [
            ("/", {}), (f"/article/{SLUG}", {}),
            ("/category/physics", {}), ("/category/physics", {"sort": "popular"})
        ]), "completed the click chain in order"),
        ("click_sixth_trending",
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
         contains_all(answer, [TITLE, "Physics"]) and has_rank(answer, 2), repr(answer)),
    ])

if __name__ == "__main__":
    run_stateless(15, checks)
