#!/usr/bin/env python3
"""Healthline--19: migraine-triggers article — report >=3 common triggers; then the Migraine
condition page — when to see a doctor. GT triggers: stress, changes in sleep, skipped meals,
certain foods/additives, bright lights, hormonal fluctuations. GT when-to-see-doctor: headaches
that are severe, sudden, or accompanied by fever, stiff neck, confusion, or weakness.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (affirmed_any, resolve_db, load_run, final_answer, navigated_to, count_groups, contains_any, llm_text_match, Judge, parse_args, run)

# each inner list is ONE distinct trigger concept; overlapping tokens count once
TRIGGER_GROUPS = [["stress"], ["sleep"], ["meal"], ["food", "additive"],
                  ["bright light"], ["hormon"]]

def main():
    a = parse_args(); j = Judge('Healthline--19', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/article/migraine-triggers"),
            "expected the migraine triggers article")
    j.check("nav_condition", navigated_to(t, "/condition/migraine"),
            "expected the Migraine condition page")
    j.check("answer_three_triggers", count_groups(fa, TRIGGER_GROUPS) >= 3,
            f"expected >=3 distinct migraine triggers; final={fa!r}")
    j.check("answer_when_to_see", affirmed_any(fa, ["see a doctor", "severe", "sudden", "fever",
                                                    "stiff neck", "confusion", "weakness"]),
            "expected the 'when to see a doctor' guidance, stated affirmatively")
    ok, ev = llm_text_match(fa, "triggers such as stress, sleep changes, skipped meals, certain "
                            "foods, bright lights, hormonal changes; see a doctor if headaches are "
                            "severe, sudden, or come with fever/stiff neck/confusion/weakness",
                            "List three migraine triggers and say when to see a doctor.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.check_screenshots(t)
    _init = resolve_db(a.initial_db, a.container, "instance_seed")
    _after = resolve_db(a.after_db, a.container, "instance")
    j.check_readonly(_init, _after)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--19')
