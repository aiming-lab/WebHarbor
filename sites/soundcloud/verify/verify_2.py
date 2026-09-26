#!/usr/bin/env python3
"""Verify SoundCloud--2.

A hip hop star sits at #9 on the US 'All music genres' Top 50 this week. Open that track's page, then open the artist's profile from it and report whether they're verified, their exact follower count, and how many tracks they've uploaded. Open every track on their Popular tracks tab and report each one's title, exact play count, and label. One of those is also on the US Hip Hop chart — report its position there and on the UK Hip Hop chart.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--2"

ARTIST = "Lil Baby"
ARTIST_PATH = "/lil-baby-4pf"
VERIFIED = True
FOLLOWERS = 1988725
TRACKS_UPLOADED = 236
# every track on the Popular tab (title, exact plays, label, page path) — frozen.
POPULAR = [
    ("Mrs. Trendsetter", 4045615, "Quality Control Music/Motown Records",
     "/lil-baby-4pf/mrs-trendsetter"),
    ("Dead Fresh", 2468395, "Quality Control Music/Motown Records",
     "/lil-baby-4pf/dead-fresh"),
    ("What She Like", 1468903, "Quality Control Music/Motown Records",
     "/lil-baby-4pf/what-she-like"),
    ("Guaranteed", 1410635, "Quality Control Music/Motown Records",
     "/lil-baby-4pf/guaranteed"),
]
CROSSOVER = ("Dead Fresh", 6, 1)          # US Hip Hop #6, UK Hip Hop #1


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_us_chart", r"/music-charts-us/sets/all-music-genres")
    check_visited_path(judge, traj, "visited_t9_track", r"/lil-baby-4pf/dead-fresh")
    check_visited_path(judge, traj, "visited_profile", ARTIST_PATH + r"/?(\?tab=popular)?(\?|$)")
    check_answer_phrase(judge, answer, "artist_name", ARTIST)
    judge.check("artist_verified",
                "verified" in answer.casefold(),
                "answer must state whether the artist is verified")
    check_answer_number(judge, answer, "followers", FOLLOWERS, "Lil Baby exact followers")
    check_answer_number(judge, answer, "tracks_uploaded", TRACKS_UPLOADED, "tracks uploaded")
    check_visited_path(judge, traj, "visited_popular_tab", ARTIST_PATH + r"\?tab=popular")
    for i, (title, plays, label, path) in enumerate(POPULAR, 1):
        check_visited_path(judge, traj, f"visited_pop{i}", path)
        check_answer_phrase(judge, answer, f"pop{i}_title", title)
        check_answer_number(judge, answer, f"pop{i}_plays", plays, f"popular #{i} exact plays")
        check_answer_phrase(judge, answer, f"pop{i}_label", label)
    check_answer_phrase(judge, answer, "crossover_title", CROSSOVER[0])
    check_answer_number(judge, answer, "crossover_us_position", CROSSOVER[1],
                        "position on the US Hip Hop chart")
    check_answer_number(judge, answer, "crossover_uk_position", CROSSOVER[2],
                        "position on the UK Hip Hop chart")
    check_visited_path(judge, traj, "visited_us_hiphop", r"/music-charts-us/sets/hip-hop")
    check_visited_path(judge, traj, "visited_uk_hiphop", r"/music-charts-uk/sets/hip-hop")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
