#!/usr/bin/env python3
"""Verify Instructure--17: sign in (david) -> Videos hub Canvas Career demo ->
transcript -> save -> Saved Resources confirmation -> footer newsletter
subscription (david.k@test.com)."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_any, contains_phrase, final_answer,
                        navigated_listing_with_filter, resource_id_by_slug,
                        run_verifier, single_added_row, table_delta,
                        user_id_by_email, delta_dicts)

TASK_ID = "Instructure--17"

VIDEO = "canvas-career-demo-build-skills-based-programs-you-can-measure"
DAVID = "david.k@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, DAVID)
    # Navigation gates: the Business-filtered Videos hub, the demo detail, the saved list.
    judge.check("visited_videos_with_business_filter",
                navigated_listing_with_filter(traj, "videos", "org", "Business"),
                "hub=/resources/videos filter org=Business")
    check_visited_path(judge, traj, "visited_video_detail",
                       "/resources/videos/" + VIDEO)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed intro + app.py flash): the demo says Canvas
    # Career "empowers L&D teams to align learning to real roles, create
    # content faster, and measure training impact at scale"; save flash
    # "Saved '<title>' to your account."; newsletter flash "You're on the
    # list! Watch your inbox for the latest from the learnosphere."
    judge.check("answer_ld_capability",
                contains_any(answer, ["align learning to real roles",
                                      "create content faster",
                                      "measure training impact"]),
                "expected at least one L&D capability from the demo page")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    judge.check("answer_newsletter_confirmation",
                contains_phrase(answer, "on the list"),
                "expected the newsletter subscription confirmation")
    # DB delta: one saved row (david -> the video) + one newsletter row.
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    david_id = user_id_by_email(initial_db, DAVID)
    video_id = resource_id_by_slug(initial_db, VIDEO)
    judge.check("db_saved_video_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == david_id
                and saved_added[0]["resource_id"] == video_id,
                "expected exactly one new saved row: david -> the demo video")
    ok_news, news_row = single_added_row(initial_db, after_db, "newsletter_subscribers")
    judge.check("db_newsletter_row",
                ok_news and news_row.get("email") == DAVID,
                "expected exactly one newsletter row for david.k@test.com")
    check_only_tables_changed(judge, initial_db, after_db,
                              ["saved_resources", "newsletter_subscribers"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
