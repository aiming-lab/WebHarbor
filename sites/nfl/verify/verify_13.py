#!/usr/bin/env python3
"""Verify NFL--13.

For Week 3, report all three prime-time windows: for each of Thursday, Sunday
and Monday night, give the matchup (away at home), the day with kickoff time,
and — from each game center — the network, the stadium, and both teams'
records. Which of the six is still undefeated (standings)? For each game, open
the site's video preview and report its exact title, its channel, and the
first video its page lists under Up Next. Also find the newsroom article with
three must-know storylines for the Thursday game and give its author and date.

Frozen ground truth (seed DB): TNF — Falcons at Packers, THU 8:15pm ET, Prime
Video, Lambeau Field (ATL 0-2, GB 1-1). SNF — Rams at Broncos, SUN 8:20pm ET,
NBC, Empower Field at Mile High (LAR 1-1, DEN 1-1). MNF — Eagles at Bears,
MON 8:15pm ET, ESPN, Soldier Field (PHI 2-0, CHI 1-1). Still undefeated of the
six: the Eagles (2-0). Video previews (all on the Latest Buzz channel): "Falcons
vs. Packers Week 3 TNF Preview | NFL Daily" (first Up Next: "Rams vs. Broncos
Week 3 Preview | NFL Daily"), "Rams vs. Broncos Week 3 Preview | NFL Daily"
(first Up Next: "Vikings vs. Buccaneers Week 3 Preview | NFL Daily"), "Eagles
vs. Bears Week 3 Preview | NFL Daily" (first Up Next: "Rams vs. Broncos Week 3
Preview | NFL Daily"). TNF storylines article: "Falcons vs. Packers: Three
must-know storylines for Thursday's Week 3 prime-time game" by Dan Parr,
September 23, 2026. Read-only task.
"""
from verify_lib import (Judge, check_read_only_db, check_trajectory_identity,
                        contains_date, contains_phrase, contains_record, contains_time,
                        final_answer, navigated_to, run_verifier)

TASK_ID = "NFL--13"
WINDOWS = (
    ("tnf", ("Falcons", "Packers", "20:15", "Prime Video", "Lambeau Field", (0, 2), (1, 1))),
    ("snf", ("Rams", "Broncos", "20:20", "NBC", "Empower Field at Mile High", (1, 1), (1, 1))),
    ("mnf", ("Eagles", "Bears", "20:15", "ESPN", "Soldier Field", (2, 0), (1, 1))),
)
UNDEFEATED = "Eagles"
PREVIEWS = ("Falcons vs. Packers Week 3 TNF Preview",
            "Rams vs. Broncos Week 3 Preview",
            "Eagles vs. Bears Week 3 Preview")
PREVIEW_CHANNEL = "Latest Buzz"
PREVIEW_SLUGS = (
    "falcons-vs-packers-week-3-tnf-preview-nfl-daily",
    "rams-vs-broncos-week-3-preview-nfl-daily",
    "eagles-vs-bears-week-3-preview-nfl-daily",
)
FIRST_UP_NEXT = (
    ("Falcons vs. Packers Week 3 TNF Preview", "Rams vs. Broncos Week 3 Preview"),
    ("Rams vs. Broncos Week 3 Preview", "Vikings vs. Buccaneers Week 3 Preview"),
    ("Eagles vs. Bears Week 3 Preview", "Rams vs. Broncos Week 3 Preview"),
)
STORYLINES = ("falcons-vs-packers-three-must-know-storylines", "Dan Parr", "2026-09-23")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the three prime-time game centers (the r3 task text
    # pulls the network, stadium and records from each game center; the
    # matchup/day/kickoff come from the same centers or the scores ribbon),
    # the standings, the video hub, the three preview video pages, and the
    # TNF storylines article
    for tag, (away, home, *_rest) in WINDOWS:
        slug = f"{away.lower()}-at-{home.lower()}".replace(" ", "-")
        judge.check(f"visited_{tag}_game_center",
                    navigated_to(traj, slug),
                    f"required: the {away}-{home} game center")
    judge.check("visited_standings", navigated_to(traj, "/standings"),
                "required: /standings/ (undefeated check)")
    judge.check("visited_video_hub", navigated_to(traj, "/videos"),
                "required: the video hub (preview discovery)")
    # r3 depth rings: every preview video page must have been opened (its
    # channel and Up Next list are only rendered there)...
    for slug in PREVIEW_SLUGS:
        judge.check(f"visited_preview_{slug.split('-week-3')[0]}",
                    navigated_to(traj, slug),
                    f"required: the preview video page {slug}")
    # ...and the TNF storylines article must have been opened
    judge.check("visited_storylines_article",
                navigated_to(traj, STORYLINES[0]),
                "required: the TNF must-know-storylines news article")
    # answer gates per window
    for tag, (away, home, kickoff, network, stadium, (aw_w, aw_l), (h_w, h_l)) in WINDOWS:
        judge.check(f"answer_{tag}_matchup",
                    contains_phrase(answer, away) and contains_phrase(answer, home),
                    f"expected {away} at {home}")
        judge.check(f"answer_{tag}_kickoff", contains_time(answer, kickoff),
                    f"expected the {kickoff} ET kickoff")
        judge.check(f"answer_{tag}_network", contains_phrase(answer, network),
                    f"expected {network}")
        judge.check(f"answer_{tag}_stadium", contains_phrase(answer, stadium),
                    f"expected {stadium}")
        judge.check(f"answer_{tag}_records",
                    contains_record(answer, aw_w, aw_l) and contains_record(answer, h_w, h_l),
                    f"expected {away} {aw_w}-{aw_l} and {home} {h_w}-{h_l}")
    judge.check("answer_undefeated_eagles", contains_phrase(answer, UNDEFEATED),
                f"expected the {UNDEFEATED} as the still-undefeated team")
    missing_previews = [p for p in PREVIEWS if p not in answer]
    judge.check("answer_preview_titles", not missing_previews,
                f"expected all three preview titles; missing {missing_previews!r}")
    # r3 depth rings: each preview's channel + its first Up Next video.
    # The SNF preview's first Up Next (Vikings vs. Buccaneers) is unique, so it
    # is gated strictly; the TNF and MNF previews' first Up Next both equal the
    # SNF preview's title, so an honest full answer mentions that title three
    # times (once as the SNF title, twice as Up Next) — gate on the count.
    judge.check("answer_preview_channel",
                contains_phrase(answer, PREVIEW_CHANNEL),
                "expected the previews' channel (Latest Buzz)")
    judge.check("answer_upnext_snf_unique",
                contains_phrase(answer, "Vikings vs. Buccaneers Week 3 Preview"),
                "expected the SNF preview's first Up Next: 'Vikings vs. Buccaneers Week 3 Preview'")
    a_norm = answer.lower()
    colliding = a_norm.count("rams vs. broncos week 3 preview")
    judge.check("answer_upnext_colliding_pair",
                colliding >= 3,
                "expected the 'Rams vs. Broncos Week 3 Preview' title plus its two Up Next "
                "mentions (TNF and MNF previews' first Up Next); found "
                f"{colliding} occurrences")
    judge.check("answer_storylines_author", contains_phrase(answer, STORYLINES[1]),
                f"expected the storylines article's author {STORYLINES[1]}")
    judge.check("answer_storylines_date", contains_date(answer, STORYLINES[2]),
                "expected the storylines article's date September 23, 2026")
    check_read_only_db(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
