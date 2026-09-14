#!/usr/bin/env python3
"""Versus--11: Bob saves the Apple Watch Series 9 vs Garmin Venu 3 comparison."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as V


def body(j, traj, initial, after):
    email = "bob.c@test.com"
    pair = frozenset(({"apple-watch-series-9", "garmin-venu-3"}))
    before = V.saved_pairs(initial, email)
    now = V.saved_pairs(after, email)
    if before is None:
        return j.fail("initial_db unreadable", "cannot establish the before state")
    if now is None:
        return j.fail("after_db unavailable",
                      "a stateful task cannot be graded without the after state")
    if pair in before:
        return j.fail("task design error",
                      "the requested comparison is already saved in the seed, so the "
                      "after state would be identical whether or not the agent acted")

    ans = V.final_answer(traj)
    j.check("the answer was emitted from a page on this site",
            V.answered_on_site(traj),
            f"terminal url={(traj.get('steps') or [{}])[-1].get('url')!r}")
    j.check("reported what it did, without denying it",
            bool(ans) and not V.looks_negated(ans),
            f"answer={ans!r} (this task is graded on the state change; the report "
            f"must still exist and must not contradict it)")

    j.check("signed in", V.navigated_to(traj, "/login"),
            f"steps={V.step_urls(traj)[:6]}")
    j.check("opened the comparison page for the requested pair",
            V.navigated_to(traj, "/compare/apple-watch-series-9-vs-garmin-venu-3")
            or V.navigated_to(traj, "/compare/garmin-venu-3-vs-apple-watch-series-9"),
            f"steps={V.step_urls(traj)[-6:]}")
    j.check("the comparison is actually saved to that account",
            pair in now, f"account pairs after the run = {sorted(map(sorted, now))}")
    j.check("no unrelated comparison was added",
            len(now - before - {pair}) == 0,
            f"unexpected additions = {sorted(map(sorted, now - before - {pair}))}")


if __name__ == "__main__":
    V.run("Versus--11", body)
