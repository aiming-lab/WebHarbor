#!/usr/bin/env python3
"""Verifier for B&H Photo--6: carry a card format from a camera page to a card page."""
import re

from verify_lib import (names_product, Judge, changed_tables_excluding, check_common, final_answer,
                        has_number, load_run, normalize_text, only_allowed_tables_changed,
                        parse_args, resolve_db, row_dicts, visited_path)

TASK_ID = 'B&H Photo--6'
CAMERA = 'canon-eos-r1-mirrorless-camera-with-essentials-kit'
FORMAT_TOKEN = 'cfexpress type b'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    slot_rows = row_dicts(initial, """
        SELECT s.value FROM product_specs s JOIN product_spec_groups g ON g.id = s.group_id
        JOIN products p ON p.id = g.product_id
        WHERE p.slug = ? AND s.name = 'Media/Memory Card Slot'
    """, (CAMERA,)) if initial else []
    judge.check('ground_truth_slot_readable',
                bool(slot_rows) and FORMAT_TOKEN in normalize_text(slot_rows[0]['value']),
                f'slot={slot_rows[0]["value"] if slot_rows else None!r}')

    cards = row_dicts(initial, """
        SELECT name, slug, price FROM products
        WHERE lower(name) LIKE '%cfexpress type b%' AND lower(name) LIKE '%memory card%'
        ORDER BY price ASC
    """) if initial else []
    judge.check('ground_truth_cards_readable', bool(cards), f'cards={len(cards)}')
    if not cards:
        judge.emit()

    judge.check('opened_camera_page', visited_path(trajectory, '/product/' + CAMERA), CAMERA)
    judge.check('opened_a_matching_card_page',
                any(visited_path(trajectory, '/product/' + card['slug']) for card in cards),
                f'candidates={[card["slug"] for card in cards]}')
    judge.check('answer_states_card_format', FORMAT_TOKEN in normalize_text(answer),
                f'answer={answer!r}')

    named = [card for card in cards if names_product(answer, card['name'])]
    judge.check('answer_names_a_catalogue_card', bool(named),
                f'expected one of {[card["name"] for card in cards]} answer={answer!r}')
    # the two checks above were independent, so a run could open one card and
    # report a different one - both true separately, but the answer then
    # describes a page the run never read. They have to agree.
    opened = [card for card in named if visited_path(trajectory, '/product/' + card['slug'])]
    judge.check('the_card_named_is_the_card_opened', bool(opened),
                f'named={[c["slug"] for c in named]} '
                f'opened={[c["slug"] for c in cards if visited_path(trajectory, "/product/" + c["slug"])]}')
    judge.check('answer_states_that_card_price',
                any(has_number(answer, card['price']) for card in opened),
                f'prices={[card["price"] for card in opened]} answer={answer!r}')

    # a Type A card is the trap: the R1 does not take one
    wrong = row_dicts(initial, """
        SELECT name FROM products WHERE lower(name) LIKE '%cfexpress%type a%'
    """) if initial else []
    named_wrong = [row['name'] for row in wrong if normalize_text(row['name']) in normalize_text(answer)]
    judge.check('answer_does_not_offer_a_type_a_card', not named_wrong, f'named={named_wrong}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
