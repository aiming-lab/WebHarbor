#!/usr/bin/env python3
"""MEGA--9 (read-only): old vendor vault entry without 2FA is Old vendor FTP."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, affirms_any, final_answer, llm_text_match, load_run,
                        navigated_to, parse_args, resolve_db, tables_unchanged,
                        vault_named)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge("MEGA--9", a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("db_read_only", tables_unchanged(init, after) == [],
            f"changed={tables_unchanged(init, after)!r}")
    j.bind_run(t, shot_url="/vault")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_vault", navigated_to(t, "/vault"), "opened MEGA Pass vault")
    row = vault_named(init or after, EMAIL, "Old vendor FTP")
    j.check("db_old_vendor", row is not None and not row[5], f"row={row!r}")
    j.check("answer_old_vendor_ftp", affirms_any(fa, ["old vendor ftp", "vendor ftp"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Old vendor FTP",
                            "Which old vendor vault entry does not have two-factor authentication?")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
