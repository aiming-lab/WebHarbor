#!/usr/bin/env python3
"""Verify League of Legends--10: Vanguard rollout (3 articles) -> bookmark.

Honest chain (16 atomic actions): Play Now -> Sign In -> fill email -> fill
password -> submit -> search icon -> fill q='Vanguard' -> Search -> open
'/dev: Vanguard x LoL' -> back -> open 'TL;DW: Gameplay, Vanguard & More Dev
Update' -> back -> open '/dev: Vanguard x LoL Retrospective' -> Save Article ->
My Account -> answer.

Frozen ground truth (seed DB):
  * /search?q=Vanguard reports News (3) and a single champion card: Garen.
  * '/dev: Vanguard x LoL' (2024-04-11, dev, id 107)
  * 'TL;DW: Gameplay, Vanguard & More Dev Update' (2024-02-29, dev, id 235)
  * '/dev: Vanguard x LoL Retrospective' (2024-08-22, dev, id 108) —
    'we have banned over 175,000 accounts for cheating'; 'our Ranked
    scripting rate fell below 1% for the first time in nearly four years'.
  * alice_j (id 1) gains exactly one bookmark row (Retrospective, article id 108)
    -> 5 saved articles total.
"""
from verify_lib import (bound_count, bound_date, champion_named,
                        check_bookmarks_delta, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity,
                        contains_any, contains_count, contains_phrase,
                        contains_phrase_loose, final_answer, navigated_search_with,
                        navigated_to_path, navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--10"
EMAIL = "alice.j@test.com"
RETROSPECTIVE_BM = (1, 108, "2026-09-22")
VANGUARD_ANNOUNCE = "/news/dev/dev-vanguard-x-lol/"
VANGUARD_TLDW = "/news/dev/tl-dw-gameplay-vanguard-more-dev-update/"
VANGUARD_RETRO = "/news/dev/dev-vanguard-x-lol-retrospective/"
TLDW_TITLE = "TL;DW"
ANNOUNCE_TITLE = "Vanguard x LoL"
RETRO_TITLE = "Retrospective"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_search_vanguard",
                navigated_search_with(traj, ["vanguard"]),
                "required: /search with q containing 'vanguard'")
    judge.check("visited_announce_article", navigated_to_path(traj, VANGUARD_ANNOUNCE),
                f"required: {VANGUARD_ANNOUNCE}")
    judge.check("visited_tldw_article", navigated_to_path(traj, VANGUARD_TLDW),
                f"required: {VANGUARD_TLDW}")
    judge.check("visited_retro_article", navigated_to_path(traj, VANGUARD_RETRO),
                f"required: {VANGUARD_RETRO}")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_bookmarks",
                navigated_to_path_any(traj, ["/account", "/account/bookmarks"]),
                "required: /account or /account/bookmarks")

    judge.check("answer_news_results_3", contains_count(answer, 3),
                "expected 3 news results reported")
    judge.check("answer_garen_card", champion_named(answer, "Garen"),
                "expected Garen named as the single matching champion card")
    judge.check("answer_tldw_title",
                contains_phrase_loose(answer, "TL;DW Gameplay, Vanguard & More Dev Update"),
                "expected the TL;DW article titled")
    judge.check("answer_tldw_date",
                bound_date(answer, "2024-02-29", TLDW_TITLE, [ANNOUNCE_TITLE, RETRO_TITLE], mode="after"),
                "expected the TL;DW date 2024-02-29 attached to the TL;DW article")
    judge.check("answer_announce_title", contains_phrase(answer, "/dev: Vanguard x LoL") or
                contains_phrase_loose(answer, "dev Vanguard x LoL"),
                "expected '/dev: Vanguard x LoL' titled")
    judge.check("answer_announce_date",
                bound_date(answer, "2024-04-11", ANNOUNCE_TITLE, [TLDW_TITLE, RETRO_TITLE], mode="after"),
                "expected the announcement date 2024-04-11 attached to the announcement")
    judge.check("answer_retro_title",
                contains_phrase_loose(answer, "Vanguard x LoL Retrospective"),
                "expected the retrospective titled")
    judge.check("answer_retro_date",
                bound_date(answer, "2024-08-22", RETRO_TITLE, [TLDW_TITLE, ANNOUNCE_TITLE], mode="after"),
                "expected the retrospective date 2024-08-22 attached to the retrospective")
    judge.check("answer_banned_175k",
                bound_count(answer, 175000, RETRO_TITLE, [TLDW_TITLE, ANNOUNCE_TITLE], mode="after"),
                "expected over 175,000 banned accounts attached to the retrospective")
    judge.check("answer_scripting_below_1pct",
                contains_any(answer, ["below 1%", "under 1%", "less than 1%",
                                      "1 in every 200", "1 in 200"]),
                "expected the Ranked scripting rate below 1%")
    judge.check("answer_new_total_5", contains_count(answer, 5),
                "expected the account's new total of 5 saved articles")

    check_bookmarks_delta(judge, initial_db, after_db, added=[RETROSPECTIVE_BM])
    check_only_tables_changed(judge, initial_db, after_db, {"bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
