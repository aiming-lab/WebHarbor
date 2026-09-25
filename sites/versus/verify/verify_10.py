#!/usr/bin/env python3
"""Versus--10: longer battery of OnePlus 12 vs Pixel 8 Pro."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    left = V.product(initial, "oneplus-12")
    right = V.product(initial, "google-pixel-8-pro")
    if not (left and right):
        return j.fail("seed data missing", "one of the two products is not in initial_db")
    if left["battery_hours"] == right["battery_hours"]:
        return j.fail("ambiguous ground truth",
                      "the two products tie on battery_hours in initial_db")
    target = left if left["battery_hours"] > right["battery_hours"] else right
    expected = target["battery_hours"]

    ans = V.final_answer(traj)
    j.check("opened the comparison or both detail pages",
            V.navigated_to(traj, f"/compare/{left['slug']}-vs-{right['slug']}")
            or V.navigated_to(traj, f"/compare/{right['slug']}-vs-{left['slug']}")
            or (V.opened_detail_or_compare(traj, left["slug"])
                and V.opened_detail_or_compare(traj, right["slug"])),
            f"steps={V.step_urls(traj)[-6:]}")
    V.terminal_state_is_sound(j, traj)
    j.check("answer names the right product",
            V.mentions_product(ans, target["name"]), f"expected={target['name']!r}")
    j.check("answer states the derived value",
            V.claims_number(ans, expected), f"expected={expected} from initial_db")
    ok, why = V.llm_text_match(ans, f"{target['name']} — {expected}",
                               "which of the two phones lasts longer and for how many hours")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--10", body)
