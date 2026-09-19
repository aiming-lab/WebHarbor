#!/usr/bin/env python3
"""MEGA--16: Alice company -> Riverlight Studio Labs; 2FA and recovery key stay on."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, parse_args, resolve_db, user_row)

EMAIL = "alice.j@test.com"
COMPANY = "Riverlight Studio Labs"

def main():
    a = parse_args()
    j = Judge("MEGA--16", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/account")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_edit", navigated_to(t, "/account/edit"), "opened account edit")
    seed = user_row(init, EMAIL) if init else None
    row = user_row(after, EMAIL) if after else None
    j.check("seed_company", seed is not None and seed[2] == "Riverlight Studio",
            f"seed company={None if not seed else seed[2]!r}")
    j.check("after_company", row is not None and row[2] == COMPANY, f"after company={None if not row else row[2]!r}")
    j.check("after_2fa", row is not None and bool(row[3]), f"2fa={None if not row else row[3]}")
    j.check("after_recovery", row is not None and bool(row[4]), f"recovery={None if not row else row[4]}")
    j.emit()

if __name__ == "__main__":
    main()
