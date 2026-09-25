"""Grade screenshot-backed navigation and exact saved-state changes; no LLM calls."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent.name
CONTRACTS = json.loads((ROOT / 'contracts.json').read_text())
class Failure(Exception): pass
class InfrastructureError(Exception): pass

def require(ok, reason):
    if not ok: raise Failure(reason)

def read_db(path):
    path = Path(path).resolve(strict=True)
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
        raise InfrastructureError('Invalid SQLite snapshot')
    tables = sorted(r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    state = {t: [dict(r) for r in db.execute(f'SELECT * FROM "{t}" ORDER BY id')] for t in tables}
    return db, state

def fingerprint(state):
    return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def same(a,b):
    return Counter(json.dumps(r,sort_keys=True) for r in a) == Counter(json.dumps(r,sort_keys=True) for r in b)

def loopback(host):
    if host == 'localhost': return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False

def proof_urls(traj, directory):
    start = urlparse(traj.get('start_url',''))
    require(start.scheme in {'http','https'} and loopback(start.hostname or ''), 'Start URL must identify the local mirror')
    require(traj.get('steps'), 'No browser steps')
    urls=[]
    for step in traj['steps']:
        if (step.get('action_result') or {}).get('error'): continue
        names=[step.get(k) for k in ('screenshot_before','screenshot_after') if step.get(k)]
        require(names,'Each evidence step must reference screenshots')
        for name in names:
            candidate=(directory/'screenshots'/Path(name).name).resolve()
            require(candidate.is_relative_to(directory.resolve()),'Screenshot escapes evidence directory')
            try: header=candidate.read_bytes()[:24]
            except OSError: raise InfrastructureError('Missing referenced screenshot')
            require(header[:8]==b'\x89PNG\r\n\x1a\n' and len(header)==24 and int.from_bytes(header[16:20],'big')>=300 and int.from_bytes(header[20:24],'big')>=180,'Invalid screenshot')
        for key in ['url_before','url','url_after']:
            value=step.get(key,'');u=urlparse(value)
            if u.scheme in {'http','https'} and loopback(u.hostname or '') and u.port==start.port:
                urls.append(value)
    require(urls,'No same-site screenshot-backed URLs')
    return urls

def evaluate(number,directory,initial,after):
    task=CONTRACTS[number];traj=json.loads((directory/'trajectory.json').read_text())
    require(traj.get('task_id')==task['id'],'Task ID does not match verifier')
    require(str(traj.get('final_answer','')).strip(),'Missing final completion response')
    urls=proof_urls(traj,directory)
    paths=[urlparse(u).path.rstrip('/') or '/' for u in urls]
    require('/login' in paths,'Missing sign-in evidence')
    typed=[]
    for s in traj['steps']:
        if s.get('action') in {'type','fill','input_text'}:
            params=s.get('params') or {};typed.extend(str(params.get(k,'')) for k in ['text','value'])
    require(task['user'] in typed,'Missing sign-in for the requested account')
    a,A=read_db(initial);b,B=read_db(after)
    try:
        require(set(A)==set(B),'Database tables changed')
        fixture=json.loads((ROOT/'fixture.json').read_text())
        require(fingerprint(A)==fixture['logical_sha256'],'Initial fixture differs from the reviewed seed')
        user=next(r['id'] for r in A['users'] if r['email']==task['user'])
        expected={t:[dict(r) for r in rows] for t,rows in A.items()}
        memberships={};new_comments=[];chosen_videos=set();changed=[]
        for op in task['operations']:
            ids=[r[0] for r in a.execute(op['query'],{'user':user})]
            require(ids,'Task candidate selection returned no results')
            table=op['table'];field='channel_id' if table=='subscriptions' else 'location_id' if table=='saved_locations' else 'video_id'
            if table=='users':
                value=op.get('value',ids[0]);next(r for r in expected['users'] if r['id']==user)[op['field']]=value;changed.append(f"users.{op['field']}");continue
            if SITE=='youtube' and table!='subscriptions':chosen_videos.update(ids)
            if table=='comments':
                for item in ids:
                    new_comments.append({'user_id':user,'video_id':item,'body':op['body'],'like_count':1})
                    next(r for r in expected['videos'] if r['id']==item)['comment_count']+=1
                changed.append('comments');continue
            if table not in memberships:
                memberships[table]={'field':field,'pairs':{(r['user_id'],r[field]) for r in A[table]}}
            pairs=memberships[table]['pairs']
            for item in ids:
                pair=(user,item)
                if op['operation']=='add':
                    require(pair not in pairs,'Task addition is already satisfied in initial state');pairs.add(pair);delta=1
                else:
                    require(pair in pairs,'Task removal is absent in initial state');pairs.remove(pair);delta=-1
                if table=='user_likes':next(r for r in expected['videos'] if r['id']==item)['likes']+=delta
            changed.append(table)
        for table,spec in memberships.items():
            field=spec['field'];pairs=spec['pairs'];rows=B[table]
            require(len(rows)==len(pairs) and {(r['user_id'],r[field]) for r in rows}==pairs,f'Wrong {table} memberships, owner or quantity')
            old={(r['user_id'],r[field]):r for r in A[table]}
            for r in rows:
                key=(r['user_id'],r[field])
                if key in old:require(r==old[key],f'Existing {table} row modified')
                else:require(r['id'] not in {x['id'] for x in A[table]},f'New {table} row reuses an existing identity')
            expected[table]=rows
        if new_comments:
            old={r['id']:r for r in A['comments']};now={r['id']:r for r in B['comments']}
            require(all(now.get(k)==v for k,v in old.items()),'Prior comment changed or removed')
            new=[{k:v for k,v in r.items() if k not in {'id','created_at'}} for r in B['comments'] if r['id'] not in old]
            require(same(new,new_comments),'Wrong comment author, video, body or count');expected['comments']=B['comments']
        if SITE=='youtube':
            old={r['id']:r for r in A['watch_history']};now={r['id']:r for r in B['watch_history']}
            require(all(now.get(k)==v for k,v in old.items()),'Prior watch history changed')
            pairs={(r['user_id'],r['video_id']) for r in B['watch_history']}
            require(len(pairs)==len(B['watch_history']),'Duplicate watch history')
            slugs={r['id']:r['slug'] for r in A['videos']}
            for r in B['watch_history']:
                if r['id'] not in old:require(r['user_id']==user and '/watch/'+slugs[r['video_id']] in paths,'History unrelated to the task account or visited video')
            expected['watch_history']=B['watch_history']
            for vid in chosen_videos:require('/watch/'+slugs[vid] in paths,'Selected video was not opened')
        for table in expected:require(same(expected[table],B[table]),f'Unexpected changes to {table}')
        for path in task['paths']:require(path in paths,'Missing required page: '+path)
        for path,key,term in task['queries']:
            require(any((urlparse(u).path.rstrip('/') or '/')==path and term.casefold() in parse_qs(urlparse(u).query).get(key,[''])[0].casefold() for u in urls),'Missing requested category/filter/search evidence')
        # Confirmation must occur after source research, not just at the beginning.
        confirm=task['confirm'];last_confirm=max((i for i,p in enumerate(paths) if p==confirm),default=-1)
        require(last_confirm>=0 and all(any(p==need for p in paths[:last_confirm+1]) for need in task['paths']),'Missing confirmation after research')
        final=urlparse(traj.get('final_url',''));require((final.path.rstrip('/') or '/')==confirm and loopback(final.hostname or '') and final.port==urlparse(traj['start_url']).port,'Finish on the requested confirmation page')
        return {'task_id':task['id'],'pass':True,'reason':'Required browser evidence and exact state changes verified','evidence':['Account: '+task['user'],'State: '+', '.join(sorted(set(changed))),'Unrelated rows preserved; reviewed initial fixture matched']}
    finally:a.close();b.close()

def main(number):
    parser=argparse.ArgumentParser();parser.add_argument('--run_dir',required=True);parser.add_argument('--initial_db');parser.add_argument('--after_db');parser.add_argument('--container',default=os.environ.get('WH_CONTAINER','wh-review'));args=parser.parse_args()
    task=CONTRACTS[number];verdict={};code=1
    try:
        directory=Path(args.run_dir).resolve(strict=True)
        initial=Path(args.initial_db) if args.initial_db else directory/'initial.db';after=Path(args.after_db) if args.after_db else directory/'after.db'
        if bool(args.initial_db)!=bool(args.after_db) or initial.exists()!=after.exists():raise InfrastructureError('Provide both initial and final snapshots; partial pairs never fall back to a live DB')
        with tempfile.TemporaryDirectory(prefix=SITE+'-verify-') as temp:
            if not initial.exists():
                # Explicit container fallback is used only when neither saved snapshot exists.
                for kind,name in [('instance_seed','initial.db'),('instance','after.db')]:
                    target=Path(temp)/name;source=f'/opt/WebSyn/{SITE}/{kind}/{SITE}.db'
                    program='import sqlite3,sys; a=sqlite3.connect("file:'+source+'?mode=ro",uri=True); b=sqlite3.connect("/tmp/'+SITE+'-grading.db"); a.backup(b); b.close()'
                    subprocess.run(['docker','exec',args.container,'python3','-c',program],check=True,capture_output=True)
                    subprocess.run(['docker','cp',args.container+':/tmp/'+SITE+'-grading.db',str(target)],check=True,capture_output=True)
                initial=Path(temp)/'initial.db';after=Path(temp)/'after.db'
            verdict=evaluate(number,directory,initial,after);code=0
    except Failure as e:verdict={'task_id':task['id'],'pass':False,'reason':str(e),'evidence':[]}
    except Exception as e:verdict={'task_id':task['id'],'pass':False,'reason':'Infrastructure error: '+str(e),'evidence':[],'error_type':'infrastructure'};code=2
    print(json.dumps(verdict));raise SystemExit(code)
