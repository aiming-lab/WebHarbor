"""Synthetic contract controls, distinct from browser completion evidence."""
import json,re,sys,sqlite3
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review_contract import check_answers,check_state
from verify_lib import TABLES
from _support import RunBuilder,copy_db,mutate_db,login_statements,run_verifier,SITE_DIR
ANSWERS = {0: 'Blood sugar monitors and blood sugar test strips are covered by Part B. The monitor must be prescribed by a doctor for home use. Doctors and suppliers must be enrolled in Medicare; ask whether the supplier accepts assignment. For both the monitor and test strips you pay 20% of the Medicare-approved amount after the Part B deductible when assignment is accepted. The annual Part B deductible for 2026 is $283.', 1: 'The Part A deductible is $1,736 per benefit period. The annual Part B deductible is $283. Inpatient hospital days 1-60 cost $0 per day after the deductible. SNF days 21-100 cost $217 per day. A qualifying inpatient hospital stay is at least 3 consecutive days, unless an approved ACO SNF 3-Day Rule Waiver applies. SNF coverage is up to 100 days per benefit period. The Part A deductible is not charged again for SNF in the same benefit period.', 2: 'Bailey Walker Goodwin accepts Medicare assignment and offers telehealth. Bailey Walker Goodwin has medical school listed as Other and graduation year 2020. Clinton K. Pong also accepts Medicare assignment and offers telehealth. Clinton K. Pong attended the University of Hawaii John A. Burns School of Medicine, graduating in 2010. Both office phone numbers are (617) 903-5000.', 3: 'Memorial Medical Center has an overall rating of 3 out of 5, voluntary non-profit private ownership, and 8 safety measures reported. St Johns Hospital has an overall rating of 2 out of 5, voluntary non-profit church ownership, and 6 safety measures reported. I recommend Memorial Medical Center based on its higher overall rating; its phone is (217) 788-3000. These counts describe reported safety measures, not a separate safety score.', 4: 'Part B covers medically necessary walkers prescribed for use at home. You pay 20% of the Medicare-approved amount after the Part B deductible if the supplier accepts assignment. The doctors and suppliers must be enrolled in Medicare. The closest walker supplier for ZIP 80204 is King Soopers Pharmacy #001, phone (303) 571-1943; it accepts Medicare assignment.', 5: 'Aetna Medicare Premier (HMO): monthly premium $0; medical deductible $0; in-network out-of-pocket limit $6,700; rating 4.5 stars. Blue Cross Medicare Classic (PPO): monthly premium $54; medical deductible $199; in-network out-of-pocket limit $7,550; rating 3 stars. I recommend Aetna Medicare Premier because it meets both budget limits. You must keep paying the Part B premium. Aetna lists an over-the-counter allowance. Blue Cross lists a 24/7 nurse line.', 6: 'The order was received for 2 Standard Print copies of Medicare & You 2027, product 10050, to 12 Elm Court, Denver, CO 80204.', 7: 'The Summary Notice service period is June 1 through August 31, 2026. For the screening colonoscopy, Medicare paid $1,736.00 and Alice may be billed $0.00. For blood sugar test strips, Medicare paid $77.12 and Alice may be billed $19.28. The total Alice may be billed across both claims is $19.28.', 8: 'The $202.90 Part B premium due October 25, 2026 is now paid with the default Bank account ending 4821. The previously paid bill was left unchanged.', 9: "Alice's Medicare Number is 1EG4-TE5-MK73. Her current mailing address is 45 Meadow Lane, Buffalo Grove, IL 60089. A replacement card for the lost card was requested; its status is Mailing in 7-10 days.", 10: 'Both orders were received: Medicare Coverage of Cancer Treatment Services, product 11931, 2 copies in Standard Print; Choosing a Medigap Policy, product 02110, 1 copy in Large Print. Both ship to 12 Sunset Terrace, Springfield, IL 62704-1234.', 11: 'The Medicare Appeals order was received: product 11525, 1 Large Print copy in English, to 302 W Edwards St, Springfield, IL 62704.', 12: 'The newest unread message is Reminder: Medicare Open Enrollment starts October 15. Open Enrollment runs October 15 through December 7, 2026; you can join, switch, or drop a Medicare Advantage Plan or Medicare drug plan. This message is now read and the other unread message remains unread.', 13: 'Hospice requires Part A. The hospice doctor and the regular doctor, if any, certify a life expectancy of 6 months or less. Hospice care costs $0, with up to a $5 copayment for each outpatient drug prescription. The first closest hospice listed near Houston is 1st Choice Hospice LLC, phone (936) 295-7100.', 14: 'Because he already receives Social Security retirement benefits, Medicare enrollment is automatic. Social Security (SSA) handles Part A and Part B enrollment. The Medicare TTY number is 1-877-486-2048. In 2026 the standard Part B monthly premium is $202.90. The annual Part B deductible is $283. The Part A deductible is $1,736 per benefit period.'}
PATHS = {
0:['/coverage/blood-sugar-monitors','/coverage/blood-sugar-test-strips','/basics/costs/medicare-costs'],
1:['/basics/costs/medicare-costs','/coverage/skilled-nursing-facility-care'],2:['/care-compare/provider/362','/care-compare/provider/367'],3:['/care-compare/provider/3045','/care-compare/provider/3046'],
4:['/coverage/walkers','/medical-equipment-suppliers/results?location=80204&equipment=walkers'],5:['/plan-compare/plan/1','/plan-compare/plan/4'],6:['/publication-ordering/10050','/publication-orders/1'],7:['/my/messages/1','/my/claims'],8:['/my/premiums'],9:['/my/account-settings','/my/account-settings/get-my-medicare-card'],10:['/publication-ordering/11931','/publication-ordering/02110','/publication-orders/2'],11:['/publication-ordering/11525','/publication-orders/1'],12:['/my/messages/3'],13:['/coverage/hospice-care','/care-compare/provider/1459'],14:['/basics/get-started-with-medicare','/basics/costs/medicare-costs','/talk-to-someone']}
class Judge:
 def __init__(self):self.failures=[]
 def check(self,name,condition,evidence=''):
  if not condition:self.failures.append(name)

