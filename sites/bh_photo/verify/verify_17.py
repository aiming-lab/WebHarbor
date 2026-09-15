#!/usr/bin/env python3
"""Verifier for B&H Photo--17: report the order number that is still processing."""
from verify_lib import (Judge, changed_tables_excluding, check_common, final_answer,
                        load_run, login_submitted_as, normalize_text,
                        only_allowed_tables_changed, orders_for, parse_args, resolve_db,
                        visited_path)

TASK_ID = 'B&H Photo--17'
EMAIL = 'bob.c@test.com'
ALLOWED = ['search_logs']


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

    orders = orders_for(initial, EMAIL)
    processing = [row for row in orders if normalize_text(row['status']) == 'processing']
    others = [row for row in orders if normalize_text(row['status']) != 'processing']
    judge.check('ground_truth_single_processing_order', len(processing) == 1,
                f'orders={[(o["order_number"], o["status"]) for o in orders]}')
    if len(processing) != 1:
        judge.emit()

    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check('opened_order_history', visited_path(trajectory, '/account/orders'), '/account/orders')
    judge.check('answer_gives_the_processing_order_number',
                normalize_text(processing[0]['order_number']) in normalize_text(answer),
                f"expected={processing[0]['order_number']!r} answer={answer!r}")
    wrong = [row['order_number'] for row in others
             if normalize_text(row['order_number']) in normalize_text(answer)]
    judge.check('answer_does_not_give_a_delivered_order', not wrong, f'also named={wrong}')
    judge.check('no_state_written', only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
