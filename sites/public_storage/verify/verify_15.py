#!/usr/bin/env python3
"""Verify Public Storage--15 (read-only) — r2 REWRITTEN task text.

Search for storage near ZIP 98101 and compare the Recommended and Lowest
Price sort orders. Which facility's street address is listed first under
each sort, and what displayed distance goes with each? Then list the top
three facility street addresses under Lowest Price in order, open the first
one, and report its cheapest listed unit size and that unit's online rate.

Frozen ground truth (seed DB): under Recommended, 1334 Alaskan Way is first
at 0.2 miles; under Lowest Price, 1200 S Dearborn St (facility 2610) is
first at 1.3 miles. The Lowest Price top three in order are 1200 S Dearborn
St, 700 Fairview Ave N, 1515 13th Ave. Facility 2610's cheapest listed unit
is a 5'x4' at $39/mo online. Unlike the pre-fix task, the two sorts lead
with different facilities at different distances, so the comparison is no
longer degenerate.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_amount, contains_phrase, final_answer,
                        navigated_facility, navigated_zip_search, run_verifier)

TASK_ID = "Public Storage--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_zip_search_98101", navigated_zip_search(traj, "98101"),
                "required: ZIP 98101 search results (Recommended)")
    judge.check("visited_price_sort",
                navigated_zip_search(traj, "98101", sort="price"),
                "required: the Lowest Price sort order")
    judge.check("visited_facility_2610", navigated_facility(traj, 2610),
                "required: open the first facility under Lowest Price (1200 S Dearborn St)")
    # Recommended first
    judge.check("answer_recommended_first", contains_phrase(answer, "1334 Alaskan Way"),
                "Recommended first: 1334 Alaskan Way")
    judge.check("answer_recommended_distance", contains_phrase(answer, "0.2"),
                "Recommended first at 0.2 miles")
    # Lowest Price first
    judge.check("answer_price_first", contains_phrase(answer, "1200 S Dearborn St"),
                "Lowest Price first: 1200 S Dearborn St")
    judge.check("answer_price_distance", contains_phrase(answer, "1.3"),
                "Lowest Price first at 1.3 miles")
    # Lowest Price top three, in the reported order
    flat = answer.replace(",", " ").replace("\n", " ").lower()
    import re as _re
    flat = _re.sub(r"\s+", " ", flat)
    p1 = flat.find("1200 s dearborn st")
    p2 = flat.find("700 fairview ave n")
    p3 = flat.find("1515 13th ave")
    judge.check("answer_price_top3_order",
                p1 >= 0 and p2 >= 0 and p3 >= 0 and p1 < p2 < p3,
                "top three under Lowest Price in order: 1200 S Dearborn St, "
                "700 Fairview Ave N, 1515 13th Ave")
    # cheapest listed unit at the first facility
    judge.check("answer_cheapest_size",
                contains_phrase(answer, "5'x4'") or contains_phrase(answer, "5x4")
                or contains_phrase(answer, "5 x 4"),
                "cheapest listed unit size 5'x4'")
    judge.check("answer_cheapest_rate", contains_amount(answer, 39),
                "cheapest listed unit online rate $39")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
