#!/usr/bin/env python3
"""Verify League of Legends--17: alice's favorite champions + skin census (baseline).

The depth-review KEEP (former League of Legends--20): the only read-only
aggregation chain retained verbatim as the depth baseline.

Honest chain (16 atomic actions): Play Now -> Sign In -> fill email -> fill
password -> submit -> My Account -> Favorite Champions -> open Amumu -> back ->
open Draven -> back -> open Kayle -> back -> open Lee Sin -> back -> open
Yunara -> back -> answer.

Frozen ground truth (seed DB, alice_j favorite_champions joined to champions):
Amumu 15 skins, Draven 15, Kayle 19, Lee Sin 20, Yunara 3 — Lee Sin has the
most. Read-only: every table must stay row-identical.
"""
from verify_lib import (SEED_USERS, bound_count, bound_phrase, check_read_only,
                        check_signed_in_as, check_trajectory_identity, champion_named,
                        contains_count, final_answer, navigated_to_path_any,
                        run_verifier)

TASK_ID = "League of Legends--17"
EMAIL = "alice.j@test.com"
FAVORITES = [("amumu", "Amumu", 15), ("draven", "Draven", 15), ("kayle", "Kayle", 19),
             ("lee-sin", "Lee Sin", 20), ("yunara", "Yunara", 3)]
MOST = "Lee Sin"
CENSUS = [name for _, name, _ in FAVORITES]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL)
    judge.check("visited_account_or_favorites",
                navigated_to_path_any(traj, ["/account", "/account/favorites"]),
                "required: /account (or /account/favorites)")
    judge.check("answer_favorite_count", contains_count(answer, len(FAVORITES)),
                f"expected {len(FAVORITES)} favorite champions")
    for slug, name, skins in FAVORITES:
        # 15 is shared by Amumu and Draven: bind existentially; unique counts bind strictly
        shared = sum(1 for _, _, n in FAVORITES if n == skins) > 1
        judge.check(f"answer_favorite_{slug}",
                    champion_named(answer, name) and
                    bound_count(answer, skins, name,
                                [c for c in CENSUS if c != name],
                                allow_misbound=shared),
                    f"expected {name!r} with {skins} skins attached to {name!r}")
    judge.check("answer_most_skins", champion_named(answer, MOST),
                f"expected {MOST!r} named as having the most skins")
    judge.check("answer_most_claim_bound",
                bound_phrase(answer, "most", MOST, [c for c in CENSUS if c != MOST],
                             mode="after", only_if_present=True),
                f"expected any 'most skins' claim attached to {MOST!r}")
    judge.check("answer_census_named_all",
                all(champion_named(answer, name) for _, name, _ in FAVORITES),
                "expected every favorite champion named")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
