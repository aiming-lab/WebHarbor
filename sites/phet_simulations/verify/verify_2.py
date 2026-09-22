#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--2.

The only Biology sim not offered at university: report its grade levels.

Ground truth is hardcoded here and nowhere in tasks.jsonl.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        contains_all, contains_any, answer_equals, numbers_in, has_number,
                        dates_in, resolve_db, saved_sims_for, saved_rows_for, user_exists,
                        read_only_run, catalog_unchanged, table_counts, db_query,
                        llm_text_match, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('PhET Interactive Simulations--2', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("nav_biology_catalog", navigated_any(t, ["subject=biology", "/simulations/category/biology"]),
            "biology listing visited")
    j.check("nav_natural_selection", navigated_to(t, "/simulation/natural-selection"), "target detail page opened")
    j.check("answer_names_target", contains_any(fa, ["Natural Selection"]), f"final={fa!r}")
    j.check("answer_grades", contains_all(fa, ["element", "middle", "high"]), f"final={fa!r}")
    # The task text itself contains the phrase "not offered at university level", so a
    # bare substring test would fail a correct answer that restates the question. Bind to
    # the page's own rendering of the band instead, and to claims of targeting it.
    low = (fa or "").casefold()
    claims_university = ("university (ages 18+)" in low
                         or "ages 18+" in low
                         or "targets university" in low
                         or "including university" in low)
    j.check("answer_does_not_claim_university", not claims_university, f"final={fa!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
