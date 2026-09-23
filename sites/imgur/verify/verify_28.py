#!/usr/bin/env python3
"""Verify the featured-tag-tile report in Imgur--28."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, phrases_in_order,
                        run_verifier)

TASK_ID = "Imgur--28"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_homepage_tiles", "/")
    # Frozen ground truth (seed DB, tags rows): the FEATURED tile is 'woodworking'
    # (20,139 Posts, rendered 'Woodworking'); the first non-featured tile after it is
    # 'Funny' (2,303,068 Posts).
    judge.check("answer_featured_tile_name", contains_phrase(answer, "Woodworking"),
                "expected the featured tile 'Woodworking'")
    judge.check("answer_featured_tile_post_count", contains_count(answer, 20139),
                "expected 20,139 posts on the featured tile")
    judge.check("answer_featured_mark", contains_phrase(answer, "FEATURED"),
                "expected the FEATURED mark")
    judge.check("answer_first_nonfeatured_tile", contains_phrase(answer, "Funny"),
                "expected the first non-featured tile 'Funny'")
    judge.check("answer_tiles_in_feed_order",
                phrases_in_order(answer, ["Woodworking", "Funny"]),
                "the featured tile must be named before the non-featured tile")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
