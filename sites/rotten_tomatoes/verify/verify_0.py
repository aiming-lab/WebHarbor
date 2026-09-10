#!/usr/bin/env python3
from datetime import datetime

from verify_lib import (Judge, check_common, check_read_only, clicked_from_query,
                        contains_all, final_answer, load_run, normalize_text,
                        parse_args, resolve_db, row_dicts, visited_query_without)

TASK_ID = 'RottenTomatoes--0'
BROWSE = '/browse/movies_at_home'
FILTER = {'genre': 'sci-fi', 'platform': 'Netflix'}


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    rows = row_dicts(initial, """SELECT DISTINCT m.slug,m.title,m.release_date_streaming,m.screenwriter
        FROM movies m JOIN movie_genres mg ON mg.movie_id=m.id JOIN genres g ON g.id=mg.genre_id
        WHERE m.available_at_home=1 AND g.slug='sci-fi'
          AND instr(','||replace(m.streaming_platform,', ', ',')||',',',Netflix,')>0
        ORDER BY m.slug""") if initial else []
    dated = [(datetime.strptime(row['release_date_streaming'], '%b %d, %Y'), row)
             for row in rows if row['release_date_streaming']]
    winners = [row for date, row in dated if date == max(value for value, _row in dated)] if dated else []
    judge.check('ground_truth_readable', bool(initial and rows and winners), f'candidates={len(rows)} winners={len(winners)}')
    judge.check('used_exact_netflix_scifi_filter', visited_query_without(
        trajectory, BROWSE, FILTER, ('provider',)), repr(FILTER))
    judge.check('inspected_every_candidate_from_filtered_results', bool(rows) and all(
        clicked_from_query(trajectory, BROWSE, FILTER, '/m/' + row['slug']) for row in rows),
        f"required={[row['slug'] for row in rows]}")
    for row in winners:
        screenwriters = [name.strip() for name in row['screenwriter'].split(',') if name.strip()]
        judge.check('winner_record_' + row['slug'], contains_all(
            answer, [row['title'], row['release_date_streaming'], *screenwriters]), repr(answer))
    extras = [row['title'] for row in rows if row not in winners and normalize_text(row['title']) in normalize_text(answer)]
    judge.check('no_extra_result_movies', not extras, f'extras={extras}')
    check_read_only(judge, args)
    judge.emit()


if __name__ == '__main__':
    main()
