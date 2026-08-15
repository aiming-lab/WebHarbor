#!/usr/bin/env python3
from verify_lib import contains_all, run_stateless, visited_path

SLUG = "jwst-spots-two-early-black-holes-growing-far-faster-than-their-galaxie"
REPLY = "Totally agree on the priors point — the new constraint is much tighter though."

def checks(t, answer):
    return ([("nav_comment_thread", visited_path(t, f"/article/{SLUG}"), "opened target article")],
            [("answer_full_reply", contains_all(answer, [REPLY]), repr(answer))])

if __name__ == "__main__":
    run_stateless(12, checks)
