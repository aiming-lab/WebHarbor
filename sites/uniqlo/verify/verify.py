#!/usr/bin/env python3
"""Primary deterministic grader; expectations are reviewer-only contracts.json."""
import argparse
import copy
import hashlib
import json
import math
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent

def load_db(path):
    if not path.is_file(): raise ValueError(f'Missing database evidence: {path.name}')
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok': raise ValueError('Corrupt database')
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: sorted([dict(r) for r in con.execute('SELECT * FROM "'+t+'"')], key=lambda r: json.dumps(r,sort_keys=True)) for t in tables}

def canonical(data):
    return json.dumps({t: sorted(rows, key=lambda r: json.dumps(r,sort_keys=True)) for t,rows in data.items()}, sort_keys=True,ensure_ascii=False,separators=(',',':'))

def fingerprint(data): return hashlib.sha256(canonical(data).encode()).hexdigest()

def norm(text):
    text=unicodedata.normalize('NFKC',text).replace('®','').replace('’',"'").replace('–','-').replace('—','-')
    text=re.sub(r'(?<=\d),(?=\d)', '', text)
    return re.sub(r'\s+',' ',text).strip()

def regex(pattern): return pattern.replace('®','').replace('’',"'").replace(',', '[,]?')

def check_facts(answer, facts):
    text=norm(answer)
    if facts and not text: raise ValueError('Missing factual answer')
    # Attribute each span to its entity, even when multiple entities share a line.
    matches=[]
    for idx,f in enumerate(facts):
        for m in re.finditer(regex(f['entity']),text,re.I): matches.append((m.start(),m.end(),idx))
    matches.sort(key=lambda m:(m[0],-(m[1]-m[0])))
    filtered=[]
    for m in matches:
        if not filtered or m[0]>=filtered[-1][1]: filtered.append(m)
    scopes={i:[] for i in range(len(facts))}
    for pos,(start,end,idx) in enumerate(filtered): scopes[idx].append(text[start:filtered[pos+1][0] if pos+1<len(filtered) else len(text)])
    for idx,f in enumerate(facts):
        scoped=' '.join(scopes[idx])
        if not scoped: raise ValueError('Missing entity: '+f['entity'])
        for pat in f['patterns']:
            hits=list(re.finditer(regex(pat),scoped,re.I))
            if not hits: raise ValueError('Missing or incorrect entity-bound fact: '+f['entity']+' / '+pat)
            # A negated correct phrase must not pass as an affirmative fact.
            if all(re.search(r"\b(?:not|isn't|is not|isn’t|never|incorrect|wrong|instead of)\s*(?:\w+\s+){0,8}$",scoped[max(0,m.start()-90):m.start()],re.I) for m in hits):
                raise ValueError('Negated required fact: '+f['entity'])
        if f.get('sections'):
            markers = list(re.finditer(r"\b(pros?|advantages?|strengths?|benefits?|cons?|drawbacks?|downsides?|limitations?)\s*(?::|are\b|include\b)", scoped, re.I))
            sections = {'pros': '', 'cons': ''}
            for j, marker in enumerate(markers):
                key = 'pros' if re.match(r'pro|advantage|strength|benefit', marker[1], re.I) else 'cons'
                sections[key] += scoped[marker.end():markers[j+1].start() if j+1<len(markers) else len(scoped)]
            for key, values in f['sections'].items():
                if any(norm(value).casefold() not in sections[key].casefold() for value in values):
                    raise ValueError('Incorrectly attributed advantages/disadvantages')
        for pat in f.get('forbid',[]):
            if re.search(regex(pat),scoped,re.I): raise ValueError('Contradictory fact: '+f['entity'])
        # Reject wrong monetary claims even when a correct amount is appended as a reference.
        expected=set()
        for pat in f['patterns']:
            for x in re.findall(r'\\\$\\s\*([\d]+(?:\\\.[\d]+)?)',pat): expected.add(float(x.replace('\\','')))
        if expected:
            amounts={float(x) for x in re.findall(r'\$\s*(\d+(?:\.\d+)?)',scoped)}
            if amounts-expected: raise ValueError('Unexpected monetary amount for '+f['entity'])
    return [f"Verified {len(facts)} entity-bound factual groups"]

