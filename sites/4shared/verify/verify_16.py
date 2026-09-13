#!/usr/bin/env python3
"""Deterministic verifier for 4shared--16 (stateful: premium checkout; task reworded
by the reviewer to name the 100 GB plan).

Log in as bob; upgrade to the annual Premium 100 GB plan with cardholder Bob Chen and
the demo card; confirm the plan name and storage allowance shown on My 4shared.

Checks: identity | signed in as bob | opened /premium, /premium/checkout and then
/account | DB: plan_orders gained exactly one row (bob, "Premium 100 GB", annual,
77.88, last4 4242); bob's users row changed ONLY in plan ("Premium") and
storage_limit_mb (102400); other users and every other table row-identical |
answer names Premium and 100 GB.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (ALL_TABLES, Judge, added_rows, affirmative_search, check_paths_in_order,  # noqa: E402
                        check_signed_in_as, check_tables_unchanged, check_trajectory_identity,
                        check_visited_path, contains_all, fail_closed, final_answer, load_run,
                        normalize_text, parse_args, resolve_snapshots, row_by_id, row_changed_only_in,
                        rows_unchanged_except, table_delta)

TASK_ID = "4shared--16"
EMAIL, USER_ID = "bob.c@test.com", 2
PLAN_NAME, PERIOD, AMOUNT, LAST4 = "Premium 100 GB", "annual", 77.88, "4242"
ACCOUNT_PLAN, STORAGE_MB = "Premium", 102400


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, EMAIL)
    check_visited_path(j, t, "visited_premium_checkout", "/premium/checkout")
    check_visited_path(j, t, "visited_account_after_upgrade", "/account")
    check_paths_in_order(j, t, "checkout_before_account_confirmation", ["/premium/checkout", "/account"])
    delta = table_delta(initial_db, after_db, "plan_orders")
    added = added_rows(initial_db, after_db, "plan_orders")
    j.check("plan_orders_exact_delta", len(added) == 1 and not delta["removed"] and not delta["changed"],
            f"added={len(added)} removed={len(delta['removed'])} changed={len(delta['changed'])}")
    r = added[0] if added else {}
    j.check("order_is_bob_premium_100gb_annual",
            bool(r) and int(r["user_id"]) == USER_ID and r["plan_name"] == PLAN_NAME and r["billing_period"] == PERIOD
            and abs(float(r["amount"]) - AMOUNT) < 0.005 and str(r["card_last4"]) == LAST4,
            f"order={ {k: r.get(k) for k in ('user_id', 'plan_name', 'billing_period', 'amount', 'card_last4')} if r else None!r}")
    ok, diff = row_changed_only_in(initial_db, after_db, "users", USER_ID, ("plan", "storage_limit_mb"))
    after = row_by_id(after_db, "users", USER_ID) or {}
    j.check("bob_plan_and_storage_updated", ok and after.get("plan") == ACCOUNT_PLAN and int(after.get("storage_limit_mb") or 0) == STORAGE_MB,
            f"plan={after.get('plan')!r} storage_limit_mb={after.get('storage_limit_mb')} diff={diff!r}")
    j.check("other_users_unchanged", rows_unchanged_except(initial_db, after_db, "users", [USER_ID]), "users rows other than bob identical")
    check_tables_unchanged(j, initial_db, after_db, [x for x in ALL_TABLES if x not in {"plan_orders", "users"}])
    fa = final_answer(t)
    j.check("answer_names_premium_plan", contains_all(fa, ["premium"]), f"answer={fa[:200]!r}")
    j.check("answer_has_100gb_allowance", affirmative_search(r"(?<![\d.])100(?:\.0)?\s*(?:gb|gib|gigabytes?)\b", normalize_text(fa)), f"answer={fa[:200]!r}")


def main():
    a = parse_args()
    try:
        t = load_run(a.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(a, TASK_ID)
    j = Judge(TASK_ID, a.no_llm)
    try:
        run_checks(j, t, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
