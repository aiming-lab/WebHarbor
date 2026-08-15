#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path, visited_search

SLUG = "method-for-measuring-energy-amounts-less-than-a-trillionth-of-a-billio"

def checks(t, answer):
    return ([
        ("nav_quantum_search", visited_search(t, "quantum"), "searched for quantum"),
        ("nav_target_article", visited_path(t, f"/article/{SLUG}"), "visited target article"),
    ], [("answer_source_journal", contains_all(answer, ["Nature Photonics"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(2, checks)
