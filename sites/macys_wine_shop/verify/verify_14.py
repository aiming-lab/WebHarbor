#!/usr/bin/env python3
"""Verify MacysWineShop--14 (KEEP): carol password change + revert.

Adapted in substance from the depth review's KEEP contract for the old --23
(21 measured steps): the trajectory signs in as carol.d@test.com, changes the
account password to AutumnCellar77! (the account page confirms each change
with 'Password changed successfully.'), reverts to TestPass123!, signs out,
and signs back in with the original password. The DB after-state is
row-identical to the seed (the revert restores the password hash exactly).

Round-2 depth re-review (F2) hardening — the sign-out + sign-back-in outcome
carries no DB evidence (read-only task), so a truncated walk or a lying
answer used to pass on phrase presence alone. The verifier now additionally
requires: (a) a re-login navigation gate — a second /login visit followed by
a recorded /account visit (the post-login landing); (b) an answer gate that
affirmatively claims signing back in with the original password SUCCEEDED;
(c) every password-shaped claim in the answer matches the task's two
credentials (AutumnCellar77! / TestPass123!); and (d) no monetary claim at
all — the password chain shows no prices or totals.
"""

import re

from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_phrase, final_answer, input_texts,
                        normalize_text, normalized_url_path, run_verifier, site_urls)

TASK_ID = "MacysWineShop--14"
NEW_PASSWORD = "AutumnCellar77!"
ORIGINAL_PASSWORD = "TestPass123!"

# ---------------------------------------------------------------- re-login navigation gate
def _collapsed_paths(traj):
    """Recorded on-site paths in visit order, consecutive duplicates collapsed."""
    seq = []
    for url in site_urls(traj):
        path = normalized_url_path(url)
        if not seq or seq[-1] != path:
            seq.append(path)
    return seq


def _relogin_lands_on_account(traj):
    """A /login visit AFTER the first one must be followed by an /account visit.

    The task chain signs in once, changes + reverts the password, signs out,
    and signs back in: the re-login is a later /login visit whose post-submit
    landing on /account must be recorded (url_after / next step url /
    final_url). A walk truncated at the sign-out fails here.
    """
    seq = _collapsed_paths(traj)
    logins = [i for i, path in enumerate(seq) if path == "/login"]
    return any("/account" in seq[i + 1:] for i in logins[1:])


# ---------------------------------------------------------------- answer gates
def _strip(word):
    return word.strip(".,;:!?(“”\"'’[]")


# negation anywhere in the last three words before a match invalidates it
_NEGATION_WORDS = {"not", "no", "never", "without", "wrong", "incorrect", "isn't", "isnt",
                   "wasn't", "wasnt", "cannot", "cant", "can't", "couldn't", "couldnt",
                   "didn't", "didnt", "don't", "dont", "doesn't", "doesnt", "won't", "wont",
                   "wouldn't", "wouldnt", "unable", "failed", "fails"}
# a failure marker in the three words right after a match invalidates it too
_AFTER_FAILURE_WORDS = {"failed", "failure", "fails", "error", "errored", "unable",
                        "incorrect", "wrong", "didn't", "didnt", "couldn't", "couldnt",
                        "cannot", "cant", "can't"}
# success markers that may trail a neutral sign-in phrasing (same sentence,
# before any failure word)
_SUCCESS_MARKERS = {"succeeded", "successful", "successfully", "success", "works",
                   "worked"}

# sign-back-in phrasings; PAST/ABILITY forms are success claims on their own,
# neutral forms need a success marker within the next eight words
_PAST_ABILITY_FORMS = (
    "signed back in", "signed in again", "logged back in", "logged in again",
    "signed in successfully", "logged in successfully", "successfully signed in",
    "successfully logged in", "signed in with the original password",
    "logged in with the original password", "able to sign in", "able to sign back in",
    "able to sign in again", "able to log in", "able to log back in",
    "able to log in again", "could sign in", "could sign back in", "could log in",
    "could log back in", "can sign in", "can sign back in", "can log in",
    "can log back in", "re-login succeeded", "relogin succeeded",
    "re-login successful", "relogin successful", "succeeded in signing in",
    "succeeded in logging in",
)
_NEUTRAL_FORMS = (
    "signing back in", "signing in again", "sign back in", "sign in again",
    "sign in with the original password", "logging back in", "logging in again",
    "log back in", "log in again", "log in with the original password",
    "re-login", "relogin",
)


