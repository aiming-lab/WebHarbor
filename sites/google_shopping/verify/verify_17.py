#!/usr/bin/env python3
"""Verify the biggest-discount report on the Deals page in Google Shopping--17."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_percent, contains_phrase, final_answer, normalize_text, run_verifier)
import re

TASK_ID = "Google Shopping--17"


def _names_exact_product(answer):
    """The biggest-discount row is titled exactly 'Trench coat' — NOT 'COTTON TRENCH COAT'
    (a different row). Accept the standalone title, not a longer title embedding it."""
    normalized = normalize_text(answer)
    return bool(re.search(r"(?<!cotton[\s_-])\btrench[\s_-]*coat\b(?!s)", normalized))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Deals page (the discount-sorted grid).
    check_visited_path(judge, traj, "visited_deals_page", "/deals")
    # Frozen ground truth (seed DB): biggest discount is 82% OFF on 'Trench coat'.
    judge.check("answer_product_title", _names_exact_product(answer),
                "expected the exact title 'Trench coat' (not 'COTTON TRENCH COAT')")
    judge.check("answer_discount_pct", contains_percent(answer, 82), "expected 82% OFF")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
