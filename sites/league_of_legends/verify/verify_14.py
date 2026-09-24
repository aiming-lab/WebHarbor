#!/usr/bin/env python3
"""Verify League of Legends--14: bookmark CRUD round-trip (save 26.19, drop oldest).

Honest chain (15 atomic actions): Play Now -> Sign In -> fill email -> fill
password -> submit -> Patch Notes nav -> open 26.19 -> Save Article ->
My Account -> Saved Articles (5 saved) -> open '/dev: Midseason and Mythics'
(the oldest seeded bookmark) -> Remove Bookmark -> My Account -> Saved
Articles (4 saved) -> answer.

Frozen ground truth (seed DB): david_k (id 4) starts with 4 bookmarks
(Zaahen Abilities Rundown 2025-11-09, /dev: Account Linking and Streamer Mode
2025-10-06, /dev: Skin Thematics and Champion Fantasies 2024-08-22, /dev:
Midseason and Mythics 2023-04-28 — the oldest). After saving Patch 26.19 Notes:
5 saved. After removing the oldest: 4 saved. Database delta: exactly one
bookmark row added (Patch 26.19 Notes, article id 133) and one removed
('/dev: Midseason and Mythics', article id 80) for david.
"""
from verify_lib import (bound_count, check_bookmarks_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_phrase,
                        contains_phrase_loose, final_answer, navigated_to_path,
                        run_verifier)

TASK_ID = "League of Legends--14"
EMAIL = "david.k@test.com"
ADDED = (4, 133, "2026-09-22")
REMOVED = (4, 80, "2026-09-22")
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"
MIDSEASON = "/news/dev/dev-midseason-and-mythics/"
SAVED_ANCHOR = "26.19"      # the save: counts after it belong to the after-save state
REMOVED_ANCHOR = "Midseason"  # the removal: counts after it belong to the after-removal state


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_patch_2619", navigated_to_path(traj, PATCH_2619),
                f"required: {PATCH_2619}")
    judge.check("visited_midseason_article", navigated_to_path(traj, MIDSEASON),
                f"required: {MIDSEASON} (removal)")
    judge.check("visited_saved_articles_verification",
                navigated_to_path(traj, "/account/bookmarks"),
                "required: /account/bookmarks (verification after each step)")
    judge.check("visited_account", navigated_to_path(traj, "/account"),
                "required: /account")

    judge.check("answer_saved_patch_title",
                contains_phrase(answer, "League of Legends Patch 26.19 Notes"),
                "expected 'League of Legends Patch 26.19 Notes' named as saved")
    judge.check("answer_after_save_5",
                bound_count(answer, 5, SAVED_ANCHOR, [REMOVED_ANCHOR]),
                "expected 5 saved articles attached to the after-save state")
    judge.check("answer_removed_title",
                contains_phrase_loose(answer, "Midseason and Mythics"),
                "expected '/dev: Midseason and Mythics' named as removed")
    judge.check("answer_after_removal_4",
                bound_count(answer, 4, REMOVED_ANCHOR, [SAVED_ANCHOR]),
                "expected 4 saved articles attached to the after-removal state")

    check_bookmarks_delta(judge, initial_db, after_db, added=[ADDED], removed=[REMOVED])
    check_only_tables_changed(judge, initial_db, after_db, {"bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
