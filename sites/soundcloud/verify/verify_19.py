#!/usr/bin/env python3
"""Verify SoundCloud--19.

One artist appears in the top 10 of both the US Rock and US Folk charts this week under two different titles. Cross-check both charts to find them, open both track pages, and report the artist's name, both positions and titles, and each track's exact play count and label. Then open their profile: report their exact follower count and tracks uploaded, plus their top three Popular-tab tracks' titles and exact play counts. One of the two also sits on the UK Indie chart; report its position, that chart's #1 title, artist, and exact plays, and that artist's profile follower count.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--19"

ARTIST = "Steve Lacy"
PROFILE_PATH = "/steevlacy"
FOLLOWERS = 377394
TRACKS_UPLOADED = 52
ROCK = ("oh yeah?", 3, 211561, "L-M Records/RCA Records", "/steevlacy/oh-yeah")
FOLK = ("nothing", 6, 85000, "L-M Records/RCA Records", "/steevlacy/nothing")
# Popular tab top three (titles, exact plays, page paths) — the tab rows only
# show compact plays, so each exact count is frozen from its track page.
POP1 = ("Buttons", 1059416, "/steevlacy/buttons")
POP2 = ("oh yeah?", 211561, "/steevlacy/oh-yeah")
POP3 = ("doom", 128218, "/steevlacy/doom")
UK_INDIE = ("oh yeah?", 3)
# UK Indie #1 and its artist's profile follower count (text-bound to the profile).
INDIE1 = ("Guilty", "Sammi Heaney", 33262, "/sam-heaney-433035397/guilty")
INDIE1_PROFILE = "/sam-heaney-433035397"
INDIE1_FOLLOWERS = 118


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_rock_chart", r"/music-charts-us/sets/rock")
    check_visited_path(judge, traj, "visited_folk_chart", r"/music-charts-us/sets/folk")
    check_visited_path(judge, traj, "visited_rock_track", ROCK[4])
    check_visited_path(judge, traj, "visited_folk_track", FOLK[4])
    check_visited_path(judge, traj, "visited_profile", PROFILE_PATH + r"/?(\?|$)")
    check_visited_path(judge, traj, "visited_popular_tab", PROFILE_PATH + r"\?tab=popular")
    check_visited_path(judge, traj, "visited_pop1_track", POP1[2])
    check_visited_path(judge, traj, "visited_pop3_track", POP3[2])
    check_visited_path(judge, traj, "visited_uk_indie", r"/music-charts-uk/sets/indie")
    check_visited_path(judge, traj, "visited_indie1_track", INDIE1[3])
    check_visited_path(judge, traj, "visited_indie1_profile",
                       INDIE1_PROFILE + r"/?(\?|$)")
    check_answer_phrase(judge, answer, "artist_name", ARTIST)
    check_answer_phrase(judge, answer, "rock_title", ROCK[0])
    check_answer_number(judge, answer, "rock_position", ROCK[1], "US Rock chart position")
    check_answer_number(judge, answer, "rock_plays", ROCK[2], "rock track exact plays")
    check_answer_phrase(judge, answer, "rock_label", ROCK[3])
    check_answer_phrase(judge, answer, "folk_title", FOLK[0])
    check_answer_number(judge, answer, "folk_position", FOLK[1], "US Folk chart position")
    check_answer_number(judge, answer, "folk_plays", FOLK[2], "folk track exact plays")
    check_answer_phrase(judge, answer, "folk_label", FOLK[3])
    check_answer_number(judge, answer, "followers", FOLLOWERS, "Steve Lacy exact followers")
    check_answer_number(judge, answer, "tracks_uploaded", TRACKS_UPLOADED,
                        "Steve Lacy tracks uploaded")
    check_answer_phrase(judge, answer, "pop1_title", POP1[0])
    check_answer_number(judge, answer, "pop1_plays", POP1[1], "popular #1 exact plays")
    check_answer_phrase(judge, answer, "pop2_title", POP2[0])
    check_answer_number(judge, answer, "pop2_plays", POP2[1], "popular #2 exact plays")
    check_answer_phrase(judge, answer, "pop3_title", POP3[0])
    check_answer_number(judge, answer, "pop3_plays", POP3[1], "popular #3 exact plays")
    check_answer_phrase(judge, answer, "uk_indie_title", UK_INDIE[0])
    check_answer_number(judge, answer, "uk_indie_position", UK_INDIE[1],
                        "UK Indie chart position")
    check_answer_phrase(judge, answer, "indie1_title", INDIE1[0])
    check_answer_phrase(judge, answer, "indie1_artist", INDIE1[1])
    check_answer_number(judge, answer, "indie1_plays", INDIE1[2],
                        "UK Indie #1 exact plays")
    check_answer_number(judge, answer, "indie1_followers", INDIE1_FOLLOWERS,
                        "UK Indie #1 artist profile followers")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
