#!/usr/bin/env python3
"""Verify Instructure--4: sign in (carol) -> Events board Event Type=Webinar
filter -> 'Canvas Tiers in Action' -> register + save -> account confirmation
-> InstructureCon 2026 homepage banner fact."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_date_phrase, contains_phrase, final_answer,
                        navigated_to_path_with_params, resource_id_by_slug,
                        run_verifier, table_delta, user_id_by_email, delta_dicts)

TASK_ID = "Instructure--4"

WEBINAR = "canvas-tiers-in-action"
CAROL = "carol.d@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL)
    # Navigation gates: the filtered Events board, the Canvas Tiers page, the account.
    judge.check("visited_events_with_webinar_filter",
                navigated_to_path_with_params(traj, "/events",
                                              {"event_type": "Webinar",
                                               "region": "North America"}),
                "required_path=/events with event_type=Webinar and region=North America")
    check_visited_path(judge, traj, "visited_canvas_tiers_page",
                       "/resources/webinars/" + WEBINAR)
    check_visited_path(judge, traj, "visited_account", "/account")
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed): event date Sep 29, 2026; register flash
    # "You're registered for '<title>' — find it under your account."; save
    # flash "Saved '<title>' to your account."; homepage banner
    # "InstructureCon 2026 / Louisville, Kentucky | July 21–23".
    judge.check("answer_event_date",
                contains_date_phrase(answer, "September 29, 2026"),
                "expected the event date September 29, 2026")
    judge.check("answer_registration_confirmation",
                contains_phrase(answer, "find it under your account"),
                "expected the registration confirmation")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    judge.check("answer_instructurecon_place",
                contains_phrase(answer, "Louisville, Kentucky"),
                "expected InstructureCon 2026 in Louisville, Kentucky")
    judge.check("answer_instructurecon_dates",
                contains_phrase(answer, "July 21-23"),
                "expected InstructureCon 2026 on July 21-23")
    # DB delta: one registration + one save, both carol -> Canvas Tiers.
    regs_delta = table_delta(initial_db, after_db, "webinar_registrations")
    regs_added = delta_dicts(after_db, "webinar_registrations", regs_delta)
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    carol_id = user_id_by_email(initial_db, CAROL)
    webinar_id = resource_id_by_slug(initial_db, WEBINAR)
    judge.check("db_registration_row",
                len(regs_added) == 1 and not regs_delta["removed"]
                and not regs_delta["changed"]
                and regs_added[0]["user_id"] == carol_id
                and regs_added[0]["resource_id"] == webinar_id,
                "expected exactly one new registration row: carol -> Canvas Tiers")
    judge.check("db_saved_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == carol_id
                and saved_added[0]["resource_id"] == webinar_id,
                "expected exactly one new saved row: carol -> Canvas Tiers")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["webinar_registrations", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
