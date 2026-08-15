#!/usr/bin/env python3
from verify_lib import (Judge, contains_all, db_query, final_answer, load_run,
                        parse_args, resolve_db, visited_path)

QUERY = """
SELECT username,email,full_name,location
FROM users
WHERE username='qa_explorer' OR email='qa_explorer@example.com'
"""
EXPECTED = ("qa_explorer", "qa_explorer@example.com", "QA Explorer", "Berlin, Germany")

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY)
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY)
    judge = Judge("Phys.org--13")
    judge.check("nav_register", visited_path(trajectory, "/register"), "visited registration")
    judge.check("nav_account", visited_path(trajectory, "/account"), "visited Account Settings")
    judge.check("db_user_absent_initially", initial == [], f"initial_rows={initial}")
    judge.check("db_registered_profile_exact", after == [EXPECTED], f"after_rows={after}")
    judge.check("answer_username", contains_all(answer, ["qa_explorer"]), repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
