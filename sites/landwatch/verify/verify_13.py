#!/usr/bin/env python3
"""Verify LandWatch--13 — 'Prime Ohio Farmland' contact form submission.

Ground truth (frozen seed): submitting the validated contact form flashes
'Your message has been sent to the listing agent.' and writes exactly one
inquiries row for pid 427843237 whose message asks about the soil quality.
"""
from verify_lib import (Judge, check_only_tables_changed,
                        check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, normalize_text,
                        run_verifier, table_delta)

TASK_ID = "LandWatch--13"
DETAIL_PATH = "/allen-county-ohio-farms-and-ranches-for-sale/pid/427843237"
CONFIRMATION = "Your message has been sent to the listing agent."
LISTING_PID = 427843237


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_ohio_farmland_detail", DETAIL_PATH)
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "inquiries"})
    delta = table_delta(initial_db, after_db, "inquiries")
    judge.check("exactly_one_inquiry_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"inquiries delta={delta!r}")
    if delta["added"]:
        row = delta["added"][0]
        # row: id, user_id, pid, name, email, phone, message, created_at
        judge.check("inquiry_for_ohio_farmland", row[2] == LISTING_PID,
                    f"expected pid {LISTING_PID}, observed {row[2]!r}")
        judge.check("inquiry_message_asks_about_soil",
                    bool(normalize_text(row[6])) and "soil" in normalize_text(row[6]),
                    f"expected a message about soil quality, observed {row[6]!r}")
        judge.check("inquiry_email_present", "@" in (row[4] or ""),
                    f"expected a valid submitter email, observed {row[4]!r}")
    judge.check("answer_confirmation", contains_phrase(answer, CONFIRMATION),
                f"expected the confirmation {CONFIRMATION!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
