#!/usr/bin/env python3
"""Verify Instructure--9: sign in (alice) -> remove the Madison County case
study -> save the 2026 EdTech Evidence Report -> profile state Colorado."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_all, contains_count, contains_phrase,
                        final_answer, resource_id_by_slug, run_verifier,
                        selected_option, single_changed_user, table_delta,
                        user_id_by_email, delta_dicts)

TASK_ID = "Instructure--9"

MADISON = "staying-course-better-benchmarks-madison-county"
STUDY = "2026-edtech-evidence-report"
ALICE = "alice.j@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE)
    # Navigation gates: saved list, the Research hub study, the account page.
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    check_visited_path(judge, traj, "visited_research_study",
                       "/resources/research-reports/" + STUDY)
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("selected_state_colorado", selected_option(traj, "Colorado"),
                "the state select must choose Colorado")
    # Frozen ground truth (app.py flashes + seed rows): removal flash
    # "Removed '<title>' from your saved resources."; profile flash
    # "Your profile has been updated."; alice keeps 4 saved resources
    # (seed 4 - Madison + the 2026 report).
    judge.check("answer_removal_confirmation",
                contains_all(answer, ["Removed", "from your saved resources"]),
                "expected the removal confirmation message")
    judge.check("answer_profile_confirmation",
                contains_phrase(answer, "Your profile has been updated"),
                "expected the profile update confirmation")
    judge.check("answer_saved_count", contains_count(answer, 4),
                "expected the post-curation saved count (4)")
    # DB delta: alice->Madison saved row removed, alice->2026-report saved row
    # added, alice's users row changed only in state (Colorado).
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_removed = delta_dicts(initial_db, "saved_resources", saved_delta, "removed")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta, "added")
    alice_id = user_id_by_email(initial_db, ALICE)
    madison_id = resource_id_by_slug(initial_db, MADISON)
    study_id = resource_id_by_slug(initial_db, STUDY)
    judge.check("db_removed_madison_row",
                len(saved_removed) == 1 and saved_removed[0]["user_id"] == alice_id
                and saved_removed[0]["resource_id"] == madison_id,
                "expected exactly the alice->Madison saved row removed")
    judge.check("db_added_study_row",
                len(saved_added) == 1 and saved_added[0]["user_id"] == alice_id
                and saved_added[0]["resource_id"] == study_id,
                "expected exactly one new saved row: alice -> the 2026 report")
    ok_profile, why = single_changed_user(initial_db, after_db, ALICE,
                                          {"state": "Colorado",
                                           "phone": "+1 801-555-0199"})
    judge.check("db_profile_state_and_phone_only", ok_profile, why)
    check_only_tables_changed(judge, initial_db, after_db, ["saved_resources", "users"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
