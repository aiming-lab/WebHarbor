#!/usr/bin/env python3
"""Verify SourceForge--18.

Using the demo account (email: bob.c@test.com, password: TestPass123!), log in and review your existing bookmarks. Report every project currently bookmarked with its name, then remove the disk-health tool from your bookmarks, add the bootable USB drive tool instead, write that new project a 4-star review mentioning USB sticks, and confirm the final bookmark list on the account page.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--18"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "login_page", r"/auth/")
    check_visited_path(judge, traj, "visited_account", r"/account/")
    check_visited_path(judge, traj, "visited_crystaldiskinfo", r"/projects/crystaldiskinfo/")
    check_visited_path(judge, traj, "visited_ventoy", r"/projects/ventoy/")
    check_visited_path(judge, traj, "visited_review_form", r"/projects/ventoy/reviews/new")
    check_answer_phrase(judge, answer, "bookmark_winscp", 'WinSCP')
    check_answer_phrase(judge, answer, "bookmark_before_crystaldiskinfo", 'CrystalDiskInfo')
    check_answer_phrase(judge, answer, "bookmark_after_ventoy", 'Ventoy')
    check_answer_phrase(judge, answer, "review_mentions_usb", 'USB')
    # stateful: bob removed CrystalDiskInfo, added Ventoy, posted a 4-star review.
    check_only_tables_changed(judge, initial_db, after_db, {"bookmarks", "reviews", "projects"})
    added, removed, changed = table_diff(initial_db, after_db, "bookmarks")
    ok_b = False
    delta = {"added": list(added.values()), "removed": list(removed.values()),
             "changed": [(k, v[0]["project_id"], v[1]["project_id"]) for k, v in changed.items()]}
    if len(changed) == 1 and not added and not removed:
        (old_row, new_row) = list(changed.values())[0]
        ok_b = (new_row["user_id"] == 1992
                and new_row["project_id"] == _pid(after_db, "ventoy")
                and old_row["project_id"] == _pid(initial_db, "crystaldiskinfo"))
    elif len(added) == 1 and len(removed) == 1 and not changed:
        ok_b = (all(r["project_id"] == _pid(after_db, "ventoy") and r["user_id"] == 1992 for r in added.values())
                and all(r["project_id"] == _pid(initial_db, "crystaldiskinfo") and r["user_id"] == 1992 for r in removed.values()))
    judge.check("bookmark_swap_ventoy_for_crystaldiskinfo", ok_b,
                f"delta={delta}")
    added, removed, changed = table_diff(initial_db, after_db, "reviews")
    ok_rev = (len(added) == 1 and not removed)
    if ok_rev:
        row = list(added.values())[0]
        ok_rev = (row["author_name"] == "bob_c" and row["rating"] == 4
                  and "usb" in (row["text"] or "").lower())
    judge.check("review_added_4star_usb", ok_rev,
                f"added={list(added.values())} removed={list(removed.values())}")
    added, removed, changed = table_diff(initial_db, after_db, "projects")
    ok_p = len(changed) == 1 and not added and not removed
    if ok_p:
        old, new = list(changed.values())[0]
        ok_p = (new["review_count"] == old["review_count"] + 1
                and new["stars_4"] == old["stars_4"] + 1
                and new["shortname"] == "ventoy")
    judge.check("ventoy_counters_bumped", ok_p,
                f"changed={[(c, v[1]['shortname']) for c, v in changed.items()]}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
