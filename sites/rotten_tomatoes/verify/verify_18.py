#!/usr/bin/env python3

import re

from verify_lib import (Judge, check_common, check_read_only, clicked_from_query,
                        clicked_transition, final_answer, has_number, load_run,
                        normalize_text, parse_args, resolve_db, row_dicts,
                        visited_path, visited_query)

TASK_ID = 'RottenTomatoes--18'


def search_used(trajectory):
    return visited_query(trajectory, '/search', {'search': 'Kevin Feige'}) or visited_query(
        trajectory, '/search', {'q': 'Kevin Feige'})


def clicked_result(trajectory, slug):
    return clicked_from_query(trajectory, '/search', {'search': 'Kevin Feige'}, '/m/' + slug) or clicked_from_query(
        trajectory, '/search', {'q': 'Kevin Feige'}, '/m/' + slug)


def result_line(answer, row):
    for line in answer.splitlines():
        normalized = normalize_text(line)
        if normalize_text(row['title']) not in normalized or not has_number(line, row['audience_score']):
            continue
        if row['release_date_streaming']:
            if normalize_text(row['release_date_streaming']) in normalized:
                return True
        elif re.search(r'\b(?:not listed|unlisted|not available|no streaming (?:release )?date)\b', normalized):
            return True
    return False


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    rows = row_dicts(initial, """SELECT slug,title,audience_score,release_date_streaming,producer FROM movies
        WHERE instr(','||replace(producer,', ', ',')||',',',Kevin Feige,')>0
        ORDER BY slug""") if initial else []
    scores = [row['audience_score'] for row in rows if row['audience_score'] is not None]
    winners = [row for row in rows if row['audience_score'] == max(scores)] if scores else []
    judge.check('ground_truth_readable', bool(initial and rows and winners), f'candidates={len(rows)} winners={len(winners)}')
    judge.check('searched_kevin_feige', search_used(trajectory), 'Kevin Feige search')
    all_details = bool(rows) and all(clicked_result(trajectory, row['slug']) for row in rows)
    filmography_route = (visited_path(trajectory, '/celebrity/kevin_feige') and
                         (clicked_from_query(trajectory, '/search', {'search': 'Kevin Feige'}, '/celebrity/kevin_feige') or
                          clicked_from_query(trajectory, '/search', {'q': 'Kevin Feige'}, '/celebrity/kevin_feige')) and
                         all(clicked_transition(trajectory, '/celebrity/kevin_feige', '/m/' + row['slug'])
                             for row in winners))
    judge.check('complete_eligible_comparison', all_details or filmography_route,
                f"detail_candidates={[row['slug'] for row in rows]} filmography={filmography_route}")
    for row in winners:
        judge.check('winner_record_' + row['slug'], result_line(answer, row), repr(answer))
    extras = [row['title'] for row in rows if row not in winners and normalize_text(row['title']) in normalize_text(answer)]
    judge.check('no_extra_result_movies', not extras, f'extras={extras}')
    check_read_only(judge, args)
    judge.emit()


if __name__ == '__main__':
    main()
