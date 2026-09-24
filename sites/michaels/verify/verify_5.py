#!/usr/bin/env python3
"""Verify Michaels--5 (round-2 redesign).

Carol's scout troop near Cary, NC: check the Michaels store in Cary — report
its Sunday hours, its phone number, whether it offers balloon inflation and
custom framing — cross-check the New Hope Commons store in Durham (same
balloon service? its Sunday hours?) — then list every other North Carolina
Michaels location that also offers balloon inflation.

Frozen ground truth (seed DB, upstream store-locator facts): Cary store #2122
"Crossroads Plaza", 340 Crossroads Blvd, Cary, NC 27518-6895, phone
(919) 851-6001, Sunday 10:00 AM - 07:00 PM, services include balloon inflation
and custom framing. Durham New Hope Commons store #9502 also offers balloon
inflation, Sunday 10:00 AM - 07:00 PM. Other NC balloon-inflation stores:
Park Road Shopping Center (Charlotte), RAL-DURHAM~NORTH, NC (Durham),
Park West Village (Morrisville).
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_all,
                        contains_any, contains_count, contains_phrase, final_answer,
                        navigated_store_locator_query, norm, phrases_in_order,
                        run_verifier)

TASK_ID = "Michaels--5"


def _mentions(text, phrase, times):
    """`phrase` occurs at least `times` times (normalized, whole-token)."""
    return norm(text).count(norm(phrase)) >= times


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the store locator queried for Cary AND Durham AND NC
    judge.check("locator_cary_query", navigated_store_locator_query(traj, "Cary"),
                "required: /store-locator?q=Cary")
    judge.check("locator_durham_query", navigated_store_locator_query(traj, "Durham"),
                "required: /store-locator?q=Durham (New Hope Commons cross-check)")
    judge.check("locator_nc_query", navigated_store_locator_query(traj, "NC"),
                "required: /store-locator?q=NC")
    # answer: Cary store facts (its hours must be attributed — the task asks for
    # BOTH stores' Sunday hours, so the range must appear for each of them)
    judge.check("answer_cary_name", contains_phrase(answer, "Crossroads Plaza"),
                "expected the Cary store name Crossroads Plaza")
    judge.check("answer_cary_phone", contains_phrase(answer, "(919) 851-6001") or
                contains_all(answer, ["919", "851", "6001"]),
                "expected phone (919) 851-6001")
    judge.check("answer_sunday_hours", contains_all(answer, ["10:00 AM", "07:00 PM"]),
                "expected Sunday hours 10:00 AM - 07:00 PM")
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
    judge.check("answer_nhc_sunday",
                phrases_in_order(answer, ["New Hope Commons", "10:00 AM", "07:00 PM"]) or
                (_mentions(answer, "10:00 AM", 2) and _mentions(answer, "07:00 PM", 2)),
                "expected the Sunday hours 10:00 AM - 07:00 PM reported for the New Hope "
                "Commons store too (attributed to it, or stated for both stores)")
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
