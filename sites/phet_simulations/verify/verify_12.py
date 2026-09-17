#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--12.

Sign in as the teacher account and report how many sims are saved.

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
    j = Judge('PhET Interactive Simulations--12', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("nav_login", navigated_to(t, "/login"), "sign-in page visited")
    j.check("nav_account", navigated_to(t, "/account"), "account page visited")
    j.check("answer_count", counts(fa, 4, "simulation", "sim", "saved", "item"),
            f"the count must be reported as a number of saved simulations; numbers={numbers_in(fa)} final={fa!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    saved = saved_sims_for(after, "teacher@phet.test")
    j.check("account_still_has_four", saved is not None and len(saved) == 4, f"saved={saved}")
    j.check("run_is_read_only", read_only_run(init, after) is True, "all runtime rows untouched")
    j.emit()


if __name__ == "__main__":
    main()
