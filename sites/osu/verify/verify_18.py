#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--18';PATH='/research/james-cancer-hospital-and-solove-research-institute'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_james_navigation',visited_in_order(t,[('/research',{}),(PATH,{})]) and clicked_transition(t,'/research',PATH),'research to James');j.check('answer_director_focus',contains_all(answer,('William Farrar','Cancer research','Oncology','Clinical trials','Precision medicine')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()
