#!/usr/bin/env python3
"""Healthline--7: sign in as alice, open 'A Beginner's Guide to Healthy Eating...' and save it.
Deterministic-first: nav to the article | DB after-state: 'healthy-eating-guide' is in alice's
saved list after AND was NOT there initially (proves the agent saved it).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (only_affirmative, affirmed_any, final_answer, load_run, navigated_to, resolve_db, saved_articles_for, Judge, parse_args, run)

EMAIL = "alice.j@test.com"
SLUG = "healthy-eating-guide"

def main():
    a = parse_args(); j = Judge('Healthline--7', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    sa = saved_articles_for(after, EMAIL) or []
    si = saved_articles_for(init, EMAIL) or []
    j.check("nav_article", navigated_to(t, f"/article/{SLUG}"), "expected the Healthy Eating guide article")
    fa = final_answer(t)
    j.check("answer_affirms_save",
            affirmed_any(fa, ["saved", "save it", "added to your saved"])
            and only_affirmative(fa, ["saved"]),
            f"expected an affirmative report of the save; final={fa!r}")
    j.check("db_saved", SLUG in sa and SLUG not in si,
            f"'{SLUG}' saved after={SLUG in sa}, initial={SLUG in si} (agent must save it)")
    j.check_screenshots(t)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--7')
