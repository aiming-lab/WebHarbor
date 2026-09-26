#!/usr/bin/env python3
"""Verify SoundCloud--16.

Sign in as Alice (alice.j@test.com / TestPass123!). Her playlist 'Late Night Drive' has three tracks, and she wants a refresh. Open her most-played liked track's page — report its exact play count and label — then add it to 'Late Night Drive' with the ＋ button. Open the playlist, remove its least-played track (open that track's page first and report its exact play count and duration), and report the three remaining titles in order.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--16"

USER_ID = 1                       # Alice
PLAYLIST_ID = 1                   # Late Night Drive
MOST_PLAYED_LIKED = ("Cowgirl", 1453008, "American Dogwood / EMPIRE",
                     "/shaboozey/cowgirl", 2328694826)
REMOVED = ("Morgan Wallen – Last Thing You Need (From Grand Theft Auto VI_ The Album)",
           205832, "3:06", 2402558166, "/faylen000/morgan-wallen-last-thing-you")
REMAINING = ["Piece Of Your Love", "Ghetto Love Story", "Cowgirl"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_library", r"/you/library")
    check_visited_path(judge, traj, "visited_most_played_page", MOST_PLAYED_LIKED[3])
    check_answer_phrase(judge, answer, "most_played_title", MOST_PLAYED_LIKED[0])
    check_answer_number(judge, answer, "most_played_plays", MOST_PLAYED_LIKED[1],
                        "most-played liked track exact plays")
    check_answer_phrase(judge, answer, "most_played_label", MOST_PLAYED_LIKED[2])
    check_answer_phrase(judge, answer, "playlist_name", "Late Night Drive")
    check_answer_phrase(judge, answer, "removed_title", "Last Thing You Need")
    check_answer_number(judge, answer, "removed_plays", REMOVED[1],
                        "removed track exact plays")
    judge.check("removed_duration", REMOVED[2] in answer,
                f"answer must report the removed track's duration {REMOVED[2]}")
    for i, t in enumerate(REMAINING, 1):
        check_answer_phrase(judge, answer, f"remaining_{i}", t)
    judge.check("remaining_order",
                answer.rfind("Piece Of Your Love") < answer.rfind("Ghetto Love Story")
                < answer.rfind("Cowgirl"),
                "answer must list the three remaining tracks in playlist order")
    check_visited_path(judge, traj, "visited_removed_page",
                       REMOVED[4] + r"/?(|$)")
    check_visited_path(judge, traj, "visited_playlist_page", r"/you/playlist/1")

    # DB after-state: net one user_playlist_tracks change on Late Night Drive —
    # Cowgirl appended at position 4, the Morgan Wallen row deleted, and the
    # remaining rows renumbered 1..3 (Piece Of Your Love, Ghetto Love Story, Cowgirl).
    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"user_playlist_tracks"})
    a, r, c = table_diff(initial_db, after_db, "user_playlist_tracks")
    judge.check("one_entry_added", len(a) == 1,
                f"added={list(a.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("added_is_cowgirl",
                    row["playlist_id"] == PLAYLIST_ID
                    and row["track_id"] == MOST_PLAYED_LIKED[4]
                    and row["position"] == 3,
                    f"row={dict(row)} (Cowgirl ends up at position 3 after the removal)")
    judge.check("one_entry_removed", len(r) == 1,
                f"removed={list(r.values())!r}")
    if r:
        row = list(r.values())[0]
        judge.check("removed_is_morgan_wallen",
                    row["playlist_id"] == PLAYLIST_ID and row["track_id"] == REMOVED[3],
                    f"row={dict(row)}")
    # the two surviving seed rows get renumbered to positions 1 and 2
    judge.check("two_rows_renumbered", len(c) == 2,
                f"changed={ {k: (o['position'], n['position']) for k, (o, n) in c.items()} }")
    for _k, (old, new) in c.items():
        judge.check("renumber_positions",
                    old["playlist_id"] == PLAYLIST_ID
                    and new["position"] in (1, 2)
                    and new["position"] < old["position"],
                    f"row {old['id']}: position {old['position']}->{new['position']}")
    # final positions: 1 Piece Of Your Love, 2 Ghetto Love Story, 3 Cowgirl
    final = after_db.execute(
        "SELECT t.title FROM user_playlist_tracks e JOIN tracks t ON t.id=e.track_id "
        "WHERE e.playlist_id=? ORDER BY e.position", (PLAYLIST_ID,)).fetchall()
    titles = [row[0] for row in final]
    judge.check("final_order_three_tracks",
                titles == REMAINING,
                f"final playlist order {titles} != {REMAINING}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
