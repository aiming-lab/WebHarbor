#!/usr/bin/env python3
"""Verify SourceForge--13.

Register a new SourceForge account with username fleet-admin and email fleet-admin@example.com (password: LongPass123!). Edit your profile to set your country to Germany and a display name of your choosing, then verify both changes appear on your account page. Bookmark the CrystalDiskInfo project from its project page, then confirm the bookmark appears on your account page. Report the exact heading text of the two account pages you used, and what the account page lists under My Reviews for a brand-new user.
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
    check_visited_path(judge, traj, "visited_crystaldiskinfo", r"/projects/crystaldiskinfo/")
    check_answer_phrase(judge, answer, "username_registered", 'fleet-admin')
    check_answer_phrase(judge, answer, "country_germany", 'Germany')
    check_answer_phrase(judge, answer, "display_name_set", 'Fleet')
    check_answer_phrase(judge, answer, "bookmark_crystaldiskinfo", 'CrystalDiskInfo')
    check_answer_phrase(judge, answer, "account_heading", 'My Account')
    check_answer_phrase(judge, answer, "edit_heading", 'Edit Profile')
    check_answer_phrase(judge, answer, "no_reviews_wording", 'any reviews yet')
    # stateful: fleet-admin registered (country DE, display name set) and
    # bookmarked CrystalDiskInfo.
    check_only_tables_changed(judge, initial_db, after_db, {"users", "bookmarks"})
    added, removed, changed = table_diff(initial_db, after_db, "users")
    ok_u = len(added) == 1 and not removed and not changed
    if ok_u:
        row = list(added.values())[0]
        ok_u = (row["username"] == "fleet-admin"
                and row["email"] == "fleet-admin@example.com"
                and row["country"] == "DE"
                and (row["display_name"] or "") != "")
    judge.check("user_registered_de_display_name", ok_u,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")
    added, removed, changed = table_diff(initial_db, after_db, "bookmarks")
    ok_b = len(added) == 1 and not removed and not changed
    if ok_b:
        row = list(added.values())[0]
        ok_b = (row["project_id"] == _pid(after_db, "crystaldiskinfo")
                and row["user_id"] == list(table_diff(initial_db, after_db, "users")[0].values())[0]["id"])
    judge.check("bookmark_added_crystaldiskinfo", ok_b,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
