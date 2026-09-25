"""Reviewed JCPenney outcome contracts and exact ownership preservation."""
import re
from verify_lib import (check_trajectory_identity,check_read_only,check_visited_path,
    check_only_tables_changed,check_signed_in_as,final_answer,contains_phrase,site_urls)
from review_common import rows,delta,same_except,current_task,fact,amount,number,order_integrity


def review(judge,traj,a,b,original):
    i=current_task(judge,traj,'jcpenney');answer=final_answer(traj)
    if i==10:
        check_trajectory_identity(judge,traj,'JCPenney--10');check_signed_in_as(judge,traj,'david.k@test.com')
        for path in ['/account/dashboard/wishlist','/p/papell-boutique-womens-v-neck-short-sleeve-cap-evening-gown/ppr5008618161','/checkout/review']:
            check_visited_path(judge,traj,'visit_'+path,path)
        check_only_tables_changed(judge,a,b,{'orders','order_items','cart_items'})
        items=delta(a,b,'order_items')[0];orders=delta(a,b,'orders')[0]
        judge.check('only_gift_gown',len(items)==1 and items[0]['product_id']==1 and items[0]['quantity']==1 and items[0]['unit_price']==89.59 and bool(items[0]['color']) and bool(items[0]['size']),'one selected gown, no unrelated bag items')
        message='Congratulations on your graduation! Love, Aunt June'
        if len(orders)==1:
            o=orders[0]
            judge.check('gift_order',o['gift_message']==message and o['coupon_code']=='' and o['subtotal']==89.59 and o['shipping']==0 and o['tax']==7.39 and o['total']==96.98,'gift message and single-gown total')
        judge.check('report_gown',contains_phrase(answer,'Papell') and message in answer,'names gift and echoes requested message')
    elif i==13:
        check_trajectory_identity(judge,traj,'JCPenney--13');check_signed_in_as(judge,traj,'david.k@test.com')
        check_read_only(judge,a,b)
        for path in ['/account/dashboard/orders','/orders/JCP2609203008']:check_visited_path(judge,traj,'visit_'+path,path)
        item=next(x for x in rows(a,'order_items') if x['order_id']==8)
        p=next(x for x in rows(a,'products') if x['id']==item['product_id'])
        path=f"/p/{p['slug']}/{p['ppid']}";check_visited_path(judge,traj,'current_dress',path)
        for label,pat in [('order_number',r'JCP2609203008'),('order_status',r'processing'),('order_total',amount(53.28))]:judge.check(label,fact(answer,r'JCP2609203008|order',pat),'pending order fact')
        judge.check('dress_paid',fact(answer,r'paid|order price',amount(item['unit_price'])),'price paid for dress')
        judge.check('dress_current',fact(answer,r'current|catalog',amount(p['price'])),'current catalog price')
        relation='same|unchanged|equal' if p['price']==item['unit_price'] else ('more|higher' if p['price']>item['unit_price'] else 'less|lower')
        judge.check('price_comparison',bool(re.search(relation,answer,re.I)),'correct current-vs-paid comparison')
    else:original(judge,traj,a,b)
    if i in [3,4,5,7,8,10,14]:
        user={3:1,4:5,5:3,7:3,8:2,10:4,14:1}[i]
        order_integrity(judge,a,b,'jcpenney',user)
        orders=delta(a,b,'orders')[0]
        if len(orders)==1:
            o=orders[0]
            if i != 14: judge.check('actual_order_in_answer',contains_phrase(answer,o['order_number']),'answer matches the actual order number')
            judge.check('actual_total_in_answer',fact(answer,r'total',amount(o['total'])),'answer attributes actual total to order')
            judge.check('confirmation_for_order',any('/checkout/confirmation/'+o['order_number'] in u for u in site_urls(traj)),'confirmation belongs to placed order')
            if i!=4:
                addr=next(x for x in rows(a,'addresses') if x['user_id']==user and x['is_default'])
                judge.check('default_shipping',o['ship_name']==addr['first_name']+' '+addr['last_name'] and o['ship_city']==addr['city'] and o['ship_state']==addr['state'] and o['ship_zip']==addr['zip'] and o['ship_phone']==addr['phone'],'requested default shipping identity')
                if i!=8:
                    card=next(x for x in rows(a,'payment_methods') if x['user_id']==user and x['is_default'])
                    judge.check('default_payment',o['payment_type']==card['card_type'] and o['payment_last4']==card['last4'],'requested default card')
    if i==12:
        for entity,price,rating,count in [('Hope Stacked Heel Booties',27.99,5,2),('Inca',36.39,3.8,8)]:
            # Catalog determines the current price; the snapshot's displayed rating is rounded.
            p=next(x for x in rows(a,'products') if entity.casefold() in x['name'].casefold())
            judge.check(entity+'_price',fact(answer,entity,amount(p['price'])),'price attributed to shoe')
            judge.check(entity+'_rating',fact(answer,entity,number(rating)+r'\s*(?:stars|out of 5|/5)'),'rating attributed to shoe')
            judge.check(entity+'_reviews',fact(answer,entity,number(count)+r'\s+reviews'),'review count attributed to shoe')
        judge.check('review_tradeoff',bool(re.search(r'(?:fewer|only|small|limited).{0,40}(?:review|sample)|(?:more|eight|8).{0,20}reviews',answer,re.I)),'recognizes difference in review support')
