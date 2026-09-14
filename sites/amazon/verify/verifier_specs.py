#!/usr/bin/env python3
"""Seed-derived grading rules for the accepted Amazon tasks."""

from __future__ import annotations

import re
from typing import Any, Callable, Sequence

from verify_lib import (
    Judge,
    appears_in_order,
    changed_tables,
    check_common,
    check_read_only_databases,
    clicked_on_path,
    clicked_transition,
    contains_all,
    contains_any,
    final_answer,
    has_money,
    has_number,
    login_submitted_as,
    load_run,
    normalize_text,
    numeric_value,
    parse_args,
    product_path,
    products,
    resolve_db,
    row_dicts,
    run_safely,
    search_used,
    selected_product,
    spec_value,
    visited_path,
)

DEMO_EMAIL = "demo@amazon.com"
DEMO_PASSWORD = "demo1234"


def _text(product: dict[str, Any]) -> str:
    return normalize_text(" ".join([
        str(product.get("name") or ""),
        str(product.get("brand") or ""),
        str(product.get("category_slug") or ""),
        str(product.get("subcategory") or ""),
        str(product.get("description") or ""),
        " ".join(str(value) for value in product.get("tags") or []),
        " ".join(str(value) for value in product.get("feature_list") or []),
        " ".join(f"{key} {value}" for key, value in (product.get("spec") or {}).items()),
    ]))


def _has_words(product: dict[str, Any], *words: str) -> bool:
    haystack = _text(product)
    return all(normalize_text(word) in haystack for word in words)


def _variant_values(product: dict[str, Any], key: str) -> list[str]:
    wanted = normalize_text(key)
    for observed, values in (product.get("variants") or {}).items():
        if normalize_text(observed) == wanted and isinstance(values, list):
            return [str(value) for value in values]
    return []


def _variant_contains(product: dict[str, Any], key: str, value: str) -> bool:
    needle = normalize_text(value)
    return any(needle in normalize_text(observed) for observed in _variant_values(product, key))


def _exact_name(answer: str, product: dict[str, Any]) -> bool:
    return contains_all(answer, (product["name"],))


def _prior_rows_preserved(
    before: Sequence[dict[str, Any]],
    after: Sequence[dict[str, Any]],
) -> bool:
    after_by_id = {row["id"]: row for row in after}
    return all(after_by_id.get(row["id"]) == row for row in before)


def _other_account_rows(path: str, table: str) -> list[dict[str, Any]]:
    if table not in {"wishlist_items", "cart_items"}:
        raise ValueError(f"unsupported account table: {table}")
    return row_dicts(
        path,
        f'''SELECT item.*
            FROM "{table}" AS item
            LEFT JOIN users AS owner ON owner.id=item.user_id
            WHERE owner.id IS NULL OR lower(owner.email)<>lower(?)
            ORDER BY item.id''',
        (DEMO_EMAIL,),
    )


def _waterproof_filter_match(product: dict[str, Any]) -> bool:
    tags = product.get("tags") or []
    return (
        normalize_text(spec_value(product, "Waterproof")) == "yes"
        and any("waterproof" in normalize_text(tag) for tag in tags)
    )


def _oven_safe(product: dict[str, Any]) -> bool:
    value = normalize_text(spec_value(product, "Oven Safe"))
    return value in {"yes", "true"} or numeric_value(value) > 0


def _supports_hdmi(product: dict[str, Any]) -> bool:
    value = normalize_text(spec_value(product, "HDMI"))
    return value in {"yes", "true", "supported"} or bool(
        re.search(r"\b(?:720p|1080p|4k|8k)\b", value)
    )


