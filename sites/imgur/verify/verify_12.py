#!/usr/bin/env python3
"""Verify the Hobbit album-card report in Imgur--12."""

import re

from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, norm, run_verifier)

TASK_ID = "Imgur--12"
GALLERY_PATH = "/gallery/hobbit-lord-of-rings-artworks-DHQdlLJ"
ALBUM_IMAGES = 25


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: the card lives on the Most Viral homepage feed; the score box and
    # author line render only on the gallery page.
    check_visited_path(judge, traj, "visited_homepage_feed", "/")
    check_visited_path(judge, traj, "visited_hobbit_gallery", GALLERY_PATH)
    # Frozen ground truth (seed DB, posts row DHQdlLJ): image_count 25 (card badge 1/25),
    # point_count 195, author username Ngugi.
    judge.check("answer_album_badge",
                bool(re.search(rf"(?<![\d/])1\s*/\s*{ALBUM_IMAGES}(?!\d)", norm(answer))),
                "expected the 1/25 album badge from the card")
    judge.check("answer_album_score", contains_count(answer, 195),
                "expected 195 in the vote box")
    judge.check("answer_album_author", contains_phrase(answer, "Ngugi"),
                "expected the author username 'Ngugi'")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
