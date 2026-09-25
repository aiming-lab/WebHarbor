#!/usr/bin/env python3
"""Verifier for B&H Photo--9: report the review headline and its star rating."""
from verify_lib import (
    Judge,
    affirmative_contains,
    changed_tables_excluding,
    check_common,
    final_answer,
    has_number,
    load_run,
    number_labelled,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    visited_path,
)

TASK_ID = 'B&H Photo--9'
SLUG = 'canon-eos-r1-mirrorless-camera-with-essentials-kit'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    reviews = row_dicts(initial, """
        SELECT r.headline, r.rating FROM product_reviews r JOIN products p ON p.id = r.product_id
        WHERE p.slug = ? ORDER BY r.created_at DESC, r.id DESC
    """, (SLUG,)) if initial else []
    judge.check('ground_truth_readable', bool(reviews), f'reviews={len(reviews)}')
    if not reviews:
        judge.emit()
    review = reviews[0]

    judge.check('opened_reviews_page', visited_path(trajectory, f'/product/{SLUG}/reviews'),
                f'{SLUG}/reviews')
    judge.check('answer_gives_review_headline',
                affirmative_contains(answer, review['headline']),
                f"expected={review['headline']!r} answer={answer!r}")
    judge.check('answer_gives_review_rating',
                number_labelled(answer, review['rating'],
                                follows=['star', 'stars', 'out of 5', '/5'],
                                precedes=['rating of', 'rated', 'rating']),
                f"expected={review['rating']} answer={answer!r}")

    product = row_dicts(initial, 'SELECT rating FROM products WHERE slug = ?', (SLUG,))
    if product and product[0]['rating'] != review['rating']:
        gave_average_only = (has_number(answer, product[0]['rating'])
                             and not has_number(answer, review['rating']))
        judge.check('answer_not_product_average_only', not gave_average_only,
                    f"average={product[0]['rating']} answer={answer!r}")

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
