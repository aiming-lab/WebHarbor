#!/usr/bin/env python3
"""Deterministic verifier for PhET task PhET Interactive Simulations--0.

Filter to Biology + Elementary School and list the titles.

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
    j = Judge('PhET Interactive Simulations--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("final_answer_nonempty", bool(fa), f"final={fa!r}")
    j.check("used_biology_filter", navigated_to(t, "subject=biology"),
            f"urls={[u for u in __import__('verify_lib').step_urls(t) if 'simulations' in u][:6]}")
    j.check("used_grade_filter", navigated_to(t, "grade=elementary"), "grade=elementary in a visited URL")
    from urllib.parse import urlsplit, parse_qs
    combined = any(navigated_to({"steps": [step]}, "/simulations")
                   and "biology" in parse_qs(urlsplit(step.get("url", "")).query).get("subject", [])
                   and "elementary" in parse_qs(urlsplit(step.get("url", "")).query).get("grade", [])
                   for step in t.get("steps", []))
    j.check("combined_facets", combined, "both facets applied to the same listing")
    j.check("answer_lists_all_three", contains_all(fa, ["Color Vision", "Density", "Natural Selection"]),
            f"final={fa!r}")
    j.check("answer_excludes_non_matches",
            not contains_any(fa, ["Neuron", "Membrane Transport", "Gene Expression", "Molecule Polarity", "pH Scale"]),
            f"final={fa!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ro = read_only_run(init, after)
    j.check("run_is_read_only", ro is True, f"read_only={ro}")
    j.emit()


if __name__ == "__main__":
    main()
