#!/usr/bin/env python3
"""Verify Instructure--15: sign in (bob) -> Infographics hub IgniteAI Quick-Start
Checklist save -> On-Demand Webinars IgniteAI K-12 webinar registration -> both
confirmations under the account."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_phrase, delta_dicts, final_answer,
                        resource_id_by_slug, run_verifier, table_delta,
                        user_id_by_email)

TASK_ID = "Instructure--15"

INFOGRAPHIC = "your-igniteai-quick-start-checklist"
WEBINAR = ("reclaim-time-and-personalize-learning-meet-igniteai-"
           "k-12-schools-and-districts")
BOB = "bob.c@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, BOB)
    # Navigation gates: both hubs, both detail pages, the account.
    check_visited_path(judge, traj, "visited_infographics_hub", "/resources/infographic")
    check_visited_path(judge, traj, "visited_checklist_detail",
                       "/resources/infographic/" + INFOGRAPHIC)
    check_visited_path(judge, traj, "visited_webinars_hub", "/resources/webinars")
    check_visited_path(judge, traj, "visited_webinar_detail",
                       "/resources/webinars/" + WEBINAR)
    check_visited_path(judge, traj, "visited_account", "/account")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (app.py flashes): save flash "Saved '<title>' to
    # your account."; register flash "You're registered for '<title>' — find
    # it under your account."
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the infographic save confirmation")
    judge.check("answer_registration_confirmation",
                contains_phrase(answer, "find it under your account"),
                "expected the webinar registration confirmation")
    # DB delta: one saved row (bob -> checklist) + one registration row
    # (bob -> webinar).
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    regs_delta = table_delta(initial_db, after_db, "webinar_registrations")
    regs_added = delta_dicts(after_db, "webinar_registrations", regs_delta)
    bob_id = user_id_by_email(initial_db, BOB)
    checklist_id = resource_id_by_slug(initial_db, INFOGRAPHIC)
    webinar_id = resource_id_by_slug(initial_db, WEBINAR)
    judge.check("db_saved_checklist_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == bob_id
                and saved_added[0]["resource_id"] == checklist_id,
                "expected exactly one new saved row: bob -> the checklist")
    judge.check("db_registration_row",
                len(regs_added) == 1 and not regs_delta["removed"]
                and not regs_delta["changed"]
                and regs_added[0]["user_id"] == bob_id
                and regs_added[0]["resource_id"] == webinar_id,
                "expected exactly one new registration row: bob -> the webinar")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["saved_resources", "webinar_registrations"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
