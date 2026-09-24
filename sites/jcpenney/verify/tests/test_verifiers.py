"""Synthetic verifier controls, separate from real browser evidence.

Fixtures retain reviewed answers, visited routes and exact table outcomes. Tiny
screenshots are explicitly synthetic; these tests do not establish UI feasibility.
"""
import json,re,shutil,sqlite3,subprocess,sys
from pathlib import Path
import pytest
from PIL import Image

VERIFY=Path(__file__).resolve().parents[1]
SITE=VERIFY.parent
SEED=SITE/'instance_seed'/f'{SITE.name}.db'
CASES=sorted((VERIFY/'tests/fixtures').glob('*.json'),key=lambda p:int(p.stem))


def build(tmp_path, fixture):
    f=json.loads(fixture.read_text());t=f['trajectory']
    tmp_path.mkdir(parents=True,exist_ok=True)
    for name in ['initial.db','after.db']:shutil.copy2(SEED,tmp_path/name)
    with sqlite3.connect(tmp_path/'after.db') as db:
        for table, rows in f['changed_tables'].items():
            db.execute(f'DELETE FROM "{table}"')
            if rows:db.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in rows[0])})',rows)
    (tmp_path/'screenshots').mkdir();Image.new('RGB',(4,4),'white').save(tmp_path/'screenshots/fixture.png')
    return t,f['changed_tables']


def grade(path,t,index):
    (path/'trajectory.json').write_text(json.dumps(t))
    p=subprocess.run([sys.executable,str(VERIFY/f'verify_{index}.py'),'--run_dir',str(path),'--no_llm','True'],capture_output=True,text=True)
    assert p.stdout.strip(),p.stderr
    return json.loads(p.stdout)


@pytest.mark.parametrize('fixture',CASES,ids=lambda p:p.stem)
@pytest.mark.parametrize('control',['honest','bullets','currency-spacing','empty-answer','wrong-answer','stale-prompt','unfinished','homepage-only','unrelated-user-change','state-noop','offsite','missing-screenshot'])
def test_outcome_contract(tmp_path,fixture,control):
    t,changed=build(tmp_path,fixture);expected=control in ['honest','bullets','currency-spacing']
    if control=='bullets':t['final_answer']='\n'.join('- '+x for x in t['final_answer'].splitlines())
    if control=='currency-spacing':t['final_answer']=t['final_answer'].replace('$','$ ')
    if control=='empty-answer':t['final_answer']=''
    if control=='wrong-answer':t['final_answer']='I could not finish the requested task.'
    if control=='stale-prompt':t['task']='Superseded instruction'
    if control=='unfinished':t['terminated']=False
    if control=='homepage-only':
        for step in t['steps']:
            for key in ['url','url_before','url_after']:step[key]=t['start_url']
    if control=='unrelated-user-change':
        with sqlite3.connect(tmp_path/'after.db') as db:db.execute("UPDATE users SET email='unrelated-change@example.com' WHERE id=4")
    if control=='state-noop':
        if not changed:expected=True
        else:shutil.copy2(tmp_path/'initial.db',tmp_path/'after.db')
    if control=='offsite':t['steps'][0]['url']='https://example.org/'
    if control=='missing-screenshot':(tmp_path/'screenshots/fixture.png').unlink()
    result=grade(tmp_path,t,fixture.stem)
    assert result['pass'] is expected,(control,result['reason'],result.get('evidence'))


@pytest.mark.parametrize('fixture',CASES,ids=lambda p:p.stem)
def test_previous_orders_and_foreign_keys_preserved(tmp_path,fixture):
    t,changed=build(tmp_path,fixture)
    if 'orders' not in changed:return
    for control in ['prior-order','line-owner','quantity']:
        path=tmp_path/control;t,_=build(path,fixture)
        with sqlite3.connect(path/'after.db') as db:
            if control=='prior-order':db.execute('UPDATE orders SET total=total+1 WHERE id=1')
            elif control=='line-owner':db.execute('UPDATE order_items SET order_id=1 WHERE id=(SELECT MAX(id) FROM order_items)')
            else:db.execute('UPDATE order_items SET quantity=quantity+1 WHERE id=(SELECT MAX(id) FROM order_items)')
        result=grade(path,t,fixture.stem)
        assert result['pass'] is False,(control,result['reason'])


@pytest.mark.parametrize('fixture',CASES,ids=lambda p:p.stem)
@pytest.mark.parametrize('control',['wrong-prices','negated-prices','wrong-price-plus-reference'])
def test_price_polarity_and_reference_numbers(tmp_path,fixture,control):
    t,_=build(tmp_path,fixture)
    if '$' not in t['final_answer']:return
    if control=='wrong-prices':t['final_answer']=re.sub(r'\$\s*([\d,]+(?:\.\d+)?)',lambda m:'$'+str(float(m[1].replace(',',''))+1),t['final_answer'])
    elif control=='negated-prices':t['final_answer']=t['final_answer'].replace('$','not $')
    else:t['final_answer']=re.sub(r'\$\s*([\d,]+(?:\.\d+)?)',lambda m:'$999999 (reference '+m[0]+')',t['final_answer'])
    result=grade(tmp_path,t,fixture.stem)
    assert result['pass'] is False,(control,result['reason'])
