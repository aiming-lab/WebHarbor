#!/usr/bin/env python3
"""MEGA--1 (read-only): recovery-key article — do not share with support or teammates."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, contains_all, final_answer, llm_text_match, load_run,
                        navigated_to, parse_args, resolve_db, tables_unchanged)

def main():
    a = parse_args()
    j = Judge("MEGA--1", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    j.bind_run(t, shot_url="/help/save-your-recovery-key")
    j.check("nav_article", navigated_to(t, "/help/save-your-recovery-key"),
            "opened the Save your recovery key article")
    j.check("answer_support_teammates", contains_all(fa, ["support", "teammate"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Do not share the recovery key with support or teammates.",
                            "Who does the recovery-key article say not to share the key with?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