def outcome(i,path):
 statements=[]
 if i in (7,8,9,10,12):statements+=login_statements(2 if i==8 else 1)
 if i in (7,12):statements+=[('UPDATE messages SET is_read=1 WHERE id=?',(1 if i==7 else 3,))]
 if i==8:statements+=[("UPDATE premium_bills SET status='Paid', paid_date='2026-09-23', method='Bank account ending 4821' WHERE user_id=2 AND status='Due'",())]
 if i==9:statements += [("UPDATE mailing_addresses SET is_current=0 WHERE user_id=1",()),("INSERT INTO mailing_addresses(user_id,line1,line2,city,state,zip,is_current,effective_date) VALUES(1,'45 Meadow Lane',NULL,'Buffalo Grove','IL','60089',1,'2026-09-23')",()),("INSERT INTO card_requests(user_id,reason,requested_at,status) VALUES(1,'lost','2026-09-23','Mailing in 7-10 days')",())]
 orders={6:[('10050',2,'Standard Print',None,'12 Elm Court','Denver','CO','80204')],10:[('11931',2,'Standard Print',1,'12 Sunset Terrace','Springfield','IL','62704-1234'),('02110',1,'Large Print',1,'12 Sunset Terrace','Springfield','IL','62704-1234')],11:[('11525',1,'Large Print',None,'302 W Edwards St','Springfield','IL','62704')]}.get(i,[])
 for num,q,fmt,uid,street,city,state,zip_ in orders:
  statements.append(("INSERT INTO pub_orders(publication_id,quantity,format,user_id,ship_line1,ship_city,ship_state,ship_zip,created_at,status) VALUES((SELECT id FROM publications WHERE product_number=?),?,?,?,?,?,?,?,'2026-09-23','Processing')",(num,q,fmt,uid,street,city,state,zip_)))
 mutate_db(path,statements)

def fixture(tmp_path,i):
 run=tmp_path/'run';b=RunBuilder(run,f'Medicare.gov--{i}')
 if i in (7,8,9,10,12):b.login('bob.c@test.com' if i==8 else 'alice.j@test.com')
 for p in PATHS[i]:b.step(p)
 b.done(ANSWERS[i]).write();traj=json.loads((run/'trajectory.json').read_text());task=json.loads((SITE_DIR/'tasks.jsonl').read_text().splitlines()[i]);traj['task']=task['ques'];(run/'trajectory.json').write_text(json.dumps(traj))
 before=copy_db(tmp_path/'initial.db');after=copy_db(tmp_path/'after.db');outcome(i,after)
 return run,before,after

@pytest.mark.parametrize('i',range(15))
@pytest.mark.parametrize('variant',['prose','bullets','uppercase'])
def test_natural_answers(i,variant):
 answer=re.sub(r'\b([A-Z])\.(?=\s+[A-Z])', r'\1', ANSWERS[i])
 if variant=='bullets':answer='\n'.join('- '+p for p in re.split(r'(?<=[.!?])\s+(?=[A-Z])',answer))
 if variant=='uppercase':answer=answer.upper()
 judge=Judge();check_answers(judge,i,answer);assert not judge.failures,judge.failures

