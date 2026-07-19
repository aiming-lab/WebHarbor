#!/usr/bin/env python3
"""Deterministic verifier for WebMD--16.

Log in as alice.j@test.com, open the "Gout Attacks: Why They Happen at 3 A.M."
article, save it, then confirm it appears in Saved Articles.
Ground truth (after-state): 'gout-attacks-prevention' is in alice's saved list AND
was NOT in alice's initial seed saved list (a real save happened).

Checks: nav login+article+saved | DB after: slug added & absent initially | LLM+screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, answer_equals,
                        date_present, resolve_db, saved_slugs_for, saved_count_for,
                        user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "gout-attacks-prevention"

def main():
    a = parse_args()
    j = Judge('WebMD--16', a.no_llm)
    t = load_run(a.run_dir)
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_article", navigated_to(t, "/articles/gout-attacks-prevention"),
            f"navigated={navigated_to(t, '/articles/gout-attacks-prevention')}")
    j.check("nav_saved", navigated_to(t, "/account/saved"),
            f"navigated={navigated_to(t, '/account/saved')}")
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    aw = saved_slugs_for(after, EMAIL)
    iw = saved_slugs_for(init, EMAIL)
    j.check("db_article_saved", aw is not None and SLUG in (aw or []),
            f"after_saved={aw}")
    j.check("db_article_absent_initial", iw is not None and SLUG not in (iw or []),
            f"initial_saved={iw}")
    s = shot_after_url(t, "/account/saved") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Gout Attacks: Why They Happen at 3 A.M.",
            "alice's Saved Articles list including the gout-attacks article")
        j.check("screenshot_shows_saved", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
