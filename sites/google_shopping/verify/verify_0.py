#!/usr/bin/env python3
"""Verify the homepage "The iconic trench" section report in Google Shopping--0."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_phrase,
                        contains_price, final_answer, normalized_url_path, run_verifier,
                        site_urls)

TASK_ID = "Google Shopping--0"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the section subtitle and card are rendered on the homepage feed.
    judge.check("visited_homepage_feed",
                any(normalized_url_path(u) == "/" for u in site_urls(traj)),
                "required_path=/ (homepage feed section 'The iconic trench')")
    # Frozen ground truth (seed DB, feed_sections row 'The iconic trench' + product
    # \"Gap Factory Women's Modern Trench Coat\"): subheading 'Popular products', card price $64.99.
    judge.check("answer_section_subtitle", contains_phrase(answer, "Popular products"),
                "expected subtitle 'Popular products'")
    judge.check("answer_gap_factory_price", contains_price(answer, 64.99),
                "expected current price $64.99")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
