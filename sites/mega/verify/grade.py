"""Shared deterministic MEGA task grading with exact persisted state deltas."""
import json
import math
import re
import sqlite3
from urllib.parse import urlsplit, parse_qs

import answers
from verify_lib import Judge, load_run, parse_args, resolve_db, navigated_path, shot_at, url_path


READ_ONLY = {0, 1, 9, 10, 11, 13, 15}
CART_TASKS = {2: ('david.k@test.com', 'pro-ii', 'yearly', 1),
              4: ('alice.j@test.com', 'business-pro', None, 5),
              12: ('bob.c@test.com', 's4-fixed-storage', None, 1),
              17: ('bob.c@test.com', 'pro-flexi', 'yearly', 1)}


def rows(path):
    if not path:
        raise ValueError('missing snapshot')
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as c:
        c.row_factory = sqlite3.Row
        return {t: [dict(r) for r in c.execute(f'SELECT * FROM "{t}" ORDER BY 1')]
                for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def one(data, table, **keys):
    found = [r for r in data[table] if all(r[k] == v for k,v in keys.items())]
    if len(found) != 1:
        raise ValueError(f'expected one {table} row matching {keys}, found {len(found)}')
    return found[0]


def key(row):
    return row.get('id', row.get('user_id'))


def preserved(before, after, changes=None, additions=None, removals=None):
    """Allow only specifically listed rows/fields; preserve all other values."""
    changes, additions, removals = changes or {}, additions or {}, removals or {}
    if before.keys() != after.keys():
        return False
    for table in before:
        b, a = ({key(r):r for r in data[table]} for data in [before,after])
        if set(a)-set(b) != set(additions.get(table,[])) or set(b)-set(a) != set(removals.get(table,[])):
            return False
        for rid in set(a)&set(b):
            permitted = changes.get(table,{}).get(rid,set())
            if {k:v for k,v in a[rid].items() if k not in permitted} != {k:v for k,v in b[rid].items() if k not in permitted}:
                return False
    return True


def new_rows(before, after, table):
    ids={key(r) for r in before[table]}
    return [r for r in after[table] if key(r) not in ids]


def final_path(t):
    last=(t.get('steps') or [{}])[-1]
    urls=[u for u in [t.get('final_url'),last.get('url_after'),last.get('url')] if u]
    paths={url_path(u).rstrip('/') or '/' for u in urls}
    return paths.pop() if len(paths)==1 else None


def visit(j,t,path):
    # Exact path matching prevents /plans/pro-i from matching /plans/pro-ii.
    paths=[path] if isinstance(path,str) else path
    ok=any(navigated_path(t,p) for p in paths)
    shots=any(shot_at(t,p)[0] for p in paths)
    j.check('visited_'+paths[0],ok and shots,str(paths))


def searched(j, t, paths, target):
    stop = {'the', 'for', 'with', 'and', 'how', 'what', 'which', 'mega', 'files'}
    matched = False
    for step in t.get('steps', []):
        url = urlsplit(step.get('url', ''))
        query = parse_qs(url.query).get('q', [''])[0]
        words = [w for w in re.findall(r"[a-z0-9]+", query.casefold()) if len(w)>1 and w not in stop]
        if url.path in paths and any(w in target.casefold() for w in words):
            matched = True
    j.check('relevant_search', matched, 'observed a search relevant to the requested target')


def grade(number):
    args=parse_args();j=Judge(f'MEGA--{number}',True);t=load_run(args.run_dir)
    fa=(t.get('final_answer') or '').strip()
    j.bind_run(t,require_answer=number in READ_ONLY|{4,6})
    try:
        b=rows(resolve_db(args.initial_db,args.container,'instance_seed'))
        a=rows(resolve_db(args.after_db,args.container,'instance'))
        if number in READ_ONLY:
            j.check('read_only',preserved(b,a),'all tables and fields unchanged')
        if number in CART_TASKS or number in {3,5,6,7,8,9,14,16}:
            visit(j,t,'/login')
        if number in CART_TASKS:
            email,slug,cycle,seats=CART_TASKS[number]
            user=one(b,'users',email=email);plan=one(b,'plans',slug=slug);uid=user['id']
            visit(j,t,'/plans/'+slug);visit(j,t,'/checkout')
            if number==4:
                visit(j,t,'/plans/pro-ii')
                j.check('answer_comparison',answers.business_winner(fa),fa)
            if number==12:
                j.check('object_storage_filter',any(urlsplit(s.get('url','')).path=='/pricing' and parse_qs(urlsplit(s.get('url','')).query).get('category')==['objectstorage'] for s in t.get('steps',[])),'pricing filter observed')
            if number==17:visit(j,t,'/plans/s4-fixed-storage')
            cart=one(a,'checkout_carts',user_id=uid)
            j.check('final_checkout',final_path(t)=='/checkout',str(final_path(t)))
            j.check('cart_plan_cycle_seats',cart['plan_id']==plan['id'] and cart['seats']==seats and (cycle is None or cart['billing_cycle']==cycle) and cart['billing_cycle'] in {'monthly','yearly'},str(cart))
            existed=any(r['user_id']==uid for r in b['checkout_carts'])
            j.check('preserve_other_state',preserved(b,a,{'checkout_carts':{uid:{'plan_id','billing_cycle','seats'}}},{} if existed else {'checkout_carts':[uid]}),'only requested account cart changes; all orders unchanged')
        elif number==3:
            user=one(b,'users',email='alice.j@test.com');uid=user['id'];plan=one(b,'plans',slug='pro-i')
            visit(j,t,'/plans/pro-i');visit(j,t,'/checkout')
            new=new_rows(b,a,'subscription_orders');j.check('one_order',len(new)==1,str(new))
            if len(new)==1:
                order=new[0];method=one(b,'payment_methods',user_id=uid,is_default=1)
                expected={'user_id':uid,'plan_id':plan['id'],'payment_id':method['id'],'billing_cycle':'monthly','seats':1,'status':'active','subtotal':round(plan['monthly_price'],2),'tax':round(plan['monthly_price']*.07,2)}
                expected['total']=round(expected['subtotal']+expected['tax'],2)
                j.check('order_details',all(order[k]==v for k,v in expected.items()),str(order))
                visit(j,t,'/orders/'+order['order_number'])
                j.check('order_confirmation',final_path(t)=='/orders/'+order['order_number'],str(final_path(t)))
                j.check('active_plan',one(a,'users',id=uid)['plan_id']==plan['id'])
                j.check('cart_empty',not any(r['user_id']==uid for r in a['checkout_carts']))
                removed=[uid] if any(r['user_id']==uid for r in b['checkout_carts']) else []
                j.check('preserve_other_state',preserved(b,a,{'users':{uid:{'plan_id'}}},{'subscription_orders':[order['id']]},{'checkout_carts':removed}))
        elif number in {5,6}:
            user=one(b,'users',email='alice.j@test.com');uid=user['id']
            name='Atlas b-roll selects.mov' if number==5 else 'Atlas launch footage.mov'
            old=one(b,'cloud_items',user_id=uid,name=name);item=one(a,'cloud_items',id=old['id'])
            visit(j,t,'/cloud/item/'+old['slug'])
            if number==5:
                emails={x.strip().casefold() for x in item['shared_with'].split(',') if x.strip()}
                j.check('share_exact_recipients',emails=={'bob.c@test.com','carol.d@test.com'})
                j.check('created_share_link',not old['share_link'] and bool(re.fullmatch(r'https://mega\.nz/file/[A-Za-z0-9_-]+#webharbor',item['share_link'] or '')))
                allowed={'shared_with','share_link'}
            else:
                visit(j,t,['/cloud','/drive'])
                searched(j,t,{'/cloud','/drive'},' '.join(str(old[k]) for k in ['name','folder','extension','content_summary']))
                largest=max((r for r in b['cloud_items'] if r['user_id']==uid and r['extension']=='mov'),key=lambda r:r['size_mb'])
                j.check('largest_file',largest['id']==old['id'] and answers.positive(fa,r'\batlas launch footage(?:\.mov)?\b'),fa)
                j.check('favorite',not old['favorite'] and item['favorite']==1)
                allowed={'favorite'}
            j.check('preserve_other_state',preserved(b,a,{'cloud_items':{old['id']:allowed}}))
        elif number==7:
            uid=one(b,'users',email='alice.j@test.com')['id'];visit(j,t,['/cloud','/drive'])
            new=new_rows(b,a,'cloud_items');j.check('two_new_items',len(new)==2,str(new))
            folder=one(a,'cloud_items',user_id=uid,name='Q3 Press Kit',item_type='folder',folder='/Projects/Atlas')
            file=one(a,'cloud_items',user_id=uid,name='press-summary.pdf',item_type='file',folder='/Projects/Atlas/Q3 Press Kit')
            j.check('new_folder_and_file',folder in new and file in new)
            j.check('file_properties',file['extension']=='pdf' and math.isclose(file['size_mb'],4.2,abs_tol=1e-9) and not file['shared_with'] and not file['share_link'])
            old=one(b,'users',id=uid);user=one(a,'users',id=uid)
            j.check('storage_accounting',math.isclose(user['storage_used_gb'],old['storage_used_gb']+4.2/1024,abs_tol=1e-9))
            j.check('preserve_other_state',preserved(b,a,{'users':{uid:{'storage_used_gb'}}},{'cloud_items':[r['id'] for r in new]}))
        elif number==8:
            uid=one(b,'users',email='alice.j@test.com')['id'];visit(j,t,'/vault');new=new_rows(b,a,'vault_items')
            j.check('one_new_entry',len(new)==1,str(new))
            if len(new)==1:
                r=new[0];j.check('vault_properties',r['user_id']==uid and re.fullmatch(r'atlas staging(?: site)?',r['title'].casefold()) is not None and r['username']=='alice_editor' and r['category']=='Client' and r['strength']=='Strong' and r['two_factor']==1,str(r))
                j.check('preserve_other_state',preserved(b,a,additions={'vault_items':[r['id']]}))
        elif number==14:
            uid=one(b,'users',email='bob.c@test.com')['id'];new=new_rows(b,a,'support_tickets');visit(j,t,'/contact')
            j.check('one_new_ticket',len(new)==1,str(new))
            if len(new)==1:
                r=new[0];visit(j,t,'/support/tickets/'+r['ticket_number'])
                j.check('ticket_properties',r['user_id']==uid and r['priority']=='High' and r['category']=='Object storage' and r['status']=='Open' and answers.ticket_request(r['subject']+'; '+r['message']),str(r))
                j.check('preserve_other_state',preserved(b,a,additions={'support_tickets':[r['id']]}))
        elif number==16:
            uid=one(b,'users',email='alice.j@test.com')['id'];visit(j,t,'/account/edit');r=one(a,'users',id=uid)
            j.check('profile_properties',r['company']=='Riverlight Studio Labs' and r['two_factor_enabled']==1 and r['recovery_key_saved']==1,str({k:r[k] for k in ['company','two_factor_enabled','recovery_key_saved']}))
            j.check('preserve_other_state',preserved(b,a,{'users':{uid:{'company','two_factor_enabled','recovery_key_saved'}}}))
        elif number==0:
            visit(j,t,'/storage');j.check('two_highlights',answers.highlights(fa),fa)
        elif number==1:
            visit(j,t,'/help/save-your-recovery-key');searched(j,t,{'/help'},one(b,'help_articles',slug='save-your-recovery-key')['body']);j.check('recovery_policy',answers.recovery(fa),fa)
        elif number==9:
            visit(j,t,'/vault');searched(j,t,{'/vault'},'Old vendor FTP weak studio-old legacy');j.check('vendor_without_2fa',answers.old_vendor(fa),fa)
        elif number in {10,11}:
            package='MEGAcmdSetup64.exe' if number==10 else 'MEGA Pass Chrome extension';r=one(b,'downloads',package_name=package)
            visit(j,t,'/downloads');visit(j,t,f"/downloads/{r['id']}")
            ok=answers.checksum_answer(fa,r['checksum']) if number==10 else answers.package_version(fa,r['version'])
            j.check('download_facts',ok,fa)
        elif number==13:
            visit(j,t,'/business');j.check('team_dashboard',answers.positive(fa,r'\bteam dashboard\b'),fa)
        elif number==15:
            visit(j,t,'/help/recover-from-ransomware');searched(j,t,{'/help'},'ransomware recovery '+one(b,'help_articles',slug='recover-from-ransomware')['body']);j.check('disconnect_affected_device',answers.disconnect(fa),fa)
    except (ValueError, KeyError, TypeError, sqlite3.Error) as error:
        j.check('fixture_or_state',False,str(error))
    j.emit()
