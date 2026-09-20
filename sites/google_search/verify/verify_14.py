#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--14.

Find the retired players the year before last named James Smith and tell me which club he has been a member of from 2020–2021.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's James Smith (retired footballer 2020-2021) player pages
    (Transfermarkt, Sky Sports, Soccerway, EFL database) all show his club
    history: 2020-21 Mansfield Town (Fourth tier, 38 apps, 2 goals);
    2019-20 Mansfield Town; 2021-22/2022-23 Wycombe Wanderers; 2017-19
    Stevenage. The club he was a member of in the 2020-2021 season is
    Mansfield Town.
Source pages: www.transfermarkt.com/james-smith and Sky Sports / Soccerway player pages

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a James Smith search | a player page opened | answer: the club for the
  2020-21 season
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--14', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["james", "smith"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-014-", "james-smith", "James_Smith_(footballer"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_club_2020_21", contains_any(fa, ["mansfield"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
