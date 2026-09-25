#!/usr/bin/env python3
"""Verify Instructure--2: sign in (carol) -> Blogs AI topic filter -> 'Finding
the Sensible Middle' -> site search -> 'No Country for Fast Answers' podcast
save -> Saved Resources confirmation."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_phrase, final_answer, navigated_listing_with_filter,
                        navigated_to_path, resource_id_by_slug, run_verifier,
                        single_added_row, table_delta, user_id_by_email,
                        delta_dicts)

TASK_ID = "Instructure--2"

BLOG = ("finding-sensible-middle-ai-literacy-cognitive-offloading-"
        "and-student-voice-classroom")
PODCAST = "no-country-fast-answers-safeguarding-critical-human-logic-world-instant-ai"
CAROL = "carol.d@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL)
    # Navigation gates: AI-filtered Blogs hub, the blog detail, a site search,
    # the podcast detail, and the saved list.
    judge.check("visited_blogs_with_ai_filter",
                navigated_listing_with_filter(traj, "blog", "topic",
                                              "Artificial Intelligence"),
                "hub=/resources/blog filter topic=Artificial Intelligence")
    check_visited_path(judge, traj, "visited_sensible_middle_post",
                       "/resources/blog/" + BLOG)
    judge.check("visited_site_search", navigated_to_path(traj, "/search"),
                "required_path=/search")
    check_visited_path(judge, traj, "visited_podcast",
                       "/resources/podcast/" + PODCAST)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed): 'Finding the Sensible Middle' is by Marianne
    # Chrisos (Aug 25, 2026) and prioritizes human connection over technology;
    # the podcast is 'No Country for Fast Answers' (July 28, 2026).
    judge.check("answer_blog_author", contains_phrase(answer, "Marianne Chrisos"),
                "expected the blog author Marianne Chrisos")
    judge.check("answer_human_connection",
                contains_phrase(answer, "human connection"),
                "expected 'human connection' as the element prioritized over technology")
    judge.check("answer_podcast_title",
                contains_phrase(answer, "No Country for Fast Answers"),
                "expected the saved podcast title")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmation")
    # DB delta: one saved_resources row linking carol to the podcast.
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    carol_id = user_id_by_email(initial_db, CAROL)
    podcast_id = resource_id_by_slug(initial_db, PODCAST)
    judge.check("db_saved_podcast_row",
                len(saved_added) == 1 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and saved_added[0]["user_id"] == carol_id
                and saved_added[0]["resource_id"] == podcast_id,
                "expected exactly one new saved row: carol -> the podcast")
    check_only_tables_changed(judge, initial_db, after_db, ["saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
