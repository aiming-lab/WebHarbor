"""Bind numerical claims and expanded content to their research outcomes."""
from verify_lib import final_answer, affirms, shot_at
from reviewed_contract import CONTRACT
from answer_checks import numeric_claim

def check_research(j, number, traj):
    text = final_answer(traj)
    plans = {
        0: [(r'last(?: price)?',14.87),(r'\bopen\b',14.84),(r'\bhigh\b',15.13),(r'\blow\b',14.60),(r'change(?: for the day)?',0.06)],
        1: [(r'previous close',7764.70),(r'\biv30\b(?: on the overview panel)?',11.793)],
        2: [(r'call open interest',230492),(r'put open interest',543294),(r'put/call ratio(?: \(volume\))?',.95)],
        3: [(r'last(?: price)?',.25),(r'open interest',944)],
        4: [(r'last(?: price)?',18.80),(r'open interest',182967)],
        8: [(r'total put/call ratio',.81),(r'index put/call ratio',.98)],
        23: [(r'\bvolume\b',6498237),(r'open interest',20716226),(r'(?:contract )?multiplier(?: for SPX index options(?: shown in the comparison calculator)?)?',100)],
    }
    for label, value in plans.get(number,[]):
        j.check('bound_fact_'+label, numeric_claim(text,label,value), f'{label}: {value}')
    if number == 0:
        j.check('positive_day_change', not __import__('re').search(r'(?:-0\.0?6|-0\.40|fell|decreased|declined)',text,__import__('re').I), 'VIX rose, rather than fell')
    spec=CONTRACT['revised'].get(str(number),{})
    if spec.get('kind')=='class':
        j.check('registration_confirmation_title', affirms(text,'Liquidity Awareness in Strategy Selection'), 'Registered class title')
        j.check('registration_confirmation_instructor', affirms(text,'Mark Phillips'), 'Registered instructor')
    if number in [18,22]:
        needle='zero days to expiration' if number==18 else '14 years'
        evidence=' '.join(str(s.get('observed_text','')) for s in traj.get('steps',[]) if '/optionsinstitute/' in s.get('url',''))
        j.check('expanded_research_content', needle in evidence.casefold(), 'The definition or biography must have been expanded and read')
