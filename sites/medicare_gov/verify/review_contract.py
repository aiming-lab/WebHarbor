"""Task-specific answer relationships and exact saved-state contracts.

Facts live here, never in task prompts. No action count or prescribed click
sequence is graded. Natural prose, bullets and labeled tables are supported;
this deterministic parser does not claim unrestricted semantic understanding.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from verify_lib import (check_trajectory_identity, check_signed_in_as, final_answer,
                        navigated_to_path, site_urls, table_rows, table_columns, TABLES)


def chunks(text):
    # Labeled markdown tables are ordinary user-facing answers. Expand headers
    # into their row cells before sentence-level relationship checks.
    lines=text.splitlines(); expanded=[]; headers=None
    for line in lines:
        if '|' in line:
            cells=[c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r'[: -]+', c or '-') for c in cells):continue
            if headers is None:headers=cells;continue
            expanded.append(cells[0]+': '+ '; '.join(h+': '+v for h,v in zip(headers[1:],cells[1:])))
        else:
            headers=None;expanded.append(line)
    text='\n'.join(expanded)
    text=re.sub(r'\bno (monthly premium|premium|medical deductible|deductible)\b',r'\1 $0',text,flags=re.I)
    text = text.replace('’', "'").replace('–', '-').replace('—', '-')
    text = re.sub(r'\b([A-Z])\.(?=\s+[A-Z])', r'\1', text)
    return [s.casefold() for s in re.split(r'\n|(?<=[.!?])\s+(?=[A-Z])', text)]


def has(text, subject, pattern, *, allow_negative=False):
    for c in chunks(text):
        if not re.search(subject, c, re.I) or not re.search(pattern, c, re.I):
            continue
        if not allow_negative and re.search(r"\b(?:not|never|incorrect|wrong|doesn't|isn't|cannot)\b", c):
            continue
        if re.search(r'\b(?:reference|example|ignore|hypothetical)\b', c):
            continue
        return True
    return False


def money(n):
    a,b=f'{n:.2f}'.split('.')
    a=f'{int(a):,}'.replace(',', '[, ]?')
    number=a+(r'(?:\.00)?' if b=='00' else r'\.'+b)
    return r'(?:\$\s*'+number+r'(?!\d|\.\d)|(?<![\d.])'+number+r'\s*(?:dollars?|USD)\b)'


def metric(label,n):
    # Do not let an amount for another property or a reference number satisfy a fact.
    m=money(n)
    return '(?:'+label+r')\s*(?:is|of|:|=|costs|was)?\s*'+m+'|'+m+r'\s*(?:(?:per|a|each)\s+(?:month|year)\s+)?(?:'+label+')'



def currency_consistent(text,subject,label,expected):
    found=[]
    for clause in chunks(text):
        if not re.search(subject,clause,re.I):continue
        for m in re.finditer('(?:'+label+r')\s*(?:is|of|:|=|costs|was)?\s*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)',clause,re.I):
            found.append(float(m[1].replace(',','')))
    return all(abs(n-expected)<.001 for n in found)

def check_answers(judge,i,a):
    def f(label,subject,pattern,negative=False):
        judge.check('answer_'+label,has(a,subject,pattern,allow_negative=negative),label)
    if i in (1,14):
        for subject,label,n in [(r'part a','deductible',1736),(r'part b','deductible',283)]:
            judge.check('consistent_'+subject, currency_consistent(a,subject,label,n),'Reject contradictory amounts for this deductible')
    if i==5:
        for subject,p,d,l in [('aetna',0,0,6700),('blue cross',54,199,7550)]:
            for label,n in [('premium',p),('deductible',d),('limit',l)]:
                judge.check('consistent_'+subject+label,currency_consistent(a,subject,label,n),'Reject contradictory plan costs')
    if i==7:
        for subject,paid,owed in [('colonoscopy',1736,0),('test strips',77.12,19.28)]:
            for label,n in [('paid',paid),('billed',owed)]:
                judge.check('consistent_'+subject+label,currency_consistent(a,subject,label,n),'Reject contradictory claim amounts')
    if i==0:
        f('monitor_part_b',r'monitor',r'part b');f('strips_part_b',r'(?:strips|both)',r'part b')
        f('home_prescription',r'monitor',r'prescrib.{0,50}(?:home|house)|home.{0,50}prescrib')
        f('enrolled_supplier',r'(?:supplier|doctor)',r'enrolled.{0,15}medicare')
        f('monitor_share',r'(?:monitor|both)',r'20\s*%|twenty percent')
        f('strips_share',r'(?:strips|both)',r'20\s*%|twenty percent')
        f('deductible_condition',r'(?:20\s*%|twenty percent)',r'after.{0,25}(?:part b )?deductible')
        f('assignment_condition',r'(?:20\s*%|twenty percent)',r'assignment')
        f('annual_deductible',r'part b',r'deductible.{0,20}'+money(283))
    elif i==1:
        f('part_a_deductible',r'part a',metric('deductible',1736));f('part_b_deductible',r'part b',metric('deductible',283))
        f('hospital_days',r'(?:hospital|inpatient).{0,30}(?:1-60|1 to 60|first 60)',money(0))
        f('snf_coinsurance',r'(?:snf|nursing).{0,35}(?:21-100|21 to 100)',money(217)+r'.{0,15}day')
        f('hospital_stay',r'(?:hospital|inpatient).{0,20}stay',r'(?:3|three).{0,20}days')
        f('waiver',r'(?:aco|accountable care)',r'(?:waiver|waived)')
        f('snf_limit',r'(?:snf|nursing)',r'100.{0,15}days.{0,25}benefit period')
        f('same_period',r'part a.{0,20}deductible',r'(?:not charged again|only once|no second|not pay.{0,15}again).{0,50}same (?:benefit )?period',True)
    elif i==2:
        for who,year,school in [(r'bailey|goodwin',2020,r'(?:school.{0,25}(?:other|unspecified|not (?:named|specified))|(?:other|unspecified).{0,15}school)'),(r'clinton|pong',2010,r'university of hawaii')]:
            f(str(year)+'_assignment',who,r'(?:accepts?|yes.{0,15}).{0,30}assignment|assignment.{0,10}yes')
            f(str(year)+'_telehealth',who,r'(?:offers?|yes.{0,10}).{0,10}telehealth|telehealth.{0,10}(?:yes|available)')
            f(str(year)+'_school',who,school);f(str(year)+'_graduation',who,r'(?:graduat\w*|year).{0,15}\b'+str(year)+r'\b')
        f('office_phone',r'(?:both|phone|office)',r'617[) .-]*903[ .-]*5000')
    elif i==3:
        for who,rating,owner,count in [(r'memorial',3,'private',8),(r'st\.? john',2,'church',6)]:
            f(owner+'_rating',who,rf'(?:rating.{0,10}{rating}\s*(?:out of|of|/|stars)|{rating}\s*(?:out of 5|stars))')
            f(owner+'_ownership',who,rf'(?:non[ -]?profit|nonprofit).{{0,20}}{owner}')
            f(owner+'_safety',who,rf'\b{count}\s+safety(?:[ -]measure)?|safety(?:[ -]measure)?s?\s*[:=]?\s*{count}\b')
        f('recommendation',r'memorial',r'recommend|higher');f('contact',r'memorial|its phone',r'217[) .-]*788[ .-]*3000')
    elif i==4:
        f('walker_part_b',r'walker',r'part b');f('prescription',r'walker|dme',r'prescrib.{0,25}home');f('medical_necessity',r'walker|dme',r'medically necessary')
        f('cost',r'(?:20\s*%|twenty percent)',r'after.{0,25}(?:part b )?deductible');f('assignment_condition',r'(?:20\s*%|twenty percent)',r'assignment');f('supplier_enrollment',r'supplier',r'enrolled.{0,15}medicare')
        f('closest_supplier',r'closest|nearest',r'king soopers');f('supplier_phone',r'king soopers',r'303[) .-]*571[ .-]*1943');f('supplier_assignment',r'king soopers|it accepts',r'accepts.{0,20}assignment|assignment.{0,10}yes')
    elif i==5:
        for who,prem,ded,limit,rating in [(r'aetna',0,0,6700,'4.5'),(r'blue cross',54,199,7550,'3')]:
            f(who+'_premium',who,metric(r'(?:monthly )?premium',prem));f(who+'_deductible',who,metric(r'(?:medical )?deductible',ded));f(who+'_limit',who,metric(r'(?:out.of.pocket )?limit',limit));f(who+'_rating',who,r'(?:rating\s*[:=]?\s*'+re.escape(rating)+r'(?![\d.])|'+re.escape(rating)+r'\s*stars)')
        f('choice',r'aetna',r'recommend|choose|meets both');f('part_b',r'part b',r'(?:keep|continue|must|still).{0,20}pay');f('otc',r'aetna',r'over.the.counter allowance');f('nurse',r'blue cross',r'24/7 nurse line')
    elif i in (6,10,11):
        f('confirmed',r'order|request|copies|copy',r'received|confirmed|accepted|ordered|placed|went through')
        for title,num,qty,fmt in ({6:[('medicare.{0,5}you 2027','10050',2,'standard')],10:[('cancer','11931',2,'standard'),('medigap','02110',1,'large')],11:[('medicare appeals','11525',1,'large')]}[i]):
            f(num+'_identity',title,r'\b'+num+r'\b' if i!=6 else title)
            f(num+'_format',title,fmt+r' print')
            if i!=11:f(num+'_quantity',title,rf'\b(?:{qty}|'+('two' if qty==2 else 'one')+r')\s*(?:standard print |large print )?cop(?:y|ies)')
        addr={6:('12 Elm Court','Denver','CO','80204'),10:('12 Sunset Terrace','Springfield','IL','62704'),11:('302 W Edwards St','Springfield','IL','62704')}[i]
        for v in addr:f('address_'+v,r'.',r'\b'+re.escape(v)+r'\b')
    elif i==7:
        for who,paid,owed in [('colonoscopy',1736,0),('test strips',77.12,19.28)]:
            f(who+'_paid',who,metric(r'(?:medicare )?paid',paid));f(who+'_owed',who,r'(?:billed|owes?|owed|responsibility).{0,10}'+money(owed))
        f('total',r'total|combined',money(19.28));f('notice_period',r'notice|period',r'june 1.{0,20}august 31,? 2026')
    elif i==8:
        f('premium',r'part b|premium',money(202.90));f('date',r'due',r'(?:2026-10-25|october 25,? 2026|25 october 2026|10/25/2026)');f('paid',r'premium|bill',r'\bpaid\b');f('method',r'bank account',r'4821')
    elif i==9:
        f('number',r'medicare',r'1eg4[ -]?te5[ -]?mk73');f('replacement',r'card|status',r'(?:7-10|7 to 10).{0,10}days')
        for v in ['45 Meadow Lane','Buffalo Grove','IL','60089']:f(v,r'.',r'\b'+re.escape(v)+r'\b')
    elif i==12:
        f('subject',r'reminder|message|subject',r'medicare open enrollment starts october 15');f('dates',r'enrollment',r'october 15.{0,20}december 7,? 2026')
        f('choices',r'medicare advantage|drug plan',r'join.{0,15}switch.{0,15}drop')
    elif i==13:
        f('part',r'hospice',r'part a');f('certification',r'hospice doctor',r'regular doctor|personal doctor|your doctor');f('life_expectancy',r'(?:life expectancy|terminal)',r'(?:6|six) months or less')
        f('hospice_cost',r'hospice care',money(0)+r'|\bnothing\b|no cost');f('drug_copay',r'(?:drug|prescription)',money(5))
        f('provider',r'1st choice hospice',r'936[) .-]*295[ .-]*7100')
    elif i==14:
        f('enrollment',r'enrollment|medicare',r'automatic');f('agency',r'(?:social security|ssa)',r'(?:part a.{0,15}part b|enrollment)');f('tty',r'tty',r'877[) .-]*486[ .-]*2048')
        f('part_b_premium',r'part b',r'(?:monthly.{0,10}premium|premium.{0,10}month).{0,10}'+money(202.90));f('part_b_deductible',r'part b',metric('deductible',283));f('part_a_deductible',r'part a',metric('deductible',1736))


PATHS={
0:['/coverage/blood-sugar-monitors','/coverage/blood-sugar-test-strips','/basics/costs/medicare-costs'],
1:['/basics/costs/medicare-costs','/coverage/skilled-nursing-facility-care'],
2:['/care-compare/provider/362','/care-compare/provider/367'],
3:['/care-compare/provider/3045','/care-compare/provider/3046'],
4:['/coverage/walkers','/medical-equipment-suppliers/results'],
5:['/plan-compare/plan/1','/plan-compare/plan/4'],
6:['/publication-ordering/10050'],7:['/my/messages/1','/my/claims'],8:['/my/premiums'],
9:['/my/account-settings','/my/account-settings/get-my-medicare-card'],
10:['/publication-ordering/11931','/publication-ordering/02110'],11:['/publication-ordering/11525'],
12:['/my/messages/3'],13:['/coverage/hospice-care','/care-compare/provider/1459'],
14:['/basics/get-started-with-medicare','/basics/costs/medicare-costs','/talk-to-someone']}


def dbrows(path,table):
    cols=table_columns(path,table)
    return [dict(zip(cols,row)) for row in table_rows(path,table)]


def check_state(judge,i,a,b):
    before={t:dbrows(a,t) for t in TABLES};after={t:dbrows(b,t) for t in TABLES}
    allowed=set();uid=2 if i==8 else 1
    def additions(table):
        allowed.add(table);old={r['id']:r for r in before[table]};new={r['id']:r for r in after[table]}
        judge.check(table+'_preserve_existing',all(new.get(k)==v for k,v in old.items()),'Existing rows must be unchanged')
        return [v for k,v in new.items() if k not in old]
    def changed(table,expected):
        allowed.add(table)
        judge.check(table+'_exact_delta',sorted(after[table],key=lambda r:r['id'])==sorted(expected,key=lambda r:r['id']),'Only requested fields change')
    if i in (7,8,9,10,12):
        rows=additions('login_events')
        judge.check('login_owner',bool(rows) and all(r['user_id']==uid and r['when']=='2026-09-23' and r['method']=='Medicare.gov account' for r in rows),'Logins only for requested account')
    if i==8:
        expected=[dict(r) for r in before['premium_bills']]
        for r in expected:
            if r['user_id']==2 and r['status']=='Due':r.update(status='Paid',paid_date='2026-09-23',method='Bank account ending 4821')
        changed('premium_bills',expected)
    if i==9:
        expected=[dict(r) for r in before['mailing_addresses']]
        for r in expected:
            if r['user_id']==1:r['is_current']=0
        old_ids={r['id'] for r in expected};new=[r for r in after['mailing_addresses'] if r['id'] not in old_ids]
        judge.check('one_new_address',len(new)==1,'One replacement current mailing address')
        if len(new)==1:expected.append(dict(id=new[0]['id'],user_id=1,line1='45 Meadow Lane',line2=None,city='Buffalo Grove',state='IL',zip='60089',is_current=1,effective_date='2026-09-23'))
        changed('mailing_addresses',expected)
        rows=additions('card_requests')
        judge.check('card_request',len(rows)==1 and {k:v for k,v in rows[0].items() if k!='id'}==dict(user_id=1,reason='lost',requested_at='2026-09-23',status='Mailing in 7-10 days'),'Exact lost card request')
    if i in (7,12):
        expected=[dict(r) for r in before['messages']]
        for r in expected:
            if r['id']==(1 if i==7 else 3):r['is_read']=1
        changed('messages',expected)
    if i in (6,10,11):
        rows=additions('pub_orders');pubs={r['product_number']:r['id'] for r in before['publications']}
        specs={6:[('10050',2,'Standard Print',None,'12 Elm Court','Denver','CO','80204')],10:[('11931',2,'Standard Print',1,'12 Sunset Terrace','Springfield','IL','62704-1234'),('02110',1,'Large Print',1,'12 Sunset Terrace','Springfield','IL','62704-1234')],11:[('11525',1,'Large Print',None,'302 W Edwards St','Springfield','IL','62704')]}[i]
        expected=[dict(publication_id=pubs[num],quantity=q,format=fmt,user_id=u,ship_line1=l,ship_city=c,ship_state=st,ship_zip=z,created_at='2026-09-23',status='Processing') for num,q,fmt,u,l,c,st,z in specs]
        actual=[{k:v for k,v in r.items() if k!='id'} for r in rows]
        judge.check('orders_exact',sorted(actual,key=lambda r:r['publication_id'])==sorted(expected,key=lambda r:r['publication_id']),'Exact products, formats, quantities, owner, full address and status')
    for table in set(TABLES)-allowed:judge.check('preserve_'+table,before[table]==after[table],'No unrelated changes')


def run_checks(judge,traj,initial_db,after_db):
    i=int(traj['task_id'].split('--')[-1]);check_trajectory_identity(judge,traj,f'Medicare.gov--{i}')
    task=json.loads((Path(__file__).parents[1]/'tasks.jsonl').read_text().splitlines()[i])
    judge.check('current_prompt',traj.get('task')==task['ques'],'Trajectory must use the current prompt')
    for path in PATHS[i]:judge.check('visited_'+path,navigated_to_path(traj,path),'Relevant content evidence')
    if i in (7,8,9,10,12):check_signed_in_as(judge,traj,'bob.c@test.com' if i==8 else 'alice.j@test.com')
    if i in (6,10,11):
        judge.check('confirmation_visited',any(urlparse(u).path.startswith('/publication-orders/') for u in site_urls(traj)),'Must reach saved-order confirmation')
    if i==4:
        judge.check('walker_search',any(urlparse(u).path=='/medical-equipment-suppliers/results' and parse_qs(urlparse(u).query).get('location')==['80204'] and 'walker' in ' '.join(parse_qs(urlparse(u).query).get('equipment',[])).lower() for u in site_urls(traj)),'Correct ZIP and equipment together')
    check_answers(judge,i,final_answer(traj));check_state(judge,i,initial_db,after_db)
