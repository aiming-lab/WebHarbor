#!/usr/bin/env python3
"""Healthline--6: sign in as alice, report how many articles are in the saved list.
GT: 5 (pre-seeded). Deterministic: nav /saved + answer count cross-checked against the DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (number_affirmed, load_run, final_answer, navigated_any, number_mentioned, resolve_db, saved_articles_for, Judge, parse_args, run)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('Healthline--6', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    saved = saved_articles_for(init, EMAIL)
    saved_after = saved_articles_for(after, EMAIL) if after else None
    # The task wording says "currently"; because this task is graded as read-only
    # (tables_unchanged below), both databases must agree. Accepting either keeps the
    # answer bounded by real list sizes without relaxing the read-only requirement.
    counts = {len(saved)} | ({len(saved_after)} if saved_after is not None else set())
    # the saved list is shown on both /saved and the /account page — accept either
    j.check("nav_saved", navigated_any(t, ["/saved", "/account"]),
            "expected the saved articles page or the account page")
    # a missing/unreadable initial DB is an infrastructure failure, never a zero count
    j.check("answer_count",
            saved is not None and any(number_affirmed(fa, c) for c in sorted(counts)),
            f"expected the saved-article count {sorted(counts)} from the database, stated "
            f"affirmatively; db_available={saved is not None}; final={fa!r}")
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--6')
