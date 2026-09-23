#!/usr/bin/env python3
"""Verify League of Legends--4: 'darkin' champion search + roles from detail pages."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_named,
                        contains_all, contains_phrase, final_answer, navigated_champion,
                        navigated_champions_listing, run_verifier)

TASK_ID = "League of Legends--4"
# Frozen ground truth (seed DB, roster search 'darkin' scores the champion search blob):
# Aatrox, Kayn, Naafiri, Varus, Zaahen; roles from the champion pages.
RESULTS = {
    "aatrox": ["Aatrox", ["Fighter"]],
    "kayn": ["Kayn", ["Fighter", "Assassin"]],
    "naafiri": ["Naafiri", ["Assassin", "Fighter"]],
    "varus": ["Varus", ["Marksman", "Mage"]],
    "zaahen": ["Zaahen", ["Fighter"]],
}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("searched_darkin_on_champions_page",
                navigated_champions_listing(traj, {"q": "darkin"}),
                "required: /champions/?q=darkin")
    missing = [slug for slug in RESULTS if not navigated_champion(traj, slug)]
    judge.check("opened_all_five_results", not missing,
                f"required detail pages for {sorted(RESULTS)}; missing={missing!r}")
    judge.check("answer_lists_all_five",
                all(champion_named(answer, name) for name, _ in RESULTS.values()),
                "expected Aatrox, Kayn, Naafiri, Varus, Zaahen in the answer")
    for slug, (name, roles) in RESULTS.items():
        judge.check(f"answer_roles_{slug}",
                    contains_all(answer, roles) and champion_named(answer, name),
                    f"expected {name!r} with roles {roles!r}")


    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
