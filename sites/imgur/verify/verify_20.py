#!/usr/bin/env python3
"""Verify the register + upload-by-URL flow in Imgur--20."""


from verify_lib import (Judge, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_all, contains_phrase, entered_identity,
                        final_answer, navigated_any, navigated_to_path_with_params, posts_of,
                        run_verifier, table_delta)

TASK_ID = "Imgur--20"
NEW_USERNAME = "mirrorfan2026"
NEW_EMAIL = "mirrorfan2026@test.com"
NEW_TITLE = "My first mirror post"
NEW_SEO_TITLE = "my-first-mirror-post"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: registration form, upload page, the new post's gallery page and
    # the new profile's POSTS tab.
    check_visited_path(judge, traj, "visited_register_page", "/register")
    check_visited_path(judge, traj, "visited_upload_page", "/upload")
    judge.check("entered_new_account_identity", entered_identity(traj, NEW_USERNAME, NEW_EMAIL),
                f"expected {NEW_USERNAME!r} or {NEW_EMAIL!r} in an input step")
    # DB after-state: one user, one post, one media row — nothing else.
    check_only_tables_changed(judge, initial_db, after_db, {"users", "posts", "media"})
    users_delta = table_delta(initial_db, after_db, "users")
    judge.check("exactly_one_user_added",
                users_delta["removed"] == [] and len(users_delta["added"]) == 1
                and len(users_delta["changed"]) == 0,
                f"users delta={users_delta!r}")
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
    new_user = new_post = None
    if users_delta["added"]:
        new_user = row_dict(initial_db, "users", users_delta["added"][0])
        judge.check("new_user_row_matches",
                    new_user.get("username") == NEW_USERNAME
                    and str(new_user.get("email", "")).lower() == NEW_EMAIL
                    and int(new_user.get("is_benchmark") or 0) == 0,
                    f"new user row={new_user!r}")
    if posts_delta["added"]:
        new_post = row_dict(initial_db, "posts", posts_delta["added"][0])
        judge.check("new_post_row_matches",
                    new_post.get("title") == NEW_TITLE
                    and new_post.get("seo_title") == NEW_SEO_TITLE
                    and str(new_post.get("id", "")).startswith("u")
                    and int(new_post.get("in_user_sub") or 0) == 1,
                    f"new post row={new_post!r}")
        judge.check("new_post_belongs_to_new_user",
                   new_user is not None and str(new_post.get("author_id")) == str(new_user.get("id")),
                   "the uploaded post must be authored by the new account")
        judge.check("visited_new_post_gallery",
                    navigated_any(traj, [f"/gallery/{NEW_SEO_TITLE}-{new_post.get('id')}",
                                         f"/gallery/{new_post.get('id')}"]),
                    "required the new post's gallery URL in the trajectory")
        judge.check("answer_contains_new_post_url",
                    contains_phrase(answer, f"{NEW_SEO_TITLE}-{new_post.get('id')}")
                    or contains_phrase(answer, f"gallery/{new_post.get('id')}"),
                    "expected the new post's URL in the answer")
    judge.check("visited_new_profile_posts_tab",
                navigated_to_path_with_params(traj, f"/user/{NEW_USERNAME}", {"tab": "posts"}),
                f"required /user/{NEW_USERNAME}?tab=posts")
    judge.check("answer_reports_title_on_posts_tab",
                contains_all(answer, [NEW_TITLE]),
                f"expected the title {NEW_TITLE!r} as shown on the POSTS tab")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
