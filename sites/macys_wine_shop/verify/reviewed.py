"""Reviewed task contracts and preservation checks, September 2026."""
import re
import hashlib
def stable_password_hash(value):
    return hashlib.sha256(("macys_wine_shop.benchmark:"+value).encode()).hexdigest()
from verify_lib import (check_trajectory_identity,check_read_only,check_visited_path,
                       check_only_tables_changed,check_signed_in_as,final_answer,
                       contains_phrase,site_urls,normalized_url_path)
from review_common import current_task,order_integrity,delta,same_except,fact,amount,number,rows


def review(judge,traj,a,b,original):
    i=current_task(judge,traj,'macys_wine_shop');answer=final_answer(traj)
    if i==10:
        check_trajectory_identity(judge,traj,'MacysWineShop--10')
        for path in ['/pages/wine-club','/products/cellar-select-merlot-3-pack','/pages/shipping-policy']:
            check_visited_path(judge,traj,'read_'+path,path)
        check_read_only(judge,a,b)
        for name,entity,pattern in [
            ('red_case_wines',r'all reds|red.{0,15}club',r'(?:6|six)\s+(?:unique|different)\s+(?:red\s+)?wines'),
            ('red_case_bottles',r'all reds|red.{0,15}club',r'(?:12|twelve)\s+bottles'),
            ('club_intro',r'intro',amount(99.99)),('club_renewal',r'renew',amount(149.99)),
            ('club_frequency',r'club|shipment',r'13\s+weeks|quarterly'),
            ('merlot_wines',r'merlot',r'(?:3|three)\s+(?:different|unique)\s+wines'),
            ('merlot_bottles',r'merlot',r'(?:3|three)[ -]?(?:pack|bottles)'),
            ('merlot_delivered',r'merlot|pack',amount(61.97)),
        ]:judge.check(name,fact(answer,entity,pattern),'fact bound to its option')
        judge.check('skip_cancel',bool(re.search(r'(?:skip|cancel)',answer,re.I)) and '855' in answer and '966' in answer and '2224' in answer,'support contact for skipping/canceling')
        judge.check('one_time_recommendation',bool(re.search(r'(?:recommend|choose|prefer).{0,100}(?:merlot|3.pack)|(?:merlot|3.pack).{0,100}(?:one.time|non.recurring|without recurring)',answer,re.I)),'recommend the one-time pack for this goal')
    elif i==14:
        check_trajectory_identity(judge,traj,'MacysWineShop--14');check_signed_in_as(judge,traj,'carol.d@test.com')
        check_visited_path(judge,traj,'password_form','/account/password')
        check_only_tables_changed(judge,a,b,{'users'})
        added,removed,changed=delta(a,b,'users')
        judge.check('only_carol_password',not added and not removed and len(changed)==1 and changed[0][0]['id']==3 and same_except(*changed[0],'password_hash') and changed[0][1]['password_hash']==stable_password_hash('AutumnCellar77!'),'only Carol password is changed and retained')
        observed='\n'.join(s.get('observed_text','') for s in traj.get('steps',[]))
        judge.check('old_password_rejected','Incorrect email or password' in observed,'browser shows old credential rejection')
        judge.check('new_password_login',normalized_url_path(traj.get('final_url') or traj['steps'][-1].get('url'))=='/account' and 'Carol' in traj['steps'][-1].get('observed_text',''),'ends signed in as Carol')
        judge.check('answer_password_result',bool(re.search(r'(?:old|original).{0,50}(?:no longer|fail|reject|does not|doesn.t)',answer,re.I)) and bool(re.search(r'new.{0,40}(?:work|sign|success)',answer,re.I)),'reports old rejection and new success')
    else:
        original(judge,traj,a,b)
        user={5:2,6:3,8:4,15:5}.get(i)
        order_integrity(judge,a,b,'macys_wine_shop',user)
        orders=delta(a,b,'orders')[0]
        if orders:
            judge.check('answer_actual_order_total',fact(answer,r'total',amount(orders[0]['total'])),'reported total belongs to the new order')
        if i==15:
            add,rem,ch=delta(a,b,'users')
            judge.check('registration_preservation',len(add)==1 and not rem and not ch and add[0]['password_hash']==stable_password_hash('CellarDoor88!'),'new user has requested password; original users preserved')
            its=delta(a,b,'order_items')[0]
            judge.check('exact_pinot_quantity',len(its)==1 and its[0]['quantity']==3,'exactly three requested bottles')
        if i==6:
            add,rem,ch=delta(a,b,'addresses')
            judge.check('preserve_prior_addresses',len(add)==1 and not rem and not ch and add[0]['user_id']==3 and not add[0]['is_default'] and add[0]['phone']=='(303) 555-0148','one second address, default and prior records unchanged')
    if i==0:
        for entity,price,rating in [('Della Flora',16.99,4.2),('Cremaschi',17.49,4.6)]:
            judge.check(entity+'_price',fact(answer,entity,amount(price)),'price belongs to wine')
            judge.check(entity+'_rating',fact(answer,entity,number(rating)+r'\s*(?:stars|out of 5|/\s*5)|rating\s*(?:of|is|:)?\s*'+number(rating)),'rating belongs to wine')
    if i==12:
        for entity,abv,year,competition in [('House Party',11,2026,'Critics Challenge'),('Misirlou',13.5,2025,'Harvest Challenge')]:
            judge.check(entity+'_award',fact(answer,entity,r'gold') and fact(answer,entity,competition) and fact(answer,entity,str(year)),'medal, competition and year bound to wine')
            judge.check(entity+'_abv',fact(answer,entity,number(abv)+r'\s*(?:%|percent)'),'ABV bound to wine')
