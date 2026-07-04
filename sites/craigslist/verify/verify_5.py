#!/usr/bin/env python3
"""Craigslist--5: log in as alice, save a search named "Gaming chair watch" for furniture matching
'gaming chair' with a max price of $200. Deterministic-first: nav | DB after-state: a saved search
named 'Gaming chair watch' exists for alice (not in the initial seed)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, saved_searches_for, Judge, parse_args)
EMAIL = "alice.j@test.com"; NAME = "gaming chair watch"
def main():
    a = parse_args(); j = Judge('Craigslist--5', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    names_a = [n.strip().lower() for n, _, _ in (saved_searches_for(after, EMAIL) or [])]
    names_i = [n.strip().lower() for n, _, _ in (saved_searches_for(init, EMAIL) or [])]
    j.check("nav_save_search", navigated_any(t, ["/save-search", "/search"]), "expected the save-search flow")
    j.check("db_saved_search", NAME in names_a and NAME not in names_i,
            f"saved search '{NAME}' after={NAME in names_a} initial={NAME in names_i}")
    j.emit()
if __name__ == "__main__":
    main()
