#!/usr/bin/env python3
"""Verify League of Legends--13: multi-account isolation (alice adds Yone, bob adds Milio).

Honest chain (25 atomic actions): Play Now -> Sign In -> fill alice email ->
fill password -> submit -> Champions nav -> fill q='Yone' -> Apply -> open
Yone -> Add to Favorites -> My Account -> Sign Out -> Play Now -> Sign In ->
fill bob email -> fill password -> submit -> My Account -> Champions nav ->
fill q='Milio' -> Apply -> open Milio -> Add to Favorites -> My Account ->
answer.

Frozen ground truth (seed DB):
  * alice_j (id 1) starts with 5 favorites (Amumu, Draven, Kayle, Lee Sin,
    Yunara); after adding Yone (champion id 162) -> 6.
  * bob_c (id 2) keeps his seeded 5 favorites (Anivia, Annie, Cho'Gath, Renata
    Glasc, Viego) — Yone is NOT among them; after adding Milio (id 84) -> 6.
  * Database delta: exactly two favorite_champions rows added — (alice, Yone)
    and (bob, Milio) — and nothing else.
"""
from verify_lib import (bound_count, bound_phrase, champion_named,
                        check_favorites_delta, check_only_tables_changed,
                        check_trajectory_identity, contains_phrase,
                        entered_identity, final_answer,
                        navigated_champion, navigated_to_path, run_verifier)

TASK_ID = "League of Legends--13"
ALICE = "alice.j@test.com"
BOB = "bob.c@test.com"
ALICE_NAME = "alice"
BOB_NAME = "bob"
ADDED = [(1, 162, "2026-09-22"), (2, 84, "2026-09-22")]
BOB_SEEDED = ["Anivia", "Annie", "Cho'Gath", "Renata Glasc", "Viego"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("entered_alice_identity", entered_identity(traj, ALICE),
                f"expected {ALICE!r} entered on the sign-in page")
    judge.check("entered_bob_identity", entered_identity(traj, BOB),
                f"expected {BOB!r} entered on the sign-in page")
    judge.check("visited_signin_twice", navigated_to_path(traj, "/login"),
                "required: /login (both sign-ins)")
    judge.check("visited_yone_page", navigated_champion(traj, "yone"),
                "required: /champions/yone/")
    judge.check("visited_milio_page", navigated_champion(traj, "milio"),
                "required: /champions/milio/")
    judge.check("visited_account", navigated_to_path(traj, "/account"),
                "required: /account (bob's unaffected favorites verified there)")

    judge.check("answer_alice_total_6",
                bound_count(answer, 6, ALICE_NAME, [BOB_NAME], mode="after", allow_misbound=True),
                "expected alice's new total of 6 favorites attached to alice")
    judge.check("answer_yone_named", champion_named(answer, "Yone"),
                "expected Yone named as alice's addition")
    judge.check("answer_yone_is_alices",
                bound_phrase(answer, "Yone", ALICE_NAME, [BOB_NAME], allow_misbound=True),
                "expected Yone attached to alice's account")
    judge.check("answer_bob_unchanged_5",
                bound_count(answer, 5, BOB_NAME, [ALICE_NAME], mode="after", allow_misbound=True),
                "expected bob's unaffected 5 favorites attached to bob")
    judge.check("answer_bob_seeded_names",
                all(bound_phrase(answer, n, BOB_NAME, [ALICE_NAME], mode="after", allow_misbound=True)
                    for n in BOB_SEEDED),
                f"expected bob's seeded favorites attached to bob: {BOB_SEEDED}")
    judge.check("answer_yone_absence",
                contains_phrase(answer, "not") or contains_phrase(answer, "without")
                or contains_phrase(answer, "no Yone") or contains_phrase(answer, "absent"),
                "expected the answer to state Yone is not among bob's favorites")
    judge.check("answer_bob_final_6",
                bound_count(answer, 6, BOB_NAME, [ALICE_NAME], mode="after", allow_misbound=True),
                "expected bob's final total of 6 favorites attached to bob")
    judge.check("answer_milio_named", champion_named(answer, "Milio"),
                "expected Milio named as bob's addition")
    judge.check("answer_milio_is_bobs",
                bound_phrase(answer, "Milio", BOB_NAME, [ALICE_NAME], allow_misbound=True),
                "expected Milio attached to bob's account")

    check_favorites_delta(judge, initial_db, after_db, added=ADDED)
    check_only_tables_changed(judge, initial_db, after_db, {"favorite_champions"})


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
