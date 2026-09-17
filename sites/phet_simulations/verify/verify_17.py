#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--17.

Compare translation counts of two named simulations.

Ground truth is hardcoded here and nowhere in tasks.jsonl.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        contains_all, contains_any, answer_equals, numbers_in, has_number,
                        dates_in, resolve_db, saved_sims_for, saved_rows_for, user_exists,
                        read_only_run, catalog_unchanged, table_counts, db_query,
                        llm_text_match, counts, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('PhET Interactive Simulations--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("nav_build_an_atom", navigated_to(t, "/simulation/build-an-atom"), "first detail page opened")
    j.check("nav_membrane_transport", navigated_to(t, "/simulation/membrane-transport"), "second detail page opened")
    winner = bool(re.search(r"build an atom[^.!?;]{0,60}\b(?:more|higher|greater|most)\b", fa, re.I)
                  or re.search(r"(?:winner|more languages)\s*(?:is|:)\s*build an atom", fa, re.I)
                  or (re.search(r"build an atom\s*(?::|has|is translated into)\s*104\b", fa, re.I)
                      and re.search(r"membrane transport\s*(?::|has|is translated into)\s*31\b", fa, re.I)))
    j.check("answer_names_winner", winner, f"final={fa!r}")
    j.check("answer_difference", counts(fa, 73, "difference", "language", "translation"), f"numbers={numbers_in(fa)}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
