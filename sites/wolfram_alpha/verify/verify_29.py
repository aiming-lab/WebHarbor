#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--29.

Task: Create a plot of cat curve using wolfram alpha.

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    The verbatim wording is rejected by the mirror's gate;
    /input?i=cat curve (parsed 'cat curve (Wolfram named curve)') or
    /input?i=plot cat curve (parsed 'cat curve (popular curve) | plot')
    render the cat-curve pods; the 'plot cat curve' query additionally
    shows the rendered plot image (static/images/topics/cat-curve.png):
      Plot: silhouette of a cat traced parametrically over t in [0, 2 pi]
      Parametric equations: x(t), y(t) Fourier series (~30+ coefficients)
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
    j = Judge('Wolfram Alpha--29', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_cat_curve_input_query",
          queried_with_all(t, must_all=[],
                          any_of=[['catcurve', 'cat-curve', 'cat curve']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'create a plot of cat', 'plot of cat curve using', 'cat curve using wolfram alpha', 'plot the cat curve', 'using wolfram alpha', 'create a plot']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_cat_curve_plot", contains_any(fa, ["catcurve", "cat curve", "cat-curve"]) and contains_any(fa, ["plot", "fourier", "parametric", "silhouette", "silhouette", "animal"]), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
