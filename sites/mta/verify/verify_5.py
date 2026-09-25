#!/usr/bin/env python3
"""Verify MTA--5.

Follow up on two lost property claims: LF-26094217 (subway lost and found)
and LF-26095803 (Long Island Rail Road). Report the status of each, the items
they cover, and what the status page says to keep handy.

Frozen ground truth (seed DB): LF-26094217 — status "Received", navy blue
JanSport backpack with a water bottle and a gray laptop sleeve (2 train,
Flatbush Av-Brooklyn College, alice.j@test.com). LF-26095803 — status "In
Review", black compact umbrella with a wooden handle left on the overhead
rack (Babylon Branch, Penn Station, bob.c@test.com). Both status pages say:
"Keep your claim reference handy. Lost & Found staff update the status as
the search progresses."
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_phrase, contains_ref, final_answer, navigated_to_path, run_verifier)

import re

TASK_ID = "MTA--5"


def _claim_sentence_has(answer, ref, *needles):
    """One sentence that names the claim by its reference must also carry one
    of the needles. The judge_rubric makes mixing up the claims a FAIL, so a
    swapped-status answer (the right words attached to the wrong claim) must
    not pass the per-claim gates (audit hardening)."""
    for s in re.split(r"[.;\n]", answer.lower()):
        if ref in s and any(n in s for n in needles):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_claim_1", navigated_to_path(traj, "/lost-and-found/claim/LF-26094217"),
                "required: /lost-and-found/claim/LF-26094217")
    judge.check("visited_claim_2", navigated_to_path(traj, "/lost-and-found/claim/LF-26095803"),
                "required: /lost-and-found/claim/LF-26095803")
    judge.check("answer_status_received",
                _claim_sentence_has(answer, "lf-26094217", "received"),
                "LF-26094217 status: Received (claim-scoped: mixing up the claims is a FAIL)")
    judge.check("answer_status_in_review",
                _claim_sentence_has(answer, "lf-26095803", "in review"),
                "LF-26095803 status: In Review (claim-scoped: mixing up the claims is a FAIL)")
    judge.check("answer_item_backpack",
                _claim_sentence_has(answer, "lf-26094217", "backpack", "jansport"),
                "LF-26094217 covers a navy blue JanSport backpack (claim-scoped)")
    judge.check("answer_item_umbrella",
                _claim_sentence_has(answer, "lf-26095803", "umbrella"),
                "LF-26095803 covers a black compact umbrella (claim-scoped)")
    judge.check("answer_keep_reference_handy",
                contains_any_phrase(answer, ["claim reference handy", "reference handy",
                                             "keep the claim reference", "keep your claim reference"]),
                "the status page says to keep the claim reference handy")
    judge.check("visited_claim_3", navigated_to_path(traj, "/lost-and-found/claim/LF-26096625"),
                "required: /lost-and-found/claim/LF-26096625")
    judge.check("visited_mnr_lost_found_page",
                navigated_to_path(traj, "/lost-and-found/metro-north-railroad"),
                "required: the Metro-North lost-and-found page (holding facility)")
    judge.check("visited_subway_lost_found_page",
                navigated_to_path(traj, "/lost-and-found/subway-bus-and-staten-island-railway"),
                "required: the subway lost-and-found page (after-filing guidance)")
    judge.check("answer_claim3_matched_jacket",
                contains_phrase(answer, "matched") and
                (contains_phrase(answer, "jacket") or contains_ref(answer, "lf-26096625")),
                "LF-26096625 is Matched - Pickup Pending (beige rain jacket)")
    judge.check("answer_facility_metro_north",
                contains_phrase(answer, "metro-north"),
                "the matched claim is held at Metro-North's Lost and Found Facility")
    judge.check("answer_after_filing_claim_reference",
                contains_any_phrase(answer, ["claim reference to track", "reference to track",
                                             "search for the item", "searches for the item",
                                             "wait for us to contact you", "we contact you",
                                             "make an appointment", "schedule an appointment"]),
                "after filing: the MTA searches and issues a claim reference to track the "
                "report (or, per the process steps: wait to be contacted, then make an appointment)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
