#!/usr/bin/env python3
"""Verify the filtered+sorted cheapest result report in Google Shopping--4."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_phrase,
                        contains_price, final_answer, run_verifier, site_urls,
                        normalized_url_path, _query_params, normalize_text)
import re

TASK_ID = "Google Shopping--4"


def _visited_filtered_sorted_search(traj):
    """A /search?q=trench coat... visit carrying price_max=100 and sort=price_asc
    (the agent may type 100, 100.0 or 100.00 into the Max filter)."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        q = _query_params(u)
        q_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(" ".join(q.get("q", [])))))
        if not {"trench", "coat"}.issubset(q_tokens):
            continue
        try:
            price_max = float(q.get("price_max", [""])[0])
        except (ValueError, IndexError):
            continue
        if price_max == 100.0 and "price_asc" in q.get("sort", []):
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_filtered_sorted_search", _visited_filtered_sorted_search(traj),
                "required=/search?q=trench coat with price_max=100 and sort=price_asc")
    # Frozen ground truth (seed DB): cheapest catalog trench coat priced <= $100 is
    # 'Women's Loft Drapey Trench Coat' at $51.95 (LOFT, 74% OFF).
    judge.check("answer_cheapest_title", contains_phrase(answer, "Women's Loft Drapey Trench Coat"),
                "expected 'Women's Loft Drapey Trench Coat'")
    judge.check("answer_cheapest_price", contains_price(answer, 51.95), "expected $51.95")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
