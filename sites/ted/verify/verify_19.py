#!/usr/bin/env python3
"""Verifier for TED--19: filtered TEDNext culture view-count comparison."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,contains_all,Judge,parse_args
NAYEEMA='nayeema-raza-3-habits-to-practice-curiosity-and-escape-your-phone'
KATE='kate-canales-the-accidental-brilliance-of-makeshift-signs'
def main():
 a=parse_args(); j=Judge('TED--19',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); urls=' '.join(s.get('url','') for s in t.get('steps',[]))
 j.check('nav_filtered_tednext_culture_under10','/talks?' in urls and 'event=TEDNext' in urls and 'topic=culture' in urls and 'max_minutes=10' in urls,f'urls={urls!r}')
 j.check('nav_nayeema',navigated_to(t,NAYEEMA),f'navigated={navigated_to(t,NAYEEMA)}'); j.check('nav_kate',navigated_to(t,KATE),f'navigated={navigated_to(t,KATE)}')
 j.check('answer_nayeema_higher_difference',contains_all(fa,['Nayeema','351132']),f'final={fa!r}'); j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
