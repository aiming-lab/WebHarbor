#!/usr/bin/env python3
"""verify_13.py — deterministic verifier for task REMAX--13.

Florida-licensed agents: open each profile and report each one's years of
experience, then send the owner-broker a message about selling a house with
solar panels as a guest with the email given in the task; report the agent's
name, one civic activity, and the confirmation.

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, added_rows, check_only_tables_changed, check_seed_contract,
    check_trajectory_identity, contains_any_phrase, contains_count,
    contains_phrase, entered_identity, final_answer, nav_agent_detail,
    nav_agents_filtered, run_verifier)

TASK_ID = "REMAX--13"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: FL-filtered directory + each FL profile + the contact
    # form actually carrying the guest email and the solar-panels message
    judge.check("nav_agents_florida",
                nav_agents_filtered(traj, licensed="FL"),
                "required: /real-estate-agents with licensed=FL")
    for rid, name in (("100028868", "Patrick Kavanagh"),
                      ("102228725", "Nathan Berlin"),
                      ("102378504", "Deirdre Hecht")):
        judge.check(f"nav_agent_{rid}", nav_agent_detail(traj, rid),
                    f"required: agent detail for {name} ({rid})")
    judge.check("entered_guest_email",
                entered_identity(traj, "solar.seller@example.com"),
                "required: contact form filled with solar.seller@example.com")
    judge.check("entered_solar_message",
                entered_identity(traj, "solar"),
                "required: message mentions solar panels")
    # ground truth (frozen seed): Patrick Kavanagh 33, Nathan Berlin 13
    # (Broker / Owner, REMAX Masterpiece Realty, Port St Lucie; civic
    # activities include Children's Miracle Network / School Volunteer /
    # Community Development), Deirdre Hecht 3
    judge.check("answer_years_kavanagh", contains_count(answer, 33),
                "must state Patrick Kavanagh's 33 years")
    judge.check("answer_years_berlin", contains_count(answer, 13),
                "must state Nathan Berlin's 13 years")
    judge.check("answer_years_hecht", contains_count(answer, 3),
                "must state Deirdre Hecht's 3 years")
    judge.check("answer_name", contains_phrase(answer, "Nathan Berlin"),
                "must name Nathan Berlin")
    judge.check("answer_title", contains_phrase(answer, "Broker / Owner"),
                "must state the Broker / Owner title")
    judge.check("answer_civic",
                contains_any_phrase(answer, ["Children's Miracle Network",
                                              "School Volunteer",
                                              "Community Development"]),
                "must name one civic activity from the profile")
    judge.check("answer_confirmation",
                contains_any_phrase(answer, ["sent", "message has been",
                                             "will get back", "thank you"]),
                "must report the site's confirmation")
    # DB after-state: exactly one new agent inquiry
    check_seed_contract(judge, initial_db)
    check_only_tables_changed(judge, initial_db, after_db, ["inquiries"])
    new_inq = added_rows(after_db, initial_db, "inquiries", "id")
    judge.check("exactly_one_new_inquiry", len(new_inq) == 1,
                f"new inquiries: {new_inq}")
    if new_inq:
        r = new_inq[0]
        judge.check("inquiry_agent_16", r["agent_id"] == 16,
                    f"agent_id={r['agent_id']}")
        judge.check("inquiry_kind_agent", r["kind"] == "agent", f"kind={r['kind']}")
        judge.check("inquiry_email",
                   (r["email"] or "").lower() == "solar.seller@example.com",
                    f"email={r['email']}")
        judge.check("inquiry_message_solar",
                   "solar" in (r["message"] or "").lower(),
                   f"message={r['message']!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