def _paired_names_and_prices(
    answer: str,
    expected: Sequence[dict[str, Any]],
    *,
    require_order: bool = False,
) -> bool:
    normalized = normalize_text(answer)
    located: list[tuple[int, dict[str, Any]]] = []
    cursor = 0
    for product in expected:
        position = normalized.find(normalize_text(product["name"]), cursor if require_order else 0)
        if position < 0:
            return False
        located.append((position, product))
        if require_order:
            cursor = position + len(normalize_text(product["name"]))
    located.sort(key=lambda item: item[0])
    for index, (position, product) in enumerate(located):
        end = located[index + 1][0] if index + 1 < len(located) else len(normalized)
        if not has_money(normalized[position:end], product["price"]):
            return False
    return True


def _mentions_unexpected_products(
    answer: str,
    catalog: Sequence[dict[str, Any]],
    expected: Sequence[dict[str, Any]],
) -> bool:
    normalized = normalize_text(answer)
    expected_ids = {product["id"] for product in expected}
    return any(
        product["id"] not in expected_ids
        and normalize_text(product["name"]) in normalized
        for product in catalog
    )


def _selected(
    judge: Judge,
    trajectory: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
    label: str,
) -> dict[str, Any] | None:
    product = selected_product(trajectory, candidates)
    judge.check(label, product is not None, f"eligible={[row['slug'] for row in candidates]}")
    return product


def _readonly_context(task_id: str):
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(task_id)
    check_common(judge, trajectory, task_id)
    initial, _ = check_read_only_databases(judge, args)
    catalog = products(initial) if initial else []
    return args, trajectory, judge, catalog


def _finish(judge: Judge) -> None:
    judge.emit()


def verify_0() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--0")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if normalize_text(p["name"]) == "xbox wireless controller" and _variant_contains(p, "color", "green") and p["rating"] > 4]
    judge.check("searched_xbox_controller_with_green_rating_filters", search_used(trajectory, terms=("xbox", "controller"), params={"color": "green", "min_rating": ("4", "4.0")}), "q=xbox controller, color=green, min_rating=4")
    product = _selected(judge, trajectory, candidates, "opened_eligible_green_controller")
    if product:
        judge.check("answer_product_color_rating", _exact_name(answer, product) and contains_all(answer, ("green",)) and has_number(answer, product["rating"]), repr(answer))
    _finish(judge)


def _golf_candidates(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        p for p in catalog
        if "golf polo" in normalize_text(p["name"])
        and 50 <= p["price"] <= 75
        and _variant_contains(p, "size", "M")
    ]


def verify_1() -> None:
    task_id = "Amazon--1"
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    judge = Judge(task_id)
    check_common(judge, trajectory, task_id)
    judge.check("login_as_demo", login_submitted_as(trajectory, DEMO_EMAIL, DEMO_PASSWORD), DEMO_EMAIL)
    judge.check("searched_and_sorted_golf_polos", search_used(trajectory, terms=("golf", "polo"), params={"size": "M", "min_price": ("50", "50.0"), "max_price": ("75", "75.0"), "sort": ("price_asc", "price-low-to-high")}), "size=M, $50-$75, price ascending")
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    if initial and after:
        candidates = sorted(_golf_candidates(products(initial)), key=lambda p: (p["price"], p["id"]))
        target = candidates[0] if candidates else None
        judge.check("seed_has_unique_lowest_medium_polo", bool(target) and (len(candidates) == 1 or target["price"] < candidates[1]["price"]), repr([(p["slug"], p["price"]) for p in candidates]))
        if target:
            path = product_path(target)
            judge.check("opened_lowest_eligible_polo", clicked_transition(trajectory, "/search", path), path)
            judge.check("wishlist_action_on_product", clicked_on_path(trajectory, path), path)
            judge.check("wishlist_opened_for_confirmation", visited_path(trajectory, "/wishlist"), "/wishlist")
            before = row_dicts(initial, "SELECT w.id,w.user_id,w.product_id,w.added_at,p.slug FROM wishlist_items w JOIN users u ON u.id=w.user_id JOIN products p ON p.id=w.product_id WHERE lower(u.email)=lower(?) ORDER BY w.id", (DEMO_EMAIL,))
            now = row_dicts(after, "SELECT w.id,w.user_id,w.product_id,w.added_at,p.slug FROM wishlist_items w JOIN users u ON u.id=w.user_id JOIN products p ON p.id=w.product_id WHERE lower(u.email)=lower(?) ORDER BY w.id", (DEMO_EMAIL,))
            before_ids = {row["id"] for row in before}
            created = [row for row in now if row["id"] not in before_ids]
            judge.check("demo_wishlist_rows_preserved", _prior_rows_preserved(before, now), f"before={before} after={now}")
            judge.check("exact_target_added_to_demo_wishlist", len(created) == 1 and created[0]["slug"] == target["slug"] and len(now) == len(before) + 1, f"before={before} after={now}")
            judge.check("other_accounts_wishlist_unchanged", _other_account_rows(initial, "wishlist_items") == _other_account_rows(after, "wishlist_items"), "non-demo rows are byte-equivalent")
            judge.check("answer_saved_name_and_price", _exact_name(answer, target) and has_money(answer, target["price"]), repr(answer))
        judge.check("only_wishlist_changed", changed_tables(initial, after) == {"wishlist_items"}, repr(changed_tables(initial, after)))
    _finish(judge)


