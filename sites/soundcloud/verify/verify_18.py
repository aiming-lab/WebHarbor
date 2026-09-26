#!/usr/bin/env python3
"""Verify SoundCloud--18.

Sign in as Bob (bob.c@test.com / TestPass123!). Search for 'lucki' and report how many tracks and how many people the site says it found. Open the most-played LUCKI track from the results, repost it, and report its title, exact play count, and the label from its Details panel. Then open LUCKI's profile from the People tab and report his city and exact follower count. Finally, back on the track's page, open the two most-played tracks in its Related tracks section and report each one's title, artist, and exact play count.

Stateful since the fix: Bob reposts '2021 Vibes' (reposts 1,422 -> 1,423; the
task was read-only before the redesign).
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier, table_diff)

TASK_ID = "SoundCloud--18"

USER_ID = 2                       # Bob
TITLE = "2021 Vibes"
TRACK_ID = 1553767969
PLAYS = 8302219
LABEL = "Lucki / EMPIRE"
SEED_REPOSTS = 1422
TRACK_PAGE = "/boob7/lucki-2021-vibes"
PROFILE_CITY = "Chicago"
PROFILE_FOLLOWERS = 498942
RELATED = [
    ("Redbone", "Childish Gambino", 92777386, "/childish-gambino/redbone"),
    ("Wrong Place", "Hurricane Wisdom", 223684, "/2020hurricane/all-on-you"),
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_signin", r"/signin")
    check_visited_path(judge, traj, "visited_search", r"/search\?q=lucki")
    check_visited_path(judge, traj, "visited_track_page", TRACK_PAGE)
    check_visited_path(judge, traj, "visited_profile", r"/boob7/?(\?|$)")
    judge.check("tracks_found_two",
                ("2 tracks" in answer) or ("two tracks" in answer.casefold()),
                "answer must report 2 tracks found")
    judge.check("people_found_one",
                ("1 people" in answer) or ("1 person" in answer.casefold())
                or ("one person" in answer.casefold()),
                "answer must report 1 person found")
    check_answer_phrase(judge, answer, "title", TITLE)
    check_answer_number(judge, answer, "plays", PLAYS, "exact play count")
    check_answer_phrase(judge, answer, "label", LABEL)
    check_answer_phrase(judge, answer, "city", PROFILE_CITY)
    check_answer_number(judge, answer, "followers", PROFILE_FOLLOWERS,
                        "LUCKI exact followers")
    for i, (title, artist, plays, path) in enumerate(RELATED, 1):
        check_answer_phrase(judge, answer, f"related{i}_title", title)
        check_answer_phrase(judge, answer, f"related{i}_artist", artist)
        check_answer_number(judge, answer, f"related{i}_plays", plays,
                            f"related #{i} exact plays")
        check_visited_path(judge, traj, f"visited_related{i}", path)

    # DB after-state: exactly one new repost row for Bob on '2021 Vibes' with
    # the repost counter bumped 1,422 -> 1,423, and nothing else.
    check_only_tables_changed(judge, initial_db, after_db, allowed={"reposts", "tracks"})
    a, r, _ = table_diff(initial_db, after_db, "reposts")
    judge.check("one_repost_added", len(a) == 1 and not r,
                f"added={list(a.values())!r} removed={list(r.values())!r}")
    if a:
        row = list(a.values())[0]
        judge.check("repost_row_is_bob_on_target",
                    row["user_id"] == USER_ID and row["track_id"] == TRACK_ID,
                    f"row={dict(row)}")
    a, r, c = table_diff(initial_db, after_db, "tracks")
    judge.check("only_repost_counter_changed",
                len(a) == 0 and len(r) == 0 and len(c) == 1,
                f"added={list(a)[:2]} removed={list(r)[:2]} changed={list(c)[:2]}")
    for _k, (old, new) in c.items():
        judge.check("repost_counter_bumped",
                    old["id"] == TRACK_ID and new["reposts"] == SEED_REPOSTS + 1,
                    f"reposts {old['reposts']} -> {new['reposts']} on track {old['id']}")


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
