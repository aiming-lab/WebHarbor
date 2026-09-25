#!/usr/bin/env python3
"""Verify Instructure--6: Leadership page (Chief Learning Officer bio) ->
Request a Demo form submission (Jordan Lee / Summit Public Schools)."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_phrase,
                        entered_identity, final_answer, run_verifier,
                        selected_option, single_added_row)

TASK_ID = "Instructure--6"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the leadership page, the demo form.
    check_visited_path(judge, traj, "visited_leadership_page", "/about/leadership")
    check_visited_path(judge, traj, "visited_request_demo_page", "/request-demo")
    judge.check("entered_demo_identity",
                entered_identity(traj, "jordan.lee@test.com"),
                "expected jordan.lee@test.com among the form inputs")
    judge.check("selected_org_type_k12", selected_option(traj, "K12"),
                "the organization-type select must choose K12")
    judge.check("selected_needs_sales",
                selected_option(traj, "I want to connect with sales"),
                "the needs select must choose the sales option")
    judge.check("selected_state_colorado", selected_option(traj, "Colorado"),
                "the state select must choose Colorado")
    # Frozen ground truth (seed leadership + app.py flash): the Chief Learning
    # Officer is Melissa Loble, who chairs the 1EdTech board of directors; the
    # demo confirmation is "Thanks! An Instructure team member will reach out
    # within one business day."
    judge.check("answer_clo_name", contains_phrase(answer, "Melissa Loble"),
                "expected Melissa Loble named as Chief Learning Officer")
    judge.check("answer_board_role", contains_phrase(answer, "1EdTech"),
                "expected the 1EdTech board named from her bio")
    judge.check("answer_demo_confirmation",
                contains_phrase(answer, "within one business day"),
                "expected the demo request confirmation")
    # DB delta: exactly one demo_requests row with the specified identity.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    judge.check("db_demo_request_row",
                ok_demo
                and demo_row.get("first_name") == "Jordan"
                and demo_row.get("last_name") == "Lee"
                and demo_row.get("email") == "jordan.lee@test.com"
                and demo_row.get("job_title") == "Director of Curriculum"
                and demo_row.get("organization") == "Summit Public Schools"
                and demo_row.get("organization_type") == "K12"
                and demo_row.get("state") == "Colorado"
                and demo_row.get("needs") == "I want to connect with sales"
                and demo_row.get("source") == "Web Site",
                "expected exactly one Jordan Lee demo_requests row from the Web Site source")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
