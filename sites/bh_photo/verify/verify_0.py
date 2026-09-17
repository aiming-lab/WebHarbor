#!/usr/bin/env python3
"""Verifier for B&H Photo--0: report the fisheye lens angle of view.

Ground truth is read from the shipped seed database at verify time, so the
answer key lives here and never in the agent-facing task file.
"""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    normalize_text,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    states_measurement,
    visited_path,
)

TASK_ID = 'B&H Photo--0'
SLUG = '7artisans-6mm-f-2-fisheye-lens-micro-four-thirds'
SPEC_LABEL = 'Angle of View'


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
    # The reported value must carry its angular unit.
    digits = ''.join(ch for ch in value if ch.isdigit())
    judge.check('answer_states_angle_of_view',
                bool(digits) and states_measurement(answer, float(digits), {r'°|degrees?': 1}),
                f'expected={value!r} answer={answer!r}')
    judge.check('answer_is_not_just_the_product_name',
                normalize_text(answer) != normalize_text('7Artisans 6mm f/2 Fisheye Lens (Micro Four Thirds)'),
                f'answer={answer!r}')
    if initial and after:
        judge.check('no_state_written',
                    only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