def verify_2() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--2")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if "gaming desktop" in _text(p) and normalize_text(spec_value(p, "Operating System")) == "windows 11 home" and "1tb" in normalize_text(spec_value(p, "Storage"))]
    judge.check("searched_gaming_desktop", search_used(trajectory, terms=("gaming", "desktop")), "q includes gaming desktop")
    product = _selected(judge, trajectory, candidates, "opened_eligible_gaming_desktop")
    if product:
        judge.check("answer_name_os_storage", _exact_name(answer, product) and contains_all(answer, ("Windows 11 Home", "1TB")), repr(answer))
    _finish(judge)


def verify_3() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--3")
    answer = final_answer(trajectory)
    candidates = sorted([p for p in catalog if normalize_text(p.get("subcategory")) == "climbing"], key=lambda p: (-p["price"], p["id"]))
    expected = candidates[:3]
    judge.check("searched_climbing_sorted_high_to_low", search_used(trajectory, terms=("climbing",), params={"sort": ("price_desc", "price-high-to-low")}), "sort=price_desc")
    judge.check("seed_has_three_ranked_results", len(expected) == 3, repr([(p["name"], p["price"]) for p in expected]))
    judge.check(
        "answer_exact_top_three_with_prices",
        len(expected) == 3
        and appears_in_order(answer, [p["name"] for p in expected])
        and _paired_names_and_prices(answer, expected, require_order=True)
        and not _mentions_unexpected_products(answer, candidates, expected),
        repr(answer),
    )
    _finish(judge)


def verify_4() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--4")
    answer = final_answer(trajectory)
    candidates = sorted([p for p in catalog if "nintendo switch lite" in normalize_text(p["name"]) and normalize_text(p["condition"]) == "used - good"], key=lambda p: (p["price"], p["id"]))
    target = candidates[0] if candidates else None
    judge.check("searched_used_good_switch_sorted_low_to_high", search_used(trajectory, terms=("nintendo", "switch", "lite"), params={"condition": "Used - Good", "sort": ("price_asc", "price-low-to-high")}), "Used - Good, sort=price_asc")
    judge.check("seed_has_unique_cheapest_used_good_switch", bool(target) and (len(candidates) == 1 or target["price"] < candidates[1]["price"]), repr([(p["slug"], p["price"]) for p in candidates]))
    if target:
        judge.check("answer_cheapest_product_condition_price", _exact_name(answer, target) and contains_all(answer, ("Used - Good",)) and has_money(answer, target["price"]), repr(answer))
    _finish(judge)


