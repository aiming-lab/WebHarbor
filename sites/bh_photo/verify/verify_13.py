#!/usr/bin/env python3
"""Verifier for B&H Photo--13: Alice saves a named microphone to her wishlist."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    exact_addition,
    load_run,
    login_submitted_as,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    trajectory_urls,
    user_id_for,
    visited_path,
    wishlist_for,
)

TASK_ID = 'B&H Photo--13'
EMAIL = 'alice.j@test.com'
SLUG = 'movo-photo-pm10-omnidirectional-lavalier-microphone-for-smartphones-trrs-black'
ALLOWED = ['wishlist_items', 'search_logs']


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    if not (initial and after):
        judge.emit()

    target = row_dicts(initial, 'SELECT name FROM products WHERE slug = ?', (SLUG,))
    judge.check('ground_truth_product_exists', bool(target), f'slug={SLUG}')

    before = {row['slug'] for row in wishlist_for(initial, EMAIL)}
    now = {row['slug'] for row in wishlist_for(after, EMAIL)}
    judge.check('target_not_saved_before_the_run', SLUG not in before, f'before={sorted(before)}')
    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    # upstream offers Add to Cart and Add to Wish List on the listing row itself,
    # so a run that never opens the product page is a legitimate path and must pass
    judge.check('reached_the_product_through_the_site',
                visited_path(trajectory, '/product/' + SLUG)
                or any(path in url for url in trajectory_urls(trajectory)
                       for path in ('/c/', '/search', '/deals', '/used', '/brand/')),
                f'slug={SLUG}')
    judge.check('product_is_in_the_wishlist_afterwards', SLUG in now, f'after={sorted(now)}')
    judge.check('no_other_wishlist_change', now - before == {SLUG} and not before - now,
                f'added={sorted(now - before)} removed={sorted(before - now)}')
    target_id = row_dicts(initial, 'SELECT id FROM products WHERE slug=?', (SLUG,))[0]['id']
    judge.check('only_requested_wishlist_entry_added', exact_addition(initial, after, 'wishlist_items',
                {'user_id': user_id_for(initial, EMAIL), 'product_id': target_id}),
                'exactly one new target entry; every existing entry, including other users, unchanged')

    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
