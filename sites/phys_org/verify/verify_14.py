#!/usr/bin/env python3
import re

from verify_lib import (
    Judge,
    check_common,
    clicked_path_transition,
    contains_all,
    db_query,
    entered_text,
    filled_field,
    final_answer,
    has_labeled_number,
    load_run,
    norm,
    parse_args,
    resolve_db,
    submitted_from_path,
    visited_in_order,
)

TARGET_SLUG = "how-a-single-star-can-reshape-an-entire-galaxy"
TOP_REMAINING = "More Star Wars-like worlds emerge as 27 planet candidates with two suns discovered"
QUERY = """
SELECT s.id,a.slug,a.title,s.note,s.created_at
FROM saved_articles s
JOIN users u ON u.id=s.user_id
JOIN articles a ON a.id=s.article_id
WHERE u.username='alice_j'
ORDER BY s.created_at DESC, s.id DESC
"""
ALL_QUERY = """
SELECT s.id,u.username,a.slug,s.note,s.created_at
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
    initial = db_query(initial_db, QUERY)
    after = db_query(after_db, QUERY)
    initial_all = db_query(initial_db, ALL_QUERY)
    after_all = db_query(after_db, ALL_QUERY)
    initial_rows = initial or []
    after_rows = after or []
    expected_after = [row for row in initial_rows if row[1] != TARGET_SLUG]
    removed_ids = {row[0] for row in initial_rows if row[1] == TARGET_SLUG}
    expected_all_after = None if initial_all is None else [
        row for row in initial_all if row[0] not in removed_ids
    ]
    judge = Judge("Phys.org--14")
    check_common(judge, trajectory, 14)
    judge.check("login_as_alice",
                filled_field(trajectory, "email", "alice.j@test.com", "/login")
                and entered_text(trajectory, "TestPass123!", "/login")
                and submitted_from_path(trajectory, "/login"),
                "submitted Alice's credentials")
    judge.check("ordered_remove_flow", visited_in_order(trajectory, [
        ("/login", {}), (f"/article/{TARGET_SLUG}", {}), ("/saved", {})
    ]), "opened target and then Saved")
    judge.check("clicked_target_from_saved", clicked_path_transition(
        trajectory, "/saved", f"/article/{TARGET_SLUG}"
    ), "clicked the target from Saved")
    judge.check("remove_submitted",
                submitted_from_path(trajectory, f"/article/{TARGET_SLUG}",
                                    f"/article/{TARGET_SLUG}"),
                "submitted removal on target article")
    judge.check("db_target_was_saved", any(row[1] == TARGET_SLUG for row in initial_rows),
                f"initial_saved={initial_rows}")
    judge.check("db_only_target_removed",
                initial is not None and after == expected_after
                and after_all == expected_all_after,
                f"after_saved={after_rows} expected={expected_after}")
    judge.check("db_five_remain", len(after_rows) == 5, f"remaining={len(after_rows)}")
    judge.check("db_top_remaining", bool(after_rows) and after_rows[0][2] == TOP_REMAINING,
                f"top={after_rows[0][2] if after_rows else None}")
    normalized = norm(answer)
    top_is_bound = contains_all(answer, [TOP_REMAINING]) and re.search(
        rf"(?:top|first|most recent).{{0,80}}{re.escape(norm(TOP_REMAINING))}|"
        rf"{re.escape(norm(TOP_REMAINING))}.{{0,80}}(?:top|first|most recent)",
        normalized,
    )
    judge.check("answer_count_and_top",
                has_labeled_number(answer, 5, ("remain", "remaining", "saved"))
                and bool(top_is_bound), repr(answer))
    judge.emit()

if __name__ == "__main__":
    main()
