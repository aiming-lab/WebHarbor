#!/usr/bin/env python3
"""Verifier for B&H Photo--14: Bob adds a named card to his cart at quantity 2."""
from verify_lib import (Judge, cart_for, changed_tables_excluding, check_common, load_run,
                        login_submitted_as, only_allowed_tables_changed, parse_args,
                        resolve_db, row_dicts, trajectory_urls, visited_path)

TASK_ID = 'B&H Photo--14'
EMAIL = 'bob.c@test.com'
SLUG = 'sony-1920gb-cfexpress-4-0-type-a-tough-memory-card'
WANTED_QUANTITY = 2
ALLOWED = ['cart_items', 'search_logs']


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

    judge.check('ground_truth_product_exists',
                bool(row_dicts(initial, 'SELECT 1 FROM products WHERE slug = ?', (SLUG,))), SLUG)
    before = {row['slug']: row['quantity'] for row in cart_for(initial, EMAIL)}
    now = {row['slug']: row['quantity'] for row in cart_for(after, EMAIL)}
    judge.check('target_not_in_cart_before_the_run', SLUG not in before, f'before={before}')
    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    # upstream offers Add to Cart and Add to Wish List on the listing row itself,
    # so a run that never opens the product page is a legitimate path and must pass
    judge.check('reached_the_product_through_the_site',
                visited_path(trajectory, '/product/' + SLUG)
                or any(path in url for url in trajectory_urls(trajectory)
                       for path in ('/c/', '/search', '/deals', '/used', '/brand/')),
                f'slug={SLUG}')
    judge.check('card_is_in_the_cart_afterwards', SLUG in now, f'after={now}')
    judge.check('cart_quantity_is_two', now.get(SLUG) == WANTED_QUANTITY,
                f'quantity={now.get(SLUG)}')
    untouched = {slug: qty for slug, qty in before.items() if now.get(slug) != qty}
    judge.check('other_cart_lines_untouched', not untouched, f'changed={untouched}')
    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
