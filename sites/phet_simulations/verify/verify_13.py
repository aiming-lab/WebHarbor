#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--13.

Student account saves Membrane Transport with a note.

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
    j = Judge('PhET Interactive Simulations--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("answer_names_saved_sim", contains_any(fa, ["Membrane Transport"]),
            f"the final answer must say which simulation was saved; final={fa!r}")
    j.check("nav_login", navigated_to(t, "/login"), "sign-in page visited")
    j.check("nav_membrane_transport", navigated_to(t, "/simulation/membrane-transport"), "detail page opened")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before = saved_sims_for(init, "student@phet.test")
    rows = saved_rows_for(after, "student@phet.test")
    j.check("exactly_one_new_save",
            before is not None and rows is not None and len(rows) == len(before) + 1,
            f"before={before} after={rows}")
    j.check("saved_the_named_sim",
            rows is not None and any(r[0] == "membrane-transport" for r in rows), f"after={rows}")
    j.check("note_is_present",
            rows is not None and any(r[0] == "membrane-transport" and r[1].strip() for r in rows),
            f"after={rows}")
    teacher = saved_sims_for(after, "teacher@phet.test")
    j.check("other_account_untouched", teacher is not None and len(teacher) == 4, f"teacher={teacher}")
    j.check("catalog_unchanged", catalog_unchanged(init, after) is True, "catalogue tables untouched")
    j.emit()


if __name__ == "__main__":
    main()
