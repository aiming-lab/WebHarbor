#!/usr/bin/env python3
"""Verify OhioMeansJobs--5.

Log in as carol.d@test.com. Create a saved search named 'Remote developer
roles' with daily alerts covering remote software developer positions, delete
her existing saved search that runs monthly, and report how many saved
searches she has afterwards.

Frozen ground truth (seed DB): carol starts with 2 saved searches ('Software
developer roles in Ohio' Daily, 'Remote data analyst jobs' Monthly). After the
task she must have exactly 2: the Daily pair (original + 'Remote developer
roles' Daily) with the Monthly one deleted. Stateful task: allowed delta =
saved_searches +1 (carol, 'Remote developer roles', Daily) and -1 (carol,
'Remote data analyst jobs', Monthly); nothing else.
"""
from verify_lib import (Judge, added_saved_searches, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_count, final_answer,
                        navigated_jobs_search, removed_saved_searches,
                        run_verifier, SEED_USERS)

TASK_ID = "OhioMeansJobs--5"
EMAIL = "carol.d@test.com"
CAROL_ID = SEED_USERS[EMAIL][0]
NEW_NAME = "Remote developer roles"
DELETED_NAME = "Remote data analyst jobs"
STATEFUL_TABLES = ("saved_searches",)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    check_visited_path(judge, traj, "visited_saved_searches", "/account/saved-searches")
    judge.check("visited_remote_dev_search",
                navigated_jobs_search(traj, tjt=["software developer"],
                                       remote=["1", "on", "true"]),
                "required: /jobs/search with tjt=software developer + remote filter")
    # answer facts
    judge.check("answer_count_two", contains_count(answer, 2),
                "expected 2 saved searches afterwards")
    # DB after-state
    added = added_saved_searches(after_db, initial_db)
    judge.check("one_search_added", len(added) == 1
                and added[0]["name"] == NEW_NAME,
                f"added={[a['name'] for a in added]!r}")
    if added:
        judge.check("added_search_daily_alerts",
                    added[0]["user_id"] == CAROL_ID and added[0]["frequency"] == "Daily"
                    and bool(added[0]["alerts_enabled"]),
                    f"row={added[0]!r}")
        judge.check("added_search_remote_params",
                    "remote" in (added[0]["query_params"] or ""),
                    f"params={added[0]['query_params']!r}")
    removed = removed_saved_searches(after_db, initial_db)
    judge.check("monthly_search_deleted", len(removed) == 1
                and removed[0]["name"] == DELETED_NAME
                and removed[0]["frequency"] == "Monthly",
                f"removed={[r['name'] for r in removed]!r}")
    check_only_tables_changed(judge, initial_db, after_db, STATEFUL_TABLES)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
