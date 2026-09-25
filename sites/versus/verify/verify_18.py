#!/usr/bin/env python3
"""Versus--18: population of the largest city by area.

Deliberately keyed on area rather than population: an earlier version asked for
the area of the most populous city, which centred on the same entity and the
same figure as Versus--17, and the adversarial wrong-task replay caught one
run satisfying the other's checks.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    rows = V.products(initial, "cities")
    if not rows:
        return j.fail("seed data missing", "no cities in initial_db")
    target = V.unique_extreme(rows, "spec_2_value", largest=True)     # area
    if target is None:
        return j.fail("ambiguous ground truth", "no unique largest area")
    expected = target["spec_1_value"]                                 # population
    most_populous = V.unique_extreme(rows, "spec_1_value", largest=True)

    ans = V.terminal_state_is_sound(j, traj)
    j.check("opened the fact-bearing page for the largest city by area",
            V.opened_detail_or_compare(traj, target["slug"]),
            f"slug={target['slug']} steps={V.step_urls(traj)[-6:]}")
    j.check("answer names the largest city by area",
            V.mentions_product(ans, target["name"]),
            f"expected={target['name']!r} at {target['spec_2_value']} km2")
    j.check("answer states that city's population",
            V.claims_number(ans, expected, tol=1.0), f"expected={expected}")
    if most_populous and most_populous["slug"] != target["slug"]:
        j.check("answer is not about the most populous city instead",
                not (V.mentions_product(ans, most_populous["name"])
                     and not V.mentions_product(ans, target["name"])),
                f"distractor={most_populous['name']!r}")
    ok, why = V.llm_text_match(ans, f"{target['name']} — {expected} people",
                               "population of the city with the largest area")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--18", body)
