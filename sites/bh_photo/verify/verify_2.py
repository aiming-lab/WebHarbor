#!/usr/bin/env python3
"""Verifier for B&H Photo--2: report the maximum read speed of the Sony CFexpress Type A card.

Ground truth is read from the shipped seed database at verify time, so the
answer key lives here and never in the agent-facing task file.
"""
from verify_lib import (Judge, changed_tables_excluding, check_common, contains_any,
                        final_answer, load_run, normalize_text, only_allowed_tables_changed,
                        parse_args, resolve_db, row_dicts, visited_path)

TASK_ID = 'B&H Photo--2'
SLUG = 'sony-1920gb-cfexpress-4-0-type-a-tough-memory-card'
SPEC_LABEL = 'Read Speed'


def spec_value(db_path):
    rows = row_dicts(db_path, """
        SELECT s.value FROM product_specs s
        JOIN product_spec_groups g ON g.id = s.group_id
        JOIN products p ON p.id = g.product_id
        WHERE p.slug = ? AND s.name = ?
    """, (SLUG, SPEC_LABEL))
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
    value = spec_value(initial) if initial else ''
    judge.check('ground_truth_readable', bool(value), f'spec={value!r}')

    judge.check('opened_product_page', visited_path(trajectory, '/product/' + SLUG),
                f'slug={SLUG}')
    # value reads "Maximum: 1800 MB/s"; the write speed row is the distractor
    import re
    number = re.search(r'([\d,]+)\s*MB/s', value)
    judge.check('ground_truth_has_read_speed', bool(number), f'spec={value!r}')
    if number:
        judge.check('answer_states_read_speed',
                    number.group(1).replace(',', '') in normalize_text(answer).replace(',', ''),
                    f'expected={number.group(1)} answer={answer!r}')
    write_rows = row_dicts(initial, """
        SELECT s.value FROM product_specs s JOIN product_spec_groups g ON g.id = s.group_id
        JOIN products p ON p.id = g.product_id WHERE p.slug = ? AND s.name = 'Write Speed'
    """, (SLUG,)) if initial else []
    if write_rows and number:
        write_number = re.search(r'([\d,]+)\s*MB/s', write_rows[0]['value'])
        if write_number and write_number.group(1) != number.group(1):
            reported_write_only = (write_number.group(1) in normalize_text(answer)
                                   and number.group(1) not in normalize_text(answer))
            judge.check('answer_not_write_speed', not reported_write_only,
                        f'write={write_number.group(1)} answer={answer!r}')
    if initial and after:
        judge.check('no_state_written',
                    only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