def _phrase_pattern(phrase):
    words = [re.escape(w) for w in
             phrase.replace("-", " ").replace("_", " ").split()]
    return r"(?<!\w)" + r"[\s_-]*".join(words) + r"(?!\w)"


def _word_window(text, start, end, count):
    segment = text[start:end]
    words = [_strip(w) for w in re.split(r"[\s_-]+", segment) if _strip(w)]
    return words[:count]


def _affirmative_match(text, match):
    before = re.split(r"[.!?;:,\n]+|\b(?:but|however|instead)\b", text[: match.start()])[-1]
    if any(w in _NEGATION_WORDS for w in _word_window(before, 0, len(before), 3)):
        return False
    after_words = _word_window(text, match.end(), len(text), 3)
    return not any(w in _AFTER_FAILURE_WORDS for w in after_words)


def _same_sentence_after(text, match):
    """The remainder of the sentence that follows the match ('!' is kept: it is
    a credential symbol here — 'TestPass123! works' is one sentence)."""
    tail = text[match.end():]
    stop = re.search(r"[.?;\n]", tail)
    return tail[: stop.start()] if stop else tail


def _marker_before_failure(segment):
    """A success marker appears in the segment before any failure word."""
    words = [_strip(w) for w in re.split(r"[\s_-]+", segment) if _strip(w)]
    for word in words:
        if word in _SUCCESS_MARKERS:
            return True
        if word in _AFTER_FAILURE_WORDS:
            return False
    return False


def _answer_relogin_succeeded(answer):
    text = normalize_text(answer)
    for phrase in _PAST_ABILITY_FORMS:
        for match in re.finditer(_phrase_pattern(phrase), text):
            if _affirmative_match(text, match):
                return True
    for phrase in _NEUTRAL_FORMS:
        for match in re.finditer(_phrase_pattern(phrase), text):
            if not _affirmative_match(text, match):
                continue
            if _marker_before_failure(_same_sentence_after(text, match)):
                return True
    return False


# password-shaped claims: letters + digits + optional credential symbol
_CREDENTIAL_TOKEN = re.compile(r"\b[a-z]+\d+[!@#$%^&*]?\b")
_LEGIT_CREDENTIALS = {"autumncellar77!", "autumncellar77", "testpass123!", "testpass123"}
# a fabricated monetary claim: '$<digits>' or any bare two-decimal amount
_MONEY_TOKEN = re.compile(r"\$\s?\d|\b\d+\.\d{2}\b")


def _answer_password_claims(text):
    claimed = [m.group(0) for m in _CREDENTIAL_TOKEN.finditer(text)]
    bad = [token for token in claimed if token not in _LEGIT_CREDENTIALS]
    return bad


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    normalized = normalize_text(answer)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "carol.d@test.com")
    check_visited_path(judge, traj, "visited_password_page", "/account/password")
    inputs = input_texts(traj)
    judge.check("entered_new_password",
                any(NEW_PASSWORD in v for v in inputs),
                f"expected {NEW_PASSWORD} in an input step; observed={inputs!r}")
    judge.check("reverted_to_original_password",
                sum(1 for v in inputs if ORIGINAL_PASSWORD in v) >= 1,
                f"expected the original password {ORIGINAL_PASSWORD} to be re-entered")
    # Frozen ground truth: the account page confirms each change with
    # "Password changed successfully."
    judge.check("answer_change_confirmed",
                contains_phrase(answer, "Password changed successfully"),
                "expected the account page confirmation 'Password changed successfully.'")
    # --- round-2 F2 gates: the sign-out + sign-back-in outcome itself ---
    judge.check("relogin_navigation",
                _relogin_lands_on_account(traj),
                "required: a second /login visit followed by a recorded /account "
                "visit (the post-re-login landing); observed path sequence="
                f"{_collapsed_paths(traj)!r}")
    judge.check("answer_relogin_succeeded",
                _answer_relogin_succeeded(answer),
                "required: the answer affirmatively states signing back in with "
                f"the original password succeeded; answer={answer!r}")
    bad_passwords = _answer_password_claims(normalized)
    judge.check("answer_password_claims_match_contract",
                not bad_passwords,
                f"every password the answer names must be {NEW_PASSWORD} or "
                f"{ORIGINAL_PASSWORD}; rejected claims={bad_passwords!r}")
    judge.check("answer_money_claim_rejected",
                not _MONEY_TOKEN.search(normalized),
                "the password chain shows no prices or totals; a monetary claim "
                f"in the answer is fabricated; answer={answer!r}")
    # DB after-state: the revert restores the seed row exactly.
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