def check_state(initial, final, state):
    restored=copy.deepcopy(final)
    def new_row(table,values,ignore):
        old={r['id']:r for r in initial[table]};new=[r for r in restored[table] if r['id'] not in old]
        if len(new)!=1: raise ValueError(f'Expected one new {table} row')
        row=new[0]
        if any(row.get(k)!=v for k,v in values.items()): raise ValueError(f'Wrong {table} owner/entity/values')
        if set(row)-set(values)-set(ignore): raise ValueError('Unchecked new-row fields')
        for field in ('created_at','saved_at','added_at'):
            if field in row and not row[field]: raise ValueError('Missing timestamp')
        restored[table].remove(row)
    if 'add' in state:
        c=state['add'];new_row(c['table'],c['values'],c['ignore'])
    if 'delete' in state:
        c=state['delete'];row=next(x for x in initial[c['table']] if x['id']==c['id'])
        if any(x['id']==c['id'] for x in final[c['table']]): raise ValueError('Requested item remains')
        restored[c['table']].append(row)
    if 'update' in state:
        c=state['update'];row=next(x for x in restored[c['table']] if x['id']==c['id']);before=next(x for x in initial[c['table']] if x['id']==c['id'])
        if any(row.get(k)!=v for k,v in c['values'].items()): raise ValueError('Requested status change missing')
        row.update({k:before[k] for k in c['values']})
    if 'review' in state:
        c=state['review'];new_row('reviews',c['values'],['id','created_at'])
        row=next(x for x in restored[c['table']] if x['id']==c['entity_id']);before=next(x for x in initial[c['table']] if x['id']==c['entity_id'])
        count=before['review_count']+1;rating=(before['rating']*before['review_count']+c['values']['rating'])/count
        if row['review_count']!=count or not math.isclose(row['rating'],rating,rel_tol=1e-10): raise ValueError('Incorrect review aggregate')
        row.update({k:before[k] for k in ['rating','review_count']})
    if canonical(restored)!=canonical(initial): raise ValueError('Unrequested changes or missing prior records')
    return ['Exact requested database delta; unrelated records preserved']

def verify(run_dir):
    traj=json.loads((run_dir/'trajectory.json').read_text());task_id=traj.get('task_id','');idx=task_id.rsplit('--',1)[-1]
    contracts=json.loads((HERE/'contracts.json').read_text());contract=contracts[idx]
    current=[json.loads(x) for x in (HERE.parent/'tasks.jsonl').read_text().splitlines()]
    task=next(x for x in current if x['id']==task_id)
    if traj.get('task')!=task['ques'] or task['ques']!=contract['prompt']: raise ValueError('Stale or mismatched task prompt')
    if not traj.get('terminated') or traj.get('termination_reason') not in ('agent_done','done','completed'): raise ValueError('Incomplete trajectory')
    steps=traj.get('steps',[])
    if not steps: raise ValueError('Empty trajectory')
    urls=[]
    for step in steps:
        for k in ['url','url_after']:
            if step.get(k): urls.append(urlsplit(step[k]).path)
        for key in ['screenshot_before','screenshot_after']:
            name=step.get(key)
            if not name: raise ValueError('Missing screenshot reference')
            p=(run_dir/'screenshots'/name).resolve()
            if not p.is_relative_to(run_dir.resolve()) or not p.is_file() or p.stat().st_size<100: raise ValueError('Missing screenshot evidence')
    for path in contract['paths']:
        if path not in urls: raise ValueError('Missing relevant page evidence: '+path)
    if contract.get('compare'):
        views=[x.get('observed_text','') for x in steps if urlsplit(x.get('url_after',x.get('url',''))).path=='/compare']
        if not any(all(name in text for name in contract['compare']) for text in views): raise ValueError('Both vehicles must be present in comparison')
    initial=load_db(run_dir/'initial.db');final=load_db(run_dir/'after.db')
    expected=(HERE/'fixture.sha256').read_text().strip()
    if fingerprint(initial)!=expected: raise ValueError('Initial snapshot does not match reviewed seed')
    evidence=check_state(initial,final,contract['state'])
    answer=traj.get('final_answer','')
    evidence+=check_facts(answer,contract['facts'])
    for pat in contract.get('answer_patterns',[]):
        if not re.search(pat,norm(answer),re.I): raise ValueError('Missing required comparison conclusion')
    for pat in contract.get('answer_forbidden',[]):
        if re.search(pat,norm(answer),re.I): raise ValueError('Contradictory comparison conclusion')
    return {'task_id':task_id,'pass':True,'reason':'Requested outcome, relevant page evidence and preserved state verified.','evidence':evidence}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run_dir',required=True);args=parser.parse_args();run=Path(args.run_dir)
    try: result=verify(run)
    except Exception as exc:
        try: task_id=json.loads((run/'trajectory.json').read_text()).get('task_id','')
        except Exception: task_id=''
        result={'task_id':task_id,'pass':False,'reason':str(exc),'evidence':[]}
    print(json.dumps(result));return 0 if result['pass'] else 1

if __name__=='__main__': sys.exit(main())
