#!/usr/bin/env python3
import re

from verify_lib import (Judge, contains_all, db_query, final_answer, load_run,
                        parse_args, resolve_db, visited_path)

QUERY = """
SELECT username,email,full_name,location,password_hash
FROM users
WHERE username='qa_explorer' OR email='qa_explorer@example.com'
"""
EXPECTED = ("qa_explorer", "qa_explorer@example.com", "QA Explorer", "Berlin, Germany")
BCRYPT_HASH = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY)
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY)
    after_profiles = [] if after is None else [row[:4] for row in after]
    valid_password_hash = (
        after is not None
        and len(after) == 1
        and BCRYPT_HASH.fullmatch(str(after[0][4] or "")) is not None
    )
    judge = Judge("Phys.org--13")
    judge.check("nav_register", visited_path(trajectory, "/register"), "visited registration")
    judge.check("nav_account", visited_path(trajectory, "/account"), "visited Account Settings")
    judge.check("db_user_absent_initially", initial == [], f"initial_rows={initial}")
    judge.check("db_registered_profile_exact", after_profiles == [EXPECTED],
                f"after_profiles={after_profiles}")
    judge.check("db_password_hash_present", valid_password_hash,
                "registered account has a valid bcrypt password hash")
    judge.check("answer_username", contains_all(answer, ["qa_explorer"]), repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
