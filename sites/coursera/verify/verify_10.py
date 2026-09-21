#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--10.

Locate an introductory artificial-intelligence course suitable for beginners with at least one module discussing ethical considerations.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Beginner AI courses with an ethics module: AI, Empathy & Ethics (AI Ethics module); Ethics of Artificial Intelligence (AI Ethics module); Everyday Ethics in Artificial Intelligence (AI Ethics module); AI For Everyone (AI Ethics module); AI Ethics Crash Course for Beginners; Introduction to Artificial Intelligence Ethics: Survey Edition.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course + its ethics module | answer names the course
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (parse_args, load_task, check_read_only, grade_options,
                        course_option_ok, search_card_ok,
                        navigated_to, navigated_any, navigated_to_course, query_has, page_text_at,
                        contains_all, contains_any, counts, has_number, numbers_in,
                        pct_of, star_level_lowest, re_found, fold, is_mirror_url,
                        states_no_other_courses,
                        step_urls, _url_path)


def main():
    a = parse_args()
    j, t, fa = load_task(a, "Coursera--10")
    ethics_page = ["AI Ethics"]
    opts = [
        {"slug": "ai-empathy-ethics",
        "page_tokens": ['AI, Empathy & Ethics', 'AI Ethics'],
        "answer_tokens": ['AI, Empathy', 'Ethics'],
        "card_tokens": ['AI, Empathy & Ethics', 'Stanford University'],},
        {"slug": "ethics-of-artificial-intelligence",
        "page_tokens": ['Ethics of Artificial Intelligence', 'AI Ethics'],
        "answer_tokens": ['Ethics of Artificial Intelligence'],
        "card_tokens": ['Ethics of Artificial Intelligence', 'Princeton University'],},
        {"slug": "everyday-ethics-ai",
        "page_tokens": ['Everyday Ethics in Artificial Intelligence', 'AI Ethics'],
        "answer_tokens": ['Everyday Ethics'],
        "card_tokens": ['Everyday Ethics in Artificial Intelligence', 'IBM'],},
        {"slug": "ai-for-everyone",
        "page_tokens": ['AI For Everyone', 'AI Ethics'],
        "answer_tokens": ['AI For Everyone'],
        "card_tokens": ['AI For Everyone', 'Deeplearning.AI'],},
        {"slug": "ai-ethics-crash-course-beginners",
        "page_tokens": ['AI Ethics Crash Course for Beginners', 'AI Ethics'],
        "answer_tokens": ['AI Ethics Crash Course'],
        "card_tokens": ['AI Ethics Crash Course for Beginners', 'University of Colorado Boulder'],},
        {"slug": "intro-ai-ethics-survey",
        "page_tokens": ['Introduction to Artificial Intelligence Ethics', 'AI Ethics'],
        "answer_tokens": ['Introduction to Artificial Intelligence Ethics'],
        "card_tokens": ['Introduction to Artificial Intelligence Ethics: Survey Edition', 'Arizona State University'],},
    ]
    via_detail = any(course_option_ok(t, fa, o) for o in opts)
    via_card = search_card_ok(t, fa, opts)
    if via_detail or via_card:
        j.evidence.append('[PASS] evidence_on_mirror: ' +
                          ('course detail page' if via_detail else 'search results card'))
    else:
        grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
