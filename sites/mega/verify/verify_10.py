#!/usr/bin/env python3
"""MEGA--10 (read-only): Windows MEGAcmd setup installer checksum."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms, download_named, final_answer, llm_text_match,
                        load_run, navigated_to, parse_args, resolve_db, tables_unchanged)

PACKAGE = "MEGAcmdSetup64.exe"

def main():
    a = parse_args()
    j = Judge("MEGA--10", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    row = download_named(init or after, PACKAGE)
    j.check("db_package", row is not None, f"row={row!r}")
    download_id = row[0] if row else None
    checksum = row[3] if row else ""
    j.bind_run(t, shot_url=f"/downloads/{download_id}" if download_id else "/downloads")
    j.check("nav_downloads", navigated_to(t, "/downloads"), "opened Downloads")
    j.check("nav_detail", download_id is not None and navigated_to(t, f"/downloads/{download_id}"),
            f"opened installer detail id={download_id}")
    j.check("not_portable_only", not (navigated_to(t, "/downloads/5") and not navigated_to(t, f"/downloads/{download_id}")),
            "did not grade the portable zip instead of the setup installer")
    j.check("answer_checksum", bool(checksum) and affirms(fa, checksum), f"expected={checksum!r} final={fa!r}")
    ok, ev = llm_text_match(fa, checksum, "What checksum is shown for MEGAcmdSetup64.exe?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
