#!/usr/bin/env python3
"""Deterministic verifier for Target--18 (stateful: open a support request).

Sign in as bob.c@test.com, submit a support request with the subject
"Order arrived damaged" and Email as the contact method, then report its
status.

Ground truth (frozen here, never read from tasks.jsonl):
  A new support_tickets row for bob.c@test.com with
    subject = "Order arrived damaged", channel = "Email", status = "Open".
  bob.c starts with one seeded ticket, so the count must grow by exactly one.

The subject and channel are dictated by the task, which is what makes this
checkable: an agent that submits the form with its own wording has not done
what was asked, even though a ticket exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, navigated_to,
                        contains_any, resolve_db, db_query,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SUBJECT = "Order arrived damaged"
CHANNEL = "Email"


def tickets_for(db_path, email):
    """[(subject, channel, status)] for this account, oldest first."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT t.subject, t.channel, t.status FROM support_tickets t "
        "JOIN users u ON u.id = t.user_id WHERE u.email = ? ORDER BY t.id", (email,))
    return [tuple(r) for r in rows]


def main():
    a = parse_args()
    j = Judge("Target--18", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_contact_form", navigated_to(t, "/support/contact"),
            f"visited={navigated_to(t, '/support/contact')}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    before = tickets_for(initial, EMAIL)
    now = tickets_for(after, EMAIL)

    j.check("db_readable", before is not None and now is not None,
            f"before={before} after={now}")

    if before is not None and now is not None:
        j.check("one_new_ticket", len(now) == len(before) + 1,
                f"before={len(before)} after={len(now)}")
        created = [row for row in now if row not in before]
        match = next((r for r in created if r[0].strip() == SUBJECT), None)
        j.check("subject_matches_task", match is not None,
                f"new tickets={created} (expected subject {SUBJECT!r})")
        j.check("channel_is_email", bool(match) and match[1] == CHANNEL,
                f"channel={match[1] if match else None} (expected {CHANNEL})")
        j.check("answer_reports_status",
                bool(match) and contains_any(fa, [match[2]]),
                f"status={match[2] if match else None} final={fa!r}")
    else:
        for name in ("one_new_ticket", "subject_matches_task",
                     "channel_is_email", "answer_reports_status"):
            j.check(name, False, "DB unavailable")

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a support request listed on the account",
                                      "the account's support requests page")
        j.check("screenshot_shows_request", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_request", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
