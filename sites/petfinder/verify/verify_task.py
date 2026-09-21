#!/usr/bin/env python3
"""Task-specific deterministic checks for the Petfinder review contract."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from answer_checks import numeric_fact, pet_named, winner, checklist as checklist_answer, inquiry_submitted, no_duplicate
from ground_truth import DETAILS, FILTERS, INQUIRY_MESSAGE
from verify_lib import (
    Judge,
    save_action_used,
    check_common,
    check_read_only,
    contains_all,
    db_query,
    entered_text,
    favorite_names,
    final_answer,
    inquiry_rows,
    input_values,
    is_site_url,
    normalize_text,
    normalized_path,
    parse_args,
    resolve_db,
    trajectory_urls,
    user_preferences,
    visited_path,
    visited_query,
    load_run,
    matches_expected_mutation,
)


READ_ONLY_TASKS = {0, 1, 2, 3, 4, 6, 7, 10, 11, 12, 13, 14}
LOGIN_TASKS = {4, 5, 8, 9, 14}


def credentials_entered(trajectory) -> bool:
    values = [normalize_text(value) for value in input_values(trajectory, "/login")]
    email = normalize_text("alice.j@test.com")
    return email in values and any(value and value != email for value in values)


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


def _main(index: int):
    args = parse_args()
    task_id = f"Petfinder--{index}"
    judge = Judge(task_id)
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, task_id)

    initial_read_db = None
    after_read_db = None
    if index in READ_ONLY_TASKS:
        initial_read_db, after_read_db = check_read_only(judge, args)

    if index in LOGIN_TASKS:
        judge.check("login_credentials_entered", credentials_entered(trajectory), "test email and a non-empty password input on /login")

    if index in (0, 1, 2):
        judge.check("requested_filters_used", visited_query(trajectory, "/pets", FILTERS[index]), str(FILTERS[index]))
        judge.check("matching_detail_opened", visited_path(trajectory, DETAILS[index]), DETAILS[index])

    if index == 0:
        judge.check("answer_identity_and_shelter", pet_named(answer, "Milo") and contains_all(answer, ["Hudson Valley Animal Rescue"]), repr(answer))
        judge.check("answer_days", numeric_fact(answer, 3, "days", "Milo"), repr(answer))
    elif index == 1:
        judge.check("answer_complete", pet_named(answer, "Luna") and contains_all(answer, ["Female", "PAWS Chicago"]), repr(answer))
    elif index == 2:
        judge.check("answer_identity_and_shelter", pet_named(answer, "Nori") and contains_all(answer, ["Seattle Animal Shelter"]), repr(answer))
        judge.check("answer_fee", numeric_fact(answer, 75, "fee"), repr(answer))
    elif index == 3:
        judge.check("site_search_used", search_used(trajectory, "Nori"), "search q contains Nori")
        judge.check("nori_detail_opened", visited_path(trajectory, "/pets/nori-rabbit"), "detail URL")
        judge.check("answer_detail_facts", contains_all(answer, ["Short", "Seattle Animal Shelter"]), repr(answer))
        judge.check("answer_fee", numeric_fact(answer, 75, "fee"), repr(answer))
    elif index == 4:
        judge.check("login_and_account_opened", visited_path(trajectory, "/login") and visited_path(trajectory, "/account"), "login + account")
        judge.check("answer_names", pet_named(answer, "Milo") and pet_named(answer, "Nori"), repr(answer))
        judge.check("answer_count", numeric_fact(answer, 2, "count"), repr(answer))
    elif index == 5:
        initial, after = state_databases(judge, args)
        judge.check("login_and_account_opened", visited_path(trajectory, "/login") and visited_path(trajectory, "/account"), "login + account")
        judge.check("initial_preferences_differ", bool(initial and user_preferences(initial) == ("New York, NY", "Nearest first")), str(user_preferences(initial) if initial else None))
        judge.check("preferences_persisted", bool(after and user_preferences(after) == ("Chicago, IL", "Newest pets first")), str(user_preferences(after) if after else None))
        judge.check(
            "exact_preference_change",
            bool(
                initial
                and after
                and matches_expected_mutation(
                    initial,
                    after,
                    "UPDATE user SET home_location=?, sort_preference=? WHERE lower(email)=lower(?)",
                    ("Chicago, IL", "Newest pets first", "alice.j@test.com"),
                )
            ),
            "only Alice's two requested preference fields may change",
        )
        judge.check("answer_complete", contains_all(answer, ["Chicago, IL", "Newest pets first"]), repr(answer))
    elif index == 6:
        judge.check("guide_opened", visited_path(trajectory, "/guides/pet-adoption-checklist"), "guide detail")
        judge.check("all_checklist_items_reported", checklist_answer(answer, "adoption"), repr(answer))
    elif index == 7:
        judge.check("senior_chicago_filters_used", visited_query(trajectory, "/pets", FILTERS[7]), str(FILTERS[7]))
        judge.check("both_details_opened", visited_path(trajectory, "/pets/maple-senior-beagle") and visited_path(trajectory, "/pets/ollie-poodle-mix"), "Maple + Ollie")
        judge.check("winner_identified", winner(answer, "Ollie", ["Ollie", "Maple"], "days"), repr(answer))
        judge.check("ollie_days", numeric_fact(answer, 5, "days", "Ollie", ["Ollie", "Maple"]), repr(answer))
        judge.check("maple_days", numeric_fact(answer, 18, "days", "Maple", ["Ollie", "Maple"]), repr(answer))
    elif index == 8:
        initial, after = state_databases(judge, args)
        judge.check("search_and_detail", search_used(trajectory, "Luna") and visited_path(trajectory, "/pets/luna-domestic-shorthair"), "search + Luna detail")
        initial_names = favorite_names(initial) if initial else []
        after_names = favorite_names(after) if after else []
        judge.check("luna_newly_saved", "Luna Domestic Shorthair" not in initial_names and "Luna Domestic Shorthair" in after_names, f"before={initial_names} after={after_names}")
        judge.check("favorite_count", len(after_names) == 3, str(after_names))
        judge.check(
            "exact_favorite_change",
            bool(
                initial
                and after
                and matches_expected_mutation(
                    initial,
                    after,
                    "INSERT INTO saved_item(user_id, listing_id) "
                    "SELECT u.id,l.id FROM user u,listing l "
                    "WHERE lower(u.email)=lower(?) AND l.slug=?",
                    ("alice.j@test.com", "luna-domestic-shorthair"),
                )
            ),
            "only Alice's Luna favorite may be added",
        )
        judge.check("answer_count", numeric_fact(answer, 3, "count"), repr(answer))
    elif index == 9:
        initial, after = state_databases(judge, args)
        judge.check("search_and_detail", search_used(trajectory, "Nori") and visited_path(trajectory, "/pets/nori-rabbit"), "search + Nori detail")
        judge.check("requested_message_entered", entered_text(trajectory, INQUIRY_MESSAGE, "/pets/nori-rabbit"), "exact inquiry text")
        before_rows = inquiry_rows(initial) if initial else []
        after_rows = inquiry_rows(after) if after else []
        expected = {"slug": "nori-rabbit", "message": INQUIRY_MESSAGE, "status": "Submitted"}
        judge.check("inquiry_newly_persisted", expected not in before_rows and expected in after_rows, f"before={before_rows} after={after_rows}")
        judge.check(
            "exact_inquiry_change",
            bool(
                initial
                and after
                and matches_expected_mutation(
                    initial,
                    after,
                    "INSERT INTO inquiry(user_id, listing_id, message, status) "
                    "SELECT u.id,l.id,?,? FROM user u,listing l "
                    "WHERE lower(u.email)=lower(?) AND l.slug=?",
                    (INQUIRY_MESSAGE, "Submitted", "alice.j@test.com", "nori-rabbit"),
                )
            ),
            "only Alice's requested Nori inquiry may be added",
        )
        judge.check("answer_status", inquiry_submitted(answer), repr(answer))
    elif index == 10:
        judge.check("requested_filters_used", visited_query(trajectory, "/pets", FILTERS[10]), str(FILTERS[10]))
        matches = db_query(
            initial_read_db,
            "SELECT slug,name,adoption_fee FROM listing "
            "WHERE species=? AND location=? AND age=? AND good_with_dogs=1 ORDER BY id",
            ("Dog", "Boston, MA", "Young"),
        ) if initial_read_db else []
        judge.check("expected_match_set_is_usable", len(matches) == 3, f"matches={len(matches)}")
        judge.check(
            "all_matching_details_opened",
            bool(matches) and all(visited_path(trajectory, f"/pets/{row['slug']}") for row in matches),
            ", ".join(str(row["slug"]) for row in matches),
        )
        lowest_fee = min((int(row["adoption_fee"]) for row in matches), default=-1)
        winners = [row for row in matches if int(row["adoption_fee"]) == lowest_fee]
        judge.check("unique_lowest_fee_pet", len(winners) == 1, f"lowest={lowest_fee} winners={len(winners)}")
        judge.check(
            "lowest_fee_pet_identified",
            len(winners) == 1 and winner(answer, winners[0]["name"], [row["name"] for row in matches], "fee"),
            repr(answer),
        )
        for row in matches:
            judge.check(
                f"fee_bound_to_{row['slug']}",
                numeric_fact(answer, int(row["adoption_fee"]), "fee", row["name"], [r["name"] for r in matches]),
                repr(answer),
            )
    elif index == 11:
        judge.check("sorted_second_page_opened", visited_query(trajectory, "/pets", FILTERS[11]), str(FILTERS[11]))
        rows = db_query(
            initial_read_db,
            "SELECT slug,name,breed,shelter FROM listing WHERE species=? ORDER BY lower(name),id LIMIT 1 OFFSET 12",
            ("Dog",),
        ) if initial_read_db else []
        judge.check("second_page_has_first_result", len(rows) == 1, f"matches={len(rows)}")
        expected = rows[0] if rows else None
        judge.check(
            "first_result_detail_opened",
            bool(expected and visited_path(trajectory, f"/pets/{expected['slug']}")),
            str(expected["slug"] if expected else None),
        )
        judge.check(
            "answer_complete",
            bool(expected and contains_all(answer, [expected["name"], expected["breed"], expected["shelter"]])),
            repr(answer),
        )
    elif index == 12:
        judge.check(
            "location_bound_search_used",
            visited_query(trajectory, "/search", {"q": "Seattle Humane", "location": "Seattle, WA"}),
            "q=Seattle Humane, location=Seattle, WA",
        )
        rows = db_query(
            initial_read_db,
            "SELECT slug,name,adoption_fee,coat,color FROM listing "
            "WHERE species=? AND age=? AND location=? AND lower(shelter)=lower(?)",
            ("Cat", "Baby", "Seattle, WA", "Seattle Humane"),
        ) if initial_read_db else []
        judge.check("search_has_one_baby_cat", len(rows) == 1, f"matches={len(rows)}")
        expected = rows[0] if rows else None
        judge.check(
            "baby_cat_detail_opened",
            bool(expected and visited_path(trajectory, f"/pets/{expected['slug']}")),
            str(expected["slug"] if expected else None),
        )
        judge.check(
            "answer_detail_facts",
            bool(expected and contains_all(answer, [expected["name"], expected["coat"], expected["color"]])),
            repr(answer),
        )
        judge.check(
            "answer_fee",
            bool(expected and numeric_fact(answer, int(expected["adoption_fee"]), "fee")),
            repr(answer),
        )
    elif index == 13:
        judge.check("site_search_used", search_used(trajectory, "rabbit housing"), "search q contains rabbit housing")
        rows = db_query(
            initial_read_db,
            "SELECT slug,section_heading,checklist FROM guide WHERE lower(title)=lower(?)",
            ("Rabbit housing essentials",),
        ) if initial_read_db else []
        judge.check("guide_fact_source_is_unique", len(rows) == 1, f"matches={len(rows)}")
        expected = rows[0] if rows else None
        checklist = [item.strip() for item in str(expected["checklist"]).split("|") if item.strip()] if expected else []
        judge.check(
            "guide_opened",
            bool(expected and visited_path(trajectory, f"/guides/{expected['slug']}")),
            str(expected["slug"] if expected else None),
        )
        judge.check(
            "heading_and_checklist_reported",
            bool(expected and len(checklist) == 3 and checklist_answer(answer, "rabbit")),
            repr(answer),
        )
    elif index == 14:
        judge.check(
            "login_search_and_detail",
            visited_path(trajectory, "/login")
            and search_used(trajectory, "Milo")
            and visited_path(trajectory, "/pets/milo-labrador-mix")
            and visited_path(trajectory, "/account"),
            "login + Milo search + detail + account",
        )
        judge.check(
            "visible_save_action_used",
            save_action_used(trajectory),
            "click locator on Milo detail",
        )
        initial_names = favorite_names(initial_read_db) if initial_read_db else []
        after_names = favorite_names(after_read_db) if after_read_db else []
        milo_rows = db_query(
            initial_read_db,
            "SELECT name FROM listing WHERE lower(name)=lower(?)",
            ("Milo Labrador Mix",),
        ) if initial_read_db else []
        milo_name = str(milo_rows[0]["name"]) if len(milo_rows) == 1 else ""
        judge.check("milo_fact_source_is_unique", bool(milo_name), f"matches={len(milo_rows)}")
        judge.check("milo_starts_saved", bool(milo_name and milo_name in initial_names), str(initial_names))
        judge.check(
            "favorite_set_unchanged",
            bool(initial_read_db and after_read_db and initial_names == after_names),
            f"before={initial_names} after={after_names}",
        )
        judge.check("answer_already_saved", no_duplicate(answer), repr(answer))
        judge.check("answer_count", numeric_fact(answer, len(initial_names), "count"), repr(answer))
    else:
        judge.check("known_task", False, f"unsupported task index {index}")

    judge.emit()


def main(index: int):
    try:
        _main(index)
    except SystemExit:
        raise
    except Exception as exception:
        judge = Judge(f"Petfinder--{index}")
        judge.check(
            "verifier_input_valid",
            False,
            f"{type(exception).__name__}: {exception}",
        )
        judge.emit()
