#!/usr/bin/env python3
"""Verify the 2026 Sinquefield/Cairns Cup winners article report in Chess.com--9.

Re-anchored (review R1): the card/search metadata (headline winners, author,
date) leaked the original answers at the listing layer, so the question now
asks for article-body-unique facts — the Cairns Cup winner's prize money and
her winning score. The navigation gate still requires opening the article.
"""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--9"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the article page (listing/search cards carry metadata; the rubric
    # requires opening the article itself for the body facts).
    check_visited_path(judge, traj, "visited_winners_article",
                       "/news/view/wesley-so-tan-win-2026-sinquefield-cairns-cup")
    # Frozen ground truth (article body, paragraphs beyond the excerpt):
    # the Cairns Cup winner (Tan Zhongyi) took home $65,000 and won the
    # tournament with 6.5 points (after nine rounds).
    judge.check("answer_cairns_prize", contains_amount(answer, 65000), "expected $65,000")
    judge.check("answer_cairns_score",
                contains_phrase(answer, "6.5") or contains_phrase(answer, "6½")
                or contains_phrase(answer, "six and a half"),
                "expected a winning score of 6.5")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
