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

NOTE = "Compare with our process"
TARGET_SLUG = "engineered-exosomes-reverse-sleep-deprivation-brain-damage-in-mice"
INITIAL_QUERY = """
SELECT a.id
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
WHERE u.username='david_k'
"""
AFTER_QUERY = """
SELECT s.id, a.id, a.title, a.slug
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
JOIN categories cat ON cat.id=a.category_id
WHERE u.username='david_k' AND s.note=? AND cat.slug='nanotechnology'
  AND a.slug=?
"""
ALL_QUERY = """
SELECT s.id,a.id,a.slug,s.note,s.created_at
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
ORDER BY s.id
"""

def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    answer = final_answer(trajectory)
    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    initial = db_query(initial_db, INITIAL_QUERY)
    after = db_query(after_db, AFTER_QUERY, (NOTE, TARGET_SLUG))
    initial_all = db_query(initial_db, ALL_QUERY)
    after_all = db_query(after_db, ALL_QUERY)
    initial_ids = set() if initial is None else {row[0] for row in initial}
    new_rows = [] if after is None else [row for row in after if row[1] not in initial_ids]
    added_full_rows = [] if after_all is None else [
        row for row in after_all if any(row[0] == added[0] for added in new_rows)
    ]
    exact_change = (
        len(new_rows) == 1 and len(added_full_rows) == 1
        and initial_all is not None and after_all == initial_all + added_full_rows
    )
    judge = Judge("Phys.org--7")
    check_common(judge, trajectory, 7)
    judge.check("login_as_david",
                filled_field(trajectory, "email", "david.k@test.com", "/login")
                and entered_text(trajectory, "TestPass123!", "/login")
                and submitted_from_path(trajectory, "/login"),
                "submitted David's credentials")
    judge.check("ordered_save_flow", visited_in_order(trajectory, [
        ("/login", {}), ("/category/nanotechnology", {}),
        (f"/article/{TARGET_SLUG}", {}), ("/saved", {})
    ]), "visited Nanotechnology, target article, then Saved")
    judge.check("clicked_target_from_nanotechnology", clicked_path_transition(
        trajectory, "/category/nanotechnology", f"/article/{TARGET_SLUG}"
    ), "clicked the target from Nanotechnology")
    judge.check("nav_saved", visited_path(trajectory, "/saved"), "visited saved list")
    judge.check("db_new_saved_article", exact_change, f"new_matching_saves={new_rows}")
    visited_target = bool(new_rows) and any(
        visited_path(trajectory, f"/article/{slug}") for _, _, _, slug in new_rows
    )
    judge.check("nav_saved_article", visited_target, f"new_matching_saves={new_rows}")
    judge.check("save_form_submitted",
                entered_text(trajectory, NOTE, f"/article/{TARGET_SLUG}")
                and submitted_from_path(trajectory, f"/article/{TARGET_SLUG}",
                                        f"/article/{TARGET_SLUG}"),
                "exact note input and save submission")
    answer_matches = bool(new_rows) and contains_all(answer, ["Bio & Medicine"])
    judge.check("answer_article_subsection", answer_matches, repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
