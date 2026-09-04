#!/usr/bin/env python3
import re

from verify_lib import (
    answers_earlier_comparison,
    clicked_path_transition,
    norm,
    run_stateless,
    visited_in_order,
)

RECENT = "machine-learning-proves-that-graphene-is-hydrophobic"
EARLIER = "hourglass-nanographenes-unlock-strong-robust-multi-spin-entanglement"
RECENT_TITLE = "Machine learning proves that graphene is hydrophobic"
EARLIER_TITLE = "Hourglass nanographenes unlock strong, robust multi-spin entanglement"

def answer_binds_winner_and_journal(answer):
    normalized = norm(answer)
    expected = re.escape(norm(EARLIER_TITLE))
    journal = re.escape("nature synthesis")
    direct = re.search(rf"{expected}\s*(?:[-—:;,])\s*{journal}\b", normalized)
    related = re.search(
        rf"{expected}.{{0,100}}\b(?:earlier|predates?)\b.{{0,50}}"
        rf"(?:journal\s*(?:is|:)?|[-—:;,])\s*{journal}\b",
        normalized,
    )
    reverse = re.search(
        rf"{journal}.{{0,50}}(?:journal.{{0,20}})?{expected}", normalized
    )
    return answers_earlier_comparison(answer, EARLIER_TITLE, RECENT_TITLE) and bool(
        direct or related or reverse
    )


def checks(t, answer):
    search_to_recent = visited_in_order(t, [
        ("/search", {"q": "graphene spin"}), (f"/article/{RECENT}", {})
    ])
    search_to_earlier = visited_in_order(t, [
        ("/search", {"q": "graphene spin"}), (f"/article/{EARLIER}", {})
    ])
    clicked_both = (
        clicked_path_transition(t, "/search", f"/article/{RECENT}")
        and clicked_path_transition(t, "/search", f"/article/{EARLIER}")
    )
    return ([
        ("search_precedes_both_articles", search_to_recent and search_to_earlier,
         "searched graphene spin before opening both articles"),
        ("clicked_both_results", clicked_both,
         "clicked both named articles from search results"),
    ], [("answer_earlier_article_and_journal",
         answer_binds_winner_and_journal(answer), repr(answer))])

if __name__ == "__main__":
    run_stateless(9, checks)
