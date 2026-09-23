"""Synthetic grading controls, not independent browser attempts."""
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from verify_lib import CONTRACTS, SITE, answer_ok, evaluate, navigation_ok, state_ok

ANSWERS=json.loads(Path(__file__).with_name('positive_answers.json').read_text())

def trajectory(index):
    c=CONTRACTS[index]; urls=['http://localhost:44818/']
    urls += ['http://localhost:44818/recipe/cookpad-'+str(i) for i in c['recipes']]
    nav=c['navigation']
    if nav:
        if ':' in nav:
            kind,token=nav.split(':'); urls.append(f'http://localhost:44818/{kind}?q={token}')
            if kind=='help': urls.append('http://localhost:44818/help/'+('shopping-list-overview' if index==10 else 'saving-recipes'))
        else: urls.append('http://localhost:44818'+nav)
    if index==5:urls.append('http://localhost:44818/category/desserts?max_time=15')
    if c['state']:
        urls.append('http://localhost:44818/'+{'list_new':'shopping-list','list_edit':'shopping-list','meal':'meal-plan','note':'recipe-box'}[c['state']['kind']])
    return dict(start_url=urls[0],final_answer=ANSWERS[index],steps=[dict(url=u) for u in urls])

def apply_expected(index,path):
    s=CONTRACTS[index]['state']
    if not s:return
    with sqlite3.connect(path) as c:
        if s['kind']=='list_new':
            items=list(dict.fromkeys(json.loads(c.execute('SELECT ingredients_json FROM recipe WHERE id=?',(s['recipe'],)).fetchone()[0])))
            if s.get('add'):items.append(s['add'])
            c.execute('INSERT INTO shopping_list(user_id,name,items_json,created_at) VALUES (?,?,?,?)',(s['user'],s['name'],json.dumps(items),'2026-09-18'))
        elif s['kind']=='list_edit':
            row=c.execute('SELECT id,items_json FROM shopping_list WHERE user_id=? AND name=?',(s['user'],s['name'])).fetchone()
            items=json.loads(row[1]);items.remove(s['remove']);items.append(s['add'])
            c.execute('UPDATE shopping_list SET items_json=? WHERE id=?',(json.dumps(items),row[0]))
        elif s['kind']=='note':
            c.execute('UPDATE recipe_box_item SET notes=? WHERE user_id=? AND recipe_id=?',(s['note'],s['user'],s['recipe']))
        else:
            c.execute('DELETE FROM meal_plan_item WHERE user_id=? AND day=? AND meal_type=?',(s['user'],s['day'],s['meal']))
            c.execute('INSERT INTO meal_plan_item(user_id,recipe_id,day,meal_type,created_at) VALUES(?,?,?,?,?)',(s['user'],s['recipe'],s['day'],s['meal'],'2026-09-18'))

