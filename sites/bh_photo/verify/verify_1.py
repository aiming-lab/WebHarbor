#!/usr/bin/env python3
"""Verifier for B&H Photo--1: two detail-only rows from the body-only EOS 90D.

Ground truth is read from the shipped seed at verify time, so the answer key
lives here and never in the agent-facing task file.
"""
import re

from verify_lib import (
    Judge,
    affirmative_contains,
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

TASK_ID = 'B&H Photo--1'
SLUG = 'canon-eos-90d-dslr-camera-body-only'
KIT_SLUG = 'canon-eos-90d-dslr-camera-with-18-135mm-lens'


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

    # the monitor group carries the dot count; the card's key features do not
    resolution = spec(initial, 'Resolution')
    battery = spec(initial, 'Battery')
    judge.check('ground_truth_readable', bool(resolution and battery),
                f'resolution={resolution!r} battery={battery!r}')

    judge.check('opened_the_body_only_page', visited_path(trajectory, '/product/' + SLUG + '/specs'), SLUG + '/specs')
    normalized = normalize_text(answer)

    numbers = re.findall(r'\d[\d,]*(?:\.\d+)?', resolution)
    judge.check('answer_gives_screen_resolution',
                bool(numbers) and states_measurement(answer, float(numbers[0].replace(',', '')), {r'dots?': 1}),
                f'expected={resolution!r} answer={answer!r}')

    # the battery row reads like "1x LP-E6N Rechargeable Lithium-Ion, 7.2 VDC, ..."
    model = re.search(r'\b([A-Z]{2,3}-?[A-Z0-9]{2,8})\b', battery)
    judge.check('ground_truth_battery_model', bool(model), f'battery={battery!r}')
    if model:
        judge.check('answer_names_the_battery_model',
                    affirmative_contains(answer, model.group(1)),
                    f'expected={model.group(1)!r} answer={answer!r}')

    judge.check('did_not_answer_from_the_kit_page',
                visited_path(trajectory, '/product/' + SLUG)
                or not visited_path(trajectory, '/product/' + KIT_SLUG),
                'body-only page required')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
