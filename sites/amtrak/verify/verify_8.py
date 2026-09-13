#!/usr/bin/env python3
"""Verify Amtrak--8: Alice changes preferred station to SEA, then reads it back on the rewards dashboard (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    LOG_TABLES,
    MUTABLE_TABLES,
    check_paths_in_order,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    contains_word,
    fail_closed,
    final_answer,
    load_run,
    parse_args,
    resolve_snapshots,
    reward_row,
    row_diff_columns,
    rows_unchanged_except,
    user_row,
)


TASK_ID = "Amtrak--8"
EMAIL = "alice.j@test.com"
NEW_STATION = "SEA"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_paths_in_order(judge, trajectory, "edit_then_rewards_in_order",
                         [("/login", {}), ("/account/edit", {}), ("/account/rewards", {})])
    before_user, after_user = user_row(initial_db, EMAIL), user_row(after_db, EMAIL)
    before_reward, after_reward = reward_row(initial_db, EMAIL), reward_row(after_db, EMAIL)
    judge.check("initial_preferred_station_differs", bool(before_user) and before_user["preferred_station_code"] != NEW_STATION,
                f"initial={before_user and before_user['preferred_station_code']!r}")
    judge.check("user_preferred_station_updated", bool(after_user) and after_user["preferred_station_code"] == NEW_STATION,
                f"after={after_user and after_user['preferred_station_code']!r}")
    judge.check("reward_preferred_station_updated", bool(after_reward) and after_reward["preferred_station_code"] == NEW_STATION,
                f"after={after_reward and after_reward['preferred_station_code']!r}")
    judge.check("user_row_changed_only_preferred_station",
                bool(after_user) and row_diff_columns(initial_db, after_db, "users", int(after_user["id"])) == ["preferred_station_code"],
                f"changed_columns={after_user and row_diff_columns(initial_db, after_db, 'users', int(after_user['id']))!r}")
    judge.check("reward_row_changed_only_preferred_station",
                bool(after_reward) and row_diff_columns(initial_db, after_db, "reward_accounts", int(after_reward["id"])) == ["preferred_station_code"],
                f"changed_columns={after_reward and row_diff_columns(initial_db, after_db, 'reward_accounts', int(after_reward['id']))!r}")
    judge.check("other_users_unchanged", bool(after_user) and rows_unchanged_except(initial_db, after_db, "users", [int(after_user["id"])]), "table=users")
    judge.check("other_reward_accounts_unchanged", bool(after_reward) and rows_unchanged_except(initial_db, after_db, "reward_accounts", [int(after_reward["id"])]), "table=reward_accounts")
    check_tables_unchanged(judge, initial_db, after_db,
                           [t for t in MUTABLE_TABLES if t not in ("users", "reward_accounts")] + list(LOG_TABLES))
    judge.check("answer_has_station_code", contains_word(answer, NEW_STATION), f"expected={NEW_STATION!r}, answer={answer!r}")


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
