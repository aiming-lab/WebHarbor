#!/usr/bin/env python3
"""Versus--6: display size of the top-scoring smartphone at $1000 or less."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    rows = V.products(initial, "smartphones")
    if not rows:
        return j.fail("seed data missing", "no products in category smartphones")
    rows = [r for r in rows if (r["price"] or 0) <= 1000]
    if not rows:
        return j.fail("ambiguous ground truth",
                      "no smartphone at or below the price limit in initial_db")
    target = V.unique_extreme(rows, "score", largest=True)
    if target is None:
        return j.fail("ambiguous ground truth",
                      "no unique extreme for score in initial_db")
    expected = target["spec_3_value"]

    ans = V.final_answer(traj)
    j.check("opened the fact-bearing page for the target product",
            V.opened_detail_or_compare(traj, target["slug"]),
            f"slug={target['slug']} steps={V.step_urls(traj)[-6:]}")
    V.terminal_state_is_sound(j, traj)
    j.check("answer names the right product",
            V.mentions_product(ans, target["name"]), f"expected={target['name']!r}")
    j.check("answer states the derived value",
            V.claims_number(ans, expected), f"expected={expected} from initial_db")
    ok, why = V.llm_text_match(ans, f"{target['name']} — {expected}",
                               "display size in inches of the highest scoring smartphone at $1000 or less")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--6", body)
