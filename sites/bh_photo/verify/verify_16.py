#!/usr/bin/env python3
"""Verifier for B&H Photo--16: David completes checkout and reports the order number."""
from verify_lib import (Judge, cart_for, changed_tables_excluding, check_common, trajectory_urls,
                        final_answer, load_run, login_submitted_as, normalize_text,
                        only_allowed_tables_changed, orders_for, parse_args, resolve_db,
                        submitted_from_path, visited_path)

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
    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