def verify_5() -> None:
    task_id = "Amazon--5"
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    judge = Judge(task_id)
    check_common(judge, trajectory, task_id)
    judge.check("login_as_demo", login_submitted_as(trajectory, DEMO_EMAIL, DEMO_PASSWORD), DEMO_EMAIL)
    judge.check("searched_blue_iphone_128gb", search_used(trajectory, terms=("iphone", "12", "pro", "128gb"), params={"color": "blue"}), "q=iPhone 12 Pro 128GB, color=blue")
    initial = resolve_db(args.initial_db, args.container, "instance_seed")
    after = resolve_db(args.after_db, args.container, "instance")
    judge.check("databases_readable", bool(initial and after), f"initial={initial} after={after}")
    if initial and after:
        catalog = products(initial)
        candidates = [p for p in catalog if normalize_text(p["name"]) == "apple iphone 12 pro 128gb" and _variant_contains(p, "color", "blue")]
        target = candidates[0] if len(candidates) == 1 else None
        judge.check("seed_has_unique_blue_iphone", target is not None, repr([p["slug"] for p in candidates]))
        if target:
            path = product_path(target)
            judge.check("opened_target_iphone", clicked_transition(trajectory, "/search", path), path)
            judge.check("submitted_add_to_cart", clicked_transition(trajectory, path, "/bag"), f"{path} -> /bag")
            before = row_dicts(initial, "SELECT c.id,c.user_id,c.product_id,c.quantity,c.variant,c.added_at,p.slug FROM cart_items c JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id WHERE lower(u.email)=lower(?) ORDER BY c.id", (DEMO_EMAIL,))
            now = row_dicts(after, "SELECT c.id,c.user_id,c.product_id,c.quantity,c.variant,c.added_at,p.slug FROM cart_items c JOIN users u ON u.id=c.user_id JOIN products p ON p.id=c.product_id WHERE lower(u.email)=lower(?) ORDER BY c.id", (DEMO_EMAIL,))
            before_ids = {row["id"] for row in before}
            created = [row for row in now if row["id"] not in before_ids]
            judge.check("demo_cart_rows_preserved", _prior_rows_preserved(before, now), f"before={before} after={now}")
            judge.check("exactly_one_target_iphone_added", len(created) == 1 and created[0]["slug"] == target["slug"] and created[0]["quantity"] == 1 and len(now) == len(before) + 1, f"before={before} after={now}")
            judge.check("other_accounts_cart_unchanged", _other_account_rows(initial, "cart_items") == _other_account_rows(after, "cart_items"), "non-demo rows are byte-equivalent")
            subtotal = sum(row["quantity"] * next(p["price"] for p in catalog if p["slug"] == row["slug"]) for row in now)
            judge.check("answer_cart_name_and_subtotal", _exact_name(answer, target) and has_money(answer, subtotal), f"subtotal={subtotal:.2f} answer={answer!r}")
        judge.check("only_cart_changed", changed_tables(initial, after) == {"cart_items"}, repr(changed_tables(initial, after)))
    _finish(judge)


def _generic_product_task(
    task_id: str,
    selector: Callable[[dict[str, Any]], bool],
    search_ok: Callable[[dict[str, Any]], bool],
    answer_ok: Callable[[str, dict[str, Any]], bool],
) -> None:
    _, trajectory, judge, catalog = _readonly_context(task_id)
    answer = final_answer(trajectory)
    candidates = [product for product in catalog if selector(product)]
    judge.check("required_search_and_filters", search_ok(trajectory), task_id)
    product = _selected(judge, trajectory, candidates, "opened_eligible_product")
    if product:
        judge.check("answer_matches_selected_product", answer_ok(answer, product), repr(answer))
    _finish(judge)


def verify_6() -> None:
    _generic_product_task(
        "Amazon--6",
        lambda p: normalize_text(p.get("subcategory")) == "baby strollers" and 100 <= p["price"] <= 200 and _variant_contains(p, "color", "black") and p["review_count"] > 20000 and p["rating"] >= 4,
        lambda t: search_used(t, terms=("stroller",), params={"color": "black", "min_price": ("100", "100.0"), "max_price": ("200", "200.0"), "min_rating": ("4", "4.0")}),
        lambda a, p: _exact_name(a, p) and has_number(a, p["rating"]) and has_number(a, p["review_count"], 0.5),
    )


