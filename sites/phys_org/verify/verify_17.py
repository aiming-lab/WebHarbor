#!/usr/bin/env python3
from verify_lib import (
    Judge,
    check_common,
    clicked_path_transition,
    contains_all,
    db_query,
    entered_text,
    filled_field,
    final_answer,
    load_run,
    parse_args,
    resolve_db,
    submitted_from_path,
    visited_in_order,
)

QUERY = """
SELECT s.query,s.created_at
FROM search_history s
JOIN users u ON u.id=s.user_id
WHERE u.username='alice_j'
ORDER BY s.created_at DESC,s.id DESC
"""
ALL_QUERY = """
SELECT id,user_id,query,created_at
FROM search_history
ORDER BY id
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    initial = db_query(initial_db, QUERY)
    after = db_query(after_db, QUERY)
    initial_all = db_query(initial_db, ALL_QUERY)
    after_all = db_query(after_db, ALL_QUERY)
    judge = Judge("Phys.org--17")
    check_common(judge, trajectory, 17)
    judge.check("login_as_alice",
                filled_field(trajectory, "email", "alice.j@test.com", "/login")
                and entered_text(trajectory, "TestPass123!", "/login")
                and submitted_from_path(trajectory, "/login"),
                "submitted Alice's credentials")
    judge.check("ordered_login_to_account", visited_in_order(trajectory, [
        ("/login", {}), ("/account", {})
    ]), "visited Account Settings after login")
    judge.check("clicked_account", clicked_path_transition(
        trajectory, "/", "/account"
    ), "clicked Account Settings after login")
    judge.check("db_search_history_unchanged",
                initial is not None and after == initial and after_all == initial_all,
                f"initial_history={initial} after_history={after}")
    judge.check("answer_second_query", contains_all(answer, ["dark matter halo"]), repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
