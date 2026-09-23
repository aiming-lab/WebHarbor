"""Reviewed Imgur task contracts. Natural text checks are lexical and scoped;
they are not a general semantic judge. State checks require precise deltas."""
import json
import re
from pathlib import Path
from verify_lib import (check_trajectory_identity, check_signed_in_as,
    check_read_only, check_only_tables_changed, navigated_to_path, final_answer,
    table_delta, row_dict, SEED_USERS)
CONFIG = json.loads(Path(__file__).with_name('reviewed_tasks.json').read_text())

def fact_scope(answer, entity, entities=()):
    # Split prose at sentence boundaries without splitting decimals, and split
    # tables/bullets at line boundaries. Keep a named entity's contiguous text.
    answer = answer.replace('’', "'").replace('“', '"').replace('”', '"')
    answer = re.sub(r'(?i)\bUSD\s*([\d,.]+)', r'$\1', answer)
    answer = re.sub(r'(?i)([\d,.]+)\s+dollars\b', r'$\1', answer)
    # A quoted post title may contain whole sentences. Protect its sentence
    # breaks while retaining decimals and the actual words for matching.
    answer = re.sub(r'"[^"]*"', lambda m: re.sub(r'([.!?])(?=\s+[A-Z])', ' ', m.group()), answer)
    segments = re.split(r'\n|(?<=[.!?])\s+(?=[A-Z])', answer)
    if entities:
        labels = '|'.join('(?:' + e + ')' for e in entities)
        # Product/comment comparisons often use semicolons, table cells, or
        # "and" within one sentence. Keep each explicitly named entity with
        # its own following facts; do not pool all values in that sentence.
        boundary = r'(?:;\s*|,\s*|\s+and\s+|\|\s*)(?=["\']?(?:[A-Za-z][A-Za-z\'_-]*\s+){0,4}(?:' + labels + r'))'
        segments = [part for segment in segments for part in re.split(boundary, segment, flags=re.I)]

    return ' '.join(s for s in segments if re.search(entity, s, re.I))


def check_facts(judge, answer, facts):
    for index, fact in enumerate(facts):
        scoped = fact_scope(answer, fact['entity'], [f['entity'] for f in facts])
        judge.check(f'fact_{index}_entity', bool(scoped), fact['entity'])
        for n, pattern in enumerate(fact['patterns']):
            matches = list(re.finditer(pattern, scoped, re.I))
            # Reject an explicitly denied positive value, but allow requirements
            # whose expected fact is itself negative (e.g. no tumble drying).
            negative_fact = bool(re.search(r'no |not |unknown|missing|unavailable|too wide|exceed|ineligible', pattern))
            denied = False
            if not negative_fact:
                for m in matches:
                    before = scoped[max(0,m.start()-35):m.start()]
                    after = scoped[m.end():m.end()+30]
                    denied |= bool(re.search(r'\b(?:not|never|incorrect(?:ly)?|wrong)\s*(?:a |an |at |is |was )?$', before, re.I)
                                   or re.match(r'\s+(?:is|was)\s+(?:wrong|incorrect|false)', after, re.I))
            judge.check(f'fact_{index}_{n}', bool(matches) and not denied,
                        f'{fact["entity"]}: expected {pattern}')


def run_checks(judge, traj, initial_db, after_db):
    spec = CONFIG[judge.task_id.rsplit('--', 1)[1]]
    check_trajectory_identity(judge, traj, judge.task_id)
    for path in spec['paths']:
        judge.check('visited_' + path, navigated_to_path(traj, path), path)
    if spec.get('login'):
        check_signed_in_as(judge, traj, spec['email'], SEED_USERS[spec['email']][1])
    check_facts(judge, final_answer(traj), spec['facts'])
    state = spec.get('state')
    if not state:
        check_read_only(judge, initial_db, after_db)
        return
    kind = state['kind']
    table = {'favorite':'favorites','follow':'follow_user','tag':'follow_tag','reply':'comments'}[kind]
    check_only_tables_changed(judge, initial_db, after_db,
                              {table, 'posts'} if kind == 'reply' else {table})
    delta = table_delta(initial_db, after_db, table)
    judge.check('preserved_existing_rows', not delta['removed'] and not delta['changed'], str(delta))
    rows = [row_dict(initial_db, table, r) for r in delta['added']]
    uid = spec['uid']
    if kind == 'favorite':
        observed = [(r['user_id'], r['post_id']) for r in rows]
        expected = [(uid, state['post'])]
    elif kind == 'follow':
        observed = [(r['follower_id'], r['followee_id']) for r in rows]
        expected = [(uid, state['target'])]
    elif kind == 'tag':
        observed = [(r['user_id'], r['tag_name']) for r in rows]
        expected = [(uid, t) for t in state['targets']]
    else:
        observed = [(r['author_id'],r['post_id'],r['parent_id'],r['text'],r['point_count'],r['upvote_count'],r['downvote_count'],r['image_path'] or '') for r in rows]
        expected = [(uid,state['post'],state['parent'],state['text'],0,0,0,'')]
        post_delta = table_delta(initial_db, after_db, 'posts')
        valid = not post_delta['added'] and not post_delta['removed'] and len(post_delta['changed']) == 1
        for old, new in post_delta['changed']:
            before = row_dict(initial_db, 'posts', old)
            after = row_dict(initial_db, 'posts', new)
            before['comment_count'] += 1
            valid &= before == after and before['id'] == state['post']
        judge.check('exact_comment_count_increment', valid, str(post_delta))
    judge.check('exact_requested_delta', sorted(observed) == sorted(expected),
                f'expected={expected}; observed={observed}')
