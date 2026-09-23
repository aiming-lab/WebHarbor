#!/usr/bin/env python3
"""Verify the trench price-range search report in Google Shopping--6."""


from verify_lib import (Judge, check_read_only, check_trajectory_identity, contains_count,
                        contains_phrase, contains_price, final_answer, run_verifier, site_urls,
                        normalized_url_path, _query_params, normalize_text)
import re

TASK_ID = "Google Shopping--6"


def _visited_range_search(traj):
    """A /search?q=trench visit carrying price_min=50 and price_max=100 (any numeric spelling)."""
    for u in site_urls(traj):
        if normalized_url_path(u) != "/search":
            continue
        q = _query_params(u)
        q_tokens = set(re.findall(r"[a-z0-9]+", normalize_text(" ".join(q.get("q", [])))))
        if "trench" not in q_tokens:
            continue
        try:
            price_min = float(q.get("price_min", [""])[0])
            price_max = float(q.get("price_max", [""])[0])
        except (ValueError, IndexError):
            continue
        if price_min == 50.0 and price_max == 100.0:
            return True
    return False


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_price_range_search", _visited_range_search(traj),
                "required=/search?q=trench with price_min=50 and price_max=100")
    # Frozen ground truth (seed DB): 12 trench results in [$50,$100]; the most expensive
    # in range is 'Trenchcoat' at $88.00 sold by NOBA.
    judge.check("answer_result_count", contains_count(answer, 12), "expected 12 results")
    judge.check("answer_most_expensive_merchant", contains_phrase(answer, "NOBA"),
                "expected merchant NOBA")
    judge.check("answer_most_expensive_price", contains_price(answer, 88.00), "expected $88.00")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
