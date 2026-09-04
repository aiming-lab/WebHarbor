#!/usr/bin/env python3
import re

import bcrypt
from verify_lib import (
    Judge,
    check_common,
    contains_all,
    db_query,
    entered_text,
    final_answer,
    input_values_at_path,
    load_run,
    parse_args,
    resolve_db,
    submitted_from_path,
    visited_in_order,
)

BCRYPT_HASH = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")
ALL_QUERY = """
SELECT id,username,email,full_name,location,bio,interests,password_hash,created_at
FROM users
ORDER BY id
"""


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    initial_all = db_query(initial_db, ALL_QUERY)
    after_all = db_query(after_db, ALL_QUERY)
    initial_ids = set() if initial_all is None else {row[0] for row in initial_all}
    new_rows = [] if after_all is None else [
        row for row in after_all if row[0] not in initial_ids
    ]
    exact_change = (
        initial_all is not None
        and len(new_rows) == 1
        and after_all == initial_all + new_rows
    )
    new_row = new_rows[0] if len(new_rows) == 1 else None
    valid_profile = bool(
        new_row
        and str(new_row[1]).strip()
        and "@" in str(new_row[2])
        and str(new_row[3]).strip()
        and new_row[4] == "Berlin, Germany"
    )
    valid_password_hash = bool(
        new_row and BCRYPT_HASH.fullmatch(str(new_row[7] or ""))
    )
    entered_profile = bool(new_row) and all(
        entered_text(trajectory, str(value), "/register")
        for value in new_row[1:4]
    )
    excluded_values = set() if new_row is None else {str(value) for value in new_row[1:4]}
    password_candidates = [
        value for value in input_values_at_path(trajectory, "/register")
        if value not in excluded_values and len(value) >= 6
    ]
    password_matches = valid_password_hash and any(
        bcrypt.checkpw(value.encode(), str(new_row[7]).encode())
        for value in password_candidates
    )

    judge = Judge("Phys.org--13")
    check_common(judge, trajectory, 13)
    judge.check("ordered_registration_flow", visited_in_order(trajectory, [
        ("/register", {}), ("/account", {})
    ]), "visited registration before Account Settings")
    judge.check("registration_fields_entered", entered_profile,
                "entered the new username, email, and full name")
    judge.check("registration_submitted", submitted_from_path(trajectory, "/register"),
                "submitted registration form")
    judge.check("location_entered", entered_text(trajectory, "Berlin, Germany", "/account"),
                "entered requested location")
    judge.check("profile_submitted", submitted_from_path(trajectory, "/account", "/account"),
                "submitted Account Settings")
    judge.check("db_one_new_user_exact", exact_change and valid_profile,
                f"new_users={[(row[1], row[2], row[3], row[4]) for row in new_rows]}")
    judge.check("db_password_matches_input", bool(password_matches),
                "new account hash matches the entered non-empty password")
    judge.check("answer_new_username",
                bool(new_row) and contains_all(answer, [str(new_row[1])]),
                repr(answer))
    judge.emit()


if __name__ == "__main__":
    main()
