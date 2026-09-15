#!/usr/bin/env python3
"""Verifier for B&H Photo--3: two detail-only rows from the 16-inch ThinkPad T1g."""
import re

from verify_lib import (Judge, changed_tables_excluding, check_common, final_answer,
                        load_run, normalize_text, only_allowed_tables_changed, parse_args,
                        resolve_db, row_dicts, visited_path)

TASK_ID = 'B&H Photo--3'
SLUG = 'lenovo-16-thinkpad-t1g-gen-8-multi-touch-laptop'


def spec(db_path, label):
    rows = row_dicts(db_path, """
        SELECT s.value FROM product_specs s JOIN product_spec_groups g ON g.id = s.group_id
        JOIN products p ON p.id = g.product_id WHERE p.slug = ? AND s.name = ?
    """, (SLUG, label))
    return rows[0]['value'] if rows else ''


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    if not initial:
        judge.emit()

    resolution = spec(initial, 'Native Resolution')
    weight = spec(initial, 'Weight')
    judge.check('ground_truth_readable', bool(resolution and weight),
                f'resolution={resolution!r} weight={weight!r}')

    judge.check('opened_the_product_page', visited_path(trajectory, '/product/' + SLUG), SLUG)
    normalized = normalize_text(answer)

    numbers = re.findall(r'\d+', resolution)
    judge.check('answer_gives_native_resolution',
                bool(numbers) and all(number in normalized for number in numbers[:2]),
                f'expected={resolution!r} answer={answer!r}')

    pounds = re.search(r'([\d.]+)\s*lb', weight)
    judge.check('ground_truth_weight_in_pounds', bool(pounds), f'weight={weight!r}')
    if pounds:
        judge.check('answer_gives_weight_in_pounds', pounds.group(1) in normalized,
                    f'expected={pounds.group(1)} answer={answer!r}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
