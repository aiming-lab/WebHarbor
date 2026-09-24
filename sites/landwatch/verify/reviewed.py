"""Coherent land research and inquiry tasks with exact snapshot deltas."""
import json,re
from verify_lib import (check_trajectory_identity,check_read_only,check_visited_path,
    check_only_tables_changed,final_answer,contains_phrase,navigated_to_path,
    normalized_url_path,site_urls,stable_password_hash)
from review_common import rows,delta,same_except,current_task,fact,amount,number

PROPERTIES={0:[425766087],3:[426260135,426632638,427919951],6:[427404605,428133842,427994329],7:[420217258,425922430],8:[419682125,422917076],9:[425766087,428212638],10:[427843237],11:[427843237],12:[428237808,421063401,424096341],14:[427200023,423734861]}
FIELDS={0:['price','acres'],3:['county','price','acres'],6:['acres','state','auction_start'],7:['county','price','acres','types'],8:['status','price','acres','types'],9:['price','acres'],11:['acres','auction_start'],12:['state','price','acres','beds','baths'],14:['county','price','acres']}

def entity(l):
    title=l['title'];return re.escape(title).replace(r'\&',r'(?:&|and)')

def property_facts(judge,traj,answer,l,fields):
    pid=l['pid'];path=f"/{l['canonical_slug']}/pid/{pid}"
    judge.check(f'visited_property_{pid}',any(re.search(rf'/pid/{pid}(?:$|[?#])',u) for u in site_urls(traj)),'inspect the candidate detail')
    for field in fields:
        v=l["property_types"] if field=="types" else l[field]
        if field=='price':pat=amount(v)
        elif field=='acres':
            n=f'{float(v):g}';pat=r'(?<!\d)'+re.escape(n).replace(',',r'[, ]?')+r'\s*(?:acres|ac)\b'
            if float(v).is_integer() and v>=1000:pat=r'(?:'+re.escape(f'{int(v):,}')+'|'+n+r')\s*(?:acres|ac)\b'
        elif field in ['beds','baths']:
            pat=number(v or 0)+r'\s*(?:'+('beds|bedrooms' if field=='beds' else 'baths|bathrooms')+')'
        elif field=='types':
            for kind in (v or '').split(','):
                judge.check(f'{pid}_type_{kind}',fact(answer,entity(l),re.escape(kind)),'property type belongs to candidate')
            continue
        elif field=='auction_start':
            from datetime import datetime
            d=datetime.fromisoformat(v);pat='(?:'+re.escape(v[:10])+'|'+d.strftime('%B')+r'\s+'+str(d.day)+r',?\s+'+str(d.year)+')'
        else:pat=re.escape(str(v))
        judge.check(f'{pid}_{field}',fact(answer,entity(l),pat),f'{field} is correctly attributed to {l["title"]}')


