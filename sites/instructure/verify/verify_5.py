#!/usr/bin/env python3
"""Verify Instructure--5: Careers location filter (Mexico) -> register a new
account -> save the Murrieta Valley case study -> Saved Resources confirmation."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_any, contains_count,
                        contains_phrase, delta_dicts, entered_test_email,
                        final_answer, resource_id_by_slug, run_verifier,
                        selected_option, single_added_row, table_delta,
                        user_id_by_email)

TASK_ID = "Instructure--5"

MVCSD = "mvcsd-studio-case-study"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: careers board with the Mexico location filter, the
    # register page, the Murrieta Valley case study, the saved list.
    check_visited_path(judge, traj, "visited_careers_page", "/about/careers")
    judge.check("careers_location_filter_mexico",
                selected_option(traj, "Mexico"),
                "a location-filter select must choose Mexico")
    check_visited_path(judge, traj, "visited_register_page", "/register")
    check_visited_path(judge, traj, "visited_mvcsd_case_study",
                       "/resources/case-studies/" + MVCSD)
    check_visited_path(judge, traj, "visited_account", "/account")
    judge.check("entered_test_email", entered_test_email(traj),
                "a @test.com address must be entered for the new account")
    # Frozen ground truth (seed careers row): 'Associate Customer Success
    # Manager - Higher Education', Mexico, FullTime, comp
    # 'MX$427K – MX$532K • Offers Equity • Offers Commission'.
    judge.check("answer_mx_salary_range",
                contains_phrase(answer, "MX$427K") and contains_phrase(answer, "MX$532K"),
                "expected the MX$427K - MX$532K salary range")
    judge.check("answer_employment_type",
                contains_phrase(answer, "full time"),
                "expected the FullTime employment type")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    # DB delta: one new @test.com user; one saved row linking that user to
    # the Murrieta Valley case study.
    ok_user, new_user = single_added_row(initial_db, after_db, "users")
    judge.check("db_users_delta",
                ok_user and str(new_user.get("email", "")).endswith("@test.com"),
                "expected exactly one new @test.com user row")
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    new_id = user_id_by_email(after_db, new_user.get("email", ""))
    mvcsd_id = resource_id_by_slug(initial_db, MVCSD)
    judge.check("db_saved_mvcsd_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == new_id
                and saved_added[0]["resource_id"] == mvcsd_id,
                "expected exactly one new saved row: new user -> Murrieta Valley")
    check_only_tables_changed(judge, initial_db, after_db, ["users", "saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
