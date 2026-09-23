#!/usr/bin/env python3
"""Verify Medicare.gov--9 — Alice's move: address change + lost-card replacement.

Stateful task (two state changes + login). Ground truth (frozen seed): Alice's
Medicare Number is 1EG4-TE5-MK73; after the change the account settings show
the current mailing address 45 Meadow Lane, Buffalo Grove, IL 60089; the
replacement card (reason 'lost') is ordered with status 'Mailing in 7-10 days'.
The DB carries exactly: one alice login_events insert, alice's old mailing
address superseded + exactly one new current row, exactly one card_requests
row (reason lost, requested 2026-09-23, status 'Mailing in 7-10 days'), and
nothing else anywhere.
"""

from verify_lib import (ALICE_EMAIL, ALICE_MBI, Judge, MIRROR_REFERENCE_DATE,
                        NEW_ADDRESS, advisory_llm_answer, card_requests_of,
                        check_login_delta, check_signed_in_as,
                        check_table_delta_shape, check_trajectory_identity,
                        contains_medicare_number, contains_phrase, final_answer,
                        mailing_addresses_of, navigated_to_path, run_verifier,
                        user_id_by_email)

TASK_ID = "Medicare.gov--9"
CARD_PAGE = "/my/account-settings/get-my-medicare-card"
CARD_STATUS = "Mailing in 7-10 days"
GROUND_TRUTH = ("Alice's Medicare Number is 1EG4-TE5-MK73. The account settings confirm the "
                "new mailing address 45 Meadow Lane, Buffalo Grove, IL 60089, and the free "
                "replacement card (reason: lost) is on its way — expect it in 7-10 days; "
                "the Medicare Number stays the same.")
QUESTION = ("Alice moved and lost her Medicare card: update the mailing address to 45 Meadow "
            "Lane, Buffalo Grove, IL 60089 (confirm it shows in account settings), order a "
            "free replacement card with 'My card was lost' as the reason, and report the "
            "Medicare Number on her current card plus the replacement status.")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    judge.check("opened_account_settings", navigated_to_path(traj, "/my/account-settings"),
                "required_path=/my/account-settings")
    judge.check("opened_card_page", navigated_to_path(traj, CARD_PAGE),
                f"required_path={CARD_PAGE}")
    judge.check("answer_medicare_number",
                contains_medicare_number(answer, ALICE_MBI),
                f"expected the Medicare Number {ALICE_MBI!r}")
    line1, city, state, zip_ = NEW_ADDRESS
    judge.check("answer_new_address_confirmed",
                contains_phrase(answer, line1) and contains_phrase(answer, city)
                and contains_phrase(answer, zip_),
                f"expected the new address {NEW_ADDRESS!r}")
    judge.check("answer_replacement_status",
                contains_phrase(answer, "7-10") or contains_phrase(answer, "7 to 10")
                or contains_phrase(answer, "7 to ten"),
                "expected 'Mailing in 7-10 days'")

    user_id = user_id_by_email(initial_db, ALICE_EMAIL)
    check_login_delta(judge, initial_db, after_db, ALICE_EMAIL,
                      extra_allowed=("mailing_addresses", "card_requests"))
    before_addr, after_addr = mailing_addresses_of(initial_db, user_id), mailing_addresses_of(after_db, user_id)
    old = [a for a in before_addr if a["is_current"]]
    judge.check("seed_has_one_current_address", len(old) == 1, f"current_in_seed={old!r}")
    superseded = [a for a in after_addr if a["id"] == old[0]["id"] and a["is_current"] == 0]
    new_rows = [a for a in after_addr if a["id"] not in {x["id"] for x in before_addr}]
    ok = (len(superseded) == 1 and len(new_rows) == 1 and new_rows[0]["line1"] == line1
          and new_rows[0]["city"] == city and new_rows[0]["state"] == state
          and new_rows[0]["zip"] == zip_ and new_rows[0]["is_current"] == 1
          and str(new_rows[0]["effective_date"]) == MIRROR_REFERENCE_DATE)
    judge.check("mailing_address_superseded_and_inserted", ok,
                f"new_rows={new_rows!r}, superseded={len(superseded)}")
    check_table_delta_shape(judge, initial_db, after_db, "mailing_addresses",
                            allowed_changed_ids=(old[0]["id"],), allowed_added=1,
                            label="mailing_addresses_only_alice_supersede")
    requests_ = card_requests_of(after_db, user_id)
    ok = (len(requests_) == 1 and requests_[0]["reason"] == "lost"
          and str(requests_[0]["requested_at"]) == MIRROR_REFERENCE_DATE
          and str(requests_[0]["status"]) == CARD_STATUS)
    judge.check("card_request_exact_row", ok, f"card_requests={requests_!r}")
    check_table_delta_shape(judge, initial_db, after_db, "card_requests",
                            allowed_added=1, label="card_requests_only_alice_row")
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
