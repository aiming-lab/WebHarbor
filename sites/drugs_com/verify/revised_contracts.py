"""Source-backed, multi-page task contracts. Answers stay out of tasks.jsonl.

The old entrypoints retain their original task contracts for regression tests;
the revised task manifest selects verify_revised_N.py. The trusted harness owns
that choice, just as it owns screenshots and snapshots. No trajectory-controlled
version switch is accepted.
"""
import json
import re
from datetime import datetime

import verify_lib as v

LABELS = {
    0: ['ibuprofen', 'naproxen'], 1: ['metformin', 'semaglutide'],
    3: ['ibuprofen'], 4: ['lisinopril', 'lorazepam'],
    6: ['metformin', 'semaglutide'], 7: ['semaglutide', 'metformin'],
    9: ['atorvastatin'], 11: ['ibuprofen', 'metformin', 'atorvastatin'],
    12: ['atorvastatin', 'sertraline'], 16: ['alprazolam', 'lorazepam'],
    20: ['lisinopril'],
}


def blocks(answer, entities):
    """Associate successive prose/table/bullet assertions with their named drug.

    Repeated drug headings are allowed. Assertions before any entity are not
    treated as evidence for a drug. This is a bounded parser, not an LLM.
    """
    matches = sorted((m.start(), m.end(), entity) for entity in entities
                     for m in v.term_pattern(entity).finditer(answer))
    result = {entity: [] for entity in entities}
    for index, (start, end, entity) in enumerate(matches):
        stop = matches[index+1][0] if index+1 < len(matches) else len(answer)
        result[entity].append(answer[start:stop])
    return {entity: ' '.join(parts) for entity, parts in result.items()}


def positive(text, pattern):
    matches = list(re.finditer(pattern, text, re.I))
    return bool(matches) and all(v.claim_is_affirmed(text, match) for match in matches)


def field(judge, name, text, values, domain=()):
    judge.check(name, all(any(v.affirmed(text, alias) for alias in aliases) for aliases in values)
                and not any(v.affirmed(text, wrong) for wrong in domain))


def formulation(judge, slug, text, record):
    expected = record['forms']
    groups = []
    for value in expected:
        words = v.norm(value)
        if words == 'tablet':
            groups.append(('tablet', 'tablets'))
        elif words == 'tablet film coated':
            groups.extend([('tablet', 'tablets'), ('film coated', 'film-coated')])
        elif words == 'tablet extended release':
            groups.extend([('tablet', 'tablets'), ('extended release', 'extended-release', 'ER')])
        elif words == 'injection solution':
            groups.extend([('injection', 'injectable'), ('solution',)])
        elif words == 'solution concentrate':
            groups.extend([('solution',), ('concentrate', 'concentrated')])
        else:
            groups.append((value,))
    field(judge, slug+'_form', text, groups)
    if record['routes'] == ['ORAL']:
        field(judge, slug+'_route', text, [('oral', 'by mouth', 'orally')], ['subcutaneous', 'intravenous'])
    else:
        field(judge, slug+'_route', text, [('subcutaneous', 'under the skin', 'under skin')], ['oral', 'intravenous'])
    for wrong in ['immediate release'] if 'TABLET, EXTENDED RELEASE' in expected else []:
        judge.check(slug+'_no_wrong_release', not v.affirmed(text, wrong))


def labeler(judge, slug, text, record):
    # Corporate suffix punctuation is not a meaningful answer difference.
    values = [re.sub(r'\b(?:LLC|INC|PBC|P\.B\.C\.|LP|LTD)\b[.,]*', '', value, flags=re.I).strip(' ,.') for value in record['labelers']]
    field(judge, slug+'_labeler', text, [(value,) for value in values])


def date_field(judge, slug, text, record, key, context):
    raw = record[key]
    date = datetime.strptime(raw, '%Y%m%d' if key == 'effective_date' else '%b %d, %Y')
    alternatives = [date.strftime('%Y-%m-%d'), date.strftime('%b %d, %Y'), date.strftime('%B %d, %Y'),
                    f'{date.strftime("%B")} {date.day}, {date.year}', f'{date.strftime("%b")} {date.day}, {date.year}']
    clauses = re.split(r'[;\n|]', text)
    matching = [clause for clause in clauses if re.search(context, clause, re.I)]
    def valid(clause):
        if not any(v.affirmed(clause, value) for value in alternatives):
            return False
        # A correct reference date must not camouflage a competing ISO date.
        return all(value == date.strftime('%Y-%m-%d') for value in re.findall(r'\b\d{4}-\d{2}-\d{2}\b', clause))
    judge.check(slug+'_'+key, bool(matching) and all(valid(clause) for clause in matching))


def number_field(judge, name, text, pattern, expected):
    matches = list(re.finditer(pattern, text, re.I))
    judge.check(name, bool(matches) and all(tuple(float(x) for x in match.groups()) == tuple(expected)
                                          and (match.group(0).lower().startswith('do not exceed') or v.claim_is_affirmed(text, match)) for match in matches))


