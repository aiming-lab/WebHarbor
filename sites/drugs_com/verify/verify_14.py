#!/usr/bin/env python3
"""Verifier for Drugs.com--14 (login-gated read). My Med List after sign-in.
Ground truth (seed): alice.j@test.com has atorvastatin, ibuprofen, metformin saved.
Checks: nav login + My Med List | answer lists all seeded meds | DB anchor (fail-closed)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, final_answer, resolve_db, med_list_for,
                        count_present, norm, llm_text_match, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('Drugs.com--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    # This task reads seeded state; use the initial (seed) DB as the source of truth for the list.
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    meds = med_list_for(init, EMAIL)
    j.check("nav_login", navigated_any(t, ["/login", "/account/login"]), "signed in")
    j.check("nav_med_list", navigated_any(t, ["/my-med-list", "/my-med-list.html"]), "opened My Med List")
    j.check("db_available", meds is not None and len(meds) >= 1, f"seed_meds={meds}")
    j.check("answer_lists_all_meds", meds is not None and count_present(fa, meds) >= len(meds),
            f"expected={meds} matched={None if meds is None else [m for m in meds if norm(m) in norm(fa)]}")
    ok, ev = llm_text_match(fa, f"The saved My Med List drugs are: {', '.join(meds or [])}.",
        "List all drugs currently saved in alice's My Med List.")
    j.check("answer_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
