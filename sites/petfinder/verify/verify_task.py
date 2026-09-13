#!/usr/bin/env python3
"""Task-specific deterministic checks for the Petfinder review contract."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from ground_truth import CHECKLIST_ITEMS, DETAILS, FILTERS, INQUIRY_MESSAGE
from verify_lib import (
    Judge,
    changed_tables,
    check_common,
    check_read_only,
    contains_all,
    entered_text,
    favorite_names,
    final_answer,
    has_number,
    inquiry_rows,
    is_site_url,
    normalize_text,
    normalized_path,
    number_bound_to,
    parse_args,
    resolve_db,
    trajectory_urls,
    user_preferences,
    visited_path,
    visited_query,
    load_run,
)


READ_ONLY_TASKS = {0, 1, 2, 3, 4, 6, 7}


def search_used(trajectory, term: str) -> bool:
    expected = normalize_text(term)
    for url in trajectory_urls(trajectory):
        if not is_site_url(url, trajectory) or normalized_path(url) != "/search":
            continue
        query = normalize_text((parse_qs(urlparse(url).query).get("q") or [""])[0])
        if expected in query:
            return True
    return False


def state_databases(judge: Judge, args):
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    return initial, after


def main(index: int):
    args = parse_args()
    task_id = f"Petfinder--{index}"
    judge = Judge(task_id)
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, task_id)

    if index in READ_ONLY_TASKS:
        check_read_only(judge, args)

    if index in (0, 1, 2):
        judge.check("requested_filters_used", visited_query(trajectory, "/pets", FILTERS[index]), str(FILTERS[index]))
        judge.check("matching_detail_opened", visited_path(trajectory, DETAILS[index]), DETAILS[index])

    if index == 0:
        judge.check("answer_identity_and_shelter", contains_all(answer, ["Milo Labrador Mix", "Hudson Valley Animal Rescue"]), repr(answer))
        judge.check("answer_days", number_bound_to(answer, 3, ["Milo", "day", "Petfinder"]), repr(answer))
    elif index == 1:
        judge.check("answer_complete", contains_all(answer, ["Luna Domestic Shorthair", "Female", "PAWS Chicago"]), repr(answer))
    elif index == 2:
        judge.check("answer_identity_and_shelter", contains_all(answer, ["Nori Rabbit", "Seattle Animal Shelter"]), repr(answer))
        judge.check("answer_fee", has_number(answer, 75), repr(answer))
    elif index == 3:
        judge.check("site_search_used", search_used(trajectory, "Nori"), "search q contains Nori")
        judge.check("nori_detail_opened", visited_path(trajectory, "/pets/nori-rabbit"), "detail URL")
        judge.check("answer_complete", contains_all(answer, ["Holland Lop Mix", "Adult", "Seattle, WA"]), repr(answer))
    elif index == 4:
        judge.check("login_and_account_opened", visited_path(trajectory, "/login") and visited_path(trajectory, "/account"), "login + account")
        judge.check("answer_names", contains_all(answer, ["Milo Labrador Mix", "Nori Rabbit"]), repr(answer))
        judge.check("answer_count", number_bound_to(answer, 2, ["favorite", "saved", "pet"]), repr(answer))
    elif index == 5:
        initial, after = state_databases(judge, args)
        judge.check("login_and_account_opened", visited_path(trajectory, "/login") and visited_path(trajectory, "/account"), "login + account")
        judge.check("initial_preferences_differ", bool(initial and user_preferences(initial) == ("New York, NY", "Nearest first")), str(user_preferences(initial) if initial else None))
        judge.check("preferences_persisted", bool(after and user_preferences(after) == ("Chicago, IL", "Newest pets first")), str(user_preferences(after) if after else None))
        judge.check("only_user_changed", bool(initial and after and changed_tables(initial, after) == {"user"}), str(changed_tables(initial, after) if initial and after else None))
        judge.check("answer_complete", contains_all(answer, ["Chicago, IL", "Newest pets first"]), repr(answer))
    elif index == 6:
        judge.check("guide_opened", visited_path(trajectory, "/guides/pet-adoption-checklist"), "guide detail")
        judge.check("all_checklist_items_reported", contains_all(answer, CHECKLIST_ITEMS), repr(answer))
    elif index == 7:
        judge.check("senior_chicago_filters_used", visited_query(trajectory, "/pets", FILTERS[7]), str(FILTERS[7]))
        judge.check("both_details_opened", visited_path(trajectory, "/pets/maple-senior-beagle") and visited_path(trajectory, "/pets/ollie-poodle-mix"), "Maple + Ollie")
        judge.check("winner_identified", contains_all(answer, ["Ollie Poodle Mix", "fewer"]), repr(answer))
        judge.check("ollie_days", number_bound_to(answer, 5, ["Ollie"]), repr(answer))
        judge.check("maple_days", number_bound_to(answer, 18, ["Maple"]), repr(answer))
    elif index == 8:
        initial, after = state_databases(judge, args)
        judge.check("search_and_detail", search_used(trajectory, "Luna") and visited_path(trajectory, "/pets/luna-domestic-shorthair"), "search + Luna detail")
        initial_names = favorite_names(initial) if initial else []
        after_names = favorite_names(after) if after else []
        judge.check("luna_newly_saved", "Luna Domestic Shorthair" not in initial_names and "Luna Domestic Shorthair" in after_names, f"before={initial_names} after={after_names}")
        judge.check("favorite_count", len(after_names) == 3, str(after_names))
        judge.check("only_favorites_changed", bool(initial and after and changed_tables(initial, after) == {"saved_item"}), str(changed_tables(initial, after) if initial and after else None))
        judge.check("answer_count", number_bound_to(answer, 3, ["favorite", "saved", "pet"]), repr(answer))
    elif index == 9:
        initial, after = state_databases(judge, args)
        judge.check("search_and_detail", search_used(trajectory, "Nori") and visited_path(trajectory, "/pets/nori-rabbit"), "search + Nori detail")
        judge.check("requested_message_entered", entered_text(trajectory, INQUIRY_MESSAGE, "/pets/nori-rabbit"), "exact inquiry text")
        before_rows = inquiry_rows(initial) if initial else []
        after_rows = inquiry_rows(after) if after else []
        expected = {"slug": "nori-rabbit", "message": INQUIRY_MESSAGE, "status": "Submitted"}
        judge.check("inquiry_newly_persisted", expected not in before_rows and expected in after_rows, f"before={before_rows} after={after_rows}")
        judge.check("only_inquiry_changed", bool(initial and after and changed_tables(initial, after) == {"inquiry"}), str(changed_tables(initial, after) if initial and after else None))
        judge.check("answer_status", contains_all(answer, ["Submitted"]), repr(answer))
    else:
        judge.check("known_task", False, f"unsupported task index {index}")

    judge.emit()
