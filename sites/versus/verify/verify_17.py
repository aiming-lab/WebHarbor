#!/usr/bin/env python3
"""Versus--17: larger of two named cities by area."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V

LEFT, RIGHT = "shanghai", "beijing"


def body(j, traj, initial, after):
    left, right = V.product(initial, LEFT), V.product(initial, RIGHT)
    if not (left and right):
        return j.fail("seed data missing", "one of the two cities is not in initial_db")
    if left["spec_2_value"] == right["spec_2_value"]:
        return j.fail("ambiguous ground truth", "the two cities tie on area")
    target = left if left["spec_2_value"] > right["spec_2_value"] else right
    other = right if target is left else left
    expected = target["spec_2_value"]

    ans = V.terminal_state_is_sound(j, traj)
    j.check("opened the comparison or both detail pages",
            V.navigated_to(traj, f"/compare/{LEFT}-vs-{RIGHT}")
            or V.navigated_to(traj, f"/compare/{RIGHT}-vs-{LEFT}")
            or (V.opened_detail_or_compare(traj, LEFT)
                and V.opened_detail_or_compare(traj, RIGHT)),
            f"steps={V.step_urls(traj)[-6:]}")
    j.check("answer names the larger city by area",
            V.mentions_product(ans, target["name"]),
            f"expected={target['name']!r} ({expected} vs {other['spec_2_value']})")
    j.check("answer states that area",
            V.claims_number(ans, expected, tol=1.0), f"expected={expected}")
    ok, why = V.llm_text_match(ans, f"{target['name']} — {expected} km2",
                               "which of the two cities is larger by area, and that area")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--17", body)