@pytest.mark.parametrize('i',range(15))
@pytest.mark.parametrize('attack',['empty','wrong_values','negated'])
def test_bad_answers(i,attack):
 answer={'empty':'','wrong_values':re.sub(r'\d','9',ANSWERS[i]),'negated':'\n'.join('This is incorrect: '+s for s in ANSWERS[i].splitlines())}[attack]
 judge=Judge();check_answers(judge,i,answer);assert judge.failures

@pytest.mark.parametrize('i',range(15))
@pytest.mark.parametrize('attack',['honest','no_answer','home_only','wrong_task','bad_png','collateral'])
def test_full_contract(tmp_path,i,attack):
 run,before,after=fixture(tmp_path,i)
 p=run/'trajectory.json';t=json.loads(p.read_text())
 if attack=='no_answer':t['final_answer']=''
 if attack=='home_only':
  for step in t['steps']:step['url']=t['start_url'];step['url_after']=t['start_url']
  t['final_url']=t['start_url']
 if attack=='wrong_task':t['task']='Old task prompt'
 if attack=='bad_png':next((run/'screenshots').glob('*.png')).write_bytes(b'not png')
 if attack=='collateral':mutate_db(after,[("UPDATE users SET display_name='Changed' WHERE id=4",())])
 p.write_text(json.dumps(t));run_verifier(i,run,before,after,expect_pass=attack=='honest')

@pytest.mark.parametrize('i',[6,7,8,9,10,11,12])
def test_stateful_noop_fails(tmp_path,i):
 run,before,after=fixture(tmp_path,i);run_verifier(i,run,before,before,expect_pass=False)

@pytest.mark.parametrize('i',[6,10,11])
@pytest.mark.parametrize('field,value',[('quantity',5),('format','Braille'),('ship_zip','99999'),('user_id',4),('status','Cancelled')])
def test_wrong_order_fields_fail(tmp_path,i,field,value):
 run,before,after=fixture(tmp_path,i);mutate_db(after,[(f'UPDATE pub_orders SET {field}=?',(value,))]);run_verifier(i,run,before,after,False)

@pytest.mark.parametrize('i,old,new',[(1,'$1,736','$283'),(1,'$283','$1,736'),(3,'3 out of 5','2 out of 5'),(3,'8 safety','6 safety'),(5,'$6,700','$7,550'),(7,'$77.12','$19.28'),(8,'$202.90','$902.90'),(14,'$283','$1,736')])
def test_wrong_fact_plus_reference_cannot_rescue(i,old,new):
 answer=ANSWERS[i].replace(old,new)+' Reference number: '+old+'.'
 judge=Judge();check_answers(judge,i,answer);assert judge.failures


@pytest.mark.parametrize('i,answer',[
 (2, 'Bailey Walker Goodwin: Medicare assignment yes; telehealth available; school unspecified; graduation year 2020. Clinton Pong: assignment yes; telehealth yes; University of Hawaii; graduation year 2010. Both office phone numbers: 617-903-5000.'),
 (5, """| Plan | Monthly premium | Medical deductible | In-network out-of-pocket limit | Rating | Benefits |
|---|---|---|---|---|---|
| Aetna Medicare Premier | $0 | $0 | $6,700 | 4.5 stars | over-the-counter allowance |
| Blue Cross Medicare Classic | $54 | $199 | $7,550 | 3 stars | 24/7 nurse line |
I recommend Aetna. She must continue to pay the Part B premium."""),
 (6, 'Order confirmed: Medicare & You 2027, two Standard Print copies, to 12 Elm Court, Denver, CO 80204.'),
 (11, 'Medicare Appeals, product 11525, one Large Print copy, order accepted. Delivery: 302 W Edwards St, Springfield, IL 62704.'),
 (13, 'Hospice care requires Part A and costs nothing. The hospice doctor and personal doctor must certify a life expectancy of six months or less. Each outpatient drug has a copayment up to $5. The first provider is 1st Choice Hospice LLC, 936-295-7100.'),
])
def test_equivalent_natural_formulations(i,answer):
 j=Judge();check_answers(j,i,answer);assert not j.failures,j.failures

@pytest.mark.parametrize('i,contradiction',[(1,'Part A deductible is $999.'),(5,'Aetna monthly premium is $999.'),(7,'For the test strips Medicare paid $999.'),(14,'Part B deductible is $999.')])
def test_contradictory_extra_fact(i,contradiction):
 j=Judge();check_answers(j,i,ANSWERS[i]+' '+contradiction);assert j.failures
