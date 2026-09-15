#!/usr/bin/env python3
"""Verifier for B&H Photo--19: Alice removes the dearer of her two cart lines.

The target is derived from the seed at verify time rather than named here, so a
catalogue change moves the answer instead of breaking the task.
"""
from verify_lib import (names_product, Judge, cart_for, changed_tables_excluding, check_common,
                        final_answer, has_number, load_run, login_submitted_as,
                        normalize_text, only_allowed_tables_changed, parse_args,
                        resolve_db, row_dicts, visited_path)

TASK_ID = 'B&H Photo--19'
EMAIL = 'alice.j@test.com'
ALLOWED = ['cart_items', 'search_logs']


def priced_cart(db_path):
    return row_dicts(db_path, """
        SELECT p.slug, p.name, p.price, c.quantity
        FROM cart_items c JOIN products p ON p.id = c.product_id
        JOIN users u ON u.id = c.user_id
        WHERE u.email = ? ORDER BY p.price DESC
    """, (EMAIL,))


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

    before = priced_cart(initial)
    judge.check('ground_truth_two_cart_lines', len(before) == 2, f'cart={[r["name"][:30] for r in before]}')
    if len(before) != 2:
        judge.emit()
    dearer, cheaper = before[0], before[1]
    judge.check('ground_truth_prices_differ', dearer['price'] > cheaper['price'],
                f"{dearer['price']} vs {cheaper['price']}")

    now = {row['slug']: row for row in priced_cart(after)}
    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check('opened_the_cart', visited_path(trajectory, '/cart'), '/cart')
    judge.check('dearer_line_removed', dearer['slug'] not in now,
                f"target={dearer['name'][:40]!r} after={sorted(now)}")
    judge.check('cheaper_line_survived', cheaper['slug'] in now,
                f"expected={cheaper['name'][:40]!r} after={sorted(now)}")
    judge.check('cart_was_not_emptied', bool(now), f'after={sorted(now)}')
    judge.check('answer_names_the_remaining_item',
                names_product(answer, cheaper['name']),
                f"expected={cheaper['name']!r} answer={answer!r}")

    # the cart page shows Subtotal, Shipping, Tax and Total; the task asks for
    # the Total, so grade that and not the merchandise subtotal, which is what
    # a reader of the page would never call the total
    subtotal = round(cheaper['price'] * cheaper['quantity'], 2)
    shipping = 0 if subtotal >= 99 else 14.95
    expected_total = round(subtotal + shipping + round(subtotal * 0.08875, 2), 2)
    judge.check('answer_gives_the_new_cart_total', has_number(answer, expected_total),
                f'expected={expected_total} (subtotal {subtotal}) answer={answer!r}')
    judge.check('answer_is_not_the_subtotal_instead',
                not (has_number(answer, subtotal) and not has_number(answer, expected_total)),
                f'subtotal={subtotal} total={expected_total} answer={answer!r}')
    old_subtotal = round(dearer['price'] * dearer['quantity'] + subtotal, 2)
    judge.check('answer_is_not_the_pre_removal_figure',
                not has_number(answer, old_subtotal) or has_number(answer, expected_total),
                f'pre_removal={old_subtotal} answer={answer!r}')

    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
