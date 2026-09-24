#!/usr/bin/env python3
"""Verify Michaels--4.

Carol's art co-op wants reliability data: compare the rating breakdowns of the
Artist's Loft Level 3 Gallery Wrapped Heavy Duty Canvas and the Level 1 Back
Stapled Canvas on their reviews pages (5-star count, 1-star count, average).

Frozen ground truth (seed DB, upstream Bazaarvoice aggregates):
Level 3 (10472532): 5-star 14,630 / 1-star 244 / average 4.8 (16,705 reviews).
Level 1 (10672808): 5-star 7,028 / 1-star 142 / average 4.7 (8,708 reviews).
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_all,
                        contains_count, contains_phrase, final_answer, navigated_product,
                        navigated_product_reviews, navigated_search, run_verifier)

TASK_ID = "Michaels--4"
L3_SLUG = "level-3-gallery-wrapped-heavy-duty-canvas-by-artist-s-loft-10472532"
L1_SLUG = "level-1-back-stapled-canvas-by-artist-s-loft-10672808"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: BOTH products' reviews pages
    judge.check("searched_canvas", navigated_search(traj, "canvas"),
                "required: a canvas search")
    judge.check("visited_l3_reviews", navigated_product_reviews(traj, L3_SLUG),
                f"required: /product/{L3_SLUG}/reviews")
    judge.check("visited_l1_reviews", navigated_product_reviews(traj, L1_SLUG),
                f"required: /product/{L1_SLUG}/reviews")
    judge.check("visited_l3_pdp", navigated_product(traj, L3_SLUG),
                f"required: /product/{L3_SLUG}")
    judge.check("visited_l1_pdp", navigated_product(traj, L1_SLUG),
                f"required: /product/{L1_SLUG}")
    # answer: both breakdowns
    judge.check("answer_l3_5star", contains_count(answer, 14630),
                "expected Level 3 5-star count 14,630")
    judge.check("answer_l3_1star", contains_count(answer, 244),
                "expected Level 3 1-star count 244")
    judge.check("answer_l3_avg", contains_phrase(answer, "4.8"),
                "expected Level 3 average 4.8")
    judge.check("answer_l1_5star", contains_count(answer, 7028),
                "expected Level 1 5-star count 7,028")
    judge.check("answer_l1_1star", contains_count(answer, 142),
                "expected Level 1 1-star count 142")
    judge.check("answer_l1_avg", contains_phrase(answer, "4.7"),
                "expected Level 1 average 4.7")
    judge.check("answer_review_counts", contains_count(answer, 16705) and
                contains_count(answer, 8708),
                "expected both total review counts (16,705 / 8,708)")
    judge.check("answer_names_both", contains_all(answer, ["Level 3", "Level 1"]),
                "expected both products named")
    # read-only task: DB must be untouched
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