def verify_revised_task(number, judge, trajectory, visits, initial):
    answer = v.normalize_answer_layout(str(trajectory.get('final_answer') or ''))
    # Conventional number words and a daily limit are equivalent units, not an
    # output-format requirement. Keep the original text in the trajectory.
    for word, value in v._NUMBER_ONES.items():
        answer = re.sub(r'\b'+word+r'\b', str(value), answer, flags=re.I)
    answer = re.sub(r'\btwenty[- ]four\b', '24', answer, flags=re.I)
    answer = re.sub(r'\btwenty[- ]4\b', '24', answer, flags=re.I)
    answer = re.sub(r'(tablets?)\s+(?:per day|daily)\b', r'\1 in 24 hours', answer, flags=re.I)
    entities = LABELS[number]
    records = {row['slug']: json.loads(row['data_json']) for row in initial.query(
        'SELECT d.slug,l.data_json FROM daily_med_label l JOIN drug d ON d.id=l.drug_id')}
    scoped = blocks(answer, entities)
    for slug in entities:
        v.require_click_transition(judge, trajectory, visits, 'ui_source_'+slug,
            lambda visit: visit.path != f'/{slug}/official-label',
            lambda visit: v.route_is(visit, f'/{slug}/official-label'))
        entity_clauses = [clause for clause in re.split(r'(?<=[.;!?\n])\s*', answer) if v.mentions(clause,slug)]
        judge.check('answer_entity_'+slug, bool(scoped[slug]) and bool(entity_clauses)
                    and all(v.affirmed(clause,slug) for clause in entity_clauses))
    # Reading/opening sections after navigation is allowed. No minimum click
    # count is imposed; task difficulty comes from the requested comparisons.
    if number in {4, 6, 9, 16, 20}:
        wanted = {4: ('/drug_information.html', 'L'), 6: ('/conditions/diabetes', None),
                  9: ('/drug-classes/statins', None), 16: ('/drug-classes/benzodiazepines', None),
                  20: ('/conditions/hypertension', None)}[number]
        v.require_visit(judge, visits, 'ui_original_catalog_context', lambda visit:
            (v.path_is(visit, wanted[0], wanted[0]+'.html') and
             (v.scalar_query(visit,'letter',wanted[1]) if wanted[1] else not visit.query)))
    if number == 0:
        for slug, low, high, maximum in [('ibuprofen',4,6,6), ('naproxen',8,12,3)]:
            text=scoped[slug]
            number_field(judge, slug+'_interval_hours', text, r'(?:every|interval\s*[:=]?)\s*(\d+)\s*(?:to|[-–])\s*(\d+)\s*hours?', (low,high))
            number_field(judge, slug+'_maximum_tablets', text, r'(?:maximum|max|limit|do not exceed)\s*(?:of|is|:|=)?\s*(\d+)\s*tablets?\s*(?:in|per|every|within|over)\s*(\d+)\s*hours?', (maximum,24))
    elif number in {1,6}:
        for slug in entities:
            formulation(judge,slug,scoped[slug],records[slug])
            if number == 6:
                labeler(judge,slug,scoped[slug],records[slug])
        if number == 1:
            field(judge,'metformin_boxed_warning',scoped['metformin'],[('lactic acidosis',)])
            field(judge,'semaglutide_boxed_warning',scoped['semaglutide'],[('thyroid C-cell tumors','thyroid C cell tumours')])
    elif number == 3:
        pills = blocks(answer, ['I-2','IP 466','ibuprofen'])
        for imprint in ['I-2','IP 466']:
            v.require_visit(judge,visits,'ui_pill_'+imprint,lambda visit:
                v.path_is(visit,'/pill-identifier','/pill-identifier.html') and visit.values('imprint')==[imprint])
            row=initial.query('SELECT shape,color,strength FROM drug_image WHERE imprint=?',(imprint,))[0]
            field(judge,'pill_'+imprint,pills[imprint],[(row['shape'],),(row['color'],),(row['strength'],)])
            number_field(judge,'pill_strength_'+imprint,pills[imprint],r'(\d+)\s*mg\b',(float(row['strength'].split()[0]),))
        labeler(judge,'ibuprofen',scoped['ibuprofen'],records['ibuprofen'])
        field(judge,'source_product_strength',scoped['ibuprofen'],[('200 mg','200mg')])
        judge.check('not_real_pill_identification',bool(re.search(r'\b(?:cannot|does not|do not|not)\b[^.;\n]{0,65}\b(?:identify|identification|verify|real pill|photograph)',answer,re.I)))
    elif number == 4:
        for slug in entities:
            labeler(judge,slug,scoped[slug],records[slug])
            date_field(judge,slug,scoped[slug],records[slug],'effective_date',r'\beffective\b')
    elif number == 7:
        formulation(judge,'semaglutide',scoped['semaglutide'],records['semaglutide'])
        formulation(judge,'metformin',scoped['metformin'],records['metformin'])
        uncertainty = any(v.affirmed(scoped['semaglutide'], cue) for cue in ['unknown','not known','not established','not determined'])
        certainty = any(v.affirmed(scoped['semaglutide'], cue) for cue in ['proven','confirmed','definitely causes'])
        judge.check('semaglutide_human_risk_uncertain', uncertainty and not certainty and bool(re.search(r'(?:unknown|not (?:known|established|determined))[^.;\n]{0,100}human|human[^.;\n]{0,100}(?:unknown|not (?:known|established|determined))',scoped['semaglutide'],re.I)))
        judge.check('metformin_swallow_whole',positive(scoped['metformin'],r'\b(?:swallow(?:ed)? whole|taken whole)\b') and bool(re.search(r'\b(?:do not|must not|not|never)\s+(?:be\s+)?(?:crush(?:ed)?|cut|chew(?:ed)?)\b',scoped['metformin'],re.I)) and not re.search(r'\b(?:can|may|should)\s+(?:be\s+)?(?:crush(?:ed)?|chew(?:ed)?)\b',scoped['metformin'],re.I))
        judge.check('no_crushing_permission',not re.search(r'\b(?:crush(?:ing|ed)?|chew(?:ing|ed)?)\s+(?:is|are)\s+(?:allowed|safe|recommended|permitted)\b',scoped['metformin'],re.I))
    elif number == 9:
        names=v.drugs_for_class(initial,'statins')
        listed=[name for name in names if v.affirmed(answer,name)]
        judge.check('three_catalog_statins',len(set(listed))>=3)
        v.check_domain_subset(judge,'only_catalog_statins',answer,v.all_drug_names(initial),names)
        labeler(judge,'atorvastatin',scoped['atorvastatin'],records['atorvastatin'])
        date_field(judge,'atorvastatin',scoped['atorvastatin'],records['atorvastatin'],'effective_date',r'\beffective\b')
        date_field(judge,'atorvastatin',scoped['atorvastatin'],records['atorvastatin'],'published_date',r'\b(?:published|publication)\b')
    elif number == 11:
        for slug in entities:
            date_field(judge,slug,scoped[slug],records[slug],'published_date',r'\b(?:published|publication)\b')
        newest=max(entities,key=lambda slug:datetime.strptime(records[slug]['published_date'],'%b %d, %Y'))
        judge.check('most_recent_label',positive(scoped[newest],r'\b(?:most recent|newest|latest)\b') and all(not re.search(r'\b(?:most recent|newest|latest)\b',scoped[slug],re.I) for slug in entities if slug!=newest))
    elif number == 12:
        # These two package strengths were transcribed from the exact archived
        # package images; the canonical seed binds the image hashes/provenance.
        for slug,strength in [('atorvastatin',10),('sertraline',25)]:
            labeler(judge,slug,scoped[slug],records[slug])
            number_field(judge,slug+'_package_strength_mg',scoped[slug],r'(\d+(?:\.\d+)?)\s*mg\b',(strength,))
        judge.check('packaging_not_pill_photos',bool(re.search(r'(?:not|aren.t)\s+(?:(?:real\s+)?pill\s+photo(?:graph)?s?|photo(?:graph)?s? of (?:real )?pills)',answer,re.I)))
    elif number == 16:
        for slug in entities:
            labeler(judge,slug,scoped[slug],records[slug])
            field(judge,slug+'_boxed_warning',scoped[slug],[('opioids','opioid'),('respiratory depression','slowed breathing'),('abuse','misuse'),('addiction',),('dependence',),('withdrawal',)])
    elif number == 20:
        text=scoped['lisinopril']
        number_field(judge,'usual_initial_adult_dose',text,r'(?:without diuretics|not taking (?:a )?diuretics?|initial adult dose)\s*(?:(?:start|starts|starting)(?: at)?|is|:|=)?\s*(\d+)\s*mg\s*(?:once (?:a |per )?day|daily)',(10,))
        with_text = re.sub(r'\bnot taking (?:a )?diuretics?\b', 'without diuretics', text, flags=re.I)
        number_field(judge,'initial_dose_with_diuretic',with_text,r'(?:with diuretics|taking (?:a )?diuretics?|on diuretics)\s*(?:(?:start|starts|starting)(?: at)?|is|:|=)?\s*(\d+)\s*mg\s*(?:once (?:a |per )?day|daily)',(5,))
        field(judge,'fetal_toxicity_warning',text,[('fetal toxicity','harm to the fetus','injury and death to the developing fetus'),('discontinue','stop taking'),('pregnancy','pregnant')])
        judge.check('pregnancy_detection_action',bool(re.search(r'(?:discontinue|stop taking)[^.;\n]{0,50}(?:when|if|once)[^.;\n]{0,20}(?:pregnancy is (?:detected|confirmed)|(?:you (?:are|become) )?pregnant)|(?:pregnancy|pregnant)[^.;\n]{0,30}(?:detected|confirmed)[^.;\n]{0,60}(?:discontinue|stop taking)',text,re.I)))
