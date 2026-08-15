#!/usr/bin/env python3
from verify_lib import (Judge, contains_all, db_query, final_answer, load_run,
                        parse_args, resolve_db, visited_path)

QUERY = """
SELECT s.query,s.created_at
FROM search_history s
JOIN users u ON u.id=s.user_id
WHERE u.username='alice_j'
ORDER BY s.created_at DESC,s.id DESC
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY)
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY)
    judge = Judge("Phys.org--17")
    judge.check("nav_login", visited_path(trajectory, "/login"), "visited login")
    judge.check("nav_account", visited_path(trajectory, "/account"), "visited Account Settings")
    judge.check("db_search_history_unchanged", initial is not None and after == initial,
                f"initial_history={initial} after_history={after}")
    judge.check("answer_recent_query", contains_all(answer, ["exoplanet atmosphere"]), repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
