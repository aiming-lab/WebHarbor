#!/usr/bin/env python3
"""MEGA--15 (read-only): ransomware article first action is disconnect the affected device."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_to, parse_args, resolve_db, tables_unchanged)

def main():
    a = parse_args()
    j = Judge("MEGA--15", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    j.bind_run(t, shot_url="/help/recover-from-ransomware")
    j.check("nav_article", navigated_to(t, "/help/recover-from-ransomware"),
            "opened Recover from ransomware")
    j.check("answer_disconnect",
            affirms_any(fa, ["disconnect the affected device", "disconnect"]),
            f"final={fa!r}")
    j.check("answer_device", affirms_any(fa, ["device", "affected device"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Disconnect the affected device",
                            "What is the first action the ransomware article recommends before restoring files?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