def verify_7() -> None:
    _generic_product_task(
        "Amazon--7",
        lambda p: "hiking boot" in normalize_text(p["name"]) and _waterproof_filter_match(p) and p["rating"] >= 4 and _variant_contains(p, "size", "6") and ("women" in _text(p) or "womens" in _text(p)),
        lambda t: search_used(t, terms=("hiking", "boots"), params={"feature": "waterproof", "min_rating": ("4", "4.0"), "size": "6"}),
        lambda a, p: _exact_name(a, p) and has_number(a, p["rating"]) and contains_all(a, ("waterproof",)) and has_number(a, 6),
    )


def _tablet_screen(product: dict[str, Any]) -> float:
    direct = spec_value(product, "screen_size_inches", None)
    return float(direct) if isinstance(direct, (int, float)) else numeric_value(spec_value(product, "Screen Size"))


def verify_8() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--8")
    answer = final_answer(trajectory)
    candidates = sorted([p for p in catalog if normalize_text(p["brand"]) == "samsung" and "tablet" in _text(p) and normalize_text(spec_value(p, "OS")) == "android" and 10 <= _tablet_screen(p) <= 10.9], key=lambda p: (p["price"], p["id"]))
    target = candidates[0] if candidates else None
    judge.check("searched_samsung_tablet_sorted_low_to_high", search_used(trajectory, terms=("samsung", "tablet"), params={"brand": "Samsung", "sort": ("price_asc", "price-low-to-high")}), "brand=Samsung, sort=price_asc")
    judge.check("seed_has_unique_cheapest_tablet", bool(target) and (len(candidates) == 1 or target["price"] < candidates[1]["price"]), repr([(p["slug"], p["price"]) for p in candidates]))
    if target:
        judge.check("opened_cheapest_tablet", clicked_transition(trajectory, "/search", product_path(target)), product_path(target))
        judge.check("answer_name_screen_price", _exact_name(answer, target) and has_number(answer, _tablet_screen(target)) and has_money(answer, target["price"]), repr(answer))
    _finish(judge)


def verify_9() -> None:
    _generic_product_task(
        "Amazon--9",
        lambda p: "dog bed" in normalize_text(p["name"]) and (normalize_text(spec_value(p, "Washable")) == "yes" or normalize_text(spec_value(p, "Machine Washable")) == "yes") and numeric_value(spec_value(p, "Length")) >= 30,
        lambda t: search_used(t, terms=("dog", "bed"), params={"feature": "washable"}),
        lambda a, p: _exact_name(a, p) and contains_all(a, ("washable",)) and has_number(a, numeric_value(spec_value(p, "Length"))),
    )


def verify_10() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--10")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if "protection plan" in normalize_text(p["name"]) and normalize_text(spec_value(p, "Plan Term")) == "2 years" and "playstation 4" in normalize_text(spec_value(p, "Covers"))]
    judge.check("searched_ps4_protection_plan", search_used(trajectory, terms=("playstation", "4")), "q includes PlayStation 4")
    product = _selected(judge, trajectory, candidates, "opened_two_year_ps4_plan")
    if product:
        judge.check("answer_plan_and_cost", _exact_name(answer, product) and has_money(answer, product["price"]), repr(answer))
    _finish(judge)


def verify_12() -> None:
    args, trajectory, judge, catalog = _readonly_context("Amazon--12")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if "ride on" in normalize_text(p["name"]) and p["review_count"] >= 100 and p["rating"] >= 4]
    judge.check("searched_ride_on_car", search_used(trajectory, terms=("ride", "on", "car")), "q includes ride on car")
    product = _selected(judge, trajectory, candidates, "opened_eligible_ride_on_car")
    if product:
        db_path = resolve_db(args.initial_db, args.container, "instance_seed")
        reviews = row_dicts(db_path, "SELECT r.title,r.body,r.rating,r.created_at,u.name AS author FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.product_id=? ORDER BY r.rating DESC,r.created_at DESC LIMIT 1", (product["id"],)) if db_path else []
        top = reviews[0] if reviews else None
        judge.check("seed_has_top_review", top is not None, repr(top))
        if top:
            judge.check("answer_product_and_top_review", _exact_name(answer, product) and contains_all(answer, (top["title"], top["author"])), repr(answer))
    _finish(judge)


