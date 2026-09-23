#!/usr/bin/env python3
"""Verify the Annoyed-Picard meme flow in Imgur--21."""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_all,
                        contains_phrase, final_answer, navigated_any,
                        navigated_to_path_with_params, run_verifier, table_delta)

TASK_ID = "Imgur--21"
ALICE_EMAIL = "alice.j@test.com"
ALICE_USER_ID = 990000001
MEME_TITLE = "My mirror meme"
MEME_SEO_TITLE = "my-mirror-meme"
TOP_TEXT = "WHY DID I"
BOTTOM_TEXT = "OPEN THE MEME GENERATOR"
TEMPLATE_ID = 11  # Annoyed Picard


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL, "alice_j")
    # Navigation gates: the meme generator, the new post's gallery page and the
    # profile POSTS tab.
    check_visited_path(judge, traj, "visited_meme_generator", "/meme-generator")
    # DB after-state: one post + one media row — nothing else.
    check_only_tables_changed(judge, initial_db, after_db, {"posts", "media"})
    posts_delta = table_delta(initial_db, after_db, "posts")
    judge.check("exactly_one_post_added",
                posts_delta["removed"] == [] and len(posts_delta["added"]) == 1
                and len(posts_delta["changed"]) == 0,
                f"posts delta={posts_delta!r}")
    media_delta = table_delta(initial_db, after_db, "media")
    judge.check("exactly_one_media_row_added",
                media_delta["removed"] == [] and len(media_delta["added"]) == 1
                and len(media_delta["changed"]) == 0,
                f"media delta={media_delta!r}")
    from verify_lib import row_dict
    if posts_delta["added"]:
        new_post = row_dict(initial_db, "posts", posts_delta["added"][0])
        judge.check("new_meme_post_row_matches",
                    new_post.get("title") == MEME_TITLE
                    and new_post.get("seo_title") == MEME_SEO_TITLE
                    and str(new_post.get("id", "")).startswith("m")
                    and str(new_post.get("author_id")) == str(ALICE_USER_ID),
                    f"new meme post row={new_post!r}")
        judge.check("visited_new_meme_gallery",
                    navigated_any(traj, [f"/gallery/{MEME_SEO_TITLE}-{new_post.get('id')}",
                                         f"/gallery/{new_post.get('id')}"]),
                    "required the new meme's gallery URL in the trajectory")
        judge.check("answer_contains_new_meme_url",
                    contains_phrase(answer, f"{MEME_SEO_TITLE}-{new_post.get('id')}")
                    or contains_phrase(answer, f"gallery/{new_post.get('id')}"),
                    "expected the new meme's URL in the answer")
        if media_delta["added"]:
            new_media = row_dict(initial_db, "media", media_delta["added"][0])
            judge.check("meme_media_row_matches",
                        str(new_media.get("post_id")) == str(new_post.get("id"))
                        and str(new_media.get("feed_path", "")).startswith("instance/uploads/meme_"),
                        f"meme media row={new_media!r}")
    judge.check("visited_profile_posts_tab",
                navigated_to_path_with_params(traj, "/user/alice_j", {"tab": "posts"}),
                "required /user/alice_j?tab=posts")
    judge.check("answer_reports_title_on_posts_tab",
                contains_all(answer, [MEME_TITLE]),
                f"expected the title {MEME_TITLE!r} as shown on the POSTS tab")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
