#!/usr/bin/env python3
"""Verify MTA--4.

Green duffel bag with running shoes left on a 7 train at Flushing-Main St on
Tuesday evening, September 22. File a lost property claim with the right
agency (Alex Rivera, alex.rivera1984@example.com, 555-0187), report the claim
reference number and what the status page says to keep handy.

Frozen ground truth (seed DB): the 7 train at Flushing-Main St belongs to the
Subway, Bus and Staten Island Railway lost and found (agency nyct). The claim
form creates the first claim after a clean reset: LF-26096491 (deterministic
next_ref on the pinned day). The claim status page says: "Keep your claim
reference handy. Lost & Found staff update the status as the search
progresses."
"""
from verify_lib import (FIRST_CLAIM_REF, added_rows, check_only_tables_changed,
                        check_seed_contract, check_trajectory_identity, contains_any_phrase,
                        contains_ref, final_answer, navigated_to_path, run_verifier)

TASK_ID = "MTA--4"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_subway_claim_form",
                navigated_to_path(traj, "/lost-and-found/subway-bus-and-staten-island-railway/claim"),
                "required: the Subway, Bus and Staten Island Railway claim form")
    judge.check("answer_agency_subway",
                contains_any_phrase(answer, ["subway", "nyct", "staten island railway"]),
                "the claim must be filed with the subway lost and found")
    judge.check("answer_claim_ref", contains_ref(answer, FIRST_CLAIM_REF),
                f"the claim reference is {FIRST_CLAIM_REF}")
    judge.check("answer_keep_reference_handy",
                contains_any_phrase(answer, ["claim reference handy", "reference handy",
                                             "keep the claim reference", "keep your claim reference"]),
                "the status page says to keep the claim reference handy")
    added = added_rows(after_db, initial_db, "lost_claims", "claim_ref")
    judge.check("one_claim_added", len(added) == 1, f"added claims={[r['claim_ref'] for r in added]!r}")
    if added:
        c = added[0]
        judge.check("added_claim_ref", c["claim_ref"] == FIRST_CLAIM_REF,
                    f"claim_ref={c['claim_ref']!r}, expected {FIRST_CLAIM_REF}")
        judge.check("added_claim_agency_nyct", c["agency"] == "nyct", f"agency={c['agency']!r}")
        judge.check("added_claim_date", c["date_lost"] == "2026-09-22", f"date_lost={c['date_lost']!r}")
        judge.check("added_claim_line_7", "7" in (c["line_route"] or ""), f"line_route={c['line_route']!r}")
        judge.check("added_claim_station", (c["station"] or "").lower() == "flushing-main st",
                    f"station={c['station']!r}")
        judge.check("added_claim_item_bag",
                    "bag" in (c["item_type"] or "").lower()
                    and "green" in (c["item_description"] or "").lower()
                    and "shoe" in (c["item_description"] or "").lower(),
                    f"item_type={c['item_type']!r} desc={c['item_description']!r}")
        judge.check("added_claim_contact",
                    (c["contact_name"] or "") == "Alex Rivera"
                    and (c["contact_email"] or "").lower() == "alex.rivera1984@example.com"
                    and (c["contact_phone"] or "") == "555-0187",
                    f"contact=({c['contact_name']!r}, {c['contact_email']!r}, {c['contact_phone']!r})")
    check_only_tables_changed(judge, initial_db, after_db, ("lost_claims",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
