#!/usr/bin/env python3
"""Verify WebMD Doctor--15: Award Winning Hospitals > Patient's Choice recipients; the Orthopedic Surgery recipient in Media; practice website + Saturday hours (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    contains_saturday_hours,
    check_paths_in_order,
    check_read_only,
    check_results_visited,
    check_trajectory_identity,
    check_visited_path,
    check_visited_profile,
    contains_hours_window,
    contains_url,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    normalized_url_path,
    parse_args,
    profile_path_pattern,
    resolve_snapshots,
    site_urls,
)


TASK_ID = "WebMD Doctor--15"
SLUG = "linda-merriweather-378753c8"
AWARDS_PATH = "/choice-awards"
RECIPIENTS_PATH = "/choice-awards/awardrecipients"
PRACTICE_PATH = "/practice/rose-tree-orthopedics-sports-medicine"
WEBSITE = "https://www.rosetreeorthopedicssportsmedicine.example"
SAT_OPEN = "9:00 am"
SAT_CLOSE = "2:00 pm"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_path(judge, trajectory, "visited_award_page", AWARDS_PATH)
    check_results_visited(judge, trajectory, "visited_patients_choice_recipients_page", {"award-class": ("patient", "")}, path=RECIPIENTS_PATH)
    check_visited_profile(judge, trajectory, SLUG)
    check_visited_path(judge, trajectory, "visited_practice_page", PRACTICE_PATH)
    # The target recipient is rank 18 of 18 in the unfiltered Patient's Choice
    # list, so a genuine run must reach a recipients view that actually shows
    # her: a later page, or a narrowed (state-filtered) list. Visiting only the
    # unfiltered first page and then jumping to the profile does not count.
    recipients_urls = [
        url for url in site_urls(trajectory)
        if normalized_url_path(url) == RECIPIENTS_PATH
    ]
    shows_target = False
    for url in recipients_urls:
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        page_value = (query.get("page") or [""])[0].strip()
        state_value = (query.get("state") or [""])[0].strip()
        if (page_value and page_value != "1") or state_value:
            shows_target = True
            break
    judge.check("visited_recipients_view_showing_target", shows_target, f"observed_recipients_urls={recipients_urls!r}")
    check_paths_in_order(judge, trajectory, "workflow_in_order", [(AWARDS_PATH, {}), (RECIPIENTS_PATH, {"award-class": ("patient", "")}), (profile_path_pattern(SLUG), {}), (PRACTICE_PATH, {})])
    judge.check("answer_has_practice_website", contains_url(answer, WEBSITE), f"expected={WEBSITE!r}, answer={answer!r}")
    judge.check("answer_has_saturday_hours", contains_hours_window(answer, SAT_OPEN, SAT_CLOSE), f"expected={SAT_OPEN!r}-{SAT_CLOSE!r}, answer={answer!r}")
    judge.check(
        "answer_has_saturday_hours_context",
        contains_saturday_hours(answer, SAT_OPEN, SAT_CLOSE),
        f"both endpoints must sit in one Saturday clause in order; answer={answer!r}",
    )
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
