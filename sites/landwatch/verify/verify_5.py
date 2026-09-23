#!/usr/bin/env python3
"""Verify LandWatch--5 — 'Tucked into the Hill Country' agent contact panel + gallery.

Ground truth (frozen seed): listing agent Jordan Shipley of Shipley Ranches,
phone (512) 798-4161, and the gallery lists 90 pictures.
"""
import re

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, normalize_text, run_verifier)

TASK_ID = "LandWatch--5"
DETAIL_PATH = "/burnet-county-texas-farms-and-ranches-for-sale/pid/428212638"


def _contains_phone(answer):
    return bool(re.search(r"512[\s.)-]*798[\s-]*4161", normalize_text(answer)))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_tucked_detail", DETAIL_PATH)
    judge.check("answer_agent_name", contains_phrase(answer, "Jordan Shipley"),
                "expected the listing agent Jordan Shipley")
    judge.check("answer_brokerage", contains_phrase(answer, "Shipley Ranches"),
                "expected the brokerage Shipley Ranches")
    judge.check("answer_phone", _contains_phone(answer),
                "expected the contact-panel phone (512) 798-4161")
    judge.check("answer_gallery_pictures", contains_count(answer, 90),
                "expected the gallery to list 90 pictures")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
