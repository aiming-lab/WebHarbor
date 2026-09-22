#!/usr/bin/env python3
"""Verify 9GAG--15: Alice logs in and publishes a new Wholesome post with the exact title/description/tags (stateful).

Deterministic only. Ground truth is hardcoded here and never appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_only_tables_changed, check_paths_in_order, check_signed_in_as, check_trajectory_identity,
    check_visited_path, normalize_text, row_dict, run_verifier, table_delta,
)

TASK_ID = "9GAG--15"
EMAIL, USERNAME = "alice.j@test.com", "alice_j"
TITLE = "Quiet victories deserve confetti"
SECTION = "wholesome"
DESCRIPTION = "My neighbor finished night school after six years."
TAGS = "community|education|wholesome"
NEW_SLUG = "quiet-victories-deserve-confetti"  # app.slugify(TITLE); the publish redirect lands on /gag/<slug>


def _tags_match(value):
    return [t.strip().casefold() for t in str(value or "").split("|") if t.strip()] == TAGS.split("|")


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, EMAIL, USERNAME)
    check_visited_path(judge, traj, "visited_submit_form", "/submit")
    check_visited_path(judge, traj, "visited_published_post", f"/gag/{NEW_SLUG}")
    check_paths_in_order(judge, traj, "workflow_login_submit_publish",
                         [("/login", {}), ("/submit", {}), (f"/gag/{NEW_SLUG}", {})])
    delta = table_delta(initial_db, after_db, "post")
    added = [row_dict(after_db, "post", r) for r in delta["added"]]
    exact = len(added) == 1 and not delta["removed"] and not delta["changed"]
    if exact:
        new = added[0]
        exact = (normalize_text(new["title"]) == normalize_text(TITLE)
                 and normalize_text(new["section"]) == SECTION
                 and normalize_text(new["description"]) == normalize_text(DESCRIPTION)
                 and _tags_match(new["tags"])
                 and str(new["author_name"]) == USERNAME
                 and str(new["slug"]) == NEW_SLUG)
    judge.check("new_post_exact_delta", exact,
                f"expected exactly one new post by {USERNAME!r}: title={TITLE!r}, section={SECTION!r}, "
                f"description={DESCRIPTION!r}, tags={TAGS!r}; added={added!r}, removed={delta['removed']!r}, changed={delta['changed']!r}")
    check_only_tables_changed(judge, initial_db, after_db, allowed=("post",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
