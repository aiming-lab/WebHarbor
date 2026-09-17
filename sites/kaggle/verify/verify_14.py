#!/usr/bin/env python3
"""Verifier for Kaggle--14 (read-only).

On Kaggle Learn, how many lessons does 'Intro to Machine Learning' (slug
intro-to-machine-learning) contain? Ground truth: 7 lessons.

Checks: nav the course page | answer states the lesson count | DB anchor | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, affirms_number, final_answer, llm_text_match,
                        load_run, navigated_to, origin_ok, parse_args, resolve_db,
                        run_complete, scalar, shot_at, shot_distinct, shot_final,
                        tables_unchanged)

SLUG = "intro-to-machine-learning"
_NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
              8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}

def main():
    a = parse_args()
    j = Judge('Kaggle--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    ref = resolve_db(a.initial_db, a.container, "instance_seed") or resolve_db(a.after_db, a.container, "instance")
    # Read-only task: the live DB must be unchanged, otherwise the run is not
    # a read-only visit (a missing DB leaves `changed` as None and fails).
    changed = tables_unchanged(ref, resolve_db(a.after_db, a.container, "instance"))
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    lessons = scalar(ref, "courses", "lessons", SLUG)  # 7
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_course", navigated_to(t, f"/learn/{SLUG}"), "opened the Intro to ML course page")
    j.check("db_ground_truth", lessons is not None, f"lessons={lessons}")
    count_ok = lessons is not None and (affirms_number(fa, lessons)
                                        or (lessons in _NUM_WORDS and affirms(fa, _NUM_WORDS[lessons])))
    j.check("answer_lesson_count", count_ok, f"expected={lessons} final={fa!r}")
    ok, ev = llm_text_match(fa, f"The course has {lessons} lessons.",
        "How many lessons does the 'Intro to Machine Learning' course contain?")
    j.check("answer_llm", ok, ev, llm=True)
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/learn/intro-to-machine-learning")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
