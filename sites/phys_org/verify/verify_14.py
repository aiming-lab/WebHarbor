#!/usr/bin/env python3
from verify_lib import (Judge, contains_all, db_query, final_answer, has_number,
                        load_run, parse_args, resolve_db, visited_path)

TARGET_SLUG = "how-a-single-star-can-reshape-an-entire-galaxy"
TOP_REMAINING = "More Star Wars-like worlds emerge as 27 planet candidates with two suns discovered"
QUERY = """
SELECT a.slug,a.title
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
WHERE u.username='alice_j'
ORDER BY s.created_at DESC, s.id DESC
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY)
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY)
    initial_rows = initial or []
    after_rows = after or []
    expected_after = [row for row in initial_rows if row[0] != TARGET_SLUG]
    judge = Judge("Phys.org--14")
    judge.check("nav_login", visited_path(trajectory, "/login"), "visited login")
    judge.check("nav_target_article", visited_path(trajectory, f"/article/{TARGET_SLUG}"),
                "opened article to remove")
    judge.check("nav_saved", visited_path(trajectory, "/saved"), "visited saved list")
    judge.check("db_target_was_saved", any(row[0] == TARGET_SLUG for row in initial_rows),
                f"initial_saved={initial_rows}")
    judge.check("db_only_target_removed", initial is not None and after == expected_after,
                f"after_saved={after_rows} expected={expected_after}")
    judge.check("db_five_remain", len(after_rows) == 5, f"remaining={len(after_rows)}")
    judge.check("db_top_remaining", bool(after_rows) and after_rows[0][1] == TOP_REMAINING,
                f"top={after_rows[0][1] if after_rows else None}")
    judge.check("answer_count_and_top", has_number(answer, 5) and contains_all(answer, [TOP_REMAINING]),
                repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
