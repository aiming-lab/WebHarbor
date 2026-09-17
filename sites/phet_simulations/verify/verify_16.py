#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--16.

About page: the four published totals.

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
    j = Judge('PhET Interactive Simulations--16', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("nav_about", navigated_to(t, "/about"), "about page visited")
    nums = numbers_in(fa)
    j.check("answer_simulations", counts(fa, 120, "simulation"), f"numbers={nums}")
    j.check("answer_subjects", counts(fa, 5, "subject"), f"numbers={nums}")
    j.check("answer_languages", counts(fa, 132, "language"), f"numbers={nums}")
    j.check("answer_activities", counts(fa, 14, "activity", "activities"), f"numbers={nums}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
