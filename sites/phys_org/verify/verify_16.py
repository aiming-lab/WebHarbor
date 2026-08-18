#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path, visited_search

SLUG = "anion-swap-unlocks-sevenfold-co-capture-in-polyionic-liquids"

def checks(t, answer):
    return ([
        ("nav_filtered_co2_systems_search", visited_search(t, "CO2 systems", "chemistry"),
         "searched CO2 systems with Chemistry filter"),
        ("nav_target_article", visited_path(t, f"/article/{SLUG}"), "opened target article"),
    ], [("answer_source_journal",
         contains_all(answer, ["Journal of the American Chemical Society"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(16, checks)
