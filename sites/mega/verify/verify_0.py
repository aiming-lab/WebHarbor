#!/usr/bin/env python3
"""MEGA--0 (read-only): Cloud storage highlights for accessing/managing files.

Ground truth: 'Mobile and desktop access' and 'File and folder links'.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_path, parse_args, resolve_db, tables_unchanged)

def main():
    a = parse_args()
    j = Judge("MEGA--0", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    changed = tables_unchanged(init, after)
    j.check("db_read_only", changed == [], f"changed tables={changed!r}")
    j.bind_run(t, shot_url="/storage")
    j.check("nav_storage", navigated_path(t, "/storage"), "opened the Cloud storage product page")
    j.check("answer_mobile_desktop", affirms_any(fa, ["mobile and desktop access", "mobile and desktop"]),
            f"final={fa!r}")
    j.check("answer_file_folder_links", affirms_any(fa, ["file and folder links", "file and folder link"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Mobile and desktop access; File and folder links",
                            "Which two Cloud storage highlights describe accessing or managing files?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
