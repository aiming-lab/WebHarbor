#!/usr/bin/env python3
"""Verifier for TED--13 science wine-tasting speaker."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,contains_all,Judge,parse_args
SLUG='qian-janice-wang-the-art-and-science-of-wine-tasting'
def main():
 a=parse_args(); j=Judge('TED--13',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); j.check('nav_wine_talk',navigated_to(t,SLUG),f'navigated={navigated_to(t,SLUG)}'); j.check('answer_speaker_exact',contains_all(fa,['Qian Janice Wang']),f'final={fa!r}'); j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
