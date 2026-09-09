"""Positive and adversarial tests for all TED verifiers."""
from __future__ import annotations
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR=Path(__file__).resolve().parent
SEED_DB=VERIFY_DIR.parent/'instance_seed'/'ted.db'
BASE='http://localhost:40019'

def url(path):return BASE+path
def nav(path):return {'url':url(path),'action':'navigate','params':{}}
def click(source,destination):return {'url':url(source),'url_after':url(destination),'action':'click','params':{}}
def enter(path,text,action='input'):return {'url':url(path),'action':action,'params':{'option' if action=='select' else 'text':text}}
def transition(source,destination):return [click(source,destination),nav(destination)]
def login(email='alice.j@test.com'):return [nav('/login'),enter('/login',email),enter('/login','TestPass123!'),click('/login','/account'),nav('/account')]
def next_id(con,table):return con.execute(f'SELECT COALESCE(MAX(id),0)+1 FROM {table}').fetchone()[0]
def ids(con,email,slug):
 uid=con.execute('SELECT id FROM user WHERE email=?',(email,)).fetchone()[0];tid=con.execute('SELECT id FROM talk WHERE slug=?',(slug,)).fetchone()[0];return uid,tid

class VerifierTests(unittest.TestCase):
 def run_verifier(self,task,steps,answer,mutate=None,task_id=None):
  with tempfile.TemporaryDirectory(prefix=f'ted-verify-{task}-') as temp:
   root=Path(temp);initial=root/'initial.db';after=root/'after.db';run=root/'run';run.mkdir();shutil.copy2(SEED_DB,initial);shutil.copy2(SEED_DB,after)
   if mutate:
    con=sqlite3.connect(after)
    try:mutate(con);con.commit()
    finally:con.close()
   trajectory={'task_id':task_id or f'TED--{task}','start_url':url('/'),'steps':steps,'final_url':steps[-1].get('url_after',steps[-1].get('url')) if steps else url('/'),'final_answer':answer}
   (run/'trajectory.json').write_text(json.dumps(trajectory),encoding='utf-8')
   result=subprocess.run([sys.executable,str(VERIFY_DIR/f'verify_{task}.py'),'--run_dir',str(run),'--initial_db',str(initial),'--after_db',str(after),'--no_llm','true'],capture_output=True,text=True,timeout=30,check=False)
   try:verdict=json.loads(result.stdout)
   except json.JSONDecodeError as error:self.fail(f'task {task} invalid output {result.stdout!r} {result.stderr!r}: {error}')
   return result.returncode,verdict
 @staticmethod
 def add_saved(con,email,slug,note):
  uid,tid=ids(con,email,slug);con.execute('INSERT INTO saved_talk(id,user_id,talk_id,saved_at,note) VALUES(?,?,?,?,?)',(next_id(con,'saved_talk'),uid,tid,'2026-09-06 10:00:00',note))
 @classmethod
 def mutate_task1(cls,con):cls.add_saved(con,'alice.j@test.com','tekedra-mawakana-sal-khan-waymo-s-case-for-a-driverless-future','mobility planning')
 @staticmethod
 def mutate_task4(con):con.execute("UPDATE user SET newsletter_topic='conservation' WHERE email='alice.j@test.com'")
 @staticmethod
 def mutate_task7(con):
  uid=con.execute("SELECT id FROM user WHERE email='alice.j@test.com'").fetchone()[0];eid=con.execute("SELECT id FROM event WHERE slug='ted2026'").fetchone()[0];con.execute('INSERT INTO registration(id,user_id,event_id,status) VALUES(?,?,?,?)',(next_id(con,'registration'),uid,eid,'waitlisted'))
 @classmethod
 def mutate_task9(cls,con):cls.add_saved(con,'alice.j@test.com','joy-milne-the-nurse-who-can-smell-parkinson-s','public health review')
 @staticmethod
 def mutate_task12(con):
  con.execute("DELETE FROM saved_talk WHERE user_id=(SELECT id FROM user WHERE email='alice.j@test.com') AND talk_id=(SELECT id FROM talk WHERE slug='christian-busch-is-luck-random-or-can-you-cultivate-it')")
 @staticmethod
 def mutate_task16(con):
  uid=next_id(con,'user');con.execute('INSERT INTO user(id,username,email,display_name,password_hash,role,city,newsletter_topic) VALUES(?,?,?,?,?,?,?,?)',(uid,'new_reviewer','new.reviewer@example.com','New Reviewer','hash','Curious learner','','technology'));tid=con.execute("SELECT id FROM talk WHERE slug='peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent'").fetchone()[0];con.execute('INSERT INTO saved_talk(id,user_id,talk_id,saved_at,note) VALUES(?,?,?,?,?)',(next_id(con,'saved_talk'),uid,tid,'2026-09-06 10:00:00',''))
 def positive(self,task):
  paths={0:'/talks/anil-seth-why-ai-is-unlikely-to-become-conscious',2:'/talks/debbie-millman-you-got-what-you-wanted-now-what',5:'/talks/malala-yousafzai-what-i-got-wrong-about-changing-the-world',6:'/talks/kimiko-hirata-a-cheat-sheet-for-accelerating-clean-energy',14:'/talks/riyad-joucka-reimagining-traditional-architecture-for-modern-needs'}
  playlist='/playlists/climate-nature-conservation';maya='/talks/maya-higa-the-wildlife-sanctuary-you-can-visit-from-anywhere';rose='/talks/rose-b-simpson-debbie-millman-how-to-invite-creativity-into-your-life';els='/talks/elsaphan-njora-conservation-a-love-story';peter='/talks/peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent';anil=paths[0];nayeema='/talks/nayeema-raza-3-habits-to-practice-curiosity-and-escape-your-phone';kate='/talks/kate-canales-the-accidental-brilliance-of-makeshift-signs'
  cases={
   0:([nav('/search?q=AI')]+transition('/search?q=AI',paths[0]),'The duration is 15 minutes.',None),
   1:(login()+[nav('/talks?event=TED2026')]+transition('/talks?event=TED2026','/talks/tekedra-mawakana-sal-khan-waymo-s-case-for-a-driverless-future')+[click('/talks/tekedra-mawakana-sal-khan-waymo-s-case-for-a-driverless-future','/talks/tekedra-mawakana-sal-khan-waymo-s-case-for-a-driverless-future')],'Saved with mobility planning.',self.mutate_task1),
   2:([nav('/search?q=design')]+transition('/search?q=design',paths[2]),'It is 8 minutes.',None),
   3:([nav('/playlists')]+transition('/playlists',playlist)+transition(playlist,maya)+[nav(playlist)]+transition(playlist,rose)+[nav(playlist)]+transition(playlist,els),'The first qualifying title is Conservation: a love story.',None),
   4:(login()+[click('/account','/account'),nav('/account')],'Newsletter topic changed to conservation.',self.mutate_task4),
   5:([nav('/search?q=Malala+Yousafzai')]+transition('/search?q=Malala+Yousafzai',paths[5]),'What I got wrong about changing the world.',None),
   6:([nav('/search?q=clean+energy')]+transition('/search?q=clean+energy',paths[6]),'TED Countdown Summit 2025.',None),
   7:(login()+[nav('/events'),click('/events','/account'),nav('/account')],'TED2026 registration confirmed.',self.mutate_task7),
   8:([nav('/search?q=Alexi+Pappas')]+transition('/search?q=Alexi+Pappas','/talks/alexi-pappas-why-i-love-my-bad-days')+[nav('/search?q=Debbie+Millman')]+transition('/search?q=Debbie+Millman',paths[2]),"Alexi Pappas is shorter at 5 minutes; Debbie Millman's talk is 8 minutes.",None),
   9:(login()+[nav('/search?q=Parkinson')]+transition('/search?q=Parkinson','/talks/joy-milne-the-nurse-who-can-smell-parkinson-s')+[click('/talks/joy-milne-the-nurse-who-can-smell-parkinson-s','/talks/joy-milne-the-nurse-who-can-smell-parkinson-s')],'Saved with public health review.',self.mutate_task9),
   10:([nav('/playlists')]+transition('/playlists','/playlists/ai-and-society')+transition('/playlists/ai-and-society','/talks/neal-kumar-katyal-what-really-won-the-trillion-dollar-supreme-court-case'),"Neal Kumar Katyal — What really won the trillion-dollar Supreme Court case.",None),
   11:([nav('/talks?event=TED2026&max_minutes=10')]+transition('/talks?event=TED2026&max_minutes=10',maya),'The wildlife sanctuary you can visit from anywhere.',None),
   12:(login()+[click('/account','/account'),nav('/account')],'I removed Is luck random - or can you cultivate it?',self.mutate_task12),
   13:([nav('/topics')]+transition('/topics','/talks?topic=science')+transition('/talks?topic=science','/talks/qian-janice-wang-the-art-and-science-of-wine-tasting'),'The art and science of wine tasting by Qian Janice Wang.',None),
   14:([nav('/search?q=architecture+3D+printing')]+transition('/search?q=architecture+3D+printing',paths[14]),'The speaker is Riyad Joucka.',None),
   15:([nav('/topics')]+transition('/topics','/talks?topic=music')+transition('/talks?topic=music','/talks/akoth-jumadi-and-mr-lu-east-african-sound-meets-cosmic-trap')+[nav('/talks?topic=music')]+transition('/talks?topic=music','/talks/turkana-sessions-a-musical-journey-through-turkana'),'Turkana Sessions has more views: 4,223 versus Akoth Jumadi and Mr. Lu at 2,781.',None),
   16:([nav('/register'),enter('/register','new.reviewer@example.com'),click('/register','/account'),nav('/account'),nav('/search?q=OpenClaw')]+transition('/search?q=OpenClaw',peter)+[click(peter,peter),nav(peter),nav('/account')],'Saved: How I created OpenClaw, the breakthrough AI agent.',self.mutate_task16),
   17:([nav('/events')],'TEDNext 2025 is scheduled for November 2025.',None),
   18:([nav('/talks?event=TED2026&topic=ai&max_minutes=20')]+transition('/talks?event=TED2026&topic=ai&max_minutes=20',peter)+[nav('/talks?event=TED2026&topic=ai&max_minutes=20')]+transition('/talks?event=TED2026&topic=ai&max_minutes=20',anil),'Peter has more views: 551,544 versus Anil at 191,682, a difference of 359,862.',None),
   19:([nav('/talks?event=TEDNext+2025&topic=culture&max_minutes=10')]+transition('/talks?event=TEDNext+2025&topic=culture&max_minutes=10',nayeema)+[nav('/talks?event=TEDNext+2025&topic=culture&max_minutes=10')]+transition('/talks?event=TEDNext+2025&topic=culture&max_minutes=10',kate),'Nayeema has more views: 554,563 versus Kate at 203,431, a difference of 351,132.',None),
  };return cases[task]
 def test_all_positive_cases(self):
  for task in range(20):
   with self.subTest(task=task):
    steps,answer,mutate=self.positive(task);code,v=self.run_verifier(task,steps,answer,mutate);self.assertEqual(code,0,v);self.assertTrue(v['pass'],v)
 def test_wrong_task_id_fails_all(self):
  for task in range(20):
   with self.subTest(task=task):
    steps,answer,mutate=self.positive(task);code,v=self.run_verifier(task,steps,answer,mutate,'TED--999');self.assertNotEqual(code,0);self.assertEqual(v['reason'],'task_id_matches')
 def test_answer_only_fails_all(self):
  for task in range(20):
   with self.subTest(task=task):
    _,answer,mutate=self.positive(task);code,v=self.run_verifier(task,[],answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_external_origin_spoof_fails(self):
  steps=[{'url':'https://evil.invalid/talks/anil-seth-why-ai-is-unlikely-to-become-conscious','action':'navigate','params':{}}];code,v=self.run_verifier(0,steps,'15 minutes');self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_negated_answers_fail(self):
  for task,answer in {0:'It is not 15 minutes.',5:'The title is not What I got wrong about changing the world.',17:'TEDNext 2025 is not November 2025.',18:'Peter does not have more views; 551,544 vs 191,682, difference 359,862.'}.items():
   with self.subTest(task=task):
    steps,_,mutate=self.positive(task);code,v=self.run_verifier(task,steps,answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_state_tasks_reject_unrelated_mutations(self):
  for task in (1,4,7,9,12,16):
   with self.subTest(task=task):
    steps,answer,base=self.positive(task)
    def mutate(con,base=base):base(con);con.execute("UPDATE user SET city='Unexpected' WHERE email='david.k@test.com'")
    code,v=self.run_verifier(task,steps,answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_swapped_comparison_values_fail(self):
  for task,answer in {8:"Alexi is shorter at 8 minutes versus Debbie at 5 minutes.",15:"Turkana has more views at 2,781 versus Akoth at 4,223.",18:"Peter has more views at 191,682 versus Anil at 551,544, difference 359,862.",19:"Nayeema has more views at 203,431 versus Kate at 554,563, difference 351,132."}.items():
   with self.subTest(task=task):
    steps,_,mutate=self.positive(task);code,v=self.run_verifier(task,steps,answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_state_tasks_reject_extra_same_table_changes(self):
  cases=[]
  def extra_saved_1(con):
   self.mutate_task1(con);self.add_saved(con,'bob.c@test.com','joy-milne-the-nurse-who-can-smell-parkinson-s','extra')
  cases.append((1,extra_saved_1))
  def extra_registration(con):
   self.mutate_task7(con);uid=con.execute("SELECT id FROM user WHERE email='bob.c@test.com'").fetchone()[0];eid=con.execute("SELECT id FROM event WHERE slug='ted2026'").fetchone()[0];con.execute('INSERT INTO registration(id,user_id,event_id,status) VALUES(?,?,?,?)',(next_id(con,'registration'),uid,eid,'waitlisted'))
  cases.append((7,extra_registration))
  def extra_saved_9(con):
   self.mutate_task9(con);self.add_saved(con,'bob.c@test.com','anil-seth-why-ai-is-unlikely-to-become-conscious','extra')
  cases.append((9,extra_saved_9))
  def extra_remove(con):
   self.mutate_task12(con);con.execute("DELETE FROM saved_talk WHERE user_id=(SELECT id FROM user WHERE email='bob.c@test.com') AND id=(SELECT MIN(id) FROM saved_talk WHERE user_id=(SELECT id FROM user WHERE email='bob.c@test.com'))")
  cases.append((12,extra_remove))
  def extra_new_user_save(con):
   self.mutate_task16(con);self.add_saved(con,'bob.c@test.com','anil-seth-why-ai-is-unlikely-to-become-conscious','extra')
  cases.append((16,extra_new_user_save))
  for task,mutate in cases:
   with self.subTest(task=task):
    steps,answer,_=self.positive(task);code,v=self.run_verifier(task,steps,answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_filter_tasks_require_combined_exact_url(self):
  for task in (11,18,19):
   with self.subTest(task=task):
    steps,answer,mutate=self.positive(task);steps=[s for s in steps if 'max_minutes' not in s.get('url','') and 'max_minutes' not in s.get('url_after','')];code,v=self.run_verifier(task,steps,answer,mutate);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
 def test_removing_ai_talk_fails_task12(self):
  steps,answer,_=self.positive(12)
  def remove_ai(con):con.execute("DELETE FROM saved_talk WHERE user_id=(SELECT id FROM user WHERE email='alice.j@test.com') AND talk_id=(SELECT id FROM talk WHERE slug='peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent')")
  code,v=self.run_verifier(12,steps,answer,remove_ai);self.assertNotEqual(code,0);self.assertFalse(v['pass'])
if __name__=='__main__':unittest.main()
