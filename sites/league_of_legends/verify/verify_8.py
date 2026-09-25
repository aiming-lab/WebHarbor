#!/usr/bin/env python3
"""Verify League of Legends--8: news curation (page 2 + Lore) -> bookmark -> verify.

Honest chain (16 atomic actions): News nav -> Older» (page 2) -> Dev chip ->
Lore chip -> open 'Previously on Star Guardian' -> back -> open 'The Council
Archives Primer' -> back -> open 'Previously on Star Guardian' again ->
Sign in to Save -> fill email -> fill password -> submit -> Save Article ->
My Account -> answer.

Frozen ground truth (seed DB):
  * News hub page 2 (24 per page, newest first) starts with 'What would a
    "League Classic Viego" Look Like?' (2026-08-06, external card).
  * Lore category: exactly 2 articles — 'Previously on Star Guardian'
    (2022-07-09, id 183) and 'The Council Archives Primer' (2021-11-08, id 225).
  * david_k (id 4) gains exactly one bookmark row ('Previously on Star
    Guardian', article id 183) -> 5 saved articles total.
"""
from verify_lib import (bound_phrase, check_bookmarks_delta,
                        check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_iso_date, contains_phrase, contains_phrase_loose,
                        final_answer, navigated_category, navigated_news_page,
                        navigated_to_path, navigated_to_path_any, run_verifier)

TASK_ID = "League of Legends--8"
EMAIL = "david.k@test.com"
STAR_GUARDIAN = (4, 183, "2026-09-22")
LORE_SG = "/news/lore/previously-on-star-guardian/"
LORE_COUNCIL = "/news/lore/the-council-archives-primer/"
SG_TITLE = "Previously on Star Guardian"
COUNCIL_TITLE = "The Council Archives Primer"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_news_page_2", navigated_news_page(traj, 2),
                "required: /news/ with page=2")
    judge.check("visited_lore_category", navigated_category(traj, "lore"),
                "required: /news/lore")
    judge.check("visited_star_guardian_article", navigated_to_path(traj, LORE_SG),
                f"required: {LORE_SG}")
    judge.check("visited_council_article", navigated_to_path(traj, LORE_COUNCIL),
                f"required: {LORE_COUNCIL}")
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_bookmarks",
                navigated_to_path_any(traj, ["/account", "/account/bookmarks"]),
                "required: /account or /account/bookmarks")

    judge.check("answer_page2_first_title",
                contains_phrase_loose(answer, "What would a League Classic Viego Look Like"),
                "expected the page-2 first article title")
    judge.check("answer_page2_first_date", contains_iso_date(answer, "2026-08-06"),
                "expected the page-2 first article date 2026-08-06")
    judge.check("answer_lore_count_2", contains_count(answer, 2),
                "expected the Lore category's 2 articles")
    judge.check("answer_star_guardian_title",
                contains_phrase(answer, SG_TITLE),
                f"expected {SG_TITLE!r} titled")
    judge.check("answer_council_title",
                contains_phrase(answer, COUNCIL_TITLE),
                f"expected {COUNCIL_TITLE!r} titled")
    judge.check("answer_star_guardian_is_recap",
                bound_phrase(answer, "recap", SG_TITLE, [COUNCIL_TITLE], mode="after",
                             allow_misbound=True, only_if_present=True),
                f"expected any 'recap' characterisation attached to {SG_TITLE!r}")
    judge.check("answer_council_is_primer",
                bound_phrase(answer, "primer", COUNCIL_TITLE, [SG_TITLE], mode="after",
                             only_if_present=True),
                f"expected any 'primer' characterisation attached to {COUNCIL_TITLE!r}")
    judge.check("answer_bookmarked_recap",
                contains_phrase(answer, SG_TITLE),
                "expected the Star Guardian recap named as the bookmarked article")
    judge.check("answer_new_total_5", contains_count(answer, 5),
                "expected the account's new total of 5 saved articles")

    check_bookmarks_delta(judge, initial_db, after_db, added=[STAR_GUARDIAN])
    check_only_tables_changed(judge, initial_db, after_db, {"bookmark_articles"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
