#!/usr/bin/env python3
"""Verify Medicare.gov--7 — alice claim reconciliation + newest unread message.

Login-read task. Ground truth (frozen seed): the July 2026 screening colonoscopy
claim shows Medicare paid $1,736.00 and you may be billed $0.00; the blood
sugar test strips claim shows Medicare paid $77.12 and you may be billed
$19.28; the newest unread message in the message center has the subject
'Reminder: Medicare Open Enrollment starts October 15'. The DB may carry
exactly one alice login_events insert, and (optionally, if the agent opened the
message) exactly the is_read flip of that newest unread message.
"""

from verify_lib import (ALICE_EMAIL, Judge, NEWEST_UNREAD_SUBJECT,
                        advisory_llm_answer, check_login_delta,
                        check_message_read_delta, check_signed_in_as,
                        check_trajectory_identity, contains_money,
                        contains_phrase, final_answer, navigated_to_path,
                        run_verifier, user_id_by_email)

TASK_ID = "Medicare.gov--7"
GROUND_TRUTH = ("The July 2026 screening colonoscopy claim: Medicare paid $1,736.00 and you "
                "may be billed $0.00. The blood sugar test strips claim: Medicare paid "
                "$77.12 and you may be billed $19.28. The newest unread message in the "
                "message center has the subject 'Reminder: Medicare Open Enrollment starts "
                "October 15'.")
QUESTION = ("For the July screening colonoscopy claim, how much did Medicare pay and how "
            "much may you be billed; same two amounts for the blood sugar test strips "
            "claim; and what is the subject of the newest unread message in the message "
            "center?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    judge.check("opened_claims_list", navigated_to_path(traj, "/my/claims"),
                "required_path=/my/claims")
    judge.check("opened_message_center", navigated_to_path(traj, "/my/messages"),
                "required_path=/my/messages")
    judge.check("answer_colonoscopy_paid_1736",
                contains_money(answer, 1736, 0) or contains_money(answer, 1736)
                or contains_phrase(answer, "1,736.00"),
                "expected Medicare paid $1,736.00 for the colonoscopy")
    judge.check("answer_colonoscopy_owed_0",
                contains_phrase(answer, "0.00") or contains_phrase(answer, "nothing")
                or contains_phrase(answer, "no cost") or contains_phrase(answer, "free"),
                "expected you may be billed $0.00 for the colonoscopy")
    judge.check("answer_strips_paid_77_12",
                contains_money(answer, 77, 12),
                "expected Medicare paid $77.12 for the test strips")
    judge.check("answer_strips_owed_19_28",
                contains_money(answer, 19, 28),
                "expected you may be billed $19.28 for the test strips")
    judge.check("answer_newest_unread_subject",
                contains_phrase(answer, "Open Enrollment") and
                contains_phrase(answer, "October 15"),
                f"expected subject {NEWEST_UNREAD_SUBJECT!r}")
    user_id = user_id_by_email(initial_db, ALICE_EMAIL)
    check_login_delta(judge, initial_db, after_db, ALICE_EMAIL,
                      extra_allowed=("messages",))
    check_message_read_delta(judge, initial_db, after_db, user_id, require_opened=False)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
