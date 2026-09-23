#!/usr/bin/env python3
"""Verify the UNIQLO 'Compare with similar items' composition report in Google Shopping--15.

Audit re-anchor (same class as the reviewer's T8/T12 round-2/3 fixes): the original
answer facts (merchant / current price / was price) are rendered on the UNIQLO search
card too, so the task leaked its whole answer on a cheaper surface. The new anchor is
the rail's merchant mix and order — both rendered only on the product panel. The
catalog holds 3 yoox.com products but the rail (first 8 'Trench Coats' category rows by
position, excluding UNIQLO) lists only 2 of them, so the store-filtered face that
shows 3 cards cannot derive the asked count, and no search face conveys rail order.
"""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer, run_verifier)

TASK_ID = "Google Shopping--15"
PRODUCT_PATH = "/product/gs266d85b487aa667d"  # UNIQLO Women's Trench Coat


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gate: the Compare-with-similar rail is rendered only on the product page.
    check_visited_path(judge, traj, "visited_uniqlo_product_page", PRODUCT_PATH)
    # Frozen ground truth (seed DB): the UNIQLO rail lists the first 8 'Trench Coats'
    # category rows by position (excluding UNIQLO): [AMUR Edikted Women's Amur Maxi
    # Trench Coat, Aritzia Women's The Finch Trench Coat, COTTON TRENCH COAT,
    # Clarissa | Belted Long Trench Coat - Khaki / M - Harper & Wells, Denim Trench
    # Coat Jacket by Pilcro in Dark Wash, Edikted Women's Amur Maxi Trench Coat in
    # Camel - Size XS, Eliza | Women's Double Breasted Trench Coat, Full-length
    # jacket]. yoox.com sells 2 of the 8 listed products (the catalog's 3rd yoox row
    # sits outside the rail), and the first listed product is 'AMUR Edikted Women's
    # Amur Maxi Trench Coat' (edikted).
    judge.check("answer_rail_yoox_count", contains_count(answer, 2),
                "expected 2 products sold by yoox.com in the rail")
    judge.check("answer_rail_first_title",
                contains_phrase(answer, "AMUR Edikted Women's Amur Maxi Trench Coat"),
                "expected 'AMUR Edikted Women's Amur Maxi Trench Coat' as the first listed product")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
