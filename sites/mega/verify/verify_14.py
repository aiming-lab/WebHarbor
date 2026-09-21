#!/usr/bin/env python3
"""MEGA--14: Bob files a High-priority Object storage ticket about S4 egress."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, load_run, navigated_to, parse_args, resolve_db,
                        tickets_for)

EMAIL = "bob.c@test.com"

def _match(row):
    _id, _num, subject, category, priority, message = row
    blob = f"{subject} {message}".casefold()
    return ((category or "").casefold() == "object storage"
            and (priority or "").casefold() == "high"
            and "s4" in blob and "egress" in blob
            and "quarter" in blob)

def main():
    a = parse_args()
    j = Judge("MEGA--14", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/support/tickets/")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_contact", navigated_to(t, "/contact") or navigated_to(t, "/support/tickets/"),
            "opened contact / ticket confirmation")
    before = tickets_for(init, EMAIL) if init else None
    after_tix = tickets_for(after, EMAIL) if after else None
    j.check("seed_no_match", before is not None and not any(_match(row) for row in before),
            f"seed={before!r}")
    new = []
    if before is not None and after_tix is not None:
        before_ids = {row[0] for row in before}
        new = [row for row in after_tix if row[0] not in before_ids]
    j.check("db_new_ticket", len(new) == 1 and _match(new[0]), f"new={new!r}")
    j.emit()

if __name__ == "__main__":
    main()
