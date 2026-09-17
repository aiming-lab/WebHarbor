#!/usr/bin/env python3
"""Verifier for B&H Photo--15: Carol reserves a named item for store pickup."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    exact_addition,
    load_run,
    login_submitted_as,
    only_allowed_tables_changed,
    parse_args,
    reservations_for,
    resolve_db,
    row_dicts,
    user_id_for,
    visited_path,
)

TASK_ID = 'B&H Photo--15'
EMAIL = 'carol.d@test.com'
SLUG = 'vox-amplug-3-ac30-in-line-headphone-amplifier'
ALLOWED = ['store_reservations', 'search_logs']


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

    product = row_dicts(initial, 'SELECT name, pickup_available FROM products WHERE slug = ?', (SLUG,))
    judge.check('ground_truth_product_is_pickup_eligible',
                bool(product) and bool(product[0]['pickup_available']), f'product={product}')

    before = [row['slug'] for row in reservations_for(initial, EMAIL)]
    now = [row['slug'] for row in reservations_for(after, EMAIL)]
    judge.check('target_not_reserved_before_the_run', SLUG not in before, f'before={before}')
    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check('reached_the_pickup_flow',
                visited_path(trajectory, '/store-pickup') or visited_path(trajectory, '/product/' + SLUG),
                'pickup page or product page')
    judge.check('reservation_exists_afterwards', SLUG in now, f'after={now}')
    judge.check('exactly_one_reservation_added', len(now) == len(before) + 1,
                f'before={len(before)} after={len(now)}')
    target_id = row_dicts(initial, 'SELECT id FROM products WHERE slug=?', (SLUG,))[0]['id']
    stores = row_dicts(initial, "SELECT id FROM store_locations WHERE name='B&H SuperStore'")
    judge.check('ground_truth_pickup_store', len(stores) == 1, repr(stores))
    judge.check('active_reservation_at_requested_store', bool(stores) and exact_addition(
                initial, after, 'store_reservations', {'user_id': user_id_for(initial, EMAIL),
                'product_id': target_id, 'store_id': stores[0]['id'], 'quantity': 1, 'status': 'Reserved'}),
                'one new Reserved item at B&H SuperStore; all existing reservations preserved')

    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
