#!/usr/bin/env python3
"""Verify Michaels--5.

Help Carol plan a Sunday trip for her scout troop's fundraiser: they need balloon inflation and custom framing for a poster near Cary, NC. Compare the Crossroads Plaza and New Hope Commons stores, including their Sunday hours and whether each offers both services; include the Cary store's phone number. Identify the other North Carolina locations with balloon inflation as backup options.
"""
import re

from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_all,
                        contains_any, contains_count, contains_phrase, final_answer,
                        navigated_store_locator_query, navigated_to_path, norm, phrases_in_order,
                        run_verifier)

TASK_ID = "Michaels--5"


def _mentions(text, phrase, times):
    """`phrase` occurs at least `times` times (normalized, whole-token)."""
    return norm(text).count(norm(phrase)) >= times


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Any locator search is valid; inspect both store-detail surfaces.
    judge.check("cary_detail", navigated_to_path(traj, "/store-locator/2122"), "Cary store details")
    judge.check("durham_detail", navigated_to_path(traj, "/store-locator/9502"), "New Hope Commons store details")
    # answer: Cary store facts (its hours must be attributed — the task asks for
    # BOTH stores' Sunday hours, so the range must appear for each of them)
    judge.check("answer_cary_name", contains_phrase(answer, "Crossroads Plaza"),
                "expected the Cary store name Crossroads Plaza")
    judge.check("answer_cary_phone", contains_phrase(answer, "(919) 851-6001") or
                contains_all(answer, ["919", "851", "6001"]),
                "expected phone (919) 851-6001")
    hours = re.findall(r"10(?::00)?\s*a\.?m\.?.{0,60}?0?7(?::00)?\s*p\.?m", answer, re.I)
    judge.check("answer_sunday_hours", bool(hours), "Sunday 10am–7pm, accepting equivalent formatting")
    judge.check("answer_balloon_inflation", contains_phrase(answer, "balloon inflation"),
                "expected: balloon inflation offered")
    judge.check("answer_custom_framing", contains_phrase(answer, "custom framing"),
                "expected: custom framing offered")
    # answer: Durham New Hope Commons cross-check (same balloon service + its own
    # Sunday hours — the range must be reported for this store too, not only Cary's)
    judge.check("answer_nhc_named", contains_phrase(answer, "New Hope Commons"),
                "expected the New Hope Commons store in Durham named")
    judge.check("answer_nhc_balloon", contains_phrase(answer, "balloon inflation"),
                "expected: New Hope Commons also offers balloon inflation")
    judge.check("answer_nhc_sunday", len(hours) >= 2 or (bool(hours) and "both" in answer.lower()),
                "Report Sunday hours for both locations, individually or together")
    # answer: the other NC balloon-inflation stores (all three others)
    for name in ("Park Road Shopping Center", "RAL-DURHAM~NORTH, NC", "Park West Village"):
        judge.check(f"answer_other_{name[:12].replace(' ', '_').replace(',', '')}",
                    contains_phrase(answer, name), f"expected other NC store {name!r}")
    judge.check("answer_count", contains_count(answer, 4) or contains_count(answer, 3),
                "expected 4 other NC balloon-inflation locations (3 if New Hope Commons "
                "is counted separately from the cross-check)")
    # read-only task: DB must be untouched
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
