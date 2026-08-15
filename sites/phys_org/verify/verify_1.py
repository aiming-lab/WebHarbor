#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path

SLUG = "quantum-circuit-test-finally-exposes-what-has-been-warping-performance"

def checks(t, answer):
    return ([("nav_target_article", visited_path(t, f"/article/{SLUG}"), "visited target article")],
            [("answer_provider", contains_all(answer, ["Technion"]), repr(answer))])

if __name__ == "__main__":
    run_stateless(1, checks)
