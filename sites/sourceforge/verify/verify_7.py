#!/usr/bin/env python3
"""Verify SourceForge--7.

Using the demo account (email: alice.j@test.com, password: TestPass123!), log in and research password managers: search the directory for "password manager", report the top result by relevance and its weekly downloads, bookmark it, then write it a 5-star review saying you use it daily. Confirm both the bookmark and the review appear on your account page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--7"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "login_page", r"/auth/")
    check_visited_path(judge, traj, "search_results", r"/directory/\?q=password\+manager")
    check_visited_path(judge, traj, "visited_passwordsafe", r"/projects/passwordsafe/")
    check_visited_path(judge, traj, "visited_review_form", r"/projects/passwordsafe/reviews/new")
    check_visited_path(judge, traj, "visited_account", r"/account/")
    check_answer_phrase(judge, answer, "top_result", 'Password Safe')
    check_answer_number(judge, answer, "top_week", 1788, 'Password Safe weekly downloads')
    check_answer_phrase(judge, answer, "review_text_daily", 'daily')
    # stateful: alice bookmarked Password Safe and posted it a 5-star review.
    check_only_tables_changed(judge, initial_db, after_db, {"bookmarks", "reviews", "projects"})
    added, removed, changed = table_diff(initial_db, after_db, "bookmarks")
    judge.check("bookmark_added_passwordsafe",
                len(added) == 1 and added and all(r["project_id"] == _pid(after_db, "passwordsafe") and r["user_id"] == 1991 for r in added.values()) and not removed and not changed,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")
    added, removed, changed = table_diff(initial_db, after_db, "reviews")
    ok_rev = (len(added) == 1 and not removed)
    if ok_rev:
        row = list(added.values())[0]
        ok_rev = (row["author_name"] == "alice_j" and row["rating"] == 5
                  and "daily" in (row["text"] or ""))
    judge.check("review_added_5star_daily", ok_rev,
                f"added={list(added.values())} removed={list(removed.values())}")
    added, removed, changed = table_diff(initial_db, after_db, "projects")
    ok_p = len(changed) == 1 and not added and not removed
    if ok_p:
        old, new = list(changed.values())[0]
        ok_p = (new["review_count"] == old["review_count"] + 1
                and new["stars_5"] == old["stars_5"] + 1
                and new["shortname"] == "passwordsafe")
    judge.check("passwordsafe_counters_bumped", ok_p,
                f"changed={[(c, v[1]['shortname']) for c, v in changed.items()]}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
