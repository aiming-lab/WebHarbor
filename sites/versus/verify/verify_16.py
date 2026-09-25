#!/usr/bin/env python3
"""Versus--16: enrolment of the longest-teaching university."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    rows = V.products(initial, "universities")
    if not rows:
        return j.fail("seed data missing", "no universities in initial_db")
    target = V.unique_extreme(rows, "spec_2_value", largest=False)   # earliest founding year
    if target is None:
        return j.fail("ambiguous ground truth", "no unique earliest founding year")
    expected = target["spec_1_value"]

    ans = V.terminal_state_is_sound(j, traj)
    j.check("opened the fact-bearing page for the target university",
            V.opened_detail_or_compare(traj, target["slug"]),
            f"slug={target['slug']} steps={V.step_urls(traj)[-6:]}")
    j.check("answer names the right university",
            V.mentions_product(ans, target["name"]), f"expected={target['name']!r}")
    j.check("answer states the derived enrolment",
            V.claims_number(ans, expected, tol=1.0), f"expected={expected}")
    ok, why = V.llm_text_match(ans, f"{target['name']} — {expected} students",
                               "student enrolment of the longest-teaching university")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--16", body)
