#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--25.

Task: Calculate the final position and velocity of a projectile launched at 45 degrees with an initial speed of 30 m/s after 3 seconds.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=projectile 30 m/s 45 degrees, t=3 s (parsed 'projectile
    path | release angle 45 | initial speed 30 m/s | t = 3 s') renders
    the Results pod:
      horizontal distance traveled: 63.64 m
      maximum height reached: 15.91 m
      gravitational acceleration: 9.81 m/s^2
    plus the Equations pod x(t) = 30 cos(45) t, y(t) = 30 sin(45) t - (1/2)(9.81) t^2
    (the mirror reports range and max height; velocity/height at t=3 s
    are derivable from those equations: vx = 21.21 m/s, y(3) = 19.49 m, vy = -8.22 m/s).
Checks (deterministic only): run-package gate + non-empty answer +
read-only user-state DB + /input navigation (anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, input_queries, queried_with_all,
                        math_norm, norm, contains_all, contains_any,
                        decimal_in, count_named, bound, bound_nearest,
                        bound_preceding, in_order, value_unit,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Wolfram Alpha--25', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_projectile_input_query",
          queried_with_all(t, must_all=['projectile', '30'],
                          any_of=[['45'], ['3']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'calculate the final position', 'projectile launched at 45', 'with an initial speed of 30', 'after 3 seconds', 'final position', 'final velocity']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_horizontal_distance", bound_preceding(fa, ["x", "distance", "range", "horizontal", "travels", "travelled", "traveled", "lands", "away"], ["63.64"], other_anchors=["y", "height", "apex", "peak", "maximum", "max"]), f"final={fa[:200]!r}")
    j.check("answer_height_or_velocity", (bound_preceding(fa, ["y", "height", "apex", "peak", "maximum", "max"], ["15.91", "19.49"], other_anchors=["x", "distance", "range", "horizontal", "travels", "travelled", "traveled", "lands", "away"]) or decimal_in(fa, "21.21", tol=0.05) or decimal_in(fa, "8.22", tol=0.05)), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
