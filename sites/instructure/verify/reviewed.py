"""Reviewed factual contracts. Deterministic lexical checks have bounded paraphrase coverage.
Facts are scoped to subjects; navigation and immutable snapshots are checked separately.
Action counts never determine success. Ground truth is not shipped in task prompts.
"""
import json
import re
from pathlib import Path
from verify_lib import (check_trajectory_identity, check_signed_in_as, check_read_only,
                        navigated_to_path, final_answer)
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
    answer = re.sub(r'\b(Dr|Mr|Ms|Mrs|Prof)\.', r'\1', answer)
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
    # References, identifiers and quoted answer banks are not asserted task facts.
    answer = re.sub(r"(?im)(?:^|[;\n])\s*(?:reference(?: text| code| id| number)?|index(?:ing)? text)\b[^\n]*", "", answer)
    # Financial listings use K notation; accept equivalent whole-dollar amounts.
    def compact_money(match):
        value = int(match.group(1).replace(',', ''))
        return '$' + str(value // 1000) + 'K' if value >= 100000 and value % 1000 == 0 else match.group(0)
    answer = re.sub(r"\$([0-9]{1,3}(?:,[0-9]{3})+)\b", compact_money, answer)
    for index, fact in enumerate(facts):
        scoped = fact_scope(answer, fact['entity'], [] if fact.get('whole_sentence') else [f['entity'] for f in facts])
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
    if spec.get('email'):
        check_signed_in_as(judge, traj, spec['email'])
    check_facts(judge, final_answer(traj), spec['facts'])
    if spec.get('save_resource'):
        from verify_lib import table_delta, check_only_tables_changed, user_by_email
        delta = table_delta(initial_db, after_db, 'saved_resources')
        uid = user_by_email(initial_db, spec['email'])['id']
        judge.check('exact_saved_report', not delta['removed'] and not delta['changed']
                    and len(delta['added']) == 1
                    and delta['added'][0][1:3] == (uid, spec['save_resource']),
                    'exactly the requested report saved by the requested account')
        check_only_tables_changed(judge, initial_db, after_db, ['saved_resources'])
    else:
        check_read_only(judge, initial_db, after_db)
