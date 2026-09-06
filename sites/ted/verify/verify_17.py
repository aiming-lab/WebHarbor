#!/usr/bin/env python3
"""Verifier for TED--17 TEDNext 2025 month."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,contains_all,Judge,parse_args
def main():
 a=parse_args(); j=Judge('TED--17',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); j.check('nav_events',navigated_to(t,'/events'),f'navigated={navigated_to(t,"/events")}'); j.check('answer_tednext_november_2025',contains_all(fa,['november','2025']),f'final={fa!r}'); j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
