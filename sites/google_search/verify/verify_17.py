#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--17.

Tell me the names of Trump's kids

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Donald Trump has five children: Donald Trump Jr., Ivanka Trump, Eric
    Trump, Tiffany Trump and Barron Trump. The mirror's Trump family pages
    corroborate the structure (five children; three from Ivana, one from
    Marla Maples, one from Melania) but, as recorded in the audit note in
    REPORT.md, none of the mirror pages prints the five names.
Source pages: the Trump family pages (whitehouse.gov archive, Forbes, AP, Washington Post)

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a Trump children search | a Trump family page opened | answer: all five
  children's names
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
    j = Judge('Google Search--17', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["trump"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-017-", "the-trump-family", "family_of_donald_trump", "forbes.com/profile/donald-trump", "biography.com/political-figures/donald-trump", "history.com/topics/us-presidents/donald-trump", "bbc.com/news/world-us-canada-30816776", "washingtonpost.com/politics/donald-trump", "nytimes.com/topic/person/donald-trump", "apnews.com/hub/donald-trump"]),
            "an answer-bearing mirror page was opened")
    kids = [r"donald (trump )?jr", r"\bivanka\b", r"\beric\b", r"\btiffany\b", r"\bbarron\b"]
    j.check("answer_all_five_children", re_count(fa, kids) == len(kids),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
