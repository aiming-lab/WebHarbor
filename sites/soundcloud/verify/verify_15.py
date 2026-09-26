#!/usr/bin/env python3
"""Verify SoundCloud--15.

Sign in as Alice (alice.j@test.com / TestPass123!). Play the top three tracks on the US Pop chart in chart order (start each one playing). Open each track's page and report the label shown in its Details panel. Then open her listening history and report the three track titles in the order she played them, plus the three entries that were already in her history before this session.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--15"

USER_ID = 1                       # Alice
# (chart rank, title, artist, track id, seed plays, label, page path)
TOP3 = [
    (1, "DARK SIDE", "SMITH", 2351528147, 392799, "Hitmaker Music Group / 10K Projects",
     "/smithsmithmusic/darkside"),
    (2, "Bass Persuades", "Miley Cyrus", 2393437119, 137891, "Atlantic Records",
     "/mileycyrus/bass-persuades"),
    (3, "Different Religion (feat. Model/Actriz)", "Miley Cyrus", 2401801014, 62218,
     "Atlantic Records", "/mileycyrus/different-religion-feat-model"),
]
# the three pre-seed history entries (most recent first on the page)
PRE_SEED = ["Cowgirl", "Backwards", "Is Dat Right?"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_pop_chart", r"/music-charts-us/sets/pop")
    check_visited_path(judge, traj, "visited_history", r"/you/history")
    for rank, title, artist, tid, plays, label, path in TOP3:
        check_visited_path(judge, traj, f"visited_t{rank}", path)
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_label", label)
    # played order = chart order
    judge.check("played_order",
                answer.casefold().find("dark side") < answer.casefold().find("bass persuades")
                < answer.casefold().find("different religion"),
                "answer must list the three tracks in the order she played them (chart order)")
    for t in PRE_SEED:
        check_answer_phrase(judge, answer, f"pre_seed_{t.split()[0].lower()}", t)
    judge.check("pre_seed_all_three",
                all(t in answer for t in PRE_SEED),
                "answer must report the three pre-seed history entries")

    # DB after-state: exactly three new play_events rows for Alice in chart
    # order and the three plays counters bumped +1, and nothing else.
    check_only_tables_changed(judge, initial_db, after_db, allowed={"play_events", "tracks"})
    a, r, _ = table_diff(initial_db, after_db, "play_events")
    judge.check("three_play_events_added", len(a) == 3 and not r,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    added_ids = sorted(row["id"] for row in a.values())
    added_tracks = [row["track_id"] for row in
                    sorted(a.values(), key=lambda row: row["id"])]
    expected_tracks = [t[3] for t in TOP3]
    judge.check("play_events_in_chart_order",
                added_tracks == expected_tracks,
                f"added play_events tracks {added_tracks} != chart order {expected_tracks}")
    for row in a.values():
        judge.check("play_event_user_is_alice", row["user_id"] == USER_ID,
                   f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("only_three_counters_changed",
                len(a) == 0 and len(r) == 0 and len(c) == 3,
                f"added={list(a)[:2]} removed={list(r)[:2]} changed={list(c)[:3]}")
    changed = {new["id"]: (old, new) for old, new in c.values()}
    for rank, title, artist, tid, plays, label, path in TOP3:
        if tid in changed:
            old, new = changed[tid]
            judge.check(f"plays_counter_t{rank}",
                        new["plays"] == plays + 1,
                        f"track {tid}: plays {old['plays']}->{new['plays']}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
