#!/usr/bin/env python3
from verify_lib import (Judge, contains_all, db_query, final_answer, load_run,
                        parse_args, resolve_db, visited_category, visited_path)

NOTE = "Compare with our process"
QUERY = """
SELECT a.id, a.title, a.slug
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
JOIN categories cat ON cat.id=a.category_id
WHERE u.username='david_k' AND s.note=? AND cat.slug='nanotechnology'
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial = db_query(resolve_db(args.initial_db, args.container, "instance_seed"), QUERY, (NOTE,))
    after = db_query(resolve_db(args.after_db, args.container, "instance"), QUERY, (NOTE,))
    initial_ids = set() if initial is None else {row[0] for row in initial}
    new_rows = [] if after is None else [row for row in after if row[0] not in initial_ids]
    judge = Judge("Phys.org--7")
    judge.check("nav_login", visited_path(trajectory, "/login"), "visited login")
    judge.check("nav_nanotechnology", visited_category(trajectory, "nanotechnology"),
                "visited Nanotechnology category")
    judge.check("nav_saved", visited_path(trajectory, "/saved"), "visited saved list")
    judge.check("db_new_saved_article", bool(new_rows), f"new_matching_saves={new_rows}")
    visited_target = bool(new_rows) and any(
        visited_path(trajectory, f"/article/{slug}") for _, _, slug in new_rows
    )
    judge.check("nav_saved_article", visited_target, f"new_matching_saves={new_rows}")
    answer_matches = bool(new_rows) and any(contains_all(answer, [title]) for _, title, _ in new_rows)
    judge.check("answer_article_title", answer_matches, repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
