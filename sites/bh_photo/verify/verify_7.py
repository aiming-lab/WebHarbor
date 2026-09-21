#!/usr/bin/env python3
"""Verifier for B&H Photo--7: which of three laptops lists an Intel processor."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    clauses,
    compare_members_seen,
    final_answer,
    load_run,
    names_product,
    normalize_text,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
)

TASK_ID = 'B&H Photo--7'
CANDIDATES = [
    'apple-14-macbook-pro-m5-silver',
    'lenovo-16-thinkpad-t1g-gen-8-multi-touch-laptop',
    'asus-16-vivobook-16-laptop-copilot-pc-cool-silver',
]


def processor(db_path, slug):
    rows = row_dicts(db_path, """
        SELECT s.value FROM product_specs s JOIN product_spec_groups g ON g.id = s.group_id
        JOIN products p ON p.id = g.product_id WHERE p.slug = ? AND s.name = 'Processor'
    """, (slug,))
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

    specs = {slug: processor(initial, slug) for slug in CANDIDATES} if initial else {}
    intel = [slug for slug, value in specs.items() if 'intel' in normalize_text(value)]
    judge.check('ground_truth_single_intel', len(intel) == 1, f'specs={specs}')
    if len(intel) != 1:
        judge.emit()
    winner_slug = intel[0]
    winner = row_dicts(initial, 'SELECT name FROM products WHERE slug = ?', (winner_slug,))[0]['name']
    losers = [row_dicts(initial, 'SELECT name FROM products WHERE slug = ?', (slug,))[0]['name']
              for slug in CANDIDATES if slug != winner_slug]

    judge.check('inspected_all_three',
                compare_members_seen(trajectory, CANDIDATES, initial, after),
                'three product pages or the compare page')
    judge.check('answer_names_the_intel_laptop',
                names_product(answer, winner),
                f'expected={winner!r} answer={answer!r}')
    # Describing a non-Intel processor does not select that laptop as Intel.
    named_losers = []
    for slug in CANDIDATES:
        if slug == winner_slug:
            continue
        name = row_dicts(initial, 'SELECT name FROM products WHERE slug=?', (slug,))[0]['name']
        for claim in clauses(answer):
            if names_product(claim, name) and normalize_text(specs[slug]) not in claim:
                named_losers.append(name)
    judge.check('answer_selects_only_the_intel_laptop', not named_losers, f'other selections={named_losers}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
