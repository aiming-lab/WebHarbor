#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--26.

Identify the hardware requirements for using the latest version of Adobe Photoshop on a Mac.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Adobe Help system-requirements page (Photoshop 26.x) lists
    the macOS requirements: Processor Apple silicon (M1) or Intel multicore
    with 64-bit support, 2 GHz or faster (recommended M2/M3/M4); Operating
    system macOS Monterey (12.0) or later; RAM 8 GB (16 GB or more
    recommended); GPU with Metal support and 1.5 GB GPU memory; 20 GB of
    hard-disk space.
Source pages: helpx.adobe.com/photoshop/system-requirements.html

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Photoshop requirements search | the system-requirements page opened |
  answer: processor, macOS version, RAM and GPU requirements
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--26', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["photoshop"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-026-", "system-requirements.html"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_macos_version", contains_any(fa, ["macos 12", "monterey"]),
            f"final={fa[:200]!r}")
    j.check("answer_processor", contains_any(fa, ["apple silicon", "m1", "intel"]),
            f"final={fa[:200]!r}")
    j.check("answer_ram", re_any(fa, [r"\b8\s*gb\b", r"\b16\s*gb\b"]),
            f"final={fa[:200]!r}")
    j.check("answer_gpu", contains_any(fa, ["metal", "gpu", "graphics"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
