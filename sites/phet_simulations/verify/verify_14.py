#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--14.

Register test_user@phet.test and save Number Pairs to it.

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
    j = Judge('PhET Interactive Simulations--14', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("answer_names_saved_sim", contains_any(fa, ["Number Pairs"]),
            f"the final answer must say which simulation was saved; final={fa!r}")
    j.check("nav_register", navigated_to(t, "/register"), "registration page visited")
    j.check("nav_number_pairs", navigated_to(t, "/simulation/number-pairs"), "detail page opened")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ci, ca = table_counts(init), table_counts(after)
    j.check("exactly_one_new_user",
            ci is not None and ca is not None and ca["user"] == ci["user"] + 1,
            f"users {ci and ci['user']} -> {ca and ca['user']}")
    j.check("new_user_has_the_named_email", user_exists(after, email="test_user@phet.test") is True,
            "test_user@phet.test present")
    rows = saved_rows_for(after, "test_user@phet.test")
    j.check("saved_number_pairs", rows is not None and any(r[0] == "number-pairs" for r in rows),
            f"saved={rows}")
    j.check("exactly_one_new_save",
            ci is not None and ca is not None and ca["saved_simulation"] == ci["saved_simulation"] + 1,
            f"saved rows {ci and ci['saved_simulation']} -> {ca and ca['saved_simulation']}")
    j.check("catalog_unchanged", catalog_unchanged(init, after) is True, "catalogue tables untouched")
    j.emit()


if __name__ == "__main__":
    main()
