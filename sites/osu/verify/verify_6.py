#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--6';PATH='/research/translational-data-analytics-institute'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_tdai_navigation',visited_in_order(t,[('/research',{}),(PATH,{})]) and clicked_transition(t,'/research',PATH),'research listing to TDAI');j.check('answer_director_and_focus',contains_all(answer,('Beth Plale','Data analytics','Machine learning','Health informatics','Social science')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()
