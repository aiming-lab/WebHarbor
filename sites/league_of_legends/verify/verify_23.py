#!/usr/bin/env python3
"""Verify League of Legends--23: david bookmarks the Patch 26.19 article (stateful)."""
from verify_lib import (PATCH_2619_ARTICLE_ID, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count, final_answer,
                        navigated_article, navigated_to_path, run_verifier, table_delta,
                        user_by_email)

TASK_ID = "League of Legends--23"
EMAIL = "david.k@test.com"
# david_k seeds 4 bookmarks; after saving the Patch 26.19 Notes article it has 5.
ARTICLE = ("game-updates", "league-of-legends-patch-26-19-notes")
EXPECTED_TOTAL = 5


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_patch_2619_article", navigated_article(traj, *ARTICLE),
                "required: the Patch 26.19 Notes article page (the Save control lives there)")
    judge.check("answer_total_after_save", contains_count(answer, EXPECTED_TOTAL),
                f"expected {EXPECTED_TOTAL} saved articles after the save")
    # state: exactly one bookmark_articles row added — (david, patch 26.19) — nothing else
    user = user_by_email(after_db, EMAIL)
    judge.check("david_exists_after", user is not None, "david_k must still exist")
    david_id = user["id"]
    delta = table_delta(initial_db, after_db, "bookmark_articles")
    judge.check("bookmark_added_exactly_one_row",
                len(delta["added"]) == 1 and len(delta["removed"]) == 0
                and len(delta["changed"]) == 0,
                f"expected exactly one added bookmark row; delta={delta!r}")
    if delta["added"]:
        row = delta["added"][0]
        judge.check("bookmark_added_is_david_2619",
                   row[1] == david_id and row[2] == PATCH_2619_ARTICLE_ID,
                   f"expected (user_id={david_id}, article_id={PATCH_2619_ARTICLE_ID}); got {row!r}")
    check_only_tables_changed(judge, initial_db, after_db, {"bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
