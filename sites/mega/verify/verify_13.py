#!/usr/bin/env python3
"""MEGA--13 (read-only): Business page highlight 'Team dashboard'."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_path, parse_args, resolve_db, tables_unchanged)

def main():
    a = parse_args()
    j = Judge("MEGA--13", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    j.bind_run(t, shot_url="/business")
    j.check("nav_business", navigated_path(t, "/business"), "opened the Business product page")
    j.check("answer_team_dashboard", affirms_any(fa, ["team dashboard"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Team dashboard",
                            "Which Business page highlight names the team administration surface?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
