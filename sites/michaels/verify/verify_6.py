#!/usr/bin/env python3
"""Verify Michaels--6.

Alice's niece wants to join the live online Halloween kids' class on September 28. Sign in as alice.j@test.com (password TestPass123!), find the class and register Alice. Tell her the class title, start time and time zone, host and platform so she can join, and confirm that it appears in her account's class registrations.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_phrase, contains_time, final_answer, navigated_to,
                        registrations_of, run_verifier)

TASK_ID = "Michaels--6"
CLASS_ID = 4


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: sign-in, classes page, the registrations page, Fabric & Sewing
    check_signed_in_as(judge, traj, "alice.j@test.com")
    check_visited_path(judge, traj, "visited_classes", "/classes")
    check_visited_path(judge, traj, "visited_registrations", "/account/registrations")
    # answer: class facts + host + registrations-page confirmation + tutorial
    judge.check("answer_class_title", contains_phrase(answer, "Kids Club: Halloween Bat Mask"),
                "expected class title Kids Club: Halloween Bat Mask")
    judge.check("answer_start_time", contains_time(answer, 3, "00", "pm") and
                contains_time(answer, 4, "00", "pm"),
                "expected start time 03:00 pm - 04:00 pm PDT")
    judge.check("answer_platform", contains_phrase(answer, "Vimeo"),
                "expected platform Virtual Classroom - Vimeo")
    judge.check("answer_host", contains_phrase(answer, "Learn With Michaels"),
                "expected the class host Learn With Michaels")
    judge.check("answer_registrations_confirm",
                contains_all(answer, ["Registered", "Alice Johnson"]),
                "expected the account class-registrations page confirmation "
                "(Registered ... for Alice Johnson)")
    # DB after-state: exactly one class registration added for alice + class 4
    before = registrations_of(initial_db, "alice.j@test.com")
    after = registrations_of(after_db, "alice.j@test.com")
    added = [r for r in after if r["id"] not in {b["id"] for b in before}]
    judge.check("added_registration_row",
                len(added) == 1 and added[0]["class_event_id"] == CLASS_ID and
                added[0]["attendee_name"] == "Alice Johnson",
                f"expected one registration row for class {CLASS_ID}; found={added!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("class_registrations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
