import copy
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from answers import answer_ok
from fixtures import PASS_ANSWERS
from verify_lib import ACCOUNTS, LOOKUPS, REQUIRED_TABLES, evaluate, load_run, navigation_ok, state_ok

BASE = 'http://localhost:40016'


def fixture(task):
    def step(path, text='Observed page'):
        return {'url': BASE+path, 'page_text': text}
    if task in LOOKUPS:
        steps = [step('/refund-status/start'), step('/refund-status/verify'),
                 step('/refund-status/result', 'Refund status result '+LOOKUPS[task])]
        if task == 10:
            steps[-1]['page_text'] = 'Information Mismatch. The ZIP code does not match. Malik Rivera'
        if task == 13:
            steps.insert(0,step('/search?q=split+deposit'))
        if task == 17:
            steps.append(step('/refund-status/summary', 'Printable summary '+LOOKUPS[task]+' Paper check'))
    elif task in ACCOUNTS:
        steps = [step('/login'), step('/lookup-history', ACCOUNTS[task])]
        if task == 8:
            steps = [step('/login'), step('/account/edit'), step('/account', 'David Kim Spokane Email')]
    elif task == 4:
        steps = [step('/search?q=amended'), step('/help/amended-return-wait-times', 'Amended returns take longer')]
    elif task == 5:
        steps = [step('/notices'), step('/notices/ID-221', 'ID-221 checklist contact preference')]
    elif task == 14:
        steps = [step('/notices?stage=Refund+Sent', 'SP-177')]
    elif task == 15:
        steps = [step('/faq', 'Saved lookup history is tied to local benchmark or registered demo accounts')]
    return {'start_url': BASE, 'steps': steps, 'final_answer': PASS_ANSWERS[task]}


