#!/usr/bin/env python3
"""Verify OhioMeansJobs--14.

Search for childcare jobs offering part-time schedules and report how many
match; open the Mount Vernon one (exact title, employer, posted date,
permanent or temporary, education level) plus the employer of the other
part-time childcare job; then find the childcare teaching job in Columbus
and report its employer, posted date, and whether it also offers part-time.

Frozen ground truth (seed DB): 'childcare' + Part-Time facet = 2 results:
'CHILDCARE WORKER' (6925540150) @ First Presbyterian Church of Mount Vernon,
Mount Vernon, OH, posted 2026-09-15, Part-Time + Permanent, education
"Bachelor's degree"; and 'Part Time Childcare Administrator - Cleveland
Heights-University Heights City Sc' (6928480951) @ Right at School LLC.
The Columbus childcare teaching job is 'Child Care Teacher' (6917643568) @
Bright Horizons Children's Centers, Inc., posted 2026-09-23 — its job types
include Part-Time. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        contains_count, contains_date, contains_phrase,
                        final_answer, navigated_job_detail, navigated_jobs_search,
                        run_verifier)

TASK_ID = "OhioMeansJobs--14"
MOUNT_VERNON_ID = "6925540150"
RIGHT_AT_SCHOOL_ID = "6928480951"
CHILD_CARE_TEACHER_ID = "6917643568"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_childcare_search",
                navigated_jobs_search(traj, tjt=["childcare"], jtype=["Part-Time"]),
                "required: /jobs/search with tjt=childcare + Part-Time facet")
    judge.check("visited_mount_vernon_detail", navigated_job_detail(traj, MOUNT_VERNON_ID),
                f"required: /jobs/view/{MOUNT_VERNON_ID} (CHILDCARE WORKER in Mount Vernon)")
    judge.check("visited_columbus_teacher_detail",
                navigated_job_detail(traj, CHILD_CARE_TEACHER_ID),
                f"required: /jobs/view/{CHILD_CARE_TEACHER_ID} (Child Care Teacher in Columbus)")
    # answer facts
    judge.check("answer_count_two", contains_count(answer, 2),
                "expected 2 part-time childcare matches")
    judge.check("answer_mount_vernon_title", contains_phrase(answer, "CHILDCARE WORKER"),
                "expected 'CHILDCARE WORKER'")
    judge.check("answer_mount_vernon_employer",
                contains_phrase(answer, "First Presbyterian Church"),
                "expected employer First Presbyterian Church of Mount Vernon")
    judge.check("answer_mount_vernon_posted", contains_date(answer, "2026-09-15"),
                "expected posted 2026-09-15")
    judge.check("answer_mount_vernon_permanent", contains_phrase(answer, "Permanent")
                and not contains_phrase(answer, "Temporary"),
                "expected Permanent (not Temporary)")
    judge.check("answer_mount_vernon_education", contains_phrase(answer, "Bachelor's degree"),
                "expected the Mount Vernon job education Bachelor's degree")
    judge.check("answer_other_employer", contains_phrase(answer, "Right at School"),
                "expected the other part-time childcare employer Right at School LLC")
    judge.check("answer_columbus_employer", contains_phrase(answer, "Bright Horizons"),
                "expected the Columbus childcare teacher employer Bright Horizons")
    judge.check("answer_columbus_posted", contains_date(answer, "2026-09-23"),
                "expected the Columbus Child Care Teacher posted 2026-09-23")
    judge.check("answer_columbus_part_time", contains_phrase(answer, "Part-Time"),
                "expected the Columbus Child Care Teacher also offers Part-Time")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
