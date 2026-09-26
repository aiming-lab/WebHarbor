#!/usr/bin/env python3
"""Verify SoundCloud--1.

Your cousin is getting into country music. From the US Country chart, take the top five tracks this week. Open each track's page and report its title, artist, and how long ago the page says it was posted. Then open the profiles of the artists behind the #1 and #2 tracks and report each one's exact follower count. Finish by saying which of the five tracks has the most plays.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--1"

# (rank, title, artist, exact plays, posted-when, track page) — frozen from the seed.
TOP5 = [
    (1, "Last Thing You Need (from GTAVI: The Album)", "Atlantic Records", 222932,
     "8 days ago", "/atlanticrecords/morgan-wallen-last-thing-you-need-from-grand-theft-auto-vi-the-album-4"),
    (2, "P.O.S.", "Riley Green", 28930, "8 days ago", "/rileygreen-music/p-o-s"),
    (3, "That's Just Me", "Riley Green", 33108, "1 month ago", "/rileygreen-music/thats-just-me"),
    (4, "Think As You Drunk", "Riley Green", 40082, "4 months ago", "/rileygreen-music/think-as-you-drunk"),
    (5, "Take Me Back (Leave Me There)", "Cody Johnson", 191856, "4 months ago",
     "/codyjohnsonband/take-me-back-leave-me-there-1"),
]
# profiles of the #1 / #2 artists with exact follower counts
PROFILES = [
    ("Atlantic Records", 500207, "/atlanticrecords"),
    ("Riley Green", 31084, "/rileygreen-music"),
]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_country_chart", r"/music-charts-us/sets/country")
    for rank, title, artist, plays, posted, path in TOP5:
        check_visited_path(judge, traj, f"visited_t{rank}_track", path)
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_artist", artist)
        check_answer_number(judge, answer, f"t{rank}_plays", plays, f"#{rank} exact plays")
        judge.check(f"t{rank}_posted_when",
                    posted in answer.casefold() or posted.replace(" ", " ") in answer,
                    f"answer must report #{rank} posted {posted}")
    for artist, followers, path in PROFILES:
        check_visited_path(judge, traj, f"visited_profile_{artist.split()[0].lower()}",
                           path + r"/?(\?|$)")
        check_answer_number(judge, answer, f"followers_{artist.split()[0].lower()}",
                            followers, f"{artist} exact followers")
    # #1 'Last Thing You Need' (222,932) has the most plays of the five
    import re as _re
    judge.check("most_plays_track",
                bool(_re.search(r"most plays[^|]*last thing you need", answer.casefold())),
                "answer must name 'Last Thing You Need' as the most-played of the five")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
