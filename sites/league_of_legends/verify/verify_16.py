#!/usr/bin/env python3
"""Verify League of Legends--16: Esports category card count, first card, external form."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, final_answer, navigated_category, run_verifier)

TASK_ID = "League of Legends--16"
# Frozen ground truth (seed DB, esports category): 52 cards, all of them external link
# cards (external_url set, rendered with target=_blank + the external badge); the first
# card (2026-09-22) is 'WORLDS 2026 VENUE EVENT POLICIES'.
CATEGORY = "esports"
COUNT = 52
FIRST_CARD = "WORLDS 2026 VENUE EVENT POLICIES"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_esports_category", navigated_category(traj, CATEGORY),
                "required: /news/esports/")
    judge.check("answer_count", contains_count(answer, COUNT),
                f"expected {COUNT} cards")
    judge.check("answer_first_card", contains_phrase(answer, FIRST_CARD),
                f"expected the first card {FIRST_CARD!r}")
    judge.check("answer_external_links", contains_phrase(answer, "external"),
                "expected the answer to state the cards open as external links")
    judge.check("answer_not_in_site_articles",
                not contains_phrase(answer, "open as articles on this site"),
                "the cards must not be described as in-site articles")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
