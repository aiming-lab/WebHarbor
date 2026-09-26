#!/usr/bin/env python3
"""Verify SoundCloud--12.

Your DJ friend wants this week's UK Dance chart top five on one card. Open the chart and, for each of its top five tracks, open the track's page and report its title, artist, exact play count, and duration. Which of the five has the most likes? Open that artist's profile and report their city and exact follower count.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--12"

# (rank, title, artist, exact plays, duration, likes, track page)
TOP5 = [
    (1, "Good Girl", "Cloonee", 1294858, "3:01", 41587, "/cloonee/goodgirl"),
    (2, "Kolter - Hey Everybody (Radio Edit)", "Kolter", 938222, "2:36", 28409,
     "/koltercologne/kolter-hey-everybody-back-in"),
    (3, "On 2nite", "SILVA BUMPA", 2399647, "2:38", 57846, "/silvabumpa/on-2nite"),
    (4, "Prospa - Masterplan", "CircoLoco Records", 1077255, "3:47", 26684,
     "/circolocorecords/prospa-masterplan-7"),
    (5, "Sun is Shining (Lovelee Dae)", "Tommy Phillips", 460800, "2:54", 16588,
     "/tommmyphillips/sunisshining"),
]
MOST_LIKED = ("On 2nite", "SILVA BUMPA", "Sheffield", 54552)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_uk_dance_chart", r"/music-charts-uk/sets/dance")
    for rank, title, artist, plays, dur, likes, path in TOP5:
        check_visited_path(judge, traj, f"visited_t{rank}", path)
        check_answer_phrase(judge, answer, f"t{rank}_title", title)
        check_answer_phrase(judge, answer, f"t{rank}_artist", artist)
        check_answer_number(judge, answer, f"t{rank}_plays", plays, f"#{rank} exact plays")
        judge.check(f"t{rank}_duration", dur in answer,
                    f"answer must report #{rank} duration {dur}")
    check_answer_phrase(judge, answer, "most_liked_title", MOST_LIKED[0])
    check_answer_phrase(judge, answer, "most_liked_artist", MOST_LIKED[1])
    check_answer_phrase(judge, answer, "most_liked_city", MOST_LIKED[2])
    check_answer_number(judge, answer, "most_liked_followers", MOST_LIKED[3],
                        "SILVA BUMPA exact followers")
    check_visited_path(judge, traj, "visited_most_liked_profile", r"/silvabumpa/?(\?|$)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
