#!/usr/bin/env python3
"""MEGA--11 (read-only): recommended MEGA Pass Chrome extension name + version."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, affirms_any, download_named, final_answer,
                        llm_text_match, load_run, navigated_to, parse_args, resolve_db,
                        tables_unchanged)

PACKAGE = "MEGA Pass Chrome extension"

def main():
    a = parse_args()
    j = Judge("MEGA--11", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    row = download_named(init or after, PACKAGE)
    j.check("db_package", row is not None and bool(row[4]), f"row={row!r}")
    download_id = row[0] if row else None
    version = row[2] if row else ""
    j.bind_run(t, shot_url=f"/downloads/{download_id}" if download_id else "/downloads")
    j.check("nav_downloads", navigated_to(t, "/downloads"), "opened Downloads")
    j.check("nav_detail", download_id is not None and navigated_to(t, f"/downloads/{download_id}"),
            f"opened Chrome extension detail id={download_id}")
    j.check("answer_name", affirms_any(fa, ["mega pass chrome", PACKAGE.lower()]), f"final={fa!r}")
    j.check("answer_version", bool(version) and affirms(fa, version), f"version={version!r} final={fa!r}")
    ok, ev = llm_text_match(fa, f"{PACKAGE} version {version}",
                            "What is the recommended MEGA Pass Chrome extension package name and version?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
