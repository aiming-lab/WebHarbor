#!/usr/bin/env python3
"""Versus--5: sign in as Alice and report one comparison already saved to the account."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V

EMAIL = "alice.j@test.com"


def body(j, traj, initial, after):
    before = V.saved_pairs(initial, EMAIL)
    if not before:
        return j.fail("seed data missing",
                      "the account has no saved comparisons in initial_db")

    ans = V.final_answer(traj)
    names = {p["slug"]: p["name"] for p in V.products(initial)}

    j.check("signed in", V.navigated_to(traj, "/login"),
            f"steps={V.step_urls(traj)[:6]}")
    j.check("opened the account page", V.navigated_to(traj, "/account"),
            f"steps={V.step_urls(traj)}")
    V.terminal_state_is_sound(j, traj)

    # Which seeded pair does the answer name? Both product names must appear.
    matched = [pair for pair in before
               if all(V.claims_product(ans, names[slug]) for slug in pair)]
    j.check("answer names both products of one comparison already on the account",
            len(matched) >= 1,
            f"seeded pairs={sorted(map(sorted, before))} answer={ans!r}")

    # The reported comparison must be one that was already there, not one the
    # agent created during the run.
    now = V.saved_pairs(after, EMAIL)
    if now is not None:
        added = now - before
        j.check("did not report a comparison it created during the run",
                not (added and matched and set(matched) <= added),
                f"added during run={sorted(map(sorted, added))}")

    if matched:
        pair = sorted(matched[0])
        ok, why = V.llm_text_match(
            ans, " vs ".join(names[s] for s in pair),
            "one comparison already saved to the signed-in account")
        j.check("anchored LLM agreement", ok, why, llm=True)


if __name__ == "__main__":
    V.run("Versus--5", body)
