#!/usr/bin/env python3
"""Verify the current task: browser evidence, requested facts and exact state."""
from verify_lib import (contains_phrase, check_visited_path,check_read_only, check_trajectory_identity, final_answer,
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
    # Navigation gates for the two relevant agencies.
    judge.check("searched_accountancy",
                navigated_with_query(traj, DIRECTORY_PATH, "q", "accountancy"),
                "required: /help-center/state-directory?q=Accountancy")
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

    judge.check('accountancy_all_socials', _any_window_has(answer, 'accountancy', ('taxation',), ['youtube']), 'YouTube also required')
    judge.check('taxation_website', _any_window_has(answer, 'taxation', ('accountancy',), ['tax.ohio.gov']), 'Taxation website')
    judge.check('taxation_all_socials', all(_any_window_has(answer, 'taxation', ('accountancy',), [x]) for x in ['facebook','youtube','linkedin']), 'all three networks required')
    check_visited_path(judge, traj, 'visited_license_faq', '/help-center/faqs/professional-licenses')
    judge.check('license_verification', contains_phrase(answer, 'elicense'), 'eLicense Ohio')

if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
