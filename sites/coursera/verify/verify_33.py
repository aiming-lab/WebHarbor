#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--33.

Find a beginner-level Coursera course related to 'Internet of Things (IoT)' with a high rating; provide the course name, the instructor's name, and a summary of the skills taught.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Introduction to the Internet of Things and Embedded Systems (UC Irvine, Ian Harris, 4.6); IoT (Internet of Things) Wireless & Cloud Computing Emerging Technologies (University at Buffalo, Amanpreet Kapoor, 4.7); Internet of Things Specialization (UC Irvine, Sujit Dey, 4.7); An Introduction to Programming the Internet of Things (UC Irvine, Ian Harris, 4.8).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + instructor + >=2 skills
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
    j, t, fa = load_task(a, "Coursera--33")
    sk1 = ["Internet of Things", "Embedded Systems", "Arduino", "Sensors", "Networking"]
    sk2 = ["IoT", "Wireless Communication", "Cloud Computing", "Edge Computing", "Sensors"]
    sk3 = ["IoT", "Arduino", "Raspberry Pi", "Cloud Connectivity"]
    sk4 = ["IoT", "Arduino", "Sensors", "Raspberry Pi"]
    n1 = sum(1 for s in sk1 if contains_all(fa, [s]))
    n2 = sum(1 for s in sk2 if contains_all(fa, [s]))
    n3 = sum(1 for s in sk3 if contains_all(fa, [s]))
    n4 = sum(1 for s in sk4 if contains_all(fa, [s]))
    opts = [
        {"slug": "introduction-internet-things-embedded-systems",
        "page_tokens": ['Introduction to the Internet of Things and Embedded Systems'],
        "answer_tokens": ['Introduction to the Internet of Things', 'Ian Harris'],
        "extra": [("answer_skills", n1 >= 2, f"skills matched={n1}/5 of {sk1}")]},
        {"slug": "iot-wireless-cloud-computing",
        "page_tokens": ['IoT (Internet of Things) Wireless & Cloud Computing Emerging Technologies'],
        "answer_tokens": ['IoT', 'Amanpreet Kapoor'],
        "extra": [("answer_skills", n2 >= 2, f"skills matched={n2}/5 of {sk2}")]},
        {"slug": "internet-of-things-specialization",
        "page_tokens": ['Internet of Things Specialization'],
        "answer_tokens": ['Internet of Things Specialization', 'Sujit Dey'],
        "extra": [("answer_skills", n3 >= 2, f"skills matched={n3}/4 of {sk3}")]},
        {"slug": "programming-iot-introduction",
        "page_tokens": ['An Introduction to Programming the Internet of Things'],
        "answer_tokens": ['Programming the Internet of Things', 'Ian Harris'],
        "extra": [("answer_skills", n4 >= 2, f"skills matched={n4}/4 of {sk4}")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
