#!/usr/bin/env python3
"""Verify SoundCloud--5.

Sign in as Bob (bob.c@test.com / TestPass123!). He's building a workout playlist: create a new playlist called 'Heavy Bag Rounds' and add this week's #1 and #2 tracks from the US Hip Hop chart to it. Report the playlist's final track count and the two track titles you added.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--5"

T1_ID, T2_ID = 2390382459, 2397840264      # Is Dat Right? / Backwards
T1_TITLE, T2_TITLE = "Is Dat Right?", "Backwards"
PLAYLIST_TITLE = "Heavy Bag Rounds"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_hiphop_chart", r"/music-charts-us/sets/hip-hop")
    check_visited_path(judge, traj, "visited_track1", r"/nardo-wick/is-dat-right")
    check_visited_path(judge, traj, "visited_track2", r"/quavoofficial/backwards")
    check_answer_phrase(judge, answer, "track1", T1_TITLE)
    check_answer_phrase(judge, answer, "track2", T2_TITLE)
    check_answer_number(judge, answer, "playlist_count", 2, "final track count")

    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"user_playlists", "user_playlist_tracks"})
    added, removed, _ = table_diff(initial_db, after_db, "user_playlists")
    judge.check("one_playlist_added", len(added) == 1 and len(removed) == 0,
                f"added={list(added.values())!r} removed={list(removed.values())!r}")
    if added:
        row = list(added.values())[0]
        judge.check("playlist_row", row["user_id"] == 2 and row["title"] == PLAYLIST_TITLE,
                    f"row={dict(row)}")
    a, r, _ = table_diff(initial_db, after_db, "user_playlist_tracks")
    judge.check("two_entries_added", len(a) == 2 and len(r) == 0,
                f"added={[(e['playlist_id'], e['track_id'], e['position']) for e in a.values()]!r}")
    judge.check("entries_are_the_two_tracks",
                sorted(e["track_id"] for e in a.values()) == [T1_ID, T2_ID],
                f"track ids={[e['track_id'] for e in a.values()]}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
