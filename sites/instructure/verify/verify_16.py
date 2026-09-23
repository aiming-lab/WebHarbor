#!/usr/bin/env python3
"""Verify Instructure--16: sign in (carol) -> Product Overviews hub Org Type=
Higher Education filter -> Canvas Career for Higher Education save (plus the
education-businesses overview) -> Saved Resources confirmation."""

from verify_lib import (check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed,
                        contains_phrase, delta_dicts, final_answer,
                        navigated_listing_with_filter, resource_id_by_slug,
                        run_verifier, table_delta, user_id_by_email)

TASK_ID = "Instructure--16"

HIGHER_ED = "canvas-career-higher-education"
EDU_BUSINESSES = "canvas-career-education-businesses"
CAROL = "carol.d@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, CAROL)
    # Navigation gates: the filtered hub, both overview details, the saved list.
    judge.check("visited_overviews_with_higher_ed_filter",
                navigated_listing_with_filter(traj, "product-overviews", "org",
                                              "Higher Education"),
                "hub=/resources/product-overviews filter org=Higher Education")
    check_visited_path(judge, traj, "visited_higher_ed_overview",
                       "/resources/product-overviews/" + HIGHER_ED)
    check_visited_path(judge, traj, "visited_edu_businesses_overview",
                       "/resources/product-overviews/" + EDU_BUSINESSES)
    check_visited_path(judge, traj, "visited_saved_resources", "/account/saved")
    # Frozen ground truth (seed intro + app.py flash): the higher-education
    # overview promises to "Empower students to move from classroom to
    # career"; each save flashes "Saved '<title>' to your account."
    judge.check("answer_classroom_to_career",
                contains_phrase(answer, "classroom to career"),
                "expected the 'from classroom to career' promise reported")
    judge.check("answer_save_confirmation",
                contains_phrase(answer, "to your account"),
                "expected the save confirmations")
    # DB delta: exactly two saved rows for carol (both Canvas Career overviews).
    saved_delta = table_delta(initial_db, after_db, "saved_resources")
    saved_added = delta_dicts(after_db, "saved_resources", saved_delta)
    carol_id = user_id_by_email(initial_db, CAROL)
    he_id = resource_id_by_slug(initial_db, HIGHER_ED)
    eb_id = resource_id_by_slug(initial_db, EDU_BUSINESSES)
    judge.check("db_saved_two_overviews",
                len(saved_added) == 2 and not saved_delta["removed"]
                and not saved_delta["changed"]
                and sorted((r["user_id"], r["resource_id"]) for r in saved_added)
                == sorted([(carol_id, he_id), (carol_id, eb_id)]),
                "expected exactly two new saved rows for the two overviews")
    check_only_tables_changed(judge, initial_db, after_db, ["saved_resources"])


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
