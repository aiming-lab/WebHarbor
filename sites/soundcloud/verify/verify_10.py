#!/usr/bin/env python3
"""Verify SoundCloud--10.

Several tracks appear in both the US 'All music genres' Top 50's top 10 and the US 'New & Hot' chart this week. Cross-check the two charts to identify all of them, then open each one's page and report its title, exact play count, duration, and position on both charts. Which of them has the most likes? Open that track's artist's profile and report their exact follower count.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--10"

# all five crossovers between the Top 50's top 10 and New & Hot — frozen.
# (title, artist, top50 position, newhot position, exact plays, likes, duration, path)
CROSSOVERS = [
    ("Backwards", "Quavo", 2, 1, 280716, 17544, "3:11", "/quavoofficial/backwards"),
    ("Something I Need", "Offset", 4, 2, 176445, 9788, "2:25", "/offset-sc/something-i-need"),
    ("Bass Persuades", "Miley Cyrus", 6, 4, 137891, 6770, "3:22", "/mileycyrus/bass-persuades"),
    ("Different Religion (feat. Model/Actriz)", "Miley Cyrus", 7, 5, 62218, 3383, "3:43",
     "/mileycyrus/different-religion-feat-model"),
    ("Last Thing You Need (from GTAVI: The Album)", "Atlantic Records", 10, 3, 222932,
     12589, "3:16",
     "/atlanticrecords/morgan-wallen-last-thing-you-need-from-grand-theft-auto-vi-the-album-4"),
]
MOST_LIKED = ("Backwards", "Quavo", 205010)      # title, artist, exact followers


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_top50", r"/music-charts-us/sets/all-music-genres")
    check_visited_path(judge, traj, "visited_new_hot", r"/music-charts-us/sets/new-hot")
    for title, artist, t50, nh, plays, likes, dur, path in CROSSOVERS:
        check_visited_path(judge, traj, f"visited_{title.split()[0].lower()}", path)
        check_answer_phrase(judge, answer, f"title_{t50}", title)
        check_answer_phrase(judge, answer, f"artist_{t50}", artist)
        check_answer_number(judge, answer, f"plays_{t50}", plays, f"{title} exact plays")
        judge.check(f"duration_{t50}", dur in answer,
                    f"answer must report {title} duration {dur}")
        check_answer_number(judge, answer, f"top50_pos_{t50}", t50, f"{title} Top 50 position")
        check_answer_number(judge, answer, f"newhot_pos_{t50}", nh, f"{title} New & Hot position")
    judge.check("five_crossovers",
                ("5" in answer) or ("five" in answer.casefold()) or ("all" in answer.casefold()),
                "answer must indicate all crossovers were identified (5)")
    check_answer_phrase(judge, answer, "most_liked_title", MOST_LIKED[0])
    check_answer_phrase(judge, answer, "most_liked_artist", MOST_LIKED[1])
    check_answer_number(judge, answer, "most_liked_followers", MOST_LIKED[2],
                        "Quavo exact followers")
    check_visited_path(judge, traj, "visited_most_liked_profile", r"/quavoofficial/?(\?|$)")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