class AnswerTests(unittest.TestCase):
    def test_examples(self):
        for i, answer in PASS_ANSWERS.items():
            with self.subTest(task=i):
                self.assertTrue(answer_ok(i,answer))

    def test_negation_reversal_and_unrelated_number(self):
        cases = {0:'Paper check, not split deposit.',1:'Identity verification is not needed.',
                 2:'He was only approved yesterday but his refund has now been sent.',
                 3:'Refund Approved, not Return Received.',
                 4:'Standard returns stay in review longer than amended returns.',
                 5:'Ignore the checklist, do not confirm the address or contact preference.',
                 6:'Identity verification is not needed.',
                 7:'2025 is further along: it is sent while 2024 is approved.',
                 9:'12345, not 00000.',10:'The ZIP is correct; the refund amount is wrong.',
                 11:'SP-177, not ID-221.',12:'Do not verify the stored mailing ZIP code.',
                 13:'Direct deposit, not split deposit.',14:'ID-221, not SP-177.',
                 15:'Yes, guest history is saved; no account sign in is necessary.',
                 16:'The refund is $500. The reference number is 980.',
                 17:'Direct deposit, not paper check.'}
        for i,a in cases.items():
            with self.subTest(task=i):self.assertFalse(answer_ok(i,a),a)

    def test_equivalent_answers(self):
        cases = [(0,'The refund is split between multiple bank accounts.'),
                 (0,'Split deposit, not paper check.'),
                 (1,'An identity check is delaying the refund.'),
                 (2,'Approved and awaiting dispatch.'),
                 (2,'Approved, not yet sent.'),
                 (3,'The return has been received.'),
                 (4,'Amended returns take more time in review than ordinary returns.'),
                 (4,'Standard returns are faster than amended returns.'),
                 (7,'2024'),(7,'The earlier refund is sent; the newer one is approved.'),
                 (7,'Year | Stage\n2024 | Refund Sent\n2025 | Refund Approved'),
                 (9,'00000'),(10,'Postal code'),(11,'ID 221'),
                 (12,'Confirm the name on the synthetic photo ID.'),
                 (14,'SP-177'),(15,'No.'),(15,'Guest lookups are not retained. Log in to retain them.'),
                 (16,'Nine hundred and eighty dollars.'),(16,'USD 980.00'),
                 (16,'The refund amount is 980.'),(17,'A paper cheque.')]
        for i,a in cases:
            with self.subTest(task=i,answer=a):self.assertTrue(answer_ok(i,a),a)

    def test_conflicting_claims(self):
        cases = [(0,'Split deposit. Actually paper check.'),
                 (2,'Approved. It has been dispatched.'),
                 (4,'Amended returns take longer than standard returns. Standard returns take longer than amended returns.'),
                 (7,'2024 is further along, but 2025 is sent and 2024 is approved.'),
                 (15,'No. Guest history is saved.'),
                 (16,'The refund is $980, or $500.'),
                 (17,'Paper cheque. It is not paper check.')]
        for i,a in cases:
            with self.subTest(task=i):self.assertFalse(answer_ok(i,a),a)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.initial = self.root/'initial.db';self.after = self.root/'after.db'
        with sqlite3.connect(self.initial) as db:
            db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY,email TEXT,city TEXT,preferred_contact_method TEXT,display_name TEXT)')
            db.executemany('INSERT INTO users VALUES (?,?,?,?,?)',[(1,'david.k@test.com','Seattle','Mail','David Kim'),(2,'alice.j@test.com','Springfield','Email','Alice Johnson')])
            for table in REQUIRED_TABLES-{'users'}:
                db.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, value TEXT)')
                db.execute(f'INSERT INTO {table} VALUES (1,?)',('seed',))
        shutil.copyfile(self.initial,self.after)

    def mutate(self,sql):
        with sqlite3.connect(self.after) as db:db.executescript(sql)

    def complete_profile(self):
        self.mutate("UPDATE users SET city='Spokane',preferred_contact_method='Email' WHERE id=1")

    def test_all_tasks_accept_observed_completion(self):
        for i in range(18):
            if i==8:self.complete_profile()
            else:shutil.copyfile(self.initial,self.after)
            v=evaluate(i,fixture(i),self.initial,self.after)
            with self.subTest(task=i):self.assertTrue(v['pass'],v)

    def test_wrong_account_and_non_mismatch(self):
        t=fixture(6);t['steps'][-1]['page_text']='Alice Johnson'
        self.assertFalse(navigation_ok(6,t)[0])
        t=fixture(10);t['steps'][-1]['page_text']='Malik Rivera Processing'
        self.assertFalse(navigation_ok(10,t)[0])

    def test_foreign_origin_and_url_query_spoof(self):
        for transform in [lambda u:u.replace('localhost','example.invalid'),lambda u:BASE+'/?memo='+u,
                          lambda u:u.replace(':40016',':40017')]:
            t=fixture(0)
            for step in t['steps']:step['url']=transform(step['url'])
            self.assertFalse(navigation_ok(0,t)[0])

    def test_manual_lookup_and_notice_without_click(self):
        self.assertTrue(navigation_ok(0,fixture(0))[0])
        self.assertTrue(navigation_ok(11,fixture(11))[0])

    def test_homepage_claims_and_missing_page_content(self):
        for i in range(18):
            t=fixture(i);t['steps']=[{'url':BASE+'/','page_text':PASS_ANSWERS[i]}]
            self.assertFalse(navigation_ok(i,t)[0])
            t=fixture(i)
            for s in t['steps']:s.pop('page_text')
            self.assertFalse(navigation_ok(i,t)[0])

    def test_actual_search_and_filter_required(self):
        for i,path in [(4,'/search?q=unrelated'),(13,'/search?q=unrelated'),(14,'/notices?stage=Refund+Approved'),(14,'/notices?stage=Refund+Sent&stage=Refund+Approved')]:
            t=fixture(i);t['steps'][0]['url']=BASE+path
            self.assertFalse(navigation_ok(i,t)[0])

    def test_profile_exact_delta(self):
        self.assertFalse(state_ok(8,self.initial,self.after)[0]);self.complete_profile()
        self.assertTrue(state_ok(8,self.initial,self.after)[0])
        for sql in ["UPDATE users SET city='Portland' WHERE id=2", "UPDATE users SET display_name='Wrong' WHERE id=1",'DELETE FROM lookup_histories','DROP TABLE alerts']:
            shutil.copyfile(self.initial,self.after);self.complete_profile();self.mutate(sql)
            with self.subTest(sql=sql):self.assertFalse(state_ok(8,self.initial,self.after)[0])

    def test_read_tasks_only_append_logs(self):
        self.mutate("INSERT INTO search_logs VALUES (2,'amended return')")
        self.assertTrue(state_ok(4,self.initial,self.after)[0])
        self.mutate("UPDATE users SET city='Spokane' WHERE id=1")
        self.assertFalse(state_ok(4,self.initial,self.after)[0])

    def test_missing_snapshot_fails_without_creating_file(self):
        missing=self.root/'missing.db'
        self.assertFalse(state_ok(8,missing,self.after)[0]);self.assertFalse(missing.exists())

    def test_wrapper_uses_run_snapshots_and_is_repeatable(self):
        self.complete_profile();(self.root/'trajectory.json').write_text(json.dumps(fixture(8)))
        cmd=[sys.executable,str(Path(__file__).parent/'verify_8.py'),'--run_dir',str(self.root),'--container','does-not-exist']
        before=(self.after.read_bytes(),self.initial.read_bytes())
        for _ in range(2):
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(before,(self.after.read_bytes(),self.initial.read_bytes()))

    def test_legacy_sidecar_is_observed_content(self):
        t=fixture(15);t['steps'][0].pop('page_text');t['steps'][0]['step']=0
        (self.root/'trajectory.json').write_text(json.dumps(t));(self.root/'page_000.txt').write_text(fixture(15)['steps'][0]['page_text'])
        self.assertTrue(navigation_ok(15,load_run(self.root))[0])

    def test_tasks_keep_natural_prompts_and_credentials(self):
        rows=[json.loads(s) for s in (Path(__file__).parents[1]/'tasks.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),18)
        for i,row in enumerate(rows):
            self.assertNotIn('answer',row)
            self.assertTrue(row['judge_rubric'])
            if i in ACCOUNTS:self.assertIn('TestPass123!',row['ques'])


if __name__ == '__main__':unittest.main()
