"""Synthetic controls for the current harder tasks, separate from browser runs."""
import json
import subprocess

import pytest

import revised_contracts as r
import verify_lib as v
from test_verifiers import PYTHON, VERIFY, ROOT, canonical_seed, snapshots, make_run


ANSWERS = {
    0: 'Ibuprofen: every 4-6 hours; maximum 6 tablets in 24 hours. Naproxen: every 8-12 hours; maximum 3 tablets in 24 hours.',
    1: 'Metformin: extended-release tablets, oral; boxed warning: lactic acidosis. Semaglutide: injection solution, subcutaneous; boxed warning: thyroid C-cell tumors.',
    3: 'I-2: Oval, White, 200 mg. IP 466: Oval, White, 800 mg. Ibuprofen DailyMed packaging: 200 mg; labeler: Cabinet Health P.B.C. These records cannot identify a real pill.',
    4: 'Lisinopril: labeler Upsher-Smith Laboratories, LLC; effective 2025-01-02. Lorazepam: labeler Clinical Solutions Wholesale, LLC; effective 2026-09-10.',
    6: 'Metformin: extended-release tablets, oral; labeler Ajanta Pharma USA Inc. Semaglutide: injection solution, subcutaneous; labeler Novo Nordisk Pharmaceutical Industries, LP.',
    7: 'Semaglutide: injection solution, subcutaneous; the risk of thyroid C-cell tumors in humans is unknown. Metformin: extended-release tablets, oral; swallow whole, do not crush or chew.',
    9: 'Three statins are atorvastatin, pravastatin, and rosuvastatin. Atorvastatin: labeler Viatris Specialty LLC; effective 2024-04-15; published 2026-07-15.',
    11: 'Ibuprofen: published September 15, 2026. Atorvastatin: published July 15, 2026. Metformin: published September 17, 2026, the most recent.',
    12: 'Atorvastatin: pictured package 10 mg; labeler Viatris Specialty LLC. Sertraline: pictured package 25 mg; labeler Viatris Specialty LLC. These are packaging labels, not pill photographs.',
    16: 'Alprazolam: labeler Pharmacia & Upjohn Company LLC; opioids can cause respiratory depression; warnings about abuse, addiction, dependence and withdrawal. Lorazepam: labeler Clinical Solutions Wholesale, LLC; opioids can cause respiratory depression; warnings about abuse, addiction, dependence and withdrawal.',
    20: 'Lisinopril: without diuretics: 10 mg daily; with diuretics: 5 mg daily. The fetal toxicity warning says to discontinue when pregnancy is detected.',
}


def steps(number):
    paths=['/']
    if number in [4,6,9,16,20]:
        paths.append({4:'/drug_information.html?letter=L',6:'/conditions/diabetes',9:'/drug-classes/statins',16:'/drug-classes/benzodiazepines',20:'/conditions/hypertension'}[number])
    if number==3:
        paths.extend(['/pill-identifier?imprint=I-2','/pill-identifier?imprint=IP+466'])
    for slug in r.LABELS[number]:
        paths.extend(['/official-labels',f'/{slug}/official-label'])
    return [dict(url=ROOT+path,action='done' if i==len(paths)-1 else 'click',params={'index':1}) for i,path in enumerate(paths)]


def semantics(number, answer, snapshot, path_steps=None):
    judge=v.Judge(f'Drugs.com--{number}')
    trajectory={'final_answer':answer,'steps':path_steps or steps(number)}
    for step in trajectory['steps']:
        step['action_result']={'success':True}
    visits=[]
    from urllib.parse import urlsplit,parse_qsl
    for i,step in enumerate(trajectory['steps']):
        url=urlsplit(step['url']);visits.append(v.Visit(i,url.path,tuple(parse_qsl(url.query))))
    source=v.Snapshot(str(snapshot))
    try:r.verify_revised_task(number,judge,trajectory,visits,source)
    finally:source.close()
    return judge


@pytest.mark.parametrize('number', sorted(ANSWERS))
def test_current_revised_entrypoints(number,snapshots,tmp_path):
    run=make_run(tmp_path,number,snapshots[0],answer=ANSWERS[number],steps=steps(number))
    p=subprocess.run([PYTHON,str(VERIFY/f'verify_revised_{number}.py'),'--run_dir',str(run),'--initial_db',str(snapshots[0]),'--after_db',str(snapshots[1])],capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr


@pytest.mark.parametrize('number', sorted(ANSWERS))
def test_correct_facts_without_source_page_fail(number,snapshots):
    bad=steps(number)
    for step in bad:
        if '/official-label' in step['url']:step['url']=ROOT+'/'
    assert not semantics(number,ANSWERS[number],snapshots[0],bad).ok


@pytest.mark.parametrize('number,old,new', [
    (0,'every 4-6 hours','every 8-12 hours'),(0,'maximum 6 tablets','maximum 3 tablets'),
    (1,'lactic acidosis','thyroid C-cell tumors'),(1,'subcutaneous','oral'),
    (3,'800 mg','200 mg'),(3,'cannot identify','can identify'),
    (4,'2025-01-02','2026-09-10'),(6,'Ajanta Pharma USA Inc.','Viatris Specialty LLC'),
    (7,'in humans is unknown','in humans is proven'),(7,'do not crush','may crush'),
    (7,'in humans is unknown','in humans is not unknown'),
    (9,'effective 2024-04-15','effective 2026-07-15'),
    (11,'September 17, 2026','September 15, 2026'),
    (12,'10 mg','25 mg'),(12,'not pill photographs','pill photographs'),
    (16,'respiratory depression','stomach pain'),(20,'without diuretics: 10 mg','without diuretics: 5 mg'),
    (20,'with diuretics: 5 mg','with diuretics: 10 mg'),
    (20,'when pregnancy is detected','when pregnancy ends'),
])
def test_wrong_swapped_and_negated_facts_fail(number,old,new,snapshots):
    result=semantics(number,ANSWERS[number].replace(old,new),snapshots[0])
    assert not result.ok,result.evidence


@pytest.mark.parametrize('answer',[
    'Ibuprofen: interval 4 to 6 hours; do not exceed 6 tablets in 24 hours. Naproxen: interval 8 to 12 hours; do not exceed 3 tablets in 24 hours.',
    '| Drug | Interval | Maximum |\n|---|---|---|\n| Ibuprofen | every 4-6 hours | maximum 6 tablets in 24 hours |\n| Naproxen | every 8-12 hours | maximum 3 tablets in 24 hours |',
    '- Ibuprofen: every 4-6 hours; maximum 6 tablets in 24 hours.\n- Naproxen: every 8-12 hours; maximum 3 tablets in 24 hours.',
])
def test_prose_table_and_bullet_comparisons(answer,snapshots):
    result=semantics(0,answer,snapshots[0])
    assert result.ok,result.evidence


def test_uncertainty_in_one_drug_does_not_negate_next_drug(snapshots):
    answer=ANSWERS[7].replace('in humans is unknown','in humans is not established')
    result=semantics(7,answer,snapshots[0])
    assert result.ok,result.evidence