def verify_13() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--13")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if normalize_text(p.get("subcategory")) == "men's big & tall" and "hoodie" in normalize_text(p["name"]) and 25 <= p["price"] <= 50 and bool(p["is_bestseller"]) and _variant_contains(p, "color", "black")]
    judge.check("searched_bestselling_black_big_tall_hoodies", search_used(trajectory, terms=("hoodie",), params={"color": "black", "min_price": ("25", "25.0"), "max_price": ("50", "50.0"), "bestseller": "1"}), "black, $25-$50, bestseller")
    judge.check("seed_has_matching_hoodies", len(candidates) >= 1, repr([(p["name"], p["price"]) for p in candidates]))
    judge.check(
        "answer_lists_all_matching_names_and_prices",
        bool(candidates)
        and _paired_names_and_prices(answer, candidates)
        and not _mentions_unexpected_products(answer, catalog, candidates),
        repr(answer),
    )
    _finish(judge)


def verify_14() -> None:
    _generic_product_task(
        "Amazon--14",
        lambda p: normalize_text(p.get("subcategory")) == "surge protectors" and normalize_text(p["condition"]) == "new" and 6 <= numeric_value(spec_value(p, "Outlets")) <= 8 and p["price"] < 25 and p["rating"] >= 4,
        lambda t: search_used(t, terms=("surge", "protector"), params={"condition": "New", "max_price": ("25", "25.0"), "min_rating": ("4", "4.0")}),
        lambda a, p: _exact_name(a, p) and has_number(a, numeric_value(spec_value(p, "Outlets"))) and has_number(a, p["rating"]) and has_money(a, p["price"]),
    )


def verify_21() -> None:
    _generic_product_task(
        "Amazon--21",
        lambda p: normalize_text(p.get("subcategory")) == "coffee makers" and 100 <= p["price"] <= 200 and p["rating"] >= 4 and numeric_value(spec_value(p, "Capacity")) == 12 and "stainless steel" in normalize_text(spec_value(p, "Material")) and normalize_text(spec_value(p, "Programmable")) == "yes",
        lambda t: search_used(t, terms=("coffee", "maker"), params={"min_price": ("100", "100.0"), "max_price": ("200", "200.0"), "min_rating": ("4", "4.0")}),
        lambda a, p: _exact_name(a, p) and has_money(a, p["price"]) and has_number(a, p["rating"]) and has_number(a, 12),
    )


def _piece_count(product: dict[str, Any]) -> float:
    for key in ("Pieces", "Piece Count", "Set Size"):
        value = numeric_value(spec_value(product, key))
        if value >= 0:
            return value
    return numeric_value(_text(product))


def verify_22() -> None:
    _generic_product_task(
        "Amazon--22",
        lambda p: "cookware" in _text(p) and p["price"] < 150 and _piece_count(p) >= 10 and _has_words(p, "nonstick") and _oven_safe(p),
        lambda t: search_used(t, terms=("cookware",), params={"max_price": ("150", "150.0")}),
        lambda a, p: _exact_name(a, p) and has_money(a, p["price"]) and has_number(a, _piece_count(p)) and contains_any(a, ("nonstick", "non-stick")) and contains_all(a, ("oven",)),
    )


