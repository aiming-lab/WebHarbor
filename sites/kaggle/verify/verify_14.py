#!/usr/bin/env python3
"""Verifier for Kaggle--14 (read-only).

On Kaggle Learn, how many lessons does 'Intro to Machine Learning' (slug
intro-to-machine-learning) contain? Ground truth: 7 lessons.

Checks: nav the course page | answer states the lesson count | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, resolve_db, scalar,
                        contains_number, contains_any, llm_text_match, Judge, parse_args)

SLUG = "intro-to-machine-learning"
_NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
              8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}

def main():
    a = parse_args()
    j = Judge('Kaggle--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    lessons = scalar(ref, "courses", "lessons", SLUG)  # 7
    j.check("nav_course", navigated_to(t, f"/learn/{SLUG}"), "opened the Intro to ML course page")
    j.check("db_ground_truth", lessons is not None, f"lessons={lessons}")
    count_ok = lessons is not None and (contains_number(fa, lessons)
                                        or (lessons in _NUM_WORDS and contains_any(fa, [_NUM_WORDS[lessons]])))
    j.check("answer_lesson_count", count_ok, f"expected={lessons} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The course has {lessons} lessons.",
        "How many lessons does the 'Intro to Machine Learning' course contain?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
