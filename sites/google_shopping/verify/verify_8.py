#!/usr/bin/env python3
"""Verify the St Barts 'Compare with similar items' composition report in Google Shopping--8.

Re-anchored in the contributor's reviewer-round fix (b41595ff): the asked facts are the
rail's merchant mix and order — both rendered only on the product panel. The catalog holds
4 TikTok Shop products but the rail (first 8 eyewear rows by position, excluding St Barts)
lists only 3 of them, so no search-results surface (including the store-filtered one that
shows 4 cards) reveals the asked count.
"""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Google Shopping--8"
PRODUCT_PATH = "/product/gsd18d8163a9c64bef"  # St Barts Bluelight (VZN Frames)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Compare-with-similar rail is rendered only on the product page.
    check_visited_path(judge, traj, "visited_st_barts_product_page", PRODUCT_PATH)
    # Frozen ground truth (seed DB): the St Barts rail lists the first 8 eyewear rows by
    # position (excluding St Barts): [AE Classic, Arlo Oval, BlockBlueLight Billie,
    # BlockBlueLight Taylor, Walmart Square Nerd, TikTok $9.99, TikTok $17.00,
    # TikTok 2-Pack $3.16]. TikTok Shop sells 3 of the 8 listed products (the catalog's
    # 4th TikTok row sits outside the rail), and the second listed product is
    # 'Arlo Oval Blue Light Glasses' (edikted).
    judge.check("answer_rail_tiktok_count", contains_count(answer, 3),
                "expected 3 products sold by TikTok Shop in the rail")
    judge.check("answer_rail_second_title",
                contains_phrase(answer, "Arlo Oval Blue Light Glasses"),
                "expected 'Arlo Oval Blue Light Glasses' as the second listed product")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
