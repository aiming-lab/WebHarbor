#!/usr/bin/env python3
"""Verify alice follows GMBrewChess and reports the settings following count in Chess.com--8."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--8"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: login, the target member profile and the settings page.
    check_signed_in_as(judge, traj, "alice.j@test.com", "alice_j")
    judge.check("visited_gmbrew_profile",
                any(u.casefold().rstrip("/").endswith("/member/gmbrewchess")
                    for u in __import__("verify_lib").site_urls(traj)),
                "required_path=/member/GMBrewChess (case-insensitive)")
    check_visited_path(judge, traj, "visited_settings", "/settings")
    # Frozen ground truth: alice follows 3 seed members (Firouzja2003, Hikaru, MagnusCarlsen);
    # after following GMBrewChess the settings page shows Following 4.
    judge.check("answer_following_count", contains_count(answer, 4), "expected 4 following")
    # DB after-state: exactly one follows row added (alice -> GMBrewChess); nothing else changes.
    from verify_lib import check_only_tables_changed
    delta = table_delta(initial_db, after_db, "follows")
    added_ok = len(delta["added"]) == 1 and delta["added"][0][1] == 1176 and delta["added"][0][2] == 279
    judge.check("follows_exact_delta",
                added_ok and not delta["removed"] and not delta["changed"],
                f"delta={delta!r} (expected exactly +1 row follower_id=1176 -> followed_id=279)")
    check_only_tables_changed(judge, initial_db, after_db, {"follows"})



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
