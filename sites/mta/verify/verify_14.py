#!/usr/bin/env python3
"""Verify MTA--14.

Journalist covering the next MTA Board meeting: when is the next committee
and board meeting on the 2026 meeting calendar, where are meetings typically
held, name two current board members with their titles, and find the recent
press release announcing the upcoming meeting dates.

Frozen ground truth (seed DB): the next meetings after the pinned date are
"September 28 and September 30, 2026: MTA Committee and Regular Board
Meetings" (Monday Sep 28 / Wednesday Sep 30), typically held the fourth
week of each month at the MTA Board Room, 2 Broadway, 20th Floor. Board
members (board-members page): Andrew Albert, Gerard Bringmann, Samuel Chu,
Michael Fleischer, Daniel Garodnick, Randolph Glucksman, Melanie Hartzog,
Marc Herbst, David R. Jones, Christopher Leathers, Blanca P. Lopez, Haeda
B. Mihaltses, Melva M. Miller, James O'Donnell, Matt Rand, John-Ross Rizzo,
Janette Sadik-Khan, John Samuelsen, Lisa Sorin, Edward Valente, Neal
Zuckerman (listed as members); Janno Lieber is Chair and CEO (executive
leadership page). Press release of September 17, 2026: "MTA Committee and
Board Meetings to Be Held Monday, September 28, and Wednesday, September 30".
r2 sync (deepened task @ f5dbe72d): new sub-ask ground truths verified live in the r2 re-review walks; see the extended judge_rubric in tasks.jsonl.
"""

from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_count, contains_phrase, final_answer, navigated_to, navigated_to_path, run_verifier)

TASK_ID = "MTA--14"
BOARD_MEMBERS = ["andrew albert", "gerard bringmann", "samuel chu", "michael fleischer",
                 "daniel garodnick", "randolph glucksman", "melanie hartzog", "marc herbst",
                 "david r. jones", "christopher leathers", "blanca p. lopez",
                 "haeda b. mihaltses", "melva m. miller", "james o'donnell", "matt rand",
                 "john-ross rizzo", "janette sadik-khan", "john samuelsen", "lisa sorin",
                 "edward valente", "neal zuckerman"]
EXEC_TITLES = ["chair and ceo", "chair", "ceo", "member"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_board_meetings",
                navigated_to_path(traj, "/transparency/board-and-committee-meetings"),
                "required: /transparency/board-and-committee-meetings")
    judge.check("visited_board_members_or_leadership",
                navigated_to_path(traj, "/transparency/leadership/board-members")
                or navigated_to_path(traj, "/transparency/leadership/executive-leadership"),
                "required: a board-members / executive-leadership page")
    judge.check("visited_press_release",
                navigated_to(traj, "/press-release/mta-committee-and-board-meetings")
                or navigated_to(traj, "/press-release/"),
                "required: a press-release article page")
    judge.check("answer_sept_28", contains_phrase(answer, "september 28"),
                "next committee/board meetings: Monday, September 28, 2026")
    judge.check("answer_sept_30", contains_phrase(answer, "september 30"),
                "and Wednesday, September 30, 2026")
    judge.check("answer_location_2_broadway",
                contains_phrase(answer, "2 broadway"),
                "meetings are held at the MTA Board Room, 2 Broadway, 20th Floor")
    named = [m for m in BOARD_MEMBERS if m in answer.lower()]
    judge.check("answer_two_board_members", len(named) >= 2 or "lieber" in answer.lower(),
                f"must name two board members (found: {named[:4]})")
    judge.check("answer_titles",
                any(t in answer.lower() for t in EXEC_TITLES),
                "must give titles (e.g. Chair and CEO / Member)")
    judge.check("visited_budget_page", navigated_to_path(traj, "/budget"),
                "required: /budget")
    judge.check("visited_foil_page", navigated_to_path(traj, "/transparency/foil"),
                "required: /transparency/foil")
    judge.check("answer_watch_livestream",
                contains_any_phrase(answer, ["livestream", "live stream", "webcast", "recordings",
                                             "streaming", "streamed", "watch online"]),
                "meetings are livestreamed and recordings are posted")
    judge.check("answer_budget_largest_revenue",
                contains_phrase(answer, "dedicated taxes") and
                (contains_count(answer, 55) or contains_phrase(answer, "55%")),
                "largest revenue source: 55% dedicated taxes and subsidies")
    judge.check("answer_foil_online_portal",
                contains_any_phrase(answer, ["online portal", "submit your request online",
                                             "through our online portal"]),
                "the best way to submit a FOIL request is the online portal")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
