#!/usr/bin/env python3
"""Verify League of Legends--9: skin-count comparison across Aatrox/Naafiri/Zaahen."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_named,
                        contains_count, contains_phrase, final_answer, navigated_champion,
                        run_verifier)

TASK_ID = "League of Legends--9"
# Frozen ground truth (seed DB): Aatrox 13 skins, Naafiri 5, Zaahen 2 — Aatrox has the most.
COUNTS = {"aatrox": ("Aatrox", 13), "naafiri": ("Naafiri", 5), "zaahen": ("Zaahen", 2)}
MOST = "Aatrox"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    missing = [slug for slug in COUNTS if not navigated_champion(traj, slug)]
    judge.check("opened_all_three_champion_pages", not missing,
                f"required detail pages for {sorted(COUNTS)}; missing={missing!r}")
    for slug, (name, count) in COUNTS.items():
        judge.check(f"answer_count_{slug}",
                    champion_named(answer, name) and contains_count(answer, count),
                    f"expected {name!r} with {count} skins")
    judge.check("answer_most_skins", champion_named(answer, MOST),
                f"expected {MOST!r} named as having the most skins")
    from reviewed import check_facts
    check_facts(judge, answer, [{'entity': 'Aatrox', 'patterns': ['\\b13\\s+(?:skins|appearances)']}, {'entity': 'Naafiri', 'patterns': ['\\b5\\s+(?:skins|appearances)']}, {'entity': 'Zaahen', 'patterns': ['\\b2\\s+(?:skins|appearances)']}])
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
