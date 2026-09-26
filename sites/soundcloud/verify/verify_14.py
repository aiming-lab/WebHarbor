#!/usr/bin/env python3
"""Verify SoundCloud--14.

Sign in as Carol (carol.d@test.com / TestPass123!). She's digging this week's US Electronic chart. Open the #1 and #2 tracks' pages and report each one's title and artist. Post the comment 'great mix!' at timestamp 1:30 on the #1, and 'so smooth' at 0:45 on the #2. Then report the total comment count shown on each page after your comment, and which of the two tracks has more plays.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--14"

# (rank, title, artist, track id, exact plays, seed comment_count, page path)
TRACKS = [
    (1, "Bass Persuades Remixx", "Miley Cyrus", 2398849314, 63265, 47,
     "/mileycyrus/bass-persuades-remixx"),
    (2, "Tape B x Effin -  I'll Never Know", "Tape B", 2319913409, 74742, 125,
     "/tape-b-official/tape-b-x-effin-ill-never-know"),
]
USER_ID = 3                       # Carol
COMMENTS = {1: ("great mix!", 90000), 2: ("so smooth", 45000)}   # (body, timestamp_ms)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_electronic_chart", r"/music-charts-us/sets/electronic")
    for rank, title, artist, tid, plays, ccount, path in TRACKS:
        check_visited_path(judge, traj, f"visited_t{rank}", path)
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_artist", artist)
        body, at_ms = COMMENTS[rank]
        check_answer_phrase(judge, answer, f"comment_body_t{rank}", body)
        check_answer_number(judge, answer, f"post_comment_count_t{rank}", ccount + 1,
                            f"#{rank} comment count after posting")
    # #2 has more plays (74,742 vs 63,265)
    judge.check("which_has_more_plays",
                "more plays" in answer.casefold()
                and answer.casefold().find("tape b") < answer.casefold().find("more plays"),
                "answer must state that the #2 track has more plays")

    # DB after-state: exactly two new comment rows (Carol, the two bodies with
    # their timestamps) and the two comment_count counters bumped +1.
    check_only_tables_changed(judge, initial_db, after_db, allowed={"comments", "tracks"})
    a, r, _ = table_diff(initial_db, after_db, "comments")
    judge.check("two_comments_added", len(a) == 2 and not r,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    by_track = {}
    for row in a.values():
        by_track.setdefault(row["track_id"], []).append(row)
    for rank, title, artist, tid, plays, ccount, path in TRACKS:
        body, at_ms = COMMENTS[rank]
        rows = by_track.get(tid, [])
        judge.check(f"comment_row_t{rank}",
                    len(rows) == 1 and rows[0]["author_name"] == "Carol Davis"
                    and rows[0]["body"] == body and rows[0]["timestamp_ms"] == at_ms,
                    f"expected one new comment '{body}' @ {at_ms}ms on track {tid}; got {rows!r}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("only_two_counters_changed",
                len(a) == 0 and len(r) == 0 and len(c) == 2,
                f"added={list(a)[:2]} removed={list(r)[:2]} changed={list(c)[:2]}")
    changed = {new["id"]: (old, new) for old, new in c.values()}
    for rank, title, artist, tid, plays, ccount, path in TRACKS:
        if tid in changed:
            old, new = changed[tid]
            judge.check(f"counter_t{rank}",
                        new["comment_count"] == ccount + 1,
                        f"track {tid}: comment_count {old['comment_count']}->{new['comment_count']}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
