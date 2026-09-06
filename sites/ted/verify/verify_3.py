#!/usr/bin/env python3
"""Verifier for TED--3 playlist title answer."""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify_lib import load_run,navigated_to,final_answer,contains_any,Judge,parse_args
TITLES=['Conservation: a love story','A cheat sheet for accelerating clean energy','How to make transportation quieter, cleaner and cheaper','What China can teach the world about scaling clean energy','The controversial climate tool funding real change']
def main():
 a=parse_args(); j=Judge('TED--3',a.no_llm); t=load_run(a.run_dir); fa=final_answer(t); j.check('nav_climate_playlist',navigated_to(t,'playlists/climate-nature-conservation'),f'navigated={navigated_to(t,"playlists/climate-nature-conservation")}'); j.check('answer_names_summit_talk_title',contains_any(fa,TITLES),f'final={fa!r}'); j.check('final_answer_nonempty',bool(fa),f'final={fa!r}'); j.emit()
if __name__=='__main__': main()
