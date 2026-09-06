#!/usr/bin/env python3
"""Verifier for TED--11 filtered TED2026 under-10 navigation."""
import os,sys
from urllib.parse import parse_qs,urlparse
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,Judge,parse_args
SLUG='maya-higa-the-wildlife-sanctuary-you-can-visit-from-anywhere'
def main():
 a=parse_args(); j=Judge('TED--11',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); ok=False
 for s in t.get('steps',[]):
  u=s.get('url',''); q=parse_qs(urlparse(u).query)
  if urlparse(u).path=='/talks' and q.get('event')==['TED2026'] and q.get('max_minutes')==['10']: ok=True; break
 j.check('nav_filtered_ted2026_under10',ok,f'filtered={ok}'); j.check('nav_maya_higa',navigated_to(t,SLUG),f'navigated={navigated_to(t,SLUG)}'); j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