def review(judge,traj,a,b,original):
    i=current_task(judge,traj,'landwatch');answer=final_answer(traj)
    # Retain the original detailed contracts for unchanged coherent tasks.
    if i in [1,2,4,5,13]:
        original(judge,traj,a,b);return
    check_trajectory_identity(judge,traj,f'LandWatch--{i}')
    listings={l['pid']:l for l in rows(a,'listings')}
    pids=PROPERTIES.get(i,[])
    if i==0:
        pids=[427317511,426764168,425766087]
        # Resolve the first Austin result from the frozen location, not a guessed ID.
        austin=sorted([l for l in listings.values() if l['city']=='Austin'],key=lambda l:l['sort_rank'])[0]
        pids[0]=austin['pid']
        for path in ['/texas-land-for-sale/austin','/texas-land-for-sale/harris-county','/texas-land-for-sale/boerne']:
            check_visited_path(judge,traj,'location_'+path,path)
        for name,count in [('Austin',1),('Harris',1),('Boerne',4)]:judge.check('count_'+name,fact(answer,name,number(count)+r'\s+listings?'),'location listing count')
    for pid in pids:property_facts(judge,traj,answer,listings[pid],FIELDS.get(i,[]))
    if i in [0,3,7,12,14]:
        vals=[listings[pid] for pid in pids];winner=min(vals,key=lambda l:l['price']/l['acres'])
        for l in vals:
            cost=round(l['price']/l['acres'],2)
            pat=r'(?:'+amount(cost)+'|'+amount(round(cost))+r')\s*(?:per\s+acre|/\s*acre)'
            judge.check('unit_value_'+str(l['pid']),fact(answer,entity(l),pat),'price divided by acreage; nearest dollar is acceptable')
        judge.check('value_recommendation',fact(answer,entity(winner),r'best value|lowest price.per.acre|recommend|most land for'), 'recommend the lowest price per acre')
    if i in [3,6,7,14]:
        count={3:81,6:25,7:5,14:11}[i]
        judge.check('result_count',bool(re.search(number(count)+r'\s+(?:listings|matches|properties)',answer,re.I)),'filtered result count')
    if i==3:check_visited_path(judge,traj,'budget_results','/texas-land-for-sale/price-over-1000000')
    if i==6:
        check_visited_path(judge,traj,'hunting_auctions','/hunting-property/auctions')
        winner=max((listings[p] for p in pids),key=lambda l:l['acres'])
        judge.check('largest_auction',fact(answer,entity(winner),r'largest|most land|recommend'),'largest shortlisted auction')
        judge.check('auction_not_price',bool(re.search(r'asking price.{0,30}(?:not|undisclosed)|(?:no|without|not a).{0,30}(?:asking|stated) price|price not disclosed',answer,re.I)),'auction sentinel prices are not asking prices')
    if i==7:check_visited_path(judge,traj,'houston_region','/texas-land-for-sale/houston-region')
    if i==8:
        for path in ['/find-agent','/profile/mac-a-coalson/32197']:check_visited_path(judge,traj,'broker_'+path,path)
        for value in ['Mac A. Coalson','Coalson Real Estate','Weatherford','11','1.1','50','22.50','5896']:
            judge.check('broker_'+value,contains_phrase(answer,value) or value.replace(',','') in answer.replace(',',''),'broker identity and ranges')
    if i==14:
        from urllib.parse import urlparse,parse_qs
        wanted={'priceMin':100000,'priceMax':1000000,'acresMin':100,'acresMax':200}
        def good(u):
            q=parse_qs(urlparse(u).query)
            try:return urlparse(u).path=='/land' and all(float(q[k][0])==v for k,v in wanted.items())
            except (KeyError,ValueError):return False
        judge.check('combined_ranges',any(good(u) for u in site_urls(traj)),'both custom ranges applied together')
    if i not in [9,10,11]:
        check_read_only(judge,a,b);return
    user=2 if i==9 else (1 if i==10 else 5)
    allowed={'sessions','favorites'} if i==9 else ({'sessions','users','inquiries'} if i==10 else {'sessions','users','favorites','inquiries'})
    check_only_tables_changed(judge,a,b,allowed)
    sa,sr,sc=delta(a,b,'sessions','token')
    judge.check('own_session',not sr and not sc and len(sa)==1 and sa[0]['user_id']==user and bool(re.fullmatch('[a-f0-9]{64}',sa[0]['token'])),'one authenticated session for the correct account')
    if i in [9,11]:
        fa,fr,fc=delta(a,b,'favorites');wanted=428212638 if i==9 else 427843237
        judge.check('only_requested_favorite',not fr and not fc and len(fa)==1 and fa[0]['user_id']==user and fa[0]['pid']==wanted,'preserve all previous favorites; save only the requested property')
    if i==9:
        judge.check('favorite_count',bool(re.search(r'(?:5|five)\s+(?:saved\s+)?propert',answer,re.I)),'five saved properties')
        judge.check('acreage_difference',bool(re.search(r'918\s+acres',answer,re.I)),'larger by 918 acres')
        return
    ua,ur,uc=delta(a,b,'users')
    if i==10:
        judge.check('only_alice_phone',not ua and not ur and len(uc)==1 and uc[0][0]['id']==1 and same_except(*uc[0],'phone') and uc[0][1]['phone']=='(512) 555-0164','only Alice phone changes')
    else:
        judge.check('new_account',not ur and not uc and len(ua)==1 and ua[0]['id']==5 and ua[0]['email']=='new.landbuyer@test.com' and ua[0]['name']=='Alex Morgan' and ua[0]['password_hash']==stable_password_hash('LandBuyer2026!'),'exact new buyer identity')
    ia,ir,ic=delta(a,b,'inquiries')
    email='alice.j@test.com' if i==10 else 'new.landbuyer@test.com'
    judge.check('one_soil_inquiry',not ir and not ic and len(ia)==1 and ia[0]['user_id']==user and ia[0]['pid']==427843237 and ia[0]['email']==email and bool(re.search(r'\bsoil\b',ia[0]['message'],re.I)),'one inquiry on the selected farmland, preserving prior inquiries')
    if i==10:judge.check('inquiry_new_phone',len(ia)==1 and ia[0]['phone']=='(512) 555-0164','inquiry uses new contact number')
    for value in ['Devin Dye',email,'soil']:judge.check('inquiry_answer_'+value,contains_phrase(answer,value),'recipient, reply email and inquiry topic')
    if i==10:judge.check('answer_phone','512' in answer and '555' in answer and '0164' in answer,'updated contact number')
    check_visited_path(judge,traj,'account_confirmation','/account')
