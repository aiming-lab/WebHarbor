#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--7.

Find the software requirements for iPhones that support AirDrop's ability to continue transmitting over the web when out of range.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Apple support pages state that continuing an AirDrop
    transfer over the internet when out of range requires iOS 17.1 or
    iPadOS 17.1 (or later) on both devices, with both signed in to iCloud
    and the sender's iCloud account having an active data connection.
Source pages: support.apple.com AirDrop guide pages and apple.com/iphone/whats-new

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an AirDrop search | an Apple support page opened | answer: the iOS
  version requirement and the iCloud/data requirement
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
    j = Judge('Google Search--7', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["airdrop"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-007-", "use-airdrop-iphcd2f071e2", "system-requirements-iphceb71808", "whats-new"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_ios_version", number_claim(fa, 17.1),
            f"final={fa[:200]!r}")
    j.check("answer_platform", contains_any(fa, ["ios", "ipados", "iphone", "ipad"]),
            f"final={fa[:200]!r}")
    j.check("answer_icloud_requirement", contains_any(fa, ["icloud"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
