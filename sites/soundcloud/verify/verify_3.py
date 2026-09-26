#!/usr/bin/env python3
"""Verify SoundCloud--3.

Sign in as Carol (carol.d@test.com / TestPass123!). Search for Miley Cyrus, open her profile from the People tab, and report her exact follower count, how many tracks she's uploaded, and how many people she follows. Then find her most-played track on the US 'New & Hot' chart this week, open its page, like it, and report its title plus the total comments shown in the comments heading and the label from its Details panel. Also report the track's position on the US Pop chart.

Fixture note (reviewer, re-review 2026-09-26): the task now signs in as Carol,
whose seeded likes are six dance/house tracks and contain no Miley track, so
"like it" is a clean +1 like on 'Bass Persuades' (tracks.likes 6,770 -> 6,771,
one new likes row for user 3). The old Alice fixture pre-liked the target
(review finding #2) and is gone.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--3"

PROFILE_FOLLOWERS = 1517357
PROFILE_TRACKS = 345
PROFILE_FOLLOWINGS = 0
TRACK_TITLE = "Bass Persuades"
TRACK_ID = 2393437119          # 'Bass Persuades' by mileycyrus
TRACK_PAGE = "/mileycyrus/bass-persuades"
COMMENTS = 120
LABEL = "Atlantic Records"
SEED_LIKES = 6770
POP_POSITION = 2


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_search", r"/search\?q=[Mm]iley\+[Cc]yrus")
    check_visited_path(judge, traj, "visited_profile", r"/mileycyrus/?(\?|$)")
    check_visited_path(judge, traj, "visited_new_hot_chart", r"/music-charts-us/sets/new-hot")
    check_visited_path(judge, traj, "visited_track_page", TRACK_PAGE)
    check_answer_number(judge, answer, "profile_followers", PROFILE_FOLLOWERS,
                        "Miley exact followers")
    check_answer_number(judge, answer, "profile_tracks", PROFILE_TRACKS,
                        "Miley tracks uploaded")
    check_answer_number(judge, answer, "profile_followings", PROFILE_FOLLOWINGS,
                        "people Miley follows")
    check_answer_phrase(judge, answer, "track_title", TRACK_TITLE)
    check_answer_number(judge, answer, "comments_count", COMMENTS, "comments heading count")
    check_answer_phrase(judge, answer, "details_label", LABEL)
    check_answer_number(judge, answer, "pop_position", POP_POSITION, "US Pop chart position")
    check_visited_path(judge, traj, "visited_pop_chart", r"/music-charts-us/sets/pop")

    # DB after-state: exactly one new like row for Carol on the target track,
    # with the tracks.likes counter bumped 6,770 -> 6,771, and nothing else.
    check_only_tables_changed(judge, initial_db, after_db, allowed={"likes", "tracks"})
    a, r, c = table_diff(initial_db, after_db, "likes")
    judge.check("one_like_added",
                len(a) == 1 and len(r) == 0,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("like_row_is_carol_on_target",
                    row["user_id"] == 3 and row["track_id"] == TRACK_ID,
                    f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("tracks_only_like_counter",
                len(a) == 0 and len(r) == 0 and len(c) == 1,
                f"added={list(a)[:2]} removed={list(r)[:2]} changed={list(c)[:2]}")
    for _k, (old, new) in c.items():
        judge.check("like_counter_bumped",
                    old["id"] == TRACK_ID and new["likes"] == SEED_LIKES + 1,
                    f"likes {old['likes']} -> {new['likes']} on track {old['id']}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
