"""Positive and adversarial tests for all OSU verifiers."""
from __future__ import annotations
import json,shutil,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from sites.osu.verify.test_support import ensure_seed
VERIFY_DIR=Path(__file__).resolve().parent;SEED=ensure_seed();BASE='http://localhost:40020'
def url(p):return BASE+p
def nav(p):return {'url':url(p),'action':'navigate','params':{}}
def click(a,b):return {'url':url(a),'url_after':url(b),'action':'click','params':{}}
def trans(a,b):return [click(a,b),nav(b)]
class VerifierTests(unittest.TestCase):
 def run_verifier(self,task,steps,answer,mutate=None,task_id=None):
  with tempfile.TemporaryDirectory(prefix=f'osu-v-{task}-') as d:
   root=Path(d);initial=root/'initial.db';after=root/'after.db';run=root/'run';run.mkdir();shutil.copy2(SEED,initial);shutil.copy2(SEED,after)
   if mutate:
    c=sqlite3.connect(after)
    try:mutate(c);c.commit()
    finally:c.close()
   traj={'task_id':task_id or f'Ohio State University--{task}','start_url':url('/'),'steps':steps,'final_url':steps[-1].get('url_after',steps[-1].get('url')) if steps else url('/'),'final_answer':answer};(run/'trajectory.json').write_text(json.dumps(traj))
   r=subprocess.run([sys.executable,str(VERIFY_DIR/f'verify_{task}.py'),'--run_dir',str(run),'--initial_db',str(initial),'--after_db',str(after),'--no_llm','true'],capture_output=True,text=True,timeout=30)
   try:v=json.loads(r.stdout)
   except Exception as e:self.fail(f'task {task}: {r.stdout!r} {r.stderr!r} {e}')
   return r.returncode,v
 def positive(self,i):
  F='/athletics/ohio-state-buckeyes-football';W='/athletics/ohio-state-buckeyes-wrestling';B='/athletics/ohio-state-buckeyes-mens-basketball';E='/athletics/ohio-state-buckeyes-fencing'
  cases={
   0:([nav('/')]+trans('/','/academics'),'Fisher College of Business dean is Anil Makhija.'),
   1:([nav('/about')],'Varsity Sports: 36.'),
   2:([nav('/athletics')]+trans('/athletics',F)+[nav('/athletics')]+trans('/athletics',W),'Football and wrestling both list the Big Ten.'),
   3:([nav('/athletics')]+trans('/athletics',F),'Head coach Ryan Day; recent record 11-2.'),
   4:([nav('/search?q=research+expenditures')]+trans('/search?q=research+expenditures','/news/ohio-state-sets-record-for-research-expenditures-at-13-billion'),'$1.3 billion; September 23, 2024.'),
   5:([nav('/about')],'Founded in 1870 as Ohio Agricultural and Mechanical College.'),
   6:([nav('/research')]+trans('/research','/research/translational-data-analytics-institute'),'Director Beth Plale; Data analytics, Machine learning, Health informatics, Social science.'),
   7:([nav('/about')],'Undergraduate: 46,820; graduate students: 14,000; difference: 32,820.'),
   8:([nav('/academics')],'Engineering: 8,000; Fisher: 4,500; Engineering has more, by 3,500.'),
   9:([nav('/programs?college=engineering')],'There are 3 distinct types: BS, MS, and PhD.'),
   10:([nav('/athletics')]+trans('/athletics',W),'Head coach Tom Ryan; home venue Covelli Center.'),
   11:([nav('/research')]+trans('/research','/research/ohio-supercomputer-center'),'Director David Bickel; founded 1987.'),
   12:([nav('/programs?q=Juris+Doctor')]+trans('/programs?q=Juris+Doctor','/programs/juris-doctor-jd'),'JD; 90 credits; 3 years.'),
   13:([nav('/departments')]+trans('/departments','/departments/department-of-mathematics'),'Chair James Cogdell; location 100 Mathematics Building.'),
   14:([nav('/athletics')]+trans('/athletics',F)+[nav('/athletics')]+trans('/athletics',B),'Football: Ohio Stadium; basketball: Value City Arena.'),
   15:([nav('/athletics')]+trans('/athletics',W)+[nav('/athletics')]+trans('/athletics',E),'Wrestling: 8; fencing: 2; wrestling has more by 6.'),
   16:([nav('/programs?degree=MBA')]+trans('/programs?degree=MBA','/programs/master-of-business-administration-mba'),'Deadline April 1; 60 credits; GRE not required.'),
   17:([nav('/search?q=cancer+research')]+trans('/search?q=cancer+research','/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy'),'Ohio State Researchers Develop Breakthrough Cancer Immunotherapy by Jody Sheridan.'),
   18:([nav('/research')]+trans('/research','/research/james-cancer-hospital-and-solove-research-institute'),'Director William Farrar; Cancer research, Oncology, Clinical trials, Precision medicine.'),
   19:([nav('/research')]+trans('/research','/research/center-for-clean-hydrogen'),'Director Yann Guezennec; founded 2022; Hydrogen energy, Fuel cells, Green hydrogen, Energy storage.'),
  };return cases[i]
 def test_all_positive(self):
  for i in range(20):
   with self.subTest(i=i):
    s,a=self.positive(i);rc,v=self.run_verifier(i,s,a);self.assertEqual(rc,0,v)
 def test_answer_only_fails(self):
  for i in range(20):
   with self.subTest(i=i):
    _,a=self.positive(i);rc,v=self.run_verifier(i,[],a);self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
 def test_wrong_task_id_fails(self):
  for i in range(20):
   with self.subTest(i=i):
    s,a=self.positive(i);rc,v=self.run_verifier(i,s,a,task_id='Ohio State University--999');self.assertNotEqual(rc,0);self.assertEqual(v['reason'],'task_id_matches')
 def test_external_origin_fails(self):
  rc,v=self.run_verifier(1,[{'url':'https://evil.invalid/about','action':'navigate','params':{}}],'Varsity Sports: 36.');self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
 def test_database_mutation_fails_all(self):
  def mutate(c):c.execute("UPDATE news_articles SET view_count=view_count+1 WHERE id=1")
  for i in range(20):
   with self.subTest(i=i):
    s,a=self.positive(i);rc,v=self.run_verifier(i,s,a,mutate);self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
 def test_negated_answers_fail(self):
  for i,a in {1:'There are not 36 varsity sports.',3:'Ryan Day is not coach; record 11-2.',5:'It was not founded in 1870 as Ohio Agricultural and Mechanical College.',16:'Deadline is not April 1; 60 credits; GRE not required.'}.items():
   s,_=self.positive(i);rc,v=self.run_verifier(i,s,a);self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
 def test_swapped_comparisons_fail(self):
  for i,a in {7:'Undergraduate: 14,000; graduate: 46,820; difference 32,820.',8:'Engineering: 4,500; Fisher: 8,000; Engineering has more by 3,500.',14:'Football: Value City Arena; basketball: Ohio Stadium.',15:'Wrestling: 2; fencing: 8; wrestling has more by 6.'}.items():
   s,_=self.positive(i);rc,v=self.run_verifier(i,s,a);self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
 def test_required_filters_fail_when_missing(self):
  for i in (9,12,16):
   s,a=self.positive(i);s=[x for x in s if '?' not in x.get('url','') and '?' not in x.get('url_after','')];rc,v=self.run_verifier(i,s,a);self.assertNotEqual(rc,0);self.assertFalse(v['pass'])
if __name__=='__main__':unittest.main()
