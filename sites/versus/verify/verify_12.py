#!/usr/bin/env python3
"""Versus--12: weight of the longest-lasting smartwatch."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    rows = V.products(initial, "smartwatches")
    if not rows:
        return j.fail("seed data missing", "no products in category smartwatches")
    target = V.unique_extreme(rows, "battery_hours", largest=True)
    if target is None:
        return j.fail("ambiguous ground truth",
                      "no unique extreme for battery_hours in initial_db")
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
                               "weight in grams of the smartwatch with the longest battery life")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--12", body)
