#!/usr/bin/env python3
"""Verify SoundCloud--17.

Count how many of the top 10 tracks on the US Folk chart are by artists with more than 100,000 followers. Check each track's page (the artist's follower count is shown in the side panel), and report the count plus the name of every qualifying artist.
"""
from verify_lib import (Judge, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier, visited_path)

TASK_ID = "SoundCloud--17"

QUALIFYING = ["Rod Wave", "Steve Lacy"]
FOLK_TOP10 = ["/rodwave/kiss-me-interlude", "/ridgeclub199999/",
              "/2020hurricane/", "/alyssa-proffitt-843724748/",
              "/malcolmtodd-sc/", "/steevlacy/nothing", "/sogand-mirzabeigi-330718986/",
              "/alyssa-proffitt-843724748/", "/vincentmason-music/", "/iman47439/"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_folk_chart", r"/music-charts-us/sets/folk")
    check_visited_path(judge, traj, "visited_qualifying_rodwave", r"/rodwave/")
    check_visited_path(judge, traj, "visited_qualifying_steevlacy", r"/steevlacy/")
    judge.check("count_is_two",
                any(tok in answer for tok in ("2 of", "count: 2", "count is 2", "2 artists",
                                              "Two", "two of", "answer: 2")),
                "answer must report the count 2")
    for a in QUALIFYING:
        check_answer_phrase(judge, answer, f"artist_{a.split()[0]}", a)
    judge.check("no_false_qualifiers",
                not any(x in answer for x in ("ridgeclub", "Hurricane Wisdom", "Alyssa Grace",
                                              "Malcolm Todd", "bleumea", "Vincent Mason",
                                              "Iman")),
                "non-qualifying artists must not be listed as qualifying")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
