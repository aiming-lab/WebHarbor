#!/usr/bin/env python3
"""Verify bob joins the Chess School club and reports its stats in Chess.com--23."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--23"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: login and the club page.
    check_signed_in_as(judge, traj, "bob.c@test.com", "bob_c")
    check_visited_path(judge, traj, "visited_chess_school_club", "/club/chess-school")
    # Frozen ground truth: member count 147,770; Super Admin mentioned in the description: Evergreen_Warrior.
    judge.check("answer_member_count", contains_amount(answer, 147770), "expected 147,770 members")
    judge.check("answer_super_admin", contains_phrase(answer, "Evergreen Warrior"),
                "expected 'Evergreen_Warrior'")
    # DB after-state: exactly one club_memberships row added (bob -> chess-school, club_id 15);
    # bob's seed memberships (clubs 3, 8) are untouched.
    from verify_lib import check_only_tables_changed
    delta = table_delta(initial_db, after_db, "club_memberships")
    added_ok = len(delta["added"]) == 1 and delta["added"][0][1] == 1177 and delta["added"][0][2] == 15
    judge.check("club_membership_exact_delta",
                added_ok and not delta["removed"] and not delta["changed"],
                f"delta={delta!r} (expected exactly +1 row user_id=1177 -> club_id=15)")
    check_only_tables_changed(judge, initial_db, after_db, {"club_memberships"})



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
