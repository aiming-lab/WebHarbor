#!/usr/bin/env python3
"""Verifier for B&H Photo--5: Sony E mount lenses under $150.

The agent must reach the filtered listing rather than guess; the answer must
carry both the match count and the cheapest match.
"""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    names_product,
    normalize_text,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    states_count,
    visited_path,
    visited_query,
)

TASK_ID = 'B&H Photo--5'
PRICE_CAP = 150.0


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    matches = row_dicts(initial, """
        SELECT name, slug, price FROM products
        WHERE mount_type = 'Sony E' AND price < ? ORDER BY price ASC
    """, (PRICE_CAP,)) if initial else []
    judge.check('ground_truth_readable', bool(matches), f'matches={len(matches)}')
    if not matches:
        judge.emit()
    cheapest = matches[0]

    judge.check('reached_a_lens_listing',
                visited_path(trajectory, '/c/camera-lenses') or visited_path(trajectory, '/c/photography'),
                'lens or photography listing')
    judge.check('applied_mount_filter', visited_query(trajectory, '/c/camera-lenses', {'mount': 'Sony E', 'max_price': '150'}), 'mount and max_price=150 on the same lens listing')
    judge.check('applied_price_filter', visited_query(trajectory, '/c/camera-lenses', {'mount': 'Sony E', 'max_price': '150'}), 'max_price=150 on the same lens listing')
    judge.check('answer_gives_match_count',
                # plural forms only: the count here is two, and the singular
                # "lens" collides with the aperture in a product name - "f/2
                # Lens" would otherwise read as a claim that two matched
                states_count(answer, len(matches),
                             ['products', 'matches', 'results', 'items', 'lenses']),
                f'expected={len(matches)} answer={answer!r}')
    judge.check('answer_names_cheapest_match',
                names_product(answer, cheapest['name']),
                f"expected={cheapest['name']!r} answer={answer!r}")

    excluded = row_dicts(initial, """
        SELECT name FROM products WHERE mount_type = 'Sony E' AND price >= ?
    """, (PRICE_CAP,)) if initial else []
    named_excluded = [row['name'] for row in excluded if normalize_text(row['name']) in normalize_text(answer)]
    judge.check('answer_excludes_pricier_sony_e_lenses', not named_excluded, f'named={named_excluded}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
