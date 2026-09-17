#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--15.

Activities filtered to Elementary School: title and duration.

Ground truth is hardcoded here and nowhere in tasks.jsonl.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        contains_all, contains_any, answer_equals, numbers_in, has_number,
                        dates_in, resolve_db, saved_sims_for, saved_rows_for, user_exists,
                        read_only_run, catalog_unchanged, table_counts, db_query,
                        llm_text_match, counts, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('PhET Interactive Simulations--15', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("nav_activities", navigated_to(t, "/teachers/activities"), "activities list visited")
    j.check("used_grade_filter", navigated_to(t, "grade=elementary"), "elementary filter applied")
    j.check("answer_title", contains_any(fa, ["Equivalent Fractions Game"]), f"final={fa!r}")
    j.check("answer_duration", counts(fa, 50, "minute", "min"), f"numbers={numbers_in(fa)}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
