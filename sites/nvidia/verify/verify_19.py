#!/usr/bin/env python3
"""NVIDIA--19: subscribe the email gamer42@example.com to the NVIDIA newsletter.
Deterministic-first: DB after-state is decisive — the newsletter table contains
gamer42@example.com after AND did not initially (proves the agent submitted the form).
The newsletter form POSTs to /newsletter (footer), which may not surface as a nav URL, so
the DB is the anchor.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, resolve_db, newsletter_has, Judge, parse_args)

TARGET = "gamer42@example.com"

def main():
    a = parse_args(); j = Judge('NVIDIA--19', a.no_llm)
    load_run(a.run_dir)  # ensure trajectory exists / well-formed
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ha = newsletter_has(after, TARGET)
    hi = newsletter_has(init, TARGET)
    j.check("db_subscribed", ha and not hi,
            f"newsletter has {TARGET} after={ha} initial={hi} (agent must subscribe it)")
    j.emit()

if __name__ == "__main__":
    main()
