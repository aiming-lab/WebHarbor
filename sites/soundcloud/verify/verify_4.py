#!/usr/bin/env python3
"""Verify SoundCloud--4.

You're building a playlist of longer Rod Wave songs. Search for 'Rod Wave', open his profile from the People tab, and report his city and exact follower count. From his Popular tracks tab, open his five most-played tracks and report each one's title, exact play count, and duration. Which of the five run longer than three minutes? Also report the label shown in the Details panel of his most-played track, and the username and 'at' timestamp of the newest comment on it.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--4"

CITY = "St. Petersburg"
FOLLOWERS = 1482902
# (title, exact plays, duration label, page path) — frozen from the seed Popular tab.
POPULAR5 = [
    ("Piece Of Your Love", 1672102, "3:46", "/rodwave/piece-of-your-love"),
    ("Hustle", 1205740, "2:19", "/rodwave/hustle"),
    ("Dope Girl", 803703, "2:12", "/rodwave/dope-girl"),
    ("TP", 653691, "2:48", "/rodwave/tp"),
    ("Kiss Me Interlude", 572927, "3:05", "/rodwave/kiss-me-interlude"),
]
# the two popular tracks longer than three minutes
OVER_3MIN = ["Piece Of Your Love", "Kiss Me Interlude"]
TOP_LABEL = "Alamo"
NEWEST_COMMENT = ("jaylan hutchins", "1:53")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_search", r"/search\?q=[Rr]od\+[Ww]ave")
    check_visited_path(judge, traj, "visited_profile", r"/rodwave/?(\?|$)")
    check_answer_phrase(judge, answer, "city", CITY)
    check_answer_number(judge, answer, "followers", FOLLOWERS, "Rod Wave exact followers")
    check_visited_path(judge, traj, "visited_popular_tab", r"/rodwave\?tab=popular")
    for i, (title, plays, dur, path) in enumerate(POPULAR5, 1):
        check_visited_path(judge, traj, f"visited_pop{i}", path + r"/?(\?|$)")
        check_answer_phrase(judge, answer, f"pop{i}_title", title)
        check_answer_number(judge, answer, f"pop{i}_plays", plays, f"popular #{i} exact plays")
        judge.check(f"pop{i}_duration", dur in answer,
                    f"answer must report popular #{i} duration {dur}")
    judge.check("over_three_minutes",
                all(t in answer for t in OVER_3MIN)
                and "longer than three minutes" in answer.casefold().replace("run ", " ")
                or all(t in answer for t in OVER_3MIN),
                "answer must name the tracks longer than three minutes")
    check_answer_phrase(judge, answer, "top_label", TOP_LABEL)
    check_answer_phrase(judge, answer, "newest_commenter", NEWEST_COMMENT[0])
    judge.check("newest_comment_at",
                NEWEST_COMMENT[1] in answer,
                f"answer must report the newest comment's 'at' timestamp {NEWEST_COMMENT[1]}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
