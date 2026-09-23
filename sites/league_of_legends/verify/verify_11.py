#!/usr/bin/env python3
"""Verify League of Legends--11: most recent patch notes article."""
from verify_lib import (check_read_only, check_trajectory_identity, contains_iso_date,
                        contains_phrase, final_answer, navigated_patch_notes, run_verifier)

TASK_ID = "League of Legends--11"
# Frozen ground truth (seed DB, is_patch_note=1 ordered by publish_date desc):
# League of Legends Patch 26.19 Notes, 2026-09-22.
TITLE = "League of Legends Patch 26.19 Notes"
DATE = "2026-09-22"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_patch_notes_listing", navigated_patch_notes(traj),
                "required: /patch-notes/")
    judge.check("answer_title", contains_phrase(answer, TITLE), f"expected {TITLE!r}")
    judge.check("answer_date", contains_iso_date(answer, DATE),
                f"expected the publish date {DATE}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
