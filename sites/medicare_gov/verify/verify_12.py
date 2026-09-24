#!/usr/bin/env python3
"""Verify Medicare.gov--12 — Alice's full account checkup.

Login-read task (login + the required message-opened flip). Ground truth
(frozen seed): the message center holds 2 unread messages; the newest one has
the subject 'Reminder: Medicare Open Enrollment starts October 15' and its body
says Open Enrollment runs October 15 through December 7, 2026; the current due
Part B premium bill is $202.90 due 2026-10-25; the Medicare Number shown in
account settings is 1EG4-TE5-MK73. The DB carries exactly one alice
login_events insert plus exactly the is_read flip of the newest message
(id 3), and nothing else anywhere.
"""

from verify_lib import (ALICE_EMAIL, ALICE_MBI, Judge, NEWEST_UNREAD_MESSAGE_ID,
                        advisory_llm_answer, check_login_delta,
                        check_message_read_delta, check_signed_in_as,
                        check_trajectory_identity, contains_count,
                        contains_medicare_number, contains_money,
                        contains_phrase, final_answer, navigated_to_path,
                        run_verifier, user_id_by_email)

TASK_ID = "Medicare.gov--12"
MESSAGE_DETAIL = f"/my/messages/{NEWEST_UNREAD_MESSAGE_ID}"
DUE_AMOUNT = "$202.90"
DUE_DATE = "2026-10-25"
GROUND_TRUTH = ("The message center holds 2 unread messages. The newest one has the "
                "subject 'Reminder: Medicare Open Enrollment starts October 15' and its "
                "body says Open Enrollment runs October 15 through December 7, 2026. The "
                "current due Part B premium bill is $202.90, due 2026-10-25. The Medicare "
                "Number in account settings is 1EG4-TE5-MK73.")
QUESTION = ("How many unread messages are in the message center; open the newest message "
            "(subject and the enrollment dates its body mentions); what are the amount and "
            "due date of the current due Part B premium bill; and what is the Medicare "
            "Number shown in account settings?")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL)
    judge.check("opened_message_center", navigated_to_path(traj, "/my/messages"),
                "required_path=/my/messages")
    judge.check("opened_newest_message",
                navigated_to_path(traj, MESSAGE_DETAIL),
                f"required_path={MESSAGE_DETAIL}")
    judge.check("opened_premiums_page", navigated_to_path(traj, "/my/premiums"),
                "required_path=/my/premiums")
    judge.check("opened_account_settings", navigated_to_path(traj, "/my/account-settings"),
                "required_path=/my/account-settings")
    judge.check("answer_2_unread_messages",
                contains_count(answer, 2) and contains_phrase(answer, "unread"),
                "expected 2 unread messages")
    judge.check("answer_newest_message_subject",
                contains_phrase(answer, "Open Enrollment") and
                contains_phrase(answer, "October 15"),
                "expected the subject 'Reminder: Medicare Open Enrollment starts October 15'")
    judge.check("answer_enrollment_dates",
                contains_phrase(answer, "December 7") and
                (contains_phrase(answer, "October 15 through December 7")
                 or contains_phrase(answer, "Oct 15") or contains_phrase(answer, "October 15")),
                "expected October 15 through December 7, 2026")
    judge.check("answer_due_premium_amount",
                contains_money(answer, 202, 90) and contains_phrase(answer, "due"),
                "expected the due premium of $202.90")
    judge.check("answer_due_date",
                contains_phrase(answer, DUE_DATE) or contains_phrase(answer, "October 25"),
                f"expected due date {DUE_DATE}")
    judge.check("answer_medicare_number",
                contains_medicare_number(answer, ALICE_MBI),
                f"expected the Medicare Number {ALICE_MBI!r}")

    user_id = user_id_by_email(initial_db, ALICE_EMAIL)
    check_login_delta(judge, initial_db, after_db, ALICE_EMAIL, extra_allowed=("messages",))
    check_message_read_delta(judge, initial_db, after_db, user_id, require_opened=True)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
