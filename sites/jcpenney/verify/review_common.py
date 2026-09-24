"""Small deterministic grading helpers; no browser actions are prescribed."""
import json,re,sqlite3
from pathlib import Path

def rows(db,table):
    with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute(f'SELECT * FROM "{table}"')]

def delta(a,b,table,key='id'):
    before={r[key]:r for r in rows(a,table)};after={r[key]:r for r in rows(b,table)}
    return ([after[k] for k in after.keys()-before.keys()], [before[k] for k in before.keys()-after.keys()], [(before[k],after[k]) for k in before.keys()&after.keys() if before[k]!=after[k]])

def same_except(a,b,*keys):
    return {k:v for k,v in a.items() if k not in keys}=={k:v for k,v in b.items() if k not in keys}

def clauses(answer):
    answer = re.sub(r"(?m)^\s*[-*]\s*", "", answer)
    answer = re.sub(r'(?i)(total|renewal price|introductory price)\s*\n+\s*(?:[-*]\s*)?(?=\$)', r'\1 ', answer)
    # Preserve decimal points; clauses also support bullet lists and table rows.
    return [s.strip().casefold().replace('’',"'") for s in re.split(r'\n|;|,?\s+and the\s+|,?\s+whereas\s+|,?\s+while\s+|(?<=[.!?])\s+(?=[A-Z])',answer)]

def fact(answer,entity,pattern):
    return any(re.search(entity,c,re.I) and re.search(pattern,c,re.I)
               and not re.search(r'\b(?:incorrect|wrong|never)\b|\b(?:is|was|are|were) not\b|\bnot\s+\$',c)
               for c in clauses(answer))

def amount(value):
    whole,dec=f'{float(value):.2f}'.split('.')
    # Dollar sign or a currency word is required; grouping separators are optional.
    digits=r'[, ]?'.join([whole[max(0,len(whole)-i-3):len(whole)-i] for i in range(0,len(whole),3)][::-1])
    number=digits+(r'(?:\.00)?' if dec=='00' else r'\.'+dec)
    return r'(?:\$\s*'+number+r'(?!\d|\.\d)|(?<![\d.])'+number+r'\s*(?:USD|dollars)\b)'

def number(value):
    value=float(value)
    base=f'{value:g}'
    return r'(?<![\d.])'+re.escape(base)+r'(?:\.0+)?(?!\d|\.\d)' if value.is_integer() else r'(?<![\d.])'+re.escape(base)+r'(?!\d|\.\d)'

def current_task(judge,traj,site):
    tasks=[json.loads(l) for l in (Path(__file__).parents[1]/'tasks.jsonl').read_text().splitlines()]
    task=next((t for t in tasks if t['id']==traj.get('task_id')),None)
    judge.check('current_task_prompt',bool(task) and traj.get('task')==task['ques'],'trajectory must identify the reviewed task, not a stale prompt')
    return int(traj['task_id'].split('--')[-1])

def order_integrity(judge,a,b,site,user):
    orders,removed,changed=delta(a,b,'orders');items,ri,ci=delta(a,b,'order_items')
    judge.check('preserve_existing_orders',not removed and not changed and len(orders)==1,'one new order; all previous orders unchanged')
    judge.check('preserve_existing_order_items',not ri and not ci,'previous order lines unchanged')
    if len(orders)!=1:return
    order=orders[0];oid=order['id']
    judge.check('order_owner_status',order['user_id']==user and order['status']=='Processing','correct buyer and processing status')
    judge.check('order_item_ownership',bool(items) and all(x['order_id']==oid for x in items),'all new lines belong to this order')
    subtotal=round(sum(x['unit_price']*x['quantity'] for x in items),2)
    judge.check('order_subtotal',abs(subtotal-order['subtotal'])<.005,'subtotal equals ordered lines')
    if site=='macys_wine_shop':
        bottles=sum(x['quantity']*x['bottle_count'] for x in items);shipping=0 if bottles==0 or bottles>=6 else 14.95;processing=2.95 if bottles else 0
        judge.check('wine_order_fees',order['bottle_count']==bottles and order['shipping']==shipping and order['processing']==processing,'actual wine bottles determine fees')
        judge.check('wine_order_total',abs(order['total']-round(subtotal+shipping+processing,2))<.005,'consistent total')
        variants={x['id']:x for x in rows(a,'product_variants')}
        products={x['id']:x for x in rows(a,'products')}
        judge.check('order_variants',all(x['variant_id'] in variants and x['product_handle']==products[variants[x['variant_id']]['product_id']]['handle'] and x['unit_price']==variants[x['variant_id']]['price'] and x['bottle_count']==variants[x['variant_id']]['bottle_count'] and x['quantity']>0 for x in items),'source variant price, count and quantity')
    else:
        judge.check('order_total_arithmetic',abs(order['total']-round(subtotal-order['discount']+order['shipping']+order['tax'],2))<.005,'consistent total')
        products={x['id']:x for x in rows(a,'products')}
        judge.check('ordered_product_prices',all(x['product_id'] in products and x['unit_price']==products[x['product_id']]['price'] and x['quantity']>0 for x in items),'catalog price and positive quantity')
        def valid_selection(item):
            colors=[c for c in rows(a,'product_colors') if c['product_id']==item['product_id']]
            if not colors:return True
            selected=next((c for c in colors if c['color'].casefold()==item['color'].casefold()),None)
            if selected is None:return False
            sizes=json.loads(selected['sizes_json'] or '[]')
            return not sizes or any(str(s['size']).casefold()==item['size'].casefold() and s.get('available') for s in sizes)
        judge.check('available_order_selection', all(valid_selection(x) for x in items), 'ordered color and size are available for their product')

    ac,rc,cc=delta(a,b,'cart_items')
    expected=[x for x in rows(a,'cart_items') if x['user_id']==user] if user is not None else []
    judge.check('cart_owner_preservation',not ac and not cc and sorted(x['id'] for x in rc)==sorted(x['id'] for x in expected),'only buyer cart is consumed; other carts unchanged')
