#!/usr/bin/env python3
"""Verify the PSA comment flow in Imgur--8."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, final_answer, run_verifier, table_delta)

TASK_ID = "Imgur--8"
CAROL_EMAIL = "carol.d@test.com"
CAROL_USER_ID = 990000003
GALLERY_PATH = "/gallery/psa-Lpeg54z"
POST_ID = "Lpeg54z"
COMMENT_TEXT = "Mirror test comment 2026"
# Frozen ground truth (seed DB): PSA (Lpeg54z) carries comment_count 40 -> 41.


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL_EMAIL, "carol_d")
    check_visited_path(judge, traj, "visited_psa_gallery", GALLERY_PATH)
    # DB after-state: one comment added by carol on Lpeg54z + that post's
    # comment_count bumped 40 -> 41; nothing else changes.
    check_only_tables_changed(judge, initial_db, after_db, {"comments", "posts"})
    delta = table_delta(initial_db, after_db, "comments")
    judge.check("exactly_one_comment_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"comments delta={delta!r}")
    from verify_lib import row_dict, table_columns
    if delta["added"]:
        added = row_dict(initial_db, "comments", delta["added"][0])
        judge.check("comment_row_matches_expected",
                    str(added.get("author_id")) == str(CAROL_USER_ID)
                    and str(added.get("post_id")) == POST_ID
                    and added.get("parent_id") is None
                    and added.get("text") == COMMENT_TEXT,
                    f"added comment row={added!r}")
    posts_delta = table_delta(initial_db, after_db, "posts")
    changed_ids = [row[0] for row, _ in posts_delta["changed"]]
    judge.check("exactly_psa_comment_count_bumped",
                posts_delta["added"] == [] and posts_delta["removed"] == []
                and len(posts_delta["changed"]) == 1 and changed_ids == [POST_ID],
                f"posts delta={posts_delta!r}")
    if posts_delta["changed"]:
        before = row_dict(initial_db, "posts", posts_delta["changed"][0][0])
        after = row_dict(initial_db, "posts", posts_delta["changed"][0][1])
        judge.check("psa_comment_count_40_to_41",
                    before.get("comment_count") == 40 and after.get("comment_count") == 41,
                    f"comment_count {before.get('comment_count')} -> {after.get('comment_count')}")
    judge.check("answer_comments_header_after_post", contains_count(answer, 41),
                "expected 41 COMMENTS in the header after posting")
    judge.check("answer_mentions_comment_text", contains_phrase(answer, COMMENT_TEXT),
                "expected the posted comment text in the answer")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
