#!/usr/bin/env python3
"""Verify OhioMeansJobs--17.

Log in as bob.c@test.com. He has three cover letters saved. Delete the one
about driving, create a new cover letter named 'Warehouse Team Letter' with a
short body about warehouse experience, report how many cover letters he has
afterwards, the name of the oldest remaining one, and the maximum number of
cover letters the site says you can save; then open his career plan and
report how many tasks it contains, how many are marked complete, and the
deadline of the task about renewing a certification.

Frozen ground truth (seed DB): bob's letters are 'Warehouse Operations Cover
Letter' (updated 2026-09-22), 'Driver Cover Letter' (2026-09-17), 'Veteran
Transition Cover Letter' (2026-09-15). After deleting the Driver letter and
creating 'Warehouse Team Letter' he has 3 letters; the oldest remaining is
'Veteran Transition Cover Letter' (2026-09-15). The cover-letters page says
you can save 5 different cover letters. His career plan has 3 tasks, 1 marked
complete; the 'Renew forklift certification' task has deadline 2026-10-10.
Stateful task: allowed delta = cover_letters -1 (bob/Driver) +1
(bob/Warehouse Team Letter); nothing else.
"""
from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path,
                        contains_count, contains_count_near, contains_phrase,
                        cover_letters_of, db_query, final_answer, run_verifier,
                        SEED_USERS)

TASK_ID = "OhioMeansJobs--17"
EMAIL = "bob.c@test.com"
BOB_ID = SEED_USERS[EMAIL][0]
DELETED_NAME = "Driver Cover Letter"
CREATED_NAME = "Warehouse Team Letter"
OLDEST_REMAINING = "Veteran Transition Cover Letter"
MAX_LETTERS = 5
PLAN_TASKS = 3
PLAN_DONE = 1
CERT_DEADLINE = "2026-10-10"
STATEFUL_TABLES = ("cover_letters",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_cover_letters", "/account/cover-letters")
    # answer facts
    judge.check("answer_count_three", contains_count(answer, 3),
                "expected 3 cover letters afterwards")
    judge.check("answer_oldest_remaining",
                contains_phrase(answer, OLDEST_REMAINING),
                f"expected the oldest remaining letter '{OLDEST_REMAINING}'")
    judge.check("answer_max_letters", contains_count(answer, MAX_LETTERS),
                f"expected the site to say you can save {MAX_LETTERS} different cover letters")
    check_visited_path(judge, traj, "visited_career_plan", "/account/career-plan")
    judge.check("answer_plan_task_count",
                contains_count_near(answer, PLAN_TASKS, ["task", "plan"]),
                f"expected {PLAN_TASKS} career-plan tasks (count near the plan/task "
                "wording, not an unrelated integer elsewhere)")
    judge.check("answer_plan_done_count", contains_count(answer, PLAN_DONE),
                f"expected {PLAN_DONE} career-plan task marked complete")
    judge.check("answer_cert_deadline", contains_phrase(answer, CERT_DEADLINE),
                f"expected the certification-renewal task deadline {CERT_DEADLINE}")
    # DB after-state: bob's Driver letter gone, Warehouse Team Letter present
    before = cover_letters_of(initial_db, BOB_ID)
    after = cover_letters_of(after_db, BOB_ID)
    judge.check("driver_letter_deleted",
                any(l["name"] == DELETED_NAME for l in before)
                and not any(l["name"] == DELETED_NAME for l in after),
                f"before={[l['name'] for l in before]!r} after={[l['name'] for l in after]!r}")
    created = [l for l in after if l["name"] == CREATED_NAME]
    judge.check("warehouse_team_letter_created", len(created) == 1,
                f"created={[l['name'] for l in created]!r}")
    if created:
        judge.check("created_letter_has_body",
                    len(created[0]["body"] or "") > 10,
                    f"body_len={len(created[0]['body'] or '')}")
    judge.check("bob_letter_count_three", len(after) == 3,
                f"bob letters after={len(after)}")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
