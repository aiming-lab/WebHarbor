#!/usr/bin/env python3
"""Deterministic verifier contract for the Best Buy mirror."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import parse_qs, urlparse


SITE = "bestbuy"
DEFAULT_CONTAINER = os.environ.get("WH_CONTAINER", "wh-review")
TABLES = {
    "brands", "cart_items", "categories", "compare_items", "deals",
    "delivery_options", "order_items", "orders", "payment_mocks",
    "pickup_slots", "products", "protection_plans", "reviews",
    "reward_accounts", "reward_activities", "search_logs",
    "store_inventory", "stores", "support_articles", "support_tickets",
    "users", "wishlist_items",
}


class InfraError(Exception):
    pass


class TaskFailure(Exception):
    pass


def require(condition: object, reason: str) -> None:
    if not condition:
        raise TaskFailure(reason)


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", "-", text)
    text = re.sub(r"(?<=\d)\s+(?=mm\b)", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_run(run_dir: str) -> dict[str, object]:
    directory = Path(run_dir).resolve(strict=True)
    trajectory_path = directory / "trajectory.json"
    if not trajectory_path.is_file():
        raise InfraError("trajectory.json is missing")
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    if not isinstance(trajectory, dict) or not isinstance(trajectory.get("steps"), list):
        raise InfraError("trajectory.json has an invalid shape")
    trajectory["_run_dir"] = str(directory)
    return trajectory


def trajectory_urls(trajectory: dict[str, object]) -> list[str]:
    values: list[str] = []
    for value in (trajectory.get("start_url"), trajectory.get("web")):
        if value:
            values.append(str(value))
    for step in trajectory.get("steps", []):
        if not isinstance(step, dict):
            raise InfraError("trajectory step is not an object")
        for key in ("url_before", "url", "url_after"):
            value = str(step.get(key) or "")
            if value and (not values or values[-1] != value):
                values.append(value)
    final_url = str(trajectory.get("final_url") or "")
    if final_url and (not values or values[-1] != final_url):
        values.append(final_url)
    return values


def _loopback(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def site_url(url: str, trajectory: dict[str, object]) -> bool:
    parsed = urlparse(url)
    start = urlparse(str(trajectory.get("start_url") or trajectory.get("web") or ""))
    return bool(
        parsed.scheme in {"http", "https"}
        and _loopback(parsed.hostname)
        and _loopback(start.hostname)
        and parsed.port == start.port
    )


def path_of(url: str) -> str:
    return (urlparse(url).path.rstrip("/") or "/")


def visited(trajectory: dict[str, object], path: str) -> bool:
    expected = path.rstrip("/") or "/"
    return any(site_url(url, trajectory) and path_of(url) == expected for url in trajectory_urls(trajectory))


def visited_in_order(trajectory: dict[str, object], paths: list[str]) -> bool:
    urls = trajectory_urls(trajectory)
    cursor = 0
    for expected in paths:
        expected = expected.rstrip("/") or "/"
        for index in range(cursor, len(urls)):
            if site_url(urls[index], trajectory) and path_of(urls[index]) == expected:
                cursor = index + 1
                break
        else:
            return False
    return True


def visited_query(
    trajectory: dict[str, object],
    path: str,
    expected: dict[str, str],
) -> bool:
    for url in trajectory_urls(trajectory):
        if not site_url(url, trajectory) or path_of(url) != (path.rstrip("/") or "/"):
            continue
        params = parse_qs(urlparse(url).query)
        if all(normalize((params.get(key) or [""])[0]) == normalize(value) for key, value in expected.items()):
            return True
    return False


def visited_search_terms(trajectory: dict[str, object], path: str, terms: list[str]) -> bool:
    for url in trajectory_urls(trajectory):
        if not site_url(url, trajectory) or path_of(url) != path:
            continue
        query = normalize((parse_qs(urlparse(url).query).get("q") or [""])[0])
        if all(normalize(term) in query for term in terms):
            return True
    return False


def final_answer(trajectory: dict[str, object]) -> str:
    return str(trajectory.get("final_answer") or "").strip()


def has_tokens(answer: str, *tokens: str) -> bool:
    normalized = normalize(answer)
    return all(normalize(token) in normalized for token in tokens)


def screenshots_valid(trajectory: dict[str, object]) -> bool:
    directory = Path(str(trajectory["_run_dir"])) / "screenshots"
    referenced: set[str] = set()
    for step in trajectory.get("steps", []):
        for key in ("screenshot_before", "screenshot_after"):
            name = str(step.get(key) or "")
            if name:
                referenced.add(Path(name).name)
    if not referenced:
        return False
    for name in referenced:
        path = directory / name
        if not path.is_file() or path.stat().st_size < 1000:
            return False
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 24:
            return False
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        if width < 300 or height < 180:
            return False
    return True


def fetch_db(container: str, kind: str) -> str:
    directory = tempfile.mkdtemp(prefix="bestbuy-verifier-")
    target = Path(directory) / f"{kind}.db"
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    result = subprocess.run(["docker", "cp", source, target], capture_output=True, text=True)
    if result.returncode:
        shutil.rmtree(directory, ignore_errors=True)
        raise InfraError(f"could not fetch {kind} database")
    return str(target)


def database(path: str | None, container: str, kind: str) -> str:
    resolved = path or fetch_db(container, kind)
    candidate = Path(resolved).resolve(strict=True)
    if not candidate.is_file():
        raise InfraError(f"{kind} database is not a regular file")
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise InfraError(f"{kind} database failed integrity_check")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise InfraError(f"{kind} database failed foreign_key_check")
    return str(candidate)


def rows(path: str, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    uri = Path(path).resolve(strict=True).as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        return connection.execute(sql, params).fetchall()


def table_rows(path: str, table: str) -> Counter[tuple[object, ...]]:
    if table not in TABLES:
        raise InfraError(f"unsupported table snapshot: {table}")
    return Counter(rows(path, f'SELECT * FROM "{table}"'))


def require_unchanged_tables(initial: str, after: str, changed: set[str]) -> None:
    unexpected = [
        table for table in sorted(TABLES - changed)
        if table_rows(initial, table) != table_rows(after, table)
    ]
    require(not unexpected, f"unexpected database changes in: {', '.join(unexpected)}")


def membership_rows(path: str, table: str) -> Counter[tuple[object, ...]]:
    if table not in {"compare_items", "wishlist_items"}:
        raise InfraError(f"unsupported membership table: {table}")
    return Counter(rows(
        path,
        f"SELECT u.email,p.sku FROM {table} x JOIN users u ON u.id=x.user_id "
        "JOIN products p ON p.id=x.product_id",
    ))


def cart_rows(path: str) -> Counter[tuple[object, ...]]:
    return Counter(rows(
        path,
        "SELECT u.email,p.sku,x.quantity,x.fulfillment_method,"
        "COALESCE(s.slug,''),COALESCE(d.slug,''),COALESCE(pp.name,'') "
        "FROM cart_items x JOIN users u ON u.id=x.user_id "
        "JOIN products p ON p.id=x.product_id "
        "LEFT JOIN stores s ON s.id=x.store_id "
        "LEFT JOIN delivery_options d ON d.id=x.delivery_option_id "
        "LEFT JOIN protection_plans pp ON pp.id=x.protection_plan_id",
    ))


def product_membership(path: str, table: str, email: str, skus: list[str]) -> set[str]:
    placeholders = ",".join("?" for _ in skus)
    result = rows(
        path,
        f"SELECT p.sku FROM {table} x JOIN users u ON u.id=x.user_id "
        f"JOIN products p ON p.id=x.product_id WHERE u.email=? AND p.sku IN ({placeholders})",
        (email, *skus),
    )
    return {str(row[0]) for row in result}


def task_0(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_search_terms(trajectory, "/search", ["dell", "touchscreen"]), "required product search was not recorded")
    require(visited(trajectory, "/product/6668953"), "requested product page was not opened")
    require(has_tokens(final_answer(trajectory), "549.99", "4.5"), "answer does not contain the frozen price and rating")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_1(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/compare"]), "required sign-in and Compare path was not recorded")
    requested = ["6668953", "6672899"]
    require(product_membership(initial, "compare_items", "alice.j@test.com", requested) == set(), "requested products were already compared initially")
    require(product_membership(after, "compare_items", "alice.j@test.com", requested) == set(requested), "after-state lacks both requested comparison products")
    require(has_tokens(final_answer(trajectory), "hp", "omnibook", "70"), "answer does not identify the cheaper product and price difference")
    require_unchanged_tables(initial, after, {"compare_items", "search_logs"})
    before_memberships = membership_rows(initial, "compare_items")
    after_memberships = membership_rows(after, "compare_items")
    added = after_memberships - before_memberships
    removed = before_memberships - after_memberships
    require(added == Counter({("alice.j@test.com", sku): 1 for sku in requested}), "comparison changes include an unexpected product or user")
    alice_before = sum(count for (email, _), count in before_memberships.items() if email == "alice.j@test.com")
    expected_evictions = max(0, alice_before + len(requested) - 4)
    require(sum(removed.values()) == expected_evictions and all(email == "alice.j@test.com" for email, _ in removed), "comparison capacity eviction is not the only removed state")


def task_2(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_query(trajectory, "/category/monitors", {"max_price": "350", "sort": "rating"}), "requested monitor filters were not recorded")
    require(visited(trajectory, "/product/6675156"), "highest-rated matching product was not opened")
    require(has_tokens(final_answer(trajectory), "playstation", "27", "4.9"), "answer does not identify the frozen top result and rating")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_3(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_search_terms(trajectory, "/search", ["canon", "t7", "lens"]), "required camera search was not recorded")
    require(visited(trajectory, "/product/6323759"), "requested camera page was not opened")
    require(has_tokens(final_answer(trajectory), "18-55mm", "75-300mm"), "answer does not contain both lens ranges")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_4(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/account/rewards"]), "required sign-in and Rewards path was not recorded")
    answer = final_answer(trajectory)
    require("1840" in normalize(answer), "answer lacks the frozen points balance")
    normalized = normalize(answer)
    require((re.search(r"\b0\b", normalized) or re.search(r"\bno\b", normalized)) and "certificate" in normalized, "answer lacks the available-certificate count")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_5(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/product/6603337"]), "required sign-in and product path was not recorded")
    initial_rows = product_membership(initial, "wishlist_items", "bob.c@test.com", ["6603337"])
    after_rows = product_membership(after, "wishlist_items", "bob.c@test.com", ["6603337"])
    require(initial_rows == set(), "requested product was already wishlisted initially")
    require(after_rows == {"6603337"}, "wishlist after-state does not contain the requested product")
    answer = final_answer(trajectory)
    require(has_tokens(answer, "echo show") and ("wishlist" in normalize(answer) or "saved" in normalize(answer)), "final answer does not confirm the requested wishlist action")
    require_unchanged_tables(initial, after, {"wishlist_items", "search_logs"})
    before_memberships = membership_rows(initial, "wishlist_items")
    after_memberships = membership_rows(after, "wishlist_items")
    require(after_memberships - before_memberships == Counter({("bob.c@test.com", "6603337"): 1}), "wishlist changes include an unexpected product or user")
    require(not (before_memberships - after_memberships), "wishlist action removed existing state")


def task_6(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/product/6501017"]), "required sign-in and product path was not recorded")
    before = rows(initial, "SELECT COUNT(*) FROM cart_items x JOIN users u ON u.id=x.user_id JOIN products p ON p.id=x.product_id WHERE u.email=? AND p.sku=?", ("bob.c@test.com", "6501017"))[0][0]
    found = rows(after, "SELECT x.quantity,x.fulfillment_method FROM cart_items x JOIN users u ON u.id=x.user_id JOIN products p ON p.id=x.product_id WHERE u.email=? AND p.sku=?", ("bob.c@test.com", "6501017"))
    require(before == 0, "requested product was already in Bob's cart initially")
    require(found == [(2, "delivery")], "cart after-state is not exactly two delivery units of the requested SKU")
    answer = final_answer(trajectory)
    normalized = normalize(answer)
    require("beats" in normalized and (re.search(r"\b2\b", normalized) or "two" in normalized) and ("cart" in normalized or "delivery" in normalized), "final answer does not confirm the requested two-unit cart action")
    require_unchanged_tables(initial, after, {"cart_items", "search_logs"})
    before_cart = cart_rows(initial)
    after_cart = cart_rows(after)
    expected = ("bob.c@test.com", "6501017", 2, "delivery", "", "", "")
    require(after_cart - before_cart == Counter({expected: 1}), "cart changes include an unexpected product, option, or user")
    require(not (before_cart - after_cart), "cart action removed or rewrote existing state")


def _new_order(initial: str, after: str, email: str) -> tuple[object, ...]:
    before_ids = {row[0] for row in rows(initial, "SELECT o.id FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=?", (email,))}
    created = rows(after, "SELECT o.id,o.order_number,o.fulfillment_method,o.shipping_name,o.shipping_city,o.shipping_state,o.shipping_zip,o.payment_brand,o.payment_last4,o.pickup_slot_label,s.slug,d.slug FROM orders o JOIN users u ON u.id=o.user_id LEFT JOIN stores s ON s.id=o.store_id LEFT JOIN delivery_options d ON d.id=o.delivery_option_id WHERE u.email=? ORDER BY o.id", (email,))
    created = [row for row in created if row[0] not in before_ids]
    require(len(created) == 1, "after-state does not contain exactly one new order")
    return created[0]


def require_checkout_effects(initial: str, after: str, email: str, order: tuple[object, ...]) -> None:
    changed = {
        "cart_items", "orders", "order_items", "payment_mocks",
        "reward_accounts", "reward_activities", "search_logs",
    }
    require_unchanged_tables(initial, after, changed)

    before_orders = table_rows(initial, "orders")
    after_orders = table_rows(after, "orders")
    added_orders = after_orders - before_orders
    require(sum(added_orders.values()) == 1 and not (before_orders - after_orders), "checkout changed an existing order or created an extra order")
    require(next(iter(added_orders))[0] == order[0], "the only added order is not the requested checkout order")

    before_cart = cart_rows(initial)
    expected_cart = Counter({row: count for row, count in before_cart.items() if row[0] != email})
    require(cart_rows(after) == expected_cart, "checkout changed a cart other than the requested user's or left checked-out items")

    expected_items = Counter(rows(
        initial,
        "SELECT p.sku,p.name,x.quantity,p.price,COALESCE(pp.name,'') "
        "FROM cart_items x JOIN users u ON u.id=x.user_id "
        "JOIN products p ON p.id=x.product_id "
        "LEFT JOIN protection_plans pp ON pp.id=x.protection_plan_id WHERE u.email=?",
        (email,),
    ))
    actual_items = Counter(rows(
        after,
        "SELECT p.sku,oi.item_name,oi.quantity,oi.unit_price,COALESCE(oi.protection_plan_name,'') "
        "FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?",
        (order[0],),
    ))
    require(actual_items == expected_items, "new order items do not exactly match the initial cart")
    before_order_items = table_rows(initial, "order_items")
    after_order_items = table_rows(after, "order_items")
    require(not (before_order_items - after_order_items), "checkout removed or rewrote an existing order item")
    require(sum((after_order_items - before_order_items).values()) == sum(expected_items.values()), "checkout created extra order items")

    subtotal, total, payment_brand = rows(
        after, "SELECT subtotal,total,payment_brand FROM orders WHERE id=?", (order[0],)
    )[0]
    payments = rows(
        after,
        "SELECT amount,card_label,auth_status,approval_code FROM payment_mocks WHERE order_id=?",
        (order[0],),
    )
    require(
        len(payments) == 1
        and payments[0][0] == total
        and payments[0][1] == payment_brand
        and payments[0][2] == "Approved"
        and re.fullmatch(r"BBYOK\d{4}", str(payments[0][3] or "")),
        "checkout payment record is missing or inconsistent",
    )
    before_payments = table_rows(initial, "payment_mocks")
    after_payments = table_rows(after, "payment_mocks")
    require(not (before_payments - after_payments) and sum((after_payments - before_payments).values()) == 1, "checkout changed or created extra payment records")

    reward_sql = (
        "SELECT u.email,r.points_balance,r.tier,r.available_certificates "
        "FROM reward_accounts r JOIN users u ON u.id=r.user_id"
    )
    before_rewards = Counter(rows(initial, reward_sql))
    expected_rewards = before_rewards.copy()
    matching = [row for row in before_rewards if row[0] == email]
    require(len(matching) == 1, "checkout user does not have exactly one reward account")
    old_reward = matching[0]
    expected_rewards.subtract({old_reward: 1})
    expected_rewards += Counter({(email, old_reward[1] + int(subtotal), old_reward[2], old_reward[3]): 1})
    require(Counter(rows(after, reward_sql)) == expected_rewards, "reward balance changes do not exactly match the checkout subtotal")

    activity_sql = (
        "SELECT u.email,a.points_delta,a.title,a.note FROM reward_activities a "
        "JOIN users u ON u.id=a.user_id"
    )
    before_activities = Counter(rows(initial, activity_sql))
    after_activities = Counter(rows(after, activity_sql))
    expected_activity = (
        email,
        int(subtotal),
        f"Points from order {order[1]}",
        "Synthetic demo checkout reward credit.",
    )
    require(after_activities - before_activities == Counter({expected_activity: 1}), "checkout reward activity is missing or includes extra activity")
    require(not (before_activities - after_activities), "checkout removed existing reward activity")


def task_7(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/checkout/shipping", "/checkout/payment", "/checkout/review", "/checkout/confirmation"]), "delivery checkout path was not recorded in order")
    order = _new_order(initial, after, "alice.j@test.com")
    require(order[2:9] == ("delivery", "Alice Jordan", "Seattle", "WA", "98101", "Demo Visa", "4242"), "new order does not match the requested delivery and payment fields")
    require(order[11] == "standard-shipping", "new order does not use standard delivery")
    require(rows(after, "SELECT COUNT(*) FROM cart_items x JOIN users u ON u.id=x.user_id WHERE u.email=?", ("alice.j@test.com",))[0][0] == 0, "Alice's cart was not emptied by checkout")
    require(str(order[1]).casefold() in final_answer(trajectory).casefold(), "final answer lacks the confirmation order number")
    require_checkout_effects(initial, after, "alice.j@test.com", order)


def task_8(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/login", "/checkout/pickup", "/checkout/payment", "/checkout/review", "/checkout/confirmation"]), "pickup checkout path was not recorded in order")
    order = _new_order(initial, after, "bob.c@test.com")
    require(order[2] == "pickup" and order[7:9] == ("Demo Mastercard", "5555"), "new order does not match the requested pickup payment")
    require(order[9] and order[10] == "austin-domain", "new order lacks the requested Austin store and pickup slot")
    require(rows(after, "SELECT COUNT(*) FROM cart_items x JOIN users u ON u.id=x.user_id WHERE u.email=?", ("bob.c@test.com",))[0][0] == 0, "Bob's cart was not emptied by checkout")
    require(str(order[1]).casefold() in final_answer(trajectory).casefold(), "final answer lacks the confirmation order number")
    require_checkout_effects(initial, after, "bob.c@test.com", order)


def task_9(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/order-lookup", "/order/BBY-240001"]), "required order-lookup path was not recorded")
    require(has_tokens(final_answer(trajectory), "pickup", "delivered"), "answer lacks the frozen fulfillment method and status")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_10(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_search_terms(trajectory, "/support", ["pickup"]), "required support search was not recorded")
    require(visited(trajectory, "/support/pickup-id-requirements"), "matching support article was not opened")
    answer = normalize(final_answer(trajectory))
    require("order number" in answer and ("photo id" in answer or "photo identification" in answer), "answer lacks both items stated by the article")
    require_unchanged_tables(initial, after, {"search_logs"})


def task_11(trajectory: dict[str, object], initial: str, after: str) -> None:
    require(visited_in_order(trajectory, ["/deals", "/product/6672899"]), "required Deals-to-product path was not recorded")
    answer = normalize(final_answer(trajectory))
    require("hp" in answer and "omnibook" in answer and ("45%" in answer or "45 percent" in answer), "answer lacks the frozen product and savings percentage")
    require_unchanged_tables(initial, after, {"search_logs"})


TASKS = {
    0: task_0, 1: task_1, 2: task_2, 3: task_3, 4: task_4, 5: task_5,
    6: task_6, 7: task_7, 8: task_8, 9: task_9, 10: task_10, 11: task_11,
}
SNAPSHOT_REQUIRED = set(TASKS)


def main(task_number: int) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db")
    parser.add_argument("--after_db")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--no_llm", action="store_true")
    args = parser.parse_args()
    task_id = f"BestBuy--{task_number}"
    try:
        trajectory = load_run(args.run_dir)
        require(screenshots_valid(trajectory), "trajectory has no complete PNG screenshot evidence")
        require(bool(final_answer(trajectory)), "final answer is empty")
        initial = after = ""
        if task_number in SNAPSHOT_REQUIRED:
            initial = database(args.initial_db, args.container, "instance_seed")
            after = database(args.after_db, args.container, "instance")
        TASKS[task_number](trajectory, initial, after)
    except TaskFailure as error:
        print(json.dumps({"task_id": task_id, "pass": False, "reason": str(error)}, indent=2))
        raise SystemExit(1)
    except (InfraError, OSError, sqlite3.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"task_id": task_id, "pass": False, "infra_error": str(error)}, indent=2))
        raise SystemExit(2)
    print(json.dumps({"task_id": task_id, "pass": True, "reason": "all deterministic checks passed"}, indent=2))
