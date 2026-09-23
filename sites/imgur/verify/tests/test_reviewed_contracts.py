"""Current task contracts; synthetic controls are separate from browser evidence."""
import json
import sqlite3
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import reviewed
from verify_lib import Judge,SEED_USERS
from _support import build_run,copy_db,run_verifier
SITE=Path(__file__).resolve().parents[2].name
NAME='Google Shopping' if SITE=='google_shopping' else 'Imgur'


def fixture(tmp_path,key):
    c=reviewed.CONFIG[key];email=c.get('email');who=(email,SEED_USERS[email][1]) if email else None
    steps=[(p,'click',{}) for p in c['paths']] or [('/search?q=trench','click',{})]
    run=build_run(tmp_path/'run',f'{NAME}--{key}',steps,c['answer'],login=who)
    initial=copy_db(tmp_path/'initial.db');after=copy_db(tmp_path/'after.db')
    with sqlite3.connect(after) as db:
        if SITE=='google_shopping':
            uid=SEED_USERS[email][0] if email else None
            for table,ids in c['remove'].items():
                for pid in ids:db.execute(f'DELETE FROM {table} WHERE user_id=? AND product_id=?',(uid,pid))
            for table,ids in c['add'].items():
                for pid in ids:db.execute(f'INSERT INTO {table}(user_id,product_id,created_at) VALUES(?,?,?)',(uid,pid,'2026-09-23 00:00:00'))
        elif c.get('state'):
            t=c['state'];uid=c['uid']
            if t['kind']=='favorite':db.execute('INSERT INTO favorites(user_id,post_id,created_at) VALUES(?,?,?)',(uid,t['post'],'2026-09-23 00:00:00'))
            if t['kind']=='follow':db.execute('INSERT INTO follow_user(follower_id,followee_id) VALUES(?,?)',(uid,t['target']))
            if t['kind']=='tag':
                for tag in t['targets']:db.execute('INSERT INTO follow_tag(user_id,tag_name) VALUES(?,?)',(uid,tag))
            if t['kind']=='reply':
                db.execute('INSERT INTO comments(post_id,parent_id,author_id,text,upvote_count,downvote_count,point_count,platform,created_at) VALUES(?,?,?,?,0,0,0,?,?)',(t['post'],t['parent'],uid,t['text'],'web','2026-09-23 00:00:00'))
                db.execute('UPDATE posts SET comment_count=comment_count+1 WHERE id=?',(t['post'],))
    return run,initial,after


@pytest.mark.parametrize('key',reviewed.CONFIG)
def test_current_contract_accepts_complete_result(tmp_path,key):
    run,initial,after=fixture(tmp_path,key)
    result=run_verifier(int(key),run,initial,after)
    assert result['pass'],result


@pytest.mark.parametrize('key',reviewed.CONFIG)
def test_current_contract_rejects_wrong_answer(tmp_path,key):
    run,initial,after=fixture(tmp_path,key)
    p=run/'trajectory.json';t=json.loads(p.read_text());t['final_answer']='I could not establish any of the requested facts.';p.write_text(json.dumps(t))
    result=run_verifier(int(key),run,initial,after)
    assert not result['pass'] and not result.get('infra_error'),result


@pytest.mark.parametrize('key',reviewed.CONFIG)
def test_current_contract_rejects_unrelated_write(tmp_path,key):
    run,initial,after=fixture(tmp_path,key)
    with sqlite3.connect(after) as db:
        field='display_name' if SITE=='google_shopping' else 'bio'
        db.execute(f"UPDATE users SET {field}='unrequested change' WHERE email='bob.c@test.com'")
    result=run_verifier(int(key),run,initial,after)
    assert not result['pass'],result


@pytest.mark.parametrize('mutation',['stale_prompt','wrong_port','missing_screenshot'])
def test_package_guards(tmp_path,mutation):
    key=next(iter(reviewed.CONFIG));run,initial,after=fixture(tmp_path,key)
    p=run/'trajectory.json';t=json.loads(p.read_text())
    if mutation=='stale_prompt':t['task']='An obsolete instruction'
    if mutation=='wrong_port':t['steps'][0]['url']='http://localhost:49999/'
    if mutation=='missing_screenshot':t['steps'][0]['screenshot_after']='missing.png'
    p.write_text(json.dumps(t));result=run_verifier(int(key),run,initial,after)
    assert not result['pass'],result


@pytest.mark.parametrize('separator',['; ', ', and ', '\n'])
def test_multi_entity_values_do_not_cross_bind(separator):
    if SITE == 'google_shopping':
        key='0'
        correct=separator.join(['Beauty And Brains: plastic square, $3.98',
            'Playing It Smart: metal aviator, $2.98, my recommendation',
            'Office Siren: plastic square, $5.99'])
        wrong=correct.replace('$3.98','SWAP').replace('$2.98','$3.98').replace('SWAP','$2.98')
    else:
        key='14'
        correct=separator.join(['Beach time by ginalynn8942: 718 points',
            'OnlyBiscuits by PushPullMagnet: 587 points', 'Score difference: 131 points'])
        wrong=correct.replace('718','SWAP').replace('587','718').replace('SWAP','587')
    for answer,expected in [(correct,True),(wrong,False)]:
        judge=Judge(NAME+'--'+key,True)
        reviewed.check_facts(judge,answer,reviewed.CONFIG[key]['facts'])
        assert judge.ok == expected, judge.evidence
