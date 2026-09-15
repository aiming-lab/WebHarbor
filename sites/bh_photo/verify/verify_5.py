#!/usr/bin/env python3
"""Verifier for B&H Photo--5: Sony E mount lenses under $150.

The agent must reach the filtered listing rather than guess; the answer must
carry both the match count and the cheapest match.
"""
from verify_lib import (names_product, Judge, changed_tables_excluding, check_common, final_answer,
                        load_run, normalize_text, only_allowed_tables_changed, parse_args,
                        resolve_db, row_dicts, states_count, trajectory_urls, visited_path)

TASK_ID = 'B&H Photo--5'
PRICE_CAP = 150.0


def used_mount_filter(trajectory) -> bool:
    """True when a listing URL carried a Sony E mount filter."""
    for url in trajectory_urls(trajectory):
        lowered = url.lower().replace('%20', ' ').replace('+', ' ')
        if 'mount=' in lowered and 'sony e' in lowered:
            return True
    return False


def used_price_filter(trajectory) -> bool:
    return any('max_price=' in url.lower() for url in trajectory_urls(trajectory))


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
    judge.check('applied_mount_filter', used_mount_filter(trajectory), 'mount=Sony E in a listing URL')
    judge.check('applied_price_filter', used_price_filter(trajectory), 'max_price in a listing URL')
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
