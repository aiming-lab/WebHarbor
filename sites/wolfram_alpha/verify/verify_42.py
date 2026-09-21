#!/usr/bin/env python3
"""Deterministic verifier for Wolfram Alpha task Wolfram Alpha--42.

Task: What is the raw memory of a 100.2" * 123.5" true colour picture at 72 ppi?

Ground truth (hardcoded; read off the served mirror pages with a real
Chromium during the reviewer audit -- reports/wolfram_alpha/audit/; the
computation catalog is fixed by the seed DB, so no wall-clock or upstream
content is involved):
    /input?i=image 100.2 in by 123.5 in at 72 ppi (parsed 'image |
    display size 100.20 in x 123.50 in | pixel resolution 72 pixels/in')
    renders the Basic-properties pod:
      pixel dimensions: 7214 x 8892 px
      pixel count: 64.15 megapixels
      raw memory: 192 MB (24-bit true color)
        = 192.45 MB decimal  = 183.54 MiB binary
    (the verbatim wording renders the raw-memory formula record:
      bytes = pixel_width x pixel_height x bytes_per_pixel,
      true color = 24 bpp = 3 bytes/pixel)
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
    j = Judge('Wolfram Alpha--42', a.no_llm)
    t, fa = grade_common(j, a)
    n = math_norm(fa)
    j.check("nav_image_memory_input_query",
          queried_with_all(t, must_all=['100.2', '123.5'],
                          any_of=[['72'], ['image', 'picture', 'rawmemory']],
                          forbidden=['find the', 'find a ', 'find an ', 'compute the', 'calculate the', 'determine the', 'evaluate the', 'estimate the', 'approximate the', 'what is the', "what's the", 'what is a ', 'what are the', 'how many', 'how much', 'how long', 'how often', 'tell me', 'tell us', 'give me', 'show me', 'display the', 'show the', 'evaluated at', 'at the point', 'when x equals', 'inflation:', 'compare burgers', 'calorie comparison', 'convert', 'converted to', 'what is the raw memory of', 'true colour picture', '100.2" * 123.5"', '100.2" x 123.5"']),
          f"input_queries={input_queries(t)[:6]}")
    j.check("answer_raw_memory", contains_any(fa, ["192.45", "183.54", "64.15", "192451332"]) or (decimal_in(fa, "192") and contains_any(fa, ["mb", "mib"])), f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
