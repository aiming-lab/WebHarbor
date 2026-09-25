#!/usr/bin/env python3
"""Verifier for B&H Photo--16: David completes checkout and reports the order number."""
from collections import Counter

from verify_lib import (
    Judge,
    affirmative_contains,
    cart_for,
    cart_totals,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    login_submitted_as,
    new_rows,
    normalize_text,
    only_allowed_tables_changed,
    orders_for,
    parse_args,
    resolve_db,
    row_dicts,
    rows_unchanged_except,
    submitted_from_path,
    trajectory_urls,
    user_id_for,
    visited_path,
    visited_query,
)

TASK_ID = 'B&H Photo--16'
EMAIL = 'david.k@test.com'
ALLOWED = ['orders', 'order_items', 'cart_items', 'search_logs']


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    if not (initial and after):
        judge.emit()

    judge.check('ground_truth_cart_not_empty', bool(cart_for(initial, EMAIL)),
                f'cart={cart_for(initial, EMAIL)}')
    before = {row['order_number'] for row in orders_for(initial, EMAIL)}
    now = {row['order_number'] for row in orders_for(after, EMAIL)}
    created = now - before

    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check('submitted_the_checkout_form', submitted_from_path(trajectory, '/checkout'),
                'a POST transition away from /checkout')
    judge.check('reached_an_order_confirmation',
                any('/order/' in url for url in trajectory_urls(trajectory))
                or visited_path(trajectory, '/account/orders'),
                f'urls={trajectory_urls(trajectory)[-3:]}')
    judge.check('exactly_one_order_created', len(created) == 1, f'created={sorted(created)}')
    if created:
        number = next(iter(created))
        judge.check('answer_reports_that_order_number',
                    normalize_text(number) in normalize_text(answer),
                    f'expected={number!r} answer={answer!r}')
    uid = user_id_for(initial, EMAIL)
    initial_cart = row_dicts(initial, """SELECT c.*, p.name AS product_name, p.price, p.image_path
        FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=? ORDER BY c.id""", (uid,))
    additions = new_rows(initial, after, 'orders')
    judge.check('single_new_order_and_old_orders_preserved', len(additions) == 1
                and rows_unchanged_except(initial, after, 'orders', [row['id'] for row in additions]),
                'exactly one order globally; existing orders unchanged')
    if len(additions) == 1:
        order = additions[0]
        totals = cart_totals(initial_cart)
        judge.check('new_order_owner_status_and_totals', order['user_id'] == uid
                    and order['status'] == 'Confirmed'
                    and all(abs(order[field] - value) < 0.005 for field, value in totals.items()), repr(order))
        items = row_dicts(after, 'SELECT * FROM order_items WHERE order_id=? ORDER BY id', (order['id'],))
        expected = Counter((r['product_id'], r['product_name'], r['quantity'], r['price'],
                            r['variant_label'] or r['bundle_label']) for r in initial_cart)
        observed = Counter((r['product_id'], r['product_name'], r['quantity'], r['price'], r['variant_label']) for r in items)
        judge.check('order_items_match_initial_cart', bool(items) and expected == observed, f'{observed} vs {expected}')
        judge.check('other_order_items_unchanged', rows_unchanged_except(initial, after, 'order_items', [r['id'] for r in items]),
                    'only the new order may add items')
        judge.check('reported_new_order_on_confirmation', visited_path(trajectory, '/order/' + order['order_number'])
                    and affirmative_contains(answer, order['order_number']), order['order_number'])
    judge.check('original_cart_cleared_and_other_carts_preserved',
                not row_dicts(after, 'SELECT id FROM cart_items WHERE user_id=?', (uid,))
                and rows_unchanged_except(initial, after, 'cart_items', [r['id'] for r in initial_cart]),
                'the original cart must be empty without changing other users')
    judge.check('completed_shipping_payment_and_review', visited_path(trajectory, '/checkout')
                and visited_query(trajectory, '/checkout', {'step': 'payment'})
                and visited_query(trajectory, '/checkout', {'step': 'review'}), 'all checkout stages visited')

    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
