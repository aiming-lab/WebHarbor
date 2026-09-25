#!/usr/bin/env python3
"""Versus--14: benchmark score of the winner of RTX 4070 Super vs RX 7800 XT."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    left = V.product(initial, "rtx-4070-super")
    right = V.product(initial, "radeon-rx-7800-xt")
    if not (left and right):
        return j.fail("seed data missing", "one of the two products is not in initial_db")
    if left["score"] == right["score"]:
        return j.fail("ambiguous ground truth",
                      "the two products tie on score in initial_db")
    target = left if left["score"] > right["score"] else right
    expected = target["spec_3_value"]

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
                               "benchmark score of the winner of the two graphics cards")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--14", body)
