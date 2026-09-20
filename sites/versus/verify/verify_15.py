#!/usr/bin/env python3
"""Versus--15: area of a named city, reached through the site."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V

SLUG = "shanghai"


def body(j, traj, initial, after):
    target = V.product(initial, SLUG)
    if not target:
        return j.fail("seed data missing", f"{SLUG} is not in initial_db")
    expected = target["spec_2_value"]

    ans = V.terminal_state_is_sound(j, traj)
    j.check("reached the city through the site",
            V.navigated_any(traj, [f"/category/{target['category_slug']}", "/rankings", "/search"]),
            f"steps={V.step_urls(traj)[:6]}")
    j.check("opened the fact-bearing page for the city",
            V.opened_detail_or_compare(traj, SLUG), f"steps={V.step_urls(traj)[-6:]}")
    j.check("answer states the derived area",
            V.claims_number(ans, expected, tol=1.0),
            f"expected={expected} {target['unit_2']} from initial_db")
    j.check("answer does not report the population instead",
            not V.claims_number(ans, target["spec_1_value"], tol=1.0)
            or V.claims_number(ans, expected, tol=1.0),
            "population and area must not be confused")
    ok, why = V.llm_text_match(ans, f"{expected} {target['unit_2']}",
                               "area in square kilometres of the named city")
    j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--15", body)
