#!/usr/bin/env python3
"""Verifier for B&H Photo--4: the least expensive used or open-box item.

Ground truth is read from the shipped seed at verify time, so the answer key
lives here and never in the agent-facing task file.
"""
from verify_lib import (names_product, Judge, changed_tables_excluding, check_common, contains_all,
                        final_answer, has_number, load_run, normalize_text,
                        only_allowed_tables_changed, parse_args, resolve_db, row_dicts,
                        visited_path)

TASK_ID = 'B&H Photo--4'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    rows = row_dicts(initial, """
        SELECT name, slug, condition, price FROM products
        WHERE condition != 'New' ORDER BY price ASC
    """) if initial else []
    judge.check('ground_truth_readable', len(rows) >= 2, f'used/open-box rows={len(rows)}')
    if not rows:
        judge.emit()
    cheapest, runner_up = rows[0], rows[1]
    judge.check('cheapest_is_unambiguous', cheapest['price'] < runner_up['price'],
                f"{cheapest['price']} vs {runner_up['price']}")

    judge.check('opened_used_listing', visited_path(trajectory, '/used'), 'used and open-box listing')
    judge.check('answer_names_cheapest_item',
                names_product(answer, cheapest['name']),
                f"expected={cheapest['name']!r} answer={answer!r}")
    judge.check('answer_states_condition',
                normalize_text(cheapest['condition']) in normalize_text(answer),
                f"expected={cheapest['condition']!r} answer={answer!r}")
    judge.check('answer_states_price', has_number(answer, cheapest['price']),
                f"expected={cheapest['price']} answer={answer!r}")
    judge.check('answer_is_not_a_pricier_item',
                normalize_text(runner_up['name']) not in normalize_text(answer),
                f"runner_up={runner_up['name']!r} answer={answer!r}")

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
