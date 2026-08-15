#!/usr/bin/env python3
from verify_lib import (Judge, contains_all, db_query, final_answer, load_run,
                        parse_args, resolve_db, visited_category, visited_path)

COMMENT = "Reviewed for our weekly journal club"
QUERY = """
SELECT a.title, a.slug
FROM comments c
JOIN users u ON u.id=c.user_id
JOIN articles a ON a.id=c.article_id
JOIN categories cat ON cat.id=a.category_id
WHERE u.username='carol_d' AND c.parent_id IS NULL
  AND c.text=? AND cat.slug='biology'
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY, (COMMENT,))
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY, (COMMENT,))
    new_rows = [] if initial is None or after is None else [row for row in after if row not in initial]
    judge = Judge("Phys.org--6")
    judge.check("nav_login", visited_path(trajectory, "/login"), "visited login")
    judge.check("nav_biology", visited_category(trajectory, "biology"), "visited Biology category")
    judge.check("db_new_top_level_comment", bool(new_rows), f"new_matching_comments={new_rows}")
    visited_target = bool(new_rows) and any(
        visited_path(trajectory, f"/article/{slug}") for _, slug in new_rows
    )
    judge.check("nav_commented_article", visited_target, f"new_matching_comments={new_rows}")
    answer_matches = bool(new_rows) and any(contains_all(answer, [title]) for title, _ in new_rows)
    judge.check("answer_article_title", answer_matches, repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
