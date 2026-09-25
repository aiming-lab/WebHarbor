"""Research contracts for multi-page comparisons in the reviewed BBB tasks."""
import re
from urllib.parse import urlsplit, parse_qs
from verify_lib import final_answer, affirms, affirms_any, shot_at, navigated_path, step_urls
from answer_checks import numeric_claim

def query(traj,path,**wanted):
    for url in step_urls(traj):
        u=urlsplit(url);p=parse_qs(u.query)
        if u.path.rstrip('/')==path.rstrip('/') and all(p.get(k,[''])[0].casefold()==v.casefold() for k,v in wanted.items()):return True
    return False

def check_research(j,n,traj):
    text=final_answer(traj)
    lookup='/scamtracker/lookupscam'
    def page(path):j.check('research_page_'+path,navigated_path(traj,path) and shot_at(traj,path)[0],path)
    if n in [15,17,20]:
        for path in [lookup+'/1388290',lookup+'/1429698']:page(path)
        j.check('scam_locations',bool(re.search(r'1388290[^;\n]*Seattle[^;\n]*WA',text,re.I)) and bool(re.search(r'Blue Heart Advocacy[^;\n]*Miami[^;\n]*FL',text,re.I)), 'Bind each location to the correct report')
        for entity,amount in [('1388290',700),('Blue Heart Advocacy',0)]:
            segments=[s for s in re.split(r'[;\n]|\.(?=\s|$)',text) if entity.casefold() in s.casefold() and 'loss' in s.casefold()]
            segment='; '.join(re.split(re.escape(entity),s,flags=re.I)[-1] for s in segments)
            j.check('report_loss_'+entity,numeric_claim(segment,r'(?:loss|lost)',amount),entity)
        j.check('loss_difference',numeric_claim(text,r'difference(?: in reported losses)?',700),'Difference $700')
        if n==15:
            j.check('report_dates',bool(re.search(r'(August 11|2026-08-11)',text,re.I)) and bool(re.search(r'(September 19|2026-09-19)',text,re.I)),'Both report dates')
    if n==18:
        j.check('wa_charity_lookup',query(traj,lookup,scam_type='Charity',state='WA'),'WA Charity filter')
        j.check('operation_count',bool(re.search(r'\b6\s+reports\b',text)),'Six Rise Up Youth reports')
        j.check('combined_loss',numeric_claim(text,r'combined(?: reported)? loss',6985),'Combined loss $6,985')
    if n in [19,25]:
        page('/us/news/bbb-tip-don-t-get-scammed-out-of-a-gift-card')
        j.check('gift_card_advice',affirms_any(text,['tamper','fraudulent','substituted']) and affirms(text,'barcode') and affirms_any(text,['sticker','cover']) and affirms_any(text,['scammer','criminal']), 'Check barcode tampering and explain payment diversion')
    if n==21:
        j.check('crypto_minimum',query(traj,lookup,scam_type='CryptoCurrency',min_dollars='1000'),'Apply $1,000 minimum loss')
        page(lookup+'/1426837')
        j.check('filtered_count',bool(re.search(r'\b19\s+(?:search\s+)?results',text,re.I)),'19 filtered results')
        j.check('filtered_location_date',affirms(text,'Lexington') and affirms(text,'NC') and bool(re.search(r'(September 17|2026-09-17)',text,re.I)),'Lexington NC, September 17')
        j.check('filtered_loss',numeric_claim(text,r'(?:qualifying report(?:\s+in Lexington, NC)?[^;\n]{0,40})?loss',2000) or bool(re.search(r'Lexington[^;\n]*\$2,?000',text,re.I)), '$2,000 for newest qualifying report')
        j.check('unfiltered_loss',bool(re.search(r'(?:newest unfiltered|Palm Desert)[^;\n]*\$200\b',text,re.I)), '$200 for original newest report')
    if n in [22,28]:
        j.check('gift_search',query(traj,lookup,q='gift card'),'Search descriptions for gift card')
        j.check('gift_search_count',bool(re.search(r'\b7\s+results',text,re.I)),'Seven public reports')
        j.check('gift_search_types',sum(affirms(text,t) for t in ['Charity','Romance','Tech Support','Utility'])>=3,'At least three supported scam types')
        if n==28:j.check('private_report_distinction',bool(re.search(r'(not part|not included|separate from)[^.;\n]*(public|lookup)',text,re.I)),'Alice\'s private submission is separate')
    if n==23:
        page('/us/news/bbb-scam-alert-use-caution-when-searching-for-weight-loss-products-online')
        j.check('weight_loss_mechanism',affirms_any(text,['AI-generated','deep-fake','deepfake']) and affirms_any(text,['doctor','celebrity','celebrities']) and affirms(text,'LipoMax') and bool(re.search(r'\b170\s+reports',text,re.I)),'Impersonation, product, report count')
    if n==24:
        page('/get-accredited')
        j.check('operating_history',bool(re.search(r'\b90\s+days',text,re.I)),'At least 90 days')
        j.check('honor_promises',affirms_any(text,['Honor promises','honoring promises']) and affirms_any(text,['written agreements','agreements','commitments']),'Honor promises')
        j.check('car_tender_accreditation',affirms(text,'Car Tender') and affirms(text,'Accredited') and bool(re.search(r'(April 1,? 2000|4/1/2000)',text,re.I)),'Accredited since April 1, 2000')
