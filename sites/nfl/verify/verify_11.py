#!/usr/bin/env python3
"""Verify NFL--11.

In the video hub, find the video previewing this week's Falcons-Packers
Thursday night game: report its exact title, its channel, and its full
description, and name two other Week 3 preview videos on that channel. Then
find the video about the Packers running back placed on the Commissioner's
Exempt List (report its channel), the video recapping the Packers' Week 2
game, and the Good Morning Football video where a linebacker calls his Week 2
game his most complete — report all three titles. Which of the four channels
lists the fewest videos?

Frozen ground truth (seed DB, video hub): the TNF preview is "Falcons vs.
Packers Week 3 TNF Preview | NFL Daily" on the Latest Buzz channel; its
description is "Gregg Rosenthal, Colleen Wolfe and Nick Shook preview the Week
Thursday Night Football game between the Falcons and Packers". Other Week 3
previews on Latest Buzz include "Rams vs. Broncos Week 3 Preview | NFL Daily"
and "Vikings vs. Buccaneers Week 3 Preview | NFL Daily". The Jacobs video:
"Packers RB Josh Jacobs has been placed on the Commissioner's Exempt List |
\"The Insiders\"" (The Insiders channel). The Packers W2 recap: "Packers vs.
Jets Week 2 Recap | NFL Daily" (Latest Buzz). The GMFB video: "LB Devin Lloyd
says Week 2 game vs. Falcons was most complete NFL game of career | 'GMFB'".
Channel sizes: Latest Buzz 40, Game Highlights 80, The Insiders 80, Good
Morning Football 80 — Latest Buzz lists the fewest. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_all, contains_phrase, final_answer, navigated_to,
                        run_verifier)

TASK_ID = "NFL--11"
TNF_PREVIEW = "Falcons vs. Packers Week 3 TNF Preview | NFL Daily"
CHANNEL = "Latest Buzz"
DESC_TOKENS = ("Gregg Rosenthal", "Colleen Wolfe", "Nick Shook")
OTHER_PREVIEWS = ("Rams vs. Broncos Week 3 Preview", "Vikings vs. Buccaneers Week 3 Preview",
                  "Bengals vs. Steelers Week 3 Preview", "Chargers vs. Bills Week 3 Preview",
                  "Ravens vs. Cowboys Week 3 Preview", "Eagles vs. Bears Week 3 Preview",
                  "Chiefs vs. Dolphins Week 3 Preview")
JACOBS_TITLE = "Packers RB Josh Jacobs has been placed on the Commissioner's Exempt List"
JACOBS_CHANNEL = "The Insiders"
RECAP_TITLE = "Packers vs. Jets Week 2 Recap | NFL Daily"
LLOYD_TITLE = "LB Devin Lloyd says Week 2 game vs. Falcons was most complete NFL game of career"
FEWEST = "Latest Buzz"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the video hub channels (all four must have been visited
    # to count videos and find the three videos), the TNF preview's detail page
    judge.check("visited_video_hub", navigated_to(traj, "/videos"),
                "required: /videos/ (the hub)")
    judge.check("visited_tnf_preview_video",
                navigated_to(traj, "falcons-vs-packers-week-3-tnf-preview"),
                "required: the TNF preview video's page (full description)")
    judge.check("visited_channels",
                all(navigated_to(traj, f"/videos/channel/{c}/")
                    for c in ("latest-buzz", "the-insiders", "good-morning-football",
                              "game-highlights")),
                "required: all four channel pages (find the videos, count the lists)")
    judge.check("visited_jacobs_video",
                navigated_to(traj, "josh-jacobs"),
                "required: the Jacobs Commissioner's Exempt List video")
    # answer gates
    judge.check("answer_tnf_preview_title", contains_phrase(answer, TNF_PREVIEW),
                f"expected the exact title {TNF_PREVIEW!r}")
    judge.check("answer_tnf_preview_channel", contains_phrase(answer, CHANNEL),
                f"expected the channel {CHANNEL}")
    judge.check("answer_tnf_preview_description",
                all(contains_phrase(answer, t) for t in DESC_TOKENS),
                f"expected the description to quote {DESC_TOKENS}")
    others = [p for p in OTHER_PREVIEWS if p in answer]
    judge.check("answer_two_other_previews", len(others) >= 2,
                f"expected at least two other Week 3 preview titles; found {others!r}")
    judge.check("answer_jacobs_title", contains_phrase(answer, JACOBS_TITLE),
                f"expected {JACOBS_TITLE!r}")
    judge.check("answer_jacobs_channel", contains_phrase(answer, JACOBS_CHANNEL),
                f"expected the channel {JACOBS_CHANNEL}")
    judge.check("answer_recap_title", contains_phrase(answer, RECAP_TITLE),
                f"expected {RECAP_TITLE!r}")
    judge.check("answer_lloyd_title", contains_phrase(answer, LLOYD_TITLE),
                f"expected {LLOYD_TITLE!r}")
    judge.check("answer_fewest_channel", contains_phrase(answer, FEWEST),
                f"expected {FEWEST} as the channel with the fewest videos (40 vs 80)")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
