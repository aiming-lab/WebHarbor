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
    visited_path,
)

COMMENT = "Reviewed for our weekly journal club"
QUERY = """
SELECT c.id, a.title, a.slug
FROM comments c
JOIN users u ON u.id=c.user_id
JOIN articles a ON a.id=c.article_id
JOIN categories cat ON cat.id=a.category_id
WHERE u.username='carol_d' AND c.parent_id IS NULL
  AND c.text=? AND cat.slug='biology'
"""
ALL_QUERY = """
SELECT id,text,user_id,article_id,parent_id,score,created_at
FROM comments
ORDER BY id
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    initial = db_query(initial_db, QUERY, (COMMENT,))
    after = db_query(after_db, QUERY, (COMMENT,))
    initial_all = db_query(initial_db, ALL_QUERY)
    after_all = db_query(after_db, ALL_QUERY)
    initial_ids = set() if initial is None else {row[0] for row in initial}
    new_rows = [] if after is None else [row for row in after if row[0] not in initial_ids]
    added_full_rows = [] if after_all is None else [
        row for row in after_all if any(row[0] == added[0] for added in new_rows)
    ]
    exact_change = (
        initial == [] and len(new_rows) == 1 and len(added_full_rows) == 1
        and initial_all is not None and after_all == initial_all + added_full_rows
    )
    judge = Judge("Phys.org--6")
    check_common(judge, trajectory, 6)
    judge.check("login_as_carol",
                filled_field(trajectory, "email", "carol.d@test.com", "/login")
                and entered_text(trajectory, "TestPass123!", "/login")
                and submitted_from_path(trajectory, "/login"),
                "submitted Carol's credentials")
    judge.check("db_new_top_level_comment", exact_change, f"new_matching_comments={new_rows}")
    visited_target = bool(new_rows) and any(
        visited_path(trajectory, f"/article/{slug}") for _, _, slug in new_rows
    )
    ordered_target = bool(new_rows) and any(
        visited_in_order(trajectory, [
            ("/login", {}), ("/category/biology", {}), (f"/article/{slug}", {})
        ]) for _, _, slug in new_rows
    )
    judge.check("ordered_biology_to_commented_article", ordered_target,
                f"new_matching_comments={new_rows}")
    judge.check("clicked_biology_article", bool(new_rows) and any(
        clicked_path_transition(trajectory, "/category/biology", f"/article/{slug}")
        for _, _, slug in new_rows
    ), "clicked the commented article from Biology")
    comment_submitted = bool(new_rows) and any(
        entered_text(trajectory, COMMENT, f"/article/{slug}")
        and submitted_from_path(trajectory, f"/article/{slug}", f"/article/{slug}")
        for _, _, slug in new_rows
    )
    judge.check("comment_form_submitted", comment_submitted, "exact comment input and submission")
    judge.check("nav_commented_article", visited_target, f"new_matching_comments={new_rows}")
    answer_matches = bool(new_rows) and any(contains_all(answer, [title]) for _, title, _ in new_rows)
    judge.check("answer_article_title", answer_matches, repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
