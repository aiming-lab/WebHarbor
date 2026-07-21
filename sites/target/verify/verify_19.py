#!/usr/bin/env python3
"""Deterministic verifier for Target--19 (stateful: write a product review).

Sign in as carol.d@test.com, open the Beats Pill Wireless Bluetooth Speaker,
and post a 4-star review headlined "Great sound for the size".

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT92595737 (Beats Pill Wireless Bluetooth Speaker).
  A new reviews row for that product with rating = 4 and
  title = "Great sound for the size", authored by carol.d's display name.

Rating and headline are dictated by the task. Checking them separately matters:
the review form defaults to no rating, so an agent that types the headline but
skips the star selector produces a row that looks nearly right.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        resolve_db, db_query, llm_screenshot_shows,
                        Judge, parse_args)

SKU = "TGT92595737"
HEADLINE = "Great sound for the size"
RATING = 4


def reviews_for(db_path, sku):
    """[(title, rating, author_name)] on this product, oldest first."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT r.title, r.rating, r.author_name FROM reviews r "
        "JOIN products p ON p.id = r.product_id WHERE p.sku = ? ORDER BY r.id", (sku,))
    return [tuple(r) for r in rows]


def main():
    a = parse_args()
    j = Judge("Target--19", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before = reviews_for(initial, SKU)
    now = reviews_for(after, SKU)

    j.check("db_readable", before is not None and now is not None,
            f"before={before} after={now}")

    if before is not None and now is not None:
        j.check("one_new_review", len(now) == len(before) + 1,
                f"before={len(before)} after={len(now)}")
        created = [row for row in now if row not in before]
        match = next((r for r in created if r[0].strip() == HEADLINE), None)
        j.check("headline_matches_task", match is not None,
                f"new reviews={created} (expected headline {HEADLINE!r})")
        # The star selector starts empty; a missed selection is the common miss.
        j.check("rating_is_four", bool(match) and match[1] == RATING,
                f"rating={match[1] if match else None} (expected {RATING})")
        j.check("existing_reviews_intact", all(r in now for r in before),
                f"before={before} after={now}")
    else:
        for name in ("one_new_review", "headline_matches_task",
                     "rating_is_four", "existing_reviews_intact"):
            j.check(name, False, "DB unavailable")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"a review titled {HEADLINE!r} on the product page",
                                      "the product page after the review was posted")
        j.check("screenshot_shows_review", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_review", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
