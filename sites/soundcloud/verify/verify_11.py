#!/usr/bin/env python3
"""Verify SoundCloud--11.

Sign in as Alice (alice.j@test.com / TestPass123!). Search for the artist Kaskade on the People tab, open their profile and report their city and follower count, then follow them. Finally, find their most-played track on the profile and add it to a brand-new playlist named 'Sunset Sets'. Report the most-played track's title too.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--11"

ARTIST_ID = 1271874               # kaskade
SEED_FOLLOWERS = 1501229
TOP_TITLE = "A Little Bit"
TOP_TRACK_ID = 253566 // 1000     # placeholder, corrected below from DB
TOP_TRACK_ID = None               # resolved dynamically below
PLAYLIST_TITLE = "Sunset Sets"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_search", r"/search\?q=[Kk]askade")
    check_visited_path(judge, traj, "visited_profile", r"/kaskade")
    check_answer_phrase(judge, answer, "city", "West Coast")
    check_answer_number(judge, answer, "followers", SEED_FOLLOWERS, "Kaskade followers")
    check_answer_phrase(judge, answer, "top_track", TOP_TITLE)
    check_answer_phrase(judge, answer, "playlist_name", PLAYLIST_TITLE)

    # resolve the most-played kaskade track id from the seed DB
    top_id = initial_db.execute(
        "SELECT id FROM tracks WHERE artist_id=? ORDER BY plays DESC LIMIT 1",
        (ARTIST_ID,)).fetchone()[0]

    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"follows", "artists", "user_playlists",
                                       "user_playlist_tracks"})
    a, r, _ = table_diff(initial_db, after_db, "follows")
    judge.check("one_follow_added", len(a) == 1 and not r, f"added={list(a.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("follow_row", row["user_id"] == 1 and row["artist_id"] == ARTIST_ID,
                    f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "artists")
    for _k, (old, new) in c.items():
        judge.check("follower_counter_bumped",
                   old["id"] == ARTIST_ID and new["followers"] == SEED_FOLLOWERS + 1,
                   f"followers {old['followers']} -> {new['followers']}")
    a, r, _ = table_diff(initial_db, after_db, "user_playlists")
    judge.check("one_playlist_added", len(a) == 1 and not r,
                f"added={list(a.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("playlist_row", row["user_id"] == 1 and row["title"] == PLAYLIST_TITLE,
                    f"row={dict(row)}")
    a, r, _ = table_diff(initial_db, after_db, "user_playlist_tracks")
    judge.check("one_entry_added", len(a) == 1 and not r, f"added={list(a.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("entry_is_top_track", row["track_id"] == top_id,
                    f"row={dict(row)} expected track {top_id}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
