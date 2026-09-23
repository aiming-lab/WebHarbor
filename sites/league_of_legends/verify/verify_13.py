#!/usr/bin/env python3
"""Verify League of Legends--13: champions changed in BOTH patch 26.19 and 26.18.

Accepted "changed in both" set (hardcoded, hand-verified against the two seeded articles):
champions with a named change entry in both patch notes — a balance change block with
before⇒after values (Master Yi, Kassadin, Nasus, Bard, Zeri, Nautilus) or, for the Classic
section, either a change block or an explicit NEW champion introduction (Fiora, Galio,
Poppy, Shyvana). Skin mentions and incidental prose mentions do NOT count.
The answer must name at least two distinct champions from this set and describe one
specific 26.18 change for one of the champions it named.
"""
from verify_lib import (check_read_only, check_trajectory_identity, champion_named,
                        contains_any, contains_phrase, final_answer, navigated_article,
                        run_verifier)

TASK_ID = "League of Legends--13"
ARTICLES = [("game-updates", "league-of-legends-patch-26-19-notes"),
            ("game-updates", "league-of-legends-patch-26-18-notes")]
# 26.18 change ground truth per accepted champion (any one match satisfies the
# "specific change" requirement for that champion).
CHANGES_2618 = {
    "Master Yi": ["33 + 4.5/Level", "33 + 5/Level", "Highlander",
                  "35 / 45 / 55%", "40 / 50 / 60%", "armor growth",
                  "Rageblade"],
    "Kassadin": ["Null Sphere", "80% AP", "Riftwalk", "80 / 95 / 110",
                 "70 / 90 / 110"],
    "Nasus": ["Q stacks could crit", "Wither", "tenacity",
              "top dog of top lane"],
    "Bard": ["34 + 5/Level", "32 + 4.7/Level", "durability", "armor"],
    "Zeri": ["Ultrashock Laser", "burst and waveclear"],
    "Nautilus": ["61 + 3.3/Level", "58 + 3.3/Level", "Dredge Line",
                 "85 / 125 / 165 / 205 / 245"],
    "Fiora": ["2012-2015", "Riposte", "Blade Waltz", "Lunge",
              "deadly duelist"],
    "Galio": ["2010-2017", "Runic Skin", "Resolute Smite", "Bulwark",
              "Idol of Durand"],
    "Poppy": ["2010-2015", "Valiant Fighter", "Devastating Blow",
              "immune to all enemies but one"],
    "Shyvana": ["2011-2013", "Fury of the Dragonborn", "Twin Bite",
                "Frozen Mallet"],
}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    for category, slug in ARTICLES:
        judge.check(f"visited_{slug}", navigated_article(traj, category, slug),
                    f"required: /news/{category}/{slug}/")
    named = [c for c in CHANGES_2618 if champion_named(answer, c)]
    judge.check("answer_two_both_changed", len(set(named)) >= 2,
                f"expected at least two champions changed in both patches; matched {named!r}")
    detail_ok = False
    for champ in named:
        if any(contains_phrase(answer, fact) for fact in CHANGES_2618[champ]):
            detail_ok = True
            break
    judge.check("answer_specific_2618_change", detail_ok,
                "expected a specific 26.18 change detail (values, ability names or quoted "
                "wording from the 26.18 notes) for one of the named champions")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
