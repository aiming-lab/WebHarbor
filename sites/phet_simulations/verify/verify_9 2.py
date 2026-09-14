#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--9.

Heat & Thermo topic filter: how many simulations.

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
    j = Judge('PhET Interactive Simulations--9', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("used_topic_filter", navigated_to(t, "topic=heat-and-thermo"), "topic facet used")
    j.check("answer_count", counts(fa, 9, "simulation", "sim", "result"),
            f"the count must be reported as a number of simulations; numbers={numbers_in(fa)} final={fa!r}")
    j.check("answer_names_topic", contains_any(fa, ["Heat", "Thermo"]),
            f"the answer must say which topic was counted; final={fa!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
