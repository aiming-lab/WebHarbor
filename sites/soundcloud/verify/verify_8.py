#!/usr/bin/env python3
"""Verify SoundCloud--8.

Sign in as Alice (alice.j@test.com / TestPass123!) and upload a new track titled 'Midnight Sketch', genre Pop, 3 minutes 45 seconds long, with tags 'demo pop'. Report the new track's page URL and the duration shown on its page. Then add it to her existing playlist 'Late Night Drive' with the ＋ button, open that playlist from her Library's Playlists tab, and report its final track count and where 'Midnight Sketch' sits in it.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--8"

TITLE = "Midnight Sketch"
GENRE = "Pop"
DURATION_MS = 225000          # 3:45
TAGS = "demo pop"
SLUG = "midnight-sketch"
PATH = "/alice_j/midnight-sketch"
DURATION_LABEL = "3:45"
PLAYLIST_ID = 1               # Late Night Drive
PLAYLIST_TITLE = "Late Night Drive"
FINAL_COUNT = 4
POSITION = 4


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_upload", r"/upload")
    check_visited_path(judge, traj, "visited_new_track_page", PATH)
    check_visited_path(judge, traj, "visited_library_playlists", r"/you/playlists")
    check_visited_path(judge, traj, "visited_playlist_page", r"/you/playlist/1")
    import re as _re
    judge.check("answer_has_url",
                bool(_re.search(r"/alice_j/midnight-sketch(?![a-z0-9-])", answer)),
                f"answer must report the new track URL {PATH} exactly")
    check_answer_phrase(judge, answer, "title", TITLE)
    judge.check("answer_has_duration", DURATION_LABEL in answer,
                f"answer must report the duration shown on the page ({DURATION_LABEL})")
    check_answer_phrase(judge, answer, "playlist_name", PLAYLIST_TITLE)
    check_answer_number(judge, answer, "final_count", FINAL_COUNT,
                        "final track count of Late Night Drive")
    check_answer_number(judge, answer, "position", POSITION,
                        "position of 'Midnight Sketch' in the playlist")

    # DB after-state: the uploaded track (+ its auto-created alice_j artist row)
    # and exactly one new user_playlist_tracks row appending it at position 4.
    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"tracks", "artists", "user_playlist_tracks"})
    added, removed, _ = table_diff(initial_db, after_db, "tracks")
    judge.check("one_track_added", len(added) == 1 and not removed,
                f"added={list(added.values())!r}")
    if added:
        row = list(added.values())[0]
        judge.check("track_row",
                   row["title"] == TITLE and row["duration"] == DURATION_MS
                   and (row["genre"] or "") == GENRE and (row["tag_list"] or "") == TAGS
                   and row["permalink"] == SLUG and row["plays"] == 0,
                   f"row={dict(row)}")
        new_track_id = row["id"]
        artist_id = row["artist_id"]
        a, r, c = table_diff(initial_db, after_db, "artists")
        judge.check("one_artist_added", len(a) == 1 and not r and not c,
                    f"added={list(a.values())!r} changed={list(c)[:2]}")
        if a:
            new_artist = list(a.values())[0]
            judge.check("artist_is_alice",
                       new_artist["id"] == artist_id and new_artist["permalink"] == "alice_j"
                       and new_artist["track_count"] == 1,
                       f"artist={dict(new_artist)}")
        a, r, c = table_diff(initial_db, after_db, "user_playlist_tracks")
        judge.check("one_entry_added", len(a) == 1 and not r and not c,
                    f"added={list(a.values())!r} removed={list(r.values())!r}")
        if a:
            row = list(a.values())[0]
            judge.check("entry_appends_new_track",
                       row["playlist_id"] == PLAYLIST_ID and row["track_id"] == new_track_id
                       and row["position"] == POSITION,
                       f"row={dict(row)}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
