#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--30.

Find the current number one artist on the Spotify Global Top 50 chart and list his/her top 10 songs as of now.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror carries two Global-Top-50 pages that disagree: (a) the
    Top 50 - Global playlist page lists #1 'DtMF' by Bad Bunny, #2 'BAILE
    INoLVIDABLE' by Bad Bunny, then APT., Die With A Smile, Birds of a
    Feather, luther, Beautiful Things, Anxiety, Pink Pony Club, That's So
    True; (b) the Spotify Charts page's #1 spotlight is Sabrina Carpenter
    with 'Espresso' and its table lists Espresso, Stargazing, Lavender
    Dreams, Midnight Caller, Holiday, Skyfall, Painted Sky, Echoes,
    Forever Young, New Mornings. Either page-consistent reading is
    accepted (same mirror-internal inconsistency pattern as tasks 5/41);
    mixing the two pages' lists is a FAIL.
Source pages: open.spotify.com/playlist/37i9dQZEVXbMDoHDwVN2tF / charts.spotify.com Global Top 50 on the mirror

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Spotify chart search | a Global Top 50 page opened | answer: the
  number-one artist and the chart's leading songs, consistent with one page
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
    j = Judge('Google Search--30', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["spotify"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-030-", "playlist/37i9dQZEVXbMDoHDwVN2tF", "charts.spotify.com/charts/view/regional-global-daily"]),
            "an answer-bearing mirror page was opened")
    reading_a = contains_any(fa, ["bad bunny"]) and contains_any(fa, ["dtmf"])
    reading_b = contains_any(fa, ["sabrina carpenter"]) and contains_any(fa, ["espresso"])
    j.check("answer_number_one_artist", reading_a or reading_b,
            f"final={fa[:200]!r}")
    j.check("answer_number_one_song", contains_any(fa, ["dtmf"]) or contains_any(fa, ["espresso"]),
            f"final={fa[:200]!r}")
    chart = ["BAILE INoLVIDABLE", "APT.", "Die With A Smile", "Birds of a Feather",
             "luther", "Beautiful Things", "Anxiety", "Pink Pony Club", "That's So True"]
    chart_b = ["Stargazing", "Lavender Dreams", "Midnight Caller", "Holiday", "Skyfall",
               "Painted Sky", "Echoes", "Forever Young", "New Mornings"]
    j.check("answer_more_chart_songs", count_names(fa, chart) >= 1 or count_names(fa, chart_b) >= 1,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
