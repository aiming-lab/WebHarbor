#!/usr/bin/env python3
"""Verifier for TED--18: filtered TED2026 AI view-count comparison."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,contains_all,extract_ints,Judge,parse_args
PETER='peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent'
ANIL='anil-seth-why-ai-is-unlikely-to-become-conscious'
def main():
 a=parse_args(); j=Judge('TED--18',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); urls=' '.join(s.get('url','') for s in t.get('steps',[]))
 j.check('nav_filtered_ted2026_ai_under20', '/talks?' in urls and 'event=TED2026' in urls and 'topic=ai' in urls and 'max_minutes=20' in urls, f'urls={urls!r}')
 j.check('nav_peter',navigated_to(t,PETER),f'navigated={navigated_to(t,PETER)}'); j.check('nav_anil',navigated_to(t,ANIL),f'navigated={navigated_to(t,ANIL)}')
 j.check('answer_peter_higher_difference',contains_all(fa,['Peter','359862']),f'final={fa!r}')
 j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
