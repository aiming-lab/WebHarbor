#!/usr/bin/env python3
"""Verify Instructure--15."""

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, check_only_tables_changed, contains_all, contains_any,
                        contains_count, contains_date_phrase, contains_klabel, contains_money,
                        contains_phrase, entered_identity, final_answer, navigated_listing_with_filter,
                        navigated_search_with, navigated_to_path, navigated_to_path_any,
                        navigated_to_path_with_params, run_verifier)

TASK_ID = "Instructure--15"


EDUCACION_TITLE = ("Para evitar que la IA se convierta en una herramienta dañina "
                   "hay que aprender a usarla")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the newsroom. The Region filter gained a Filter Results button
    # in the fix round (F5), so /news?region=Europe is the natural post-fix surface;
    # a plain /news visit (the pre-fix reading) also satisfies the gate.
    judge.check("visited_newsroom",
                navigated_to_path(traj, "/news"),
                "required: /news (region filter optional — the control is inert in the "
                "mirror)")
    # Frozen ground truth (seed DB, news_items): the Educacion 3.0 article "Para evitar
    # que la IA se convierta en una herramienta dañina hay que aprender a usarla"
    # (October 28, 2024), spokesperson Ryan Lufkin.
    judge.check("answer_article_title", contains_all(answer, ["Para evitar que la IA",
                                                              "aprender a usarla"]),
                "expected the Educacion 3.0 article title")
    judge.check("answer_outlet", contains_phrase(answer, "Educacion 3.0"),
                "expected the outlet Educacion 3.0")
    judge.check("answer_spokesperson", contains_phrase(answer, "Ryan Lufkin"),
                "expected the spokesperson Ryan Lufkin")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