def verify_27() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--27")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if normalize_text(p.get("subcategory")) == "usb-c hubs" and p["price"] < 50 and numeric_value(spec_value(p, "Ports")) >= 4 and normalize_text(spec_value(p, "SD Card")) == "yes" and _supports_hdmi(p) and "macbook pro" in normalize_text(spec_value(p, "Compatible"))]
    candidates.sort(key=lambda p: (-int(bool(p["is_bestseller"])), -p["review_count"], p["id"]))
    target = candidates[0] if candidates else None
    judge.check("searched_hub_sorted_best_sellers", search_used(trajectory, terms=("usb", "hub"), params={"max_price": ("50", "50.0"), "sort": ("bestseller", "best-sellers")}), "max_price=50, sort=bestseller")
    judge.check("seed_has_ranked_matching_hub", target is not None, repr([(p["slug"], p["is_bestseller"], p["review_count"]) for p in candidates]))
    if target:
        judge.check("opened_first_matching_hub", clicked_transition(trajectory, "/search", product_path(target)), product_path(target))
        judge.check("answer_name_ports_price", _exact_name(answer, target) and has_number(answer, numeric_value(spec_value(target, "Ports"))) and has_money(answer, target["price"]), repr(answer))
    _finish(judge)


def verify_30() -> None:
    _, trajectory, judge, catalog = _readonly_context("Amazon--30")
    answer = final_answer(trajectory)
    candidates = [p for p in catalog if normalize_text(p.get("subcategory")) == "fiction" and str(p.get("release_date") or "").startswith("2024-") and p["review_count"] >= 50]
    candidates.sort(key=lambda p: (-p["rating"], -p["review_count"], p["id"]))
    target = candidates[0] if candidates else None
    judge.check("searched_2024_fiction_sorted_rating", search_used(trajectory, terms=("fiction", "book", "2024"), params={"sort": ("rating", "avg_rating")}), "q includes fiction book 2024, sort=rating")
    judge.check("seed_has_ranked_fiction_winner", target is not None, repr([(p["name"], p["rating"], p["review_count"]) for p in candidates]))
    if target:
        judge.check("answer_highest_rated_book", _exact_name(answer, target) and has_number(answer, target["rating"]) and has_number(answer, target["review_count"], 0.5), repr(answer))
    _finish(judge)


def verify_39() -> None:
    _generic_product_task(
        "Amazon--39",
        lambda p: normalize_text(p.get("subcategory")) == "travel guides" and "japan" in _text(p) and str(p.get("release_date") or "").startswith("2024-") and p["review_count"] >= 20,
        lambda t: search_used(t, terms=("japan", "travel", "guide", "2024")),
        lambda a, p: _exact_name(a, p) and has_number(a, 2024) and has_number(a, p["review_count"], 0.5) and has_money(a, p["price"]),
    )


def verify_40() -> None:
    def answer_ok(answer: str, product: dict[str, Any]) -> bool:
        colors = _variant_values(product, "color")
        return (
            _exact_name(answer, product)
            and has_number(answer, len(colors))
            and contains_all(answer, (product["return_policy"], product["delivery_estimate"]))
        )

    _generic_product_task(
        "Amazon--40",
        lambda p: "yoga mat" in _text(p) and "women" in _text(p) and _variant_contains(p, "color", "purple") and numeric_value(spec_value(p, "Thickness")) >= 5 and p["rating"] >= 4 and p["price"] < 30,
        lambda t: search_used(t, terms=("yoga", "mat"), params={"color": "purple", "max_price": ("30", "30.0"), "min_rating": ("4", "4.0")}),
        answer_ok,
    )


TASKS: dict[str, Callable[[], None]] = {
    "0": verify_0,
    "1": verify_1,
    "2": verify_2,
    "3": verify_3,
    "4": verify_4,
    "5": verify_5,
    "6": verify_6,
    "7": verify_7,
    "8": verify_8,
    "9": verify_9,
    "10": verify_10,
    "12": verify_12,
    "13": verify_13,
    "14": verify_14,
    "21": verify_21,
    "22": verify_22,
    "27": verify_27,
    "30": verify_30,
    "39": verify_39,
    "40": verify_40,
}


def run_task(task_number: str) -> None:
    task_id = f"Amazon--{task_number}"
    callback = TASKS.get(str(task_number))
    if callback is None:
        raise ValueError(f"unsupported Amazon task: {task_number}")
    run_safely(task_id, callback)
