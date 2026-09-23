#!/usr/bin/env python3
"""Verify LandWatch--12 — homepage market overview + Hunting Land cross-check.

Ground truth (frozen seed): the featured carousel's first three properties
are 'Potomac Ridge View Estate' ($450,000 / 20.18 Acres / WV), 'Rustic Cabin
on 25 Acres' ($299,000 / 25 Acres / VA), and 'Skyline Creekside Log Cabin'
($799,900 / 5.87 Acres / UT). The first four category tiles read 'Land for
Sale — 436 Land Properties', 'Farms and Ranches — 233 Farms and Ranches
Properties', 'Hunting Land — 176 Hunting Land Properties', and 'Homesites —
53 Homesites Properties'. The Hunting Land category page's results heading
shows 176 listings, matching the tile count.
"""
import re

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_acres, contains_any, contains_count,
                        contains_money, contains_phrase,
                        contains_phrase_without_prefix, final_answer,
                        phrases_in_order, run_verifier)

TASK_ID = "LandWatch--12"


def window_contains(answer, anchor, facts):
    """Every fact pattern appears within 140 chars after the anchor match."""
    match = re.search(anchor, answer, re.I)
    if not match:
        return False
    window = answer[match.start():match.end() + 140]
    return all(re.search(pattern, window, re.I) for pattern in facts)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # beyond-homepage gate: the Hunting Land category page was opened
    check_visited_path(judge, traj, "visited_hunting_category", "/hunting-property")
    # featured carousel: each triple is anchored to its own price
    judge.check("answer_featured_first",
                window_contains(answer, r"\$?450,?000",
                                [r"20[.,]?18", r"\bWV\b|West Virginia"]),
                "expected the first featured property: $450,000 / 20.18 Acres / WV")
    judge.check("answer_featured_second",
                window_contains(answer, r"\$?299,?000",
                                [r"\b25\b", r"\bVA\b|Virginia"]),
                "expected the second featured property: $299,000 / 25 Acres / VA")
    judge.check("answer_featured_third",
                window_contains(answer, r"\$?799,?900",
                                [r"5[.,]?87", r"\bUT\b|Utah"]),
                "expected the third featured property: $799,900 / 5.87 Acres / UT")
    # belt-and-suspenders on the WV/VA pairing (the old carousel trap)
    judge.check("answer_states_in_order",
                phrases_in_order(answer, ["West Virginia", "Utah"])
                or phrases_in_order(answer, ["WV", "UT"]),
                "expected West Virginia (WV) before Utah (UT), carousel order")
    judge.check("answer_second_state_is_plain_virginia",
                contains_phrase_without_prefix(answer, "Virginia", "West ")
                or contains_phrase(answer, "VA"),
                "the second property is in Virginia (VA), not West Virginia")
    # category tiles
    judge.check("answer_tile_land_for_sale", contains_count(answer, 436),
                "expected the Land for Sale tile count 436")
    judge.check("answer_tile_farms", contains_count(answer, 233),
                "expected the Farms and Ranches tile count 233")
    judge.check("answer_tile_hunting", contains_count(answer, 176),
                "expected the Hunting Land tile count 176")
    judge.check("answer_tile_homesites", contains_count(answer, 53),
                "expected the Homesites tile count 53")
    # cross-check: the Hunting Land page heading total matches the tile count
    judge.check("answer_hunting_heading_matches_tile",
                contains_any(answer, ["match", "matches", "matching", "consistent",
                                     "consistently", "same", "agree", "agrees"]),
                "expected the heading total to be stated as matching the tile count")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