class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.before=Path(self.temp.name)/'initial.db';self.after=Path(self.temp.name)/'after.db'
        shutil.copy2(SITE/'instance_seed/cookpad.db',self.before)
        shutil.copy2(self.before,self.after)
    def tearDown(self):self.temp.cleanup()
    def test_all_nineteen_positive_controls(self):
        for i in range(19):
            with self.subTest(task=i):
                shutil.copy2(self.before,self.after);apply_expected(i,self.after)
                result=evaluate(i,trajectory(i),self.before,self.after)
                self.assertTrue(result['pass_'],result)
    def test_natural_formats_and_units(self):
        variants=[
            (0,'| Recipe | Time (minutes) | Saves |\n|---|---|---|\n| Best waffles ever | 6 | 2,888 |\n| Buttermilk Belgium Waffles | 10 | 514 |'),
            (0,'Best waffles ever: six minutes, 2888 bookmarks.\nButtermilk Belgium Waffles: ten minutes, 514 bookmarks.'),
            (4,ANSWERS[4].replace('220 g firm tofu','0.22 kg tofu').replace('500 g tofu','0.5 kilograms of tofu')),
            (7,ANSWERS[7].replace('3 hours','180 minutes')),
            (18,ANSWERS[18].replace('not provided','unknown')),
        ]
        for i,text in variants:
            with self.subTest(task=i,text=text):self.assertTrue(answer_ok(i,text))
    def test_wrong_units_swapped_and_negated_values(self):
        bad=[
            (0,ANSWERS[0].replace('6 minutes','6 hours')),
            (0,ANSWERS[0].replace('6 minutes','10 minutes').replace('10 minutes and has 514','6 minutes and has 514')),
            (0,ANSWERS[0].replace('2,888 saves','2,888 reviews')),
            (0,ANSWERS[0].replace('6 minutes','60 minutes (reference 6)')),
            (0,ANSWERS[0].replace('takes 6','does not take 6')),
            (0,ANSWERS[0]+'\nBest waffles ever actually takes 90 minutes.'),
            (1,ANSWERS[1].replace('danrowe57','Mrsrachaelr')),
            (4,ANSWERS[4].replace('220 g','220 kg')),
            (6,ANSWERS[6].replace('2 eggs','3 eggs')),
            (8,ANSWERS[8].replace('Monday breakfast','Sunday dinner')),
            (17,ANSWERS[17].replace('41 minutes longer','41 minutes shorter')),
            (18,ANSWERS[18].replace('not provided','0 minutes')),
        ]
        for i,text in bad:
            with self.subTest(task=i,text=text):self.assertFalse(answer_ok(i,text))
    def test_homepage_and_external_query_spoof_rejected(self):
        for i in range(19):
            t=trajectory(i);t['steps']=[dict(url=t['start_url'])]
            self.assertFalse(navigation_ok(CONTRACTS[i],t),i)
            t=trajectory(i)
            for step in t['steps']:step['url']=step['url'].replace('localhost:44818','evil.test')
            self.assertFalse(navigation_ok(CONTRACTS[i],t),i)
    def test_collateral_deletion_rejected_for_every_task(self):
        for i in range(19):
            shutil.copy2(self.before,self.after);apply_expected(i,self.after)
            with sqlite3.connect(self.after) as c:c.execute('DELETE FROM shopping_list WHERE id=3')
            self.assertFalse(state_ok(CONTRACTS[i],self.before,self.after)[0],i)
    def test_noop_and_wrong_owner_rejected_for_each_write(self):
        for i in [9,10,12,13,15,16,18]:
            shutil.copy2(self.before,self.after)
            self.assertFalse(state_ok(CONTRACTS[i],self.before,self.after)[0],i)
            apply_expected(i,self.after)
            s=CONTRACTS[i]['state'];table={'list_new':'shopping_list','list_edit':'shopping_list','meal':'meal_plan_item','note':'recipe_box_item'}[s['kind']]
            with sqlite3.connect(self.after) as c:
                c.execute(f'UPDATE {table} SET user_id=99 WHERE user_id=?',(s['user'],))
            self.assertFalse(state_ok(CONTRACTS[i],self.before,self.after)[0],i)
    def test_missing_snapshots_fail_closed(self):
        self.assertFalse(evaluate(0,trajectory(0),'','')['pass_'])
    def test_favorites_is_a_valid_saved_recipes_route_for_note_task(self):
        t=trajectory(16)
        for step in t['steps']:step['url']=step['url'].replace('/recipe-box','/favorites')
        apply_expected(16,self.after)
        self.assertTrue(evaluate(16,t,self.before,self.after)['pass_'])
    def test_fixture_tampering_rejected_even_if_both_snapshots_match(self):
        for path in [self.before,self.after]:
            with sqlite3.connect(path) as c:c.execute('UPDATE recipe SET total_time_mins=NULL WHERE id=365027')
        self.assertFalse(state_ok(CONTRACTS[0],self.before,self.after)[0])

if __name__=='__main__':unittest.main()
