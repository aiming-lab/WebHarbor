#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, has_number, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--11';PATH='/research/ohio-supercomputer-center'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_osc_navigation',visited_in_order(t,[('/research',{}),(PATH,{})]) and clicked_transition(t,'/research',PATH),'research to OSC');j.check('answer_director_and_year',contains_all(answer,('David Bickel',)) and has_number(answer,1987),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()
