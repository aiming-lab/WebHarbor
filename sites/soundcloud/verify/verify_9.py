#!/usr/bin/env python3
"""Verify SoundCloud--9.

Your friend only listens to artists from Texas. On the US Rock chart this week, check the top five tracks: open each track's page and report its exact play count and duration, then open its artist's profile and report their city. Finally report which artist has a Texas city, their name, and the title of their track on the chart.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--9"

# (rank, title, artist, exact plays, duration, track page, artist profile, city)
TOP5 = [
    (1, "Joseph", "Falling In Reverse", 66992, "4:09",
     "/fallinginreverseofficial/joseph", "/fallinginreverseofficial", ""),
    (2, "Benny Boy (prod badlilcoup)", "Pink Boy", 49855, "2:08",
     "/user-73135476/benny-boy-prod-badlilcoup", "/user-73135476", ""),
    (3, "oh yeah?", "Steve Lacy", 211561, "0:30",
     "/steevlacy/oh-yeah", "/steevlacy", ""),
    (4, "It Doesn't Matter", "The Living Tombstone", 295495, "3:45",
     "/tltombstone/it-doesnt-matter", "/tltombstone", ""),
    (5, "12 Steps", "Dexter and The Moonrocks", 218454, "3:11",
     "/dexter-and-the-moonrocks/12-steps", "/dexter-and-the-moonrocks", "Abilene, TX"),
]
TEXAS_ARTIST = "Dexter and The Moonrocks"
TEXAS_CITY = "Abilene, TX"
TEXAS_TRACK = "12 Steps"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_rock_chart", r"/music-charts-us/sets/rock")
    for rank, title, artist, plays, dur, tpath, apath, city in TOP5:
        check_visited_path(judge, traj, f"visited_t{rank}", tpath)
        check_visited_path(judge, traj, f"visited_a{rank}", apath + r"/?(\?|$)")
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_artist", artist)
        check_answer_number(judge, answer, f"t{rank}_plays", plays, f"#{rank} exact plays")
        judge.check(f"t{rank}_duration", dur in answer,
                    f"answer must report #{rank} duration {dur}")
    check_answer_phrase(judge, answer, "texas_artist", TEXAS_ARTIST)
    judge.check("texas_city",
                ("abilene" in answer.casefold() and "tx" in answer.casefold()),
                "answer must report the Texas city (Abilene, TX)")
    check_answer_phrase(judge, answer, "texas_track", TEXAS_TRACK)
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
