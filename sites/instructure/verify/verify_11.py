#!/usr/bin/env python3
"""Verify Instructure--11: Research hub 2026 Canvas LMS Educator Impact Study
(250-educator survey) -> Request a Demo (Alex Rivera / Cascadia)."""

from verify_lib import (check_trajectory_identity, check_visited_path,
                        check_only_tables_changed, contains_count,
                        contains_phrase, entered_identity, final_answer,
                        run_verifier, selected_option, single_added_row)

TASK_ID = "Instructure--11"

STUDY = "27890"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the Research hub study and the demo form.
    check_visited_path(judge, traj, "visited_research_hub", "/resources/research-reports")
    check_visited_path(judge, traj, "visited_impact_study",
                       "/resources/research-reports/" + STUDY)
    check_visited_path(judge, traj, "visited_request_demo_page", "/request-demo")
    judge.check("entered_demo_identity",
                entered_identity(traj, "alex.rivera@test.com"),
                "expected alex.rivera@test.com among the form inputs")
    judge.check("selected_org_type_higher_ed",
                selected_option(traj, "Higher Ed"),
                "the organization-type select must choose Higher Ed")
    judge.check("selected_needs_sales",
                selected_option(traj, "I want to connect with sales"),
                "the needs select must choose the sales option")
    judge.check("selected_state_washington", selected_option(traj, "Washington"),
                "the state select must choose Washington")
    # Frozen ground truth (seed intro): the 2026 Canvas LMS Educator Impact
    # Study is based on a 2026 survey of 250 educators; the demo flash is
    # "Thanks! An Instructure team member will reach out within one business day."
    judge.check("answer_survey_size", contains_count(answer, 250),
                "expected the 250-educator survey size")
    judge.check("answer_demo_confirmation",
                contains_phrase(answer, "within one business day"),
                "expected the demo request confirmation")
    # DB delta: exactly one demo_requests row with the specified identity.
    ok_demo, demo_row = single_added_row(initial_db, after_db, "demo_requests")
    judge.check("db_demo_request_row",
                ok_demo
                and demo_row.get("first_name") == "Alex"
                and demo_row.get("last_name") == "Rivera"
                and demo_row.get("email") == "alex.rivera@test.com"
                and demo_row.get("job_title") == "Dean of Instruction"
                and demo_row.get("organization") == "Cascadia Community College"
                and demo_row.get("organization_type") == "Higher Ed"
                and demo_row.get("state") == "Washington"
                and demo_row.get("needs") == "I want to connect with sales"
                and demo_row.get("source") == "Web Site",
                "expected exactly one Alex Rivera demo_requests row from the Web Site source")
    check_only_tables_changed(judge, initial_db, after_db, ["demo_requests"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
