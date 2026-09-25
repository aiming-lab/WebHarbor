#!/usr/bin/env python3
"""Verify Ohio.gov--15.

State Directory chain: the Accountancy Board entry (website, contact method,
which social networks it lists), then search the directory for "Lottery"
(full agency name + contact method), then search for "Taxation" (which social
networks that entry lists + contact method).

Frozen ground truth (tracked data snapshot): the Accountancy Board's website
is acc.ohio.gov with contact method "contact form" and 3 social links
(Facebook / YouTube / LinkedIn). Searching "Lottery" returns the Lottery
agency with contact method "contact list and form". Searching "Taxation"
returns the Taxation entry listing Facebook, YouTube, and LinkedIn with
contact method "contact list".

F-REND-1 follow-up: the directory social links now render their network names
(canonical title text + brand icons), so the answer must name the networks.
"""
from verify_lib import (check_read_only, check_trajectory_identity, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--15"
DIRECTORY_PATH = "/help-center/state-directory"


def _segment_after(answer, keyword, stop_words):
    """Windows of `answer` starting at each case-insensitive `keyword` occurrence,
    truncated at the first following stop word (or end). Facts about one directory
    entry must appear inside that entry's own window, not anywhere in the answer."""
    low = answer.lower()
    windows = []
    start = 0
    while True:
        i = low.find(keyword, start)
        if i < 0:
            break
        end = len(answer)
        for stop in stop_words:
            j = low.find(stop, i + len(keyword))
            if j >= 0:
                end = min(end, j)
        windows.append(answer[i:end].lower())
        start = i + len(keyword)
    return windows


def _any_window_has(answer, keyword, stop_words, needles):
    return any(all(n in w for n in needles) for w in _segment_after(answer, keyword, stop_words))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: directory searched for Accountancy, Lottery, Taxation
    judge.check("searched_accountancy",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "accountancy"),
                "required: /help-center/state-directory?q=Accountancy")
    judge.check("searched_lottery",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "lottery"),
                "required: /help-center/state-directory?q=Lottery")
    judge.check("searched_taxation",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "taxation"),
                "required: /help-center/state-directory?q=Taxation")
    # answer: Accountancy website, contact, socials — entry-scoped windows
    judge.check("answer_accountancy_website",
                _any_window_has(answer, "accountancy", ("lottery", "taxation"),
                                ["acc.ohio.gov"]),
                "expected website: acc.ohio.gov")
    judge.check("answer_accountancy_contact",
                _any_window_has(answer, "accountancy", ("lottery", "taxation"),
                                ["contact form"]),
                "expected contact method: contact form")
    judge.check("answer_accountancy_socials",
            any(("facebook" in w and "linkedin" in w)
                for w in _segment_after(answer, "accountancy", ("lottery", "taxation"))),
                "expected: 3 social networks (Facebook / YouTube / LinkedIn)")
    # answer: Lottery full name + contact — entry-scoped window
    judge.check("answer_lottery_name",
                _any_window_has(answer, "lottery", ("accountancy", "taxation"),
                                ["lottery"]),
                "expected full agency name: Lottery")
    judge.check("answer_lottery_contact",
                _any_window_has(answer, "lottery", ("accountancy", "taxation"),
                                ["contact list and form"]),
                "expected Lottery contact method: contact list and form")
    # answer: Taxation socials + contact — the facts must appear in the Taxation
    # entry's own text window (an entry-scoped check, not a whole-answer check)
    judge.check("answer_taxation_socials",
                _any_window_has(answer, "taxation", ("accountancy", "lottery"),
                                ["facebook", "youtube", "linkedin"]),
                "expected Taxation social networks: Facebook, YouTube, LinkedIn")
    judge.check("answer_taxation_contact",
                _any_window_has(answer, "taxation", ("accountancy", "lottery"),
                                ["contact list"]),
                "expected Taxation contact method: contact list")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
