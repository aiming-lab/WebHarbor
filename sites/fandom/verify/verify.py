"""Offline reviewer grader: evidence, task-specific claims, and exact DB deltas.

Language coverage is finite. No external calls or mutable live database fallback.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit, unquote, parse_qsl
from PIL import Image


def norm(value):
    from decimal import Decimal
    text=re.sub(r'(?<=\d),(?=\d)', '', str(value))
    def currency(m):
        scales={'k':1000,'thousand':1000,'m':1000000,'million':1000000,'billion':1000000000}
        amount=Decimal(m[1])*scales.get((m[2] or '').lower(),1)
        return '$'+format(amount.normalize(),'f')+' '
    value=re.sub(r'\$\s*([0-9]+(?:\.[0-9]+)?)\s*(?:(thousand|million|billion|k|m)\b)?',currency,text,flags=re.I)
    return re.sub(r'\s+', ' ', re.sub(r'(?<=\d),(?=\d)', '', str(value)).casefold().replace('’', "'").replace('–', '-').replace('—', '-')).strip()


def database(path):
    if not path.is_file():
        raise ValueError('Missing saved database: ' + path.name)
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as c:
        c.row_factory = sqlite3.Row
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result = {}
        for table in tables:
            cols = c.execute(f'PRAGMA table_info("{table}")').fetchall()
            keys = [r[1] for r in sorted(cols,key=lambda r:r[5]) if r[5]]
            rows = [dict(r) for r in c.execute(f'SELECT * FROM "{table}"')]
            result[table] = {json.dumps([r[k] for k in keys],sort_keys=True):r for r in rows}
        return result


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def matches(value, expected):
    if not isinstance(expected,dict):
        if isinstance(value,str) and isinstance(expected,str):
            try:
                return json.loads(value)==json.loads(expected)
            except (ValueError,TypeError):
                return norm(value)==norm(expected)
        return value == expected
    if 'regex' in expected:
        return re.fullmatch(expected['regex'],str(value),re.I|re.S) is not None
    if 'contains' in expected:
        text=norm(value)
        return all(re.search(p,text,re.I) for p in expected['contains']) and not re.search(r'\b(?:do not|don.t|never|cancel|delete)\b',text)
    if 'json' in expected:
        try:
            return json.loads(value)==expected['json']
        except (ValueError,TypeError):
            return False
    if 'query' in expected:
        return dict((k,v) for k,v in parse_qsl(value) if v and k!='sort')==expected['query']
    if 'nonempty' in expected:
        return isinstance(value,str) and len(value.strip())>=expected['nonempty']
    if 'number' in expected:
        try:return float(value)==expected['number']
        except (ValueError,TypeError):return False
    return False


def check_state(initial, after, spec):
    if digest(initial)!=spec['initial_digest']:
        raise ValueError('Initial snapshot does not match the reviewed fixture')
    if initial.keys()!=after.keys():
        raise ValueError('Database table set changed')
    rules=spec.get('state',{})
    for table,old in initial.items():
        new=after[table];rule=rules.get(table,{})
        if old.keys()-new.keys():raise ValueError('Existing rows removed from '+table)
        added=[r for k,r in new.items() if k not in old]
        expects=rule.get('added',[])
        if len(added)!=len(expects):raise ValueError('Unexpected addition count in '+table)
        for expected in expects:
            candidates=[r for r in added if set(r)==set(expected) and all(matches(r[k],v) for k,v in expected.items())]
            if not candidates:raise ValueError('Incorrect new row in '+table)
            added.remove(candidates[0])
        updates=rule.get('updated',{})
        for key,before in old.items():
            current=new[key];allow=updates.get(key,{})
            for col,value in current.items():
                if col in allow:
                    if not matches(value,allow[col]):raise ValueError(f'Wrong requested update in {table}.{col}')
                    if col=='updated_at' and value==before[col]:raise ValueError('Update timestamp did not advance')
                elif col=='view_count' and table in spec.get('view_tables',[]):
                    if not isinstance(value,int) or value<before[col]:raise ValueError('Invalid view counter')
                elif value!=before[col]:raise ValueError(f'Unrequested change in {table}.{col}')
    # Ensure linked duplicated message copies agree, not just independently match words.
    if spec.get('portal_message'):
        a=[r for k,r in after['portal_message'].items() if k not in initial['portal_message']][0]
        b=[r for k,r in after['provider_message'].items() if k not in initial['provider_message']][0]
        if a['body']!=b['body'] or a['subject']!=b['subject']:raise ValueError('Portal message copies disagree')
    if spec.get('password'):
        from werkzeug.security import check_password_hash
        table='users';rows=[r for k,r in after[table].items() if k not in initial[table]]
        if len(rows)!=1:raise ValueError('Registration row missing')
        field=next(k for k in rows[0] if 'password' in k)
        encoded=rows[0][field]
        if encoded.startswith(('$2a$', '$2b$', '$2y$')):
            import bcrypt
            valid=bcrypt.checkpw(spec['password'].encode(),encoded.encode())
        else:
            valid=check_password_hash(encoded,spec['password'])
        if not valid:raise ValueError('Registered password is incorrect')


def check_claims(answer, claims):
    # Each claim is scoped to a clause/line; entities, properties and values must
    # occur together. Patterns describe allowed paraphrases, not required output syntax.
    blocks=[norm(s) for s in re.split(r'\n+',answer) if s.strip()]
    entity_patterns=list(dict.fromkeys(c['entity'] for c in claims if c.get('entity')))
    for claim in claims:
        valid=[]
        candidates=blocks
        if claim.get('entity'):
            candidates=[]
            other=[p for p in entity_patterns if p!=claim['entity']]
            for block in blocks:
                for start in re.finditer(claim['entity'],block,re.I):
                    tail=block[start.start():]
                    stop=re.search('|'.join(other),tail,re.I) if other else None
                    candidates.append(tail[:stop.start()] if stop else tail)
        for block in candidates:
            if all(re.search(p,block,re.I) for p in claim['all']):
                if re.match(r'^(?:not true|false|incorrect|wrong|not the case)\b',block):
                    raise ValueError('Negated claim: '+claim['label'])
                if any(re.search(p,block,re.I) for p in claim.get('reject',[])):
                    raise ValueError('Contradictory claim: '+claim['label'])
                valid.append(block)
        if not valid:raise ValueError('Missing or incorrect claim: '+claim['label'])
        if claim.get('scope'):
            for block in blocks:
                if re.search(claim['scope'],block,re.I) and re.search(r'^(?:not true|false|incorrect|wrong|not the case)\b|\b(?:is not|was not|isn.t|wasn.t|never)\b',block) and all(re.search(p,block,re.I) for p in claim['all']):
                    raise ValueError('Negated claim: '+claim['label'])


def verify(run_dir):
    run=Path(run_dir).resolve();traj=json.loads((run/'trajectory.json').read_text())
    specs=json.loads(Path(__file__).with_name('contract.json').read_text())
    task=traj.get('task_id',traj.get('id'));spec=specs[task]
    if not traj.get('terminated') or not traj.get('final_answer','').strip():raise ValueError('Unfinished browser attempt')
    if traj.get('task',traj.get('ques'))!=spec['task']:raise ValueError('Task wording does not match current contract')
    steps=traj.get('steps',[]);urls=[];actions=[];seen=set()
    for step in steps:
        url=step.get('url_after',step.get('url',''));parts=urlsplit(url)
        if parts.scheme not in ['http','https'] or not parts.hostname:raise ValueError('Invalid browser URL')
        urls.append(unquote(parts.path)+('?' + parts.query if parts.query else ''));actions.append(step.get('action'))
        name=step.get('screenshot_after',step.get('screenshot',''))
        if not name:raise ValueError('Screenshot reference missing')
        path=(run/'screenshots'/Path(name).name).resolve()
        if not path.is_relative_to(run):raise ValueError('Screenshot outside run')
        if path not in seen:
            with Image.open(path) as im:
                im.load()
                if im.width<300 or im.height<200:raise ValueError('Invalid screenshot size')
            seen.add(path)
    if not any(a in ['click','fill','type','select'] for a in actions):raise ValueError('No browser interaction evidence')
    for pattern in spec['paths']:
        if not any(re.search(pattern,u) for u in urls):raise ValueError('Required page evidence missing: '+pattern)
    if spec.get('ics'):
        text=(run/'event.ics').read_text()
        for line in spec['ics']:
            if line not in text:raise ValueError('Incorrect downloaded calendar: '+line)
    initial=database(run/'initial.db');after=database(run/'after.db');check_state(initial,after,spec)
    answer=traj['final_answer'];check_claims(' '.join(answer.splitlines()) if spec.get('join_answer_lines') else answer,spec['claims'])
    for table,field in spec.get('answer_state',[]):
        added=[r for k,r in after[table].items() if k not in initial[table]]
        if len(added)!=1 or str(added[0][field]).casefold() not in answer.casefold():raise ValueError('Answer does not match saved confirmation')
    return {'task_id':task,'pass':True,'reason':'Required browser evidence, answer claims and precise saved-state checks passed.','evidence':[f'{len(seen)} decoded screenshots',f'{len(spec["claims"])} answer claims','Saved initial/final database comparison']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run_dir',required=True);args=parser.parse_args()
    try:result=verify(args.run_dir)
    except Exception as exc:result={'task_id':None,'pass':False,'reason':str(exc),'evidence':[]}
    print(json.dumps(result));sys.exit(0 if result['pass'] else 1)
