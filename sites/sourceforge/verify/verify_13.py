#!/usr/bin/env python3
"""Verify SourceForge--13.

Register a new SourceForge account with username mirror-tester and email mirror-tester@example.com (password: LongPass123!). Then edit your profile to set your country to Germany, verify the change is saved, and report the exact wording of the two account pages you used plus what the account page shows for a brand-new user with no bookmarks.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--13"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_registration", r"/user/registration/")
    check_visited_path(judge, traj, "visited_account_edit", r"/account/edit")
    check_visited_path(judge, traj, "visited_account", r"/account/")
    check_answer_phrase(judge, answer, "username_registered", 'mirror-tester')
    check_answer_phrase(judge, answer, "country_germany", 'Germany')
    check_answer_phrase(judge, answer, "bookmarks_wording", 'bookmark')
    # stateful: a new user mirror-tester registered and set country to Germany.
    check_only_tables_changed(judge, initial_db, after_db, {"users"})
    added, removed, changed = table_diff(initial_db, after_db, "users")
    ok_u = len(added) == 1 and not removed and not changed
    if ok_u:
        row = list(added.values())[0]
        ok_u = (row["username"] == "mirror-tester"
                and row["email"] == "mirror-tester@example.com"
                and row["country"] == "DE")
    judge.check("user_registered_country_de", ok_u,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
