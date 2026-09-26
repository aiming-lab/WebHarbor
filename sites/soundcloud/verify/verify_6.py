#!/usr/bin/env python3
"""Verify SoundCloud--6.

Sign in as Carol (carol.d@test.com / TestPass123!). Among her liked tracks that are House tracks, she wants to drop the least-played one: unlike it, then follow its artist. Report the track title you unliked, the artist's name, and the artist's follower count shown right after you follow them.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--6"

TRACK_ID = 2362598162            # 'Kolter - Hey Everybody (Radio Edit)' (House)
TRACK_TITLE = "Kolter - Hey Everybody"
ARTIST = "Kolter"
ARTIST_ID = 24114332             # koltercologne
SEED_LIKES = 28409
SEED_FOLLOWERS = 105235


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_likes", r"/you/likes|/you/library")
    check_visited_path(judge, traj, "visited_track_page", r"/koltercologne/")
    check_answer_phrase(judge, answer, "unliked_title", TRACK_TITLE)
    check_answer_phrase(judge, answer, "artist_name", ARTIST)
    check_answer_number(judge, answer, "followers_after_follow", 105236,
                        "follower count right after following")

    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"likes", "tracks", "follows", "artists"})
    a, r, _ = table_diff(initial_db, after_db, "likes")
    judge.check("one_like_removed", len(a) == 0 and len(r) == 1,
                f"removed={list(r.values())!r}")
    if r:
        row = list(r.values())[0]
        judge.check("removed_like_row", row["user_id"] == 3 and row["track_id"] == TRACK_ID,
                    f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("tracks_only_like_counter", len(c) == 1 and not a and not r,
                f"changed={list(c)[:2]}")
    for _k, (old, new) in c.items():
        judge.check("like_counter_dropped",
                   old["id"] == TRACK_ID and new["likes"] == SEED_LIKES - 1,
                   f"likes {old['likes']} -> {new['likes']}")
    a, r, _ = table_diff(initial_db, after_db, "follows")
    judge.check("one_follow_added", len(a) == 1 and not r, f"added={list(a.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("follow_row", row["user_id"] == 3 and row["artist_id"] == ARTIST_ID,
                    f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "artists")
    judge.check("artists_only_follower_counter", len(c) == 1 and not a and not r,
                f"changed={list(c)[:2]}")
    for _k, (old, new) in c.items():
        judge.check("follower_counter_bumped",
                   old["id"] == ARTIST_ID and new["followers"] == SEED_FOLLOWERS + 1,
                   f"followers {old['followers']} -> {new['followers']}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
