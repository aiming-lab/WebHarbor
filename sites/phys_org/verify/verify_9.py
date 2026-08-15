#!/usr/bin/env python3
from verify_lib import claims_earlier, contains_all, run_stateless, visited_path, visited_search

RECENT = "machine-learning-proves-that-graphene-is-hydrophobic"
EARLIER = "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement"

def checks(t, answer):
    return ([
        ("nav_graphene_search", visited_search(t, "graphene"), "searched for graphene"),
        ("nav_recent_nanotech_result", visited_path(t, f"/article/{RECENT}"), "opened first comparison article"),
        ("nav_earlier_nanotech_result", visited_path(t, f"/article/{EARLIER}"), "opened second comparison article"),
    ], [
        ("answer_earlier_article_and_journal",
         claims_earlier(answer, "Hourglass nanographenes unlock strong, robust multi-spin entanglement")
         and contains_all(answer, ["Nano Letters"]),
         repr(answer)),
    ])

if __name__ == "__main__":
    run_stateless(9, checks)
