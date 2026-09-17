#!/usr/bin/env python3
"""Verifier for B&H Photo--11: the mirrorless camera with the highest effective megapixels."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    names_product,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    states_measurement,
    visited_path,
)

TASK_ID = 'B&H Photo--11'


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
        SELECT name, slug, megapixels FROM products
        WHERE subcategory_slug = 'mirrorless-cameras'
        ORDER BY megapixels DESC, name ASC
    """) if initial else []
    judge.check('ground_truth_readable', len(rows) >= 2, f'cameras={len(rows)}')
    if len(rows) < 2:
        judge.emit()
    judge.check('all_candidates_have_effective_resolution', all(row['megapixels'] and row['megapixels'] > 0 for row in rows), 'missing values invalidate a whole-catalogue comparison')
    winner = rows[0]
    judge.check('winner_is_unambiguous', winner['megapixels'] > rows[1]['megapixels'],
                f"{winner['megapixels']} vs {rows[1]['megapixels']}")

    judge.check('browsed_mirrorless_cameras',
                visited_path(trajectory, '/c/mirrorless-cameras')
                or all(visited_path(trajectory, '/product/' + row['slug']) for row in rows),
                'mirrorless listing or every candidate product page')
    judge.check('answer_names_the_camera', names_product(answer, winner['name']),
                f"expected={winner['name']!r} answer={answer!r}")
    judge.check('answer_states_the_figure',
                states_measurement(answer, winner['megapixels'],
                                   {r'megapixels?': 1, r'mp': 1, r'pixels?': 1e-6}),
                f"expected={winner['megapixels']} answer={answer!r}")

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
