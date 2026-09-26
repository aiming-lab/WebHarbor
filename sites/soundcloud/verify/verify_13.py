#!/usr/bin/env python3
"""Verify SoundCloud--13.

Sign in as Bob (bob.c@test.com / TestPass123!). He wants to back the UK scene: open the UK Hip Hop chart and the pages of its #1 and #2 tracks, and report each one's title, artist, and exact play count. Like and repost both tracks, then report the like count and repost count shown on each page after your actions, and which of the two has more plays.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--13"

# (rank, title, artist, track id, exact plays, seed likes, seed reposts, page path)
TRACKS = [
    (1, "Dead Fresh", "Lil Baby", 2360196407, 2468395, 63981, 331,
     "/lil-baby-4pf/dead-fresh"),
    (2, "Lil azz-make it out", "dirty mick", 2327612231, 463675, 7633, 32,
     "/user-94225447/lil-azz-make-it-out"),
]
USER_ID = 2                       # Bob


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_uk_hiphop_chart", r"/music-charts-uk/sets/hip-hop")
    for rank, title, artist, tid, plays, likes, reposts, path in TRACKS:
        check_visited_path(judge, traj, f"visited_t{rank}", path)
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_artist", artist)
        check_answer_number(judge, answer, f"t{rank}_plays", plays, f"#{rank} exact plays")
        # post-action counts as shown on the page (the JS writes the raw number
        # into the button label, e.g. 63982; compact/exact both accepted)
        check_answer_number(judge, answer, f"t{rank}_post_like_count", likes + 1,
                            f"#{rank} post-like count")
        check_answer_number(judge, answer, f"t{rank}_post_repost_count", reposts + 1,
                            f"#{rank} post-repost count")
    # #1 has more plays (2,468,395 vs 463,675)
    judge.check("which_has_more_plays",
                "more plays" in answer.casefold()
                and answer.casefold().find("dead fresh") < answer.casefold().find("more plays"),
                "answer must state that the #1 track has more plays")

    # DB after-state: exactly one like row and one repost row added for Bob on
    # each of the two tracks, with both counters bumped +1, and nothing else.
    check_only_tables_changed(judge, initial_db, after_db,
                              allowed={"likes", "reposts", "tracks"})
    a, r, _ = table_diff(initial_db, after_db, "likes")
    judge.check("two_likes_added", len(a) == 2 and not r,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    added_ids = {row["track_id"]: row for row in a.values()}
    for rank, title, artist, tid, *_ in TRACKS:
        judge.check(f"like_row_t{rank}",
                    tid in added_ids and added_ids[tid]["user_id"] == USER_ID,
                    f"expected new like for user {USER_ID} on track {tid}; got {list(a.values())!r}")
    a, r, _ = table_diff(initial_db, after_db, "reposts")
    judge.check("two_reposts_added", len(a) == 2 and not r,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    added_ids = {row["track_id"]: row for row in a.values()}
    for rank, title, artist, tid, *_ in TRACKS:
        judge.check(f"repost_row_t{rank}",
                    tid in added_ids and added_ids[tid]["user_id"] == USER_ID,
                    f"expected new repost for user {USER_ID} on track {tid}; got {list(a.values())!r}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("only_two_counters_changed",
                len(a) == 0 and len(r) == 0 and len(c) == 2,
                f"added={list(a)[:2]} removed={list(r)[:2]} changed={list(c)[:2]}")
    changed = {row[1]["id"]: row for row in c.values()}
    for rank, title, artist, tid, plays, likes, reposts, path in TRACKS:
        if tid in changed:
            old, new = changed[tid]
            judge.check(f"counters_t{rank}",
                        new["likes"] == likes + 1 and new["reposts"] == reposts + 1,
                        f"track {tid}: likes {old['likes']}->{new['likes']}, "
                        f"reposts {old['reposts']}->{new['reposts']}")



if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
